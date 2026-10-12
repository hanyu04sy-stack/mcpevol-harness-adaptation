# Tool Schema Changes

Benchmark commit: `888c779a0fe735f612ca62bdd1fdd7c9e6bf8701`

| Comparison | Servers compared | Added | Removed | Renamed | Description | Parameters |
|---|---:|---:|---:|---:|---:|---:|
| early to middle | 26 | 10 | 3 | 0 | 3 | 9 |
| middle to late | 12 | 1 | 0 | 0 | 1 | 4 |
| early to late | 12 | 1 | 0 | 0 | 2 | 3 |

## early to middle

### `@j0kz/orchestrator-mcp`

- Changed descriptions: `run_workflow`
- Changed parameters: `run_workflow`

### `@kazuph/mcp-taskmanager`

- Changed descriptions: `request_planning`
- Changed parameters: `request_planning`

### `@magicuidesign/mcp`

- Added tools: `getAnimations`, `getBackgrounds`, `getButtons`, `getComponentIndex`, `getComponents`, `getDeviceMocks`, `getSpecialEffects`, `getTextAnimations`, `getUIComponents`
- Removed tools: `getRegistryItem`, `listRegistryItems`, `searchRegistryItems`

### `@rtuin/mcp-mermaid-validator`

- Changed parameters: `validateMermaid`

### `coffee-mcp-agent`

- Changed parameters: `orderCoffee`

### `mcp-calculator`

- Changed parameters: `loan_payment`

### `mcp-filesystem-server`

- Changed parameters: `list_directory`

### `mcp-server-commands`

- Changed descriptions: `run_process`
- Changed parameters: `run_process`

### `mcp-weather-demo`

- Added tools: `get-weather-advice`
- Changed parameters: `get-forecast`

### `nfty-mcp-server`

- Changed parameters: `send-ntfy`


## middle to late

Unavailable in the target snapshot: `@aiuluna/knowledge-graph-mcp`, `@j0kz/orchestrator-mcp`, `@magicuidesign/mcp`, `@regle/mcp-server`, `@rtuin/mcp-mermaid-validator`, `bazi-mcp`, `mcp-calculator`, `mcp-filesystem-server`, `mcp-shrimp-task-manager`, `mcp-tasks`, `mcp-tung-shing`, `mcp-weather-demo`, `pantheon-mcp`, `time-mcp`

### `@kazuph/mcp-taskmanager`

- Changed descriptions: `request_planning`
- Changed parameters: `request_planning`

### `coffee-mcp-agent`

- Added tools: `checkOrderEstimate`
- Changed parameters: `orderCoffee`

### `mcp-server-commands`

- Changed parameters: `run_process`

### `nfty-mcp-server`

- Changed parameters: `send-ntfy`


## early to late

Unavailable in the target snapshot: `@aiuluna/knowledge-graph-mcp`, `@j0kz/orchestrator-mcp`, `@magicuidesign/mcp`, `@regle/mcp-server`, `@rtuin/mcp-mermaid-validator`, `bazi-mcp`, `mcp-calculator`, `mcp-filesystem-server`, `mcp-shrimp-task-manager`, `mcp-tasks`, `mcp-tung-shing`, `mcp-weather-demo`, `pantheon-mcp`, `time-mcp`

### `@kazuph/mcp-taskmanager`

- Changed descriptions: `request_planning`
- Changed parameters: `request_planning`

### `coffee-mcp-agent`

- Added tools: `checkOrderEstimate`
- Changed parameters: `orderCoffee`

### `mcp-server-commands`

- Changed descriptions: `run_process`
- Changed parameters: `run_process`

## Pilot manifest alignment

- Affected servers with detected changes: 10
- Affected servers unavailable in at least one schema snapshot: 14
- Unmatched affected servers: 0
