#!/usr/bin/env python3
"""Collect formal benchmark runs into task-level CSV and aggregate JSON."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment_config import VERSIONS


CSV_FIELDS = (
    "strategy",
    "version",
    "run_id",
    "task_idx",
    "tf",
    "pe",
    "ecs",
    "success",
    "failure_category",
    "prompt_tokens",
    "completion_tokens",
    "judge_prompt_tokens",
    "judge_completion_tokens",
    "all_tokens",
    "wall_clock_s",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def numeric(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def task_scores(run_dir: Path) -> list[dict[str, Any]]:
    normalized = run_dir / "judge-results.json"
    if normalized.is_file():
        tasks = read_json(normalized).get("tasks", [])
        if not isinstance(tasks, list):
            raise ValueError(f"{normalized}: tasks must be a list")
        return tasks

    rows: list[dict[str, Any]] = []
    for path in sorted((run_dir / "judge-tasks").glob("*.json")):
        payload = read_json(path)
        aggregate = payload.get("eval_result", {}).get("aggregate", {})
        rows.append(
            {
                "task_idx": int(payload.get("task_idx", path.stem)),
                "tf": aggregate.get("task_fulfillment_mean"),
                "pe": aggregate.get("planning_and_efficiency_mean"),
            }
        )
    return rows


def manifest_statuses(root: Path) -> dict[int, str]:
    path = root / "data/subsets/pilot-30/manifest.json"
    if not path.is_file():
        return {}
    return {
        int(item["idx"]): str(item.get("status", "unknown"))
        for item in read_json(path).get("selected_task_details", [])
    }


def metadata_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name", ""))
    return str(value or "")


def collect(results_root: Path, success_threshold: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    project_root = Path(__file__).resolve().parents[1]
    statuses = manifest_statuses(project_root)
    details: list[dict[str, Any]] = []
    run_costs: dict[tuple[str, str, int], float | None] = {}
    judge_costs: dict[tuple[str, str, int], float | None] = {}

    for run_dir in sorted(path for path in results_root.rglob("run-[0-9][0-9]") if path.is_dir()):
        metadata_path = run_dir / "run-metadata.json"
        if not metadata_path.is_file():
            raise ValueError(f"{run_dir}: missing run-metadata.json")
        metadata = read_json(metadata_path)
        strategy = str(metadata.get("strategy") or run_dir.parents[1].name)
        version = str(metadata.get("version") or run_dir.parent.name)
        run_id = int(metadata.get("run_id") or run_dir.name.split("-", 1)[1])
        if version not in VERSIONS:
            raise ValueError(f"{run_dir}: invalid version {version!r}")
        rows = task_scores(run_dir)
        if not rows:
            raise ValueError(f"{run_dir}: no judge task results")
        prompt_tokens = numeric(metadata.get("total_prompt_tokens"))
        completion_tokens = numeric(metadata.get("total_completion_tokens"))
        judge_metadata_path = run_dir / "judge-metadata.json"
        judge_metadata = read_json(judge_metadata_path) if judge_metadata_path.is_file() else {}
        judge_prompt_tokens = numeric(judge_metadata.get("total_prompt_tokens"))
        judge_completion_tokens = numeric(judge_metadata.get("total_completion_tokens"))
        wall_clock = numeric(metadata.get("wall_clock_seconds"))
        run_costs[(strategy, version, run_id)] = (
            prompt_tokens + completion_tokens
            if prompt_tokens is not None and completion_tokens is not None
            else None
        )
        judge_costs[(strategy, version, run_id)] = (
            judge_prompt_tokens + judge_completion_tokens
            if judge_prompt_tokens is not None and judge_completion_tokens is not None
            else None
        )
        for task in rows:
            idx = int(task["task_idx"])
            tf = numeric(task.get("tf"))
            pe = numeric(task.get("pe"))
            if tf is None or pe is None:
                raise ValueError(f"{run_dir}: task {idx} has no TF/PE score")
            success = tf >= success_threshold
            category = str(task.get("failure_category", ""))
            if not success and category not in {"under_update", "over_update", "other", "unknown"}:
                category = "unknown"
            if success:
                category = ""
            details.append(
                {
                    "strategy": strategy,
                    "version": version,
                    "run_id": run_id,
                    "task_idx": idx,
                    "tf": tf,
                    "pe": pe,
                    "ecs": None,
                    "success": success,
                    "failure_category": category,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "judge_prompt_tokens": judge_prompt_tokens,
                    "judge_completion_tokens": judge_completion_tokens,
                    "all_tokens": (
                        prompt_tokens
                        + completion_tokens
                        + judge_prompt_tokens
                        + judge_completion_tokens
                        if all(
                            value is not None
                            for value in (
                                prompt_tokens,
                                completion_tokens,
                                judge_prompt_tokens,
                                judge_completion_tokens,
                            )
                        )
                        else None
                    ),
                    "wall_clock_s": wall_clock,
                    "task_status": statuses.get(idx, "unknown"),
                    "model": metadata_name(metadata.get("model") or metadata.get("model_name")),
                    "judge": metadata_name(metadata.get("judge") or metadata.get("judge_name")),
                    "mcp_status_at_start": metadata.get("mcp_status_at_start"),
                }
            )

    by_task: dict[tuple[str, int, int], dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in details:
        by_task[(row["strategy"], row["run_id"], row["task_idx"])][row["version"]].append(row)
    for versions in by_task.values():
        if set(versions) != set(VERSIONS):
            continue
        scores = [versions[version][0]["tf"] for version in VERSIONS]
        ecs = statistics.fmean(scores) - statistics.pstdev(scores)
        for version in VERSIONS:
            for row in versions[version]:
                row["ecs"] = ecs

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in details:
        grouped[(row["strategy"], row["version"])].append(row)
    aggregates: list[dict[str, Any]] = []
    for (strategy, version), rows in sorted(grouped.items()):
        affected = [row for row in rows if row["task_status"] == "affected"]
        retention = [row for row in rows if row["task_status"] == "retention"]
        ecs_values = [row["ecs"] for row in rows if row["ecs"] is not None]
        keys = {key for key in run_costs if key[0] == strategy and key[1] == version}
        aggregates.append(
            {
                "strategy": strategy,
                "version": version,
                "mean_tf": statistics.fmean(row["tf"] for row in rows),
                "mean_pe": statistics.fmean(row["pe"] for row in rows),
                "mean_ecs": statistics.fmean(ecs_values) if ecs_values else None,
                "recovery_rate": (
                    sum(row["success"] for row in affected) / len(affected) if affected else None
                ),
                "retention_rate": (
                    sum(row["success"] for row in retention) / len(retention) if retention else None
                ),
                "total_cost_tokens": (
                    int(sum(run_costs[key] for key in keys))
                    if all(run_costs[key] is not None for key in keys)
                    else None
                ),
                "total_judge_tokens": (
                    int(sum(judge_costs[key] for key in keys))
                    if all(judge_costs[key] is not None for key in keys)
                    else None
                ),
                "total_all_tokens": (
                    int(sum(run_costs[key] + judge_costs[key] for key in keys))
                    if all(
                        run_costs[key] is not None and judge_costs[key] is not None
                        for key in keys
                    )
                    else None
                ),
                "n_runs": len({row["run_id"] for row in rows}),
                "n_tasks": len(rows),
            }
        )
    return details, aggregates


def write_outputs(
    details: list[dict[str, Any]],
    aggregates: list[dict[str, Any]],
    *,
    output_csv: Path,
    output_json: Path,
    success_threshold: float,
) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(details)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "success_threshold": success_threshold,
                "details": details,
                "aggregates": aggregates,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect benchmark and judge results")
    parser.add_argument("--results-root", type=Path, default=Path("results"))
    parser.add_argument("--output-csv", type=Path, default=Path("results/summary.csv"))
    parser.add_argument("--output-json", type=Path, default=Path("results/summary.json"))
    parser.add_argument("--success-threshold", type=float, default=6.0)
    args = parser.parse_args()
    try:
        details, aggregates = collect(args.results_root, args.success_threshold)
        write_outputs(
            details,
            aggregates,
            output_csv=args.output_csv,
            output_json=args.output_json,
            success_threshold=args.success_threshold,
        )
        print(f"Collected {len(details)} task rows from {len(aggregates)} strategy/version groups.")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise SystemExit(f"COLLECTION ERROR: {exc}") from exc


if __name__ == "__main__":
    main()
