#!/usr/bin/env python3
"""Check that all benchmark versions resolve from one shared configuration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment_config import ConfigError, VERSIONS, load_experiment, public_summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/experiment.json"))
    args = parser.parse_args()
    try:
        resolved = [load_experiment(args.config, version) for version in VERSIONS]
        shared_fields = (
            "benchmark_commit",
            "task_sha256",
            "task_count",
            "model_name",
            "temperature",
            "max_completion_tokens",
            "judge_name",
            "judge_temperature",
        )
        for field in shared_fields:
            if len({item[field] for item in resolved}) != 1:
                raise ConfigError(f"{field} differs between versions")
        output_dirs = {str(item["output_dir"]) for item in resolved}
        if len(output_dirs) != len(VERSIONS):
            raise ConfigError("each version must have a separate output directory")
        if len({item["mcp_url"] for item in resolved}) != len(VERSIONS):
            raise ConfigError("each version must have a separate MCP URL")
        if len({str(item["server_config"]) for item in resolved}) != len(VERSIONS):
            raise ConfigError("each version must have a separate 1MCP config")
    except ConfigError as exc:
        raise SystemExit(f"CONFIG ERROR: {exc}") from exc
    print(
        json.dumps(
            {
                "ok": True,
                "shared_fields": list(shared_fields),
                "versions": {
                    item["version"]: public_summary(item) for item in resolved
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
