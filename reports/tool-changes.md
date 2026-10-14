# Tool Schema Changes

Benchmark commit: `888c779a0fe735f612ca62bdd1fdd7c9e6bf8701`

| Comparison | Servers compared | Added | Removed | Renamed | Description | Parameters |
|---|---:|---:|---:|---:|---:|---:|
| early to middle | 26 | 10 | 3 | 0 | 3 | 9 |
| middle to late | 26 | 7 | 0 | 0 | 12 | 15 |
| early to late | 26 | 17 | 3 | 0 | 5 | 17 |

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

### `@j0kz/orchestrator-mcp`

- Added tools: `inspect_workflow`
- Changed parameters: `run_workflow`

### `@kazuph/mcp-taskmanager`

- Changed descriptions: `request_planning`
- Changed parameters: `request_planning`

### `@magicuidesign/mcp`

- Added tools: `getComponentDetails`, `getComponentsByNames`, `searchComponents`
- Changed descriptions: `getAnimations`, `getBackgrounds`, `getButtons`, `getComponentIndex`, `getComponents`, `getDeviceMocks`, `getSpecialEffects`, `getTextAnimations`, `getUIComponents`

### `@rtuin/mcp-mermaid-validator`

- Changed parameters: `validateMermaid`

### `coffee-mcp-agent`

- Added tools: `checkOrderEstimate`
- Changed parameters: `orderCoffee`

### `mcp-calculator`

- Added tools: `break_even_analysis`, `percentage_calculator`
- Changed descriptions: `loan_payment`, `net_present_value`

### `mcp-filesystem-server`

- Changed parameters: `read_file`, `read_multiple_files`

### `mcp-server-commands`

- Changed parameters: `run_process`

### `mcp-tung-shing`

- Changed parameters: `get-tung-shing`

### `nfty-mcp-server`

- Changed parameters: `send-ntfy`

### `time-mcp`

- Changed parameters: `convert_time`, `current_time`, `days_in_month`, `get_timestamp`, `get_week_year`, `relative_time`


## early to late

### `@j0kz/orchestrator-mcp`

- Added tools: `inspect_workflow`
- Changed descriptions: `run_workflow`
- Changed parameters: `run_workflow`

### `@kazuph/mcp-taskmanager`

- Changed descriptions: `request_planning`
- Changed parameters: `request_planning`

### `@magicuidesign/mcp`

- Added tools: `getAnimations`, `getBackgrounds`, `getButtons`, `getComponentDetails`, `getComponentIndex`, `getComponents`, `getComponentsByNames`, `getDeviceMocks`, `getSpecialEffects`, `getTextAnimations`, `getUIComponents`, `searchComponents`
- Removed tools: `getRegistryItem`, `listRegistryItems`, `searchRegistryItems`

### `@rtuin/mcp-mermaid-validator`

- Changed parameters: `validateMermaid`

### `coffee-mcp-agent`

- Added tools: `checkOrderEstimate`
- Changed parameters: `orderCoffee`

### `mcp-calculator`

- Added tools: `break_even_analysis`, `percentage_calculator`
- Changed descriptions: `loan_payment`, `net_present_value`
- Changed parameters: `loan_payment`

### `mcp-filesystem-server`

- Changed parameters: `list_directory`, `read_file`, `read_multiple_files`

### `mcp-server-commands`

- Changed descriptions: `run_process`
- Changed parameters: `run_process`

### `mcp-tung-shing`

- Changed parameters: `get-tung-shing`

### `mcp-weather-demo`

- Added tools: `get-weather-advice`
- Changed parameters: `get-forecast`

### `time-mcp`

- Changed parameters: `convert_time`, `current_time`, `days_in_month`, `get_timestamp`, `get_week_year`, `relative_time`

## Pilot manifest alignment

- Affected servers with detected changes: 12
- Affected servers unavailable in at least one schema snapshot: 0
- Unmatched affected servers: 6
