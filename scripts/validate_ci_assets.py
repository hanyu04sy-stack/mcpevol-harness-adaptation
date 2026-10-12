#!/usr/bin/env python3
"""Validate tracked configs and task manifests without installing server bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from experiment_config import VERSIONS

VERSION_SET = set(VERSIONS)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


class ValidationError(ValueError):
    """A tracked CI asset is missing or internally inconsistent."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError(f"{path}: cannot read valid JSON: {exc}") from exc


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_tasks(path: Path, expected_size: int, expected_hash: str) -> list[int]:
    require(path.is_file(), f"{path}: task file is missing")
    require(SHA256_RE.fullmatch(expected_hash) is not None, "invalid dataset SHA-256")
    require(sha256(path) == expected_hash, f"{path}: SHA-256 does not match config")
    tasks = read_json(path)
    require(isinstance(tasks, list), f"{path}: top-level value must be a list")
    require(len(tasks) == expected_size, f"{path}: expected {expected_size} tasks")

    indices: list[int] = []
    for position, task in enumerate(tasks):
        require(isinstance(task, dict), f"{path}: task {position} must be an object")
        idx = task.get("idx")
        require(isinstance(idx, int), f"{path}: task {position} has no integer idx")
        indices.append(idx)
        require(
            isinstance(task.get("question"), str) and bool(task["question"].strip()),
            f"{path}: task {idx} has no question",
        )
        servers = task.get("servers")
        require(isinstance(servers, dict) and bool(servers), f"{path}: task {idx} has no servers")
        for server, tools in servers.items():
            require(isinstance(server, str) and bool(server), f"{path}: invalid server name")
            require(
                isinstance(tools, list)
                and bool(tools)
                and all(isinstance(tool, str) and tool for tool in tools),
                f"{path}: task {idx} has an invalid tool list for {server}",
            )
    require(len(indices) == len(set(indices)), f"{path}: duplicate task idx")
    return indices


def validate_manifest(path: Path, task_ids: list[int]) -> None:
    manifest = read_json(path)
    require(isinstance(manifest, dict), f"{path}: manifest must be an object")
    require(manifest.get("actual_size") == len(task_ids), f"{path}: actual_size mismatch")
    require(manifest.get("selected_indices") == task_ids, f"{path}: selected_indices mismatch")
    details = manifest.get("selected_task_details")
    require(isinstance(details, list) and len(details) == len(task_ids), f"{path}: details mismatch")
    require(all(isinstance(item, dict) for item in details), f"{path}: every detail must be an object")
    detail_ids = [item.get("idx") for item in details]
    require(detail_ids == task_ids, f"{path}: task detail order/IDs mismatch")
    statuses = {item.get("status") for item in details}
    change_types = {
        change
        for item in details
        for change in item.get("change_types", [])
        if isinstance(item, dict)
    }
    require({"affected", "retention"} <= statuses, f"{path}: affected/retention coverage missing")
    require(
        {"tool", "parameter", "description"} <= change_types,
        f"{path}: tool/parameter/description coverage missing",
    )


def validate_linked_report(root: Path, dataset: dict[str, Any], key: str) -> dict[str, Any]:
    relative = dataset.get(key)
    expected = dataset.get(f"{key}_sha256")
    require(isinstance(relative, str) and relative, f"dataset.{key} must be set")
    require(isinstance(expected, str) and SHA256_RE.fullmatch(expected) is not None, f"invalid {key} SHA-256")
    path = root / relative
    require(path.is_file(), f"{path}: linked report is missing")
    require(sha256(path) == expected, f"{path}: linked report SHA-256 mismatch")
    report = read_json(path)
    require(isinstance(report, dict), f"{path}: report must be an object")
    return report


def validate_experiment_config(root: Path, path: Path) -> dict[str, Any]:
    config = read_json(path)
    require(isinstance(config, dict), f"{path}: config must be an object")
    require(config.get("schema_version") == 1, f"{path}: unsupported schema_version")
    benchmark = config.get("benchmark", {})
    require(COMMIT_RE.fullmatch(str(benchmark.get("commit", ""))) is not None, f"{path}: invalid benchmark commit")
    harness = config.get("harness", {})
    harness_relative = harness.get("default_dir") if isinstance(harness, dict) else None
    require(
        isinstance(harness_relative, str) and harness_relative,
        f"{path}: missing harness.default_dir",
    )
    harness_dir = root / harness_relative
    for filename in ("system_prompt.md", "tool_usage_rules.md", "manifest.json"):
        require(
            (harness_dir / filename).is_file(),
            f"{path}: harness file is missing: {harness_relative}/{filename}",
        )
    harness_manifest = read_json(harness_dir / "manifest.json")
    require(
        harness_manifest.get("benchmark_commit") == benchmark.get("commit"),
        f"{path}: harness benchmark commit mismatch",
    )

    versions = config.get("mcp", {}).get("versions", {})
    require(set(versions) == VERSION_SET, f"{path}: MCP versions must be early/middle/late")
    urls: list[str] = []
    for version in sorted(VERSIONS):
        entry = versions[version]
        require(isinstance(entry, dict), f"{path}: invalid {version} MCP config")
        require(isinstance(entry.get("url"), str) and entry["url"], f"{path}: missing {version} URL")
        require(
            isinstance(entry.get("server_config"), str) and entry["server_config"],
            f"{path}: missing {version} server config path",
        )
        urls.append(entry["url"])
    require(len(set(urls)) == 3, f"{path}: each version must use a distinct MCP URL")

    dataset = config.get("dataset", {})
    relative_task_path = dataset.get("path")
    require(isinstance(relative_task_path, str) and relative_task_path, f"{path}: missing dataset path")
    expected_size = dataset.get("size")
    require(isinstance(expected_size, int) and expected_size > 0, f"{path}: invalid dataset size")
    task_ids = validate_tasks(root / relative_task_path, expected_size, str(dataset.get("sha256", "")))

    if relative_task_path.endswith("pilot-30/test_cases.json"):
        validate_manifest(root / "data/subsets/pilot-30/manifest.json", task_ids)
        matrix = validate_linked_report(root, dataset, "runnability_matrix")
        require(matrix.get("task_count") == len(task_ids), "runnability matrix task count mismatch")
        require(matrix.get("all_tasks_runnable_in_all_versions") is True, "not all tasks are runnable")
        matrix_ids = [task.get("idx") for task in matrix.get("tasks", [])]
        require(matrix_ids == task_ids, "runnability matrix task IDs mismatch")
        stability = validate_linked_report(root, dataset, "startup_stability_report")
        require(stability.get("all_versions_stable") is True, "startup stability report failed")
        require(int(stability.get("trial_count", 0)) >= 2, "fewer than two startup trials")
        require(set(stability.get("versions", {})) == VERSION_SET, "stability report versions mismatch")

    return {"config": str(path.relative_to(root)), "task_file": relative_task_path, "tasks": len(task_ids)}


def validate_tool_schema_reports(root: Path, benchmark_commit: str) -> dict[str, int]:
    directory = root / "reports/tool-schemas"
    counts: dict[str, int] = {}
    for version in sorted(VERSIONS):
        path = directory / f"{version}.json"
        report = read_json(path)
        require(report.get("benchmark_commit") == benchmark_commit, f"{path}: benchmark commit mismatch")
        require(report.get("version") == version, f"{path}: version mismatch")
        servers = report.get("servers")
        require(isinstance(servers, list), f"{path}: servers must be a list")
        require(report.get("server_count") == len(servers), f"{path}: server count mismatch")
        names = [server.get("name") for server in servers]
        require(len(names) == len(set(names)), f"{path}: duplicate server name")
        connected = [server for server in servers if server.get("status") == "connected"]
        require(
            report.get("connected_server_count") == len(connected),
            f"{path}: connected server count mismatch",
        )
        tool_count = 0
        for server in servers:
            tools = server.get("tools")
            require(isinstance(tools, list), f"{path}: tools must be a list")
            require(
                server.get("status") == "connected" or tools == [],
                f"{path}: unavailable server contains tools",
            )
            for tool in tools:
                require(isinstance(tool.get("name"), str), f"{path}: invalid tool name")
                require(isinstance(tool.get("description"), str), f"{path}: invalid description")
                require(isinstance(tool.get("inputSchema"), dict), f"{path}: invalid inputSchema")
            tool_count += len(tools)
        require(report.get("tool_count") == tool_count, f"{path}: tool count mismatch")
        counts[version] = tool_count
    diff = read_json(directory / "diff.json")
    require(diff.get("benchmark_commit") == benchmark_commit, "tool schema diff commit mismatch")
    require(len(diff.get("comparisons", [])) == 3, "tool schema diff must contain three comparisons")
    return counts


def validate_repository(root: Path) -> dict[str, Any]:
    config_paths = [
        path
        for path in sorted((root / "configs").glob("*.json"))
        if isinstance(read_json(path), dict) and "experiment_name" in read_json(path)
    ]
    require(bool(config_paths), "no JSON configs found")
    configs = [validate_experiment_config(root, path) for path in config_paths]
    experiment = read_json(root / "configs/experiment.json")
    tool_schema_counts = validate_tool_schema_reports(
        root, experiment["benchmark"]["commit"]
    )
    return {
        "schema_version": 1,
        "passed": True,
        "mode": "lightweight_static_only",
        "server_bundles_used": False,
        "configs_checked": len(configs),
        "configs": configs,
        "tool_schema_counts": tool_schema_counts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        report = validate_repository(args.root.resolve())
    except ValidationError as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from exc
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
