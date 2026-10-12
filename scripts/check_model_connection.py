#!/usr/bin/env python3
"""Make a minimal paid request to verify configured model credentials."""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from experiment_config import (
    ConfigError,
    load_env_file,
    load_experiment,
    resolve_runtime_credentials,
    validate_endpoint_model_consistency,
)


def endpoint_connectivity(base_url: str, timeout: float = 10.0) -> None:
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"invalid base URL: {base_url!r}")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    with socket.create_connection((parsed.hostname, port), timeout=timeout) as connection:
        if parsed.scheme == "https":
            context = ssl.create_default_context()
            with context.wrap_socket(connection, server_hostname=parsed.hostname):
                pass


def error_advice(exc: BaseException) -> str:
    status = getattr(exc, "status_code", None)
    text = str(exc).lower()
    if status == 401 or "authentication" in text or "invalid api key" in text:
        return "401/authentication failed: replace the API key in the local .env file."
    if status == 402 or "insufficient balance" in text:
        return "Insufficient balance: top up the provider account before running the benchmark."
    if "model" in text and ("not found" in text or "does not exist" in text):
        return "Model not found: verify model.name in the config against the provider model list."
    if isinstance(exc, TimeoutError) or "timeout" in type(exc).__name__.lower() or "timed out" in text:
        return "Timeout: check the network/proxy and confirm the configured base URL is reachable."
    if isinstance(exc, OSError):
        return "Network/TLS failure: check DNS, proxy settings, certificates, and the base URL."
    return f"Request failed: {exc}. Check the key, model name, base URL, and provider status."


def endpoint_candidates(base_url: str) -> list[str]:
    """Return endpoint variants to probe, preserving an explicit /v1 URL."""
    normalized = base_url.rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.hostname == "api.deepseek.com" and parsed.path in {"", "/"}:
        return [normalized, normalized + "/v1"]
    return [normalized]


def tool_call_self_test(client: Any, model: str) -> bool:
    """Verify the provider returns OpenAI-compatible function calls."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": "What is the weather in Beijing? Use the get_weather tool.",
            }
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather for a city",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                        "required": ["city"],
                    },
                },
            }
        ],
        max_tokens=100,
        temperature=0.0,
    )
    message = response.choices[0].message
    calls = getattr(message, "tool_calls", None)
    if not isinstance(calls, list) or not calls:
        print("Tool-calling self-test: FAIL")
        print(f"  - raw content: {getattr(message, 'content', None)!r}")
        print(
            "  - Model ignored the tool definition. Try deepseek-chat "
            "(not deepseek-reasoner)."
        )
        return False
    function = getattr(calls[0], "function", None)
    name = getattr(function, "name", None)
    if name != "get_weather":
        print("Tool-calling self-test: FAIL")
        print(f"  - raw content: {getattr(message, 'content', None)!r}")
        print(f"  - model called {name!r}, not 'get_weather'.")
        print("  - Model called a different function. Check tool definitions match.")
        return False
    arguments = getattr(function, "arguments", "")
    try:
        parsed = json.loads(arguments)
    except (TypeError, json.JSONDecodeError):
        print("Tool-calling self-test: FAIL")
        print(f"  - raw content: {getattr(message, 'content', None)!r}")
        print(f"  - raw arguments: {arguments!r}")
        print(
            "  - Model emitted malformed tool arguments. This is a known DeepSeek "
            "compatibility issue; do not change your harness config."
        )
        return False
    if not isinstance(parsed, dict) or not parsed.get("city"):
        print("Tool-calling self-test: FAIL")
        print(f"  - raw content: {getattr(message, 'content', None)!r}")
        print(f"  - parsed arguments lack city: {parsed!r}")
        print("  - Check tool definitions match the requested arguments.")
        return False
    print("Tool-calling self-test: PASS")
    print("  - model emitted a properly formatted tool_calls[]")
    print(f"  - arguments parsed as JSON: {json.dumps(parsed, ensure_ascii=False)}")
    return True


def check_target(
    *,
    label: str,
    model: str,
    api_key: str,
    base_url: str,
    credential_source: str,
    client_factory: Callable[..., Any],
    connectivity_checker: Callable[[str], None] = endpoint_connectivity,
    check_tools: bool = False,
) -> bool:
    print(f"[{label}] model: {model}")
    print(f"[{label}] base_url: {base_url}")
    print(f"[{label}] credential source: {credential_source}")
    selected_client = None
    selected_response = None
    latency = 0.0
    for candidate in endpoint_candidates(base_url):
        try:
            connectivity_checker(candidate)
            client = client_factory(
                api_key=api_key,
                base_url=candidate,
                timeout=30.0,
                max_retries=2,
            )
            started = time.monotonic()
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Reply with the single word: ok"}],
                max_tokens=5,
                temperature=0.0,
            )
            latency = time.monotonic() - started
            selected_client = client
            selected_response = response
            if len(endpoint_candidates(base_url)) > 1:
                print(
                    f"Detected DeepSeek endpoint: {candidate} "
                    f"(200 OK in {latency:.3f}s)"
                )
            else:
                print(f"[{label}] HTTP connectivity: ok")
            break
        except BaseException as exc:
            print(f"[{label}] endpoint probe failed: {candidate}: {error_advice(exc)}")
    if selected_client is None or selected_response is None:
        return False
    try:
        response = selected_response
        content = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None)
        print(f"[{label}] provider_model: {getattr(response, 'model', model)}")
        print(f"[{label}] response: {content.strip()}")
        print(f"[{label}] prompt_tokens: {getattr(usage, 'prompt_tokens', None)}")
        print(f"[{label}] completion_tokens: {getattr(usage, 'completion_tokens', None)}")
        print(f"[{label}] latency_seconds: {latency:.3f}")
        if check_tools and not tool_call_self_test(selected_client, model):
            return False
        return True
    except BaseException as exc:
        print(f"[{label}] ERROR: {error_advice(exc)}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify model and judge API connectivity")
    parser.add_argument("--config", type=Path, default=Path("configs/experiment.json"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--skip-judge", action="store_true")
    args = parser.parse_args()
    try:
        load_env_file(args.env_file.resolve())
        resolved = load_experiment(args.config, "early")
        resolve_runtime_credentials(resolved)
        model_key = str(resolved["model_api_key_resolved"])
        model_url = str(resolved["model_base_url_resolved"])
        if not model_key or not model_url:
            raise ConfigError("MODEL_API_KEY and MODEL_BASE_URL must be set in the local .env")
        validate_endpoint_model_consistency(str(resolved["model_name"]), model_url)
        from openai import OpenAI

        passed = check_target(
            label="agent",
            model=str(resolved["model_name"]),
            api_key=model_key,
            base_url=model_url,
            credential_source=str(resolved["model_api_key_env"]),
            client_factory=OpenAI,
            check_tools=True,
        )
        if not args.skip_judge:
            judge_key = str(resolved["judge_api_key_resolved"])
            judge_url = str(resolved["judge_base_url_resolved"])
            if not judge_key or not judge_url:
                raise ConfigError(
                    "Judge credentials are empty and MODEL_* fallback is unavailable"
                )
            passed = check_target(
                label="judge",
                model=str(resolved["judge_name"]),
                api_key=judge_key,
                base_url=judge_url,
                credential_source=str(resolved["judge_api_key_source"]),
                client_factory=OpenAI,
            ) and passed
        if not passed:
            raise SystemExit(1)
    except (ConfigError, OSError, ValueError) as exc:
        raise SystemExit(f"MODEL CHECK ERROR: {exc}") from exc


if __name__ == "__main__":
    main()
