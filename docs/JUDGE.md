# Judge Integration

See [Judge Model Trade-offs](JUDGE_TRADEOFFS.md) for the cost decision,
self-judgment limitations, and required final-report disclosure.

## Upstream findings

The pinned upstream benchmark does **not** invoke its judge from
`src/custom/real_mcp/tool_level_test.py`. Step 3 only writes one trajectory per
task to `<output>/<model>/ANSWER/<task_idx>.json` (lines 561-613). Evaluation is
a separate operation implemented by
`src/custom/analysis/answer/evaluation.py`.

The upstream evaluator accepts `--model` at line 385. Its `evaluate_one()`
passes that model and `temperature=0.0` to `chat_with_openai()` at lines
124-142. The pinned `src/custom/utils/openai_llm.py` contains placeholder
module globals for the API key and base URL at lines 19-20; it does not read a
safe experiment-specific environment variable. Therefore the repository uses
the separate `scripts/run_judge.py` adapter. It imports the upstream prompt
builder but supplies the configured judge model, temperature, API key variable,
and base URL variable without editing the upstream checkout.

The judge prompt is assembled in
`src/custom/prompt/eval_error_prompt.py`, lines 11-177. The exact output fields
requested by that prompt are:

- `task_fulfillment`
- `grounding`
- `planning_and_efficiency`

Upstream evaluation files store repeated-run means at
`EVAL/<task_idx>.json -> eval_result.aggregate.task_fulfillment_mean` and
`eval_result.aggregate.planning_and_efficiency_mean`. This repository writes
the equivalent normalized fields to
`results/<strategy>/<version>/run-XX/judge-results.json -> tasks[].tf` and
`tasks[].pe`.

ECS is not produced by the per-run judge. Upstream computes it separately in
`src/custom/analysis/answer/evolutionary_volatility.py`, lines 225-266, as the
mean across tasks of `mean(version TF scores) - population_stdev(version TF
scores)`. `scripts/collect_results.py` applies that formula after matching a
task across Early, Middle, and Late and writes it to `details[].ecs` and
`aggregates[].mean_ecs`.

## Output files

A benchmark run directory contains:

- `run-metadata.json`: non-secret model, judge, harness, environment, and timing metadata;
- `<model>/ANSWER/<task_idx>.json`: upstream answer and trajectory;
- `judge-tasks/<task_idx>.json`: complete repeated judge responses;
- `judge-results.json`: normalized TF/PE scores consumed by result collection;
- `judge-metadata.json`: non-secret judge configuration, token usage, and cost audit data.

The judge metadata separates Agent usage, valid Judge repetitions, and malformed
Judge responses that triggered application-level retries. It records separate
estimated USD costs plus `total_est_cost_usd`. If any response omits usage, the
affected cost remains `null` rather than silently treating missing tokens as zero.
It also records `provider_reported_model` and every distinct model identifier
returned during judging so aliases can be audited after a provider-side change.
For quick audits, the metadata also exposes `configured_model`,
`provider_reported_model`, total Judge `prompt_tokens` and `completion_tokens`,
`attempt_count`, and `valid_score_count`; the detailed `usage` object continues
to separate valid scores from malformed-response retries.
It also records `rate_limit_retry`: every HTTP 429, `Retry-After` value,
exponential delay, actual retry, exhausted request, and total wait. SDK retries
are disabled so this transport behavior is not hidden from the experiment log.
The same state is checkpointed to `judge-rate-limit-retry.json` after every 429,
so exhausted retries remain available even when judging stops before completion.

## Command

```bash
.venv/bin/python scripts/run_judge.py \
  --version early \
  --harness-dir harness/no_update \
  --run-id 1
```

`JUDGE_API_KEY` and `JUDGE_BASE_URL` are loaded from `.env` or the process
environment. When blank and `judge.name == model.name`, they inherit `MODEL_*`.
The shared configuration pins `deepseek-chat` and uses DeepSeek's official
endpoint. Credential values are never written to metadata, results, or logs.

JSON mode is intentionally not forced because provider behavior can vary. If
JSON parsing repeatedly fails, retry with `--num-runs 3`; the existing parser
accepts plain or fenced JSON and records every failed attempt for audit.
