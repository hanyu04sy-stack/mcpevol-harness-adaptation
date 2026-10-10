#!/usr/bin/env python3
"""Report whether the local machine has the benchmark prerequisites."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import hashlib
from pathlib import Path


BUNDLE_HASHES = {
    "iter3_servers.zip": "18ef1f0c693b4d84730992211f0663817973f3fb6b436e2e77f7c082137e2391",
    "iter5_servers.zip": "67cc5adc6959acfa978ee67a0b53cc02f2fb064b16811d7a300a505117acaad1",
}


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def python_packages(python: Path) -> dict[str, object]:
    packages = ["accelerate", "backoff", "cachetools", "mcp", "openai", "pydantic", "requests", "torch", "tqdm", "transformers"]
    if not python.is_file():
        return {"ok": False, "python": str(python), "missing": packages}
    code = "import " + ", ".join(packages)
    result = subprocess.run([str(python), "-c", code], text=True, capture_output=True)
    return {
        "ok": result.returncode == 0,
        "python": str(python.resolve()),
        "error": result.stderr.strip() or None,
    }


def benchmark_import(python: Path) -> dict[str, object]:
    if not python.is_file():
        return {"ok": False, "error": "virtual-environment Python is missing"}
    result = subprocess.run(
        [str(python), "-c", "import custom.real_mcp.tool_level_test"],
        text=True,
        capture_output=True,
    )
    return {
        "ok": result.returncode == 0,
        "error": result.stderr.strip() if result.returncode else None,
    }


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
    venv_python = Path(".venv/bin/python")
    archives = bundle_root / "archives"
    bundle_checks = {}
    for filename, expected in BUNDLE_HASHES.items():
        actual = file_sha256(archives / filename)
        bundle_checks[filename] = {
            "ok": actual == expected,
            "path": str((archives / filename).resolve()),
            "sha256": actual,
            "expected_sha256": expected,
        }
    checks = {
        "platform": platform.platform(),
        "python": {
            "ok": sys.version_info[:2] == (3, 12),
            "path": sys.executable,
            "version": platform.python_version(),
            "expected": "3.12.x",
        },
        "node": command_version("node"),
        "pnpm": command_version("pnpm"),
        "1mcp": command_version("1mcp", fallback=Path("node_modules/.bin/1mcp")),
        "python_packages": python_packages(venv_python),
        "benchmark_runner_import": benchmark_import(venv_python),
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
        "bundle_archives": {
            "ok": all(item["ok"] for item in bundle_checks.values()),
            "files": bundle_checks,
        },
        "generated_configs": {
            "ok": all((Path("generated/1mcp") / f"{version}.json").is_file() for version in ("early", "middle", "late")),
            "path": str(Path("generated/1mcp").resolve()),
        },
    }
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    ok = all(value.get("ok", True) for value in checks.values() if isinstance(value, dict))
    if args.strict and not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
