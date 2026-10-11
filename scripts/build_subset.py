#!/usr/bin/env python3
"""Build a deterministic recovery + retention subset for MCPEvol-Bench."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

PINNED_COMMIT = "888c779a0fe735f612ca62bdd1fdd7c9e6bf8701"
CHANGE_TYPES = ("tool", "parameter", "description")
VERSIONS = ("early", "middle", "late")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def infer_change_types(change: Any) -> set[str]:
    if not isinstance(change, dict):
        return set()
    keys: set[str] = set()
    stack = [change]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            keys.update(current)
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    result: set[str] = set()
    if keys & {"new_tool_config", "integration_summary", "tool"}:
        result.add("tool")
    if keys & {
        "parameter_additions", "parameter_removals", "parameter_changes",
        "parameters", "input_schema", "output_schema",
    }:
        result.add("parameter")
    if keys & {
        "tool_description_change", "original_description", "modified_description",
        "old_description", "new_description",
    }:
        result.add("description")
    return result or {"tool"}


def changed_server_types(evolution_paths: list[Path]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for path in evolution_paths:
        for server, change in read_json(path).items():
            result.setdefault(server, set()).update(infer_change_types(change))
    return result


def connected_servers(report: dict[str, Any]) -> dict[str, set[str]]:
    versions = report.get("versions")
    if not isinstance(versions, dict) or not set(VERSIONS) <= set(versions):
        raise ValueError("availability report must contain early, middle, and late")
    result = {}
    for version in VERSIONS:
        servers = versions[version].get("servers")
        if not isinstance(servers, list):
            raise ValueError(f"availability report has no server list for {version}")
        result[version] = {
            item["name"]
            for item in servers
            if item.get("status") == "connected" and item.get("available") is True
        }
    return result


def select_subset(
    tasks: list[dict[str, Any]],
    server_types: dict[str, set[str]],
    size: int,
    seed: int,
    affected_fraction: float = 0.8,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if size <= 0 or size > len(tasks):
        raise ValueError(f"size must be between 1 and {len(tasks)}")
    rng = random.Random(seed)
    annotated = []
    for task in tasks:
        servers = set(task.get("servers", {}))
        changed = servers & set(server_types)
        labels = sorted({label for server in changed for label in server_types[server]})
        annotated.append((task, changed, labels))

    affected = [row for row in annotated if row[1]]
    retention = [row for row in annotated if not row[1]]
    rng.shuffle(affected)
    rng.shuffle(retention)
    retention_target = min(len(retention), max(1, round(size * (1 - affected_fraction))))
    affected_target = size - retention_target
    if len(affected) < affected_target:
        affected_target = len(affected)
        retention_target = size - affected_target
    if len(retention) < retention_target:
        raise ValueError("Not enough tasks to satisfy the requested subset size")

    chosen: list[tuple[dict[str, Any], set[str], list[str]]] = []
    used_ids: set[int] = set()
    for label in CHANGE_TYPES:
        candidate = next(
            (row for row in affected if label in row[2] and int(row[0]["idx"]) not in used_ids),
            None,
        )
        if candidate and len(chosen) < affected_target:
            chosen.append(candidate)
            used_ids.add(int(candidate[0]["idx"]))
    for row in affected:
        idx = int(row[0]["idx"])
        if len(chosen) >= affected_target:
            break
        if idx not in used_ids:
            chosen.append(row)
            used_ids.add(idx)
    chosen.extend(retention[:retention_target])
    chosen.sort(key=lambda row: int(row[0]["idx"]))

    covered = {label for row in chosen for label in row[2]}
    missing_types = set(CHANGE_TYPES) - covered
    if missing_types:
        raise ValueError(
            "Eligible tasks do not cover change types: "
            + ", ".join(sorted(missing_types))
        )

    selected_tasks = [row[0] for row in chosen]
    type_counts = Counter(label for row in chosen for label in row[2])
    manifest = {
        "benchmark_commit": PINNED_COMMIT,
        "version_mapping": {
            "early": "original",
            "middle": "iter3",
            "late": "iter5",
        },
        "seed": seed,
        "requested_size": size,
        "actual_size": len(selected_tasks),
        "affected_count": sum(bool(row[1]) for row in chosen),
        "retention_count": sum(not row[1] for row in chosen),
        "change_type_task_counts": dict(sorted(type_counts.items())),
        "selected_indices": [int(task["idx"]) for task in selected_tasks],
        "selected_task_details": [
            {
                "idx": int(row[0]["idx"]),
                "status": "affected" if row[1] else "retention",
                "affected_servers": sorted(row[1]),
                "change_types": row[2],
                "required_servers": sorted(row[0].get("servers", {})),
            }
            for row in chosen
        ],
    }
    return selected_tasks, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--size", type=int, default=30)
    parser.add_argument("--seed", type=int, default=6203)
    parser.add_argument("--affected-fraction", type=float, default=0.8)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--availability-report",
        type=Path,
        help="Only select tasks whose servers are connected in every version",
    )
    args = parser.parse_args()

    data_root = args.benchmark_root / "src/custom/data"
    task_path = data_root / "test_cases/test_cases.json"
    evolution_paths = [
        data_root / "mutation/HYBRID/evolution.json",
        data_root / "mutation/HYBRID/HYBRID/evolution.json",
    ]
    tasks = read_json(task_path)
    configured_server_sets = []
    for version_dir in ("original", "iter3", "iter5"):
        config_path = args.benchmark_root / "servers/1mcp_config" / version_dir / "mcp.json"
        configured_server_sets.append(set(read_json(config_path)["mcpServers"]))
    common_configured_servers = set.intersection(*configured_server_sets)
    eligible_servers = common_configured_servers
    availability: dict[str, Any] | None = None
    if args.availability_report:
        availability = read_json(args.availability_report)
        if availability.get("benchmark_commit") != PINNED_COMMIT:
            raise ValueError("availability report benchmark commit does not match")
        per_version = connected_servers(availability)
        eligible_servers = common_configured_servers & set.intersection(
            *per_version.values()
        )
    eligible_tasks = [
        task
        for task in tasks
        if task.get("servers") and set(task["servers"]) <= eligible_servers
    ]
    server_types = changed_server_types(evolution_paths)
    selected, manifest = select_subset(
        eligible_tasks, server_types, args.size, args.seed, args.affected_fraction
    )
    manifest["source_test_cases_sha256"] = hashlib.sha256(task_path.read_bytes()).hexdigest()
    manifest["source_task_count"] = len(tasks)
    manifest["eligible_task_count"] = len(eligible_tasks)
    manifest["excluded_due_to_missing_server_count"] = len(tasks) - len(eligible_tasks)
    manifest["common_configured_server_count"] = len(common_configured_servers)
    manifest["eligibility_basis"] = (
        "connected_in_all_versions" if availability else "configured_in_all_versions"
    )
    manifest["common_eligible_server_count"] = len(eligible_servers)
    manifest["common_eligible_servers"] = sorted(eligible_servers)
    if availability is not None:
        manifest["availability_report"] = str(args.availability_report)
        manifest["availability_report_sha256"] = hashlib.sha256(
            args.availability_report.read_bytes()
        ).hexdigest()
        manifest["availability_report_generated_at"] = availability.get("generated_at")
        manifest["connected_server_counts"] = {
            version: len(connected_servers(availability)[version])
            for version in VERSIONS
        }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "test_cases.json").write_text(
        json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
