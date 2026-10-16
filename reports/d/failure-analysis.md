# Failure analysis: under-update and over-update (Member D)

Status: FINAL — completed from the paired trajectories of the formal 27-run
matrix (3 strategies x 3 versions x 3 runs, 5 Judge scores per task, 810
scored trajectories, `audit passed: true`). Every claim cites a task index,
run_id, and the exact evidence inside the trajectory.

## How failures are classified

`run_judge.py` writes `failure_category: "unknown"` for every task with
`TF < 6.0`. Classification below is done by D on **paired trajectories** — the
same task, the same run_id, and the same environment version across
no_update / full_rewrite / selective_patch.

- **under_update**: selective_patch missed a changed tool contract (renamed
  tool, changed parameter, changed description/rule) AND the trajectory shows
  the agent calling the stale contract AND another strategy (full_rewrite or
  the corrected patch) handled the same task.
- **over_update**: a retention task fails under an updated harness while the
  unchanged baseline succeeds, AND paired trajectories isolate unrelated or
  over-broad rewritten knowledge as the cause. A score or efficiency dip that
  remains successful without an isolated causal rewrite is documented
  separately and is not promoted to an over-update case.
- **other**: tool-call formatting, environment/path issues, or model
  randomness with no harness-difference explanation.
- **unknown**: no reliable attribution yet.

Explicitly excluded (per handoff): task 161 (patch identical to original
harness in Early, cannot prove over-update), original task 28 (file path /
environment), tasks 281/386 (extra `}` — tool-call formatting failure).

## Method

1. From `results/summary.csv`, list every cell with `tf < 6.0` under
   selective_patch for affected tasks, and every retention-task failure under
   full_rewrite / selective_patch.
2. For each candidate, read the paired trajectories
   (`results/{strategy}/{version}/run-XX/gpt-4o-mini/ANSWER/{idx}.json`).
3. Keep a case only when the trajectory directly shows the causal link
   (stale tool contract vs. rewritten unrelated knowledge).
4. If no natural case satisfies the criteria, run a small controlled
   re-run/ablation and describe it; never edit the benchmark label, and never
   label general low TF as under/over-update.

## Candidate under-update — Task 2 (causal attribution incomplete)

| Field | Value |
|---|---|
| Task idx | 2 |
| Status / change types | affected; affected_servers = `mcp-shrimp-task-manager`, `pantheon-mcp`; change_types = `description`, `parameter`, `tool` (per `data/subsets/pilot-30/manifest.json`) |
| Strategy failing | selective_patch (6 of 9 cells TF < 6; mean TF 5.56) |
| Strategy succeeding | full_rewrite (9 of 9 cells TF = 10.00, PE = 10.00) |
| no_update | 6 of 9 cells TF < 6 (mean 5.84) — stale knowledge fails too |
| Scores (TF / PE, success) | SP: early r1 3.4/2.8 F, r2 5.2/3.8 F, r3 4.0/2.2 F; middle r1 6.4/4.6 T, r2 5.0/2.2 F, r3 4.6/5.0 F; late r1 3.8/3.8 F, r2 8.8/8.0 T, r3 8.8/7.6 T. FR: all 9 cells 10.0/10.0 T |
| Change-coverage observation | `pantheon-mcp / search_agents` (and the whole `pantheon-mcp` + `mcp-shrimp-task-manager` servers). `harness/selective_patch/{middle,late}/patch-audit.json` contains 22 / 38 tool entries and **no entry for pantheon-mcp or mcp-shrimp-task-manager**, although the manifest marks both as affected |
| Evidence in trajectory | SP (`reports/d/evidence/task2-under-update-sp.json` — copied from `results/selective_patch/early/run-01/...`; other cells vary): `search_agents(keywords="data analysis, recommendation")` → `{"agents": [], "total": 0}`; then `"recommendation"`, `"AI recommendation"`, `"recommendation engine"` → all empty; agent finishes with an empty answer. FR (same run; `reports/d/evidence/task2-under-update-fr.json`): `search_agents(keywords="data analysis")` → returns `business-analyst`, `cfo-financial-analyzer`; `search_agents(keywords="recommendation")` → non-empty; `plan_task(...)` → detailed plan; answer contains the agent names and integration steps |
| Interpretation | Full Rewrite succeeds consistently while Selective Patch often fails, but causation by an environment change is not established. The exported search_agents description and input schema are unchanged across Early/Middle/Late, and the original harness has no keyword-specific rule. Task 2 also fails in Early. Missing a patch entry is therefore insufficient to prove under-update; this remains a query-planning failure and candidate adaptation gap. |

## Documented efficiency degradation — Task 260 (NOT classified as over-update)

Task 260 is a retention task asking for two time-zone conversions and whether
the proposed time works for all parties. No Update and Selective Patch both
solve it directly in all nine cells: two `convert_time` calls, no
`request_user_input` calls, six trajectory messages, and TF/PE = 10/10.

Full Rewrite retains task success but damages efficiency and answer quality.
In every one of its nine paired cells it calls `request_user_input` after the
two correct conversions, despite the system instruction not to ask follow-up
questions. The tool description strongly encourages proactive questioning;
the broad rewrite's rule to select tools from the current descriptions makes
that unrelated tool guidance salient. Full Rewrite invokes the tool between
1 and 12 times per trajectory, often receives empty input, and then either
repeats the call or qualifies an otherwise complete answer.

| Version / run | NU request calls | SP request calls | FR request calls | FR TF / PE |
|---|---:|---:|---:|---:|
| Early / 1 | 0 | 0 | 1 | 7.6 / 5.6 |
| Early / 2 | 0 | 0 | 12 | 8.4 / 3.0 |
| Early / 3 | 0 | 0 | 1 | 10.0 / 6.8 |
| Middle / 1 | 0 | 0 | 5 | 7.6 / 2.8 |
| Middle / 2 | 0 | 0 | 3 | 10.0 / 5.2 |
| Middle / 3 | 0 | 0 | 2 | 10.0 / 7.4 |
| Late / 1 | 0 | 0 | 10 | 8.0 / 3.2 |
| Late / 2 | 0 | 0 | 2 | 10.0 / 7.6 |
| Late / 3 | 0 | 0 | 8 | 6.4 / 2.8 |

Representative paired trajectory: in Late run 3, No Update calls
`convert_time` twice and gives the complete answer. Full Rewrite makes the
same conversions, then calls `request_user_input` eight times across four
duplicate pairs. Each returns `User replied with empty input`; the final
answer says availability cannot be confirmed and omits the explicit New York
time. Its score falls from NU 10.0/10.0 to FR 6.4/2.8.

**Why this is not classified as over-update.** The rubric requires a
retention task to fail or degrade under an updated harness with paired
trajectories showing that unrelated rewritten knowledge *caused* the damage.
Task 260 stays at TF >= 6 in all nine Full Rewrite cells, and the extra
`request_user_input` behaviour is consistent with the tool's own description
(which invites proactive questioning) rather than with an explicit rewrite
error; no single rewritten rule can be isolated as causally wrong. Per the
handoff requirement ("do not label a slight score dip as over-update"),
Task 260 is recorded as a **documented efficiency degradation**, not as an
over-update case.

The complete retention view is:

| Retention task | NU (9-cell mean TF) | SP (9-cell mean TF) | FR (9-cell mean TF) | Note |
|---|---|---|---|---|
| 235 | 10.00 | 10.00 | 10.00 | all pass |
| 249 | 10.00 | 10.00 | 10.00 | all pass |
| 260 | 10.00 | 10.00 | 8.67 | documented FR efficiency degradation; not classified as over-update |
| 291 | 10.00 | 10.00 | 10.00 | all pass |
| 448 | 10.00 | 10.00 | 10.00 | all pass |
| 161 | 4.27 | 4.02 | 5.62 | all strategy means are below six; individual runs can succeed; cause remains unresolved |

Across 54 retention cells per strategy (6 tasks x 3 runs x 3 versions), Task
260 is the only systematic update-related degradation. The paired evidence is
stronger than a single score dip: the extra confirmation behavior occurs in
9/9 Full Rewrite trajectories and 0/18 No Update or Selective Patch
trajectories. No update strategy causes a retention task to cross below the
TF 6 success threshold.

## Controlled over-update ablation (supplementary case — NOT part of the formal statistics)

Because no natural retention failure satisfies the over-update criteria
above, D ran a small controlled ablation on retention task 235 (middle
version, single-task subset `data/subsets/ablation-over-broad/`, config
`configs/ablation-over-broad/experiment.json`, harness
`harness/over_broad_rewrite/middle/`). The harness is a deliberate
"over-broad rewrite" of an otherwise-working baseline; it is labelled as an
ablation, lives under `results/ablation-over-broad/` outside the strategy
directories, and is excluded from `results/summary.csv` and all formal
statistics.

In the formal matrix all three strategies solve task 235 perfectly (9/9
cells, TF 10.00, 3 tool calls + `[FINISH]`). The ablation injects
increasingly invasive "updated knowledge" into the same middle-version
harness and measures whether the agent's behaviour degrades:

| Attempt | Injected over-broad rewrite | Result |
|---|---|---|
| v1 | Chart tool renamed (`generate_district_map` → `_v2`), staging-write prerequisite | TF 10.0 — model ignored the injected contract, called the real tool, succeeded |
| v2 | v1 + system-prompt "fail → `[FINISH]`, never fall back" | TF 10.0 — injection ignored |
| v3 | "Chart server under maintenance; do not call chart tools" | TF 10.0 — model rejected the environment-status claim |
| v4 | Output-protocol rewrite: final answers must be pure JSON with no `[FINISH]` | **stop=False, exceeded=True, 11 tool-call rounds / 33 tool calls (vs 1 round / 3 calls normally), empty answer** — the agent never terminated normally |

v4 evidence is paired with the evaluated Full Rewrite baseline from which the
ablation harness was derived. Full Rewrite
(`reports/d/evidence/task235-baseline-fr.json`, copied from
`results/full_rewrite/middle/run-01/...`) calls the three chart tools once each
in one tool-call round and finishes with `[FINISH]` plus a complete answer. The
No Update trajectory is retained as supporting evidence, but it is not the
primary causal baseline. Under the
injected over-broad rewrite
(`reports/d/evidence/task235-over-update-ablation.json`, copied from
`results/ablation-over-broad/middle/middle/run-01/...`), the model obeys the
rewritten OUTPUT FORMAT — the one injected rule that does
not contradict the live tool list — and therefore never emits the
termination marker the runner requires. The runner keeps asking; the agent
repeats one three-call chart sequence across 11 tool-call rounds (33 calls), exhausts the step budget
(`exceeded=True`), and returns an empty answer. (The tool-call-based Judge
still scores 10.0 because every chart call succeeded; the damage is the
broken termination, not the individual tool calls.)

Interpretation. v1–v3 show that tool-contract-level over-rewriting is
rejected in these exploratory attempts. This does not explain the absence of
natural over-update across the entire matrix. v4 shows
the one mechanism that does degrade a retention task: rewriting an unrelated
output protocol breaks normal task termination. This case is a
**supplementary controlled ablation** (complete trajectory reproduced under
`reports/d/evidence/task235-over-update-ablation.json`, original under
`results/ablation-over-broad/`), explicitly not part of the formal
experiment statistics; v1–v3 runs were overwritten by the v4 run in the
shared ablation output directory, and their scores are recorded in the D
work logs (`wsl-ablation4/5/7-stdout.log` on the Windows host). Frozen-file,
iteration, and raw path-naming details are documented in
`reports/d/ablation-provenance.md`.

## Summary table

| Category | Task idx | Strategy failing | Version | Run | Evidence status |
|---|---|---|---|---|---|
| under_update candidate | 2 | selective_patch | early/middle/late | all 3 runs | query-planning contrast observed; changed-contract cause unproven |
| over_update (controlled ablation, supplementary) | 235 | over_broad_rewrite (ablation harness) | middle | run-01 | confirmed: `exceeded=True`, 11 rounds / 33 calls vs 1 round / 3 calls, empty answer |
| efficiency degradation (NOT over-update) | 260 | full_rewrite | early/middle/late | all 3 runs | documented (1–12 redundant confirmation calls vs 0 for NU/SP) |

## Notes

- The 5 Judge scores per task reduce scoring noise; the three runs are the
  independent repeats. A single low TF cell is not a failure case by itself.
- Shared failures do not by themselves identify an environment cause; they
  also do not establish that an update caused the failure.
- The under-update case (task 2) is the only affected task where FR is
  consistently perfect while SP is mostly failing; task 434 shows a similar
  shape (FR 10.0 vs SP 5.2 mean) and is listed as a secondary candidate in
  collected task rows. The comparison-analysis JSON contains aggregate views,
  not a per-task candidate list.
