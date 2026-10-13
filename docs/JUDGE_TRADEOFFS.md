# Judge Model Trade-offs

## Decision

- Agent model: `deepseek-flash` (currently DeepSeek-V4.1-Flash).
- Judge model: `deepseek-flash`, the same model as the agent.
- Rationale: cost. The planned 30 tasks × 3 versions × 3 runs × 5 judge
  repeats produces 1,350 judge calls, so judge cost materially affects the
  experiment budget.

## Known limitations

1. **Self-judgment bias:** the judge may be lenient toward its own reasoning
   style because agent and judge use the same model.
2. **JSON adherence:** `deepseek-flash` may produce malformed JSON. The judge
   retries up to `num_runs * 3` attempts and averages five successful repeats.
3. **Score-scale drift:** 1–10 scores may be systematically compressed relative
   to another judge. Cross-model comparisons are invalid; compare strategies
   only under the same pinned judge.

## Mitigations already in code

- `scripts/run_judge.py` defaults to five successful scores per task and uses
  `statistics.fmean` for each aggregate mean.
- `extract_json()` accepts fenced JSON and rejects malformed or out-of-range
  scores, allowing the retry loop to continue.
- Temperature is pinned to `0.0`.

## Required statement for the final report (Member D)

> Due to compute budget, both the agent and the judge use deepseek-flash at
> temperature 0.0. Each task is judged 5 times and the mean score is reported.
> We do not claim absolute TF/PE values are comparable to gpt-4o-judged
> benchmarks; all comparisons are between strategies under the same judge.
