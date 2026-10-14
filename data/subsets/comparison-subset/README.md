# Comparison task subset

This subset contains the exact `task_idx` intersection of the six No Update and Full Rewrite groups in `reports/baseline-run20-summary.json`. All six groups have the same 23 IDs. The task objects retain their original order and content from `data/subsets/pilot-30/test_cases.json`; the original 30-task files and configuration are unchanged.

IDs: `2, 28, 34, 142, 144, 161, 218, 235, 246, 249, 260, 273, 281, 289, 291, 358, 385, 386, 389, 403, 434, 445, 448`.

The seven IDs absent from B's summary are `37, 162, 177, 251, 327, 384, 422`. The 23-task set has 17 affected tasks and 6 retention tasks. It still covers tool, parameter and description changes (14, 16 and 13 task memberships respectively; a task can cover more than one type). The original 30-task matrix marks every one of the seven omitted tasks runnable in all versions. The summary does not explain why they are absent; this subset records an observed comparison set, not a finding about B's execution.

`manifest.json` records the source summary hash, selected IDs, status and change coverage. `reports/comparison-runnability-matrix.json` is the matching 23-row projection of A's matrix. `configs/comparison-subset/experiment.json` pins this task file and matrix by SHA-256 while preserving the model, judge, MCP, benchmark and startup settings from the original configuration.

Zero-cost preflight:

```bash
.venv/bin/python scripts/check_experiment_config.py --config configs/comparison-subset/experiment.json
.venv/bin/python scripts/verify_untouched.py --config configs/comparison-subset/experiment.json --report /tmp/comparison-subset-fairness.json
.venv/bin/python scripts/run_benchmark.py --version early --config configs/comparison-subset/experiment.json --harness-dir harness/selective_patch/early --dry-run
```

Repeat the dry run for `middle` and `late` with their matching harness directories. These checks make no model or Judge API calls. The completed paid runs and their scoring records are documented in `reports/selective-patch/README.md`; the run number in those commands is a historical execution label.

Matching task IDs alone does not establish full experimental fairness. B's raw run-20 trajectories and judge metadata are not in the repository, so the exact prompt protocol, judge repetition count and runtime conditions cannot be verified from its summary. The current runner adds a shared completion instruction that was introduced after B's published run. For a strict comparison, rerun the baselines under the same current runner or document and assess this protocol difference. The group should also state in its report that it selected the 23-task common set from B's observed results rather than A's original 30-task design.
