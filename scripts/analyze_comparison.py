#!/usr/bin/env python3
"""Paired comparison analysis on top of collected results.

Reads results/summary.json (or raw results/) and produces:
  1. strategy x version tables: mean +/- std of TF/PE/ECS over the 3 runs
  2. affected vs retention breakdown: mean TF and success rate
  3. paired recovery gain: selective_patch - no_update / - full_rewrite on
     affected tasks (same task, same run_id)
  4. paired retention loss: selective_patch - no_update / - full_rewrite on
     retention tasks
  5. 95% bootstrap confidence intervals for the paired deltas

Output: reports/d/comparison-analysis.json and a text table printed to stdout.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment_config import VERSIONS

SUCCESS_THRESHOLD = 6.0
BOOTSTRAP_ITERATIONS = 10_000
BOOTSTRAP_SEED = 6203


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def pstdev(values: list[float]) -> float | None:
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def mean_std(values: list[float]) -> dict[str, Any]:
    return {
        "mean": round(mean(values), 4) if values else None,
        "std": round(pstdev(values), 4) if values else None,
        "n": len(values),
    }


def bootstrap_ci(deltas: list[float], alpha: float = 0.05) -> dict[str, Any]:
    if not deltas:
        return {"lo": None, "hi": None, "n": 0}
    rng = random.Random(BOOTSTRAP_SEED)
    sample_mean = statistics.fmean(deltas)
    replicates: list[float] = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        sample = [deltas[rng.randrange(len(deltas))] for _ in range(len(deltas))]
        replicates.append(statistics.fmean(sample))
    replicates.sort()
    lo = replicates[int(BOOTSTRAP_ITERATIONS * alpha / 2)]
    hi = replicates[int(BOOTSTRAP_ITERATIONS * (1 - alpha / 2)) - 1]
    return {"mean_delta": round(sample_mean, 4), "ci95_lo": round(lo, 4), "ci95_hi": round(hi, 4), "n": len(deltas)}


def analyze(details: list[dict[str, Any]]) -> dict[str, Any]:
    statuses: dict[int, str] = {}
    for row in details:
        statuses.setdefault(int(row["task_idx"]), str(row.get("task_status", "unknown")))

    # 1) strategy x version: per-cell means over tasks; then mean +/- std over runs.
    by_cell: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in details:
        by_cell[(row["strategy"], row["version"])].append(row)

    strategy_version: dict[str, Any] = {}
    for (strategy, version), rows in sorted(by_cell.items()):
        runs: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            runs[int(row["run_id"])].append(row)
        run_tf: list[float] = []
        run_pe: list[float] = []
        run_ecs: list[float] = []
        for run_id in sorted(runs):
            cell = runs[run_id]
            tfs = [float(r["tf"]) for r in cell]
            pes = [float(r["pe"]) for r in cell]
            ecs_values = [r["ecs"] for r in cell if r["ecs"] is not None]
            run_tf.append(statistics.fmean(tfs))
            run_pe.append(statistics.fmean(pes))
            if ecs_values:
                run_ecs.append(statistics.fmean(ecs_values))
        strategy_version[f"{strategy}/{version}"] = {
            "mean_tf": mean_std(run_tf),
            "mean_pe": mean_std(run_pe),
            "mean_ecs": mean_std(run_ecs),
        }

    # 2) affected vs retention per strategy x version
    breakdown: dict[str, Any] = {}
    for (strategy, version), rows in sorted(by_cell.items()):
        for subset in ("affected", "retention"):
            subset_rows = [r for r in rows if statuses.get(int(r["task_idx"])) == subset]
            if not subset_rows:
                continue
            tfs = [float(r["tf"]) for r in subset_rows]
            breakdown[f"{strategy}/{version}/{subset}"] = {
                "mean_tf": round(statistics.fmean(tfs), 4),
                "success_rate": round(sum(1 for r in subset_rows if float(r["tf"]) >= SUCCESS_THRESHOLD) / len(subset_rows), 4),
                "n_task_runs": len(subset_rows),
            }

    # 3) paired deltas on the same (strategy, run_id, task_idx)
    deltas_affected: dict[str, list[float]] = {"sp_minus_nu": [], "sp_minus_fr": []}
    deltas_retention: dict[str, list[float]] = {"sp_minus_nu": [], "sp_minus_fr": []}
    by_key: dict[tuple[str, int, int], dict[str, float]] = {}
    for row in details:
        key = (row["strategy"], int(row["run_id"]), int(row["task_idx"]))
        if key not in by_key or row["version"] == "early":
            by_key[key] = {"early": float(row["tf"])}
        else:
            by_key[key].setdefault("middle", float(row["tf"]))
            by_key[key].setdefault("late", float(row["tf"]))

    # paired within each version (early/middle/late)
    for version in VERSIONS:
        pairs_nu: dict[tuple[int, int], float] = {}
        pairs_fr: dict[tuple[int, int], float] = {}
        pairs_sp: dict[tuple[int, int], float] = {}
        for (strategy, run_id, task_idx), scores in by_key.items():
            tf = scores.get(version)
            if tf is None:
                continue
            target = pairs_nu if strategy == "no_update" else (pairs_fr if strategy == "full_rewrite" else pairs_sp)
            target[(run_id, task_idx)] = tf
        for (run_id, task_idx), sp_tf in pairs_sp.items():
            status = statuses.get(task_idx, "unknown")
            if (run_id, task_idx) in pairs_nu:
                bucket = deltas_affected if status == "affected" else (deltas_retention if status == "retention" else None)
                if bucket is not None:
                    bucket["sp_minus_nu"].append(sp_tf - pairs_nu[(run_id, task_idx)])
            if (run_id, task_idx) in pairs_fr:
                bucket = deltas_affected if status == "affected" else (deltas_retention if status == "retention" else None)
                if bucket is not None:
                    bucket["sp_minus_fr"].append(sp_tf - pairs_fr[(run_id, task_idx)])

    paired: dict[str, Any] = {}
    for group, key in (("affected_recovery_gain", "sp_minus_nu"), ("affected_recovery_gain", "sp_minus_fr"), ("retention_loss", "sp_minus_nu"), ("retention_loss", "sp_minus_fr")):
        source = deltas_affected if group.startswith("affected") else deltas_retention
        paired.setdefault(group, {})[key] = bootstrap_ci(source[key])

    # 4) overall strategy summary (across all versions and runs)
    strategy_overall: dict[str, Any] = {}
    by_strategy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in details:
        by_strategy[row["strategy"]].append(row)
    for strategy, rows in sorted(by_strategy.items()):
        tfs = [float(r["tf"]) for r in rows]
        pes = [float(r["pe"]) for r in rows]
        strategy_overall[strategy] = {
            "mean_tf": mean_std(tfs),
            "mean_pe": mean_std(pes),
            "n_cells": len({(r["strategy"], r["version"], r["run_id"]) for r in rows}),
        }

    return {
        "success_threshold": SUCCESS_THRESHOLD,
        "strategy_version": strategy_version,
        "breakdown": breakdown,
        "paired": paired,
        "strategy_overall": strategy_overall,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Paired comparison analysis")
    parser.add_argument("--results-root", type=Path, default=Path("results"))
    parser.add_argument("--output", type=Path, default=Path("reports/d/comparison-analysis.json"))
    args = parser.parse_args()

    summary = args.results_root / "summary.json"
    details_path = args.results_root / "summary.csv" if False else summary
    if summary.is_file():
        payload = read_json(summary)
        details = payload.get("details", [])
    else:
        # fall back to collecting from raw cells
        sys_path = Path(__file__).resolve().parent
        import sys

        sys.path.insert(0, str(sys_path))
        from collect_results import collect

        details, _aggregates = collect(args.results_root, SUCCESS_THRESHOLD)

    if not details:
        raise SystemExit("no collected details found; run collect_results.py first")

    result = analyze(details)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(), **result},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
