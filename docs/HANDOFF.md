# B / C / D 交接命令

## 所有成员：首次初始化

```bash
git clone https://github.com/hanyu04sy-stack/mcpevol-harness-adaptation.git
cd mcpevol-harness-adaptation
python3 scripts/setup_environment.py
.venv/bin/python scripts/check_experiment_config.py
.venv/bin/python scripts/run_smoke_tests.py
```

smoke 命令会自动依次启动 Early/Middle/Late，不需要 `.env`，也不使用外部模型 API。

## B / C：运行正式 30 题实验

先本地填写密钥：

```bash
cp .env.example .env
```

每个版本需要两个终端。以 Early 为例：

```bash
# 终端 1
pnpm run serve:early

# 终端 2
pnpm run run:early
```

其余版本直接复制：

```bash
pnpm run serve:middle
pnpm run run:middle

pnpm run serve:late
pnpm run run:late
```

B 和 C 只能修改各自的 harness 逻辑；不得修改 `configs/experiment.json` 中的 model、temperature、task SHA-256、MCP URL 和 benchmark commit。正式对比前必须再运行：

```bash
.venv/bin/python scripts/validate_subset_coverage.py
.venv/bin/python scripts/build_runnability_matrix.py
.venv/bin/python scripts/check_experiment_config.py
```

当前固定集已实测 Early/Middle/Late 各 26/26 server 连接成功。如果本机启动结果不符，先执行 `python3 scripts/setup_environment.py`，不要自行删题或更换数据集。

## D：收集和核对输出

```bash
python3 -m json.tool reports/environment-validation.json >/dev/null
python3 -m json.tool reports/pilot-30-environment-validation.json >/dev/null
python3 -m json.tool reports/pilot-30-coverage.json >/dev/null
python3 -m json.tool reports/pilot-30-runnability-matrix.json >/dev/null
python3 -m json.tool reports/pilot-30-startup-stability.json >/dev/null
python3 -m json.tool reports/smoke/summary.json >/dev/null
find results/pilot-30 -type f -name '*.json' | sort
```

每个正式运行目录必须有 `run-metadata.json`，并核对其 `benchmark_commit`、`task_sha256`、`model_name`、`temperature` 和对应版本的 `mcp_url`。实验数据在 `results/` 中，已提交的环境和 smoke 证据在 `reports/` 中。
