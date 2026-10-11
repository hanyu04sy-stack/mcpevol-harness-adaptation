#!/usr/bin/env python3
"""Run a deterministic one-task MCPEvol-Bench smoke test on all environments."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from experiment_config import VERSIONS, load_experiment


ROOT = Path(__file__).resolve().parents[1]
SMOKE_CONFIG = Path("configs/smoke.json")
MODEL_PORT = 8011
TOOL_SEQUENCE = (
    ("list-projects", {}),
    ("read-project-summary", {}),
    ("search-element", {"search": "payment"}),
    (
        "convert_time",
        {
            "source_timezone": "Asia/Tokyo",
            "target_timezone": "America/New_York",
            "time": "14:00",
        },
    ),
)


class SmokeModelHandler(BaseHTTPRequestHandler):
    events: list[dict[str, Any]] = []

    def log_message(self, format: str, *args: object) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        available = {
            item["function"]["name"] for item in body.get("tools", [])
        }
        used = {
            call["function"]["name"]
            for message in body.get("messages", [])
            for call in message.get("tool_calls", [])
        }
        selected = next(
            (
                (name, arguments)
                for name, arguments in TOOL_SEQUENCE
                if name in available and name not in used
            ),
            None,
        )
        if selected:
            name, arguments = selected
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": f"smoke-{uuid.uuid4().hex[:12]}",
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": json.dumps(arguments),
                        },
                    }
                ],
            }
            finish_reason = "tool_calls"
            action = name
        else:
            message = {
                "role": "assistant",
                "content": (
                    "[FINISH] Deterministic smoke run completed the available "
                    "architecture and time-conversion tool calls."
                ),
            }
            finish_reason = "stop"
            action = "finish"
        self.events.append(
            {
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "model": body.get("model"),
                "message_count": len(body.get("messages", [])),
                "action": action,
            }
        )
        payload = {
            "id": f"chatcmpl-smoke-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": body.get("model", "smoke-local"),
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": finish_reason,
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def render_smoke_configs(python: str) -> None:
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
                "data/subsets/smoke-1/test_cases.json",
                "--output",
                f"generated/1mcp-smoke/{version}.json",
            ],
            cwd=ROOT,
            check=True,
        )


def inspect_servers(port: int) -> list[dict[str, Any]]:
    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}/api/v1/inspect", timeout=10
    ) as response:
        return json.load(response)["servers"]


def wait_for_servers(
    process: subprocess.Popen[str], port: int, expected: int, timeout: int
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"1MCP exited early with code {process.returncode}")
        try:
            servers = inspect_servers(port)
        except (OSError, KeyError, json.JSONDecodeError):
            time.sleep(1)
            continue
        if len(servers) == expected and all(
            server["status"] in {"connected", "failed"} for server in servers
        ):
            return servers
        time.sleep(1)
    raise TimeoutError(f"1MCP did not settle within {timeout} seconds")


def stop_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


def validate_trajectory(path: Path) -> dict[str, Any]:
    trajectory = json.loads(path.read_text(encoding="utf-8"))
    messages = trajectory.get("trajectory_messages", [])
    tool_messages = [message for message in messages if message.get("role") == "tool"]
    errors = [
        message["content"]
        for message in tool_messages
        if str(message.get("content", "")).startswith("Error:")
    ]
    success = bool(
        trajectory.get("stop")
        and not trajectory.get("exceeded")
        and len(tool_messages) == len(TOOL_SEQUENCE)
        and not errors
    )
    return {
        "success": success,
        "stop": bool(trajectory.get("stop")),
        "exceeded": bool(trajectory.get("exceeded")),
        "tool_message_count": len(tool_messages),
        "tool_errors": errors,
        "answer": trajectory.get("answer"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--versions", nargs="+", choices=VERSIONS, default=list(VERSIONS))
    parser.add_argument("--one-mcp-cli", type=Path)
    parser.add_argument("--startup-timeout", type=int, default=180)
    parser.add_argument("--run-timeout", type=int, default=300)
    parser.add_argument(
        "--harness-dir",
        type=Path,
        default=Path("harness/original"),
        help="Harness knowledge directory passed to the unified runner",
    )
    args = parser.parse_args()
    os.chdir(ROOT)
    python = str((ROOT / ".venv/bin/python").resolve())
    if not Path(python).is_file():
        raise SystemExit("Missing .venv; run scripts/setup_environment.py first")
    cli: Path | None = args.one_mcp_cli.resolve() if args.one_mcp_cli else None
    if cli and not cli.is_file():
        raise SystemExit(f"Missing 1MCP CLI: {cli}")
    if cli:
        cli_command = [str(cli)]
    else:
        pnpm = shutil.which("pnpm")
        if not pnpm:
            raise SystemExit("Missing pnpm; run scripts/setup_environment.py first")
        cli_command = [
            pnpm,
            "--package=@1mcp/agent@0.38.2",
            "--package=npm@11.6.2",
            "dlx",
            "1mcp",
        ]
    render_smoke_configs(python)

    reports = ROOT / "reports/smoke"
    reports.mkdir(parents=True, exist_ok=True)
    model_server = ThreadingHTTPServer(("127.0.0.1", MODEL_PORT), SmokeModelHandler)
    model_thread = threading.Thread(target=model_server.serve_forever, daemon=True)
    model_thread.start()
    summary: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_commit": None,
        "model_mode": "deterministic_local_openai_compatible_smoke",
        "external_api_used": False,
        "task_indices": [161],
        "versions": {},
    }
    try:
        for version in args.versions:
            resolved = load_experiment(SMOKE_CONFIG, version)
            summary["benchmark_commit"] = resolved["benchmark_commit"]
            version_dir = reports / version
            version_dir.mkdir(parents=True, exist_ok=True)
            server_log_path = version_dir / "server.log"
            benchmark_log_path = version_dir / "benchmark.log"
            port = urlsplit(str(resolved["mcp_url"])).port
            if port is None:
                raise RuntimeError(f"MCP URL has no port: {resolved['mcp_url']}")
            env = os.environ.copy()
            path_entries = [
                str((ROOT / ".venv/bin").resolve()),
                str((ROOT / "node_modules/.bin").resolve()),
                env.get("PATH", ""),
            ]
            if cli:
                path_entries.insert(0, str(cli.parent))
            env["PATH"] = os.pathsep.join(path_entries)
            started = time.monotonic()
            event_start = len(SmokeModelHandler.events)
            with server_log_path.open("w", encoding="utf-8") as server_log:
                process = subprocess.Popen(
                    [
                        *cli_command,
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
                    env=env,
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
                    failed = [s["server"] for s in servers if s["status"] != "connected"]
                    if failed:
                        raise RuntimeError(f"Smoke servers failed to load: {failed}")
                    run_env = env.copy()
                    run_env["MODEL_API_KEY"] = "local-smoke-no-secret"
                    run_env["MODEL_BASE_URL"] = f"http://127.0.0.1:{MODEL_PORT}/v1"
                    completed = subprocess.run(
                        [
                            python,
                            "scripts/run_benchmark.py",
                            "--config",
                            str(SMOKE_CONFIG),
                            "--version",
                            version,
                            "--harness-dir",
                            str(args.harness_dir),
                        ],
                        cwd=ROOT,
                        env=run_env,
                        text=True,
                        capture_output=True,
                        timeout=args.run_timeout,
                    )
                    benchmark_log_path.write_text(
                        completed.stdout + completed.stderr, encoding="utf-8"
                    )
                    if completed.returncode:
                        raise RuntimeError(
                            f"benchmark exited with code {completed.returncode}"
                        )
                    trajectory_source = (
                        Path(resolved["output_dir"])
                        / str(resolved["model_name"])
                        / "ANSWER/161.json"
                    )
                    trajectory_report = version_dir / "trajectory-161.json"
                    shutil.copy2(trajectory_source, trajectory_report)
                    validation = validate_trajectory(trajectory_report)
                    if not validation["success"]:
                        raise RuntimeError(f"trajectory validation failed: {validation}")
                    model_events = SmokeModelHandler.events[event_start:]
                    (version_dir / "model-events.json").write_text(
                        json.dumps(model_events, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    summary["versions"][version] = {
                        "success": True,
                        "duration_seconds": round(time.monotonic() - started, 3),
                        "configured_servers": len(servers),
                        "connected_servers": len(servers),
                        "available_tools": sum(int(s["toolCount"]) for s in servers),
                        "trajectory": str(trajectory_report.relative_to(ROOT)),
                        "benchmark_log": str(benchmark_log_path.relative_to(ROOT)),
                        "server_log": str(server_log_path.relative_to(ROOT)),
                        **validation,
                    }
                except Exception as exc:
                    summary["versions"][version] = {
                        "success": False,
                        "duration_seconds": round(time.monotonic() - started, 3),
                        "failure": str(exc),
                        "benchmark_log": str(benchmark_log_path.relative_to(ROOT)),
                        "server_log": str(server_log_path.relative_to(ROOT)),
                    }
                finally:
                    stop_process_group(process)
            print(f"{version}: {summary['versions'][version]}", flush=True)
    finally:
        model_server.shutdown()
        model_server.server_close()
        model_thread.join(timeout=5)

    summary["all_passed"] = set(summary["versions"]) == set(args.versions) and all(
        item["success"] for item in summary["versions"].values()
    )
    summary_name = (
        "summary.json"
        if set(args.versions) == set(VERSIONS)
        else f"summary-{'-'.join(args.versions)}.json"
    )
    (reports / summary_name).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not summary["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
