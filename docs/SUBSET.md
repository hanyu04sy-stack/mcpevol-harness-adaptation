# 固定任务子集方案

## 为什么先用 30 题

完整 benchmark 会启动大量 MCP servers，并产生较高的模型、judge、时间和 API 成本。Case 允许在算力有限时使用固定且有记录的子集，因此第一阶段先建立 30 题开发集。

## 子集必须同时测两件事

- Recovery：约 24 个任务涉及发生变化的 server。
- Retention：约 6 个任务不涉及已知变化，用来观察更新是否误伤旧能力。

受影响任务会尽量覆盖：

- Tool-level change
- Parameter-level change
- Description-level change

一个任务可以同时属于多种变化类型。

## 可复现性

生成器固定使用：

- size：30
- seed：6203
- 上游 commit：`888c779a0fe735f612ca62bdd1fdd7c9e6bf8701`

生成结果包含：

- `test_cases.json`：真正交给 benchmark 的任务文件
- `manifest.json`：源文件哈希、选中任务 idx、affected/retention 数量和变化类型覆盖情况

三种策略必须使用同一个生成结果，不能各自重新抽样。

## 从 30 题升级到全量

只有在 30 题已经完整跑通，并确认预算、运行时间和 server 稳定性以后，才切换为全量。升级后应创建新的 experiment name，不能覆盖 pilot 结果。

