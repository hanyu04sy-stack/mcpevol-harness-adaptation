#!/usr/bin/env python3
"""One-command reproducible setup for member A's benchmark environment."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from experiment_config import VERSIONS


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(*args: str) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-repair", action="store_true")
    args = parser.parse_args()
    experiment = json.loads((ROOT / "configs/experiment.json").read_text(encoding="utf-8"))
    task_file = str(experiment["dataset"]["path"])
    run(PYTHON, "scripts/bootstrap_benchmark.py")
    run(PYTHON, "scripts/setup_python.py")
    pnpm = shutil.which("pnpm")
    if not pnpm:
        raise SystemExit("pnpm is required (expected version 11.25.x).")
    run(pnpm, "install", "--frozen-lockfile")
    try:
        subprocess.run(
            [str(ROOT / "node_modules/.bin/1mcp"), "--version"],
            cwd=ROOT,
            check=True,
            timeout=30,
            stdout=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        print("Local node_modules is unreadable; reinstalling it...", flush=True)
        shutil.rmtree(ROOT / "node_modules", ignore_errors=True)
        run(pnpm, "install", "--frozen-lockfile")
    download_args = [PYTHON, "scripts/download_server_bundles.py"]
    if not args.skip_repair:
        download_args.append("--repair-extraction")
    run(*download_args)
    for version in VERSIONS:
        run(
            PYTHON, "scripts/render_mcp_config.py",
            "--benchmark-root", "external/MCPEvol-Bench",
            "--server-bundle-root", "external/servers",
            "--version", version,
            "--test-case-file", task_file,
            "--output", f"generated/1mcp/{version}.json",
        )
        run(
            PYTHON, "scripts/render_mcp_config.py",
            "--benchmark-root", "external/MCPEvol-Bench",
            "--server-bundle-root", "external/servers",
            "--version", version,
            "--test-case-file", "data/subsets/smoke-1/test_cases.json",
            "--output", f"generated/1mcp-smoke/{version}.json",
        )
    run(PYTHON, "scripts/validate_subset_coverage.py")
    run(PYTHON, "scripts/build_runnability_matrix.py")
    run(PYTHON, "scripts/check_experiment_config.py")
    run(PYTHON, "scripts/check_experiment_config.py", "--config", "configs/smoke.json")
    run(PYTHON, "scripts/check_environment.py", "--strict")


if __name__ == "__main__":
    main()

