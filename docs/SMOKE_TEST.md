# MCPEvol-Bench Smoke Test Report

## Scope

The fixed task `idx=161` uses two servers verified in all three versions: `@likec4/mcp` and `time`. It calls:

1. `list-projects`
2. `read-project-summary`
3. `search-element`
4. `convert_time`

To avoid external API credentials and cost while remaining reproducible, the smoke test uses a deterministic OpenAI-compatible local model built into the script. It emits tool calls in a fixed sequence; real MCPEvol-Bench, 1MCP, and MCP servers still execute every tool request.

## Verified results

Final verification: 2026-10-11 09:11 (Asia/Shanghai).

| Version | Result | Servers | Tools | Completed tool calls | Tool errors | Duration |
|---|---:|---:|---:|---:|---:|---:|
| Early | Passed | 2/2 | 22 | 4/4 | 0 | 18.738s |
| Middle | Passed | 2/2 | 22 | 4/4 | 0 | 10.374s |
| Late | Passed | 2/2 | 22 | 4/4 | 0 | 10.138s |

All trajectories have `stop=true`, `exceeded=false`, four tool responses, and zero tool errors. `convert_time` returned a real time-zone conversion. The example LikeC4 workspace contained no matching architecture elements, but the MCP protocol call completed successfully and is not a run failure.

The machine-readable summary is `reports/smoke/summary.json`. Each version directory retains:

- `trajectory-161.json`: complete trajectory
- `benchmark.log`: benchmark standard output and error
- `server.log`: 1MCP and tool-call log
- `model-events.json`: local model decision timestamps and tool names

## Interpretation

The test proves that installation, startup, model requests, tool schemas, real MCP calls, trajectory writing, and version-separated output all work in every version.

It is not a model-quality score and does not use a judge. The complete 30-task comparison across three harnesses belongs to Members B/C/D. Unavailable upstream servers are recorded separately in `reports/environment-validation.json` and do not affect this stable smoke subset.
