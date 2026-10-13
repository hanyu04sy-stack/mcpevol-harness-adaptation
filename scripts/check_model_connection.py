#!/usr/bin/env python3
"""Cheap, human-readable model and tool-calling preflight."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, TextIO
from urllib.parse import urlsplit

from experiment_config import (
    ConfigError,
    parse_env_file,
    pricing_warning,
    validate_endpoint_model_consistency,
)
from rate_limit_retry import call_with_rate_limit_retry, new_retry_audit


@dataclass
class Result:
    number: int
    title: str
    passed: bool
    detail: str
    action: str
    suffix: str = ""


def endpoint_candidates(url: str) -> list[str]:
    url = url.rstrip("/")
    parsed = urlsplit(url)
    return [url, url + "/v1"] if parsed.hostname == "api.deepseek.com" and parsed.path in {"", "/"} else [url]


JUDGE_RUNS_PER_TASK = 5
JUDGE_MAX_ATTEMPTS_PER_VALID_SCORE = 3
CHARS_PER_TOKEN_ESTIMATE = 4
JUDGE_COMPLETION_TOKENS_PER_ATTEMPT = 128


def friendly_error(exc: Exception) -> tuple[str, str]:
    status, message = getattr(exc, "status_code", None), str(exc).strip() or type(exc).__name__
    lower = message.lower()
    if status in {401, 403} or "authentication" in lower or "invalid api key" in lower:
        return (
            f"HTTP {status or 401}: Invalid API key ({message})",
            "Fix: open .env and set MODEL_API_KEY to a valid key from https://platform.deepseek.com/.\nRe-run this script after editing.",
        )
    if status == 402 or "insufficient balance" in lower:
        return (
            f"HTTP 402: insufficient balance ({message})",
            "Fix: check the key and account balance at https://platform.deepseek.com/, then re-run this script.",
        )
    if status == 404 or ("model" in lower and ("not found" in lower or "does not exist" in lower)):
        return (
            f"HTTP 404: model not found ({message})",
            "Fix: model.name and the endpoint do not match. Check whether configs/experiment.json still says gpt-4o instead of deepseek-flash.",
        )
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)) or any(x in lower for x in ("timeout", "timed out", "connection error")):
        return (
            f"Network/timeout error: {message}",
            "Fix: the network cannot reach the endpoint. Check the proxy or try another network, then re-run this script.",
        )
    if isinstance(exc, json.JSONDecodeError) or "json" in lower:
        return (
            f"OpenAI-compatible response decode failed: {message}",
            "Fix: the endpoint did not return OpenAI-compatible JSON. Check that MODEL_BASE_URL is an API endpoint, not a website URL.",
        )
    return f"Request failed: {message}", "Fix: check the key, endpoint, model.name, and provider status, then re-run this script."


def intro(config: Path, env: Path, out: TextIO) -> None:
    print("""== Model connection self-check ==
This script verifies four things before you spend money on the real benchmark:
  [1] MODEL_API_KEY is valid and the endpoint responds.
  [2] model.name in configs/experiment.json matches what the endpoint expects.
  [3] DeepSeek /v1 endpoint auto-detection (which base_url works).
  [4] Tool calling works in the format upstream agent expects.
If any check FAILS, fix it before running smoke or the 30-task experiment.""", file=out)
    print(f"Config: {config}\nEnv:    {env}\n", file=out)


def render(result: Result, out: TextIO) -> None:
    print(f"[{'PASS' if result.passed else 'FAIL'}] {result.number}. {result.title}", file=out)
    print(f"       {result.detail}", file=out)
    for i, line in enumerate(result.action.splitlines()):
        print(("       " if i == 0 else "            ") + line, file=out)
    print(file=out)


def skipped(number: int, title: str, reason: str) -> Result:
    return Result(number, title, False, f"Not run: {reason}", "Fix: resolve the earlier FAIL, then re-run this script.")


def check_config(
    model: str, judge: str, model_endpoint: str, judge_endpoint: str
) -> Result:
    try:
        if model != judge:
            raise ConfigError(f"model.name={model!r} does not match judge.name={judge!r}")
        validate_endpoint_model_consistency(model, model_endpoint)
        validate_endpoint_model_consistency(judge, judge_endpoint)
        return Result(2, "Config / env consistency", True, f"model={model}, judge={judge} (match), model_endpoint={model_endpoint}, judge_endpoint={judge_endpoint}", "Next: both Agent and Judge configurations agree with their endpoints.")
    except ConfigError as exc:
        if "DeepSeek" in str(exc) and not model.lower().startswith("deepseek"):
            fix = "Fix: change model.name and judge.name in configs/experiment.json to deepseek-flash."
        elif model.lower().startswith("deepseek"):
            fix = "Fix: set MODEL_BASE_URL and JUDGE_BASE_URL (if non-empty) to https://api.deepseek.com, or use model slugs served by those endpoints."
        else:
            fix = "Fix: make model.name and judge.name identical in configs/experiment.json."
        return Result(2, "Config / env consistency", False, str(exc), fix)


def request_chat(client: Any, model: str) -> tuple[Any, float]:
    started = time.monotonic()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Reply with the single word: ok"}],
        max_tokens=5,
        temperature=0.0,
    )
    return response, time.monotonic() - started


def probe(
    model: str,
    key: str,
    endpoint: str,
    factory: Callable[..., Any],
    retry_audit: dict[str, Any] | None = None,
):
    retry_audit = retry_audit or new_retry_audit(2)
    successes, failures = [], []
    for candidate in endpoint_candidates(endpoint):
        try:
            client = factory(api_key=key, base_url=candidate, timeout=30.0, max_retries=0)
            started = time.monotonic()
            response = call_with_rate_limit_retry(
                lambda: request_chat(client, model)[0],
                max_retries=2,
                audit=retry_audit,
            )
            latency = time.monotonic() - started
            successes.append((candidate, response, latency))
        except Exception as exc:
            failures.append((candidate, exc))
    return (successes[0] if successes else (None, None, None)), failures


def chat_result(endpoint: str, response: Any, latency: float) -> Result:
    try:
        message, usage = response.choices[0].message, response.usage
        content = (message.content or "").strip()
        prompt, completion = int(usage.prompt_tokens), int(usage.completion_tokens)
        if not content or prompt < 1:
            raise json.JSONDecodeError("content is empty or prompt token usage is invalid", "", 0)
        reported = str(getattr(response, "model", "<not reported>"))
        return Result(1, "Chat completion", True, f"model={reported}, endpoint={endpoint}, latency={latency:.3f}s, usage={prompt} prompt / {completion} completion tokens.", "Next: this is the model that will run all 30 tasks.")
    except (AttributeError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        detail, fix = friendly_error(exc)
        return Result(1, "Chat completion", False, detail, fix)


def _tool_call_payload(call: Any) -> dict[str, Any]:
    function = getattr(call, "function", None)
    return {
        "id": getattr(call, "id", ""),
        "type": "function",
        "function": {
            "name": getattr(function, "name", ""),
            "arguments": getattr(function, "arguments", ""),
        },
    }


def check_tools(
    client: Any, model: str, retry_audit: dict[str, Any] | None = None
) -> Result:
    retry_audit = retry_audit or new_retry_audit(2)
    try:
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "plan_trip",
                    "description": "Create a trip plan from structured preferences",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "destinations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "city": {"type": "string"},
                                        "days": {"type": "integer"},
                                    },
                                    "required": ["city", "days"],
                                },
                            },
                            "preferences": {
                                "type": "object",
                                "properties": {
                                    "activities": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    }
                                },
                                "required": ["activities"],
                            },
                        },
                        "required": ["destinations", "preferences"],
                    },
                },
            },
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
            },
        ]
        messages = [
            {
                "role": "user",
                "content": (
                    "First call plan_trip for Beijing (2 days) and Shanghai "
                    "(3 days), with food and museums as activities."
                ),
            }
        ]
        response = call_with_rate_limit_retry(
            lambda: client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                max_tokens=100,
                temperature=0.0,
            ),
            max_retries=2,
            audit=retry_audit,
        )
        message = response.choices[0].message
        calls = getattr(message, "tool_calls", None)
        if not isinstance(calls, list) or not calls:
            return Result(4, "Tool calling", False, f"No tool_calls[] returned; raw content={getattr(message, 'content', None)!r}", "Fix: the model ignored the tool definition. Use deepseek-flash, not deepseek-reasoner.")
        function = getattr(calls[0], "function", None)
        if getattr(function, "name", None) != "plan_trip":
            return Result(4, "Tool calling", False, f"Model called {getattr(function, 'name', None)!r}, not plan_trip.", "Fix: check the tool definition format.")
        first_id = getattr(calls[0], "id", None)
        if not isinstance(first_id, str) or not first_id:
            return Result(4, "Tool calling", False, "First tool call has no tool_call_id.", "Fix: the endpoint must return OpenAI-compatible tool call IDs.")
        raw = getattr(function, "arguments", "")
        try:
            arguments = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return Result(4, "Tool calling", False, f"Tool arguments are malformed JSON: {raw!r}", "Fix: DeepSeek tool calling compatibility failed; this is not a harness configuration error. If frequent, consider a matching OpenRouter gpt-4o configuration.")
        destinations = arguments.get("destinations") if isinstance(arguments, dict) else None
        preferences = arguments.get("preferences") if isinstance(arguments, dict) else None
        activities = preferences.get("activities") if isinstance(preferences, dict) else None
        if not isinstance(destinations, list) or len(destinations) < 2 or not all(isinstance(item, dict) and item.get("city") and isinstance(item.get("days"), int) for item in destinations) or not isinstance(activities, list) or not activities:
            return Result(4, "Tool calling", False, f"Nested/array arguments are invalid: {arguments!r}", "Fix: check nested object and array support in the tool definition format.")
        messages.extend(
            [
                {
                    "role": "assistant",
                    "content": getattr(message, "content", None),
                    "tool_calls": [_tool_call_payload(calls[0])],
                },
                {
                    "role": "tool",
                    "tool_call_id": first_id,
                    "content": json.dumps({"status": "planned"}),
                },
                {
                    "role": "user",
                    "content": "Now call get_weather for Beijing.",
                },
            ]
        )
        chained = call_with_rate_limit_retry(
            lambda: client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                max_tokens=100,
                temperature=0.0,
            ),
            max_retries=2,
            audit=retry_audit,
        )
        chained_calls = getattr(chained.choices[0].message, "tool_calls", None)
        if not isinstance(chained_calls, list) or not chained_calls:
            return Result(4, "Tool calling", False, "No second tool call returned after a tool result.", "Fix: the model must support consecutive tool calls.")
        chained_function = getattr(chained_calls[0], "function", None)
        second_id = getattr(chained_calls[0], "id", None)
        if getattr(chained_function, "name", None) != "get_weather" or not isinstance(second_id, str) or not second_id:
            return Result(4, "Tool calling", False, "Second call lacks get_weather or a tool_call_id.", "Fix: check consecutive OpenAI-compatible tool calling.")
        weather_arguments = json.loads(getattr(chained_function, "arguments", ""))
        if not isinstance(weather_arguments, dict) or not weather_arguments.get("city"):
            return Result(4, "Tool calling", False, f"Second-call arguments lack city: {weather_arguments!r}", "Fix: check the tool definition format.")
        return Result(4, "Tool calling", True, f"nested_arguments={json.dumps(arguments, ensure_ascii=False)}, chained_arguments={json.dumps(weather_arguments, ensure_ascii=False)}, linked_tool_call_id={first_id}", "Next: nested arrays, consecutive calls, and tool_call_id linkage match the upstream format.")
    except (AttributeError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        detail, fix = friendly_error(exc)
        return Result(4, "Tool calling", False, detail, fix)
    except Exception as exc:
        detail, fix = friendly_error(exc)
        return Result(4, "Tool calling", False, detail, fix)


def _tokens_from_chars(characters: int) -> int:
    return max(1, (characters + CHARS_PER_TOKEN_ESTIMATE - 1) // CHARS_PER_TOKEN_ESTIMATE)


def _cost(prompt_tokens: int, completion_tokens: int, rate: dict[str, Any]) -> float:
    return (
        prompt_tokens / 1_000_000 * float(rate["prompt_per_mtok_usd"])
        + completion_tokens
        / 1_000_000
        * float(rate["completion_per_mtok_usd"])
    )


def _usage_calibration(
    root: Path, model: str, target_tasks: int
) -> dict[str, Any] | None:
    """Use the newest completed real run to calibrate per-task token estimates."""
    candidates = sorted(
        (root / "results").rglob("run-metadata.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if (root / "results").is_dir() else []
    for metadata_path in candidates:
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            configured = metadata.get("model", {})
            configured_name = (
                configured.get("name") if isinstance(configured, dict) else configured
            )
            if configured_name != model or metadata.get("status") != "completed":
                continue
            run_dir = metadata_path.parent
            judge_results_path = run_dir / "judge-results.json"
            if not judge_results_path.is_file():
                continue
            tasks = json.loads(judge_results_path.read_text(encoding="utf-8")).get(
                "tasks", []
            )
            observed_tasks = len(tasks) if isinstance(tasks, list) else 0
            agent_prompt = metadata.get("total_prompt_tokens")
            agent_completion = metadata.get("total_completion_tokens")
            if (
                observed_tasks < 1
                or not isinstance(agent_prompt, int)
                or not isinstance(agent_completion, int)
            ):
                continue
            scale = target_tasks / observed_tasks
            calibrated: dict[str, Any] = {
                "source": str(metadata_path.relative_to(root)),
                "observed_tasks": observed_tasks,
                "agent_prompt_tokens": round(agent_prompt * scale),
                "agent_completion_tokens": round(agent_completion * scale),
            }
            judge_path = run_dir / "judge-metadata.json"
            if judge_path.is_file():
                judge = json.loads(judge_path.read_text(encoding="utf-8"))
                usage = judge.get("usage", {})
                valid_scores = judge.get("valid_score_count")
                for source_key, output_key in (
                    ("judge_prompt_tokens", "judge_prompt_tokens"),
                    ("judge_completion_tokens", "judge_completion_tokens"),
                ):
                    value = usage.get(source_key)
                    if isinstance(value, int):
                        calibrated[output_key] = round(value * scale)
                if isinstance(valid_scores, int) and valid_scores > 0:
                    calibrated["valid_score_count"] = valid_scores
                    calibrated["judge_prompt_per_score"] = (
                        usage.get("judge_prompt_tokens", 0) / valid_scores
                    )
                    calibrated["judge_completion_per_score"] = (
                        usage.get("judge_completion_tokens", 0) / valid_scores
                    )
            return calibrated
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return None


def estimate_cost(config: dict[str, Any], root: Path) -> dict[str, Any] | None:
    """Estimate one version using actual stored trajectory text plus Judge reserves."""
    try:
        model = str(config["model"]["name"])
        maximum = int(config["model"]["max_completion_tokens"])
        count = int(config["dataset"]["size"])
        rate = json.loads((root / "configs/pricing.json").read_text(encoding="utf-8"))["models"][model]
        dataset_path = root / str(config["dataset"]["path"])
        cases = json.loads(dataset_path.read_text(encoding="utf-8"))
        if not isinstance(cases, list) or not cases:
            raise ValueError("dataset is empty")
        cases = cases[:count]

        agent_prompt_chars = 0
        agent_completion_chars = 0
        judge_prompt_chars = 0
        for case in cases:
            if not isinstance(case, dict):
                continue
            messages = case.get("trajectory_messages", [])
            assistant_calls = 0
            if isinstance(messages, list):
                for index, message in enumerate(messages):
                    if isinstance(message, dict) and message.get("role") == "assistant":
                        agent_prompt_chars += len(
                            json.dumps(messages[:index], ensure_ascii=False)
                        )
                        agent_completion_chars += len(
                            json.dumps(message, ensure_ascii=False)
                        )
                        assistant_calls += 1
            if assistant_calls == 0:
                agent_prompt_chars += len(str(case.get("question", "")))
                agent_completion_chars += maximum * CHARS_PER_TOKEN_ESTIMATE
            judge_prompt_chars += len(
                json.dumps(
                    {
                        "question": case.get("question", ""),
                        "tools": case.get("involved_tools", case.get("servers", {})),
                        "trajectory": messages,
                        "answer": case.get("answer", ""),
                    },
                    ensure_ascii=False,
                )
            )

        agent_prompt = _tokens_from_chars(agent_prompt_chars)
        agent_completion = _tokens_from_chars(agent_completion_chars)
        judge_prompt_once = _tokens_from_chars(judge_prompt_chars)
        judge_prompt = judge_prompt_once * JUDGE_RUNS_PER_TASK
        judge_completion = (
            len(cases)
            * JUDGE_RUNS_PER_TASK
            * JUDGE_COMPLETION_TOKENS_PER_ATTEMPT
        )
        retry_attempts = len(cases) * JUDGE_RUNS_PER_TASK * (
            JUDGE_MAX_ATTEMPTS_PER_VALID_SCORE - 1
        )
        retry_prompt = (
            judge_prompt_once
            * JUDGE_RUNS_PER_TASK
            * (JUDGE_MAX_ATTEMPTS_PER_VALID_SCORE - 1)
        )
        retry_completion = retry_attempts * JUDGE_COMPLETION_TOKENS_PER_ATTEMPT
        calibration = _usage_calibration(root, model, len(cases))
        estimation_method = "actual_trajectory_chars_divided_by_4"
        calibration_source = None
        if calibration is not None:
            agent_prompt = int(calibration["agent_prompt_tokens"])
            agent_completion = int(calibration["agent_completion_tokens"])
            if "judge_prompt_tokens" in calibration:
                judge_prompt = int(calibration["judge_prompt_tokens"])
            if "judge_completion_tokens" in calibration:
                judge_completion = int(calibration["judge_completion_tokens"])
            if "judge_prompt_per_score" in calibration:
                retry_prompt = round(
                    float(calibration["judge_prompt_per_score"]) * retry_attempts
                )
            if "judge_completion_per_score" in calibration:
                retry_completion = round(
                    float(calibration["judge_completion_per_score"])
                    * retry_attempts
                )
            estimation_method = "calibrated_from_real_usage"
            calibration_source = calibration["source"]
        agent_cost = _cost(agent_prompt, agent_completion, rate)
        judge_cost = _cost(judge_prompt, judge_completion, rate)
        retry_reserve = _cost(retry_prompt, retry_completion, rate)
        return {
            "task_count": len(cases),
            "agent_prompt_tokens": agent_prompt,
            "agent_completion_tokens": agent_completion,
            "judge_prompt_tokens": judge_prompt,
            "judge_completion_tokens": judge_completion,
            "judge_runs_per_task": JUDGE_RUNS_PER_TASK,
            "retry_attempt_reserve": retry_attempts,
            "retry_prompt_tokens": retry_prompt,
            "retry_completion_tokens": retry_completion,
            "estimation_method": estimation_method,
            "calibration_source": calibration_source,
            "agent_cost": agent_cost,
            "judge_cost": judge_cost,
            "retry_reserve": retry_reserve,
            "total": agent_cost + judge_cost + retry_reserve,
        }
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def summary(
    results: list[Result],
    config: dict[str, Any],
    root: Path,
    out: TextIO,
    retry_audit: dict[str, Any] | None = None,
) -> None:
    print("== Summary ==", file=out)
    for item in results:
        suffix = f" {item.suffix}" if item.suffix else ""
        print(f"  [{'PASS' if item.passed else 'FAIL'}] {item.number}. {item.title}{suffix}", file=out)
    if all(item.passed for item in results):
        print("""All checks passed. You can now run:
  1. .venv/bin/python scripts/run_smoke_tests.py        (free, no API cost)
  2. .venv/bin/python scripts/run_benchmark.py --version early --dry-run
  3. Then start the 1MCP server and run the real experiment.""", file=out)
    else:
        print("Do NOT run the 30-task experiment yet. Fix the FAIL above, then re-run this script.", file=out)
        estimate = estimate_cost(config, root)
        if estimate is None:
            print("Estimated cost if you ran anyway: unknown (see configs/pricing.json).", file=out)
        else:
            print(
                "Estimated single-version cost if you ran anyway: "
                f"~${estimate['total']:.2f} = Agent ${estimate['agent_cost']:.2f} "
                f"+ Judge {estimate['judge_runs_per_task']}x ${estimate['judge_cost']:.2f} "
                f"+ malformed-Judge retry reserve ${estimate['retry_reserve']:.2f}.",
                file=out,
            )
            print(
                (
                    f"Estimate calibrated from real usage in {estimate['calibration_source']} "
                    if estimate["calibration_source"]
                    else "Estimate uses actual stored trajectory text at 4 chars/token "
                )
                + f"(~{estimate['agent_prompt_tokens'] + estimate['judge_prompt_tokens']:,} prompt tokens), includes up to "
                f"{estimate['retry_attempt_reserve']} Judge retries, and excludes "
                "normally-unbilled HTTP 429 retries. See configs/pricing.json.",
                file=out,
            )
    if retry_audit is not None:
        print(
            "429 retry audit: "
            f"responses={retry_audit['rate_limit_responses']}, "
            f"actual_retries={retry_audit['actual_retries']}, "
            f"total_backoff_seconds={retry_audit['total_backoff_seconds']}, "
            f"exhausted_requests={retry_audit['exhausted_requests']}, "
            f"events={json.dumps(retry_audit['events'], ensure_ascii=False)}",
            file=out,
        )


def run_self_check(*, config_path: Path, env_file: Path, client_factory: Callable[..., Any], environ: Mapping[str, str] | None, stream: TextIO) -> int:
    intro(config_path, env_file, stream)
    if not env_file.is_file():
        print("[FAIL] .env file is missing.\n       Fix: cp .env.example .env first, then fill MODEL_API_KEY", file=stream)
        return 2
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        dotenv = parse_env_file(env_file)
    except (OSError, json.JSONDecodeError, ConfigError) as exc:
        print(f"[FAIL] Cannot load configuration: {exc}\n       Fix: repair the config or .env, then re-run this script.", file=stream)
        return 1
    source = os.environ if environ is None else environ
    model_cfg, judge_cfg = config["model"], config["judge"]
    price_warning = pricing_warning(
        config_path.resolve().parents[1] / "configs/pricing.json",
        str(model_cfg["name"]),
    )
    if price_warning:
        print(f"[WARN] {price_warning}\n", file=stream)
    key_name, url_name = str(model_cfg["api_key_env"]), str(model_cfg["base_url_env"])
    key = str(source.get(key_name, dotenv.get(key_name, ""))).strip()
    endpoint = str(source.get(url_name, dotenv.get(url_name, ""))).strip()
    judge_key_name = str(judge_cfg.get("api_key_env", "JUDGE_API_KEY"))
    judge_url_name = str(judge_cfg.get("base_url_env", "JUDGE_BASE_URL"))
    judge_key = str(
        source.get(judge_key_name, dotenv.get(judge_key_name, ""))
    ).strip() or key
    judge_endpoint = str(
        source.get(judge_url_name, dotenv.get(judge_url_name, ""))
    ).strip() or endpoint
    model, judge = str(model_cfg["name"]), str(judge_cfg["name"])
    retry_audit = new_retry_audit(2)
    consistency = check_config(model, judge, endpoint, judge_endpoint)
    if not consistency.passed:
        results = [skipped(1, "Chat completion", "config / env consistency failed"), consistency, skipped(3, "Endpoint detection", "config / env consistency failed"), skipped(4, "Tool calling", "config / env consistency failed")]
    elif not key:
        results = [Result(1, "Chat completion", False, "MODEL_API_KEY is empty.", "Fix: open .env and set MODEL_API_KEY to a valid key from https://platform.deepseek.com/.\nRe-run this script after editing."), consistency, skipped(3, "Endpoint detection", "MODEL_API_KEY is empty"), skipped(4, "Tool calling", "MODEL_API_KEY is empty")]
    else:
        (selected, response, latency), failures = probe(
            model, key, endpoint, client_factory, retry_audit
        )
        if selected is None:
            detail, fix = friendly_error(failures[0][1] if failures else RuntimeError("no endpoint candidate"))
            chat = Result(1, "Chat completion", False, detail, fix)
            failed = "; ".join(f"{url}: {friendly_error(exc)[0]}" for url, exc in failures)
            endpoint_result = Result(3, "Endpoint detection", False, failed or "No endpoint succeeded.", "Fix: manually try https://api.deepseek.com/v1, then re-run this script.")
            tool = skipped(4, "Tool calling", "no endpoint returned HTTP 200")
        else:
            chat = chat_result(selected, response, latency)
            is_deepseek = urlsplit(endpoint).hostname == "api.deepseek.com"
            judge_selected = selected
            judge_failures: list[tuple[str, Exception]] = []
            if judge_endpoint != endpoint or judge_key != key:
                (judge_selected, _, _), judge_failures = probe(
                    judge, judge_key, judge_endpoint, client_factory, retry_audit
                )
            if judge_selected is None:
                failed = "; ".join(
                    f"{url}: {friendly_error(exc)[0]}"
                    for url, exc in judge_failures
                )
                endpoint_result = Result(
                    3,
                    "Endpoint detection",
                    False,
                    f"Agent selected {selected}; Judge failed: {failed}",
                    "Fix: correct JUDGE_BASE_URL/JUDGE_API_KEY or leave them blank to inherit MODEL_*.",
                )
            else:
                endpoint_result = Result(
                    3,
                    "Endpoint detection",
                    True,
                    f"Agent selected {selected}; Judge selected {judge_selected}. "
                    + (
                        f"You may set MODEL_BASE_URL={selected} in .env for stability."
                        if is_deepseek
                        else "DeepSeek probing is not required."
                    ),
                    "Next: keep these URLs; the script never rewrites .env.",
                    f"(agent={selected}, judge={judge_selected})",
                )
            client = client_factory(api_key=key, base_url=selected, timeout=30.0, max_retries=0)
            tool = check_tools(client, model, retry_audit)
        results = [chat, consistency, endpoint_result, tool]
    for result in results:
        render(result, stream)
    summary(
        results,
        config,
        config_path.resolve().parents[1],
        stream,
        retry_audit,
    )
    return 0 if all(item.passed for item in results) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify model and judge API connectivity")
    parser.add_argument("--config", type=Path, default=Path("configs/experiment.json"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args(argv)
    if not args.env_file.is_file():
        return run_self_check(
            config_path=args.config,
            env_file=args.env_file,
            client_factory=lambda **kwargs: None,
            environ=None,
            stream=sys.stdout,
        )
    try:
        from openai import OpenAI
        return run_self_check(config_path=args.config, env_file=args.env_file, client_factory=OpenAI, environ=None, stream=sys.stdout)
    except Exception as exc:
        print(f"[FAIL] Model self-check could not start: {exc}\n       Fix: run scripts/setup_environment.py, then re-run this script.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
