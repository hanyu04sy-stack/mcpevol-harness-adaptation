# macOS / Linux 故障排查手册

本手册只针对当前锁定的 A 环境。遇到问题时，先在仓库根目录运行：

```bash
.venv/bin/python scripts/check_environment.py --strict
.venv/bin/python scripts/check_experiment_config.py
```

不要为了让检查通过而删题、改 SHA-256、更换 benchmark commit 或忽略失败 server。先用下面的对应步骤确定根因。

## 快速定位顺序

1. 确认命令是在仓库根目录执行的。
2. 运行上面两个检查，保留第一条错误。
3. 如果是端口错误，先处理端口；如果是版本错误，先修正版本。
4. 然后处理哈希或 server 加载问题。
5. 修复后运行 `.venv/bin/python scripts/check_handoff.py`。

## 1. 端口被占用

### 项目使用的端口

| 用途 | Early | Middle | Late |
|---|---:|---:|---:|
| 正式 pilot | 3051 | 3052 | 3053 |
| smoke | 3151 | 3152 | 3153 |
| 冷启动稳定性 | 3251 | 3252 | 3253 |
| canary | 3351 | 3352 | 3353 |

常见症状是 `EADDRINUSE`、`address already in use`、1MCP 启动后立即退出，或检查连到上一次残留的进程。

macOS 查询示例：

```bash
lsof -nP -iTCP:3051 -sTCP:LISTEN
```

Linux 查询示例：

```bash
ss -ltnp | grep -E ':(3051|3052|3053)([^0-9]|$)'
```

先核对输出中的 PID 和命令，确认它是本项目残留的 1MCP，再正常终止：

```bash
kill -TERM <PID>
```

再次执行 `lsof` 或 `ss`。不要盲目杀掉不熟悉的系统进程。如果端口由其他项目长期使用，可用临时隔离端口做环境诊断：

```bash
.venv/bin/python scripts/validate_tool_environments.py --base-port 4051
```

正式 B/C/D 实验仍必须使用 `configs/experiment.json` 锁定的 3051–3053，不能只改一个成员的地址。

## 2. Python / Node.js / pnpm / 1MCP 版本错误

期望版本：Python 3.12.x、Node.js 24.x、pnpm 11.25.x、项目本地 1MCP 0.38.2。检查实际被调用的程序：

```bash
python3 --version
node --version
pnpm --version
node_modules/.bin/1mcp --version
command -v python3
command -v node
command -v pnpm
```

如果 Python 不是 3.12，先用系统包管理器或版本管理器安装 Python 3.12，然后明确用它启动安装：

```bash
python3.12 scripts/setup_environment.py
```

如果 Node.js 或 pnpm 版本不对，切换到 Node.js 24 和 pnpm 11.25 后重建项目本地依赖：

```bash
pnpm install --frozen-lockfile
node_modules/.bin/1mcp --version
```

始终使用 `node_modules/.bin/1mcp` 或 `pnpm run serve:early` 这类项目本地命令，不要依赖全局安装的 1MCP。最后运行：

```bash
.venv/bin/python scripts/check_environment.py --strict
```

## 3. SHA-256 或文件哈希不一致

### server bundle 哈希不一致

先只验证，不下载、不解压：

```bash
python3 scripts/download_server_bundles.py --verify-only
```

预期哈希已固定在 `scripts/download_server_bundles.py` 中。如果压缩包大小或 SHA-256 不匹配，不要修改预期哈希。先把损坏文件移到可恢复的隔离名称，再让脚本重新下载：

```bash
mv external/servers/archives/iter3_servers.zip external/servers/archives/iter3_servers.zip.corrupt
python3 scripts/download_server_bundles.py --versions middle --repair-extraction
```

Late 对应 `iter5_servers.zip` 和 `--versions late`。重新下载前确保约 1.1 GB 空间和网络可用。

### 任务、报告或配置哈希不一致

```bash
git diff -- configs data/subsets reports
.venv/bin/python scripts/check_experiment_config.py
```

如果是无意修改，先保存自己需要的内容，然后仅恢复明确受影响的文件，例如：

```bash
git restore -- data/subsets/pilot-30/test_cases.json
```

如果是 A 有意重建任务集或重跑稳定性，必须同时重新生成相关报告、更新配置中的哈希，并通过 `scripts/check_handoff.py`。B/C/D 不应自行更换锁定哈希。

## 4. server 加载失败或长时间停在 loading

常见症状是 `failed`、长时间 `loading`、`validation timeout`、可见 server 数少于配置数，或 `MCP task dependencies are unavailable`。

先一次只验证问题版本，并保留日志：

```bash
.venv/bin/python scripts/validate_tool_environments.py --versions late --timeout 900
```

查看报告和原始日志：

```bash
python3 -m json.tool reports/environment-validation.json
grep -n "Failed to connect" logs/environment-validation/late.log
```

如果 1MCP 仍在运行，可查看实时状态：

```bash
curl -fsS http://127.0.0.1:3053/api/v1/inspect | python3 -m json.tool
```

按错误类型处理：

- `command not found`：确认 `.venv/bin`、`node_modules/.bin` 已存在，重跑 `python3 scripts/setup_environment.py`。
- 缺少 Python 包：使用 `.venv/bin/python`，不要用系统 Python 运行 benchmark。
- 缺少 Node 包：运行 `pnpm install --frozen-lockfile`。
- macOS 解压目录出现 dataless/空占位文件：从已验证压缩包恢复：

```bash
python3 scripts/download_server_bundles.py --versions late --repair-extraction
```

如果生成的 server 配置缺失或被手动改过，不要手动补 server；用锁定任务集重新渲染。以 Late 为例：

```bash
.venv/bin/python scripts/render_mcp_config.py \
  --benchmark-root external/MCPEvol-Bench \
  --server-bundle-root external/servers \
  --version late \
  --test-case-file data/subsets/pilot-30/test_cases.json \
  --output generated/1mcp/late.json
```

修复后重新验证该版本。只有报告中所有当前任务依赖均为 `connected` 才能继续实验：

```bash
.venv/bin/python scripts/validate_tool_environments.py --versions late --timeout 900
.venv/bin/python scripts/check_experiment_config.py
```

## 5. 最终恢复确认

局部错误修复后，先跑不启动 server bundle 的 A 交接门禁：

```bash
.venv/bin/python scripts/check_handoff.py
```

如果本次问题与真实 server 启动相关，再运行完整 smoke：

```bash
.venv/bin/python scripts/run_smoke_tests.py
```

交接门禁、配置检查和对应的 server 验证全部通过后，才认为故障已解决。
