#!/usr/bin/env python3
"""Render upstream 1mcp configs with machine-specific absolute paths."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

VERSION_DIR = {"early": "original", "middle": "iter3", "late": "iter5"}


def render_config(
    benchmark_root: Path,
    server_bundle_root: Path,
    version: str,
    output: Path,
    test_case_file: Path | None = None,
) -> None:
    source = benchmark_root / "servers/1mcp_config" / VERSION_DIR[version] / "mcp.json"
    text = source.read_text(encoding="utf-8")
    replacements = {
        "/path/to/workspace/": f"{benchmark_root.resolve()}/",
        "/path/to/iter3-servers": str((server_bundle_root / "iter3_servers").resolve()),
        "/path/to/iter5-servers": str((server_bundle_root / "iter5_servers").resolve()),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    if "/path/to/" in text:
        raise ValueError("Rendered config still contains /path/to/ placeholders")
    payload = json.loads(text)
    if test_case_file:
        tasks = json.loads(test_case_file.read_text(encoding="utf-8"))
        required_servers = {
            server for task in tasks for server in task.get("servers", {})
        }
        missing = sorted(required_servers - set(payload["mcpServers"]))
        if missing:
            raise ValueError(
                f"{version} config is missing required servers: {', '.join(missing)}"
            )
        payload["mcpServers"] = {
            name: config
            for name, config in payload["mcpServers"].items()
            if name in required_servers
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--server-bundle-root", type=Path, required=True)
    parser.add_argument("--version", choices=sorted(VERSION_DIR), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--test-case-file",
        type=Path,
        help="Optional task JSON; when supplied, keep only servers required by these tasks",
    )
    args = parser.parse_args()
    render_config(
        args.benchmark_root,
        args.server_bundle_root,
        args.version,
        args.output,
        args.test_case_file,
    )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
