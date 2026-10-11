# Benchmark 环境搭建说明

## 1. 为什么锁定版本

MCPEvol-Bench 仍在更新。为了保证三种策略的分数可以比较，本项目固定使用提交：

```text
888c779a0fe735f612ca62bdd1fdd7c9e6bf8701
```

如果之后升级 benchmark，必须新建实验批次，不能把新旧版本结果混在同一张表里。

## 2. 三个版本怎样对应

| Case 名称 | 上游目录 | 含义 |
|---|---|---|
| Early | `servers/1mcp_config/original` | 初始工具环境 |
| Middle | `servers/1mcp_config/iter3` | 第一次持续变化后的环境 |
| Late | `servers/1mcp_config/iter5` | 第二次持续变化后的环境 |

## 3. 安装顺序

先安装 Python 3.12、Node.js 24 和 pnpm 11.25，然后在项目根目录只运行：

```bash
python3 scripts/setup_environment.py
```

脚本会依次完成：锁定上游代码、创建 `.venv`、安装精简且固定的 Python 依赖、安装 1mcp、下载/校验/解压 server bundles、生成三个本机配置，最后执行严格自检。

上游 `requirements.txt` 同时包含 CUDA/NVIDIA 专用包，不能在 macOS 上直接使用。本项目改用 `requirements/benchmark.txt`：仅保留远程 OpenAI-compatible tool-level benchmark 所需依赖，并固定版本，因此同时支持 macOS 和 Linux。

单独验证下载档案（不联网、不解压）：

```bash
python3 scripts/download_server_bundles.py --verify-only
```

一键严格检查：

```bash
.venv/bin/python scripts/check_environment.py --strict
```

如果检查失败，按 [macOS / Linux 故障排查手册](TROUBLESHOOTING.md) 处理端口占用、版本、SHA-256 或 server 加载问题。

## 4. 当前机器检查结果

本次初始化时已经确认：

- 可用 Python：3.12.14
- 可用 Node.js：24.19.0
- 可用 pnpm：11.25.0
- `1mcp`：项目本地固定为 0.38.2
- iter3/iter5 evolution server bundles：已下载、SHA-256 校验通过并解压

因此可复现安装阶段已完成；下一阶段是实际启动并验证 Early/Middle/Late 三个环境。

## 5. 工具环境验证

以隔离端口依次启动三个环境，等待 server 进入 connected/failed 状态；若个别 server 一直卡在 loading，则在 15 分钟上限后把它记为未可用，并生成机器可读报告：

```bash
.venv/bin/python scripts/validate_tool_environments.py
```

报告位于 `reports/environment-validation.json`，包含每个版本的 server 数、tool 数、连接状态、失败清单和失败原因。原始日志位于 `logs/environment-validation/`，不提交 Git。

本次实测结果和已知失败项见 [ENVIRONMENT_VALIDATION.md](ENVIRONMENT_VALIDATION.md)。

## 6. 公平比较规则

每次正式实验都要保存一份填写完成的配置文件。No-update、Full-rewrite、Selective-patch 只能改变 harness 内容，以下项目必须完全相同：

- benchmark commit
- Early/Middle/Late server bundle
- test case JSON 及其 SHA-256
- model 名称和参数
- judge 名称和参数
- 运行次数
- MCP host/port 设置

## 7. 已发现的版本差异

Case 文档写的是 201 个任务，但当前锁定的公开仓库中 `test_cases.json` 实际包含 393 个任务。这不是代码错误，而是课程说明与公开仓库版本之间的差异。报告中必须写明实际使用的仓库提交、任务数量和固定子集清单。
