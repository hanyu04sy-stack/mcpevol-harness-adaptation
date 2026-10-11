#!/usr/bin/env python3
"""Validate and report formal subset coverage requirements."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


CHANGE_TYPES = {"tool", "parameter", "description"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_coverage(
    tasks: list[dict[str, Any]], manifest: dict[str, Any]
) -> dict[str, Any]:
    details = manifest.get("selected_task_details")
    if not isinstance(details, list) or len(details) != len(tasks):
        raise ValueError("manifest details must contain one entry per task")
    task_ids = [int(task["idx"]) for task in tasks]
    detail_ids = [int(detail["idx"]) for detail in details]
    if manifest.get("selected_indices") != task_ids or detail_ids != task_ids:
        raise ValueError("task IDs and manifest details do not match")

    statuses = Counter(detail.get("status") for detail in details)
    type_counts = Counter(
        change_type
        for detail in details
        for change_type in detail.get("change_types", [])
    )
    for task, detail in zip(tasks, details, strict=True):
        required = sorted(task.get("servers", {}))
        if detail.get("required_servers") != required:
            raise ValueError(f"task {task['idx']} required server list does not match")
        if detail.get("status") == "affected":
            if not detail.get("affected_servers") or not detail.get("change_types"):
                raise ValueError(f"affected task {task['idx']} has no recorded change")
        elif detail.get("status") == "retention":
            if detail.get("affected_servers") or detail.get("change_types"):
                raise ValueError(f"retention task {task['idx']} records a change")
        else:
            raise ValueError(f"task {task['idx']} has an invalid status")

    requirements = {
        "tool_change": type_counts["tool"] > 0,
        "parameter_change": type_counts["parameter"] > 0,
        "description_change": type_counts["description"] > 0,
        "affected_recovery_tasks": statuses["affected"] > 0,
        "retention_tasks": statuses["retention"] > 0,
    }
    if not all(requirements.values()):
        missing = [name for name, passed in requirements.items() if not passed]
        raise ValueError("subset coverage is incomplete: " + ", ".join(missing))
    if set(type_counts) - CHANGE_TYPES:
        raise ValueError("manifest contains an unknown change type")
    if manifest.get("affected_count") != statuses["affected"]:
        raise ValueError("affected count does not match task details")
    if manifest.get("retention_count") != statuses["retention"]:
        raise ValueError("retention count does not match task details")
    if manifest.get("change_type_task_counts") != dict(sorted(type_counts.items())):
        raise ValueError("change-type counts do not match task details")

    return {
        "schema_version": 1,
        "passed": True,
        "benchmark_commit": manifest.get("benchmark_commit"),
        "task_count": len(tasks),
        "affected_recovery_task_count": statuses["affected"],
        "retention_task_count": statuses["retention"],
        "change_type_task_counts": dict(sorted(type_counts.items())),
        "requirements": requirements,
        "selected_indices": task_ids,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tasks", type=Path, default=Path("data/subsets/pilot-30/test_cases.json")
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("data/subsets/pilot-30/manifest.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("reports/pilot-30-coverage.json")
    )
    args = parser.parse_args()
    tasks = json.loads(args.tasks.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = validate_coverage(tasks, manifest)
    report["task_file_sha256"] = sha256(args.tasks)
    report["manifest_sha256"] = sha256(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
