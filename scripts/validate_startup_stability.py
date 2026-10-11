#!/usr/bin/env python3
"""Cold-start each MCP version repeatedly and report server stability."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_tool_environments import VERSIONS, validate_version


def summarize_trials(trials: list[dict[str, Any]]) -> dict[str, Any]:
    if not trials:
        raise ValueError("at least one trial is required")
    configured = int(trials[0]["configured_server_count"])
    names = sorted(
        {server["name"] for trial in trials for server in trial.get("servers", [])}
    )
    server_trials = {}
    flaky = []
    for name in names:
        statuses = []
        for trial in trials:
            status = next(
                (
                    server["status"]
                    for server in trial.get("servers", [])
                    if server["name"] == name
                ),
                "not_observed",
            )
            statuses.append(status)
        stable = all(status == "connected" for status in statuses)
        server_trials[name] = {"statuses": statuses, "stable_connected": stable}
        if not stable:
            flaky.append(name)
    successful_trials = sum(
        trial.get("validation_complete") is True
        and trial.get("connected_server_count") == configured
        and trial.get("failed_server_count") == 0
        for trial in trials
    )
    return {
        "trial_count": len(trials),
        "configured_server_count": configured,
        "successful_trial_count": successful_trials,
        "all_trials_successful": successful_trials == len(trials),
        "stable_connected_server_count": sum(
            detail["stable_connected"] for detail in server_trials.values()
        ),
        "flaky_or_unavailable_servers": flaky,
        "servers": server_trials,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--stable-seconds", type=float, default=10.0)
    parser.add_argument("--base-port", type=int, default=3251)
    parser.add_argument(
        "--output", type=Path, default=Path("reports/pilot-30-startup-stability.json")
    )
    parser.add_argument(
        "--log-dir", type=Path, default=Path("logs/pilot-30-startup-stability")
    )
    args = parser.parse_args()
    if args.trials < 2:
        raise SystemExit("ERROR: startup stability requires at least two trials")

    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    one_mcp = (root / "node_modules/.bin/1mcp").resolve()
    if not one_mcp.is_file():
        raise SystemExit("1MCP is missing; run scripts/setup_environment.py first")
    env = os.environ.copy()
    extra_path = [one_mcp.parent, root / ".venv/bin", root / "node_modules/.bin"]
    env["PATH"] = os.pathsep.join(str(path.resolve()) for path in extra_path) + os.pathsep + env.get("PATH", "")
    benchmark_commit = subprocess.run(
        ["git", "-C", "external/MCPEvol-Bench", "rev-parse", "HEAD"],
        env=env,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    ).stdout.strip()
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "benchmark_commit": benchmark_commit,
        "trial_count": args.trials,
        "versions": {version: {"trials": []} for version in VERSIONS},
    }
    for trial_number in range(1, args.trials + 1):
        for offset, version in enumerate(VERSIONS):
            print(f"Trial {trial_number}/{args.trials}: {version}", flush=True)
            result = validate_version(
                version,
                args.base_port + offset,
                args.timeout,
                args.poll_seconds,
                args.stable_seconds,
                [str(one_mcp)],
                env,
                args.log_dir / f"trial-{trial_number}",
            )
            result["trial"] = trial_number
            report["versions"][version]["trials"].append(result)
            print(
                f"  {result['connected_server_count']}/{result['configured_server_count']} "
                f"connected; {result['failed_server_count']} failed",
                flush=True,
            )
            write_report(args.output, report)

    for version in VERSIONS:
        report["versions"][version]["summary"] = summarize_trials(
            report["versions"][version]["trials"]
        )
    report["all_versions_stable"] = all(
        report["versions"][version]["summary"]["all_trials_successful"]
        and not report["versions"][version]["summary"]["flaky_or_unavailable_servers"]
        for version in VERSIONS
    )
    write_report(args.output, report)
    print(f"Wrote {args.output}")
    if not report["all_versions_stable"]:
        raise SystemExit("ERROR: one or more MCP servers failed a repeated startup")


if __name__ == "__main__":
    main()
