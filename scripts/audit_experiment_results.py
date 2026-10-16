#!/usr/bin/env python3
"""Audit completeness and fairness of the final formal experiment matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STRATEGIES = ("no_update", "full_rewrite", "selective_patch")
VERSIONS = ("early", "middle", "late")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(
    root: Path,
    config_path: Path,
    run_ids: tuple[int, ...],
    judge_runs: int,
) -> dict[str, Any]:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    config = read_json(config_path)
    task_path = root / config["dataset"]["path"]
    tasks = read_json(task_path)
    task_ids = {int(task["idx"]) for task in tasks}
    expected_task_hash = config["dataset"]["sha256"]
    issues: list[dict[str, object]] = []
    completed_runs = 0
    scored_tasks = 0

    def issue(strategy: str, version: str, run_id: int, message: str) -> None:
        issues.append(
            {
                "strategy": strategy,
                "version": version,
                "run_id": run_id,
                "message": message,
            }
        )

    if sha256(task_path) != expected_task_hash:
        issues.append({"message": "configured task SHA-256 does not match the task file"})

    for strategy in STRATEGIES:
        for version in VERSIONS:
            for run_id in run_ids:
                run = root / "results" / strategy / version / f"run-{run_id:02d}"
                required = (
                    run / "run-metadata.json",
                    run / "judge-results.json",
                    run / "judge-metadata.json",
                )
                missing = [path.name for path in required if not path.is_file()]
                if missing:
                    issue(strategy, version, run_id, f"missing files: {missing}")
                    continue
                metadata = read_json(required[0])
                judged = read_json(required[1])
                judge_metadata = read_json(required[2])
                checks = {
                    "strategy": strategy,
                    "version": version,
                    "run_id": run_id,
                    "benchmark_commit": config["benchmark"]["commit"],
                    "task_sha256": expected_task_hash,
                    "status": "completed",
                }
                for key, expected in checks.items():
                    if metadata.get(key) != expected:
                        issue(
                            strategy,
                            version,
                            run_id,
                            f"metadata {key}={metadata.get(key)!r}, expected {expected!r}",
                        )
                model = metadata.get("model", {})
                for key, expected in (
                    ("name", config["model"]["name"]),
                    ("temperature", config["model"]["temperature"]),
                    ("max_completion_tokens", config["model"]["max_completion_tokens"]),
                ):
                    if model.get(key) != expected:
                        issue(strategy, version, run_id, f"model {key} mismatch")
                judge = metadata.get("judge", {})
                for key, expected in (
                    ("name", config["judge"]["name"]),
                    ("temperature", config["judge"]["temperature"]),
                ):
                    if judge.get(key) != expected:
                        issue(strategy, version, run_id, f"judge {key} mismatch")
                if not metadata.get("harness_manifest_sha256") or len(
                    metadata.get("harness_files", [])
                ) != 3:
                    issue(strategy, version, run_id, "harness hashes are incomplete")
                mcp = metadata.get("mcp_status_at_start") or {}
                if not mcp.get("connected_servers") or (
                    mcp.get("connected_servers") != mcp.get("observed_servers")
                ):
                    issue(strategy, version, run_id, "MCP servers were not all connected")
                if any(metadata.get(key) is None for key in (
                    "total_prompt_tokens",
                    "total_completion_tokens",
                    "wall_clock_seconds",
                )):
                    issue(strategy, version, run_id, "benchmark usage or timing is missing")

                rows = judged.get("tasks", [])
                observed_ids = {int(row["task_idx"]) for row in rows}
                if observed_ids != task_ids:
                    issue(strategy, version, run_id, "Judge task IDs do not match the fixed set")
                if any(int(row.get("successful_judge_runs", 0)) < judge_runs for row in rows):
                    issue(strategy, version, run_id, "a task has fewer successful Judge runs than required")
                if judge_metadata.get("num_runs_requested_per_task") != judge_runs:
                    issue(strategy, version, run_id, "Judge repetition metadata mismatch")
                if any(judge_metadata.get(key) is None for key in (
                    "total_prompt_tokens",
                    "total_completion_tokens",
                )):
                    issue(strategy, version, run_id, "Judge usage is missing")
                completed_runs += 1
                scored_tasks += len(rows)

    expected_runs = len(STRATEGIES) * len(VERSIONS) * len(run_ids)
    try:
        reported_config = config_path.relative_to(root).as_posix()
    except ValueError:
        reported_config = str(config_path)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": not issues and completed_runs == expected_runs,
        "config": reported_config,
        "task_count": len(task_ids),
        "expected_runs": expected_runs,
        "completed_runs": completed_runs,
        "expected_scored_tasks": expected_runs * len(task_ids),
        "scored_tasks": scored_tasks,
        "judge_runs_per_task": judge_runs,
        "issues": issues,
        "secrets_recorded": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("configs/comparison-subset/experiment.json")
    )
    parser.add_argument("--run-ids", nargs="+", type=int, default=(1, 2, 3))
    parser.add_argument("--judge-runs", type=int, default=5)
    parser.add_argument(
        "--output", type=Path, default=Path("reports/d/final-experiment-audit.json")
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = audit(root, args.config, tuple(args.run_ids), args.judge_runs)
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
