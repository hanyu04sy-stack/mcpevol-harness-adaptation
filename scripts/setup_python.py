#!/usr/bin/env python3
"""Create the pinned Python environment for macOS or Linux."""

from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import venv
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--venv", type=Path, default=Path(".venv"))
    parser.add_argument("--benchmark-root", type=Path, default=Path("external/MCPEvol-Bench"))
    parser.add_argument("--requirements", type=Path, default=Path("requirements/benchmark.txt"))
    args = parser.parse_args()

    if platform.system() not in {"Darwin", "Linux"}:
        raise SystemExit("This installer supports macOS and Linux only.")
    if sys.version_info[:2] != (3, 12):
        raise SystemExit(f"Python 3.12 is required; found {platform.python_version()}")
    benchmark_src = (args.benchmark_root / "src").resolve()
    fastchat_src = benchmark_src / "FastChat"
    if not benchmark_src.is_dir():
        raise SystemExit("Benchmark checkout missing. Run scripts/bootstrap_benchmark.py first.")

    if not args.venv.exists():
        venv.EnvBuilder(with_pip=True).create(args.venv)
    python = args.venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run([str(python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([str(python), "-m", "pip", "install", "-r", str(args.requirements)], check=True)

    result = subprocess.run(
        [str(python), "-c", "import site; print(site.getsitepackages()[0])"],
        check=True, text=True, capture_output=True,
    )
    path_file = Path(result.stdout.strip()) / "mcpevol_benchmark.pth"
    path_file.write_text(f"{benchmark_src}\n{fastchat_src}\n", encoding="utf-8")
    print(f"Python environment ready: {python}")


if __name__ == "__main__":
    main()

