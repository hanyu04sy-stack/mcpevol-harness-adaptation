# MCPEvol Harness Adaptation

> **PE6203 Case 4** · Reproducible evaluation of harness adaptation under MCP environment change

[![Final audit](https://img.shields.io/badge/final_audit-passed-1f883d)](reports/d/final-experiment-audit.json)
[![Matrix](https://img.shields.io/badge/experiment_cells-27-0969da)](reports/d/final-comparison.csv)
[![Trajectories](https://img.shields.io/badge/trajectories-810-8250df)](reports/final-report.md)
[![Judge scores](https://img.shields.io/badge/Judge_scores-4%2C050-bf8700)](reports/d/fairness-audit.md)
[![Lightweight validation](https://github.com/hanyu04sy-stack/mcpevol-harness-adaptation/actions/workflows/ci.yml/badge.svg)](https://github.com/hanyu04sy-stack/mcpevol-harness-adaptation/actions/workflows/ci.yml)

This repository reproduces a controlled experiment: **when MCP tools evolve,
should an agent keep its old harness, rewrite everything, or patch only the
knowledge linked to detected changes?** All numbers quoted in the report are
computed from data in this repository by the committed scripts.

## Status

| Component | Status |
|---|---|
| Experiment matrix — 3 strategies × 3 versions × 3 runs × 30 tasks | ✅ 27/27 cells audited |
| Trajectories and Judge scores | ✅ 810/810 scored · 4,050 Judge evaluations |
| Lightweight CI validation | ✅ passing on ubuntu-24.04 and macos-15 |
| Course report | ✅ final ([Markdown](reports/final-report.md) · [Word](reports/final-report.docx)) |
| Raw results archive (3.8 MB) | 📦 delivered separately — not in this repository (see below) |

## The three strategies

| Strategy | Adaptation rule |
|---|---|
| **No Update** | Keep the original harness after the environment changes. |
| **Full Rewrite** | Replace all tool-use guidance and defer to the live tool list. |
| **Selective Patch** | Append focused guidance only for tools detected as changed. |

## Results at a glance

| Strategy | TF mean ± SD | PE | Success rate | ECS |
|---|---:|---:|---:|---:|
| No Update | 8.25 ± 2.88 | 7.82 | 75.2% | 7.98 |
| **Full Rewrite** | **8.75 ± 2.41** | **7.92** | **81.5%** | **8.63** |
| Selective Patch | 8.21 ± 2.84 | 7.70 | 75.2% | 7.82 |

**Main finding.** Full Rewrite performs best in this experiment. Selective
Patch does not show a reliable improvement over No Update on affected tasks
(paired TF difference +0.10; 95% bootstrap interval −0.14 to +0.35), and it
underperforms Full Rewrite (−0.51; interval −0.72 to −0.33).

**Why?** The patch generator misses an affected `pantheon-mcp/search_agents`
contract in Task 2. The stale combined-keyword call is visible in the failed
Selective Patch trajectories, while Full Rewrite follows the current live
contract and succeeds in all nine paired cells.

**Retention.** Five of six retention tasks remain successful under every
formal strategy; four stay perfect throughout. No natural formal-matrix case
meets the strict over-update definition. A separately labelled controlled
Task 235 ablation demonstrates that an unrelated output-protocol rewrite can
break termination; it is excluded from all formal aggregates.

## Reproduce the results

### Lightweight gate — no API key, no network (CI runs this)

```bash
python3 -m pip install -r requirements-ci.txt
python3 scripts/check_handoff.py
```

Expected tail (Linux/macOS): `passed: true` after the inventory check
(127 required files, none missing or empty) and all five checks —
tool-change consistency, JSON Schema validation, semantic asset validation,
Python compilation, and the 71-test unit suite.

### Full experiment — requires MCP servers and a paid model

Requirements: Linux or WSL, Python 3.12, Node.js 24, pnpm 11.25, and a local
`.env` (copy `.env.example`) with provider credentials.

```bash
python3 scripts/setup_environment.py
.venv/bin/python scripts/check_environment.py --strict
.venv/bin/python scripts/check_experiment_config.py --config configs/experiment.json
```

The 27-run matrix, judging, and final audit are driven by
`scripts/run_experiment_matrix.py` and documented in
[docs/RUNNING.md](docs/RUNNING.md), [docs/JUDGE.md](docs/JUDGE.md), and
[docs/D_EVALUATION.md](docs/D_EVALUATION.md). The audit reports
27/27 cells with no issues and no recorded secrets.

## Where to read what

| You want | Read |
|---|---|
| One-page result summary | [conclusion-summary.md](reports/d/conclusion-summary.md) |
| Full course report (Markdown / Word) | [final-report.md](reports/final-report.md) · [final-report.docx](reports/final-report.docx) |
| Fairness and protocol audit | [fairness-audit.md](reports/d/fairness-audit.md) |
| Failure analysis with trajectories | [failure-analysis.md](reports/d/failure-analysis.md) |
| Metric definitions | [metric-definitions.md](docs/metric-definitions.md) |
| Machine-readable final audit | [final-experiment-audit.json](reports/d/final-experiment-audit.json) |
| Assignment 4.2 report coverage | [§ Report coverage](#report-coverage) |

## Repository map

| Path | What is in it | In Git |
|---|---|---|
| `configs/` | pinned experiment and ablation configurations | ✅ |
| `data/subsets/` | fixed task sets and affected/retention labels | ✅ |
| `harness/` | No Update, Full Rewrite, Selective Patch, and the ablation harness | ✅ |
| `scripts/` | setup, validation, execution, judging, and analysis | ✅ |
| `tests/` | offline validation tests | ✅ |
| `docs/` | environment, metrics, execution, and handoff documentation | ✅ |
| `reports/` | final report, audits, comparisons, and curated evidence | ✅ |
| `results/` | raw experiment outputs (21.8 MB) | ❌ kept local, excluded by `.gitignore` |
| `deliverables/` | D handoff manifest ([README-D-deliverable.md](deliverables/README-D-deliverable.md)) | ✅ (archive ❌, see below) |

**About the raw results archive.** The complete raw trajectory archive
(`mcpevol-D-raw-results-2026-10-16.tar.gz`, 3.8 MB) is intentionally excluded
from Git and is delivered separately with the course submission. Curated
summaries, comparisons, audits, and failure evidence are committed under
`reports/d/`, so every number in the report remains reproducible from this
repository.

## Report coverage

| Required report component | Where to read it |
|---|---|
| Main results: TF, PE, ECS | [Final report §5](reports/final-report.md#5-main-results) · [comparison CSV](reports/d/final-comparison.csv) |
| Recovery and retention | [Final report §5.3](reports/final-report.md#53-recovery-and-retention) |
| Update cost | [Final report §7](reports/final-report.md#7-cost) · [per-cell cost data](reports/d/cost-analysis.csv) |
| Under-update trajectory | [Task 2 analysis](reports/d/failure-analysis.md#under-update-case--task-2-confirmed-all-3-versions) |
| Over-update trajectory | [Task 235 controlled ablation](reports/d/failure-analysis.md#controlled-over-update-ablation-supplementary-case--not-part-of-the-formal-statistics) |
| Discussion | [Final report §8](reports/final-report.md#8-discussion) |

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

API credentials belong only in the local `.env`. The final audit reports
`secrets_recorded: false`; `.env` is excluded from Git and from the packaged
handoff archive.
