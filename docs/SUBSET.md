# Fixed Task Subset

## Why the pilot uses 30 tasks

The full benchmark starts many MCP servers and has substantial model, judge, runtime, and API cost. The case permits a fixed, documented subset when compute is limited, so the first phase uses a 30-task development set.

## Required coverage

- Recovery: approximately 24 tasks use changed servers.
- Retention: approximately six tasks use no known changed server and detect regressions in existing capability.

Affected tasks collectively cover tool-level, parameter-level, and description-level changes. One task may cover several change types.

## Reproducibility

The generator pins:

- Size: 30
- Seed: 6203
- Upstream commit: `888c779a0fe735f612ca62bdd1fdd7c9e6bf8701`
- Availability report: `reports/environment-validation.json`

A task is eligible only when every required server is actually `connected` in Early, Middle, and Late. Presence in a configuration file alone is insufficient.

The generated output contains `test_cases.json`, which is passed to the benchmark, and `manifest.json`, which records the source hash, selected task IDs, affected/retention counts, and change-type coverage. All harness strategies must use the same generated files.

```bash
.venv/bin/python scripts/build_subset.py \
  --benchmark-root external/MCPEvol-Bench \
  --size 30 --seed 6203 --affected-fraction 0.8 \
  --availability-report reports/environment-validation.json \
  --output-dir data/subsets/pilot-30
```

The current result contains 24 affected and six retention tasks, including 17 description-change, 23 parameter-change, and 20 tool-change tasks.

Validate coverage with:

```bash
.venv/bin/python scripts/validate_subset_coverage.py
```

The command verifies task IDs, required servers, labels, summary counts, and writes `reports/pilot-30-coverage.json`.

## Machine-readable runnability matrix

```bash
.venv/bin/python scripts/build_runnability_matrix.py
```

The matrix records every task's `required_servers` and their state in every version. The command and `check_experiment_config.py` fail if any dependency is not `connected`.

## Upgrading to the full dataset

Use the full dataset only after the 30-task pilot succeeds and budget, runtime, and server stability are confirmed. Create a new experiment name and never overwrite pilot results.
