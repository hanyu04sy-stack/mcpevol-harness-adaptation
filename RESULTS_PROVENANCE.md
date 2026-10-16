# Results Provenance

This document distinguishes the historical intermediate results from the final
formal evaluation. It defines which dataset, repetitions, and artifacts may be
used for the project's reported conclusions.

## Result sets

| Contributor and stage | Scope | Role in the repository |
|---|---|---|
| Member B baseline | 23 tasks × 1 run for each No Update and Full Rewrite environment cell | Historical intermediate results |
| Member C Selective Patch | 23 tasks × 1 run for each Selective Patch environment cell | Historical intermediate results |
| Member D formal matrix | 30 fixed tasks × 3 independent runs for every strategy/environment cell | **Sole source of formal statistics and final conclusions** |

The Member B baseline is retained in
`reports/baseline-run20-summary.{csv,json}`. The Member C results are retained
under `reports/selective-patch/`. These artifacts document the development and
handoff history, but they must not be combined with or substituted for the
formal matrix when quoting final metrics.

## Formal evaluation boundary

The formal evaluation consists of:

- 3 strategies: No Update, Full Rewrite, and Selective Patch;
- 3 environment versions: Early, Middle, and Late;
- 3 independent benchmark runs per strategy/version cell;
- 30 fixed tasks per run;
- 27 total experiment cells and 810 total trajectories; and
- 5 successful Judge evaluations per trajectory, for 4,050 Judge scores.

All headline metrics, confidence intervals, strategy rankings, cost estimates,
and final conclusions must be derived only from the Member D formal matrix.
The canonical formal artifacts are:

- `reports/d/summary.{csv,json}`;
- `reports/d/final-comparison.{csv,json}`;
- `reports/d/comparison-analysis.json`;
- `reports/d/final-experiment-audit.json`; and
- `reports/final-report.md`.

The complete raw formal result tree is packaged in
`deliverables/mcpevol-D-raw-results-2026-10-16.tar.gz`.

## Why the task counts differ

The historical B and C result sets contain the 23 task IDs that survived the
upstream benchmark's stock 201-sample filter. Seven tasks from the predeclared
30-task pilot set were therefore absent from those intermediate runs.

For the final matrix, the project runner applies the documented in-memory
override described in `reports/d/fairness-audit.md`. This preserves the pinned
upstream checkout while evaluating the same fixed 30 tasks across every
strategy, version, and repetition.

Accordingly, the 23-task artifacts are useful for provenance and development
history only. They are not part of the final statistical comparison.
