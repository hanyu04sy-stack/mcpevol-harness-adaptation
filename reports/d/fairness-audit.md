# Fairness audit (Member D)

Status: FINAL — the formal 27-run matrix completed on 2026-10-16 and
`reports/d/final-experiment-audit.json` reports `passed: true` (generated
2026-10-15T23:34:00.099530Z).

## 1. Protocol pins

| Pin | Value | Evidence |
|---|---|---|
| Benchmark repository | https://github.com/Octobrist/MCPEvol-Bench.git | `configs/experiment.json` |
| Benchmark commit | `888c779a0fe735f612ca62bdd1fdd7c9e6bf8701` | `run-metadata.json` per cell |
| Runner | `src/custom/real_mcp/tool_level_test.py`, step 3 | `configs/experiment.json` |
| Task set | pilot-30 (30 tasks), SHA-256 `9e7ab1d858ae8d8df2808e46d804d94baf13a3e94ca6c57755d246c3a30f4d92` | `configs/experiment.json`; `reports/pilot-30-coverage.json` |
| Affected / retention | 24 affected + 6 retention | `data/subsets/pilot-30/manifest.json` |
| Runnability matrix | SHA-256 `7fd33bc19910214d89d77d928caa567c5cf9519530235d8ecc180595a0ad1a25` | `reports/pilot-30-runnability-matrix.json` |
| Model (benchmark + Judge) | gpt-4o-mini, temperature 0.0, max_completion_tokens 4096 | `configs/experiment.json`; per-cell metadata |
| Judge runs | 5 successful scores per task (up to 15 attempts) | `judge-results.json`; `judge-metadata.json` |
| Runs per cell | 3 independent (run_id 1, 2, 3) | `configs/experiment.json`; matrix plan |
| 1MCP endpoints | early `http://127.0.0.1:3051/mcp`, middle `:3052`, late `:3053` | `configs/experiment.json` |
| MCP servers | 26 servers / 304 tools (early); versions differ by tool changes | `generated/1mcp/{early,middle,late}.json` |
| Harness hashes | per-cell `run-metadata.json` `harness_files` | per-cell evidence |

## 2. Fixed-subset declaration (must be reported to the team)

The stock upstream runner applies an internal filter (`src/custom/utils/test_utils.py`
`clean_all_test_cases` reading `src/custom/data/test_cases/chosen_idx.json`, the
official 201-sample index). The intersection of pilot-30 with that official index
is exactly 23 tasks; 7 pilot tasks (idx 37, 162, 177, 251, 327, 384, 422) are
marked runnable in the validated runnability matrix but would be dropped by the
stock runner.

Resolution (C-approved, implemented in `scripts/run_benchmark.py`):
- The project runner replaces `clean_all_test_cases` **in memory only**, after
  changing directory into the upstream checkout, before the upstream `sys.argv`
  is injected. No upstream file is modified; `git status --porcelain` on the
  upstream checkout stays empty after every phase (`verify_untouched.py`).
- Effect: the same fixed 30 tasks are evaluated for all three strategies, all
  three versions, and all three runs, under the same runner, model, Judge, and
  protocol. The only deliberate difference between cells is the harness.
- This is a fixed, documented evaluation subset (course-allowable), not a
  post-hoc selection from results, and it removes the selection-bias concern of
  the earlier 23-task comparison subset.

## 3. Evidence requirements per cell (strategy x version x run)

Each of the 27 cells must contain:

- `run-metadata.json` — status, task_count=30, model/temperature, benchmark
  commit, harness files + hashes, MCP endpoints + server status, usage tokens,
  wall_clock_seconds
- 30 trajectory files (`gpt-4o-mini/ANSWER/*.json`)
- `judge-results.json` — 30 tasks, 5 successful runs each, TF/PE/grounding,
  per-task judge tokens
- `judge-metadata.json` — judge model, input file list, totals, metered responses
- benchmark trajectories, Judge task records, and their corresponding run and
  Judge metadata. Environment logs are supplementary and are not required
  for a cell to pass the metadata audit.

## 4. Verification checklist (filled post-matrix)

| Check | Method | Result |
|---|---|---|
| 27 run dirs exist | `audit_experiment_results.py` | PASS — completed_runs = 27 (expected 27) |
| 810 trajectories (30 x 27) | audit + `collect_results.py` counts | PASS — scored_tasks = 810 (expected 810) |
| 4050 successful Judge scores (30 x 27 x 5) | judge-results distribution | PASS — judge_runs_per_task = 5; every task has 5 successful runs |
| task_count == 30 in every run-metadata | audit | PASS — task_count = 30 |
| commit hash matches everywhere | audit | PASS — `888c779a0fe735f612ca62bdd1fdd7c9e6bf8701` in every run-metadata |
| task SHA-256 matches everywhere | audit | PASS — `9e7ab1d858ae8d8df2808e46d804d94baf13a3e94ca6c57755d246c3a30f4d92` |
| model == gpt-4o-mini, temperature == 0.0 everywhere | audit | PASS |
| Judge == gpt-4o-mini, 5 runs requested everywhere | audit | PASS — judge_runs_per_task = 5 |
| MCP addresses per version match config | audit | PASS — early :3051, middle :3052, late :3053 |
| harness file hashes consistent | audit | PASS — harness_files recorded per cell (see run-metadata) |
| upstream checkout clean after every phase | `verify_untouched.py` | PASS — no `git status` residue at any phase boundary |
| usage tokens non-null in every cell | audit + `build_cost_analysis.py` | PASS — all 27 cells have benchmark + judge token totals (see `reports/d/cost-analysis.csv`) |
| issues | audit | PASS — `issues: []`, `secrets_recorded: false` |

Audit summary (verbatim from `reports/d/final-experiment-audit.json`):
`passed: true`, 27 runs, 810 scored tasks, 5 Judge runs per task, no issues,
no secrets recorded. The matrix is therefore protocol-complete: the only
deliberate difference between the 27 cells is the harness strategy
(no_update / full_rewrite / selective_patch × early / middle / late).

## 5. Known limitations (disclosed, not hidden)

- Full Rewrite is a version-invariant generic replacement that defers to each
  live `tools/list`. Identical prompt/rule text is materialized under the three
  version directories; it is not schema-generated version-specific prose.
- Single environment (WSL Ubuntu 26.04) for all cells; formally supported
  platforms are macOS/Linux — WSL is Linux.
- n = 3 repeats follows the course preference. Paired
  differences are preferred over significance claims.
- Judge scores are model-based (gpt-4o-mini), same model as the agent, per the
  project's pinned protocol.
- The stock upstream 23-task filter is bypassed via an in-memory override,
  declared above.

## 6. Secrets

`.env` (MODEL_API_KEY / JUDGE fallback) is read only inside WSL; key values are
never written to logs, metadata, reports, or commits. `secrets_recorded: false`
in audit and metadata files.
