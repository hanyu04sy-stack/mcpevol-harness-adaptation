# Metric definitions (Member D)

Status: FINAL — definitions are implemented exactly as described below in
`scripts/collect_results.py`, `scripts/analyze_comparison.py`, and
`scripts/build_cost_analysis.py`, and the numeric results of the formal 27-run
matrix (audit `passed: true`, 2026-10-15T18:37:09Z) are in
`reports/d/comparison-analysis.json`, `reports/d/cost-analysis.csv`, and
`results/summary.csv/json`.

Scope: the fixed 30-task pilot (`configs/experiment.json`, SHA-256
`9e7ab1d858ae8d8df2808e46d804d94baf13a3e94ca6c57755d246c3a30f4d92`),
three strategies (no_update, full_rewrite, selective_patch), three environment
versions (early, middle, late), three independent runs (run_id 1-3), five
successful Judge scores per task, model gpt-4o-mini, temperature 0.0.

## 1. Per-task scores from the Judge

Each task trajectory is scored by the pinned upstream Judge prompt
(`custom.prompt.eval_error_prompt.build_mcp_bench_judge_prompt`), five times.
The three dimension orders are shuffled deterministically (seed `6203 ^ idx`),
and up to `num_runs * 3` attempts are made to obtain five valid 1-10 scores
(`scripts/run_judge.py`).

| Field | Meaning | Computation |
|---|---|---|
| TF (task_fulfillment) | How completely the agent fulfilled the requested task | Mean of the 5 valid `task_fulfillment` scores, each 1-10 |
| PE (planning_and_efficiency) | How efficiently the agent planned and used tool calls | Mean of the 5 valid `planning_and_efficiency` scores, each 1-10 |
| Grounding | Whether claims/actions were grounded in tool results | Mean of the 5 valid `grounding` scores (recorded, not used as a headline metric) |
| Success | Task considered recovered/completed | `TF >= 6.0` (default threshold in `scripts/collect_results.py`, overridable) |

Invalid or non-JSON Judge responses are billed before a retry and are counted
in `metered_responses`; they do not contribute to the means
(`scripts/run_judge.py`, `judge-metadata.json`).

## 2. ECS (Environment Change Stability)

Computed per (strategy, run_id, task_idx) in `scripts/collect_results.py`:

```
ECS = mean(TF over early, middle, late) - population_sd(TF over early, middle, late)
```

- Uses the three environment versions as the "across-environment" spread.
- Only rows with all three versions present are included.
- `mean_ecs` in the aggregate JSON is the mean of per-task ECS over the 30 tasks.

Rationale: a strategy is "stable" if it keeps TF high on average AND does not
lose performance when the environment changes.

## 3. Recovery

Two complementary views are reported.

### 3a. Recovery rate (existing aggregate, `collect_results.py`)

```
recovery_rate = (tasks in the affected subset with success) / (all affected tasks)
```

where `success = TF >= 6.0`, and the affected subset comes from
`data/subsets/pilot-30/manifest.json` (`status == "affected"`, 24 tasks).

Note: this answers "how many affected tasks were handled" per cell, not "how
much the update improved over the baseline". The gain view below is the
additional table required by the handoff.

### 3b. Recovery gain (paired-difference table, computed after collection)

For affected tasks only, on the same (task, run_id) pairing:

```
Recovery gain (selective_patch - no_update)     = mean(SP.TF - NU.TF)
Recovery gain (selective_patch - full_rewrite)  = mean(SP.TF - FR.TF)
```

Reported as mean over affected tasks, and per affected task in the detail CSV
(`results/summary.csv`, columns `strategy/version/run_id/task_idx/tf`).

## 4. Retention

### 4a. Retention rate (existing aggregate, `collect_results.py`)

```
retention_rate = (retention tasks with success) / (all retention tasks)
```

with `status == "retention"` (6 tasks).

### 4b. Retention loss (paired-difference table, computed after collection)

For retention tasks only:

```
Retention loss = mean(update_strategy.TF - no_update.TF)   (same task, same run)
```

A negative value means the update degraded an unchanged task. This must be
separated from unrelated model noise; a loss is only attributed to over-update
when the paired trajectory shows changed harness knowledge caused the failure
(see `failure-analysis.md`).

## 5. Aggregates and cost fields

`results/summary.json` `aggregates` (per strategy x version):

| Field | Meaning |
|---|---|
| mean_tf / mean_pe / mean_ecs | Means over all cells of that group (3 runs x 30 tasks) |
| recovery_rate / retention_rate | Section 3a / 4a |
| total_cost_tokens | Sum of benchmark (model) prompt+completion tokens over the 3 runs of the cell |
| total_judge_tokens | Sum of Judge prompt+completion tokens over the 3 runs of the cell |
| total_all_tokens | benchmark + Judge combined |
| n_runs / n_tasks | Run and task counts (completeness check) |

Token fields are `null`/absent only when a run did not record usage; the
protocol records provider-reported usage for every paid phase, so a `null`
after the formal matrix indicates a real gap, not a zero.

`results/summary.csv` detail rows additionally carry
`prompt_tokens`, `completion_tokens`, `judge_prompt_tokens`,
`judge_completion_tokens`, `all_tokens`, `wall_clock_s`, `task_status`,
`model`, `judge`, and `mcp_status_at_start` per task row.

## 6. Failure categories (under-update / over-update)

The Judge does not classify failures. `failure_category` is written as
`unknown` for every TF < 6 cell by `run_judge.py`. Classification is a
human-in-the-loop step on paired trajectories (same task, same run_id across
the three strategies):

| Category | Evidence required |
|---|---|
| under_update | Selective Patch missed a changed tool contract (renamed tool, changed parameter/description/rule) AND the trajectory shows the agent called the stale contract, AND another strategy (Full Rewrite or the corrected patch) handled the same task. |
| over_update | A retention task fails under an updated harness while No Update succeeds, AND paired trajectories isolate unrelated or over-broad rewritten knowledge as the cause. A successful score/efficiency dip without an isolated causal rewrite is documented separately, not promoted to over-update. |
| other | Tool-call formatting, environment/path issues, model randomness with no harness-difference explanation. |
| unknown | No evidence yet. |

Do not label general low TF or retention dips as under/over-update without the
paired trajectory evidence.

## 7. Update cost (harness generation, separate table)

- Selective Patch: 0 / 22 / 38 tool entries updated for Early/Middle/Late
  (`harness/selective_patch/*/patch-audit.json`); generation is local, no model
  API cost; generation time recorded in the patch-audit JSON.
- Full Rewrite: one version-invariant generic rewrite is materialized by
  `scripts/build_full_rewrite_versions.py` under early/middle/late. It removes
  stale tool-specific rules and defers to the live `tools/list`; it is not
  schema-generated prose. Generation is local and its metadata is recorded in
  `harness/full_rewrite/*/manifest.json`.
- Prompt/completion tokens, benchmark and Judge wall time, and API cost (USD)
  are recorded per cell in `run-metadata.json` / `judge-metadata.json` and
  aggregated in `reports/d/cost-analysis.csv`.

## 8. Statistical reporting rules

- Three runs are independent repeats; five Judge runs per task are scoring
  noise control, not statistical repeats.
- Report `mean +/- standard deviation` across the three runs and, where useful,
  95% bootstrap confidence intervals for paired differences (Selective Patch
  minus No Update / Full Rewrite).
- n = 3 repeats: do not overclaim significance; prefer paired per-task deltas
  and effect sizes over p-values.
