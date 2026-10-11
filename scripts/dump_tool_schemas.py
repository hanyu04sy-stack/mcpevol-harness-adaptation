#!/usr/bin/env python3
"""Export per-server MCP tool schemas for Early, Middle, and Late."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from experiment_config import VERSIONS, load_experiment, sha256


ROOT = Path(__file__).resolve().parents[1]
TERMINAL_STATUSES = {"connected", "failed"}
SCHEMA_EXPORT_TIMEOUT_MS = 180_000


def with_export_timeouts(config: dict[str, Any]) -> dict[str, Any]:
    """Give slow servers enough time to initialize and answer tools/list."""
    copied = json.loads(json.dumps(config))
    for definition in copied["mcpServers"].values():
        definition.setdefault("connectionTimeout", SCHEMA_EXPORT_TIMEOUT_MS)
        definition.setdefault("requestTimeout", SCHEMA_EXPORT_TIMEOUT_MS)
    return copied


def inspect_servers(base_url: str) -> list[dict[str, Any]]:
    # 1MCP may spend up to 60 seconds querying one slow server for its count.
    # The client timeout must exceed that window or every retry is abandoned.
    with urllib.request.urlopen(f"{base_url}/api/v1/inspect", timeout=90) as response:
        return json.load(response)["servers"]


def wait_for_servers(
    process: subprocess.Popen[str], base_url: str, expected: int, timeout: int
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"1MCP exited early with code {process.returncode}")
        try:
            servers = inspect_servers(base_url)
        except (OSError, KeyError, json.JSONDecodeError):
            time.sleep(1)
            continue
        if len(servers) == expected and all(
            server.get("status") in TERMINAL_STATUSES for server in servers
        ):
            return servers
        time.sleep(1)
    raise TimeoutError(f"1MCP did not settle within {timeout} seconds")


def stop_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=10)


def start_one_mcp(
    one_mcp: Path,
    runtime_config: Path,
    port: int,
    env: dict[str, str],
    log: Any,
) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            str(one_mcp),
            "serve",
            "--config",
            str(runtime_config),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
            "--enable-async-loading",
            "--async-max-concurrent-loads",
            "2",
            "--async-max-retries",
            "1",
        ],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )


async def list_aggregated_tools(mcp_url: str) -> list[dict[str, Any]]:
    # Keep this dependency lazy so lightweight CI can test schema diff logic
    # without installing the full benchmark runtime.
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(mcp_url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await asyncio.wait_for(session.initialize(), timeout=30)
            response = await asyncio.wait_for(session.list_tools(), timeout=90)
    tools = []
    for tool in response.tools:
        item = tool.model_dump(by_alias=True, mode="json", exclude_none=True)
        tools.append(
            {
                "name": item["name"],
                "description": item.get("description", ""),
                "inputSchema": item.get("inputSchema", item.get("input_schema", {})),
            }
        )
    return tools


def split_aggregated_tools(
    tools: list[dict[str, Any]], server_names: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Remove the 1MCP server prefix and group tools by their source server."""
    grouped = {server: [] for server in server_names}
    prefixes = sorted(
        ((f"{server}_1mcp_", server) for server in server_names),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    unmatched = []
    for tool in tools:
        match = next(
            ((prefix, server) for prefix, server in prefixes if tool["name"].startswith(prefix)),
            None,
        )
        if match is None:
            unmatched.append(tool["name"])
            continue
        prefix, server = match
        grouped[server].append(
            {
                "name": tool["name"][len(prefix) :],
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
            }
        )
    if unmatched:
        raise RuntimeError(f"cannot map aggregated tools to servers: {unmatched}")
    for server_tools in grouped.values():
        server_tools.sort(key=lambda item: item["name"])
    return grouped


def build_report(
    version: str,
    resolved: dict[str, Any],
    observed: list[dict[str, Any]],
    aggregated_tools: list[dict[str, Any]],
) -> dict[str, Any]:
    server_names = sorted(server["server"] for server in observed)
    grouped = split_aggregated_tools(aggregated_tools, server_names)
    servers = []
    for server in sorted(observed, key=lambda item: item["server"]):
        name = server["server"]
        status = str(server.get("status", "unknown"))
        tools = grouped[name] if status == "connected" else []
        expected_count = int(server.get("toolCount", 0)) if status == "connected" else 0
        if len(tools) != expected_count:
            raise RuntimeError(
                f"{version}/{name}: inspect reports {expected_count} tools, "
                f"but tools/list returned {len(tools)}"
            )
        servers.append({"name": name, "status": status, "tools": tools})
    return {
        "schema_version": 1,
        "benchmark_commit": resolved["benchmark_commit"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "version": version,
        "mcp_url": resolved["mcp_url"],
        "server_config_sha256": sha256(Path(resolved["server_config"])),
        "server_count": len(servers),
        "connected_server_count": sum(item["status"] == "connected" for item in servers),
        "tool_count": sum(len(item["tools"]) for item in servers),
        "servers": servers,
    }


def export_isolated(
    version: str,
    resolved: dict[str, Any],
    one_mcp: Path,
    env: dict[str, str],
    log_dir: Path,
    port: int,
    timeout: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Export one source server at a time to avoid cross-server startup contention."""
    source = with_export_timeouts(
        json.loads(Path(resolved["server_config"]).read_text(encoding="utf-8"))
    )
    definitions = source["mcpServers"]
    observed_all: list[dict[str, Any]] = []
    tools_all: list[dict[str, Any]] = []
    isolated_dir = log_dir / "isolated" / version
    isolated_dir.mkdir(parents=True, exist_ok=True)
    base_url = f"http://127.0.0.1:{port}"
    for index, (server_name, definition) in enumerate(sorted(definitions.items())):
        runtime_config = isolated_dir / f"{index:02d}.json"
        runtime_config.write_text(
            json.dumps({"mcpServers": {server_name: definition}}, indent=2) + "\n",
            encoding="utf-8",
        )
        with (isolated_dir / f"{index:02d}.log").open("w", encoding="utf-8") as log:
            process = start_one_mcp(one_mcp, runtime_config, port, env, log)
            try:
                observed = wait_for_servers(process, base_url, 1, timeout)
                if observed[0].get("status") != "connected":
                    raise RuntimeError(
                        f"{version}/{server_name}: server did not connect: {observed[0]}"
                    )
                tools = asyncio.run(list_aggregated_tools(f"{base_url}/mcp"))
                observed[0]["toolCount"] = len(tools)
                observed_all.extend(observed)
                tools_all.extend(tools)
            finally:
                stop_process_group(process)
    return observed_all, tools_all


def tool_index(report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (server["name"], tool["name"]): tool
        for server in report["servers"]
        for tool in server["tools"]
    }


def diff_reports(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic tool/description/input-schema change inventory."""
    old_servers = {server["name"] for server in old["servers"]}
    new_servers = {server["name"] for server in new["servers"]}
    old_connected = {
        server["name"]
        for server in old["servers"]
        if server.get("status", "connected") == "connected"
    }
    new_connected = {
        server["name"]
        for server in new["servers"]
        if server.get("status", "connected") == "connected"
    }
    comparable_servers = old_connected & new_connected
    old_tools = tool_index(old)
    new_tools = tool_index(new)
    old_keys = {key for key in old_tools if key[0] in comparable_servers}
    new_keys = {key for key in new_tools if key[0] in comparable_servers}
    changed = []
    for server, name in sorted(old_keys & new_keys):
        before = old_tools[(server, name)]
        after = new_tools[(server, name)]
        description_changed = before.get("description", "") != after.get("description", "")
        input_schema_changed = before.get("inputSchema", {}) != after.get("inputSchema", {})
        if description_changed or input_schema_changed:
            changed.append(
                {
                    "server": server,
                    "tool": name,
                    "description_changed": description_changed,
                    "input_schema_changed": input_schema_changed,
                    "before": before,
                    "after": after,
                }
            )
    added = [{"server": server, "tool": tool} for server, tool in sorted(new_keys - old_keys)]
    removed = [{"server": server, "tool": tool} for server, tool in sorted(old_keys - new_keys)]
    return {
        "from_version": old["version"],
        "to_version": new["version"],
        "added_servers": sorted(new_servers - old_servers),
        "removed_servers": sorted(old_servers - new_servers),
        "compared_servers": sorted(comparable_servers),
        "unavailable_in_from_version": sorted(new_connected - old_connected),
        "unavailable_in_to_version": sorted(old_connected - new_connected),
        "added_tools": added,
        "removed_tools": removed,
        "changed_tools": changed,
        "summary": {
            "added_server_count": len(new_servers - old_servers),
            "removed_server_count": len(old_servers - new_servers),
            "added_tool_count": len(added),
            "removed_tool_count": len(removed),
            "changed_tool_count": len(changed),
            "description_change_count": sum(item["description_changed"] for item in changed),
            "input_schema_change_count": sum(item["input_schema_changed"] for item in changed),
            "compared_server_count": len(comparable_servers),
            "unavailable_in_from_version_count": len(new_connected - old_connected),
            "unavailable_in_to_version_count": len(old_connected - new_connected),
        },
    }


def write_diff(output_dir: Path, reports: dict[str, dict[str, Any]]) -> None:
    diff = {
        "schema_version": 1,
        "benchmark_commit": reports["early"]["benchmark_commit"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "comparisons": [
            diff_reports(reports["early"], reports["middle"]),
            diff_reports(reports["middle"], reports["late"]),
            diff_reports(reports["early"], reports["late"]),
        ],
    }
    (output_dir / "diff.json").write_text(
        json.dumps(diff, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/experiment.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("reports/tool-schemas"))
    parser.add_argument("--log-dir", type=Path, default=Path("logs/tool-schema-dump"))
    parser.add_argument("--versions", nargs="+", choices=VERSIONS, default=list(VERSIONS))
    parser.add_argument("--startup-timeout", type=int, default=300)
    parser.add_argument("--one-mcp-cli", type=Path)
    parser.add_argument(
        "--isolated",
        action="store_true",
        help="Start one source server at a time to avoid startup contention",
    )
    parser.add_argument(
        "--diff-only",
        action="store_true",
        help="Regenerate diff.json from existing per-version reports",
    )
    args = parser.parse_args()

    os.chdir(ROOT)
    one_mcp = (args.one_mcp_cli or ROOT / "node_modules/.bin/1mcp").resolve()
    if not one_mcp.is_file():
        raise SystemExit("1MCP is missing; run scripts/setup_environment.py first")
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join(
        [
            str(one_mcp.parent),
            str((ROOT / ".venv/bin").resolve()),
            str((ROOT / "node_modules/.bin").resolve()),
            env.get("PATH", ""),
        ]
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.log_dir.mkdir(parents=True, exist_ok=True)
    if args.diff_only:
        reports = {
            version: json.loads(
                (args.output_dir / f"{version}.json").read_text(encoding="utf-8")
            )
            for version in VERSIONS
        }
        write_diff(args.output_dir, reports)
        return
    reports: dict[str, dict[str, Any]] = {}

    for version in args.versions:
        resolved = load_experiment(args.config, version)
        parsed = urlsplit(str(resolved["mcp_url"]))
        if parsed.port is None:
            raise RuntimeError(f"MCP URL has no port: {resolved['mcp_url']}")
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        if args.isolated:
            observed, aggregated = export_isolated(
                version,
                resolved,
                one_mcp,
                env,
                args.log_dir,
                parsed.port,
                args.startup_timeout,
            )
        else:
            runtime_config = args.log_dir / "runtime" / version / "mcp.json"
            runtime_config.parent.mkdir(parents=True, exist_ok=True)
            runtime_config.write_text(
                json.dumps(
                    with_export_timeouts(
                        json.loads(
                            Path(resolved["server_config"]).read_text(encoding="utf-8")
                        )
                    ),
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            log_path = args.log_dir / f"{version}.log"
            with log_path.open("w", encoding="utf-8") as log:
                process = start_one_mcp(
                    one_mcp, runtime_config, parsed.port, env, log
                )
                try:
                    observed = wait_for_servers(
                        process,
                        base_url,
                        int(resolved["configured_server_count"]),
                        args.startup_timeout,
                    )
                    aggregated = asyncio.run(
                        list_aggregated_tools(str(resolved["mcp_url"]))
                    )
                finally:
                    stop_process_group(process)
        report = build_report(version, resolved, observed, aggregated)
        output = args.output_dir / f"{version}.json"
        output.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        reports[version] = report
        print(f"{version}: {report['connected_server_count']} servers, {report['tool_count']} tools")

    if set(VERSIONS) <= set(reports):
        write_diff(args.output_dir, reports)


if __name__ == "__main__":
    main()
