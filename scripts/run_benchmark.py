#!/usr/bin/env python3
"""Unified entry point for Early, Middle, and Late benchmark runs."""

from __future__ import annotations

import argparse
import json
import os
import runpy
import sys
import urllib.request
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
)


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
    return {
        "observed_servers": len(servers),
        "connected_servers": sum(s["status"] == "connected" for s in servers),
        "available_tools": sum(
            int(s["toolCount"]) for s in servers if s["status"] == "connected"
        ),
    }


def upstream_arguments(resolved: dict[str, object]) -> list[str]:
    return [
        str(resolved["benchmark_runner"]),
        "--step",
        "3",
        "--model_name",
        str(resolved["model_name"]),
        "--test_case_file",
        str(resolved["task_file"]),
        "--mcp_server_url",
        str(resolved["mcp_url"]),
        "--output_path",
        str(resolved["output_dir"]),
    ]


def configured_initializer(
    original_init: Callable[..., None],
    resolved: dict[str, object],
    api_key: str,
    base_url: str | None,
) -> Callable[..., None]:
    """Wrap the upstream agent so shared settings replace its placeholders."""
    def configured_init(instance: object, *args: object, **kwargs: object) -> None:
        kwargs["api_key"] = api_key
        kwargs["model_url"] = base_url
        kwargs["temperature"] = resolved["temperature"]
        kwargs["max_new_tokens"] = resolved["max_completion_tokens"]
        original_init(instance, *args, **kwargs)

    return configured_init


def run_upstream(
    resolved: dict[str, object], api_key: str, base_url: str | None
) -> None:
    benchmark_src = Path(resolved["benchmark_root"]) / "src"
    old_cwd = Path.cwd()
    old_argv = sys.argv[:]
    agent_module = None
    original_init = None
    sys.path.insert(0, str(benchmark_src))
    os.chdir(benchmark_src)
    try:
        from custom.agents import SimpleOpenAIAgent as agent_module

        original_init = agent_module.ChatModel.__init__
        agent_module.ChatModel.__init__ = configured_initializer(
            original_init, resolved, api_key, base_url
        )
        sys.argv = upstream_arguments(resolved)
        runpy.run_path(str(resolved["benchmark_runner"]), run_name="__main__")
    finally:
        if agent_module is not None and original_init is not None:
            agent_module.ChatModel.__init__ = original_init
        sys.argv = old_argv
        os.chdir(old_cwd)
        if sys.path and sys.path[0] == str(benchmark_src):
            sys.path.pop(0)


def write_metadata(
    resolved: dict[str, object], mcp_status: dict[str, int], status: str
) -> Path:
    output_dir = Path(resolved["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "run-metadata.json"
    payload = public_summary(resolved)
    payload.update(
        {
            "status": status,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "mcp_status_at_start": mcp_status,
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print resolved settings without secrets, MCP, or API calls",
    )
    args = parser.parse_args()
    try:
        resolved = load_experiment(args.config, args.version)
        print(json.dumps(public_summary(resolved), ensure_ascii=False, indent=2))
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
        mcp_status = check_mcp(resolved)
        metadata = write_metadata(resolved, mcp_status, "running")
        try:
            run_upstream(resolved, api_key, base_url)
        except BaseException:
            write_metadata(resolved, mcp_status, "failed")
            raise
        write_metadata(resolved, mcp_status, "completed")
        print(f"Run completed; metadata: {metadata}")
    except ConfigError as exc:
        raise SystemExit(f"CONFIG ERROR: {exc}") from exc


if __name__ == "__main__":
    main()
