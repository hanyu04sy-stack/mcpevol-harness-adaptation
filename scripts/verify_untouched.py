#!/usr/bin/env python3
"""Enforce the immutable inputs shared by all harness strategies."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_HARNESS_DIRS = {"original", "no_update", "full_rewrite", "selective_patch"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dotted(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(path)
        value = value[part]
    return value


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )


def verify_run_metadata_model(metadata_path: Path, pins_path: Path) -> None:
    """Ensure recorded runtime metadata uses the fairness-pinned model."""
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    pins = json.loads(pins_path.read_text(encoding="utf-8"))
    expected = pins["model.name"]
    model = metadata.get("model")
    actual = model.get("name") if isinstance(model, dict) else metadata.get("model_name")
    if actual != expected:
        raise ValueError(
            f"run metadata model mismatch: expected {expected!r}, got {actual!r}"
        )


def check_fairness(
    *,
    config_path: Path,
    pins_path: Path,
    report_path: Path,
    root: Path,
) -> dict[str, Any]:
    root = root.resolve()
    config_path = config_path if config_path.is_absolute() else root / config_path
    pins_path = pins_path if pins_path.is_absolute() else root / pins_path
    report_path = report_path if report_path.is_absolute() else root / report_path
    config = json.loads(config_path.read_text(encoding="utf-8"))
    pins = json.loads(pins_path.read_text(encoding="utf-8"))
    upstream = root / config["benchmark"]["root"]

    upstream_status = git(upstream, "status", "--porcelain")
    upstream_clean = upstream_status.returncode == 0 and not upstream_status.stdout.strip()
    upstream_diff = ""
    if not upstream_clean:
        diff = git(upstream, "diff", "--stat", "--", ".")
        upstream_diff = (upstream_status.stdout + diff.stdout + diff.stderr).strip()[-4000:]

    task_path = root / config["dataset"]["path"]
    expected_task_sha = str(config["dataset"]["sha256"])
    actual_task_sha = sha256(task_path) if task_path.is_file() else None
    task_match = actual_task_sha == expected_task_sha

    mismatches: list[dict[str, Any]] = []
    for key, expected in pins.items():
        if key == "schema_version":
            continue
        try:
            actual = dotted(config, key)
        except KeyError:
            actual = None
        if actual != expected:
            mismatches.append({"field": key, "expected": expected, "actual": actual})
    pinned_match = not mismatches

    warnings: list[str] = []
    workspace = git(root, "diff", "--name-only")
    if workspace.returncode == 0:
        for line in workspace.stdout.splitlines():
            relative = line.strip().strip('"')
            if relative.startswith(("configs/experiment.json", "data/subsets/", "external/")):
                warnings.append(f"protected working-tree path changed: {relative}")
            if relative.startswith("harness/"):
                parts = Path(relative).parts
                if len(parts) > 1 and parts[1] not in ALLOWED_HARNESS_DIRS:
                    warnings.append(f"unexpected harness directory: {parts[1]}")
    harness_root = root / "harness"
    if harness_root.is_dir():
        for path in harness_root.iterdir():
            if path.is_dir() and path.name not in ALLOWED_HARNESS_DIRS:
                warnings.append(f"unexpected harness directory: {path.name}")

    payload = {
        "schema_version": 1,
        "passed": upstream_clean and task_match and pinned_match,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "upstream_clean": upstream_clean,
        "upstream_status": upstream_diff,
        "task_sha256_match": task_match,
        "expected_task_sha256": expected_task_sha,
        "actual_task_sha256": actual_task_sha,
        "pinned_config_match": pinned_match,
        "pinned_mismatches": mismatches,
        "warnings": warnings,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify immutable fairness inputs")
    parser.add_argument("--config", type=Path, default=Path("configs/experiment.json"))
    parser.add_argument("--pins", type=Path, default=Path("configs/fairness-pins.json"))
    parser.add_argument("--report", type=Path, default=Path("reports/fairness-check.json"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        result = check_fairness(
            config_path=args.config,
            pins_path=args.pins,
            report_path=args.report,
            root=args.root,
        )
    except (OSError, KeyError, ValueError, json.JSONDecodeError, subprocess.SubprocessError) as exc:
        raise SystemExit(f"FAIRNESS ERROR: {exc}") from exc
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
