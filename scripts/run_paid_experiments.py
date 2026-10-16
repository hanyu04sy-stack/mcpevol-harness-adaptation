#!/usr/bin/env python3
"""Start versioned 1MCP services and run a resumable paid experiment matrix."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from experiment_config import VERSIONS, load_env_file, load_experiment


ROOT = Path(__file__).resolve().parents[1]
STRATEGIES = ("no_update", "full_rewrite", "selective_patch")


def inspect_servers(port: int) -> list[dict[str, object]]:
    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}/api/v1/inspect", timeout=10
    ) as response:
        return json.load(response)["servers"]


def wait_for_servers(
    process: subprocess.Popen[str], port: int, expected: int, timeout: int
) -> list[dict[str, object]]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"1MCP exited early with code {process.returncode}")
        try:
            servers = inspect_servers(port)
        except (OSError, KeyError, json.JSONDecodeError):
            time.sleep(2)
            continue
        if len(servers) == expected and all(
            server.get("status") in {"connected", "failed"} for server in servers
        ):
            return servers
        time.sleep(2)
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


def matrix_command(args: argparse.Namespace, phase: str, versions: list[str]) -> list[str]:
    return [
        sys.executable,
        "scripts/run_experiment_matrix.py",
        "--config",
        str(args.config),
        "--strategies",
        *args.strategies,
        "--versions",
        *versions,
        "--run-ids",
        *(str(run_id) for run_id in args.run_ids),
        "--judge-runs",
        str(args.judge_runs),
        "--phase",
        phase,
        "--execute",
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=Path("configs/comparison-subset/experiment.json")
    )
    parser.add_argument("--strategies", nargs="+", choices=STRATEGIES, default=STRATEGIES)
    parser.add_argument("--versions", nargs="+", choices=VERSIONS, default=list(VERSIONS))
    parser.add_argument("--run-ids", nargs="+", type=int, default=[1, 2, 3])
    parser.add_argument("--judge-runs", type=int, default=5)
    parser.add_argument("--phase", choices=("all", "benchmark", "judge"), default="all")
    parser.add_argument("--startup-timeout", type=int, default=900)
    args = parser.parse_args()
    os.chdir(ROOT)

    first = load_experiment(args.config, args.versions[0])
    run_env = os.environ.copy()
    load_env_file(Path(first["env_file"]), run_env)
    model_key_name = str(first["model_api_key_env"])
    judge_key_name = str(first["judge_api_key_env"])
    if not run_env.get(model_key_name, "").strip():
        raise SystemExit(f"Missing {model_key_name} in .env")
    if not run_env.get(judge_key_name, "").strip():
        run_env[judge_key_name] = run_env[model_key_name]
        print(f"Using {model_key_name} for the judge in process memory; no secret was written.")
    run_env["PYTHONDONTWRITEBYTECODE"] = "1"
    run_env["PATH"] = os.pathsep.join(
        [
            str((ROOT / "node_modules/.bin").resolve()),
            str((ROOT / ".venv/bin").resolve()),
            run_env.get("PATH", ""),
        ]
    )
    one_mcp = (ROOT / "node_modules/.bin/1mcp").resolve()
    if not one_mcp.is_file():
        raise SystemExit("Missing project-local 1MCP")

    subprocess.run(
        [sys.executable, "scripts/build_full_rewrite_versions.py"],
        cwd=ROOT,
        env=run_env,
        check=True,
    )
    log_dir = ROOT / "logs/formal"
    log_dir.mkdir(parents=True, exist_ok=True)

    if args.phase in {"all", "benchmark"}:
        for version in args.versions:
            resolved = load_experiment(args.config, version)
            port = urlsplit(str(resolved["mcp_url"])).port
            if port is None:
                raise RuntimeError(f"MCP URL has no port for {version}")
            server_log_path = log_dir / f"{version}-1mcp.log"
            with server_log_path.open("a", encoding="utf-8") as server_log:
                process = subprocess.Popen(
                    [
                        str(one_mcp),
                        "serve",
                        "--config",
                        str(resolved["server_config"]),
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
                    cwd=ROOT,
                    env=run_env,
                    stdout=server_log,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                )
                try:
                    servers = wait_for_servers(
                        process,
                        port,
                        int(resolved["configured_server_count"]),
                        args.startup_timeout,
                    )
                    unavailable = [
                        str(server.get("server"))
                        for server in servers
                        if server.get("status") != "connected"
                        or server.get("available") is not True
                    ]
                    if unavailable:
                        raise RuntimeError(
                            f"{version} MCP servers unavailable: {unavailable}"
                        )
                    subprocess.run(
                        matrix_command(args, "benchmark", [version]),
                        cwd=ROOT,
                        env=run_env,
                        check=True,
                    )
                finally:
                    stop_process_group(process)

    if args.phase in {"all", "judge"}:
        subprocess.run(
            matrix_command(args, "judge", list(args.versions)),
            cwd=ROOT,
            env=run_env,
            check=True,
        )

    print("PAID_MATRIX_COMPLETED")


if __name__ == "__main__":
    main()
