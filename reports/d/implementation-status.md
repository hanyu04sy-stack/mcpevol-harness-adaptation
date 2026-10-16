# Member D implementation status

Status: FINAL  
Updated: 2026-10-16

## Implementation and completed experiments

- Added a resumable 27-run experiment matrix for three strategies, three
  versions, and run IDs 1-3.
- Pinned five successful Judge evaluations per task.
- Added exact task-set checks before a benchmark or Judge phase is skipped.
- Added provider-reported benchmark token accumulation without editing the
  pinned upstream benchmark.
- Added per-task and batch Judge token accumulation, including billed invalid
  responses before a retry.
- Extended result collection with separate benchmark, Judge, and combined
  token totals.
- Added a final machine-readable completeness and fairness audit.
- Added unit tests and the Member D execution guide.
- Updated the formal D protocol to use the validated 30-task pilot set: 24
  affected/recovery tasks and six retention tasks.
- Generated `experiment-matrix-plan.json`: 810 expected trajectories and 4,050
  expected Judge scores.
- Completed all 27 formal cells and generated a passing
  `final-experiment-audit.json` covering 810 scored trajectories and 4,050
  successful Judge scores.

## Verification

- Python compilation passed for all modified and added scripts.
- 18 focused D and affected-component tests passed.
- Earlier local test counts were environment-specific. Final verification uses
  the pinned `requirements-ci.txt` dependencies. Native Windows checks can
  still fail where Unix symbolic-link privileges or LF byte comparisons are
  required; full execution is documented for macOS/Linux/WSL.
- Final review on 2026-10-16: 72 tests ran on native Windows; 68 passed and
  four did not pass (directory replacement permissions, symbolic-link
  privilege, LF/CRLF byte equality, and path separators). Ten focused result,
  audit, matrix-runner, and binary-archive checks passed after the final fixes.
- JSON Schema and semantic asset validations passed. The schema-diff check
  still reports Windows path separators as a provenance difference; no schema
  snapshots or evaluated harness files were regenerated during this review.

## Final verification status

- Formal execution completed under WSL Ubuntu with the pinned model, task set,
  Judge settings, and harness hashes.
- Final audit passes with no missing result cells or score records.
- The final audit records `secrets_recorded: false`; `.env` remains a local
  file and is excluded from the deliverable boundary.
- Native Windows remains unsupported for full execution because annotation
  links require Unix-style symbolic links; use WSL, Linux, or macOS to rerun.

- The final review excludes supplementary ablations from result and cost
  collection and treats compressed result archives as binary in text checks.
- Task 2 remains a candidate under-update case; a changed-contract cause has
  not been established by the retained evidence.

## Full Rewrite interpretation

The evaluated Full Rewrite is one generic, version-invariant replacement that
removes stale tool-specific guidance and directs the model to the live
`tools/list`. It is materialized under Early, Middle, and Late for uniform
runner selection, but the text is identical and was not synthesized from each
schema snapshot. Results and reports use this exact definition; a
schema-generated version-specific rewrite would be a separate future
experiment.
