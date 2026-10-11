# MCPEvol Harness Adaptation

这是 6203 Case 4 的小组项目仓库。当前第一阶段负责把 MCPEvol-Bench 变成一个可复现、可公平比较的实验环境。

## 当前决定

- 上游基准：[`Octobrist/MCPEvol-Bench`](https://github.com/Octobrist/MCPEvol-Bench)
- 固定上游提交：`888c779a0fe735f612ca62bdd1fdd7c9e6bf8701`
- 三个环境版本：Early=`original`、Middle=`iter3`、Late=`iter5`
- 默认开发集：30 个任务的固定子集，随机种子 `6203`
- 可运行性门槛：任务依赖的 server 必须在 Early/Middle/Late 三版都实际连接成功
- 子集构成：约 80% affected tasks + 20% retention tasks
- 公平性原则：三种 harness 策略必须共用同一个模型、任务文件、推理参数和 judge 配置

选择固定子集是为了先在有限算力下跑通端到端流程。配置仍然支持之后切换到全量任务。

## 目录

```text
configs/                  统一实验配置
docs/                     环境和任务子集说明
scripts/                  环境检查、基准下载、配置生成、子集生成
tests/                    不需要 API key 的本地测试
data/subsets/             固定的 30 题子集和 1 题 smoke 子集
external/MCPEvol-Bench/   bootstrap 后生成，不提交到 Git
generated/                生成的任务子集和 1mcp 配置，不提交到 Git
reports/                  已验证的环境、smoke trajectory 和原始日志
results/                  实验输出，不提交到 Git
```

## 从零开始

要求：macOS/Linux、Python 3.12、Node.js 24 和 pnpm 11.25。其余内容（包括固定版本的 1mcp）由脚本安装。

```bash
python3 scripts/setup_environment.py
```

该命令会锁定 benchmark 提交、创建 `.venv`、安装 macOS/Linux 通用依赖、安装 1mcp、自动下载并校验约 2.2 GB 的 Middle/Late server bundles，再生成 Early/Middle/Late 配置。已存在且校验通过的压缩包会自动跳过下载；脚本会恢复 macOS/iCloud 可能卸载的 dataless 依赖文件。

一键检查：

```bash
.venv/bin/python scripts/check_environment.py --strict
```

详细步骤见 [环境安装](docs/ENVIRONMENT.md)、[任务子集](docs/SUBSET.md)、[统一运行](docs/RUNNING.md)、[smoke 报告](docs/SMOKE_TEST.md) 和 [B/C/D 交接](docs/HANDOFF.md)。

统一配置检查和运行入口：

```bash
.venv/bin/python scripts/validate_subset_coverage.py
.venv/bin/python scripts/build_runnability_matrix.py
.venv/bin/python scripts/check_experiment_config.py
.venv/bin/python scripts/run_benchmark.py --version early --dry-run
```

覆盖检查会对 tool/parameter/description change、affected/recovery 和 retention 五项要求逐项判定，并写入 [`reports/pilot-30-coverage.json`](reports/pilot-30-coverage.json)。任何一项缺失都会以非零状态退出。

任务可运行矩阵位于 [`reports/pilot-30-runnability-matrix.json`](reports/pilot-30-runnability-matrix.json)，记录每道题在 Early/Middle/Late 中的每个 server 依赖状态。配置检查会核对矩阵 SHA-256 和任务 SHA-256；正式运行前还会实时要求所有依赖为 `connected`。

冷启动稳定性报告位于 [`reports/pilot-30-startup-stability.json`](reports/pilot-30-startup-stability.json)。已完成 Early/Middle/Late 各 3 次独立启动，9 次均为 26/26 server 连接、0 失败、0 波动 server。

不需要 API key 的完整端到端自检：

```bash
.venv/bin/python scripts/run_smoke_tests.py
```

已实测 Early、Middle、Late 全部通过：每个版本 2/2 server 连接、4/4 tool call 完成、0 tool error，完整 trajectory 和原始日志位于 [`reports/smoke/`](reports/smoke/)。

## 当前完成度

- [x] 创建公开 GitHub 仓库
- [x] 锁定 benchmark 来源和提交
- [x] 建立统一实验配置
- [x] 建立可复现的固定子集生成器
- [x] 建立 Early/Middle/Late 配置生成器
- [x] 建立环境自检和自动测试
- [x] 建立 macOS/Linux 可复现 Python 安装脚本
- [x] 建立 server bundles 自动下载、断点续传和 SHA-256 校验
- [x] 下载、校验并解压 iter3/iter5 evolution server bundles
- [x] 在项目中固定安装 1mcp 0.38.2
- [x] 建立统一模型与 judge 配置（当前统一使用 `gpt-4o`）
- [x] 安装 benchmark tool-level runner 所需的 Python 依赖
- [x] 启动并验证 Early/Middle/Late 工具环境
- [x] 修复 Late bundle 的 dataless 文件，Late 可用 server 从 23 提升到 54
- [x] 按三版实际连接结果重建 30 题子集，26/26 server 在每个版本全部可用
- [x] Early/Middle/Late 各完成 3 次独立冷启动，所有 server 稳定连接
- [x] 建立安全、统一且真正读取配置的 benchmark 运行入口
- [x] 完成 Early/Middle/Late 小规模端到端 smoke run 并保留 trajectory/log

## 安全说明

不要把 API key 写入 Python 文件或提交到 Git。复制 `.env.example` 为 `.env`，仅在本机填写。
