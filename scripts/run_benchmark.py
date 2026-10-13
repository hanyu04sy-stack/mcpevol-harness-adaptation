#!/usr/bin/env python3
"""Unified entry point for Early, Middle, and Late benchmark runs."""

from __future__ import annotations

import argparse
import json
import os
import runpy
import string
import sys
import threading
import urllib.request
import time
from collections.abc import Callable
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from urllib.parse import urlsplit

from experiment_config import (
    ConfigError,
    VERSIONS,
    load_env_file,
    load_experiment,
    public_summary,
    resolve_runtime_credentials,
    sha256,
    validate_endpoint_model_consistency,
)
from rate_limit_retry import call_with_rate_limit_retry, new_retry_audit


HARNESS_FILENAMES = ("system_prompt.md", "tool_usage_rules.md", "manifest.json")


def injected_tool_rules(document: str) -> str:
    """Return only the prompt-bearing section of the documented tool rules."""
    marker = "## Injected rules"
    if marker not in document:
        return document.strip()
    section = document.split(marker, 1)[1]
    if "\n## " in section:
        section = section.split("\n## ", 1)[0]
    return section.strip()


def load_harness(harness_dir: Path, benchmark_commit: str) -> dict[str, object]:
    """Load, validate, and audit a harness-knowledge directory."""
    directory = harness_dir.resolve()
    if not directory.is_dir():
        raise ConfigError(f"harness directory does not exist: {directory}")
    paths = {name: directory / name for name in HARNESS_FILENAMES}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ConfigError(f"harness directory is incomplete; missing={missing}")

    try:
        manifest = json.loads(paths["manifest.json"].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read harness manifest: {exc}") from exc
    if manifest.get("benchmark_commit") != benchmark_commit:
        raise ConfigError(
            "harness manifest benchmark commit does not match the experiment"
        )
    source_files = manifest.get("source_files")
    if not isinstance(source_files, list) or not source_files:
        raise ConfigError("harness manifest must record at least one source file")

    system_prompt = paths["system_prompt.md"].read_text(encoding="utf-8")
    fields = {
        name
        for _, name, _, _ in string.Formatter().parse(system_prompt)
        if name is not None
    }
    if fields != {"SET_TIME", "FILE_EXISTS"}:
        raise ConfigError(
            "system_prompt.md must contain exactly {SET_TIME} and {FILE_EXISTS}"
        )
    rules_document = paths["tool_usage_rules.md"].read_text(encoding="utf-8")
    rules = injected_tool_rules(rules_document)
    if not rules:
        raise ConfigError("tool_usage_rules.md has no injectable rules")

    resolved_prompt = system_prompt
    if rules not in system_prompt:
        resolved_prompt = f"{system_prompt.rstrip()}\n\n{rules}\n"
    files = [
        {"name": name, "sha256": sha256(path)}
        for name, path in paths.items()
    ]
    return {
        "harness_dir": directory,
        "harness_manifest_sha256": sha256(paths["manifest.json"]),
        "harness_files": files,
        "harness_prompt": resolved_prompt,
    }


def check_mcp(resolved: dict[str, object]) -> dict[str, int]:
    parsed = urlsplit(str(resolved["mcp_url"]))
    inspect_url = f"{parsed.scheme}://{parsed.netloc}/api/v1/inspect"
    try:
        with urllib.request.urlopen(inspect_url, timeout=20) as response:
            servers = json.load(response)["servers"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ConfigError(
            f"MCP environment is not ready at {resolved['mcp_url']}: {exc}"
        ) from exc
    expected = set(
        json.loads(Path(resolved["server_config"]).read_text(encoding="utf-8"))[
            "mcpServers"
        ]
    )
    observed = {server["server"] for server in servers}
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise ConfigError(
            f"MCP server set mismatch; missing={missing}, extra={extra}"
        )
    unavailable = {
        server["server"]: server.get("status", "unknown")
        for server in servers
        if server.get("status") != "connected" or server.get("available") is not True
    }
    if unavailable:
        detail = ", ".join(
            f"{name}({status})" for name, status in sorted(unavailable.items())
        )
        raise ConfigError(f"MCP task dependencies are unavailable: {detail}")
    return {
        "observed_servers": len(servers),
        "connected_servers": sum(s["status"] == "connected" for s in servers),
        "available_tools": sum(
            int(s["toolCount"]) for s in servers if s["status"] == "connected"
        ),
    }


def upstream_arguments(resolved: dict[str, object]) -> list[str]:
    arguments = [
        str(resolved["benchmark_runner"]),
        "--step",
        str(resolved["runner_step"]),
        "--model_name",
        str(resolved["model_name"]),
        "--test_case_file",
        str(resolved["task_file"]),
        "--mcp_server_url",
        str(resolved["mcp_url"]),
        "--output_path",
        str(resolved["output_dir"]),
        "--part_num",
        str(resolved["runner_part_num"]),
        "--part_idx",
        str(resolved["runner_part_idx"]),
    ]
    if resolved["runner_fschat"]:
        arguments.append("--fschat_flag")
    return arguments


def resolve_run_output(resolved: dict[str, object], run_id: int) -> Path:
    """Use the shared strategy/version/run-NN layout for formal runs."""
    if run_id < 1:
        raise ConfigError("run-id must be positive")
    strategy = Path(resolved["harness_dir"]).name
    if not strategy or strategy in {".", ".."}:
        raise ConfigError("cannot derive a strategy name from harness directory")
    output = Path(resolved["output_root"]) / strategy / str(resolved["version"]) / f"run-{run_id:02d}"
    resolved["strategy"] = strategy
    resolved["run_id"] = run_id
    resolved["output_dir"] = output.resolve()
    return output.resolve()


def configured_initializer(
    original_init: Callable[..., None],
    resolved: dict[str, object],
    api_key: str,
    base_url: str | None,
) -> Callable[..., None]:
    """Wrap the upstream agent so shared settings replace its placeholders."""
    usage_lock = resolved.setdefault("_usage_lock", threading.Lock())
    retry_audit = resolved.setdefault(
        "rate_limit_retry",
        new_retry_audit(int(resolved["openai_max_retries"])),
    )

    def configured_init(instance: object, *args: object, **kwargs: object) -> None:
        kwargs["api_key"] = api_key
        kwargs["model_url"] = base_url
        kwargs["temperature"] = resolved["temperature"]
        kwargs["max_new_tokens"] = resolved["max_completion_tokens"]
        original_init(instance, *args, **kwargs)
        instance.client.timeout = resolved["openai_timeout_seconds"]
        # Disable the SDK's opaque retry loop; the wrapper below records every 429.
        instance.client.max_retries = 0
        original_create = instance.client.chat.completions.create

        def tracked_create(*call_args: object, **call_kwargs: object) -> object:
            response = call_with_rate_limit_retry(
                lambda: original_create(*call_args, **call_kwargs),
                max_retries=int(resolved["openai_max_retries"]),
                audit=retry_audit,
                lock=usage_lock,
            )
            usage = getattr(response, "usage", None)
            reported_model = getattr(response, "model", None)
            prompt_tokens = getattr(usage, "prompt_tokens", None)
            completion_tokens = getattr(usage, "completion_tokens", None)
            if isinstance(prompt_tokens, int) and not isinstance(prompt_tokens, bool):
                with usage_lock:
                    resolved["total_prompt_tokens"] = int(
                        resolved.get("total_prompt_tokens", 0)
                    ) + max(0, prompt_tokens)
            if isinstance(completion_tokens, int) and not isinstance(
                completion_tokens, bool
            ):
                with usage_lock:
                    resolved["total_completion_tokens"] = int(
                        resolved.get("total_completion_tokens", 0)
                    ) + max(0, completion_tokens)
            if isinstance(reported_model, str) and reported_model.strip():
                with usage_lock:
                    observed = resolved.setdefault("provider_reported_models", [])
                    if reported_model not in observed:
                        observed.append(reported_model)
                    if not resolved.get("provider_reported_model"):
                        resolved["provider_reported_model"] = reported_model
            return response

        instance.chat = partial(
            tracked_create,
            model=instance.model_name,
            temperature=resolved["temperature"],
            max_tokens=resolved["max_completion_tokens"],
        )

    return configured_init


def run_upstream(
    resolved: dict[str, object], api_key: str, base_url: str | None
) -> None:
    benchmark_src = Path(resolved["benchmark_root"]) / "src"
    old_cwd = Path.cwd()
    old_argv = sys.argv[:]
    agent_module = None
    original_init = None
    original_prompt = None
    created_annotation_link = False
    old_dont_write_bytecode = sys.dont_write_bytecode
    annotation_link = benchmark_src / "anotation_path"
    annotation_target = Path(resolved["benchmark_root"]) / "anotation_path"
    if not annotation_link.exists() and annotation_target.is_dir():
        annotation_link.symlink_to(Path("..") / "anotation_path", target_is_directory=True)
        created_annotation_link = True
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(benchmark_src))
    os.chdir(benchmark_src)
    try:
        from custom.agents import SimpleOpenAIAgent as agent_module

        original_init = agent_module.ChatModel.__init__
        original_prompt = agent_module.SINGLE_SERVER_INTERATION_SYSTEM_PROMPT
        agent_module.SINGLE_SERVER_INTERATION_SYSTEM_PROMPT = str(
            resolved["harness_prompt"]
        )
        agent_module.ChatModel.__init__ = configured_initializer(
            original_init, resolved, api_key, base_url
        )
        sys.argv = upstream_arguments(resolved)
        runpy.run_path(str(resolved["benchmark_runner"]), run_name="__main__")
    finally:
        if agent_module is not None and original_init is not None:
            agent_module.ChatModel.__init__ = original_init
        if agent_module is not None and original_prompt is not None:
            agent_module.SINGLE_SERVER_INTERATION_SYSTEM_PROMPT = original_prompt
        sys.argv = old_argv
        os.chdir(old_cwd)
        if sys.path and sys.path[0] == str(benchmark_src):
            sys.path.pop(0)
        sys.dont_write_bytecode = old_dont_write_bytecode
        if created_annotation_link and annotation_link.is_symlink():
            annotation_link.unlink()


def write_metadata(
    resolved: dict[str, object],
    mcp_status: dict[str, int],
    status: str,
    *,
    wall_clock_seconds: float | None = None,
) -> Path:
    output_dir = Path(resolved["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "run-metadata.json"
    payload = public_summary(resolved)
    payload.update(
        {
            "strategy": resolved["strategy"],
            "run_id": resolved["run_id"],
            "model": {
                "provider": resolved["model_provider"],
                "name": resolved["model_name"],
                "temperature": resolved["temperature"],
                "max_completion_tokens": resolved["max_completion_tokens"],
                "api_key_env": resolved["model_api_key_env"],
                "timeout_seconds": resolved["openai_timeout_seconds"],
                "max_retries": resolved["openai_max_retries"],
                "provider_reported_model": resolved.get(
                    "provider_reported_model"
                ),
                "provider_reported_models": list(
                    resolved.get("provider_reported_models", [])
                ),
            },
            "rate_limit_retry": dict(resolved.get("rate_limit_retry", {})),
            "judge": {
                "name": resolved["judge_name"],
                "temperature": resolved["judge_temperature"],
                "api_key_env": resolved["judge_api_key_env"],
            },
            "status": status,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "mcp_status_at_start": mcp_status,
            "total_prompt_tokens": int(resolved.get("total_prompt_tokens", 0)),
            "total_completion_tokens": int(
                resolved.get("total_completion_tokens", 0)
            ),
            "wall_clock_seconds": wall_clock_seconds,
            "secrets_recorded": False,
        }
    )
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=VERSIONS, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/experiment.json"))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--run-id", type=int, default=1)
    parser.add_argument(
        "--harness-dir",
        type=Path,
        help="Harness knowledge directory; overrides harness.default_dir",
    )
    parser.add_argument(
        "--print-resolved-prompt",
        action="store_true",
        help="Print the exact harness prompt after validation and deduplication",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print resolved settings without secrets, MCP, or API calls",
    )
    args = parser.parse_args()
    try:
        resolved = load_experiment(args.config, args.version)
        if args.harness_dir is not None:
            override = args.harness_dir
            if not override.is_absolute():
                override = Path(resolved["project_root"]) / override
            resolved["harness_dir"] = override.resolve()
        resolved.update(
            load_harness(
                Path(resolved["harness_dir"]), str(resolved["benchmark_commit"])
            )
        )
        formal_run = Path(resolved["config_path"]).name == "experiment.json"
        if formal_run:
            resolve_run_output(resolved, args.run_id)
        else:
            resolved["strategy"] = Path(resolved["harness_dir"]).name
            resolved["run_id"] = args.run_id
        env_file = (args.env_file or Path(resolved["env_file"])).resolve()
        load_env_file(env_file)
        resolve_runtime_credentials(resolved)
        resolved["effective_endpoint"] = resolved["model_base_url_resolved"]
        validate_endpoint_model_consistency(
            str(resolved["model_name"]), str(resolved["model_base_url_resolved"])
        )
        print(json.dumps(public_summary(resolved), ensure_ascii=False, indent=2))
        print("upstream_argv=" + json.dumps(upstream_arguments(resolved)))
        if args.print_resolved_prompt:
            print("--- resolved harness prompt ---")
            print(str(resolved["harness_prompt"]), end="")
            print("--- end resolved harness prompt ---")
        if args.dry_run:
            return

        key_name = str(resolved["model_api_key_env"])
        api_key = str(resolved["model_api_key_resolved"])
        base_url = str(resolved["model_base_url_resolved"]) or None
        if not api_key:
            raise ConfigError(
                f"missing {key_name}; copy .env.example to .env and fill it locally"
            )
        if formal_run:
            from verify_untouched import check_fairness, verify_run_metadata_model

            fairness = check_fairness(
                config_path=Path(resolved["config_path"]),
                pins_path=Path(resolved["project_root"]) / "configs/fairness-pins.json",
                report_path=Path(resolved["project_root"]) / "reports/fairness-check.json",
                root=Path(resolved["project_root"]),
            )
            if not fairness["passed"]:
                raise ConfigError("fairness guard failed; see reports/fairness-check.json")
        mcp_status = check_mcp(resolved)
        resolved["total_prompt_tokens"] = 0
        resolved["total_completion_tokens"] = 0
        resolved["provider_reported_model"] = None
        resolved["provider_reported_models"] = []
        resolved["rate_limit_retry"] = new_retry_audit(
            int(resolved["openai_max_retries"])
        )
        resolved["_usage_lock"] = threading.Lock()
        started = time.monotonic()
        metadata = write_metadata(resolved, mcp_status, "running")
        if formal_run:
            verify_run_metadata_model(
                metadata,
                Path(resolved["project_root"]) / "configs/fairness-pins.json",
            )
        try:
            run_upstream(resolved, api_key, base_url)
        except BaseException:
            write_metadata(
                resolved,
                mcp_status,
                "failed",
                wall_clock_seconds=round(time.monotonic() - started, 3),
            )
            raise
        write_metadata(
            resolved,
            mcp_status,
            "completed",
            wall_clock_seconds=round(time.monotonic() - started, 3),
        )
        print(f"Run completed; metadata: {metadata}")
        print(
            "Now run: .venv/bin/python scripts/run_judge.py "
            f"--version {resolved['version']} --harness-dir {resolved['harness_dir']} "
            f"--run-id {resolved['run_id']}"
        )
    except ConfigError as exc:
        raise SystemExit(f"CONFIG ERROR: {exc}") from exc


if __name__ == "__main__":
    main()
