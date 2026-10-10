# MCPEvol Harness Adaptation

这是 6203 Case 4 的小组项目仓库。当前第一阶段负责把 MCPEvol-Bench 变成一个可复现、可公平比较的实验环境。

## 当前决定

- 上游基准：[`Octobrist/MCPEvol-Bench`](https://github.com/Octobrist/MCPEvol-Bench)
- 固定上游提交：`888c779a0fe735f612ca62bdd1fdd7c9e6bf8701`
- 三个环境版本：Early=`original`、Middle=`iter3`、Late=`iter5`
- 默认开发集：30 个任务的固定子集，随机种子 `6203`
- 子集构成：约 80% affected tasks + 20% retention tasks
- 公平性原则：三种 harness 策略必须共用同一个模型、任务文件、推理参数和 judge 配置

选择固定子集是为了先在有限算力下跑通端到端流程。配置仍然支持之后切换到全量任务。

## 目录

```text
configs/                  统一实验配置
docs/                     环境和任务子集说明
scripts/                  环境检查、基准下载、配置生成、子集生成
tests/                    不需要 API key 的本地测试
external/MCPEvol-Bench/   bootstrap 后生成，不提交到 Git
generated/                生成的任务子集和 1mcp 配置，不提交到 Git
results/                  实验输出，不提交到 Git
```

## 从零开始

要求：macOS/Linux、Python 3.12、Node.js 24 和 pnpm 11.25。其余内容（包括固定版本的 1mcp）由脚本安装。

```bash
python3 scripts/setup_environment.py
```

该命令会锁定 benchmark 提交、创建 `.venv`、安装 macOS/Linux 通用依赖、安装 1mcp、自动下载并校验约 2.2 GB 的 Middle/Late server bundles，再生成 Early/Middle/Late 配置。已存在且校验通过的文件会自动跳过下载。

一键检查：

```bash
.venv/bin/python scripts/check_environment.py --strict
```

详细步骤见 [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) 和 [docs/SUBSET.md](docs/SUBSET.md)。

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
- [ ] 完成一次小规模 smoke run

## 安全说明

不要把 API key 写入 Python 文件或提交到 Git。复制 `.env.example` 为 `.env`，仅在本机填写。
