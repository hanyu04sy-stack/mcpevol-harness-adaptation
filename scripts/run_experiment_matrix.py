#!/usr/bin/env python3
"""Plan and execute the complete fair strategy/version/repeat experiment matrix."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ("early", "middle", "late")
STRATEGIES = ("no_update", "full_rewrite", "selective_patch")


@dataclass(frozen=True)
class RunSpec:
    strategy: str
    version: str
    run_id: int
    harness_dir: str


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def harness_for(strategy: str, version: str) -> Path:
    if strategy == "selective_patch":
        return ROOT / "harness" / strategy / version
    if strategy == "full_rewrite":
        versioned = ROOT / "harness" / strategy / version
        if versioned.is_dir():
            return versioned
    return ROOT / "harness" / strategy


def build_specs(
    strategies: tuple[str, ...],
    versions: tuple[str, ...],
    run_ids: tuple[int, ...],
) -> list[RunSpec]:
    specs: list[RunSpec] = []
    for version in versions:
        for strategy in strategies:
            harness = harness_for(strategy, version)
            if not harness.is_dir():
                raise ValueError(f"missing harness directory: {harness}")
            for run_id in run_ids:
                if run_id < 1:
                    raise ValueError("run IDs must be positive")
                specs.append(
                    RunSpec(strategy, version, run_id, relative(harness))
                )
    return specs


def result_dir(spec: RunSpec) -> Path:
    return ROOT / "results" / spec.strategy / spec.version / f"run-{spec.run_id:02d}"


def benchmark_complete(spec: RunSpec, task_ids: set[int]) -> bool:
    directory = result_dir(spec)
    metadata_path = directory / "run-metadata.json"
    if not metadata_path.is_file():
        return False
    metadata = read_json(metadata_path)
    if metadata.get("status") != "completed":
        return False
    observed = {
        int(read_json(path)["idx"])
        for path in directory.glob("*/ANSWER/*.json")
    }
    return observed == task_ids


def judge_complete(spec: RunSpec, task_ids: set[int], judge_runs: int) -> bool:
    path = result_dir(spec) / "judge-results.json"
    if not path.is_file():
        return False
    tasks = read_json(path).get("tasks", [])
    if {int(task["task_idx"]) for task in tasks} != task_ids:
        return False
    return all(int(task.get("successful_judge_runs", 0)) >= judge_runs for task in tasks)


def benchmark_command(spec: RunSpec, config: str) -> list[str]:
    return [
        sys.executable,
        "scripts/run_benchmark.py",
        "--version",
        spec.version,
        "--config",
        config,
        "--harness-dir",
        spec.harness_dir,
        "--run-id",
        str(spec.run_id),
    ]


def judge_command(spec: RunSpec, config: str, judge_runs: int) -> list[str]:
    return [
        sys.executable,
        "scripts/run_judge.py",
        "--version",
        spec.version,
        "--config",
        config,
        "--harness-dir",
        spec.harness_dir,
        "--run-id",
        str(spec.run_id),
        "--num-runs",
        str(judge_runs),
    ]


def run(command: list[str]) -> None:
    print("RUN " + subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plan or execute the complete MCPEvol comparison matrix"
    )
    parser.add_argument(
        "--config", default="configs/comparison-subset/experiment.json"
    )
    parser.add_argument("--strategies", nargs="+", choices=STRATEGIES, default=STRATEGIES)
    parser.add_argument("--versions", nargs="+", choices=VERSIONS, default=VERSIONS)
    parser.add_argument("--run-ids", nargs="+", type=int, default=(1, 2, 3))
    parser.add_argument("--judge-runs", type=int, default=5)
    parser.add_argument("--phase", choices=("all", "benchmark", "judge"), default="all")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--rerun-completed", action="store_true")
    parser.add_argument("--skip-preflight", action="store_true")
    parser.add_argument("--keep-going", action="store_true")
    parser.add_argument(
        "--plan-output", type=Path, default=Path("reports/d/experiment-matrix-plan.json")
    )
    args = parser.parse_args()

    config_path = ROOT / args.config
    config = read_json(config_path)
    tasks_path = ROOT / config["dataset"]["path"]
    task_ids = {int(task["idx"]) for task in read_json(tasks_path)}
    if args.judge_runs < 1:
        raise SystemExit("--judge-runs must be positive")
    specs = build_specs(tuple(args.strategies), tuple(args.versions), tuple(args.run_ids))
    generic_full_rewrite = any(
        spec.strategy == "full_rewrite" and spec.harness_dir == "harness/full_rewrite"
        for spec in specs
    )
    plan = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": args.config,
        "task_count": len(task_ids),
        "task_ids": sorted(task_ids),
        "judge_runs_per_task": args.judge_runs,
        "benchmark_run_count": len(specs),
        "expected_trajectory_count": len(specs) * len(task_ids),
        "expected_judge_score_count": len(specs) * len(task_ids) * args.judge_runs,
        "full_rewrite_is_version_specific": not generic_full_rewrite,
        "warnings": (
            [
                "Full Rewrite uses one generic harness for all versions. A strict full-rewrite baseline should generate one complete harness per version."
            ]
            if generic_full_rewrite
            else []
        ),
        "runs": [asdict(spec) for spec in specs],
        "secrets_recorded": False,
    }
    output = args.plan_output if args.plan_output.is_absolute() else ROOT / args.plan_output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: plan[key] for key in (
        "task_count",
        "judge_runs_per_task",
        "benchmark_run_count",
        "expected_trajectory_count",
        "expected_judge_score_count",
        "full_rewrite_is_version_specific",
        "warnings",
    )}, ensure_ascii=False, indent=2))
    print(f"Plan written: {output}")
    if not args.execute:
        return

    if not args.skip_preflight:
        run([sys.executable, "scripts/check_experiment_config.py", "--config", args.config])
        run(
            [
                sys.executable,
                "scripts/verify_untouched.py",
                "--config",
                args.config,
                "--report",
                "reports/d/fairness-preflight.json",
            ]
        )

    failures: list[dict[str, object]] = []
    for spec in specs:
        try:
            if args.phase in {"all", "benchmark"}:
                if args.rerun_completed or not benchmark_complete(spec, task_ids):
                    run(benchmark_command(spec, args.config))
                else:
                    print(f"SKIP completed benchmark: {spec}")
            if args.phase in {"all", "judge"}:
                if not benchmark_complete(spec, task_ids):
                    raise RuntimeError(f"benchmark is incomplete: {spec}")
                if args.rerun_completed or not judge_complete(spec, task_ids, args.judge_runs):
                    run(judge_command(spec, args.config, args.judge_runs))
                else:
                    print(f"SKIP completed judge: {spec}")
        except (OSError, ValueError, KeyError, subprocess.CalledProcessError, RuntimeError) as exc:
            failures.append({"run": asdict(spec), "error": str(exc)})
            if not args.keep_going:
                break

    if failures:
        failure_path = ROOT / "reports/d/experiment-matrix-failures.json"
        failure_path.write_text(
            json.dumps({"failures": failures}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        raise SystemExit(f"{len(failures)} matrix run(s) failed; see {failure_path}")


if __name__ == "__main__":
    main()
