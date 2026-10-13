#!/usr/bin/env python3
"""Load, validate, and resolve the shared benchmark experiment configuration."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any, MutableMapping
from urllib.parse import urlsplit


VERSIONS = ("early", "middle", "late")
THINKING_MODES = {"enabled", "disabled", "provider_default"}
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


def resolve_runtime_credentials(
    resolved: dict[str, Any],
    environ: MutableMapping[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve model credentials and safe same-model judge fallbacks."""
    source = os.environ if environ is None else environ
    model_key_name = str(resolved["model_api_key_env"])
    model_url_name = str(resolved["model_base_url_env"])
    judge_key_name = str(resolved["judge_api_key_env"])
    judge_url_name = str(resolved["judge_base_url_env"])
    model_key = source.get(model_key_name, "").strip()
    model_url = source.get(model_url_name, "").strip()
    judge_key = source.get(judge_key_name, "").strip()
    judge_url = source.get(judge_url_name, "").strip()
    same_model = resolved["model_name"] == resolved["judge_name"]
    if same_model and not judge_key:
        judge_key = model_key
        judge_key_source = f"{model_key_name} (fallback)"
    else:
        judge_key_source = judge_key_name
    if same_model and not judge_url:
        judge_url = model_url
        judge_url_source = f"{model_url_name} (fallback)"
    else:
        judge_url_source = judge_url_name
    resolved.update(
        {
            "model_api_key_resolved": model_key,
            "model_base_url_resolved": model_url,
            "judge_api_key_resolved": judge_key,
            "judge_base_url_resolved": judge_url,
            "judge_api_key_source": judge_key_source,
            "judge_base_url_source": judge_url_source,
        }
    )
    if same_model and model_url and judge_url and model_url.rstrip("/") != judge_url.rstrip("/"):
        raise ConfigError(
            "model and judge must use the same base URL when their model names match"
        )
    return resolved


def validate_endpoint_model_consistency(model_name: str, base_url: str) -> None:
    """Reject provider endpoints paired with an obviously incompatible model slug."""
    if not base_url:
        return
    hostname = (urlsplit(base_url).hostname or "").lower()
    is_deepseek_model = model_name.lower().startswith("deepseek")
    if hostname == "deepseek.com" or hostname.endswith(".deepseek.com"):
        if not is_deepseek_model:
            raise ConfigError(
                f"MODEL_BASE_URL points to DeepSeek ({base_url}), but model.name is "
                f"still {model_name!r}. Update model.name in configs/experiment.json "
                "to 'deepseek-flash'."
            )
    if hostname in {"openai.com", "openrouter.ai"} or hostname.endswith(
        (".openai.com", ".openrouter.ai")
    ):
        if is_deepseek_model:
            raise ConfigError(
                f"MODEL_BASE_URL points to {hostname} ({base_url}), but model.name is "
                f"{model_name!r}. Use a model slug served by that endpoint, or set "
                "MODEL_BASE_URL to https://api.deepseek.com."
            )


def thinking_request_kwargs(thinking_mode: str) -> dict[str, object]:
    """Build the OpenAI-compatible request extension for an explicit mode."""
    if thinking_mode == "provider_default":
        return {}
    if thinking_mode not in THINKING_MODES:
        raise ConfigError(f"unsupported thinking_mode: {thinking_mode!r}")
    return {"extra_body": {"thinking": {"type": thinking_mode}}}


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
    harness = _require(raw, "harness", dict, "config")
    model = _require(raw, "model", dict, "config")
    judge = _require(raw, "judge", dict, "config")
    openai_client = raw.get("openai_client", {})
    if not isinstance(openai_client, dict):
        raise ConfigError("config.openai_client must be dict")
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

    harness_dir = _path(
        project_root,
        _require(harness, "default_dir", str, "harness"),
        "harness.default_dir",
    )
    if not harness_dir.is_dir():
        raise ConfigError(f"harness.default_dir is not a directory: {harness_dir}")

    matrix_path: Path | None = None
    matrix_hash: str | None = None
    matrix_raw = dataset.get("runnability_matrix")
    expected_matrix_hash = dataset.get("runnability_matrix_sha256")
    if (matrix_raw is None) != (expected_matrix_hash is None):
        raise ConfigError(
            "dataset.runnability_matrix and runnability_matrix_sha256 must be set together"
        )
    if matrix_raw is not None:
        if not isinstance(matrix_raw, str) or not isinstance(expected_matrix_hash, str):
            raise ConfigError("runnability matrix path and SHA-256 must be strings")
        matrix_path = _path(
            project_root, matrix_raw, "dataset.runnability_matrix"
        )
        matrix_hash = sha256(matrix_path)
        if matrix_hash != expected_matrix_hash:
            raise ConfigError(
                "runnability matrix SHA-256 mismatch: "
                f"expected {expected_matrix_hash}, got {matrix_hash}"
            )
        try:
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"invalid runnability matrix: {exc}") from exc
        if matrix.get("task_file_sha256") != actual_hash:
            raise ConfigError("runnability matrix was built for a different task file")
        if matrix.get("benchmark_commit") != expected_commit:
            raise ConfigError("runnability matrix benchmark commit does not match")
        rows = matrix.get("tasks")
        if not isinstance(rows, list) or len(rows) != len(tasks):
            raise ConfigError("runnability matrix must contain one row per task")
        task_ids = [int(task["idx"]) for task in tasks]
        if [int(row.get("idx", -1)) for row in rows] != task_ids:
            raise ConfigError("runnability matrix task IDs do not match the dataset")
        if matrix.get("all_tasks_runnable_in_all_versions") is not True:
            raise ConfigError("runnability matrix contains unavailable task dependencies")
        for row in rows:
            version_result = row.get("versions", {}).get(version, {})
            if (
                version_result.get("runnable") is not True
                or version_result.get("unavailable_servers") != []
            ):
                raise ConfigError(
                    f"task {row.get('idx')} has unavailable dependencies in {version}"
                )

    stability_path: Path | None = None
    stability_hash: str | None = None
    stability: dict[str, Any] | None = None
    stability_raw = dataset.get("startup_stability_report")
    expected_stability_hash = dataset.get("startup_stability_report_sha256")
    if (stability_raw is None) != (expected_stability_hash is None):
        raise ConfigError(
            "dataset.startup_stability_report and its SHA-256 must be set together"
        )
    if stability_raw is not None:
        if not isinstance(stability_raw, str) or not isinstance(
            expected_stability_hash, str
        ):
            raise ConfigError("startup stability report path and SHA-256 must be strings")
        stability_path = _path(
            project_root, stability_raw, "dataset.startup_stability_report"
        )
        stability_hash = sha256(stability_path)
        if stability_hash != expected_stability_hash:
            raise ConfigError(
                "startup stability report SHA-256 mismatch: "
                f"expected {expected_stability_hash}, got {stability_hash}"
            )
        try:
            stability = json.loads(stability_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"invalid startup stability report: {exc}") from exc
        if stability.get("benchmark_commit") != expected_commit:
            raise ConfigError("startup stability benchmark commit does not match")
        if stability.get("trial_count", 0) < 3:
            raise ConfigError("startup stability report requires at least three trials")
        if stability.get("all_versions_stable") is not True:
            raise ConfigError("startup stability report contains intermittent failures")
        version_stability = stability.get("versions", {}).get(version, {}).get(
            "summary", {}
        )
        if (
            version_stability.get("trial_count", 0) < 3
            or version_stability.get("all_trials_successful") is not True
            or version_stability.get("flaky_or_unavailable_servers") != []
        ):
            raise ConfigError(f"{version} did not pass repeated startup validation")

    model_provider = _require(model, "provider", str, "model")
    if model_provider not in {"openai_compatible", "local_ollama"}:
        raise ConfigError("model.provider is unsupported")
    model_name = _require(model, "name", str, "model")
    thinking_mode = _require(model, "thinking_mode", str, "model")
    if thinking_mode not in THINKING_MODES:
        raise ConfigError("model.thinking_mode is unsupported")
    temperature = model.get("temperature")
    if not isinstance(temperature, (int, float)) or not 0 <= temperature <= 2:
        raise ConfigError("model.temperature must be between 0 and 2")
    max_tokens = _require(model, "max_completion_tokens", int, "model")
    if max_tokens <= 0:
        raise ConfigError("model.max_completion_tokens must be positive")
    if _require(judge, "name", str, "judge") != model_name:
        raise ConfigError("model.name and judge.name must match for this experiment")
    judge_thinking_mode = _require(judge, "thinking_mode", str, "judge")
    if judge_thinking_mode != thinking_mode:
        raise ConfigError("model.thinking_mode and judge.thinking_mode must match")
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
    timeout_seconds = openai_client.get("timeout_seconds", 120)
    max_retries = openai_client.get("max_retries", 3)
    if (
        not isinstance(timeout_seconds, (int, float))
        or isinstance(timeout_seconds, bool)
        or timeout_seconds <= 0
    ):
        raise ConfigError("openai_client.timeout_seconds must be positive")
    if not isinstance(max_retries, int) or isinstance(max_retries, bool) or max_retries < 0:
        raise ConfigError("openai_client.max_retries must be a non-negative integer")

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
    if stability is not None:
        stability_trials = stability["versions"][version].get("trials", [])
        if not stability_trials:
            raise ConfigError(f"startup stability report has no {version} trials")
        for trial in stability_trials:
            observed = {server["name"] for server in trial.get("servers", [])}
            if observed != set(configured_servers):
                raise ConfigError(
                    f"startup stability {version} trial server set does not match config"
                )
        if version_stability.get("configured_server_count") != len(
            configured_servers
        ):
            raise ConfigError(
                f"startup stability {version} server count does not match config"
            )

    runner_step = runner.get("step")
    if not isinstance(runner_step, int) or runner_step < 1:
        raise ConfigError("runner.step must be a positive integer")
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

    resolved = {
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
        "harness_dir": harness_dir,
        "runnability_matrix": matrix_path,
        "runnability_matrix_sha256": matrix_hash,
        "startup_stability_report": stability_path,
        "startup_stability_report_sha256": stability_hash,
        "model_name": model_name,
        "model_provider": model_provider,
        "thinking_mode": thinking_mode,
        "temperature": float(temperature),
        "max_completion_tokens": max_tokens,
        "model_api_key_env": _require(model, "api_key_env", str, "model"),
        "model_base_url_env": _require(model, "base_url_env", str, "model"),
        "judge_name": judge["name"],
        "judge_thinking_mode": judge_thinking_mode,
        "judge_temperature": float(judge_temperature),
        "judge_api_key_env": _require(judge, "api_key_env", str, "judge"),
        "judge_base_url_env": _require(judge, "base_url_env", str, "judge"),
        "openai_timeout_seconds": float(timeout_seconds),
        "openai_max_retries": max_retries,
        "runner_step": runner_step,
        "runner_part_num": runner["part_num"],
        "runner_part_idx": runner["part_idx"],
        "runner_fschat": runner["fschat"],
        "mcp_url": mcp_url,
        "server_config": server_config,
        "configured_server_count": len(configured_servers),
        "output_dir": output_dir.resolve(),
        "output_root": output_root.resolve(),
        "env_file": env_file,
    }
    return resolve_runtime_credentials(resolved)


def public_summary(resolved: dict[str, Any]) -> dict[str, Any]:
    """Return serializable, non-secret settings for logs and dry runs."""
    keys = (
        "experiment_name",
        "version",
        "config_sha256",
        "benchmark_commit",
        "task_sha256",
        "task_count",
        "harness_dir",
        "runnability_matrix_sha256",
        "startup_stability_report_sha256",
        "model_name",
        "model_provider",
        "thinking_mode",
        "temperature",
        "max_completion_tokens",
        "judge_name",
        "judge_thinking_mode",
        "judge_temperature",
        "judge_api_key_env",
        "judge_base_url_env",
        "openai_timeout_seconds",
        "openai_max_retries",
        "runner_step",
        "mcp_url",
        "configured_server_count",
        "effective_endpoint",
    )
    result = {key: resolved[key] for key in keys if key in resolved}
    for key in ("strategy", "run_id"):
        if key in resolved:
            result[key] = resolved[key]
    for key in ("harness_manifest_sha256", "harness_files"):
        if key in resolved:
            result[key] = resolved[key]
    for key in (
        "config_path",
        "task_file",
        "harness_dir",
        "runnability_matrix",
        "startup_stability_report",
        "server_config",
        "output_dir",
        "output_root",
    ):
        result[key] = str(resolved[key]) if resolved[key] is not None else None
    return result


def pricing_warning(
    pricing_path: Path, model_name: str, *, today: date | None = None
) -> str | None:
    """Return a pre-run warning when configured prices are stale or historical."""
    try:
        payload = json.loads(pricing_path.read_text(encoding="utf-8"))
        reviewed = date.fromisoformat(str(payload["last_reviewed_at"]))
        stale_after = int(payload["stale_after_days"])
        model = payload["models"][model_name]
        age = ((today or date.today()) - reviewed).days
        status = str(model["pricing_status"])
        if status != "current" or age > stale_after:
            return (
                f"Pricing for {model_name} is {status.replace('_', ' ')} and was "
                f"reviewed {reviewed.isoformat()} ({age} days ago). Confirm current "
                f"rates at {model['source_url']} before paid runs."
            )
        return None
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return (
            f"Pricing metadata for {model_name} is incomplete; verify it before "
            "paid runs."
        )
