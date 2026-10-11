# Benchmark Environment Setup

## 1. Why versions are pinned

MCPEvol-Bench continues to change. To keep the three strategy scores comparable, this project pins commit:

```text
888c779a0fe735f612ca62bdd1fdd7c9e6bf8701
```

Any future benchmark upgrade must use a new experiment batch. Never mix results from different benchmark commits.

## 2. Environment mapping

| Case version | Upstream directory | Meaning |
|---|---|---|
| Early | `servers/1mcp_config/original` | Initial tool environment |
| Middle | `servers/1mcp_config/iter3` | Environment after the first evolution stage |
| Late | `servers/1mcp_config/iter5` | Environment after the second evolution stage |

## 3. Installation

Install Python 3.12, Node.js 24, and pnpm 11.25, then run this command from the repository root:

```bash
python3 scripts/setup_environment.py
```

The script checks out the pinned upstream source, creates `.venv`, installs pinned Python dependencies and 1MCP, downloads and verifies the server bundles, renders local configurations, and runs strict validation.

The upstream `requirements.txt` contains CUDA/NVIDIA-only packages and is not suitable for macOS. This project uses `requirements/benchmark.txt`, which pins only the dependencies required for the remote OpenAI-compatible tool-level runner and supports both macOS and Linux.

Verify existing archives without downloading or extracting:

```bash
python3 scripts/download_server_bundles.py --verify-only
```

Run strict validation:

```bash
.venv/bin/python scripts/check_environment.py --strict
```

If validation fails, follow the [macOS/Linux troubleshooting guide](TROUBLESHOOTING.md).

## 4. Verified toolchain

- Python 3.12.14
- Node.js 24.19.0
- pnpm 11.25.0
- Project-local 1MCP 0.38.2
- Downloaded, SHA-256-verified, and extracted iter3/iter5 bundles

## 5. Tool-environment validation

The validator starts each version on an isolated port, waits for servers to reach `connected` or `failed`, marks any server still loading at the 15-minute limit as unavailable, and writes a machine-readable report.

```bash
.venv/bin/python scripts/validate_tool_environments.py
```

`reports/environment-validation.json` contains server counts, tool counts, connection states, failure lists, and failure reasons. Untracked raw logs are written under `logs/environment-validation/`. See [validated results](ENVIRONMENT_VALIDATION.md).

## 6. Fair-comparison rules

No-update, Full-rewrite, and Selective-patch may change only the harness content. They must share the same benchmark commit, server bundle, task JSON and SHA-256, model and parameters, judge and parameters, run count, and MCP host/port configuration.

## 7. Known upstream discrepancy

The case document mentions 201 tasks, while the pinned public repository contains 393 tasks in `test_cases.json`. This is not a code defect. Every report must identify the exact commit, actual task count, and fixed subset used.
