#!/usr/bin/env python3
"""Run the complete, lightweight handoff gate for member A's deliverables."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


REQUIRED_FILES: dict[str, list[str]] = {
    "configs": [
        "configs/experiment.json",
        "configs/smoke.json",
        "configs/canary-real.json",
        "configs/canary-local.json",
        "schemas/experiment-config.schema.json",
        "schemas/task-list.schema.json",
        "schemas/subset-manifest.schema.json",
        "schemas/validation-report.schema.json",
    ],
    "task_sets": [
        "data/subsets/pilot-30/test_cases.json",
        "data/subsets/pilot-30/manifest.json",
        "data/subsets/smoke-1/test_cases.json",
        "data/subsets/canary-real-2/test_cases.json",
    ],
    "reports": [
        "reports/environment-validation.json",
        "reports/pilot-30-environment-validation.json",
        "reports/pilot-30-coverage.json",
        "reports/pilot-30-runnability-matrix.json",
        "reports/pilot-30-startup-stability.json",
        "reports/smoke/summary.json",
        "reports/canary-local-qwen35-4b-2/summary.json",
        "reports/tool-schemas/early.json",
        "reports/tool-schemas/middle.json",
        "reports/tool-schemas/late.json",
        "reports/tool-schemas/diff.json",
        *[
            f"reports/smoke/{version}/{name}"
            for version in ("early", "middle", "late")
            for name in ("trajectory-161.json", "model-events.json", "benchmark.log", "server.log")
        ],
        *[
            f"reports/canary-local-qwen35-4b-2/{version}/{name}"
            for version in ("early", "middle", "late")
            for name in ("trajectory-144.json", "trajectory-161.json", "benchmark.log", "server.log")
        ],
    ],
    "scripts": [
        "scripts/setup_environment.py",
        "scripts/setup_python.py",
        "scripts/bootstrap_benchmark.py",
        "scripts/download_server_bundles.py",
        "scripts/render_mcp_config.py",
        "scripts/check_environment.py",
        "scripts/validate_tool_environments.py",
        "scripts/validate_startup_stability.py",
        "scripts/build_subset.py",
        "scripts/validate_subset_coverage.py",
        "scripts/build_runnability_matrix.py",
        "scripts/check_experiment_config.py",
        "scripts/experiment_config.py",
        "scripts/run_benchmark.py",
        "scripts/run_smoke_tests.py",
        "scripts/build_real_canary_subset.py",
        "scripts/configure_api_credentials.py",
        "scripts/run_real_canary.py",
        "scripts/run_local_canary.py",
        "scripts/validate_ci_assets.py",
        "scripts/validate_json_schemas.py",
        "scripts/check_handoff.py",
        "scripts/dump_tool_schemas.py",
    ],
    "tests": [
        "tests/test_build_runnability_matrix.py",
        "tests/test_build_subset.py",
        "tests/test_ci_workflow.py",
        "tests/test_download_server_bundles.py",
        "tests/test_experiment_config.py",
        "tests/test_local_canary_report.py",
        "tests/test_real_canary.py",
        "tests/test_smoke_report.py",
        "tests/test_validate_ci_assets.py",
        "tests/test_validate_json_schemas.py",
        "tests/test_validate_startup_stability.py",
        "tests/test_validate_subset_coverage.py",
        "tests/test_validate_tool_environments.py",
        "tests/test_check_handoff.py",
        "tests/test_troubleshooting_doc.py",
        "tests/test_dump_tool_schemas.py",
        "tests/test_english_only_repository.py",
    ],
    "harness": [
        "harness/original/system_prompt.md",
        "harness/original/tool_usage_rules.md",
        "harness/original/manifest.json",
        "harness/no_update/system_prompt.md",
        "harness/no_update/tool_usage_rules.md",
        "harness/no_update/manifest.json",
        "harness/full_rewrite/README.md",
        "harness/selective_patch/README.md",
    ],
    "documentation": [
        "README.md",
        "docs/ENVIRONMENT.md",
        "docs/ENVIRONMENT_VALIDATION.md",
        "docs/SUBSET.md",
        "docs/RUNNING.md",
        "docs/SMOKE_TEST.md",
        "docs/HANDOFF.md",
        "docs/TROUBLESHOOTING.md",
        "requirements-ci.txt",
    ],
}


def check_inventory(
    root: Path, required_files: dict[str, list[str]] = REQUIRED_FILES
) -> dict[str, Any]:
    missing: list[str] = []
    empty: list[str] = []
    category_counts: dict[str, int] = {}
    for category, relative_paths in required_files.items():
        category_counts[category] = len(relative_paths)
        for relative in relative_paths:
            path = root / relative
            if not path.is_file():
                missing.append(relative)
            elif path.stat().st_size == 0:
                empty.append(relative)
    return {
        "passed": not missing and not empty,
        "required_file_count": sum(category_counts.values()),
        "category_counts": category_counts,
        "missing": missing,
        "empty": empty,
    }


def run_check(name: str, command: list[str], cwd: Path) -> dict[str, Any]:
    started = time.monotonic()
    process = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    combined = "\n".join(part.strip() for part in (process.stdout, process.stderr) if part.strip())
    result: dict[str, Any] = {
        "name": name,
        "passed": process.returncode == 0,
        "returncode": process.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
    }
    if name == "unit_tests":
        match = re.search(r"Ran (\d+) tests?", combined)
        result["tests_run"] = int(match.group(1)) if match else None
    if process.returncode != 0:
        result["output_tail"] = combined[-4000:]
    return result


def run_handoff(root: Path, inventory_only: bool = False) -> dict[str, Any]:
    inventory = check_inventory(root)
    checks: list[dict[str, Any]] = []
    if inventory["passed"] and not inventory_only:
        python = sys.executable
        checks = [
            run_check("json_schema_validation", [python, "scripts/validate_json_schemas.py", "--root", str(root)], root),
            run_check("semantic_asset_validation", [python, "scripts/validate_ci_assets.py", "--root", str(root)], root),
            run_check("python_compilation", [python, "-m", "compileall", "-q", "scripts", "tests"], root),
            run_check("unit_tests", [python, "-m", "unittest", "discover", "-s", "tests", "-v"], root),
        ]
    passed = inventory["passed"] and all(check["passed"] for check in checks)
    return {
        "schema_version": 1,
        "passed": passed,
        "mode": "inventory_only" if inventory_only else "complete_lightweight_handoff",
        "server_bundles_used": False,
        "inventory": inventory,
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_handoff(args.root.resolve(), inventory_only=args.inventory_only)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="", file=sys.stdout if report["passed"] else sys.stderr)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
