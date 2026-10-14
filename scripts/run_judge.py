#!/usr/bin/env python3
"""Run the pinned MCPEvol judge prompt as a separate, auditable phase."""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiment_config import ConfigError, VERSIONS, load_env_file, load_experiment
from run_benchmark import load_harness, provider_model_id, resolve_run_output


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
) -> dict[str, Any]:
    rng = random.Random(seed)
    attempts: list[dict[str, Any]] = []
    scores: list[dict[str, Any]] = []
    max_attempts = num_runs * 3
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
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        raw = response.choices[0].message.content or ""
        try:
            parsed = extract_json(raw)
            scores.append(parsed)
            attempts.append({"dimension_order": order, "result": parsed})
        except (json.JSONDecodeError, ValueError) as exc:
            attempts.append({"dimension_order": order, "error": str(exc), "raw": raw})
    if not scores:
        raise RuntimeError(f"judge returned no valid score after {max_attempts} attempts")
    return {
        "runs": attempts,
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
        key = os.environ.get(str(resolved["judge_api_key_env"]), "").strip()
        base_url = os.environ.get(str(resolved["judge_base_url_env"]), "").strip() or None
        if not key:
            raise ConfigError(f"missing {resolved['judge_api_key_env']}")

        from openai import OpenAI

        client = OpenAI(api_key=key, base_url=base_url)
        prompt_builder = load_prompt_builder(Path(resolved["benchmark_root"]))
        task_dir = run_dir / "judge-tasks"
        task_dir.mkdir(parents=True, exist_ok=True)
        normalized: list[dict[str, Any]] = []
        for source in trajectories:
            case = json.loads(source.read_text(encoding="utf-8"))
            idx = int(case["idx"])
            evaluated = judge_case(
                case,
                client=client,
                prompt_builder=prompt_builder,
                model=provider_model_id(str(resolved["judge_name"]), base_url),
                temperature=float(resolved["judge_temperature"]),
                max_tokens=int(resolved["max_completion_tokens"]),
                num_runs=max(1, args.num_runs),
                seed=6203 ^ idx,
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
        metadata.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "recorded_at": generated_at,
                    "judge": public["judge"],
                    "input_files": public["trajectory_files"],
                    "output_file": output.name,
                    "secrets_recorded": False,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Judge completed: {output}")
    except (ConfigError, OSError, KeyError, ValueError, RuntimeError) as exc:
        raise SystemExit(f"JUDGE ERROR: {exc}") from exc


if __name__ == "__main__":
    main()
