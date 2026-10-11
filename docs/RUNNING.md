# Unified Experiment Entry Point

## 1. Canonical experiment configuration

`configs/experiment.json` is the configuration actually read by the program. It pins the benchmark commit, the 30-task file and SHA-256, model settings, Early/Middle/Late MCP endpoints and server configurations, and separate output directories.

The three versions do not accept independent model or task arguments, preventing accidental configuration drift.

## 2. Secure API configuration

```bash
cp .env.example .env
```

Set `MODEL_API_KEY` and the optional `MODEL_BASE_URL` only in the local `.env`. Git ignores this file. The runner parses `NAME=value` directly; it never executes the file through a shell, overwrites pre-existing environment variables, or writes credentials to logs or metadata.

## 3. Preflight checks

```bash
.venv/bin/python scripts/check_experiment_config.py
```

This verifies the checkout commit, task count and hash, model settings, all three 1MCP configurations, URLs, and output directories.

Preview one version without reading credentials or making an API request:

```bash
.venv/bin/python scripts/run_benchmark.py --version early --dry-run
```

## 4. Run one version

Start the matching 1MCP environment in one terminal:

```bash
pnpm exec 1mcp serve --config generated/1mcp/early.json --host 127.0.0.1 --port 3051
```

Run the benchmark in another terminal:

```bash
.venv/bin/python scripts/run_benchmark.py --version early
```

Use `middle`/`3052` or `late`/`3053` for the other versions. The entry point checks the MCP server set before injecting the configured API key, base URL, and temperature into the upstream runner. Metadata is written to:

```text
results/pilot-30/<early|middle|late>/run-metadata.json
```

Metadata never contains credentials.

## 5. Zero-cost end-to-end smoke test

```bash
.venv/bin/python scripts/run_smoke_tests.py
```

This command uses `configs/smoke.json` and a deterministic local model, then starts, executes, and stops all three environments. See [smoke results](SMOKE_TEST.md) and [handoff commands](HANDOFF.md).
