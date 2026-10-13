#!/usr/bin/env python3
"""Run the pinned MCPEvol judge prompt as a separate, auditable phase."""

from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment_config import (
    ConfigError,
    VERSIONS,
    load_env_file,
    load_experiment,
    pricing_warning,
    resolve_runtime_credentials,
)
from run_benchmark import load_harness, resolve_run_output
from rate_limit_retry import call_with_rate_limit_retry, new_retry_audit


def extract_json(text: str) -> dict[str, Any]:
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1)
    else:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    payload = json.loads(candidate)
    if not isinstance(payload, dict):
        raise ValueError("judge response must be a JSON object")
    for key in ("task_fulfillment", "grounding", "planning_and_efficiency"):
        score = payload.get(key)
        if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 10:
            raise ValueError(f"judge response has invalid {key}")
    return payload


def trajectory_text(messages: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for message in messages[2:]:
        role = str(message.get("role", ""))
        content = message.get("content", "")
        if role == "assistant":
            content = ""
        if role == "tool" and isinstance(content, str):
            content = content[:1000] + ("..." if len(content) > 1000 else "")
        for call in message.get("tool_calls", []) or []:
            function = call.get("function", {})
            lines.append(
                f"[{role} -> Tool]: tool_call_id={call.get('id')!r} "
                f"Call {function.get('name', 'unknown')}({function.get('arguments', '{}')})"
            )
        lines.append(f"[{role}]: {content}")
    return "\n".join(lines)


def available_tools(case: dict[str, Any]) -> str:
    tools = case.get("involved_tools")
    if isinstance(tools, list) and tools:
        return json.dumps(tools, ensure_ascii=False, indent=2)
    return json.dumps(case.get("servers", {}), ensure_ascii=False, indent=2)


def load_prompt_builder(benchmark_root: Path):
    benchmark_src = benchmark_root / "src"
    sys.path.insert(0, str(benchmark_src))
    try:
        from custom.prompt.eval_error_prompt import build_mcp_bench_judge_prompt

        return build_mcp_bench_judge_prompt
    finally:
        if sys.path and sys.path[0] == str(benchmark_src):
            sys.path.pop(0)


def find_trajectories(run_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in run_dir.glob("*/ANSWER/*.json")
        if path.is_file()
    )


def response_usage(response: Any) -> tuple[int | None, int | None]:
    usage = getattr(response, "usage", None)
    prompt = getattr(usage, "prompt_tokens", None)
    completion = getattr(usage, "completion_tokens", None)
    if not isinstance(prompt, int) or isinstance(prompt, bool):
        prompt = None
    if not isinstance(completion, int) or isinstance(completion, bool):
        completion = None
    return prompt, completion


def estimated_cost(
    prompt_tokens: int | None,
    completion_tokens: int | None,
    rate: dict[str, Any],
) -> float | None:
    if prompt_tokens is None or completion_tokens is None:
        return None
    return (
        prompt_tokens / 1_000_000 * float(rate["prompt_per_mtok_usd"])
        + completion_tokens
        / 1_000_000
        * float(rate["completion_per_mtok_usd"])
    )


def judge_audit_summary(
    configured_model: str,
    provider_models: list[str],
    usage: dict[str, int],
    attempt_count: int,
    valid_score_count: int,
) -> dict[str, Any]:
    """Return the compact model/usage audit requested for every judge run."""
    return {
        "configured_model": configured_model,
        "provider_reported_model": provider_models[0] if provider_models else None,
        "prompt_tokens": usage["prompt_tokens"] + usage["retry_prompt_tokens"],
        "completion_tokens": (
            usage["completion_tokens"] + usage["retry_completion_tokens"]
        ),
        "attempt_count": attempt_count,
        "valid_score_count": valid_score_count,
    }


def judge_case(
    case: dict[str, Any],
    *,
    client: Any,
    prompt_builder: Any,
    model: str,
    temperature: float,
    max_tokens: int,
    num_runs: int,
    seed: int,
    max_retries: int = 0,
    retry_audit: dict[str, Any] | None = None,
    on_retry_record: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    rng = random.Random(seed)
    attempts: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    provider_reported_models: list[str] = []
    usage_totals = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "retry_prompt_tokens": 0,
        "retry_completion_tokens": 0,
        "responses_missing_usage": 0,
    }
    max_attempts = num_runs * 3
    if retry_audit is None:
        retry_audit = new_retry_audit(max_retries)
    while len(scores) < num_runs and len(attempts) < max_attempts:
        order = [0, 1, 2]
        rng.shuffle(order)
        prompt = prompt_builder(
            str(case.get("question", "")),
            available_tools(case),
            trajectory_text(case.get("trajectory_messages", [])),
            str(case.get("answer", "")),
            dimension_order=tuple(order),
        )
        request: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        response = call_with_rate_limit_retry(
            lambda: client.chat.completions.create(**request),
            max_retries=max_retries,
            audit=retry_audit,
            on_record=on_retry_record,
        )
        reported_model = getattr(response, "model", None)
        if (
            isinstance(reported_model, str)
            and reported_model.strip()
            and reported_model not in provider_reported_models
        ):
            provider_reported_models.append(reported_model)
        prompt_tokens, completion_tokens = response_usage(response)
        attempt_usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        }
        if prompt_tokens is None or completion_tokens is None:
            usage_totals["responses_missing_usage"] += 1
        raw = response.choices[0].message.content or ""
        try:
            parsed = extract_json(raw)
            scores.append(parsed)
            if prompt_tokens is not None:
                usage_totals["prompt_tokens"] += prompt_tokens
            if completion_tokens is not None:
                usage_totals["completion_tokens"] += completion_tokens
            attempts.append(
                {"dimension_order": order, "result": parsed, "usage": attempt_usage}
            )
        except (json.JSONDecodeError, ValueError) as exc:
            if prompt_tokens is not None:
                usage_totals["retry_prompt_tokens"] += prompt_tokens
            if completion_tokens is not None:
                usage_totals["retry_completion_tokens"] += completion_tokens
            attempts.append(
                {
                    "dimension_order": order,
                    "error": str(exc),
                    "raw": raw,
                    "usage": attempt_usage,
                    "counted_as_retry": True,
                }
            )
    if not scores:
        raise RuntimeError(f"judge returned no valid score after {max_attempts} attempts")
    return {
        "runs": attempts,
        "usage": usage_totals,
        "provider_reported_models": provider_reported_models,
        "aggregate": {
            "successful_runs": len(scores),
            "total_runs": len(attempts),
            "task_fulfillment_mean": statistics.fmean(item["task_fulfillment"] for item in scores),
            "grounding_mean": statistics.fmean(item["grounding"] for item in scores),
            "planning_and_efficiency_mean": statistics.fmean(item["planning_and_efficiency"] for item in scores),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Score one completed benchmark run")
    parser.add_argument("--version", choices=VERSIONS, required=True)
    parser.add_argument("--harness-dir", type=Path, required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/experiment.json"))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--num-runs", type=int, default=5)
    parser.add_argument("--pricing", type=Path, default=Path("configs/pricing.json"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        resolved = load_experiment(args.config, args.version)
        harness_dir = args.harness_dir
        if not harness_dir.is_absolute():
            harness_dir = Path(resolved["project_root"]) / harness_dir
        resolved["harness_dir"] = harness_dir.resolve()
        resolved.update(load_harness(harness_dir, resolved["benchmark_commit"]))
        run_dir = resolve_run_output(resolved, args.run_id)
        trajectories = find_trajectories(run_dir)
        public = {
            "run_dir": str(run_dir),
            "trajectory_files": [str(path.relative_to(run_dir)) for path in trajectories],
            "judge": {
                "name": resolved["judge_name"],
                "temperature": resolved["judge_temperature"],
                "api_key_env": resolved["judge_api_key_env"],
                "base_url_env": resolved["judge_base_url_env"],
            },
        }
        if args.dry_run:
            print(json.dumps(public, indent=2))
            return
        if not trajectories:
            raise ConfigError(f"no upstream trajectories found under {run_dir}")
        load_env_file((args.env_file or Path(resolved["env_file"])).resolve())
        resolve_runtime_credentials(resolved)
        key = str(resolved["judge_api_key_resolved"])
        base_url = str(resolved["judge_base_url_resolved"]) or None
        if not key:
            raise ConfigError(
                "Missing JUDGE_API_KEY (or MODEL_API_KEY as fallback). Since "
                "model.name == judge.name, you can just fill MODEL_API_KEY."
            )
        run_metadata_path = run_dir / "run-metadata.json"
        if not run_metadata_path.is_file():
            raise ConfigError(f"missing benchmark metadata: {run_metadata_path}")
        run_metadata = json.loads(run_metadata_path.read_text(encoding="utf-8"))
        pricing_path = args.pricing
        if not pricing_path.is_absolute():
            pricing_path = Path(resolved["project_root"]) / pricing_path
        pricing = json.loads(pricing_path.read_text(encoding="utf-8"))
        rate = pricing.get("models", {}).get(str(resolved["judge_name"]))
        if not isinstance(rate, dict):
            raise ConfigError(
                f"no pricing configured for judge model {resolved['judge_name']!r}"
            )
        price_warning = pricing_warning(pricing_path, str(resolved["judge_name"]))
        if price_warning:
            print(f"PRICING WARNING: {price_warning}")
        agent_prompt = run_metadata.get("total_prompt_tokens")
        agent_completion = run_metadata.get("total_completion_tokens")
        if not isinstance(agent_prompt, int) or not isinstance(agent_completion, int):
            agent_prompt = agent_completion = None

        from openai import OpenAI

        client = OpenAI(
            api_key=key,
            base_url=base_url,
            timeout=float(resolved["openai_timeout_seconds"]),
            # Keep retries visible and auditable instead of delegating to the SDK.
            max_retries=0,
        )
        prompt_builder = load_prompt_builder(Path(resolved["benchmark_root"]))
        task_dir = run_dir / "judge-tasks"
        task_dir.mkdir(parents=True, exist_ok=True)
        normalized: list[dict[str, Any]] = []
        judge_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "retry_prompt_tokens": 0,
            "retry_completion_tokens": 0,
            "responses_missing_usage": 0,
        }
        judge_provider_models: list[str] = []
        judge_attempt_count = 0
        valid_score_count = 0
        rate_limit_retry = new_retry_audit(int(resolved["openai_max_retries"]))
        retry_audit_path = run_dir / "judge-rate-limit-retry.json"

        def persist_retry_audit(audit: dict[str, Any], status: str) -> None:
            retry_audit_path.write_text(
                json.dumps(
                    {"schema_version": 1, "status": status, **audit}, indent=2
                )
                + "\n",
                encoding="utf-8",
            )

        persist_retry_audit(rate_limit_retry, "running")
        for source in trajectories:
            case = json.loads(source.read_text(encoding="utf-8"))
            idx = int(case["idx"])
            evaluated = judge_case(
                case,
                client=client,
                prompt_builder=prompt_builder,
                model=str(resolved["judge_name"]),
                temperature=float(resolved["judge_temperature"]),
                max_tokens=int(resolved["max_completion_tokens"]),
                num_runs=max(1, args.num_runs),
                seed=6203 ^ idx,
                max_retries=int(resolved["openai_max_retries"]),
                retry_audit=rate_limit_retry,
                on_retry_record=lambda audit: persist_retry_audit(
                    audit,
                    "failed" if audit["exhausted_requests"] else "running",
                ),
            )
            task_payload = {
                "task_idx": idx,
                "source_file": str(source.relative_to(run_dir)),
                "eval_result": evaluated,
            }
            (task_dir / f"{idx}.json").write_text(
                json.dumps(task_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            aggregate = evaluated["aggregate"]
            judge_attempt_count += int(aggregate["total_runs"])
            valid_score_count += int(aggregate["successful_runs"])
            for name in judge_usage:
                judge_usage[name] += int(evaluated["usage"][name])
            for reported_model in evaluated["provider_reported_models"]:
                if reported_model not in judge_provider_models:
                    judge_provider_models.append(reported_model)
            tf = aggregate["task_fulfillment_mean"]
            normalized.append(
                {
                    "task_idx": idx,
                    "tf": tf,
                    "pe": aggregate["planning_and_efficiency_mean"],
                    "grounding": aggregate["grounding_mean"],
                    "success": tf >= 6,
                    "failure_category": "" if tf >= 6 else "unknown",
                    "successful_judge_runs": aggregate["successful_runs"],
                    "source_file": str(source.relative_to(run_dir)),
                }
            )

        generated_at = datetime.now(timezone.utc).isoformat()
        output = run_dir / "judge-results.json"
        output.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "strategy": resolved["strategy"],
                    "version": resolved["version"],
                    "run_id": resolved["run_id"],
                    "generated_at": generated_at,
                    "ecs": None,
                    "ecs_note": "Computed across Early/Middle/Late by collect_results.py",
                    "tasks": normalized,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        metadata = run_dir / "judge-metadata.json"
        usage_complete = judge_usage["responses_missing_usage"] == 0
        agent_cost = estimated_cost(agent_prompt, agent_completion, rate)
        judge_cost = estimated_cost(
            judge_usage["prompt_tokens"] if usage_complete else None,
            judge_usage["completion_tokens"] if usage_complete else None,
            rate,
        )
        retry_cost = estimated_cost(
            judge_usage["retry_prompt_tokens"] if usage_complete else None,
            judge_usage["retry_completion_tokens"] if usage_complete else None,
            rate,
        )
        cost_parts = (agent_cost, judge_cost, retry_cost)
        total_cost = (
            sum(cost_parts) if all(value is not None for value in cost_parts) else None
        )
        model_usage_audit = judge_audit_summary(
            str(resolved["judge_name"]),
            judge_provider_models,
            judge_usage,
            judge_attempt_count,
            valid_score_count,
        )
        metadata.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "recorded_at": generated_at,
                    "judge": public["judge"],
                    **model_usage_audit,
                    "provider_reported_models": judge_provider_models,
                    "model_usage_audit": model_usage_audit,
                    "rate_limit_retry": rate_limit_retry,
                    "rate_limit_retry_file": retry_audit_path.name,
                    "input_files": public["trajectory_files"],
                    "output_file": output.name,
                    "usage": {
                        "agent_prompt_tokens": agent_prompt,
                        "agent_completion_tokens": agent_completion,
                        "judge_prompt_tokens": judge_usage["prompt_tokens"],
                        "judge_completion_tokens": judge_usage["completion_tokens"],
                        "retry_prompt_tokens": judge_usage["retry_prompt_tokens"],
                        "retry_completion_tokens": judge_usage[
                            "retry_completion_tokens"
                        ],
                        "responses_missing_usage": judge_usage[
                            "responses_missing_usage"
                        ],
                    },
                    "costs": {
                        "currency": "USD",
                        "model": resolved["judge_name"],
                        "agent_est_cost_usd": agent_cost,
                        "judge_est_cost_usd": judge_cost,
                        "retry_est_cost_usd": retry_cost,
                        "total_est_cost_usd": total_cost,
                    },
                    "secrets_recorded": False,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        persist_retry_audit(rate_limit_retry, "completed")
        print(f"Judge completed: {output}")
    except (ConfigError, OSError, KeyError, ValueError, RuntimeError) as exc:
        raise SystemExit(f"JUDGE ERROR: {exc}") from exc


if __name__ == "__main__":
    main()
