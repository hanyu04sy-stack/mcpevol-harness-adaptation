#!/usr/bin/env python3
"""Build a machine-readable task-by-version MCP runnability matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from experiment_config import VERSIONS  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_matrix(
    tasks: list[dict[str, Any]], report: dict[str, Any]
) -> dict[str, Any]:
    versions = report.get("versions")
    if not isinstance(versions, dict) or set(versions) != set(VERSIONS):
        raise ValueError("environment report must define early, middle, and late")
    status_maps: dict[str, dict[str, str]] = {}
    for version in VERSIONS:
        result = versions[version]
        if result.get("validation_complete") is not True:
            raise ValueError(f"{version} environment validation is incomplete")
        servers = result.get("servers")
        if not isinstance(servers, list):
            raise ValueError(f"{version} environment has no server details")
        status_maps[version] = {
            str(server["name"]): str(server["status"]) for server in servers
        }

    rows = []
    for task in tasks:
        required = sorted(task.get("servers", {}))
        if not required:
            raise ValueError(f"task {task.get('idx')} has no MCP server dependency")
        version_results = {}
        for version in VERSIONS:
            unavailable = [
                server
                for server in required
                if status_maps[version].get(server) != "connected"
            ]
            version_results[version] = {
                "runnable": not unavailable,
                "unavailable_servers": unavailable,
                "server_statuses": {
                    server: status_maps[version].get(server, "not_observed")
                    for server in required
                },
            }
        rows.append(
            {
                "idx": int(task["idx"]),
                "required_servers": required,
                "versions": version_results,
                "runnable_in_all_versions": all(
                    item["runnable"] for item in version_results.values()
                ),
            }
        )

    version_summary = {
        version: {
            "runnable_task_count": sum(
                row["versions"][version]["runnable"] for row in rows
            ),
            "unrunnable_task_count": sum(
                not row["versions"][version]["runnable"] for row in rows
            ),
        }
        for version in VERSIONS
    }
    return {
        "schema_version": 1,
        "benchmark_commit": report.get("benchmark_commit"),
        "task_count": len(rows),
        "all_tasks_runnable_in_all_versions": all(
            row["runnable_in_all_versions"] for row in rows
        ),
        "version_summary": version_summary,
        "tasks": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tasks", type=Path, default=Path("data/subsets/pilot-30/test_cases.json")
    )
    parser.add_argument(
        "--environment-report",
        type=Path,
        default=Path("reports/pilot-30-environment-validation.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/pilot-30-runnability-matrix.json"),
    )
    parser.add_argument(
        "--allow-unrunnable",
        action="store_true",
        help="Write the matrix without failing when any task is not runnable",
    )
    args = parser.parse_args()
    tasks = json.loads(args.tasks.read_text(encoding="utf-8"))
    environment = json.loads(args.environment_report.read_text(encoding="utf-8"))
    matrix = build_matrix(tasks, environment)
    matrix["task_file_sha256"] = sha256(args.tasks)
    matrix["environment_report_sha256"] = sha256(args.environment_report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(matrix, ensure_ascii=False, indent=2))
    if not matrix["all_tasks_runnable_in_all_versions"] and not args.allow_unrunnable:
        raise SystemExit("ERROR: one or more tasks have unavailable MCP dependencies")


if __name__ == "__main__":
    main()
