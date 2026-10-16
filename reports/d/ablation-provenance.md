# Task 235 controlled-ablation provenance

Status: supplementary evidence; excluded from the formal 27-cell experiment
matrix and all aggregate statistics.

## Purpose

The controlled Task 235 ablation tests whether an intentionally over-broad
harness rewrite can damage an otherwise successful retention task. The causal
comparison uses the evaluated Full Rewrite middle/run-01 trajectory as the
baseline because the ablation was derived from that harness.

- Baseline evidence: `reports/d/evidence/task235-baseline-fr.json`
- Ablation evidence: `reports/d/evidence/task235-over-update-ablation.json`
- Original baseline: `results/full_rewrite/middle/run-01/gpt-4o-mini/ANSWER/235.json`
- Original ablation: `results/ablation-over-broad/middle/middle/run-01/gpt-4o-mini/ANSWER/235.json`

The baseline terminates normally after one tool-call round containing three
chart calls. The ablation reaches 11 tool-call rounds and 33 chart calls,
exhausts the step budget (`exceeded=True`), and returns an empty answer.

## Iteration history and frozen files

Versions v1-v3 explored renamed tools, staging prerequisites, and a simulated
maintenance condition. Those attempts did not produce a behavioral failure and
were overwritten in the shared ablation output directory during iteration.
Only the final v4 trajectory is retained as result evidence.

The evaluated v4 mechanism is the output-protocol instruction visible in
`harness/over_broad_rewrite/middle/system_prompt.md` and
`harness/over_broad_rewrite/middle/tool_usage_rules.md`: final output is
JSON-only and must omit the runner's required `[FINISH]` marker. The retained
`manifest.json` description records the broader historical candidate classes
from v1-v3 as well as the final experiment context; it is not a literal summary
of only the effective v4 text.

The three evaluated harness files are hash-frozen because their hashes match
the ablation run metadata. They are therefore preserved unchanged. The raw run
also records strategy `middle` and is stored under a duplicated
`middle/middle` path. This is a harness-leaf naming artifact, not a fourth
formal strategy, and the raw evidence is intentionally left unchanged.

## Interpretation boundary

The tool-call-based Judge still assigns TF 10.0 because the chart calls
succeed. The failure claim instead rests on the paired termination evidence:
the baseline emits `[FINISH]` with a complete answer, while the ablation cannot
emit the required marker, exceeds its budget, and returns no answer. This is a
controlled mechanism demonstration, not a naturally occurring formal-matrix
failure and not evidence that Task 260 is an over-update case.
