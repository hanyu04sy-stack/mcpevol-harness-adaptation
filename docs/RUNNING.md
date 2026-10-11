# 统一运行入口

## 1. 唯一实验配置

`configs/experiment.json` 是程序实际读取的配置，统一固定了：

- benchmark commit；
- 30 题任务文件及 SHA-256；
- 模型、temperature 和最大输出 token；
- Early/Middle/Late 的 MCP 地址和 server 配置；
- 按版本分开的输出目录。

三个版本不再各自接收模型或任务参数，因此不会意外使用不同配置。

## 2. 安全填写 API 配置

```bash
cp .env.example .env
```

只在本机 `.env` 中填写 `MODEL_API_KEY` 和可选的 `MODEL_BASE_URL`。`.env` 已被 Git 忽略。运行器直接解析 `NAME=value`，不会把文件交给 shell 执行，不会覆盖系统已设置的环境变量，也不会把密钥写入日志或元数据。

## 3. 运行前检查

```bash
.venv/bin/python scripts/check_experiment_config.py
```

该命令会检查 checkout commit、任务数量和哈希、模型参数、三个 1MCP 配置、URL 和输出目录是否一致。

只验证某个版本将使用什么参数，不读密钥也不发起 API 请求：

```bash
.venv/bin/python scripts/run_benchmark.py --version early --dry-run
```

## 4. 运行一个版本

先在一个终端启动对应的 1MCP 环境：

```bash
pnpm exec 1mcp serve --config generated/1mcp/early.json --host 127.0.0.1 --port 3051
```

再在另一个终端运行：

```bash
.venv/bin/python scripts/run_benchmark.py --version early
```

Middle 和 Late 分别改为 `middle`/`3052` 和 `late`/`3053`。入口会先核对 MCP server 集合，再把配置中的 API key、base URL 和 temperature 注入上游 runner。运行元数据保存为：

```text
results/pilot-30/<early|middle|late>/run-metadata.json
```

元数据不包含密钥。

## 5. 无 API 费用的端到端 smoke test

```bash
.venv/bin/python scripts/run_smoke_tests.py
```

该命令使用 `configs/smoke.json` 和本地确定性模型，自动启动、执行并停止三个环境。完整结果见 [SMOKE_TEST.md](SMOKE_TEST.md)，成员交接命令见 [HANDOFF.md](HANDOFF.md)。
