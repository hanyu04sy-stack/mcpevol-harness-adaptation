# MCPEvol Harness Adaptation

[![Lightweight validation](https://github.com/hanyu04sy-stack/mcpevol-harness-adaptation/actions/workflows/ci.yml/badge.svg)](https://github.com/hanyu04sy-stack/mcpevol-harness-adaptation/actions/workflows/ci.yml)
[![Final audit](https://img.shields.io/badge/final_audit-passed-1f883d)](reports/d/final-experiment-audit.json)
[![Experiment cells](https://img.shields.io/badge/experiment_cells-27-0969da)](reports/d/final-comparison.csv)
[![Judge scores](https://img.shields.io/badge/Judge_scores-4%2C050-bf8700)](reports/d/fairness-audit.md)

This repository contains the group project for 6203 Case 4. Member A prepared
MCPEvol-Bench as a reproducible and fair experimental environment for the three
harness strategies; B and C implemented the No Update / Full Rewrite and
Selective Patch strategies; the completed three-strategy experiment, evaluation,
audit, and the final report are included in this repository as well.

## Final results

The completed experiment compares three adaptation strategies under one fixed,
audited protocol — 3 strategies × 3 environment versions × 3 independent runs
× 30 fixed tasks = 810 trajectories, scored by 5 Judge evaluations each.

| Strategy | TF mean ± SD | PE | Success rate | ECS |
|---|---:|---:|---:|---:|
| No Update | 8.25 ± 2.88 | 7.82 | 75.2% | 7.98 |
| **Full Rewrite** | **8.75 ± 2.41** | **7.92** | **81.5%** | **8.63** |
| Selective Patch | 8.21 ± 2.84 | 7.70 | 75.2% | 7.82 |

**Main finding.** Full Rewrite performs best in this experiment. Selective
Patch does not show a reliable improvement over No Update on affected tasks
(paired TF difference +0.10; 95% bootstrap interval −0.14 to +0.35), and it
underperforms Full Rewrite (−0.51; interval −0.72 to −0.33).

**Failure evidence.** Task 2 exposes a query-planning gap: failed Selective
Patch trajectories use combined keywords, while Full Rewrite succeeds in all
nine cells. Its classification as under-update remains a candidate: the
exported `search_agents` contract is unchanged across versions and failures
also occur in Early, so a changed-contract cause is not established.

**Retention.** Five of six retention tasks remain successful under every
formal strategy; four stay perfect throughout. No natural formal-matrix case
meets the strict over-update definition. A separately labelled controlled
Task 235 ablation demonstrates that an unrelated output-protocol rewrite can
break termination; it is excluded from all formal aggregates.

Where to read the evidence:

- Full report: [Markdown](reports/final-report.md) · [Word](reports/final-report.docx)
- Results summary: [conclusion-summary.md](reports/d/conclusion-summary.md)
- Fairness and protocol audit: [fairness-audit.md](reports/d/fairness-audit.md)
- Failure analysis with trajectories: [failure-analysis.md](reports/d/failure-analysis.md)
- Metric definitions: [metric-definitions.md](docs/metric-definitions.md)
- Machine-readable audit: [final-experiment-audit.json](reports/d/final-experiment-audit.json)

The full raw result tree is packaged as
`deliverables/mcpevol-D-raw-results-2026-10-16.tar.gz` and is included with
the repository submission. The summaries, audits, and curated paired
trajectories also remain directly reviewable without unpacking the archive.

## Fixed experimental decisions

- Upstream benchmark: [`Octobrist/MCPEvol-Bench`](https://github.com/Octobrist/MCPEvol-Bench)
- Pinned upstream commit: `888c779a0fe735f612ca62bdd1fdd7c9e6bf8701`
- Environment versions: Early=`original`, Middle=`iter3`, Late=`iter5`
- Development set: a fixed 30-task subset generated with seed `6203`
- Runnability requirement: every task dependency must connect successfully in all three versions
- Subset composition: approximately 80% affected tasks and 20% retention tasks
- Fairness rule: all harness strategies must use the same model, tasks, inference parameters, and judge configuration

The fixed subset makes an end-to-end run practical with limited compute. The configuration can later be upgraded to the full dataset as a separate experiment.

The archived baseline and Selective Patch formal results use the same 23 task IDs, documented in [the comparison subset](data/subsets/comparison-subset/README.md). This is the intersection of the six baseline result groups, not the complete original 30-task development set. The baseline summary does not explain why seven originally selected tasks are absent. The [Selective Patch result handoff](reports/selective-patch/README.md) records its run protocol and comparison limits.

`configs/comparison-subset/experiment.json` retains its historical filename for
compatibility with recorded run metadata, but the completed formal matrix uses
the 30-task `data/subsets/pilot-30/test_cases.json` dataset referenced inside
that configuration. The separate `data/subsets/comparison-subset/` directory
remains the archived 23-task dataset and is not the final D evaluation set.

## Repository layout

```text
configs/                  Canonical experiment configurations
harness/                  Auditable prompt and tool-usage knowledge by strategy
docs/                     Environment, execution, and handoff guides
scripts/                  Setup, validation, generation, and run scripts
tests/                    Local tests that require no API key
data/subsets/             Fixed pilot, smoke, and canary task subsets
external/MCPEvol-Bench/   Generated by setup and excluded from Git
generated/                Generated task and 1MCP configurations, excluded from Git
reports/                  Validated environment, trajectory, and raw log evidence
reports/d/                Final D analysis, audits, comparisons, and curated evidence
results/                  Experiment output, excluded from Git
```

## Install from scratch

Requirements: macOS or Linux, Python 3.12, Node.js 24, and pnpm 11.25. The setup script installs everything else, including the pinned 1MCP version.

```bash
python3 scripts/setup_environment.py
```

The command pins the benchmark checkout, creates `.venv`, installs cross-platform dependencies and 1MCP, downloads and SHA-256 verifies about 2.2 GB of Middle/Late server bundles, repairs possible macOS/iCloud dataless files, and renders all three configurations. Existing verified archives are reused.

Run the complete environment check:

```bash
.venv/bin/python scripts/check_environment.py --strict
```

See [environment setup](docs/ENVIRONMENT.md), [troubleshooting](docs/TROUBLESHOOTING.md), [task subset](docs/SUBSET.md), [unified execution](docs/RUNNING.md), [judge integration](docs/JUDGE.md), [smoke results](docs/SMOKE_TEST.md), and the [B/C/D handoff](docs/HANDOFF.md).

## Validation and unified execution

```bash
.venv/bin/python scripts/validate_subset_coverage.py
.venv/bin/python scripts/build_runnability_matrix.py
.venv/bin/python scripts/check_experiment_config.py
.venv/bin/python scripts/run_benchmark.py --version early --dry-run
.venv/bin/python scripts/run_benchmark.py --version early --dry-run --print-resolved-prompt
```

Coverage validation enforces tool, parameter, and description changes plus affected/recovery and retention tasks. It writes `reports/pilot-30-coverage.json` and exits nonzero if any category is missing.

`reports/pilot-30-runnability-matrix.json` records every task dependency in Early, Middle, and Late. Configuration validation checks the matrix and task SHA-256 values, and a real run requires every dependency to be `connected`.

GitHub Actions runs the same lightweight gate on pinned Ubuntu 24.04 and macOS 15 runners for every push and pull request. It validates JSON Schema Draft 2020-12 documents, hashes, counts, unique IDs, version configurations, five-category coverage, the runnability matrix, the stability report, and all unit tests. CI does not download bundles or run 1MCP, Ollama, or the benchmark.

```bash
python3 -m pip install -r requirements-ci.txt
python3 scripts/check_handoff.py
```

`check_handoff.py` is the machine-readable handoff gate. It checks all required configurations, tasks, reports, scripts, tests, and documents, then runs schema validation, semantic consistency checks, Python compilation, and the full lightweight test suite. The full 27-run experiment is driven by `scripts/run_experiment_matrix.py`; see [docs/RUNNING.md](docs/RUNNING.md) and [docs/D_EVALUATION.md](docs/D_EVALUATION.md).

The cold-start report is `reports/pilot-30-startup-stability.json`. Early, Middle, and Late each passed three independent starts: 26/26 connected servers, no failures, and no unstable servers in all nine trials.

## Harness knowledge and tool schemas

`harness/original/` is the immutable No Update knowledge snapshot extracted from the pinned upstream agent. `harness/no_update/` aliases that snapshot; B writes a replacement under `harness/full_rewrite/`, and C writes a focused update under `harness/selective_patch/`. The runner injects the selected system prompt and tool rules without modifying the upstream checkout:

```bash
.venv/bin/python scripts/run_benchmark.py --version early \
  --harness-dir harness/no_update
```

Every run records the harness directory, manifest hash, and individual file hashes in `run-metadata.json`. Use `--print-resolved-prompt` with `--dry-run` to audit the exact injected prompt.

Export the exact MCP `tools/list` schemas and a deterministic cross-version diff with:

```bash
.venv/bin/python scripts/dump_tool_schemas.py
```

The machine-readable outputs are `reports/tool-schemas/{early,middle,late}.json` and `reports/tool-schemas/diff.json`. Add `--isolated` on resource-constrained machines to start one source server at a time.

Generate the detailed per-server change inventory and readable summary with:

```bash
.venv/bin/python scripts/diff_tool_schemas.py
```

The outputs are `reports/tool-changes.json` and `reports/tool-changes.md`. They classify added, removed, heuristically renamed, description-changed, and parameter-changed tools for Early to Middle, Middle to Late, and Early to Late. The handoff gate validates both reports without an API key.

## Deterministic smoke test

```bash
.venv/bin/python scripts/run_smoke_tests.py
```

All three versions passed with 2/2 connected servers, 4/4 completed tool calls, and no tool errors. Full trajectories and raw logs are stored under `reports/smoke/`.

## External-model canary

The external-model canary uses fixed upstream runnable tasks 142 and 161. Credentials are entered privately and are never written to configuration, logs, or Git.

```bash
.venv/bin/python scripts/configure_api_credentials.py
.venv/bin/python scripts/check_experiment_config.py --config configs/canary-real.json
.venv/bin/python scripts/run_real_canary.py --overwrite
```

For OpenRouter, use `https://openrouter.ai/api/v1` with model slug `openai/gpt-4o`. To update only the endpoint:

```bash
.venv/bin/python scripts/configure_api_credentials.py \
  --set-base-url https://openrouter.ai/api/v1
```

Only redacted reports are committed. `.env`, raw `results/`, and generated 1MCP configurations are ignored. Any failed version or task produces a nonzero exit status.

### Free local-model canary

Install Ollama and run one command. The script downloads the tool-capable `qwen3.5:4b` model, starts the local service, and tests all three versions.

```bash
curl -fsSL https://ollama.com/install.sh | sh
.venv/bin/python scripts/run_local_canary.py
```

Verified results are under `reports/canary-local-qwen35-4b-2/`. Each version passed both tasks with 3/3 connected servers and 28 visible tools. Across all trajectories there were 34 tool messages and no tool errors. Task 144 validates two time-tool calls; task 161 validates LikeC4 exploration and time-zone conversion. This flow is fully local, sets `external_api_used=false`, and does not read `.env`.

## Completion status

- [x] Public repository and pinned benchmark source
- [x] Canonical configuration and reproducible fixed subset
- [x] Early/Middle/Late generation and environment validation
- [x] Cross-platform installer and verified bundle downloader
- [x] Pinned 1MCP 0.38.2 and benchmark dependencies
- [x] Unified `gpt-4o` agent configuration plus a separate configured judge phase
- [x] Repaired Late dataless files, increasing usable servers from 23 to 54
- [x] Fixed 30-task set with 26/26 dependencies available in all versions
- [x] Three independent cold starts per version
- [x] Secure unified benchmark entry point
- [x] Deterministic smoke evidence and free local-model canary evidence
- [x] Dual-platform CI, JSON Schemas, final handoff tag, and branch protection
- [x] Auditable harness injection and Early/Middle/Late tool-schema diff
- [x] Judge adapter, TF/PE/ECS result collection, and formal result schema
- [x] Pre-run fairness guard and config-driven upstream runner arguments
- [x] Idempotent Late dataless repair with dry-run and fixture tests
- [x] Completed 27-cell three-strategy experiment, 810/810 trajectories and 4,050 Judge scores
- [x] Final report, fairness/completeness audit, cost analysis, and failure analysis

## Interpretation boundaries

- The 30 tasks are a predeclared fixed subset, not the full benchmark.
- Three benchmark runs are the independent repeats; the five Judge scores
  reduce scorer noise and are not five additional independent experiments.
- The controlled over-update ablation is supplementary and is not included in
  formal strategy means, confidence intervals, or rankings.
- The reported **$5.78** is a token-based estimate at the pinned reference
  rates, not a provider invoice.
- One Judge cell lacks wall-clock metadata; the reported Judge runtime is a
  measured lower bound across 26/27 cells rather than an invented total.

## Security

Never place an API key in Python source or commit it to Git. Copy `.env.example` to `.env` and fill it only on the local machine. The final audit reports `secrets_recorded: false`; `.env` is excluded from Git and from the packaged handoff archive.
