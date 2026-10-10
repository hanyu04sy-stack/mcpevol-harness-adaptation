#!/usr/bin/env python3
"""Report whether the local machine has the benchmark prerequisites."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def command_version(
    command: str, flag: str = "--version", fallback: Path | None = None
) -> dict[str, object]:
    path = shutil.which(command)
    if not path and fallback and fallback.is_file():
        path = str(fallback.resolve())
    if not path:
        return {"ok": False, "path": None, "version": None}
    result = subprocess.run([path, flag], text=True, capture_output=True)
    version = (result.stdout or result.stderr).strip().splitlines()
    return {
        "ok": result.returncode == 0,
        "path": path,
        "version": version[0] if version else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--benchmark-root", default="external/MCPEvol-Bench")
    parser.add_argument("--server-bundle-root", default="external/servers")
    args = parser.parse_args()

    benchmark_root = Path(args.benchmark_root)
    bundle_root = Path(args.server_bundle_root)
    checks = {
        "platform": platform.platform(),
        "python": {
            "ok": sys.version_info[:2] == (3, 12),
            "path": sys.executable,
            "version": platform.python_version(),
            "expected": "3.12.x",
        },
        "node": command_version("node"),
        "npm": command_version("npm"),
        "1mcp": command_version("1mcp", fallback=Path("node_modules/.bin/1mcp")),
        "benchmark_checkout": {
            "ok": (benchmark_root / "src/custom/data/test_cases/test_cases.json").is_file(),
            "path": str(benchmark_root.resolve()),
        },
        "middle_server_bundle": {
            "ok": (bundle_root / "iter3_servers").is_dir(),
            "path": str((bundle_root / "iter3_servers").resolve()),
        },
        "late_server_bundle": {
            "ok": (bundle_root / "iter5_servers").is_dir(),
            "path": str((bundle_root / "iter5_servers").resolve()),
        },
    }
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    ok = all(value.get("ok", True) for value in checks.values() if isinstance(value, dict))
    if args.strict and not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
