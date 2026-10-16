#!/usr/bin/env python3
"""Build reports/d/cost-analysis.csv/json from per-cell run metadata.

Reads every results/<strategy>/<version>/run-XX cell, joins run-metadata.json
(benchmark usage + wall time) with judge-metadata.json (judge usage + wall
time), and estimates USD cost at the pinned gpt-4o-mini reference rate.
Unknown values are written as "unknown", never as zero.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment_config import VERSIONS


# Reference price used by the experiment (USD per million tokens).  This is a
# token-based estimate, not a provider invoice; actual billing may differ.
PRICE_IN_PER_M = 0.15
PRICE_OUT_PER_M = 0.60

CSV_FIELDS = (
    "strategy",
    "version",
    "run_id",
    "benchmark_prompt_tokens",
    "benchmark_completion_tokens",
    "benchmark_total_tokens",
    "benchmark_wall_clock_s",
    "judge_prompt_tokens",
    "judge_completion_tokens",
    "judge_total_tokens",
    "judge_wall_clock_s",
    "metered_judge_responses",
    "all_tokens",
    "estimated_usd_benchmark",
    "estimated_usd_judge",
    "estimated_usd_total",
    "notes",
)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def numeric(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def usd(prompt: float | None, completion: float | None) -> float | None:
    if prompt is None or completion is None:
        return None
    return prompt * PRICE_IN_PER_M / 1_000_000 + completion * PRICE_OUT_PER_M / 1_000_000


def fmt(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def build(results_root: Path, output_csv: Path, output_json: Path) -> None:
    rows: list[dict[str, Any]] = []
    for run_dir in sorted(path for path in results_root.rglob("run-[0-9][0-9]") if path.is_dir()):
        if any(part.startswith("ablation-") for part in run_dir.relative_to(results_root).parts):
            continue
        metadata_path = run_dir / "run-metadata.json"
        judge_metadata_path = run_dir / "judge-metadata.json"
        if not metadata_path.is_file():
            continue
        metadata = read_json(metadata_path)
        strategy = str(metadata.get("strategy") or run_dir.parents[1].name)
        version = str(metadata.get("version") or run_dir.parent.name)
        run_id = int(metadata.get("run_id") or run_dir.name.split("-", 1)[1])

        b_prompt = numeric(metadata.get("total_prompt_tokens"))
        b_completion = numeric(metadata.get("total_completion_tokens"))
        b_wall = numeric(metadata.get("wall_clock_seconds"))

        j_prompt = j_completion = j_wall = None
        j_metered = None
        if judge_metadata_path.is_file():
            judge_metadata = read_json(judge_metadata_path)
            j_prompt = numeric(judge_metadata.get("total_prompt_tokens"))
            j_completion = numeric(judge_metadata.get("total_completion_tokens"))
            j_wall = numeric(judge_metadata.get("judge_wall_clock_seconds"))
            j_metered = numeric(judge_metadata.get("metered_responses"))

        notes: list[str] = []
        if not judge_metadata_path.is_file():
            notes.append("judge phase not run")
        elif j_wall is None:
            notes.append("judge wall-clock time not recorded; excluded from runtime total")
        b_total = b_prompt + b_completion if b_prompt is not None and b_completion is not None else None
        j_total = j_prompt + j_completion if j_prompt is not None and j_completion is not None else None
        all_tokens = (
            b_total + j_total
            if b_total is not None and j_total is not None
            else None
        )
        usd_b = usd(b_prompt, b_completion)
        usd_j = usd(j_prompt, j_completion)
        usd_all = usd_b + usd_j if usd_b is not None and usd_j is not None else None

        rows.append(
            {
                "strategy": strategy,
                "version": version,
                "run_id": run_id,
                "benchmark_prompt_tokens": fmt(b_prompt),
                "benchmark_completion_tokens": fmt(b_completion),
                "benchmark_total_tokens": fmt(b_total),
                "benchmark_wall_clock_s": fmt(b_wall),
                "judge_prompt_tokens": fmt(j_prompt),
                "judge_completion_tokens": fmt(j_completion),
                "judge_total_tokens": fmt(j_total),
                "judge_wall_clock_s": fmt(j_wall),
                "metered_judge_responses": fmt(j_metered),
                "all_tokens": fmt(all_tokens),
                "estimated_usd_benchmark": fmt(usd_b),
                "estimated_usd_judge": fmt(usd_j),
                "estimated_usd_total": fmt(usd_all),
                "notes": "; ".join(notes),
            }
        )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "price_input_usd_per_million": PRICE_IN_PER_M,
                "price_output_usd_per_million": PRICE_OUT_PER_M,
                "note": "estimated_usd_* is a token-based estimate using the pinned "
                "gpt-4o-mini reference price ($0.15/M input, $0.60/M output), not an "
                "API invoice. Actual billing may differ. 'unknown' means not recorded, "
                "never zero. Runtime totals must exclude unknown values and disclose "
                "their coverage.",
                "cells": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Built cost analysis: {len(rows)} cells -> {output_csv}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build per-cell cost analysis")
    parser.add_argument("--results-root", type=Path, default=Path("results"))
    parser.add_argument("--output-csv", type=Path, default=Path("reports/d/cost-analysis.csv"))
    parser.add_argument("--output-json", type=Path, default=Path("reports/d/cost-analysis.json"))
    args = parser.parse_args()
    try:
        build(args.results_root, args.output_csv, args.output_json)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise SystemExit(f"COST ANALYSIS ERROR: {exc}") from exc


if __name__ == "__main__":
    main()
