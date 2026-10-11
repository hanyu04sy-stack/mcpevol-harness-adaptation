# Early / Middle / Late Environment Validation

Validation date: 2026-10-10 (Asia/Shanghai). All three versions started the 1MCP aggregation endpoint and discovered all 59 configured servers.

| Version | Startup | Available servers | Unavailable servers | Available tools |
|---|---:|---:|---:|---:|
| Early | Passed | 47 | 12 | 520 |
| Middle | Passed | 55 | 4 | 602 |
| Late | Passed | 54 | 5 | 640 |

At the 15-minute Early sampling limit, three servers remained `loading` and were recorded as unavailable: `@assistant-ui/mcp-docs-server`, `mcp-maven-deps`, and `xcomet-mcp-server`. Every other unavailable server reached the terminal `failed` state.

Late initially had only 23 available servers. macOS had converted extracted dependencies into dataless files with a logical size but no local data. Restoring 20,027 files from the SHA-256-verified bundle increased Late to 54/59 available servers.

The complete 59-server result is in `reports/environment-validation.json`. The exact pilot result is in `reports/pilot-30-environment-validation.json`: all versions have 26/26 connected servers and no failures, with 304, 311, and 318 tools respectively.

## Repeated cold starts

Each version was started in a fresh 1MCP process three times and stopped after sampling.

| Version | Successful trials | Connected per trial | Failures | Unstable servers |
|---|---:|---:|---:|---:|
| Early | 3/3 | 26/26 | 0 | 0 |
| Middle | 3/3 | 26/26 | 0 | 0 |
| Late | 3/3 | 26/26 | 0 | 0 |

Per-trial and per-server states are stored in `reports/pilot-30-startup-stability.json`. The canonical configuration pins its SHA-256. Validation fails if there are fewer than three trials, any failures, any unstable servers, or a mismatch with current server configurations.

Member A can repeat the stability validation with:

```bash
.venv/bin/python scripts/validate_startup_stability.py --trials 3
```

A new run changes timestamps and the report hash, so Member A must review and update the canonical configuration. Members B/C/D should use the pinned report rather than repeat nine starts before every experiment.
