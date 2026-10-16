# D — Final conclusion summary

Status: FINAL. Full 27-run matrix (3 strategies x 3 versions x 3 runs, 5 Judge
scores per task) on the fixed 30-task pilot (`pilot-30`, commit
`888c779a0fe735f612ca62bdd1fdd7c9e6bf8701`, model/Judge gpt-4o-mini,
temperature 0.0). Audit `passed: true`; 810 scored trajectories; 4,050 Judge
scores. All numbers below are from `reports/d/final-comparison.{csv,json}`
(aggregates) and `reports/d/comparison-analysis.json` (paired differences).

## One-paragraph headline

Under this specific protocol and fixed subset (same 30 tasks, same model and
temperature, same runner, same Judge with 5 scores per task, 3 independent
runs), **Full Rewrite performed best**: mean TF 8.75 ± 2.41 and an 81.5%
success rate, ahead of No Update (8.25 ± 2.88, 75.2%) and Selective Patch
(8.21 ± 2.84, 75.2%). On the 24 environment-affected tasks, Full Rewrite
recovers 79.2% vs. 70.8–76.4% for the other two. Selective Patch shows **no
reliable advantage over No Update** (affected-task paired
delta +0.10, 95% bootstrap CI −0.14…+0.35, contains 0), and it is
**worse than Full Rewrite under the paired bootstrap analysis** (paired delta
−0.51, CI −0.72…−0.33, excludes 0). Retention is broadly preserved: 5 of 6
retention tasks remain successful under all strategies, and 4 of 6 stay at
full score throughout. Task 260 has a mild Full Rewrite dip to 8.67 but still
passes; task 161 has a below-six mean under each strategy and remains in
all aggregate statistics. Task 2 is a **candidate under-update case**: Selective Patch's patch list
missed the affected `pantheon-mcp` / `search_agents` contract that Full
Rewrite handled perfectly in all 9 cells. No natural over-update case was
observed in the formal matrix. Task 235 is a controlled over-update ablation;
it showed that tool-contract
over-rewriting was rejected in three exploratory attempts, while an
output-protocol over-rewrite broke task termination (`exceeded=True`, 11
rounds, empty answer) — reported as a supplementary case excluded from the
formal statistics.
Estimated API cost: **$5.78** (≈33.7M tokens), calculated from recorded token
usage at the pinned gpt-4o-mini reference rates. This is not an API invoice;
the provider dashboard is the source of truth for actual spend.

## Strategy x version means (mean +/- SD across three run means)

| Strategy | Version | TF | PE | Success |
|---|---|---|---|---|
| No Update | early | 8.22 ± 0.20 | 8.10 ± 0.15 | — |
| No Update | middle | 8.24 ± 0.16 | 7.62 ± 0.29 | — |
| No Update | late | 8.28 ± 0.17 | 7.76 ± 0.12 | — |
| Full Rewrite | early | 8.74 ± 0.09 | 7.88 ± 0.15 | — |
| Full Rewrite | middle | 8.79 ± 0.04 | 7.96 ± 0.15 | — |
| Full Rewrite | late | 8.73 ± 0.06 | 7.91 ± 0.06 | — |
| Selective Patch | early | 8.24 ± 0.14 | 7.88 ± 0.07 | — |
| Selective Patch | middle | 8.03 ± 0.03 | 7.43 ± 0.09 | — |
| Selective Patch | late | 8.36 ± 0.06 | 7.79 ± 0.14 | — |

Strategy-level (pooled, n=270 each): Full Rewrite TF 8.75 ± 2.41, success
81.5%; No Update 8.25 ± 2.88, 75.2%; Selective Patch 8.21 ± 2.84, 75.2%.
ECS (Evolutionary Competency Score, 9-cell means): Full Rewrite 8.63 vs
No Update 7.98 vs Selective Patch 7.82 — Full Rewrite is also the most stable
across early/middle/late.

## Recovery and retention (paired, same task / same run)

| Pair | Affected tasks (n=216) | Retention tasks (n=54) |
|---|---|---|
| Selective Patch − No Update | +0.10 (CI −0.14…+0.35) | −0.08 (CI −0.20…0.00) |
| Selective Patch − Full Rewrite | **−0.51 (CI −0.72…−0.33)** | −0.01 (CI −0.33…+0.33) |

Interpretation: updating the harness helps vs. no update only weakly and not
reliably (Selective Patch); the generic Full Rewrite produces the main
recovery gain. Its aggregate retention remains high, but Task 260 shows that
broad rewriting can still introduce a systematic efficiency regression.

## Failure analysis (paired trajectories)

- **Candidate under-update — Task 2.** `pantheon-mcp/search_agents` is
  marked affected (description/parameter/tool changes) in the manifest, yet
  the Selective Patch patch list (22 / 38 entries for middle/late) contains no
  entry for it. Selective Patch repeatedly calls
  `search_agents(keywords="data analysis, recommendation")` (stale comma-
  combined habit) and gets empty results in 6 of 9 cells (TF 3.4–5.2), while
  Full Rewrite, told to follow the current tools/list, calls single keywords
  and returns the correct agents in all 9 cells (TF 10.0). No Update fails
  like Selective Patch (6 of 9). However, the exported contract is identical
  across versions and failures also occur in Early. These observations show a
  query-planning gap; a changed-contract cause remains unproven.
- **Controlled over-update ablation — Task 235 (supplementary case, not in the
  formal statistics).** No natural over-update case was observed in the formal
  matrix under the stated criteria (see `reports/d/failure-analysis.md`), so D ran a small controlled
  ablation on retention task 235 (middle, `harness/over_broad_rewrite/middle/`,
  `results/ablation-over-broad/`, trajectory reproduced in
  `reports/d/evidence/task235-over-update-ablation.json`). Tool-contract-level
  injections (renamed
  tools, staged-write prerequisites, "server under maintenance") were all
  ignored by the model (TF 10.0) — the model treats the live tool list as
  authoritative in those attempts. This does not explain the absence of a
  natural over-update case across the entire matrix. The one injection that took effect was an output-protocol
  rewrite (JSON-only final answers, no `[FINISH]`): the agent then never
  emitted the termination marker, repeated a three-call chart sequence for 11
  tool-call rounds (33 calls, versus 1 round / 3 calls in the Full Rewrite
  baseline), and terminated only via the step budget (`exceeded=True`)
  with an empty answer. Judge (tool-call-based) still scored 10.0, so this is
  reported as a supplementary ablation with its complete trajectory kept,
  explicitly excluded from the formal comparison.
- **Efficiency degradation — Task 260 (documented, NOT over-update).** No
  Update and Selective Patch each use exactly two `convert_time` calls and
  score 10/10 in all nine cells. Full Rewrite makes the same conversions but
  then invokes `request_user_input` 1-12 times in every cell, producing
  empty-input loops and reducing its nine-cell mean to TF 8.67. Late run 3
  falls from NU 10.0/10.0 to FR 6.4/2.8 after eight redundant confirmation
  calls. Per the handoff rule ("do not label a slight score dip as
  over-update") this is recorded as an efficiency degradation, not an
  over-update case: no single rewritten rule can be isolated as causally wrong
  and every FR Task 260 cell remains at TF >= 6.

## Cost and runtime

27 cells, 33.74M tokens total (benchmark 13.37M, Judge 20.37M);
Estimated **$5.78** total (benchmark $2.26, Judge $3.51), using the pinned
gpt-4o-mini reference prices ($0.15/M input, $0.60/M output). Benchmark wall
time ≈ 5.3h. Recorded Judge wall time is **at least 3.65h across 26 of 27
cells**; `no_update/early/run-01` did not record a Judge wall-clock value, so
no unsupported 27-cell runtime total is claimed. Add 1MCP startup time per
environment version. All per-cell numbers and coverage notes:
`reports/d/cost-analysis.csv`. (The earlier canary-23 cell was archived; the
reported totals cover the retained formal-cell metadata. Historical overwritten
attempts have no complete separate usage ledger and are not claimed as total spend.)

## Limitations

1. n = 3 runs is the course preference; paired differences + bootstrap CIs are
   used instead of significance claims.
2. Fixed 30-task subset is course-allowable but not the original full
   benchmark; the 7 dropped-by-stock-runner tasks are documented in
   `reports/d/fairness-audit.md` §2 (in-memory override, upstream untouched).
3. Judge is gpt-4o-mini (same model as the agent), per the pinned protocol.
4. Runs executed on WSL Ubuntu 26.04 (Linux); platform effects, if any, apply
   equally to all 27 cells.
5. The under-update attribution rests on one task (Task 2); Task 434 shows
   the same shape (FR 10.0 vs SP 5.2) and is listed as the secondary candidate
   in the raw collected task rows; it is not causally classified in the aggregate JSON.
6. The evaluated Full Rewrite is one version-invariant generic rewrite that
   defers to the live `tools/list`. It was materialized under all three version
   directories but was not synthesized into version-specific prose from the
   schema snapshots.
