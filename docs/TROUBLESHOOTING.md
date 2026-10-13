# macOS / Linux Troubleshooting Guide

This guide applies to the pinned Member A environment. Start from the repository root:

```bash
.venv/bin/python scripts/check_environment.py --strict
.venv/bin/python scripts/check_experiment_config.py
```

Do not remove tasks, change SHA-256 values, replace the benchmark commit, or ignore failed servers merely to pass validation.

## Diagnostic order

1. Confirm the current directory is the repository root.
2. Run both checks above and preserve the first error.
3. Resolve port conflicts before version errors.
4. Then resolve hash mismatches or server loading failures.
5. Run `.venv/bin/python scripts/check_handoff.py` after repair.

## 1. Port already in use

| Purpose | Early | Middle | Late |
|---|---:|---:|---:|
| Formal pilot | 3051 | 3052 | 3053 |
| Smoke | 3151 | 3152 | 3153 |
| Cold-start stability | 3251 | 3252 | 3253 |
| Canary | 3351 | 3352 | 3353 |

Typical symptoms are `EADDRINUSE`, `address already in use`, an immediate 1MCP exit, or validation connecting to a stale process.

macOS:

```bash
lsof -nP -iTCP:3051 -sTCP:LISTEN
```

Linux:

```bash
ss -ltnp | grep -E ':(3051|3052|3053)([^0-9]|$)'
```

Verify the PID and command belong to a stale 1MCP process from this project, then terminate it normally:

```bash
kill -TERM <PID>
```

Never terminate an unfamiliar system process. For diagnosis, use isolated temporary ports:

```bash
.venv/bin/python scripts/validate_tool_environments.py --base-port 4051
```

Formal B/C/D runs must still use ports 3051-3053 pinned in `configs/experiment.json`.

## 2. Python / Node.js / pnpm / 1MCP version error

Expected versions are Python 3.12.x, Node.js 24.x, pnpm 11.25.x, and project-local 1MCP 0.38.2.

```bash
python3 --version
node --version
pnpm --version
node_modules/.bin/1mcp --version
command -v python3
command -v node
command -v pnpm
```

If Python is not 3.12, install it with a system package or version manager, then run:

```bash
python3.12 scripts/setup_environment.py
```

For Node.js or pnpm mismatches, select Node.js 24 and pnpm 11.25, then rebuild local dependencies:

```bash
pnpm install --frozen-lockfile
node_modules/.bin/1mcp --version
```

Always use project-local commands such as `node_modules/.bin/1mcp` or `pnpm run serve:early`, then rerun strict environment validation.

## 3. SHA-256 or file-hash mismatch

Verify server bundles without downloading or extracting:

```bash
python3 scripts/download_server_bundles.py --verify-only
```

Expected hashes are pinned in `scripts/download_server_bundles.py`. Do not change them after a mismatch. Move the damaged archive to a recoverable quarantine name and download it again:

```bash
mv external/servers/archives/iter3_servers.zip external/servers/archives/iter3_servers.zip.corrupt
python3 scripts/download_server_bundles.py --versions middle --repair-extraction
```

For Late, use `iter5_servers.zip` and `--versions late`. Ensure about 1.1 GB of free space and network access.

For task, report, or configuration mismatches:

```bash
git diff -- configs data/subsets reports
.venv/bin/python scripts/check_experiment_config.py
```

If a change was accidental, preserve any needed work and restore only the known affected file. If Member A intentionally rebuilds the subset or stability report, regenerate dependent reports and hashes and pass `check_handoff.py`. Members B/C/D must not replace pinned hashes.

## 4. Server loading failure or timeout

Typical symptoms include `failed`, persistent `loading`, `validation timeout`, fewer visible servers than expected, or `MCP task dependencies are unavailable`.

Validate one version and preserve its logs:

```bash
.venv/bin/python scripts/validate_tool_environments.py --versions late --timeout 900
python3 -m json.tool reports/environment-validation.json
grep -n "Failed to connect" logs/environment-validation/late.log
```

Inspect a running Late endpoint with:

```bash
curl -fsS http://127.0.0.1:3053/api/v1/inspect | python3 -m json.tool
```

- `command not found`: confirm `.venv/bin` and `node_modules/.bin` exist, then rerun setup.
- Missing Python package: use `.venv/bin/python`, not system Python.
- Missing Node package: run `pnpm install --frozen-lockfile`.
- macOS dataless or empty extracted files: restore from the verified archive:

```bash
python3 scripts/download_server_bundles.py --versions late --repair-extraction
```

Do not manually add missing servers to a generated configuration. Render it again from the pinned task set:

```bash
.venv/bin/python scripts/render_mcp_config.py \
  --benchmark-root external/MCPEvol-Bench \
  --server-bundle-root external/servers \
  --version late \
  --test-case-file data/subsets/pilot-30/test_cases.json \
  --output generated/1mcp/late.json
```

Continue only after every required dependency is `connected`:

```bash
.venv/bin/python scripts/validate_tool_environments.py --versions late --timeout 900
.venv/bin/python scripts/check_experiment_config.py
```

## 5. "Tool call format error" during agent run

If the agent repeatedly fails with tool-call parse errors while the harness
configuration is otherwise valid:

1. Run `.venv/bin/python scripts/check_model_connection.py`.
2. If the tool-calling self-test fails, treat this as a DeepSeek
   function-calling compatibility issue rather than a harness bug.
3. Confirm the model is `deepseek-flash`, not `deepseek-reasoner`.
4. Reduce parallel tool calls; the pinned upstream agent normally emits one at
   a time.
5. As a last resort, configure an endpoint and matching model slug for a
   provider known to support the required tool-calling behavior.

## 6. Final recovery check

```bash
.venv/bin/python scripts/check_handoff.py
```

If the incident involved real server startup, also run:

```bash
.venv/bin/python scripts/run_smoke_tests.py
```

The incident is resolved only when the handoff gate, configuration check, and relevant server validation all pass.
