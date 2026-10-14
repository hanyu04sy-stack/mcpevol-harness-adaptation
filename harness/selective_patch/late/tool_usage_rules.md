# Tool Usage Rules

## Injected rules

Note that do not to ask any questions to the user, just call the tool to complete the task.


### Tool @j0kz/orchestrator-mcp / inspect_workflow
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Inspect the detailed structure and configuration of a workflow without executing it. Useful for debugging, validation, and understanding workflow composition before running.\n\n**Use Cases:**\n- Validate workflow structure before execution\n- D"

### Tool @j0kz/orchestrator-mcp / run_workflow
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Updated description guidance: ["Execute an intelligent workflow with optional focus detection and user-intent context.", "- Ambiguous request \u2192 Call WITHOUT workflow and focus to get clarification", "- Richer requests \u2192 Include prompt to preserve the user's original intent for downstream workflow context", "- \"review my code\" \u2192 omit workflow and focus (get clarification)", "- \"check security in this project\" \u2192 focus='security', prompt='check security in this project'", "- \"run pre-commit for my repo\" \u2192 workflow='pre-commit', prompt='run pre-commit for my repo'"]
Changed parameter contract (current values under after): {{"added": [{{"name": "excludePaths", "required": false, "schema": {{"description": "Glob patterns or paths to exclude from analysis (optional, e.g. [\"node_modules\", \"dist\"])", "items": {{"type": "string"}}, "type": "array"}}}}, {{"name": "output_format", "required": false, "schema": {{"description": "Response structure: full (default), summary, or minimal (optional)", "enum": ["full", "summary", "minimal"], "type": "string"}}}}, {{"name": "prompt", "required": false, "schema": {{"description": "Original user request for workflow context (optional)", "type": "string"}}}}, {{"name": "severity_threshold", "required": false, "schema": {{"description": "Minimum severity level to include in results (optional, defaults to low)", "enum": ["low", "medium", "high", "critical"], "type": "string"}}}}], "modified": [], "removed": [{{"name": "files", "required": false, "schema": {{"description": "Files to process (optional for project-level)", "items": {{"type": "string"}}, "type": "array"}}}}, {{"name": "language", "required": false, "schema": {{"description": "Response language (optional, auto-detects from user input)", "enum": ["en", "es"], "type": "string"}}}}], "renamed": []}}

### Tool @kazuph/mcp-taskmanager / request_planning
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Updated description guidance: ["Register a new user request and plan its associated tasks with priority levels and optional deadline tracking. You must provide 'originalRequest', 'splitDetails', 'tasks', 'priority', and 'tags'. Optionally provide 'estimatedDeadline' for time-sensitive requests.", "Validation rules: 'originalRequest' must be 20-1500 characters and 'splitDetails' must be 15-2000 characters after trimming. 'tasks' must contain 1 to 50 items. Each task title must be 3-120 characters, each description 5-2000 characters, and task titles must be unique within the request. 'priority' must be one of: 'low', 'medium', 'high', 'critical'. 'tags' must contain 1 to 10 unique values, each 2-30 characters after trimming. 'estimatedDeadline' may be either a valid ISO 8601 datetime string or a YYYY-MM-DD date string, and if provided it must be in the future.", "This tool initiates a priority-aware workflow for handling user requests. The workflow is as follows:", "1. Use 'request_planning' to register a request with its priority level and tasks.", "2. After adding tasks, you MUST use 'get_next_task' to retrieve the first task (now prioritized by request priority). A progress table will be displayed.", "The critical point is to always wait for user approval after completing each task and after all tasks are done, wait for request completion approval. Do not proceed automatically. High-priority requests will be surfaced first in multi-request scenarios."]
Changed parameter contract (current values under after): {{"added": [{{"name": "assignee", "required": false, "schema": {{"maxLength": 100, "minLength": 1, "type": "string"}}}}, {{"name": "dependencies", "required": false, "schema": {{"items": {{"maxLength": 50, "minLength": 1, "type": "string"}}, "maxItems": 20, "type": "array"}}}}, {{"name": "estimatedDeadline", "required": false, "schema": {{"description": "ISO 8601 datetime or YYYY-MM-DD date string in the future", "type": "string"}}}}, {{"name": "notificationPreferences", "required": false, "schema": {{"properties": {{"onDeadlineApproaching": {{"type": "boolean"}}, "onRequestComplete": {{"type": "boolean"}}, "onTaskComplete": {{"type": "boolean"}}}}, "type": "object"}}}}, {{"name": "priority", "required": true, "schema": {{"enum": ["low", "medium", "high", "critical"], "type": "string"}}}}, {{"name": "tags", "required": true, "schema": {{"items": {{"maxLength": 30, "minLength": 2, "type": "string"}}, "maxItems": 10, "minItems": 1, "type": "array"}}}}], "modified": [{{"after": {{"maxLength": 1500, "minLength": 20, "type": "string"}}, "before": {{"type": "string"}}, "name": "originalRequest", "required_after": true, "required_before": true}}, {{"after": {{"maxLength": 2000, "minLength": 15, "type": "string"}}, "before": {{"type": "string"}}, "name": "splitDetails", "required_after": true, "required_before": false}}, {{"after": {{"items": {{"properties": {{"description": {{"maxLength": 2000, "minLength": 5, "type": "string"}}, "title": {{"maxLength": 120, "minLength": 3, "type": "string"}}}}, "required": ["title", "description"], "type": "object"}}, "maxItems": 50, "minItems": 1, "type": "array"}}, "before": {{"items": {{"properties": {{"description": {{"type": "string"}}, "title": {{"type": "string"}}}}, "required": ["title", "description"], "type": "object"}}, "type": "array"}}, "name": "tasks", "required_after": true, "required_before": true}}], "removed": [], "renamed": []}}
Current required fields: ["originalRequest", "splitDetails", "tasks", "priority", "tags"]

### Tool @magicuidesign/mcp / getAnimations
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Provides detailed implementation data for blur-fade components in the Animations category. Use getComponentIndex first if you need a categorized discovery overview before fetching full component code and examples. If you only need a selecte"

### Tool @magicuidesign/mcp / getBackgrounds
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Provides detailed implementation data for warp-background, flickering-grid, animated-grid-pattern, retro-grid, ripple, dot-pattern, grid-pattern, interactive-grid-pattern components in the Backgrounds category. Use getComponentIndex first i"

### Tool @magicuidesign/mcp / getButtons
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Provides detailed implementation data for rainbow-button, shimmer-button, shiny-button, interactive-hover-button, animated-subscribe-button, pulsating-button, ripple-button components in the Buttons category. Use getComponentIndex first if "

### Tool @magicuidesign/mcp / getComponentDetails
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Retrieves comprehensive implementation details for a single Magic UI component by name, including full source code, installation instructions, and all associated examples. Use this when you already know one component name (e.g., from search"

### Tool @magicuidesign/mcp / getComponentIndex
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Provides a full categorized index of Magic UI components with example coverage counts to help clients discover components by category. Use searchComponents for keyword/category-filtered queries. Once you identify components, call getCompone"

### Tool @magicuidesign/mcp / getComponents
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Provides detailed implementation data for marquee, terminal, hero-video-dialog, bento-grid, animated-list, dock, globe, tweet-card, client-tweet-card, orbiting-circles, avatar-circles, icon-cloud, animated-circular-progress-bar, file-tree, "

### Tool @magicuidesign/mcp / getComponentsByNames
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Retrieves comprehensive implementation details for multiple known Magic UI components in a single request, including full source code, installation instructions, and associated examples for each found component. Use this after getComponentI"

### Tool @magicuidesign/mcp / getDeviceMocks
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Provides detailed implementation data for safari, iphone-15-pro, android components in the DeviceMocks category. Use getComponentIndex first if you need a categorized discovery overview before fetching full component code and examples. If y"

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
This tool is newly available. Purpose: "Provides the complete raw catalog of all Magic UI components without implementation code or examples. For discovery, use getComponentIndex (categorized overview) or searchComponents (keyword/category filtering). To fetch full implementation"

### Tool @magicuidesign/mcp / listRegistryItems
This tool was removed from this connected server. Do not call its old name. Select an available tool only if its documented capability fits the task; do not invent a replacement.

### Tool @magicuidesign/mcp / searchComponents
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Searches Magic UI components by keyword (matched against name and description) with an optional category filter. Returns matching components with their category assignments and example counts. After finding relevant components, use getCompo"

### Tool @magicuidesign/mcp / searchRegistryItems
This tool was removed from this connected server. Do not call its old name. Select an available tool only if its documented capability fits the task; do not invent a replacement.

### Tool @rtuin/mcp-mermaid-validator / validateMermaid
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [{{"name": "backgroundColor", "required": false, "schema": {{"type": "string"}}}}, {{"name": "config", "required": false, "schema": {{"anyOf": [{{"type": "string"}}, {{"additionalProperties": {{}}, "type": "object"}}]}}}}, {{"name": "height", "required": false, "schema": {{"maximum": 10000, "minimum": 1, "type": "integer"}}}}, {{"name": "scale", "required": false, "schema": {{"maximum": 10, "minimum": 1, "type": "number"}}}}, {{"name": "theme", "required": false, "schema": {{"enum": ["default", "dark", "forest", "neutral"], "type": "string"}}}}, {{"name": "width", "required": false, "schema": {{"maximum": 10000, "minimum": 1, "type": "integer"}}}}], "modified": [{{"after": {{"maxLength": 50000, "minLength": 1, "type": "string"}}, "before": {{"type": "string"}}, "name": "diagram", "required_after": true, "required_before": true}}, {{"after": {{"enum": ["svg", "png"], "type": "string"}}, "before": {{"default": "png", "enum": ["svg", "png"], "type": "string"}}, "name": "format", "required_after": true, "required_before": false}}], "removed": [], "renamed": []}}
Current required fields: ["diagram", "format"]

### Tool coffee-mcp-agent / checkOrderEstimate
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "\u6839\u636e\u5546\u54c1\u540d\u79f0\u3001\u89c4\u683c\u548c\u6570\u91cf\u9884\u4f30\u8ba2\u5355\u603b\u4ef7\u53ca\u5236\u4f5c\u65f6\u95f4\uff0c\u4e0b\u5355\u524d\u786e\u8ba4\u8d39\u7528"

### Tool coffee-mcp-agent / orderCoffee
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [{{"name": "contactPhone", "required": false, "schema": {{"description": "\u8054\u7cfb\u7535\u8bdd\uff0c\u9009\u586b\uff0c\u7528\u4e8e\u53d6\u9910\u8054\u7cfb", "type": "string"}}}}, {{"name": "extraShot", "required": false, "schema": {{"description": "\u662f\u5426\u52a0\u6d53\u7f29\uff0c\u9009\u586b\uff0ctrue \u8868\u793a\u6bcf\u676f\u52a0 1 \u4efd\u6d53\u7f29\u5e76\u589e\u52a0\u8d39\u7528", "type": "boolean"}}}}, {{"name": "iceLevel", "required": false, "schema": {{"description": "\u51b0\u91cf\u8981\u6c42\uff0c\u9009\u586b\uff0c\u4f8b\u5982\uff1a\u53bb\u51b0\u3001\u5c11\u51b0\u3001\u6b63\u5e38\u51b0", "type": "string"}}}}, {{"name": "milkType", "required": false, "schema": {{"description": "\u5976\u578b\u9009\u62e9\uff0c\u9009\u586b\uff0c\u4f8b\u5982\uff1a\u5168\u8102\u5976\u3001\u71d5\u9ea6\u5976\u3001\u8131\u8102\u5976", "type": "string"}}}}, {{"name": "note", "required": false, "schema": {{"description": "\u8ba2\u5355\u5907\u6ce8\uff0c\u9009\u586b\uff0c\u4f8b\u5982\uff1a\u5c11\u7cd6\u3001\u5c3d\u5feb\u5236\u4f5c", "type": "string"}}}}, {{"name": "packagingPreference", "required": false, "schema": {{"description": "\u5305\u88c5\u504f\u597d\uff0c\u9009\u586b\uff0c\u4f8b\u5982\uff1a\u5802\u98df\u676f\u3001\u5916\u5e26\u676f", "type": "string"}}}}, {{"name": "pickupTime", "required": false, "schema": {{"description": "\u53d6\u9910\u65f6\u95f4\uff0c\u9009\u586b\uff0c\u4f8b\u5982\uff1a\u7acb\u5373\u5236\u4f5c\u300118:30 \u53d6\u9910", "type": "string"}}}}, {{"name": "quantity", "required": false, "schema": {{"description": "\u8d2d\u4e70\u676f\u6570\uff0c\u9009\u586b\uff0c\u9ed8\u8ba4\u4e3a1", "type": "integer"}}}}, {{"name": "sweetness", "required": false, "schema": {{"description": "\u751c\u5ea6\u8981\u6c42\uff0c\u9009\u586b\uff0c\u4f8b\u5982\uff1a\u65e0\u7cd6\u3001\u5c11\u7cd6\u3001\u534a\u7cd6\u3001\u5168\u7cd6", "type": "string"}}}}], "modified": [], "removed": [], "renamed": []}}
Current required fields: ["productName", "spec"]

### Tool mcp-calculator / break_even_analysis
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "\u8ba1\u7b97\u5355\u4f4d\u8d21\u732e\u6bdb\u76ca\u3001\u8d21\u732e\u6bdb\u76ca\u7387\u3001\u76c8\u4e8f\u5e73\u8861\u9500\u91cf/\u9500\u552e\u989d\uff0c\u4ee5\u53ca\u76ee\u6807\u5229\u6da6\u6240\u9700\u9500\u91cf\uff0c\u9002\u7528\u4e8e\u6210\u672c\u7ed3\u6784\u4e0e\u7ecf\u8425\u51b3\u7b56\u5206\u6790"

### Tool mcp-calculator / loan_payment
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Updated description guidance: ["\u8ba1\u7b97\u7b49\u989d\u672c\u606f\u8d37\u6b3e\u5728\u4e0d\u540c\u8fd8\u6b3e\u9891\u7387\u4e0b\u7684\u6bcf\u671f\u8fd8\u6b3e\u91d1\u989d\uff0c\u9002\u7528\u4e8e\u8d37\u6b3e\u878d\u8d44\u4e0e\u8fd8\u6b3e\u89c4\u5212\u573a\u666f"]
Changed parameter contract (current values under after): {{"added": [{{"name": "extra_payment", "required": false, "schema": {{"default": 0, "description": "\u6bcf\u671f\u989d\u5916\u8fd8\u6b3e\u91d1\u989d\uff08\u9ed8\u8ba40\uff09", "minimum": 0, "type": "number"}}}}, {{"name": "include_schedule", "required": false, "schema": {{"default": false, "description": "\u662f\u5426\u5305\u542b\u7b80\u8981\u8fd8\u6b3e\u8fdb\u5ea6\u6458\u8981", "type": "boolean"}}}}, {{"name": "payment_frequency", "required": false, "schema": {{"default": 12, "description": "\u6bcf\u5e74\u8fd8\u6b3e\u6b21\u6570\uff08\u9ed8\u8ba412\uff0c12=\u6309\u6708\uff0c4=\u6309\u5b63\uff0c1=\u6309\u5e74\uff09", "exclusiveMinimum": 0, "type": "integer"}}}}], "modified": [], "removed": [], "renamed": []}}
Current required fields: ["loan_amount", "annual_rate", "years"]

### Tool mcp-calculator / net_present_value
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Updated description guidance: ["\u8ba1\u7b97\u6295\u8d44\u9879\u76ee\u7684\u51c0\u73b0\u503c\uff08NPV\uff09\uff0c\u7528\u4e8e\u57fa\u4e8e\u6298\u73b0\u73b0\u91d1\u6d41\u7684\u6295\u8d44\u53ef\u884c\u6027\u8bc4\u4f30\uff0c\u4e0e\u8fd0\u8425\u5c42\u9762\u7684\u76c8\u4e8f\u5e73\u8861\u5206\u6790\u5f62\u6210\u4e92\u8865"]

### Tool mcp-calculator / percentage_calculator
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "\u6267\u884c\u901a\u7528\u767e\u5206\u6bd4\u8ba1\u7b97\uff0c\u5305\u62ec\u767e\u5206\u6bd4\u53d8\u5316\u3001\u5360\u6bd4\u3001\u52a0\u4ef7\u3001\u6298\u6263\u7b49\uff0c\u53ef\u4f5c\u4e3a\u8d22\u52a1\u5206\u6790\u4e0e\u7ecf\u8425\u6d4b\u7b97\u7684\u8f85\u52a9\u5de5\u5177"

### Tool mcp-filesystem-server / list_directory
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [{{"name": "reverse", "required": false, "schema": {{"default": false, "description": "Reverse the sort order", "type": "boolean"}}}}, {{"name": "sortBy", "required": false, "schema": {{"default": "default", "description": "Sorting mode: default (directories first), name, or type", "enum": ["default", "name", "type"], "type": "string"}}}}], "modified": [], "removed": [], "renamed": []}}
Current required fields: ["path"]

### Tool mcp-filesystem-server / read_file
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [{{"name": "endLine", "required": false, "schema": {{"description": "Ending line number (1-indexed) for reading a specific range", "type": "number"}}}}, {{"name": "maxSize", "required": false, "schema": {{"description": "Maximum file size in bytes to read (default: no limit)", "type": "number"}}}}, {{"name": "startLine", "required": false, "schema": {{"description": "Starting line number (1-indexed) for reading a specific range", "type": "number"}}}}], "modified": [], "removed": [], "renamed": []}}
Current required fields: ["path"]

### Tool mcp-filesystem-server / read_multiple_files
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [{{"name": "ignoreErrors", "required": false, "schema": {{"default": false, "description": "Silently skip files that cannot be read instead of including error messages", "type": "boolean"}}}}, {{"name": "includeMetadata", "required": false, "schema": {{"default": false, "description": "Prepend file metadata (size, last modified) before each file's content", "type": "boolean"}}}}, {{"name": "separator", "required": false, "schema": {{"default": "---", "description": "Separator string inserted between file contents (default: '---')", "type": "string"}}}}], "modified": [], "removed": [], "renamed": []}}
Current required fields: ["paths"]

### Tool mcp-server-commands / run_process
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Updated description guidance: ["Run a process on this darwin machine,                         oneOf: [", "                            {{", "                                properties: {{ mode: {{ const: \"shell\" }} }},", "                                required: [\"command_line\"],", "                                not: {{ required: [\"argv\"] }}", "                            }},", "                            {{", "                                properties: {{ mode: {{ const: \"executable\" }} }},", "                                required: [\"argv\"],", "                                not: {{ required: [\"command_line\"] }}", "                            }}", "                        ]"]
Changed parameter contract (current values under after): {{"added": [{{"name": "capture_output", "required": false, "schema": {{"description": "Optional output capture mode: 'full' (default, capture all), 'truncated' (limit to 10KB per stream), or 'none' (discard output).", "enum": ["full", "truncated", "none"], "type": "string"}}}}, {{"name": "dry_run", "required": false, "schema": {{"description": "Optional explain what would run, defaults to False.", "type": "boolean"}}}}, {{"name": "env", "required": false, "schema": {{"additionalProperties": {{"type": "string"}}, "description": "Optional environment variables as key-value pairs, merged with current process environment.", "type": "object"}}}}, {{"name": "kill_signal", "required": false, "schema": {{"description": "Optional signal to send on timeout: 'SIGTERM' (default), 'SIGKILL', or 'SIGINT'.", "enum": ["SIGTERM", "SIGKILL", "SIGINT"], "type": "string"}}}}, {{"name": "max_output_bytes", "required": false, "schema": {{"description": "Optional maximum bytes to capture from stdout/stderr combined, overrides capture_output truncation behavior", "maximum": 104857600, "minimum": 1, "type": "integer"}}}}, {{"name": "memory_limit_mb", "required": false, "schema": {{"description": "Optional memory limit in megabytes for the spawned process, enforcement is platform-dependent", "maximum": 16384, "minimum": 1, "type": "integer"}}}}, {{"name": "mode", "required": true, "schema": {{"description": "What are you running, two choices: 'shell' or 'executable' (required, no default)", "enum": ["shell", "executable"]}}}}], "modified": [{{"after": {{"description": "Executable and arguments. argv[0] is the executable. Required when mode='executable'. Forbidden when mode='shell'.", "items": {{"minLength": 1, "type": "string"}}, "minItems": 1, "type": "array"}}, "before": {{"description": "Executable mode: directly spawn a process. argv[0] is the executable, followed by arguments passed verbatim (no shell interpretation). Cannot be combined with 'command_line'.", "items": {{"type": "string"}}, "minItems": 1, "type": "array"}}, "name": "argv", "required_after": false, "required_before": false}}, {{"after": {{"description": "Shell command line. Required when mode='shell'. Forbidden when mode='executable'.", "minLength": 1, "type": "string"}}, "before": {{"description": "Shell mode: a shell command line executed via the system's default shell. Supports pipes, redirects, globbing. Cannot be combined with 'argv'.", "type": "string"}}, "name": "command_line", "required_after": false, "required_before": false}}, {{"after": {{"description": "Working directory. Required and must be a non-empty string.", "minLength": 1, "type": "string"}}, "before": {{"description": "Optional to set working directory", "type": "string"}}, "name": "cwd", "required_after": true, "required_before": false}}, {{"after": {{"description": "Optional timeout in milliseconds, must be an integer between 1 and 300000, defaults to 30,000ms", "maximum": 300000, "minimum": 1, "type": "integer"}}, "before": {{"description": "Optional timeout in milliseconds, defaults to 30,000ms", "type": "number"}}, "name": "timeout_ms", "required_after": false, "required_before": false}}], "removed": [], "renamed": [{{"after": {{"name": "stdin", "required": false, "schema": {{"description": "Optional text written to STDIN (written fully, then closed). Useful for heredoc-style input or file contents.", "type": "string"}}}}, "before": {{"name": "stdin_text", "required": false, "schema": {{"description": "Optional text written to STDIN (written fully, then closed). Useful for heredoc-style input or file contents.", "type": "string"}}}}}}]}}
Current required fields: ["mode", "cwd"]

### Tool mcp-tung-shing / get-tung-shing
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [], "modified": [{{"after": {{"default": "2026-10-13", "description": "\u5f00\u59cb\u65e5\u671f\uff0c\u683c\u5f0f\u4e3a\"YYYY-MM-DD\"\u7684\u5b57\u7b26\u4e32", "type": "string"}}, "before": {{"default": "2026-10-11", "description": "\u5f00\u59cb\u65e5\u671f\uff0c\u683c\u5f0f\u4e3a\"YYYY-MM-DD\"\u7684\u5b57\u7b26\u4e32", "type": "string"}}, "name": "startDate", "required_after": false, "required_before": false}}], "removed": [], "renamed": []}}

### Tool mcp-weather-demo / get-forecast
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [{{"name": "includeDetails", "required": false, "schema": {{"description": "Whether to include detailed lines such as wind information", "type": "boolean"}}}}, {{"name": "periods", "required": false, "schema": {{"description": "Maximum number of forecast periods to return", "exclusiveMinimum": 0, "type": "integer"}}}}], "modified": [], "removed": [], "renamed": []}}
Current required fields: ["latitude", "longitude"]

### Tool mcp-weather-demo / get-weather-advice
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
This tool is newly available. Purpose: "Get practical weather advice for a location and activity"

### Tool time-mcp / convert_time
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [], "modified": [{{"after": {{"type": "string"}}, "before": {{"description": "The source timezone. IANA timezone name, e.g. Asia/Shanghai", "type": "string"}}, "name": "sourceTimezone", "required_after": true, "required_before": true}}, {{"after": {{"type": "string"}}, "before": {{"description": "The target timezone. IANA timezone name, e.g. Europe/London", "type": "string"}}, "name": "targetTimezone", "required_after": true, "required_before": true}}, {{"after": {{"type": "string"}}, "before": {{"description": "Date and time in 24-hour format. e.g. 2025-03-23 12:30:00", "type": "string"}}, "name": "time", "required_after": true, "required_before": true}}], "removed": [], "renamed": []}}
Current required fields: ["sourceTimezone", "targetTimezone", "time"]

### Tool time-mcp / current_time
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [], "modified": [{{"after": {{"default": "YYYY-MM-DD HH:mm:ss", "enum": ["h:mm A", "h:mm:ss A", "YYYY-MM-DD HH:mm:ss", "YYYY-MM-DD", "YYYY-MM", "MM/DD/YYYY", "MM/DD/YY", "YYYY/MM/DD", "YYYY/MM"], "type": "string"}}, "before": {{"default": "YYYY-MM-DD HH:mm:ss", "description": "The format of the time", "enum": ["h:mm A", "h:mm:ss A", "YYYY-MM-DD HH:mm:ss", "YYYY-MM-DD", "YYYY-MM", "MM/DD/YYYY", "MM/DD/YY", "YYYY/MM/DD", "YYYY/MM"], "type": "string"}}, "name": "format", "required_after": false, "required_before": false}}, {{"after": {{"type": "string"}}, "before": {{"description": "The timezone of the time, IANA timezone name, e.g. Asia/Shanghai", "type": "string"}}, "name": "timezone", "required_after": false, "required_before": false}}], "removed": [], "renamed": []}}

### Tool time-mcp / days_in_month
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [], "modified": [{{"after": {{"type": "string"}}, "before": {{"description": "The date to get the days in month. Format: YYYY-MM-DD", "type": "string"}}, "name": "date", "required_after": false, "required_before": false}}], "removed": [], "renamed": []}}

### Tool time-mcp / get_timestamp
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [], "modified": [{{"after": {{"type": "string"}}, "before": {{"description": "The time to get the timestamp. Format: YYYY-MM-DD HH:mm:ss.SSS", "type": "string"}}, "name": "time", "required_after": false, "required_before": false}}], "removed": [], "renamed": []}}

### Tool time-mcp / get_week_year
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [], "modified": [{{"after": {{"type": "string"}}, "before": {{"description": "The date to get the week and isoWeek of the year. e.g. 2025-03-23", "type": "string"}}, "name": "date", "required_after": false, "required_before": false}}], "removed": [], "renamed": []}}

### Tool time-mcp / relative_time
Use the current tools/list description and schema as authority for this tool. Do not apply old arguments or guidance that conflict with them.
Changed parameter contract (current values under after): {{"added": [], "modified": [{{"after": {{"type": "string"}}, "before": {{"description": "The time to get the relative time from now. Format: YYYY-MM-DD HH:mm:ss", "type": "string"}}, "name": "time", "required_after": true, "required_before": true}}], "removed": [], "renamed": []}}
Current required fields: ["time"]

## Routing reference

The upstream agent selects the server for a requested tool through `tool_server_map[tool_name]`, converts the selected tool to `<server>_1mcp_<tool>`, and sends it to the configured 1MCP endpoint. Tool results are appended as `role=tool` messages with the original tool-call ID. If the model returns ordinary text without a tool call, the agent reminds it to call a tool directly and stops after three consecutive no-tool responses.

This section documents the runtime routing implemented in `src/custom/agents/SimpleOpenAIAgent.py`. Only the text under `Injected rules` is added to the resolved system prompt, and duplicate text already present in `system_prompt.md` is not added twice.
