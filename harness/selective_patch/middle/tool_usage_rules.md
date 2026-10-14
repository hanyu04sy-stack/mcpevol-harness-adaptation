# Tool Usage Rules

## Injected rules

Note that do not to ask any questions to the user, just call the tool to complete the task.


### Tool @j0kz/orchestrator-mcp / run_workflow
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Updated description guidance: ["Execute an intelligent workflow with optional focus detection and user-intent context.", "- Ambiguous request \u2192 Call WITHOUT workflow and focus to get clarification", "- Richer requests \u2192 Include prompt to preserve the user's original intent for downstream workflow context", "- \"review my code\" \u2192 omit workflow and focus (get clarification)", "- \"check security in this project\" \u2192 focus='security', prompt='check security in this project'", "- \"run pre-commit for my repo\" \u2192 workflow='pre-commit', prompt='run pre-commit for my repo'"]
Changed parameter contract (current values under after): {{"added": [{{"name": "prompt", "required": false, "schema": {{"description": "Original user request for workflow context (optional)", "type": "string"}}}}], "modified": [], "removed": [{{"name": "files", "required": false, "schema": {{"description": "Files to process (optional for project-level)", "items": {{"type": "string"}}, "type": "array"}}}}, {{"name": "language", "required": false, "schema": {{"description": "Response language (optional, auto-detects from user input)", "enum": ["en", "es"], "type": "string"}}}}], "renamed": []}}

### Tool @kazuph/mcp-taskmanager / request_planning
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Updated description guidance: ["Register a new user request and plan its associated tasks. You must provide 'originalRequest', 'splitDetails', and 'tasks'.", "Validation rules: 'originalRequest' and 'splitDetails' must each be 10-2000 characters after trimming. 'tasks' must contain 1 to 50 items. Each task title must be 3-120 characters, each description 5-2000 characters, and task titles must be unique within the request."]
Changed parameter contract (current values under after): {{"added": [], "modified": [{{"after": {{"maxLength": 2000, "minLength": 10, "type": "string"}}, "before": {{"type": "string"}}, "name": "originalRequest", "required_after": true, "required_before": true}}, {{"after": {{"maxLength": 2000, "minLength": 10, "type": "string"}}, "before": {{"type": "string"}}, "name": "splitDetails", "required_after": true, "required_before": false}}, {{"after": {{"items": {{"properties": {{"description": {{"maxLength": 2000, "minLength": 5, "type": "string"}}, "title": {{"maxLength": 120, "minLength": 3, "type": "string"}}}}, "required": ["title", "description"], "type": "object"}}, "maxItems": 50, "minItems": 1, "type": "array"}}, "before": {{"items": {{"properties": {{"description": {{"type": "string"}}, "title": {{"type": "string"}}}}, "required": ["title", "description"], "type": "object"}}, "type": "array"}}, "name": "tasks", "required_after": true, "required_before": true}}], "removed": [], "renamed": []}}
Current required fields: ["originalRequest", "splitDetails", "tasks"]

### Tool @magicuidesign/mcp / getAnimations
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Provides detailed implementation data for blur-fade components in the Animations category. Use getComponentIndex first if you need a categorized discovery overview before fetching full component code and examples."

### Tool @magicuidesign/mcp / getBackgrounds
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Provides detailed implementation data for warp-background, flickering-grid, animated-grid-pattern, retro-grid, ripple, dot-pattern, grid-pattern, interactive-grid-pattern components in the Backgrounds category. Use getComponentIndex first i"

### Tool @magicuidesign/mcp / getButtons
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Provides detailed implementation data for rainbow-button, shimmer-button, shiny-button, interactive-hover-button, animated-subscribe-button, pulsating-button, ripple-button components in the Buttons category. Use getComponentIndex first if "

### Tool @magicuidesign/mcp / getComponentIndex
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Provides a categorized index of Magic UI components with example coverage counts to help clients discover the most relevant category tool before fetching full implementation details."

### Tool @magicuidesign/mcp / getComponents
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Provides detailed implementation data for marquee, terminal, hero-video-dialog, bento-grid, animated-list, dock, globe, tweet-card, client-tweet-card, orbiting-circles, avatar-circles, icon-cloud, animated-circular-progress-bar, file-tree, "

### Tool @magicuidesign/mcp / getDeviceMocks
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Provides detailed implementation data for safari, iphone-15-pro, android components in the DeviceMocks category. Use getComponentIndex first if you need a categorized discovery overview before fetching full component code and examples."

### Tool @magicuidesign/mcp / getRegistryItem
This tool was removed from this connected server. Do not call its old name. Select an available tool only if its documented capability fits the task; do not invent a replacement.

### Tool @magicuidesign/mcp / getSpecialEffects
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Provides detailed implementation data for animated-beam, border-beam, shine-border, magic-card, meteors, neon-gradient-card, confetti, particles, cool-mode, scratch-to-reveal components in the SpecialEffects category. Use getComponentIndex "

### Tool @magicuidesign/mcp / getTextAnimations
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Provides detailed implementation data for text-animate, line-shadow-text, aurora-text, number-ticker, animated-shiny-text, animated-gradient-text, text-reveal, hyper-text, word-rotate, typing-animation, scroll-based-velocity, flip-text, box"

### Tool @magicuidesign/mcp / getUIComponents
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Provides the complete raw catalog of all Magic UI components. Use getComponentIndex for a categorized discovery-oriented overview before requesting detailed category implementations."

### Tool @magicuidesign/mcp / listRegistryItems
This tool was removed from this connected server. Do not call its old name. Select an available tool only if its documented capability fits the task; do not invent a replacement.

### Tool @magicuidesign/mcp / searchRegistryItems
This tool was removed from this connected server. Do not call its old name. Select an available tool only if its documented capability fits the task; do not invent a replacement.

### Tool @rtuin/mcp-mermaid-validator / validateMermaid
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [], "modified": [{{"after": {{"maxLength": 50000, "minLength": 1, "type": "string"}}, "before": {{"type": "string"}}, "name": "diagram", "required_after": true, "required_before": true}}, {{"after": {{"enum": ["svg", "png"], "type": "string"}}, "before": {{"default": "png", "enum": ["svg", "png"], "type": "string"}}, "name": "format", "required_after": true, "required_before": false}}], "removed": [], "renamed": []}}
Current required fields: ["diagram", "format"]

### Tool coffee-mcp-agent / orderCoffee
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [{{"name": "note", "required": false, "schema": {{"description": "\u8ba2\u5355\u5907\u6ce8\uff0c\u9009\u586b\uff0c\u4f8b\u5982\uff1a\u5c11\u7cd6\u3001\u5c3d\u5feb\u5236\u4f5c", "type": "string"}}}}, {{"name": "quantity", "required": false, "schema": {{"description": "\u8d2d\u4e70\u676f\u6570\uff0c\u9009\u586b\uff0c\u9ed8\u8ba4\u4e3a1", "type": "integer"}}}}], "modified": [], "removed": [], "renamed": []}}
Current required fields: ["productName", "spec"]

### Tool mcp-calculator / loan_payment
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [{{"name": "extra_payment", "required": false, "schema": {{"default": 0, "description": "\u6bcf\u671f\u989d\u5916\u8fd8\u6b3e\u91d1\u989d\uff08\u9ed8\u8ba40\uff09", "minimum": 0, "type": "number"}}}}, {{"name": "include_schedule", "required": false, "schema": {{"default": false, "description": "\u662f\u5426\u5305\u542b\u7b80\u8981\u8fd8\u6b3e\u8fdb\u5ea6\u6458\u8981", "type": "boolean"}}}}, {{"name": "payment_frequency", "required": false, "schema": {{"default": 12, "description": "\u6bcf\u5e74\u8fd8\u6b3e\u6b21\u6570\uff08\u9ed8\u8ba412\uff0c12=\u6309\u6708\uff0c4=\u6309\u5b63\uff0c1=\u6309\u5e74\uff09", "exclusiveMinimum": 0, "type": "integer"}}}}], "modified": [], "removed": [], "renamed": []}}
Current required fields: ["loan_amount", "annual_rate", "years"]

### Tool mcp-filesystem-server / list_directory
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [{{"name": "reverse", "required": false, "schema": {{"default": false, "description": "Reverse the sort order", "type": "boolean"}}}}, {{"name": "sortBy", "required": false, "schema": {{"default": "default", "description": "Sorting mode: default (directories first), name, or type", "enum": ["default", "name", "type"], "type": "string"}}}}], "modified": [], "removed": [], "renamed": []}}
Current required fields: ["path"]

### Tool mcp-server-commands / run_process
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Updated description guidance: ["Run a process on this darwin machine,                         oneOf: [", "                            {{", "                                properties: {{ mode: {{ const: \"shell\" }} }},", "                                required: [\"command_line\"],", "                                not: {{ required: [\"argv\"] }}", "                            }},", "                            {{", "                                properties: {{ mode: {{ const: \"executable\" }} }},", "                                required: [\"argv\"],", "                                not: {{ required: [\"command_line\"] }}", "                            }}", "                        ]"]
Changed parameter contract (current values under after): {{"added": [{{"name": "dry_run", "required": false, "schema": {{"description": "Optional explain what would run, defaults to False.", "type": "boolean"}}}}, {{"name": "mode", "required": true, "schema": {{"description": "What are you running, two choices: 'shell' or 'executable' (required, no default)", "enum": ["shell", "executable"]}}}}], "modified": [{{"after": {{"description": "Executable and arguments. argv[0] is the executable. Required when mode='executable'. Forbidden when mode='shell'.", "items": {{"minLength": 1, "type": "string"}}, "minItems": 1, "type": "array"}}, "before": {{"description": "Executable mode: directly spawn a process. argv[0] is the executable, followed by arguments passed verbatim (no shell interpretation). Cannot be combined with 'command_line'.", "items": {{"type": "string"}}, "minItems": 1, "type": "array"}}, "name": "argv", "required_after": false, "required_before": false}}, {{"after": {{"description": "Shell command line. Required when mode='shell'. Forbidden when mode='executable'.", "minLength": 1, "type": "string"}}, "before": {{"description": "Shell mode: a shell command line executed via the system's default shell. Supports pipes, redirects, globbing. Cannot be combined with 'argv'.", "type": "string"}}, "name": "command_line", "required_after": false, "required_before": false}}, {{"after": {{"description": "Working directory. Required and must be a non-empty string.", "minLength": 1, "type": "string"}}, "before": {{"description": "Optional to set working directory", "type": "string"}}, "name": "cwd", "required_after": true, "required_before": false}}, {{"after": {{"description": "Optional timeout in milliseconds, must be an integer between 1 and 300000, defaults to 30,000ms", "maximum": 300000, "minimum": 1, "type": "integer"}}, "before": {{"description": "Optional timeout in milliseconds, defaults to 30,000ms", "type": "number"}}, "name": "timeout_ms", "required_after": false, "required_before": false}}], "removed": [], "renamed": [{{"after": {{"name": "stdin", "required": false, "schema": {{"description": "Optional text written to STDIN (written fully, then closed). Useful for heredoc-style input or file contents.", "type": "string"}}}}, "before": {{"name": "stdin_text", "required": false, "schema": {{"description": "Optional text written to STDIN (written fully, then closed). Useful for heredoc-style input or file contents.", "type": "string"}}}}}}]}}
Current required fields: ["mode", "cwd"]

### Tool mcp-weather-demo / get-forecast
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [{{"name": "includeDetails", "required": false, "schema": {{"description": "Whether to include detailed lines such as wind information", "type": "boolean"}}}}, {{"name": "periods", "required": false, "schema": {{"description": "Maximum number of forecast periods to return", "exclusiveMinimum": 0, "type": "integer"}}}}], "modified": [], "removed": [], "renamed": []}}
Current required fields: ["latitude", "longitude"]

### Tool mcp-weather-demo / get-weather-advice
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Get practical weather advice for a location and activity"

### Tool nfty-mcp-server / send-ntfy
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [{{"name": "delaySeconds", "required": false, "schema": {{"minimum": 0, "type": "integer"}}}}, {{"name": "markdown", "required": false, "schema": {{"type": "boolean"}}}}, {{"name": "topic", "required": false, "schema": {{"minLength": 1, "type": "string"}}}}], "modified": [], "removed": [], "renamed": []}}
Current required fields: ["message"]

## Routing reference

The upstream agent selects the server for a requested tool through `tool_server_map[tool_name]`, converts the selected tool to `<server>_1mcp_<tool>`, and sends it to the configured 1MCP endpoint. Tool results are appended as `role=tool` messages with the original tool-call ID. If the model returns ordinary text without a tool call, the agent reminds it to call a tool directly and stops after three consecutive no-tool responses.

This section documents the runtime routing implemented in `src/custom/agents/SimpleOpenAIAgent.py`. Only the text under `Injected rules` is added to the resolved system prompt, and duplicate text already present in `system_prompt.md` is not added twice.
