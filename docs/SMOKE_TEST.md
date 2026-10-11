# MCPEvol-Bench smoke test 报告

## 测试范围

本次使用固定任务 `idx=161`，仅启动在 Early、Middle、Late 中都已验证可用的两个 server：`@likec4/mcp` 和 `time`。任务依次调用：

1. `list-projects`；
2. `read-project-summary`；
3. `search-element`；
4. `convert_time`。

为了不使用真实 API key、不产生费用并保证可重复，smoke test 使用脚本内置的确定性 OpenAI-compatible 本地模型。该模型只负责按固定顺序发出 tool call；工具调用仍由真实 MCPEvol-Bench、1MCP 和 MCP server 执行。

## 实测结果

最终复验时间：2026-10-11 09:11（Asia/Shanghai）。

| 版本 | 结果 | server | tools | 完成 tool call | tool error | 耗时 |
|---|---:|---:|---:|---:|---:|---:|
| Early | 通过 | 2/2 | 22 | 4/4 | 0 | 18.738s |
| Middle | 通过 | 2/2 | 22 | 4/4 | 0 | 10.374s |
| Late | 通过 | 2/2 | 22 | 4/4 | 0 | 10.138s |

三个版本的 trajectory 都满足：`stop=true`、`exceeded=false`、4 条 tool response、0 条 tool error。`convert_time` 返回了真实时区转换结果；LikeC4 的示例 workspace 未返回架构元素，但 MCP 协议调用成功完成，不属于运行失败。

机器可读总结位于 [`reports/smoke/summary.json`](../reports/smoke/summary.json)。每个版本目录都保留了：

- `trajectory-161.json`：完整原始 trajectory；
- `benchmark.log`：benchmark 标准输出和标准错误；
- `server.log`：1MCP 和工具调用日志；
- `model-events.json`：本地 smoke model 每次决策的时间和工具名。

## 成功和失败的边界

本次证明了三个版本的安装、启动、模型请求、tool schema 传递、真实 MCP 调用、trajectory 写入和输出分目录全部连通。

它不是正式模型质量得分，也没有使用 judge。完整 30 题、真实模型和三种 harness 的对比属于 B/C/D 的后续实验。完整环境中的上游不可用 server 已单独记录在 [`reports/environment-validation.json`](../reports/environment-validation.json)，不影响这个稳定 smoke 子集。
