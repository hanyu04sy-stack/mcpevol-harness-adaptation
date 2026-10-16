# D deliverable contents

The project folder itself is the deliverable. Its D-specific content includes:

- all 27 experiment cells under `results/`, including trajectories, Judge
  task records, run metadata, and the unified summaries;
- all final D analysis and audit files under `reports/d/`, including the
  fairness audit, failure analysis, conclusion summary, cost analysis, final
  comparison, and final experiment audit;
- `docs/metric-definitions.md`;
- the final integrated report at `reports/final-report.md`; and
- this deliverable manifest.

Cost fields named `estimated_usd_*` are token-based estimates at the pinned
gpt-4o-mini reference prices, not provider invoices. Judge wall-clock time is
recorded for 26 of 27 cells; the missing `no_update/early/run-01` value remains
`unknown` and is excluded from runtime totals rather than inferred.

## Repository contents

The GitHub repository contains everything needed to read, audit, and reproduce
the D results:

- `reports/d/` — all analysis/audit documents, `final-comparison.{csv,json}`,
  `cost-analysis.{csv,json}`, `summary.{csv,json}` (copies of the unified
  summaries so the key numbers are available even though `results/` is not
  committed), and the paired-trajectory evidence under `reports/d/evidence/`:
  - `task2-under-update-{sp,fr,nu}.json` — Task 2 candidate under-update
    evidence (SP query-planning failure vs FR success vs NU baseline, early
    run-01); filenames are retained, but a changed-contract cause is unproven;
  - `task235-baseline-fr.json` — primary Full Rewrite baseline for retention
    task 235 (middle run-01), causally matched to the derived ablation harness;
  - `task235-baseline-nu.json` — supporting No Update baseline for the same task;
  - `task235-over-update-ablation.json` — the controlled over-update ablation
    trajectory (`exceeded=True`, 11 rounds / 33 calls, empty answer).
- `reports/d/ablation-provenance.md` documents the iterative ablation history,
  frozen harness hashes, and the raw `middle/middle` naming artifact.
- `docs/` (incl. `metric-definitions.md`), `scripts/`, `harness/` (the three
  strategies plus the `over_broad_rewrite/` ablation harness), `configs/`,
  `data/subsets/` (pilot-30 + ablation-over-broad), and `tests/`.

The raw trajectory archive `mcpevol-D-raw-results-2026-10-16.tar.gz`
is included with the repository submission so that the full
`results/` tree — including all raw trajectories, run metadata, and Judge
records — remains available to graders. The archive also contains the three
formal Early/Middle/Late 1MCP environment logs and the available matrix and
ablation console logs; per-cell benchmark and Judge
evidence is stored in JSON rather than as separate console-log files. The
committed summaries and audits under
`reports/d/` are the canonical source for every number in the final report.

Extract the archive in the repository root on macOS/Linux/WSL:

```bash
tar -xzf deliverables/mcpevol-D-raw-results-2026-10-16.tar.gz
python3 scripts/audit_experiment_results.py
python3 scripts/collect_results.py
```

The archive contains raw results and logs only. Current reports and protocol
documents are read directly from the repository, preventing conflicting
copies of the final report inside the archive. The collector excludes the
supplementary `ablation-over-broad/` result from formal aggregates.
