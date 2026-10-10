#!/usr/bin/env python3
"""Clone MCPEvol-Bench and check out the project-pinned commit."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

REPOSITORY = "https://github.com/Octobrist/MCPEvol-Bench.git"
PINNED_COMMIT = "888c779a0fe735f612ca62bdd1fdd7c9e6bf8701"


def run(*args: str, cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", default="external/MCPEvol-Bench")
    args = parser.parse_args()
    destination = Path(args.destination).resolve()

    if destination.exists() and any(destination.iterdir()):
        current = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=destination, text=True,
            capture_output=True, check=True,
        ).stdout.strip()
        if current != PINNED_COMMIT:
            raise SystemExit(
                f"Existing checkout is at {current}; expected {PINNED_COMMIT}. "
                "Move it aside or choose another --destination."
            )
        print(f"Benchmark already ready at {destination}")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    run("git", "clone", REPOSITORY, str(destination))
    run("git", "checkout", "--detach", PINNED_COMMIT, cwd=destination)
    print(f"Benchmark ready at {destination} ({PINNED_COMMIT})")


if __name__ == "__main__":
    main()

