#!/usr/bin/env python3
"""Load, validate, and resolve the shared benchmark experiment configuration."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, MutableMapping
from urllib.parse import urlsplit


VERSIONS = ("early", "middle", "late")
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigError(ValueError):
    """Raised when the experiment configuration is unsafe or inconsistent."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse dotenv assignments without shell execution or variable expansion."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ConfigError(f"{path}:{line_number}: expected NAME=value")
        name, value = line.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not ENV_NAME.fullmatch(name):
            raise ConfigError(f"{path}:{line_number}: invalid variable name")
        if value[:1] in {"'", '"'}:
            quote = value[0]
            if len(value) < 2 or value[-1] != quote:
                raise ConfigError(f"{path}:{line_number}: unmatched quote")
            value = value[1:-1]
        values[name] = value
    return values


def load_env_file(
    path: Path, environ: MutableMapping[str, str] | None = None
) -> list[str]:
    """Load missing variables only; return names, never secret values."""
    target = os.environ if environ is None else environ
    loaded = []
    for name, value in parse_env_file(path).items():
        if name not in target:
            target[name] = value
            loaded.append(name)
    return loaded


def _require(mapping: dict[str, Any], key: str, kind: type, where: str) -> Any:
    value = mapping.get(key)
    if not isinstance(value, kind):
        raise ConfigError(f"{where}.{key} must be {kind.__name__}")
    return value


def _path(root: Path, raw: str, where: str, must_exist: bool = True) -> Path:
    path = (root / raw).resolve()
    if must_exist and not path.exists():
        raise ConfigError(f"{where} does not exist: {path}")
    return path


def load_experiment(
    config_path: Path,
    version: str,
    *,
    root: Path | None = None,
    verify_checkout: bool = True,
) -> dict[str, Any]:
    """Validate shared settings and resolve one version into absolute paths."""
    if version not in VERSIONS:
        raise ConfigError(f"version must be one of: {', '.join(VERSIONS)}")
    project_root = (root or Path(__file__).resolve().parents[1]).resolve()
    config_path = config_path if config_path.is_absolute() else project_root / config_path
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read config {config_path}: {exc}") from exc
    if raw.get("schema_version") != 1:
        raise ConfigError("schema_version must be 1")

    experiment_name = _require(raw, "experiment_name", str, "config")
    benchmark = _require(raw, "benchmark", dict, "config")
    dataset = _require(raw, "dataset", dict, "config")
    model = _require(raw, "model", dict, "config")
    judge = _require(raw, "judge", dict, "config")
    runner = _require(raw, "runner", dict, "config")
    mcp = _require(raw, "mcp", dict, "config")
    output = _require(raw, "output", dict, "config")
    environment = _require(raw, "environment", dict, "config")

    benchmark_root = _path(
        project_root, _require(benchmark, "root", str, "benchmark"), "benchmark.root"
    )
    benchmark_runner = _path(
        benchmark_root,
        _require(benchmark, "runner", str, "benchmark"),
        "benchmark.runner",
    )
    expected_commit = _require(benchmark, "commit", str, "benchmark")
    if verify_checkout:
        try:
            actual_commit = subprocess.run(
                ["git", "-C", str(benchmark_root), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            raise ConfigError(f"cannot verify benchmark checkout: {exc}") from exc
        if actual_commit != expected_commit:
            raise ConfigError(
                f"benchmark commit mismatch: expected {expected_commit}, got {actual_commit}"
            )

    task_file = _path(
        project_root, _require(dataset, "path", str, "dataset"), "dataset.path"
    )
    expected_hash = _require(dataset, "sha256", str, "dataset")
    actual_hash = sha256(task_file)
    if actual_hash != expected_hash:
        raise ConfigError(
            f"dataset SHA-256 mismatch: expected {expected_hash}, got {actual_hash}"
        )
    tasks = json.loads(task_file.read_text(encoding="utf-8"))
    expected_size = _require(dataset, "size", int, "dataset")
    if not isinstance(tasks, list) or len(tasks) != expected_size:
        raise ConfigError(f"dataset must contain exactly {expected_size} tasks")

    model_name = _require(model, "name", str, "model")
    temperature = model.get("temperature")
    if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2:
        raise ConfigError("model.temperature must be between 0 and 2")
    max_tokens = _require(model, "max_completion_tokens", int, "model")
    if max_tokens <= 0:
        raise ConfigError("model.max_completion_tokens must be positive")
    if _require(judge, "name", str, "judge") != model_name:
        raise ConfigError("model.name and judge.name must match for this experiment")
    judge_temperature = judge.get("temperature")
    if judge_temperature != temperature:
        raise ConfigError("model.temperature and judge.temperature must match")
    for where, name in (
        ("model.api_key_env", _require(model, "api_key_env", str, "model")),
        ("model.base_url_env", _require(model, "base_url_env", str, "model")),
        ("judge.api_key_env", _require(judge, "api_key_env", str, "judge")),
        ("judge.base_url_env", _require(judge, "base_url_env", str, "judge")),
    ):
        if not ENV_NAME.fullmatch(name):
            raise ConfigError(f"{where} is not a valid environment variable name")

    versions = _require(mcp, "versions", dict, "mcp")
    if set(versions) != set(VERSIONS):
        raise ConfigError("mcp.versions must define exactly early, middle, and late")
    version_config = _require(versions, version, dict, f"mcp.versions.{version}")
    mcp_url = _require(version_config, "url", str, f"mcp.versions.{version}")
    parsed_url = urlsplit(mcp_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname:
        raise ConfigError(f"invalid MCP URL: {mcp_url}")
    if parsed_url.path != "/mcp":
        raise ConfigError(f"MCP URL must end in /mcp: {mcp_url}")
    server_config = _path(
        project_root,
        _require(version_config, "server_config", str, f"mcp.versions.{version}"),
        f"mcp.versions.{version}.server_config",
    )
    configured_servers = json.loads(server_config.read_text(encoding="utf-8")).get(
        "mcpServers"
    )
    if not isinstance(configured_servers, dict) or not configured_servers:
        raise ConfigError(f"invalid 1MCP server config: {server_config}")
    required_servers = {
        server for task in tasks for server in task.get("servers", {})
    }
    missing_servers = sorted(required_servers - set(configured_servers))
    if missing_servers:
        raise ConfigError(
            f"{version} server config is missing task servers: {missing_servers}"
        )

    if runner.get("step") != 3:
        raise ConfigError("runner.step must be 3 for benchmark execution")
    if runner.get("part_num") != -1 or runner.get("part_idx") != 0:
        raise ConfigError("pilot configuration must run the complete fixed subset")
    if runner.get("fschat") is not False:
        raise ConfigError("runner.fschat must be false for the shared API configuration")

    output_root = _path(
        project_root,
        _require(output, "root", str, "output"),
        "output.root",
        must_exist=False,
    )
    layout = _require(output, "layout", str, "output")
    try:
        output_dir = output_root / layout.format(
            experiment_name=experiment_name, version=version
        )
    except (KeyError, ValueError) as exc:
        raise ConfigError(f"invalid output.layout: {exc}") from exc
    output_dir = output_dir.resolve()
    if output_dir != output_root and output_root not in output_dir.parents:
        raise ConfigError("output.layout escapes output.root")
    env_file = _path(
        project_root,
        _require(environment, "file", str, "environment"),
        "environment.file",
        must_exist=False,
    )

    return {
        "project_root": project_root,
        "config_path": config_path.resolve(),
        "config_sha256": sha256(config_path),
        "experiment_name": experiment_name,
        "version": version,
        "benchmark_root": benchmark_root,
        "benchmark_runner": benchmark_runner,
        "benchmark_commit": expected_commit,
        "task_file": task_file,
        "task_sha256": actual_hash,
        "task_count": len(tasks),
        "model_name": model_name,
        "temperature": float(temperature),
        "max_completion_tokens": max_tokens,
        "model_api_key_env": _require(model, "api_key_env", str, "model"),
        "model_base_url_env": _require(model, "base_url_env", str, "model"),
        "judge_name": judge["name"],
        "judge_temperature": float(judge_temperature),
        "mcp_url": mcp_url,
        "server_config": server_config,
        "configured_server_count": len(configured_servers),
        "output_dir": output_dir.resolve(),
        "env_file": env_file,
    }


def public_summary(resolved: dict[str, Any]) -> dict[str, Any]:
    """Return serializable, non-secret settings for logs and dry runs."""
    keys = (
        "experiment_name",
        "version",
        "config_sha256",
        "benchmark_commit",
        "task_sha256",
        "task_count",
        "model_name",
        "temperature",
        "max_completion_tokens",
        "judge_name",
        "judge_temperature",
        "mcp_url",
        "configured_server_count",
    )
    result = {key: resolved[key] for key in keys}
    for key in ("config_path", "task_file", "server_config", "output_dir"):
        result[key] = str(resolved[key])
    return result
