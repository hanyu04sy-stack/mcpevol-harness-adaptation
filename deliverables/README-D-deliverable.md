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

The local `.env` file and the `不上传/` holding directory are not deliverable
content. Move `不上传/` out of the project folder and remove `.env` before the
final submission. No compressed package is required for this handoff.

## What to commit to the GitHub repository

The repo already ignores `results/`, `logs/`, `external/`, `generated/`,
`.env` and `knowledge_graph/`. For the final GitHub push, commit:

- `reports/d/` — all analysis/audit documents, `final-comparison.{csv,json}`,
  `cost-analysis.{csv,json}`, `summary.{csv,json}` (copies of the unified
  summaries so the key numbers are available even though `results/` is not
  committed), and the paired-trajectory evidence under `reports/d/evidence/`:
  - `task2-under-update-{sp,fr,nu}.json` — Task 2 under-update case (SP
    stale-call failure vs FR success vs NU baseline, early run-01);
  - `task235-baseline-fr.json` — primary Full Rewrite baseline for retention
    task 235 (middle run-01), causally matched to the derived ablation harness;
  - `task235-baseline-nu.json` — supporting No Update baseline for the same task;
  - `task235-over-update-ablation.json` — the controlled over-update ablation
    trajectory (`exceeded=True`, 11 rounds / 33 calls, empty answer).
- `reports/d/ablation-provenance.md` documents the iterative ablation history,
  frozen harness hashes, and the raw `middle/middle` naming artifact.
- `docs/` (incl. `metric-definitions.md`), `scripts/`, `harness/` (the three
  strategies plus the `over_broad_rewrite/` ablation harness), `configs/`,
  `data/subsets/` (pilot-30 + ablation-over-broad), `tests/`, and this README.

The complete local folder retains `results/` as the raw trajectory record.
Because `results/` is ignored by Git, anyone submitting through GitHub must
preserve those raw results separately or intentionally change the upload plan.
