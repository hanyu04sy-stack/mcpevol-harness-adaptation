#!/usr/bin/env python3
"""Build auditable per-server tool changes from three MCP schema snapshots."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment_config import VERSIONS

ROOT = Path(__file__).resolve().parents[1]
COMPARISONS = (("early", "middle"), ("middle", "late"), ("early", "late"))
DESCRIPTION_PREFIX_LENGTH = 40


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def description_prefix(description: str, length: int = DESCRIPTION_PREFIX_LENGTH) -> str:
    return re.sub(r"\s+", " ", description).strip().casefold()[:length]


def server_index(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {server["name"]: server for server in report["servers"]}


def tool_index(server: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {tool["name"]: tool for tool in server["tools"]}


def tool_record(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": tool["name"],
        "description": tool.get("description", ""),
        "inputSchema": tool.get("inputSchema", {}),
    }


def match_tool_renames(
    removed: list[dict[str, Any]], added: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Match different names with identical schemas and description prefixes."""
    matches: list[dict[str, Any]] = []
    used_added: set[str] = set()
    for before in sorted(removed, key=lambda item: item["name"]):
        candidates = [
            after
            for after in added
            if after["name"] not in used_added
            and canonical(before.get("inputSchema", {}))
            == canonical(after.get("inputSchema", {}))
            and description_prefix(before.get("description", ""))
            == description_prefix(after.get("description", ""))
        ]
        if len(candidates) == 1:
            after = candidates[0]
            used_added.add(after["name"])
            matches.append(
                {
                    "before": tool_record(before),
                    "after": tool_record(after),
                    "evidence": {
                        "same_input_schema": True,
                        "description_prefix_length": DESCRIPTION_PREFIX_LENGTH,
                        "description_prefix": description_prefix(
                            before.get("description", "")
                        ),
                    },
                }
            )
    return matches


def parameter_record(name: str, schema: Any, required: bool) -> dict[str, Any]:
    return {"name": name, "schema": schema, "required": required}


def parameter_changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_properties = before.get("properties", {})
    after_properties = after.get("properties", {})
    if not isinstance(before_properties, dict):
        before_properties = {}
    if not isinstance(after_properties, dict):
        after_properties = {}
    before_required = set(before.get("required", []))
    after_required = set(after.get("required", []))
    removed_names = set(before_properties) - set(after_properties)
    added_names = set(after_properties) - set(before_properties)

    renamed: list[dict[str, Any]] = []
    consumed_added: set[str] = set()
    consumed_removed: set[str] = set()
    for old_name in sorted(removed_names):
        candidates = [
            new_name
            for new_name in sorted(added_names)
            if new_name not in consumed_added
            and canonical(before_properties[old_name])
            == canonical(after_properties[new_name])
            and (old_name in before_required) == (new_name in after_required)
        ]
        if len(candidates) == 1:
            new_name = candidates[0]
            consumed_removed.add(old_name)
            consumed_added.add(new_name)
            renamed.append(
                {
                    "before": parameter_record(
                        old_name, before_properties[old_name], old_name in before_required
                    ),
                    "after": parameter_record(
                        new_name, after_properties[new_name], new_name in after_required
                    ),
                }
            )

    common = set(before_properties) & set(after_properties)
    modified = [
        {
            "name": name,
            "before": before_properties[name],
            "after": after_properties[name],
            "required_before": name in before_required,
            "required_after": name in after_required,
        }
        for name in sorted(common)
        if canonical(before_properties[name]) != canonical(after_properties[name])
        or (name in before_required) != (name in after_required)
    ]
    return {
        "added": [
            parameter_record(name, after_properties[name], name in after_required)
            for name in sorted(added_names - consumed_added)
        ],
        "removed": [
            parameter_record(name, before_properties[name], name in before_required)
            for name in sorted(removed_names - consumed_removed)
        ],
        "renamed": renamed,
        "modified": modified,
    }


def diff_server(name: str, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    old_tools = tool_index(before)
    new_tools = tool_index(after)
    old_names = set(old_tools)
    new_names = set(new_tools)
    removed = [old_tools[item] for item in sorted(old_names - new_names)]
    added = [new_tools[item] for item in sorted(new_names - old_names)]
    renamed = match_tool_renames(removed, added)

    descriptions = []
    parameters = []
    for tool_name in sorted(old_names & new_names):
        old_tool = old_tools[tool_name]
        new_tool = new_tools[tool_name]
        old_description = old_tool.get("description", "")
        new_description = new_tool.get("description", "")
        if old_description != new_description:
            descriptions.append(
                {"name": tool_name, "before": old_description, "after": new_description}
            )
        old_schema = old_tool.get("inputSchema", {})
        new_schema = new_tool.get("inputSchema", {})
        if canonical(old_schema) != canonical(new_schema):
            parameters.append(
                {
                    "name": tool_name,
                    "before": old_schema,
                    "after": new_schema,
                    "parameters": parameter_changes(old_schema, new_schema),
                }
            )
    return {
        "server": name,
        "added_tools": [tool_record(tool) for tool in added],
        "removed_tools": [tool_record(tool) for tool in removed],
        "renamed_tools": renamed,
        "changed_descriptions": descriptions,
        "changed_parameters": parameters,
    }


def comparison(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    old_servers = server_index(before)
    new_servers = server_index(after)
    common = set(old_servers) & set(new_servers)
    comparable = sorted(
        name
        for name in common
        if old_servers[name].get("status") == "connected"
        and new_servers[name].get("status") == "connected"
    )
    unavailable_before = sorted(
        name
        for name in common
        if old_servers[name].get("status") != "connected"
        and new_servers[name].get("status") == "connected"
    )
    unavailable_after = sorted(
        name
        for name in common
        if old_servers[name].get("status") == "connected"
        and new_servers[name].get("status") != "connected"
    )
    categories = (
        "added_tools",
        "removed_tools",
        "renamed_tools",
        "changed_descriptions",
        "changed_parameters",
    )
    servers = []
    for name in comparable:
        result = diff_server(name, old_servers[name], new_servers[name])
        if any(result[key] for key in categories):
            servers.append(result)
    return {
        "from_version": before["version"],
        "to_version": after["version"],
        "compared_servers": comparable,
        "unavailable_in_from_version": unavailable_before,
        "unavailable_in_to_version": unavailable_after,
        "servers": servers,
        "summary": {
            **{f"{key}_count": sum(len(server[key]) for server in servers) for key in categories},
            "changed_server_count": len(servers),
            "compared_server_count": len(comparable),
        },
    }


def manifest_alignment(manifest: dict[str, Any], comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    affected = sorted(
        {
            server
            for task in manifest["selected_task_details"]
            for server in task.get("affected_servers", [])
        }
    )
    detected = sorted(
        {server["server"] for item in comparisons for server in item["servers"]}
    )
    unavailable = sorted(
        {
            server
            for item in comparisons
            for key in ("unavailable_in_from_version", "unavailable_in_to_version")
            for server in item[key]
        }
    )
    return {
        "manifest_affected_servers": affected,
        "detected_change_servers": sorted(set(affected) & set(detected)),
        "unavailable_schema_servers": sorted(set(affected) & set(unavailable)),
        "unmatched_manifest_servers": sorted(
            set(affected) - set(detected) - set(unavailable)
        ),
    }


def build_report(
    reports: dict[str, dict[str, Any]], source_paths: dict[str, Path], manifest: dict[str, Any]
) -> dict[str, Any]:
    commits = {report["benchmark_commit"] for report in reports.values()}
    if len(commits) != 1:
        raise ValueError("tool schema snapshots use different benchmark commits")
    results = [comparison(reports[old], reports[new]) for old, new in COMPARISONS]
    totals = {
        key: sum(item["summary"][f"{key}_count"] for item in results)
        for key in (
            "added_tools",
            "removed_tools",
            "renamed_tools",
            "changed_descriptions",
            "changed_parameters",
        )
    }
    return {
        "schema_version": 1,
        "benchmark_commit": next(iter(commits)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "description_prefix_length": DESCRIPTION_PREFIX_LENGTH,
        "source_files": [
            {"version": version, "path": str(path), "sha256": sha256(path)}
            for version, path in source_paths.items()
        ],
        "comparisons": results,
        "totals": totals,
        "manifest_alignment": manifest_alignment(manifest, results),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Tool Schema Changes",
        "",
        f"Benchmark commit: `{report['benchmark_commit']}`",
        "",
        "| Comparison | Servers compared | Added | Removed | Renamed | Description | Parameters |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["comparisons"]:
        summary = item["summary"]
        lines.append(
            f"| {item['from_version']} to {item['to_version']} | "
            f"{summary['compared_server_count']} | {summary['added_tools_count']} | "
            f"{summary['removed_tools_count']} | {summary['renamed_tools_count']} | "
            f"{summary['changed_descriptions_count']} | {summary['changed_parameters_count']} |"
        )
    for item in report["comparisons"]:
        lines.extend(["", f"## {item['from_version']} to {item['to_version']}", ""])
        if item["unavailable_in_to_version"]:
            lines.append(
                "Unavailable in the target snapshot: "
                + ", ".join(f"`{name}`" for name in item["unavailable_in_to_version"])
            )
            lines.append("")
        if not item["servers"]:
            lines.append("No changes were detected among comparable connected servers.")
            continue
        for server in item["servers"]:
            lines.extend([f"### `{server['server']}`", ""])
            rows = (
                ("Added tools", [tool["name"] for tool in server["added_tools"]]),
                ("Removed tools", [tool["name"] for tool in server["removed_tools"]]),
                (
                    "Renamed tools",
                    [
                        f"{change['before']['name']} to {change['after']['name']}"
                        for change in server["renamed_tools"]
                    ],
                ),
                (
                    "Changed descriptions",
                    [change["name"] for change in server["changed_descriptions"]],
                ),
                (
                    "Changed parameters",
                    [change["name"] for change in server["changed_parameters"]],
                ),
            )
            for label, values in rows:
                if values:
                    lines.append(f"- {label}: " + ", ".join(f"`{value}`" for value in values))
            lines.append("")
    alignment = report["manifest_alignment"]
    lines.extend(
        [
            "## Pilot manifest alignment",
            "",
            f"- Affected servers with detected changes: {len(alignment['detected_change_servers'])}",
            f"- Affected servers unavailable in at least one schema snapshot: {len(alignment['unavailable_schema_servers'])}",
            f"- Unmatched affected servers: {len(alignment['unmatched_manifest_servers'])}",
            "",
        ]
    )
    return "\n".join(lines)


def validate_nonempty(report: dict[str, Any]) -> None:
    required = (
        "added_tools",
        "removed_tools",
        "changed_descriptions",
        "changed_parameters",
    )
    missing = [key for key in required if report["totals"].get(key, 0) < 1]
    if missing:
        raise ValueError(f"tool change report has no records for: {missing}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema-dir", type=Path, default=Path("reports/tool-schemas"))
    parser.add_argument("--manifest", type=Path, default=Path("data/subsets/pilot-30/manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/tool-changes.json"))
    parser.add_argument("--markdown", type=Path, default=Path("reports/tool-changes.md"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source_paths = {version: args.schema_dir / f"{version}.json" for version in VERSIONS}
    reports = {version: read_json(path) for version, path in source_paths.items()}
    manifest = read_json(args.manifest)
    generated = build_report(reports, source_paths, manifest)
    validate_nonempty(generated)
    markdown = render_markdown(generated)
    if args.check:
        existing = read_json(args.output)
        validate_nonempty(existing)
        for key in (
            "benchmark_commit",
            "description_prefix_length",
            "source_files",
            "comparisons",
            "totals",
            "manifest_alignment",
        ):
            if existing.get(key) != generated.get(key):
                raise SystemExit(f"tool change report is stale or inconsistent: {key}")
        if args.markdown.read_text(encoding="utf-8") != render_markdown(existing):
            raise SystemExit("tool change Markdown summary is stale")
        print("Tool change reports are complete and current.")
        return
    args.output.write_text(
        json.dumps(generated, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )
    args.markdown.write_text(markdown, encoding="utf-8")
    print(f"Wrote {args.output} and {args.markdown}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
