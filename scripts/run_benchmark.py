#!/usr/bin/env python3
"""Unified entry point for Early, Middle, and Late benchmark runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import runpy
import string
import subprocess
import sys
import threading
import urllib.request
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from experiment_config import (
    ConfigError,
    VERSIONS,
    load_env_file,
    load_experiment,
    public_summary,
    sha256,
)


HARNESS_FILENAMES = ("system_prompt.md", "tool_usage_rules.md", "manifest.json")
SHARED_COMPLETION_PROTOCOL = (
    "After the requested tool work is complete, give the final answer beginning "
    "with [FINISH]. Do not repeat successful tool calls merely to produce the final answer."
)


class UsageTotals:
    """Thread-safe OpenAI-compatible response usage accumulator."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._prompt_tokens = 0
        self._completion_tokens = 0
        self._responses = 0

    @staticmethod
    def _value(usage: object, name: str) -> int:
        if isinstance(usage, dict):
            value = usage.get(name, 0)
        else:
            value = getattr(usage, name, 0)
        return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0

    def record(self, response: object) -> None:
        usage = getattr(response, "usage", None)
        if usage is None and isinstance(response, dict):
            usage = response.get("usage")
        if usage is None:
            return
        with self._lock:
            self._prompt_tokens += self._value(usage, "prompt_tokens")
            self._completion_tokens += self._value(usage, "completion_tokens")
            self._responses += 1

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            prompt = self._prompt_tokens
            completion = self._completion_tokens
            responses = self._responses
        return {
            "total_prompt_tokens": prompt,
            "total_completion_tokens": completion,
            "total_tokens": prompt + completion,
            "metered_responses": responses,
        }


def provider_model_id(configured_name: str, base_url: str | None) -> str:
    """Map a canonical OpenAI name to OpenRouter's provider-qualified ID."""
    if base_url and urlsplit(base_url).hostname == "openrouter.ai" and "/" not in configured_name:
        return f"openai/{configured_name}"
    return configured_name


def injected_tool_rules(document: str) -> str:
    """Return only the prompt-bearing section of the documented tool rules."""
    marker = "## Injected rules"
    if marker not in document:
        return document.strip()
    section = document.split(marker, 1)[1]
    if "\n## " in section:
        section = section.split("\n## ", 1)[0]
    return section.strip()


def select_task_harness_prompt(
    resolved: dict[str, object],
    tools: list[dict[str, object]],
    tool_server_map: dict[str, str],
) -> str:
    """Inject only patch sections for the current task's servers and tools."""
    directory = Path(resolved["harness_dir"])
    if directory.parent.name != "selective_patch":
        return str(resolved["harness_prompt"])
    system_prompt = (directory / "system_prompt.md").read_text(encoding="utf-8")
    rules = injected_tool_rules((directory / "tool_usage_rules.md").read_text(encoding="utf-8"))
    sections = re.split(r"(?=^### Tool )", rules, flags=re.MULTILINE)
    base = sections[0].strip()
    available = {(tool_server_map.get(str(tool.get("name"))), str(tool.get("name"))) for tool in tools}
    task_servers = set(tool_server_map.values())
    selected = []
    for section in sections[1:]:
        heading = section.splitlines()[0]
        match = re.fullmatch(r"### Tool (.+) / (.+)", heading)
        if not match:
            raise ConfigError(f"invalid selective patch heading: {heading}")
        server, name = match.groups()
        is_removal = "This tool was removed" in section
        if (server, name) in available or (is_removal and server in task_servers):
            selected.append(section.strip())
    task_rules = "\n\n".join([base, *selected])
    if task_rules in system_prompt:
        return f"{system_prompt.rstrip()}\n\n{SHARED_COMPLETION_PROTOCOL}\n"
    return f"{system_prompt.rstrip()}\n\n{task_rules}\n\n{SHARED_COMPLETION_PROTOCOL}\n"


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
    resolved_prompt = f"{resolved_prompt.rstrip()}\n\n{SHARED_COMPLETION_PROTOCOL}\n"
    files = [
        {"name": name, "sha256": sha256(path)}
        for name, path in paths.items()
    ]
    return {
        "harness_dir": directory,
        "harness_manifest_sha256": sha256(paths["manifest.json"]),
        "harness_files": files,
        "harness_prompt": resolved_prompt,
        "shared_completion_protocol_sha256": hashlib.sha256(
            SHARED_COMPLETION_PROTOCOL.encode("utf-8")
        ).hexdigest(),
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
    # Derive the strategy from the harness path. Versioned harnesses live at
    # harness/<strategy>/<version> (e.g. harness/full_rewrite/early), so the
    # strategy is the path component that names a known strategy, not the last
    # component (which would be the version name).
    known = ("no_update", "full_rewrite", "selective_patch")
    parts = Path(resolved["harness_dir"]).parts
    strategy = next((part for part in parts if part in known), None)
    if strategy is None:
        strategy = Path(resolved["harness_dir"]).name
    directory = Path(resolved["harness_dir"])
    if directory.parent.name == "selective_patch":
        manifest = json.loads((directory / "manifest.json").read_text())
        if manifest.get("strategy") != "selective_patch":
            raise ConfigError("versioned patch must declare selective_patch strategy")
        if manifest.get("target_version") != resolved["version"]:
            raise ConfigError("selective patch target version does not match run version")
        if manifest.get("formal_run_ready") is not True:
            raise ConfigError("selective patch has incomplete schema evidence; regenerate snapshots")
        strategy = "selective_patch"
    if directory.parent.name == "full_rewrite":
        manifest = json.loads((directory / "manifest.json").read_text())
        if manifest.get("strategy") != "full_rewrite":
            raise ConfigError("versioned rewrite must declare full_rewrite strategy")
        if manifest.get("target_version") != resolved["version"]:
            raise ConfigError("full rewrite target version does not match run version")
        strategy = "full_rewrite"
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
    prompt_module: object | None = None,
    usage_totals: UsageTotals | None = None,
) -> Callable[..., None]:
    """Wrap the upstream agent so shared settings replace its placeholders."""
    def configured_init(instance: object, *args: object, **kwargs: object) -> None:
        if prompt_module is not None:
            prompt_module.SINGLE_SERVER_INTERATION_SYSTEM_PROMPT = select_task_harness_prompt(
                resolved,
                kwargs.get("tools", []),
                kwargs.get("tool_server_map", {}),
            )
        kwargs["api_key"] = api_key
        kwargs["model_url"] = base_url
        if "model_name" in kwargs:
            kwargs["model_name"] = provider_model_id(str(kwargs["model_name"]), base_url)
        kwargs["temperature"] = resolved["temperature"]
        kwargs["max_new_tokens"] = resolved["max_completion_tokens"]
        original_init(instance, *args, **kwargs)
        if usage_totals is not None:
            original_chat = getattr(instance, "chat")

            def tracked_chat(*chat_args: object, **chat_kwargs: object) -> object:
                response = original_chat(*chat_args, **chat_kwargs)
                usage_totals.record(response)
                return response

            setattr(instance, "chat", tracked_chat)

    return configured_init


def prepare_annotation_links(resolved: dict[str, object]) -> list[Path]:
    """Expose benchmark assets at both the agent and MCP server working directories."""
    benchmark_root = Path(resolved["benchmark_root"])
    asset_dir = benchmark_root / "anotation_path"
    if not asset_dir.is_dir():
        raise ConfigError(f"benchmark annotation assets are missing: {asset_dir}")

    links = [Path(resolved["project_root"]) / "anotation_path", benchmark_root / "src/anotation_path"]
    created: list[Path] = []
    try:
        for link in links:
            if link.is_symlink():
                if link.resolve() != asset_dir.resolve():
                    raise ConfigError(f"annotation link points to a different directory: {link}")
                continue
            if link.exists():
                raise ConfigError(f"annotation path already exists and cannot be replaced: {link}")
            link.symlink_to(os.path.relpath(asset_dir, link.parent), target_is_directory=True)
            created.append(link)
    except BaseException:
        for link in reversed(created):
            link.unlink()
        raise
    return created


def run_upstream(
    resolved: dict[str, object],
    api_key: str,
    base_url: str | None,
    usage_totals: UsageTotals | None = None,
) -> None:
    benchmark_src = Path(resolved["benchmark_root"]) / "src"
    old_cwd = Path.cwd()
    old_argv = sys.argv[:]
    agent_module = None
    original_init = None
    original_prompt = None
    created_annotation_links: list[Path] = []
    old_dont_write_bytecode = sys.dont_write_bytecode
    try:
        created_annotation_links = prepare_annotation_links(resolved)
        sys.dont_write_bytecode = True
        sys.path.insert(0, str(benchmark_src))
        os.chdir(benchmark_src)
        from custom.agents import SimpleOpenAIAgent as agent_module

        original_init = agent_module.ChatModel.__init__
        original_prompt = agent_module.SINGLE_SERVER_INTERATION_SYSTEM_PROMPT
        agent_module.SINGLE_SERVER_INTERATION_SYSTEM_PROMPT = str(
            resolved["harness_prompt"]
        )
        agent_module.ChatModel.__init__ = configured_initializer(
            original_init,
            resolved,
            api_key,
            base_url,
            prompt_module=agent_module,
            usage_totals=usage_totals,
        )
        import custom.utils.test_utils as benchmark_test_utils

        # D-side documented deviation (see reports/d/fairness-audit.md):
        # The upstream runner filters the pinned test_case_file through its
        # built-in official chosen set (custom/data/test_cases/chosen_idx.json,
        # 201 tasks). That silently drops 7 of the 30 fixed pilot tasks even
        # though they are runnable. Override the filter in memory (identity) so
        # every task in the pinned task file is evaluated. No upstream file is
        # modified; `verify_untouched.py` still passes because the upstream git
        # checkout remains clean. The subset is fixed and identical for every
        # strategy/version/repeat, per the case's "fixed documented subset" rule.
        benchmark_test_utils.clean_all_test_cases = lambda cases: cases

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
        for link in reversed(created_annotation_links):
            if link.is_symlink():
                link.unlink()
        # D-side self-clean (mirrors the canary recipe): the upstream agent
        # writes analysis byproducts (bazi_analysis_report.md,
        # log_analysis_report.md, tasks.md) into the upstream checkout's
        # anotation_path and may rewrite the tracked work.md. Restore the
        # subtree to the pinned commit (checkout tracked + clean untracked)
        # after every cell so the next cell's fairness preflight and the Judge
        # phase pass. Only the anotation_path subtree is touched; all other
        # tracked upstream content is untouched.
        try:
            subprocess.run(
                ["git", "-C", str(Path(resolved["benchmark_root"])), "checkout", "--", "anotation_path"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(Path(resolved["benchmark_root"])), "clean", "-fdq", "--", "anotation_path"],
                check=True,
                capture_output=True,
            )
        except Exception as exc:  # pragma: no cover - cleanup is best effort
            print(f"WARNING: could not clean upstream byproducts: {exc}")


def write_metadata(
    resolved: dict[str, object],
    mcp_status: dict[str, int],
    status: str,
    *,
    wall_clock_seconds: float | None = None,
    usage_totals: UsageTotals | None = None,
) -> Path:
    output_dir = Path(resolved["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "run-metadata.json"
    payload = public_summary(resolved)
    usage = usage_totals.snapshot() if usage_totals is not None else {
        "total_prompt_tokens": None,
        "total_completion_tokens": None,
        "total_tokens": None,
        "metered_responses": None,
    }
    payload.update(
        {
            "strategy": resolved["strategy"],
            "run_id": resolved["run_id"],
            "model": {
                "name": resolved["model_name"],
                "temperature": resolved["temperature"],
                "max_completion_tokens": resolved["max_completion_tokens"],
                "api_key_env": resolved["model_api_key_env"],
            },
            "judge": {
                "name": resolved["judge_name"],
                "temperature": resolved["judge_temperature"],
                "api_key_env": resolved["judge_api_key_env"],
            },
            "status": status,
            "shared_completion_protocol_sha256": resolved.get(
                "shared_completion_protocol_sha256"
            ),
            "provider_model_name": provider_model_id(
                str(resolved["model_name"]),
                os.environ.get(str(resolved["model_base_url_env"]), "") or None,
            ),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "mcp_status_at_start": mcp_status,
            **usage,
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
        print(json.dumps(public_summary(resolved), ensure_ascii=False, indent=2))
        print("upstream_argv=" + json.dumps(upstream_arguments(resolved)))
        if args.print_resolved_prompt:
            print("--- resolved harness prompt ---")
            print(str(resolved["harness_prompt"]), end="")
            print("--- end resolved harness prompt ---")
        if args.dry_run:
            return

        env_file = (args.env_file or Path(resolved["env_file"])).resolve()
        load_env_file(env_file)
        key_name = str(resolved["model_api_key_env"])
        base_name = str(resolved["model_base_url_env"])
        api_key = os.environ.get(key_name, "").strip()
        base_url = os.environ.get(base_name, "").strip() or None
        if not api_key:
            raise ConfigError(
                f"missing {key_name}; copy .env.example to .env and fill it locally"
            )
        if formal_run:
            from verify_untouched import check_fairness

            fairness = check_fairness(
                config_path=Path(resolved["config_path"]),
                pins_path=Path(resolved["project_root"]) / "configs/fairness-pins.json",
                report_path=Path(resolved["project_root"]) / "reports/fairness-check.json",
                root=Path(resolved["project_root"]),
            )
            if not fairness["passed"]:
                raise ConfigError("fairness guard failed; see reports/fairness-check.json")
        mcp_status = check_mcp(resolved)
        started = time.monotonic()
        usage_totals = UsageTotals()
        metadata = write_metadata(
            resolved, mcp_status, "running", usage_totals=usage_totals
        )
        try:
            run_upstream(resolved, api_key, base_url, usage_totals=usage_totals)
        except BaseException:
            write_metadata(
                resolved,
                mcp_status,
                "failed",
                wall_clock_seconds=round(time.monotonic() - started, 3),
                usage_totals=usage_totals,
            )
            raise
        write_metadata(
            resolved,
            mcp_status,
            "completed",
            wall_clock_seconds=round(time.monotonic() - started, 3),
            usage_totals=usage_totals,
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
