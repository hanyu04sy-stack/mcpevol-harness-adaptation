#!/usr/bin/env python3
"""One-command reproducible setup for member A's benchmark environment."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(*args: str) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> None:
    run(PYTHON, "scripts/bootstrap_benchmark.py")
    run(PYTHON, "scripts/setup_python.py")
    pnpm = shutil.which("pnpm")
    if not pnpm:
        raise SystemExit("pnpm is required (expected version 11.25.x).")
    run(pnpm, "install", "--frozen-lockfile")
    run(PYTHON, "scripts/download_server_bundles.py")
    for version in ("early", "middle", "late"):
        run(
            PYTHON, "scripts/render_mcp_config.py",
            "--benchmark-root", "external/MCPEvol-Bench",
            "--server-bundle-root", "external/servers",
            "--version", version,
            "--test-case-file", "data/subsets/pilot-30/test_cases.json",
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
    run(PYTHON, "scripts/check_experiment_config.py")
    run(PYTHON, "scripts/check_experiment_config.py", "--config", "configs/smoke.json")
    run(PYTHON, "scripts/check_environment.py", "--strict")


if __name__ == "__main__":
    main()

