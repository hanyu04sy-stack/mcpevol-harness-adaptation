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
- 可用性报告：`reports/environment-validation.json`

任务不再只因为 server 出现在配置文件中就入选。只有当它需要的所有 server 在 Early/Middle/Late 三版中都是 `connected` 时，才进入候选池。

生成结果包含：

- `test_cases.json`：真正交给 benchmark 的任务文件
- `manifest.json`：源文件哈希、选中任务 idx、affected/retention 数量和变化类型覆盖情况

三种策略必须使用同一个生成结果，不能各自重新抽样。

重建命令：

```bash
.venv/bin/python scripts/build_subset.py \
  --benchmark-root external/MCPEvol-Bench \
  --size 30 --seed 6203 --affected-fraction 0.8 \
  --availability-report reports/environment-validation.json \
  --output-dir data/subsets/pilot-30
```

当前结果为 24 affected + 6 retention，覆盖 17 个 description、23 个 parameter 和 20 个 tool change 任务。

覆盖性不需要人工数 manifest，直接执行：

```bash
.venv/bin/python scripts/validate_subset_coverage.py
```

该命令同时核对任务 ID、required server、affected/retention 标签和汇总计数，产生机器可读的 `reports/pilot-30-coverage.json`。

## 任务可运行矩阵

```bash
.venv/bin/python scripts/build_runnability_matrix.py
```

矩阵逐题记录 `required_servers`，以及每个版本中这些 server 的实际状态。任意一题在任意一版有依赖不是 `connected`，命令就会返回失败，且 `check_experiment_config.py` 也会拒绝该配置。

## 从 30 题升级到全量

只有在 30 题已经完整跑通，并确认预算、运行时间和 server 稳定性以后，才切换为全量。升级后应创建新的 experiment name，不能覆盖 pilot 结果。

