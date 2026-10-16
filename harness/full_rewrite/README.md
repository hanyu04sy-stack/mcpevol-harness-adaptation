# Full Rewrite Harness

Member B's completed Full Rewrite knowledge is stored in `system_prompt.md`,
`tool_usage_rules.md`, and `manifest.json`. The final experiment uses the
materialized `early/`, `middle/`, and `late/` copies. They contain the same
generic replacement rules and defer to the live tool list; they are not
schema-generated version-specific prose. See `docs/D_EVALUATION.md` for the
evaluated definition and limitations.

Do not modify the benchmark checkout, fixed task set, model settings, judge settings, or MCP version mapping.
