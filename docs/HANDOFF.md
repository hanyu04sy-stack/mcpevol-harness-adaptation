# B / C / D Handoff Commands

## Accept Member A's deliverables

```bash
python3 -m pip install -r requirements-ci.txt
python3 scripts/check_handoff.py
```

The top-level `passed` value must be `true`. This command validates all required configurations, tasks, reports, scripts, tests, and documents without downloading or starting server bundles.

If acceptance or a later server start fails, use the [macOS/Linux troubleshooting guide](TROUBLESHOOTING.md). Do not remove tasks or change pinned hashes.

## First-time setup for every member

```bash
git clone https://github.com/hanyu04sy-stack/mcpevol-harness-adaptation.git
cd mcpevol-harness-adaptation
python3 scripts/setup_environment.py
.venv/bin/python scripts/check_experiment_config.py
.venv/bin/python scripts/verify_untouched.py
.venv/bin/python scripts/run_smoke_tests.py
```

The smoke command starts Early, Middle, and Late sequentially. It requires no `.env` and uses no external model API.

## Members B/C: run the fixed 30-task experiment

Create the local credential file:

```bash
cp .env.example .env
```

Each version uses two terminals. For Early:

```bash
# Terminal 1
pnpm run serve:early

# Terminal 2
pnpm run run:early
```

Copy the same pattern for the other versions:

```bash
pnpm run serve:middle
pnpm run run:middle

pnpm run serve:late
pnpm run run:late
```

Members B and C may modify only their own harness knowledge directory. Do not change the upstream source, model, temperature, task SHA-256, MCP URL, or benchmark commit in `configs/experiment.json`.

- No Update: `harness/no_update/`
- Full Rewrite (B): `harness/full_rewrite/`
- Selective Patch (C): `harness/selective_patch/`

Each completed strategy directory must contain `system_prompt.md`, `tool_usage_rules.md`, and `manifest.json`. Select it with `--harness-dir`; the runner injects it at runtime and records its hashes. Before the final comparison, run:

```bash
.venv/bin/python scripts/validate_subset_coverage.py
.venv/bin/python scripts/build_runnability_matrix.py
.venv/bin/python scripts/check_experiment_config.py
.venv/bin/python scripts/run_benchmark.py --version early --dry-run \
  --harness-dir harness/no_update --print-resolved-prompt
```

The exact tool definitions and change inventory are in `reports/tool-schemas/`. Regenerate them only when the pinned server environments change:

```bash
.venv/bin/python scripts/dump_tool_schemas.py
.venv/bin/python scripts/diff_tool_schemas.py --check
```

The fixed subset has 26/26 connected servers in every version. If a local result differs, rerun `python3 scripts/setup_environment.py`; do not remove tasks or replace the dataset.

For each strategy and repeat, run the same ID across all versions, then score
each run separately:

```bash
.venv/bin/python scripts/run_benchmark.py --version early --harness-dir harness/no_update --run-id 1
.venv/bin/python scripts/run_judge.py --version early --harness-dir harness/no_update --run-id 1
```

B uses `harness/full_rewrite`; C uses `harness/selective_patch`. Repeat the two
commands for Middle and Late. Always run `scripts/verify_untouched.py` before a
formal batch.

## Member D: collect and verify output

For the final three-repeat, five-Judge protocol, follow
[`D_EVALUATION.md`](D_EVALUATION.md). It includes the resumable matrix runner,
provider-reported token collection, and the final machine-readable fairness and
completeness audit.

```bash
python3 -m json.tool reports/environment-validation.json >/dev/null
python3 -m json.tool reports/pilot-30-environment-validation.json >/dev/null
python3 -m json.tool reports/pilot-30-coverage.json >/dev/null
python3 -m json.tool reports/pilot-30-runnability-matrix.json >/dev/null
python3 -m json.tool reports/pilot-30-startup-stability.json >/dev/null
python3 -m json.tool reports/smoke/summary.json >/dev/null
.venv/bin/python scripts/collect_results.py
python3 -m json.tool results/summary.json >/dev/null
```

Every formal run directory must contain `run-metadata.json`, `judge-results.json`, and `judge-metadata.json`. Verify its `benchmark_commit`, `task_sha256`, model, judge, harness hashes, and version-specific `mcp_url`. Experiment data is under `results/`; committed environment and smoke evidence is under `reports/`.

Run the local-model canary without an external API:

```bash
.venv/bin/python scripts/run_local_canary.py
```

It uses local Ollama `qwen3.5:4b` and does not read `.env`. Verified trajectories and logs are stored under `reports/canary-local-qwen35-4b-2/`.
