#!/usr/bin/env python3
"""Run the two-task canary with a free local Ollama model."""

from __future__ import annotations

import os
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
LOCAL_OLLAMA = ROOT / "external/ollama-bin/ollama"
MODELS = ROOT / "external/ollama-models"
HOST = "127.0.0.1:11434"
MODEL = "qwen3.5:4b"


def ready() -> bool:
    try:
        return requests.get(f"http://{HOST}/api/tags", timeout=2).status_code == 200
    except requests.RequestException:
        return False


def main() -> None:
    ollama = LOCAL_OLLAMA if LOCAL_OLLAMA.is_file() else shutil.which("ollama")
    if not ollama:
        raise SystemExit("Ollama is missing; install it from https://ollama.com/download")
    ollama = str(ollama)
    env = os.environ.copy()
    env.update(
        {
            "OLLAMA_HOST": HOST,
            "OLLAMA_MODELS": str(MODELS),
            "OLLAMA_CONTEXT_LENGTH": "16384",
            "MODEL_API_KEY": "ollama-local",
            "MODEL_BASE_URL": f"http://{HOST}/v1",
            "JUDGE_API_KEY": "ollama-local",
            "JUDGE_BASE_URL": f"http://{HOST}/v1",
        }
    )
    server = None
    if not ready():
        server = subprocess.Popen(
            [ollama, "serve"],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        for _ in range(60):
            if ready():
                break
            if server.poll() is not None:
                raise SystemExit("Ollama exited before becoming ready")
            time.sleep(1)
        else:
            raise SystemExit("Ollama did not become ready within 60 seconds")
    try:
        listed = subprocess.run(
            [ollama, "show", MODEL], env=env, capture_output=True
        )
        if listed.returncode:
            subprocess.run([ollama, "pull", MODEL], env=env, check=True)
        command = [
            sys.executable,
            "scripts/run_real_canary.py",
            "--config",
            "configs/canary-local.json",
            "--local",
            "--overwrite",
            *sys.argv[1:],
        ]
        raise SystemExit(subprocess.run(command, cwd=ROOT, env=env).returncode)
    finally:
        if server and server.poll() is None:
            os.killpg(server.pid, signal.SIGTERM)
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(server.pid, signal.SIGKILL)


if __name__ == "__main__":
    main()
