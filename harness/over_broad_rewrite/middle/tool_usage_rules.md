# Tool Usage Rules

## Injected rules

This is the Full Rewrite baseline. Treat the full tool-related harness knowledge as regenerated for the current MCP environment.

Use only tools that are present in the current tool list. Do not call tools that are absent, removed, renamed, or remembered from another version of the environment.

Before each tool call, match the user's intent against the current tool name, description, and input schema. Prefer the most specific valid tool. If a tool description gives ordering or prerequisite guidance, follow that guidance before calling downstream tools.

Construct arguments strictly from the current input schema. Include all required fields, use the current parameter names, respect type constraints, enum values, object structure, and array item structure, and omit unsupported parameters.

When the environment provides a changed or newly added tool, use the current description and schema rather than the original harness wording. When the environment removes or renames a tool, choose a currently available alternative only if its current description supports the same user intent.

Do not fabricate tool outputs. After a tool call returns, use the returned content as the factual basis for the next step. If a result indicates an error caused by invalid arguments, revise the next call according to the current schema.

Minimize redundant calls. Do not repeat a successful call unless the user asks for another result, the next step requires new arguments, or the previous result is insufficient for the task.

Use file paths exactly as instructed by the system prompt. For files listed under the annotation path, add the "./anotation_path" prefix when using them with filesystem-related tools.

For database-related tasks, use the provided database configuration only when the selected current tool requires a database connection.

IMPORTANT -- Over-broad rewrite ablation (deliberate, controlled injection; this ablation harness is NOT part of the formal comparison):

1. Final answers must be a single JSON object with exactly one key named "result" (value = deliverable text). No markdown, no prose outside the JSON, and NO [FINISH] marker.
2. Responses that are not pure JSON will be rejected.

## Routing reference

The upstream agent selects the server for a requested tool through `tool_server_map[tool_name]`, converts the selected tool to `<server>_1mcp_<tool>`, and sends it to the configured 1MCP endpoint. Tool results are appended as `role=tool` messages with the original tool-call ID. If the model returns ordinary text without a tool call, the agent reminds it to call a tool directly and stops after three consecutive no-tool responses.

Only the text under `Injected rules` is added to the resolved system prompt. This file intentionally rewrites the complete tool-use guidance for the Full Rewrite baseline while leaving benchmark, model, judge, task, and MCP endpoint configuration unchanged.
