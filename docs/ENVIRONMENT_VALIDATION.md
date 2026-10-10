# Early / Middle / Late 环境验证结果

验证日期：2026-10-10（Asia/Shanghai）。三个版本均成功启动 1MCP 聚合端点，并完整识别到各自配置的 59 个 server。

| 版本 | 启动结果 | 可用 server | 未可用 server | 可用 tool |
|---|---:|---:|---:|---:|
| Early | 成功 | 47 | 12 | 520 |
| Middle | 成功 | 55 | 4 | 602 |
| Late | 成功 | 23 | 36 | 206 |

Early 在 15 分钟采样上限时仍有 3 个 server 处于 `loading`，已作为未可用项记录：`@assistant-ui/mcp-docs-server`、`mcp-maven-deps`、`xcomet-mcp-server`。其余未可用 server 均已进入 `failed` 终态。

完整失败清单、每个 server 的原始状态、失败原因和计数见 [`reports/environment-validation.json`](../reports/environment-validation.json)。未可用 server 不代表聚合环境未启动；它们主要是上游 server 包、运行时或外部服务不兼容，已保留在报告中供后续成员筛选固定任务子集时使用。
