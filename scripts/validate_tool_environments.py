#!/usr/bin/env python3
"""Start Early/Middle/Late 1MCP environments and write a JSON report."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VERSIONS = ("early", "middle", "late")
TERMINAL_STATUSES = {"connected", "failed"}


def run_output(args: list[str], env: dict[str, str], timeout: int = 30) -> str:
    result = subprocess.run(
        args, env=env, text=True, capture_output=True, timeout=timeout, check=True
    )
    return result.stdout.strip()


def inspect(url: str) -> list[dict[str, Any]]:
    with urllib.request.urlopen(f"{url}/api/v1/inspect", timeout=20) as response:
        return json.load(response)["servers"]


def failure_reason(log_text: str, server: str) -> str | None:
    pattern = re.compile(rf"Failed to connect to {re.escape(server)}: ([^\r\n]+)")
    matches = pattern.findall(log_text)
    if not matches:
        return None
    reason = matches[-1].strip()
    if " {" in reason:
        reason = reason.split(" {", 1)[0]
    return reason


def summarize(
    version: str,
    port: int,
    configured_count: int,
    servers: list[dict[str, Any]],
    log_text: str,
    elapsed_seconds: float,
    timed_out: bool = False,
) -> dict[str, Any]:
    statuses = Counter(server["status"] for server in servers)
    unavailable = [
        server["server"] for server in servers if server["status"] != "connected"
    ]
    unresolved = [
        server["server"]
        for server in servers
        if server["status"] not in TERMINAL_STATUSES
    ]
    details = []
    for server in sorted(servers, key=lambda item: item["server"]):
        item = {
            "name": server["server"],
            "status": server["status"],
            "available": bool(server["available"]),
            "tool_count": int(server["toolCount"]),
        }
        if server["status"] != "connected":
            item["failure_reason"] = failure_reason(log_text, server["server"])
            if (
                item["failure_reason"] is None
                and timed_out
                and server["status"] not in TERMINAL_STATUSES
            ):
                item["failure_reason"] = (
                    f"Validation timeout while status remained {server['status']}"
                )
            elif item["failure_reason"] is None:
                item["failure_reason"] = "No failure reason emitted by 1MCP log"
        details.append(item)
    all_observed = len(servers) == configured_count
    settled = all_observed and all(
        server["status"] in TERMINAL_STATUSES for server in servers
    )
    return {
        "version": version,
        "collection_mode": "direct_run",
        "start_result": "started" if all_observed else "incomplete",
        "validation_complete": all_observed,
        "settled": settled,
        "timed_out": timed_out,
        "url": f"http://127.0.0.1:{port}",
        "elapsed_seconds": round(elapsed_seconds, 3),
        "configured_server_count": configured_count,
        "observed_server_count": len(servers),
        "connected_server_count": statuses["connected"],
        "failed_server_count": len(unavailable),
        "backend_failed_status_count": statuses["failed"],
        "unresolved_server_count": len(unresolved),
        "tool_count": sum(server["toolCount"] for server in servers if server["status"] == "connected"),
        "status_counts": dict(sorted(statuses.items())),
        "failed_servers": unavailable,
        "unresolved_servers": unresolved,
        "servers": details,
    }


def validate_version(
    version: str,
    port: int,
    timeout_seconds: int,
    poll_seconds: float,
    stable_seconds: float,
    cli: list[str],
    env: dict[str, str],
    log_dir: Path,
) -> dict[str, Any]:
    config = Path("generated/1mcp") / f"{version}.json"
    configured_count = len(json.loads(config.read_text(encoding="utf-8"))["mcpServers"])
    log_path = log_dir / f"{version}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    servers: list[dict[str, Any]] = []
    stable_since: float | None = None
    previous_signature: tuple[tuple[str, str], ...] | None = None
    settled = False
    runtime_config = log_dir / "runtime" / version / "mcp.json"
    runtime_config.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(config, runtime_config)
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                *cli, "serve", "--config", str(runtime_config), "--host", "127.0.0.1",
                "--port", str(port), "--log-level", "info", "--enable-async-loading",
                "--async-max-concurrent-loads", "4", "--async-max-retries", "1",
            ],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        try:
            deadline = start + timeout_seconds
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError(f"1MCP exited early with code {process.returncode}")
                try:
                    servers = inspect(f"http://127.0.0.1:{port}")
                except (OSError, json.JSONDecodeError, KeyError):
                    time.sleep(poll_seconds)
                    continue
                terminal = len(servers) == configured_count and all(
                    server["status"] in TERMINAL_STATUSES for server in servers
                )
                signature = tuple(
                    sorted((server["server"], server["status"]) for server in servers)
                )
                if terminal:
                    if signature != previous_signature:
                        stable_since = time.monotonic()
                    elif stable_since and time.monotonic() - stable_since >= stable_seconds:
                        settled = True
                        break
                else:
                    stable_since = None
                previous_signature = signature
                time.sleep(poll_seconds)
        finally:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=10)
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    return summarize(
        version,
        port,
        configured_count,
        servers,
        log_text,
        time.monotonic() - start,
        timed_out=not settled,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("reports/environment-validation.json"))
    parser.add_argument("--log-dir", type=Path, default=Path("logs/environment-validation"))
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    parser.add_argument("--stable-seconds", type=float, default=60.0)
    parser.add_argument("--base-port", type=int, default=3051)
    parser.add_argument("--versions", nargs="+", choices=VERSIONS, default=list(VERSIONS))
    parser.add_argument("--append", action="store_true", help="Keep completed versions already in the output report")
    parser.add_argument("--one-mcp-cli", type=Path, help="Optional 1mcp executable override")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    one_mcp = (args.one_mcp_cli or (root / "node_modules/.bin/1mcp")).resolve()
    if not one_mcp.is_file():
        raise SystemExit("1MCP is missing; run scripts/setup_environment.py first")
    cli = [str(one_mcp)]
    env = os.environ.copy()
    extra_path = [one_mcp.parent, root / ".venv/bin", root / "node_modules/.bin"]
    env["PATH"] = os.pathsep.join(str(path.resolve()) for path in extra_path) + os.pathsep + env.get("PATH", "")

    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "benchmark_commit": run_output(
            ["git", "-C", "external/MCPEvol-Bench", "rev-parse", "HEAD"], env
        ),
        "one_mcp_version": json.loads(
            (root / "node_modules/@1mcp/agent/package.json").read_text(encoding="utf-8")
        )["version"],
        "versions": {},
    }
    if args.append and args.output.is_file():
        previous = json.loads(args.output.read_text(encoding="utf-8"))
        report["versions"].update(previous.get("versions", {}))
    for version in args.versions:
        offset = VERSIONS.index(version)
        print(f"Validating {version}...", flush=True)
        report["versions"][version] = validate_version(
            version, args.base_port + offset, args.timeout, args.poll_seconds, args.stable_seconds,
            cli, env, args.log_dir,
        )
        summary = report["versions"][version]
        print(
            f"{version}: {summary['connected_server_count']} connected, "
            f"{summary['failed_server_count']} failed, {summary['tool_count']} tools",
            flush=True,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["all_versions_started"] = set(report["versions"]) == set(VERSIONS) and all(
        item["start_result"] == "started" for item in report["versions"].values()
    )
    report["all_validations_complete"] = set(report["versions"]) == set(VERSIONS) and all(
        item["validation_complete"] for item in report["versions"].values()
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    if any(not report["versions"][version]["validation_complete"] for version in args.versions):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
