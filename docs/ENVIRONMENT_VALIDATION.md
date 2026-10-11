# Early / Middle / Late 环境验证结果

验证日期：2026-10-10（Asia/Shanghai）。三个版本均成功启动 1MCP 聚合端点，并完整识别到各自配置的 59 个 server。

| 版本 | 启动结果 | 可用 server | 未可用 server | 可用 tool |
|---|---:|---:|---:|---:|
| Early | 成功 | 47 | 12 | 520 |
| Middle | 成功 | 55 | 4 | 602 |
| Late | 成功 | 54 | 5 | 640 |

Early 在 15 分钟采样上限时仍有 3 个 server 处于 `loading`，已作为未可用项记录：`@assistant-ui/mcp-docs-server`、`mcp-maven-deps`、`xcomet-mcp-server`。其余未可用 server 均已进入 `failed` 终态。

首次检查时 Late 只有 23 个 server 可用。根因是 macOS 将已解压依赖变成了逻辑大小仍在、实际数据为空的 dataless 文件。从已通过 SHA-256 校验的 bundle 恢复 20,027 个文件后，Late 提升至 54/59 server。

完整 59-server 失败清单、原始状态和失败原因见 [`reports/environment-validation.json`](../reports/environment-validation.json)。正式 30 题子集的精确验证见 [`reports/pilot-30-environment-validation.json`](../reports/pilot-30-environment-validation.json)：Early/Middle/Late 均为 26/26 server 连接、0 失败，tool 数分别为 304/311/318。

## 重复冷启动结果

Early/Middle/Late 各重复启动 3 次，每次均创建新的 1MCP 进程并在采样后关闭：

| 版本 | 成功次数 | 每次连接 | 失败 | 波动 server |
|---|---:|---:|---:|---:|
| Early | 3/3 | 26/26 | 0 | 0 |
| Middle | 3/3 | 26/26 | 0 | 0 |
| Late | 3/3 | 26/26 | 0 | 0 |

逐轮、逐 server 状态见 [`reports/pilot-30-startup-stability.json`](../reports/pilot-30-startup-stability.json)。正式配置锁定该报告的 SHA-256；少于 3 轮、出现任何失败、波动 server 或报告与当前 server 配置不一致时，配置检查会直接失败。

成员 A 需要重做稳定性验证时执行：

```bash
.venv/bin/python scripts/validate_startup_stability.py --trials 3
```

重做会产生新的实验时间和 SHA-256，应由成员 A 审核后同步更新正式配置；B/C/D 直接使用已锁定的报告，无需在每次正式实验前重跑9次冷启动。
