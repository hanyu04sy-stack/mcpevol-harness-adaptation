# Selective Patch results

Archive status: the results below are C's historical 23-task, one-Judge run.
The final evaluation is the 30-task, three-repeat, five-Judge matrix in
`reports/d/`. The legacy `configs/comparison-subset/experiment.json` now points
to that 30-task dataset; the historical commands below therefore no longer
reproduce the 23-task run unchanged. Its original configuration is retained
under `provenance/` in `raw-results.zip`.

This folder is the C strategy's reproducible result handoff. The implementation is in `scripts/build_selective_patch.py` and `harness/selective_patch/{early,middle,late}/`. The common task file and pinned configuration are `data/subsets/comparison-subset/test_cases.json` and `configs/comparison-subset/experiment.json`.

The formal run uses the 23 task IDs present in every group of `reports/baseline-run20-summary.json`, with one benchmark run per version and one successful Judge evaluation per task. All three versions have 23 trajectories and 23 scored tasks (69 of each in total). The model and Judge were configured as `gpt-4o-mini` at temperature 0; the OpenRouter model identifier at the API boundary was `openai/gpt-4o-mini`. Each version started with 26 of 26 MCP servers connected. A later three-trajectory diagnostic for task 28, with one successful Judge scoring run per version, is recorded separately below and is not part of these formal results.

| Version | Mean TF | Mean PE | ECS | Recovery | Retention |
| --- | ---: | ---: | ---: | ---: | ---: |
| Early | 8.96 | 8.04 | 8.44 | 88.2% | 83.3% |
| Middle | 8.87 | 8.70 | 8.44 | 82.4% | 83.3% |
| Late | 8.83 | 8.83 | 8.44 | 82.4% | 83.3% |

`summary.csv` contains the 69 task rows. `summary.json` has the same detail-and-aggregate layout as B's baseline summary, with unknown token totals represented as `null` rather than zero. `raw-results.zip` contains the C trajectories, per-task Judge records, run metadata, and six benchmark/Judge console logs. Machine-specific home-directory path prefixes in that archive were replaced with `<HOME>` for repository sharing; scores, task content, and tool calls were otherwise preserved. The original run configuration and preflight are preserved under `provenance/` in `raw-results.zip`. The renamed configuration has the same pinned tasks, model, Judge, and runner settings but a different file hash; its configuration check passes offline. No `.env` file or API key is included. The JSON and CSV are reproducible from the run directories with `scripts/collect_results.py`.

The adaptation generator compares the Early tool contracts directly with the target version. It changed 0, 22, and 38 tool entries in Early, Middle, and Late respectively. The generation step was deterministic, used zero model API calls, and took 0.008, 0.009, and 0.010 seconds respectively as recorded in the three harness manifests. These timings exclude schema collection, environment setup, benchmark execution, and judging. Runtime token use and monetary cost were not recorded, so they remain unknown.

To reproduce the scored run, start the matching MCP environment as described in `docs/HANDOFF.md`, configure `.env` locally, then run the following for each of `early`, `middle`, and `late`:

```bash
.venv/bin/python scripts/run_benchmark.py --version VERSION --config configs/comparison-subset/experiment.json --harness-dir harness/selective_patch/VERSION --run-id 20
.venv/bin/python scripts/run_judge.py --version VERSION --config configs/comparison-subset/experiment.json --harness-dir harness/selective_patch/VERSION --run-id 20 --num-runs 1
```

Replace `VERSION` with the version name. Run `scripts/verify_untouched.py` and `scripts/check_experiment_config.py` with the same config before the paid phase. The `--run-id 20` flag reproduces the historical result directory and is an execution label, not a task count. The original 30-task subset is unchanged; the seven IDs absent from B's result were not included in this C run. See `data/subsets/comparison-subset/README.md` for their IDs and selection caveat.

The 11 below-threshold task rows have an [offline failure review](failure-review.md). They remain `unknown` in the summary because the recorded failures do not establish an under-update or over-update caused by the patch. B's raw run-20 Judge records are unavailable in this checkout, so identical task IDs alone do not prove that every evaluation setting matched. In particular, the B scores are consistent with averaging multiple integer Judge scores, while C used one; this is an inference, not a confirmed B configuration. The current runner's shared completion instruction was introduced after B published run-20. Cross-strategy claims should disclose these limits.

After the input-path correction, task 28 alone was rerun once in Early, Middle and Late with one Judge pass each. Both log files were read successfully in all three trajectories. Early and Middle were judged successful (TF 10, PE 8 each); Late still failed (TF 4, PE 6) because its final response was only `[FINISH]`. The sanitized trajectories, Judge records, metadata, commands' console logs and diagnostic configuration are in `diagnostic-results.zip`. This archive is evidence for the failure review, not a replacement for `raw-results.zip` or the formal summary. No other failed task was rerun.
