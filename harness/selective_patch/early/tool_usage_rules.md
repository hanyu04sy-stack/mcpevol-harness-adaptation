# Tool Usage Rules

## Injected rules

Note that do not to ask any questions to the user, just call the tool to complete the task.

## Routing reference

The upstream agent selects the server for a requested tool through `tool_server_map[tool_name]`, converts the selected tool to `<server>_1mcp_<tool>`, and sends it to the configured 1MCP endpoint. Tool results are appended as `role=tool` messages with the original tool-call ID. If the model returns ordinary text without a tool call, the agent reminds it to call a tool directly and stops after three consecutive no-tool responses.

This section documents the runtime routing implemented in `src/custom/agents/SimpleOpenAIAgent.py`. Only the text under `Injected rules` is added to the resolved system prompt, and duplicate text already present in `system_prompt.md` is not added twice.
