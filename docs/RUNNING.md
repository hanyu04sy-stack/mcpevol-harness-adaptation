# Unified Experiment Entry Point

## 1. Canonical experiment configuration

`configs/experiment.json` is the configuration actually read by the program. It pins the benchmark commit, the 30-task file and SHA-256, model settings, the default harness directory, Early/Middle/Late MCP endpoints and server configurations, and separate output directories.

The three versions do not accept independent model or task arguments, preventing accidental configuration drift.

## 2. Secure API configuration

```bash
cp .env.example .env
```

Set `MODEL_API_KEY` only in the local `.env`; the checked-in example already
sets `MODEL_BASE_URL=https://api.deepseek.com` for the pinned
`deepseek-chat` model. Git ignores `.env`. The runner parses `NAME=value`
directly; it never executes the file through a shell, overwrites pre-existing
environment variables, or writes credentials to logs or metadata.

Leave `JUDGE_API_KEY` and `JUDGE_BASE_URL` blank when judge and agent use the
same model; the judge safely inherits `MODEL_*`. Client timeout and retry values
come from `openai_client` in the experiment config.

## Model provider notes

- Recommended DeepSeek endpoint: `https://api.deepseek.com`; current OpenAI SDKs handle the compatible route.
- With an OpenAI SDK older than 1.0, use `https://api.deepseek.com/v1`.
- If unsure, run `.venv/bin/python scripts/check_model_connection.py`; it probes both forms when needed and reports the working endpoint.
- The configured V3 slug is `deepseek-chat`. Do not use `deepseek-reasoner` as the tool-calling agent.
- Run `.venv/bin/python scripts/check_model_connection.py` before any paid batch.
- Provider slugs and prices change. A model-not-found result means the config must be updated before continuing.

## 3. Preflight checks

```bash
.venv/bin/python scripts/check_experiment_config.py
```

This verifies the checkout commit, task count and hash, model settings, all three 1MCP configurations, URLs, and output directories.

Preview one version without reading credentials or making an API request:

```bash
.venv/bin/python scripts/run_benchmark.py --version early --dry-run
```

Print the exact injected prompt and all harness file hashes:

```bash
.venv/bin/python scripts/run_benchmark.py --version early --dry-run \
  --harness-dir harness/no_update --print-resolved-prompt
```

## 4. Run one version

Start the matching 1MCP environment in one terminal:

```bash
pnpm exec 1mcp serve --config generated/1mcp/early.json --host 127.0.0.1 --port 3051
```

Run the benchmark in another terminal:

```bash
.venv/bin/python scripts/run_benchmark.py --version early --run-id 1
```

The default comes from `harness.default_dir`. B and C can override only the harness knowledge while leaving every fairness-critical setting unchanged:

```bash
.venv/bin/python scripts/run_benchmark.py --version early \
  --harness-dir harness/full_rewrite
.venv/bin/python scripts/run_benchmark.py --version early \
  --harness-dir harness/selective_patch
```

Use `middle`/`3052` or `late`/`3053` for the other versions. The entry point checks the MCP server set before injecting the configured API key, base URL, and temperature into the upstream runner. Metadata is written to:

```text
results/<strategy>/<early|middle|late>/run-XX/run-metadata.json
```

Metadata never contains credentials. It does contain `harness_dir`, `harness_manifest_sha256`, and the SHA-256 of each injected harness file for auditability.

## 5. Run IDs and fairness check

Use the same positive `--run-id` for the three versions that form one repeat.
Before a real benchmark call, the runner automatically verifies the upstream
checkout, task SHA-256, and pinned model/judge settings. It writes the audit to
`reports/fairness-check.json`. The same check can be run directly:

```bash
.venv/bin/python scripts/verify_untouched.py
```

The check must pass before B or C compares strategies.

## 6. Judge

The pinned upstream runner creates trajectories but does not automatically
score them. The judge inherits the agent key and endpoint by default. Run the
separate judge phase with the same version, strategy, and run ID:

```bash
.venv/bin/python scripts/run_judge.py \
  --version early --harness-dir harness/no_update --run-id 1
```

Normalized scores are written to `judge-results.json`: TF is `tasks[].tf`, PE
is `tasks[].pe`, and ECS is calculated after all three versions are available.
See [Judge Integration](JUDGE.md) for the exact upstream source locations.

Collect every completed formal run with:

```bash
.venv/bin/python scripts/collect_results.py
```

This creates `results/summary.csv` and `results/summary.json`, including TF, PE,
ECS, recovery, retention, timing, and separate Agent/Judge/retry cost totals.

## 7. Export tool definitions

```bash
.venv/bin/python scripts/dump_tool_schemas.py
```

This starts the configured Early, Middle, and Late 1MCP environments, calls MCP `tools/list`, preserves each tool description and `inputSchema`, and writes a deterministic diff under `reports/tool-schemas/`. If concurrent startup is unreliable on a small machine, add `--isolated`.

Build the detailed change report after schema export:

```bash
.venv/bin/python scripts/diff_tool_schemas.py
.venv/bin/python scripts/diff_tool_schemas.py --check
```

The first command writes `reports/tool-changes.json` and `reports/tool-changes.md`; the second verifies that both remain consistent with the three source snapshots and requires non-empty tool, description, and parameter change evidence.

## 8. Zero-cost end-to-end smoke test

```bash
.venv/bin/python scripts/run_smoke_tests.py
```

This command uses `configs/smoke.json` and a deterministic local model, then starts, executes, and stops all three environments. See [smoke results](SMOKE_TEST.md) and [handoff commands](HANDOFF.md).
