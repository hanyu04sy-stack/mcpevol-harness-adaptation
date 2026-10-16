# MCPEvol Harness Adaptation

> **PE6203 Case 4 · Reproducible evaluation of harness adaptation under MCP environment change**

[![Final audit](https://img.shields.io/badge/final_audit-passed-1f883d)](reports/d/final-experiment-audit.json)
[![Matrix](https://img.shields.io/badge/experiment_cells-27-0969da)](reports/d/final-comparison.csv)
[![Trajectories](https://img.shields.io/badge/trajectories-810-8250df)](reports/final-report.md)
[![Judge scores](https://img.shields.io/badge/Judge_scores-4%2C050-bf8700)](reports/d/fairness-audit.md)
[![Lightweight validation](https://github.com/hanyu04sy-stack/mcpevol-harness-adaptation/actions/workflows/ci.yml/badge.svg)](https://github.com/hanyu04sy-stack/mcpevol-harness-adaptation/actions/workflows/ci.yml)

This project asks a practical question: **when MCP tools evolve, should an
agent keep its old harness, rewrite everything, or patch only the knowledge
linked to detected changes?** We compare three strategies under one fixed,
audited protocol:

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

## Experimental design

```text
3 strategies × 3 environment versions × 3 independent runs
× 30 fixed tasks = 810 trajectories
× 5 Judge evaluations = 4,050 Judge scores
```

- **Benchmark:** [MCPEvol-Bench](https://github.com/Octobrist/MCPEvol-Bench),
  pinned at `888c779a0fe735f612ca62bdd1fdd7c9e6bf8701`
- **Versions:** Early (`original`), Middle (`iter3`), Late (`iter5`)
- **Task set:** fixed 30-task subset: 24 affected + 6 retention tasks
- **Model / Judge:** `gpt-4o-mini`, temperature `0.0`
- **Fairness:** identical tasks, model, parameters, Judge, runner, endpoints,
  source commit, and task hashes; only the harness strategy changes
- **Audit:** 27/27 cells, 810/810 scored tasks, no issues, no secrets recorded

## Assignment 4.2 report coverage

| Required report component | Where to read it |
|---|---|
| Main results: TF, PE, ECS | [Final report §5](reports/final-report.md#5-main-results) · [comparison CSV](reports/d/final-comparison.csv) |
| Recovery and retention | [Final report §5.3](reports/final-report.md#53-recovery-and-retention) |
| Update cost | [Final report §7](reports/final-report.md#7-cost) · [per-cell cost data](reports/d/cost-analysis.csv) |
| Under-update trajectory | [Task 2 analysis](reports/d/failure-analysis.md#under-update-case--task-2-confirmed-all-3-versions) |
| Over-update trajectory | [Task 235 controlled ablation](reports/d/failure-analysis.md#controlled-over-update-ablation-supplementary-case--not-part-of-the-formal-statistics) |
| Discussion | [Final report §8](reports/final-report.md#8-discussion) |

## Start here

- **Course report:** [Markdown](reports/final-report.md) · [Word](reports/final-report.docx)
- **One-page result summary:** [conclusion-summary.md](reports/d/conclusion-summary.md)
- **Fairness and protocol audit:** [fairness-audit.md](reports/d/fairness-audit.md)
- **Failure analysis and trajectories:** [failure-analysis.md](reports/d/failure-analysis.md)
- **Metric definitions:** [metric-definitions.md](docs/metric-definitions.md)
- **Final machine-readable audit:** [final-experiment-audit.json](reports/d/final-experiment-audit.json)
- **Complete D handoff archive:** `deliverables/mcpevol-D-raw-results-2026-10-16.tar.gz`

## Repository map

```text
configs/       pinned experiment and ablation configurations
data/subsets/  fixed task sets and affected/retention labels
harness/       No Update, Full Rewrite, Selective Patch, and ablation harnesses
scripts/       setup, validation, execution, judging, and analysis
tests/         offline validation tests
docs/          environment, metrics, execution, and handoff documentation
reports/       final report, audits, comparisons, and curated evidence
results/       raw experiment outputs (normally excluded from Git)
deliverables/  packaged handoff archive and retained execution logs
```

## Reproduce the environment

Requirements: Linux or WSL, Python 3.12, Node.js 24, and pnpm 11.25.

```bash
python3 scripts/setup_environment.py
.venv/bin/python scripts/check_environment.py --strict
.venv/bin/python scripts/check_experiment_config.py --config configs/experiment.json
```

Run the lightweight handoff gate without paid API calls:

```bash
python3 -m pip install -r requirements-ci.txt
python3 scripts/check_handoff.py
```

For complete execution commands and resume behavior, see
[docs/RUNNING.md](docs/RUNNING.md), [docs/JUDGE.md](docs/JUDGE.md), and
[docs/HANDOFF.md](docs/HANDOFF.md).

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

