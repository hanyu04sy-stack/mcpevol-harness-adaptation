#!/usr/bin/env python3
"""Run the fixed two-task canary against a real OpenAI-compatible model."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from experiment_config import VERSIONS, load_env_file, load_experiment
from run_smoke_tests import stop_process_group, wait_for_servers


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = Path("configs/canary-real.json")
TASK_INDICES = (144, 161)


def redact(text: str, secret: str) -> str:
    if secret:
        text = text.replace(secret, "[REDACTED_API_KEY]")
    # Providers may return a masked key in an error response. Remove that too.
    return re.sub(r"sk-[A-Za-z0-9_*.-]+", "[REDACTED_API_KEY]", text)


def validate_trajectory(payload: dict[str, Any]) -> dict[str, Any]:
    messages = payload.get("trajectory_messages", [])
    tool_messages = [message for message in messages if message.get("role") == "tool"]
    errors = [
        str(message.get("content", ""))
        for message in tool_messages
        if str(message.get("content", "")).startswith("Error:")
    ]
    success = bool(
        payload.get("stop")
        and not payload.get("exceeded")
        and tool_messages
        and not errors
    )
    return {
        "success": success,
        "stop": bool(payload.get("stop")),
        "exceeded": bool(payload.get("exceeded")),
        "tool_message_count": len(tool_messages),
        "tool_error_count": len(errors),
        "answer_present": bool(payload.get("answer")),
    }


def render_configs(python: str, task_file: str) -> None:
    for version in VERSIONS:
        subprocess.run(
            [
                python,
                "scripts/render_mcp_config.py",
                "--benchmark-root",
                "external/MCPEvol-Bench",
                "--server-bundle-root",
                "external/servers",
                "--version",
                version,
                "--test-case-file",
                task_file,
                "--output",
                f"generated/1mcp-canary/{version}.json",
            ],
            cwd=ROOT,
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--local",
        action="store_true",
        help="use MODEL_API_KEY/MODEL_BASE_URL from the process without reading .env",
    )
    parser.add_argument("--versions", nargs="+", choices=VERSIONS, default=list(VERSIONS))
    parser.add_argument("--startup-timeout", type=int, default=180)
    parser.add_argument("--run-timeout", type=int, default=900)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace this canary's prior generated results and sanitized reports",
    )
    args = parser.parse_args()
    os.chdir(ROOT)
    config_path = args.config
    python = str((ROOT / ".venv/bin/python").resolve())
    one_mcp = (ROOT / "node_modules/.bin/1mcp").resolve()
    if not Path(python).is_file() or not one_mcp.is_file():
        raise SystemExit("Environment is incomplete; run scripts/setup_environment.py")

    if not args.local:
        env_path = ROOT / ".env"
        if not env_path.is_file():
            raise SystemExit("Missing .env; run scripts/configure_api_credentials.py")
        if stat.S_IMODE(env_path.stat().st_mode) & 0o077:
            raise SystemExit(".env permissions are too broad; run chmod 600 .env")
        load_env_file(env_path)
    api_key = os.environ.get("MODEL_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("MODEL_API_KEY is empty")

    raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    task_file = str(raw_config["dataset"]["path"])
    render_configs(python, task_file)
    first_resolved = load_experiment(config_path, args.versions[0])
    experiment_name = str(first_resolved["experiment_name"])
    report_root = ROOT / "reports" / experiment_name
    result_root = ROOT / "results" / experiment_name
    if args.overwrite:
        for version in args.versions:
            shutil.rmtree(report_root / version, ignore_errors=True)
            shutil.rmtree(result_root / version, ignore_errors=True)
    report_root.mkdir(parents=True, exist_ok=True)
    previous_summary_path = report_root / "summary.json"
    previous_versions: dict[str, Any] = {}
    if previous_summary_path.is_file():
        try:
            previous_versions = json.loads(
                previous_summary_path.read_text(encoding="utf-8")
            ).get("versions", {})
        except (OSError, json.JSONDecodeError):
            previous_versions = {}
    summary: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "external_api_used": not args.local,
        "credential_recorded": False,
        "model": str(first_resolved["model_name"]),
        "temperature": 0.0,
        "task_indices": list(TASK_INDICES),
        "versions": {
            version: result
            for version, result in previous_versions.items()
            if version not in args.versions
        },
    }
    run_env = os.environ.copy()
    run_env["PATH"] = os.pathsep.join(
        [
            str((ROOT / "node_modules/.bin").resolve()),
            str((ROOT / ".venv/bin").resolve()),
            run_env.get("PATH", ""),
        ]
    )
    for version in args.versions:
        resolved = load_experiment(config_path, version)
        version_dir = report_root / version
        version_dir.mkdir(parents=True, exist_ok=True)
        server_log_path = version_dir / "server.log"
        benchmark_log_path = version_dir / "benchmark.log"
        port = urlsplit(str(resolved["mcp_url"])).port
        if port is None:
            raise RuntimeError(f"MCP URL has no port: {resolved['mcp_url']}")
        started = time.monotonic()
        with server_log_path.open("w", encoding="utf-8") as server_log:
            process = subprocess.Popen(
                [
                    str(one_mcp),
                    "serve",
                    "--config",
                    str(resolved["server_config"]),
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--log-level",
                    "info",
                    "--enable-async-loading",
                    "--async-max-concurrent-loads",
                    "2",
                    "--async-max-retries",
                    "1",
                ],
                env=run_env,
                stdout=server_log,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )
            try:
                servers = wait_for_servers(
                    process,
                    port,
                    int(resolved["configured_server_count"]),
                    args.startup_timeout,
                )
                unavailable = [
                    server["server"]
                    for server in servers
                    if server["status"] != "connected"
                ]
                if unavailable:
                    raise RuntimeError(f"Canary servers unavailable: {unavailable}")
                completed = subprocess.run(
                    [
                        python,
                        "scripts/run_benchmark.py",
                        "--config",
                        str(config_path),
                        "--version",
                        version,
                    ],
                    cwd=ROOT,
                    env=run_env,
                    text=True,
                    capture_output=True,
                    timeout=args.run_timeout,
                )
                benchmark_log_path.write_text(
                    redact(completed.stdout + completed.stderr, api_key),
                    encoding="utf-8",
                )
                if completed.returncode:
                    raise RuntimeError(
                        f"benchmark exited with code {completed.returncode}; see sanitized log"
                    )
                trajectory_results = {}
                for idx in TASK_INDICES:
                    source = (
                        Path(resolved["output_dir"])
                        / str(resolved["model_name"])
                        / f"ANSWER/{idx}.json"
                    )
                    if not source.is_file():
                        raise RuntimeError(
                            f"benchmark did not produce trajectory for whitelisted task {idx}"
                        )
                    payload_text = redact(source.read_text(encoding="utf-8"), api_key)
                    destination = version_dir / f"trajectory-{idx}.json"
                    destination.write_text(payload_text, encoding="utf-8")
                    validation = validate_trajectory(json.loads(payload_text))
                    trajectory_results[str(idx)] = {
                        **validation,
                        "trajectory": str(destination.relative_to(ROOT)),
                    }
                success = all(item["success"] for item in trajectory_results.values())
                summary["versions"][version] = {
                    "success": success,
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "connected_servers": len(servers),
                    "available_tools": sum(int(s["toolCount"]) for s in servers),
                    "tasks": trajectory_results,
                    "benchmark_log": str(benchmark_log_path.relative_to(ROOT)),
                    "server_log": str(server_log_path.relative_to(ROOT)),
                }
                if not success:
                    raise RuntimeError("one or more canary trajectories failed validation")
            except Exception as exc:
                summary["versions"].setdefault(
                    version,
                    {
                        "success": False,
                        "duration_seconds": round(time.monotonic() - started, 3),
                        "failure": redact(str(exc), api_key),
                        "benchmark_log": str(benchmark_log_path.relative_to(ROOT)),
                        "server_log": str(server_log_path.relative_to(ROOT)),
                    },
                )
                break
            finally:
                stop_process_group(process)
        print(f"{version}: {'passed' if summary['versions'][version]['success'] else 'failed'}")

    summary["requested_versions_passed"] = all(
        summary["versions"].get(version, {}).get("success", False)
        for version in args.versions
    )
    summary["all_passed"] = set(summary["versions"]) == set(VERSIONS) and all(
        summary["versions"].get(version, {}).get("success", False)
        for version in VERSIONS
    )
    (report_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not summary["requested_versions_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
