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

1. 运行 `python3 scripts/check_environment.py`。
2. 运行 `python3 scripts/bootstrap_benchmark.py` 下载并锁定上游代码。
3. 创建 Python 3.12 虚拟环境并安装上游 `requirements.txt`。
4. 安装 Node.js 24、npm 11 和 1mcp。
5. 从上游 README 指向的数据源下载 evolution server bundles。
6. 把 bundles 解压到 `external/servers/iter3_servers` 和 `external/servers/iter5_servers`。
7. 用 `render_mcp_config.py` 生成三个不含占位符的本机配置。
8. 先用 1 到 3 个任务做 smoke run，再运行固定 30 题子集。

## 4. 当前机器检查结果

本次初始化时已经确认：

- 可用 Python：3.12.14
- 可用 Node.js：24.19.0
- 可用 pnpm：11.25.0
- `1mcp`：项目本地固定为 0.38.2
- iter3/iter5 evolution server bundles：已下载、SHA-256 校验通过并解压

因此目前是“代码骨架已建立，重量级依赖和数据尚未安装”的状态。

## 5. 公平比较规则

每次正式实验都要保存一份填写完成的配置文件。No-update、Full-rewrite、Selective-patch 只能改变 harness 内容，以下项目必须完全相同：

- benchmark commit
- Early/Middle/Late server bundle
- test case JSON 及其 SHA-256
- model 名称和参数
- judge 名称和参数
- 运行次数
- MCP host/port 设置

## 6. 已发现的版本差异

Case 文档写的是 201 个任务，但当前锁定的公开仓库中 `test_cases.json` 实际包含 393 个任务。这不是代码错误，而是课程说明与公开仓库版本之间的差异。报告中必须写明实际使用的仓库提交、任务数量和固定子集清单。
