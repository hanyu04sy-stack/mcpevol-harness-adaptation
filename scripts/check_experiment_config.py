#!/usr/bin/env python3
"""Check that all benchmark versions resolve from one shared configuration."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from experiment_config import (
    ConfigError,
    VERSIONS,
    load_env_file,
    load_experiment,
    public_summary,
    resolve_runtime_credentials,
    validate_endpoint_model_consistency,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/experiment.json"))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--endpoint-only",
        action="store_true",
        help="check only endpoint/model consistency without requiring benchmark assets",
    )
    args = parser.parse_args()
    try:
        if args.endpoint_only:
            config_path = args.config.resolve()
            raw = json.loads(config_path.read_text(encoding="utf-8"))
            model = raw["model"]
            configured_env = raw.get("environment", {}).get("file", ".env")
            env_file = (args.env_file or Path(configured_env)).resolve()
            load_env_file(env_file)
            base_url = os.environ.get(str(model["base_url_env"]), "").strip()
            validate_endpoint_model_consistency(str(model["name"]), base_url)
            print(
                json.dumps(
                    {
                        "ok": True,
                        "model_name": model["name"],
                        "effective_endpoint": base_url or None,
                    },
                    indent=2,
                )
            )
            return
        resolved = [load_experiment(args.config, version) for version in VERSIONS]
        env_file = (args.env_file or Path(resolved[0]["env_file"])).resolve()
        load_env_file(env_file)
        for item in resolved:
            resolve_runtime_credentials(item)
            item["effective_endpoint"] = item["model_base_url_resolved"]
        validate_endpoint_model_consistency(
            str(resolved[0]["model_name"]),
            str(resolved[0]["model_base_url_resolved"]),
        )
        shared_fields = (
            "benchmark_commit",
            "task_sha256",
            "task_count",
            "runnability_matrix_sha256",
            "startup_stability_report_sha256",
            "model_provider",
            "model_name",
            "temperature",
            "max_completion_tokens",
            "openai_timeout_seconds",
            "openai_max_retries",
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
        task_file = Path(resolved[0]["task_file"])
        manifest_path = task_file.with_name("manifest.json")
        if manifest_path.is_file():
            if resolved[0]["runnability_matrix"] is None:
                raise ConfigError("formal subset requires a runnability matrix")
            if resolved[0]["startup_stability_report"] is None:
                raise ConfigError("formal subset requires repeated startup evidence")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            tasks = json.loads(task_file.read_text(encoding="utf-8"))
            task_ids = [int(task["idx"]) for task in tasks]
            if manifest.get("selected_indices") != task_ids:
                raise ConfigError("task file does not match its subset manifest")
            if manifest.get("eligibility_basis") != "connected_in_all_versions":
                raise ConfigError(
                    "formal subset must be selected from servers connected in all versions"
                )
            covered = set(manifest.get("change_type_task_counts", {}))
            if covered != {"tool", "parameter", "description"}:
                raise ConfigError("formal subset does not cover all three change types")
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
