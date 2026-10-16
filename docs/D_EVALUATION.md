# Member D final evaluation workflow

This workflow runs the validated fixed 30-task pilot set with three strategies, three
environment versions, three independent benchmark repeats, and five successful
Judge scores per task. It never writes API-key values to a plan, report, log, or
metadata file.

The task set contains 24 affected/recovery tasks and six retention tasks. It is
the same `pilot-30` set validated as runnable in Early, Middle, and Late. The
archived 23-task comparison set remains in the repository only as historical
evidence and is not the default for Member D's new formal runs.

## 1. Full Rewrite baseline definition and limitation

The completed matrix used a **version-invariant full-harness rewrite**. The
same replacement system prompt and tool-usage rules were materialized under
`harness/full_rewrite/{early,middle,late}/`; each run then treated the live
`tools/list` response as the source of truth. The rewrite therefore removes
all stale tool-specific guidance, but it does not synthesize different prose
from each version's schema snapshot.

This is a valid generic Full Rewrite baseline and is the exact baseline whose
hashes appear in the formal results. It must not be described as
schema-generated or version-specific. A stronger follow-up baseline could
generate complete version-specific knowledge from each schema snapshot, but
that would be a new experiment and would require rerunning the matrix.

## 2. Generate the zero-cost plan

```bash
.venv/bin/python scripts/run_experiment_matrix.py
```

The default plan contains 27 benchmark runs, 810 trajectories, and 4,050 Judge
scores. It is written to `reports/d/experiment-matrix-plan.json`. Plan mode does
not read `.env`, start MCP servers, or call a model API.

## 3. Formal execution

Use macOS, Linux, or WSL. Complete environment setup and the lightweight
handoff gate first. Keep `.env` local and ignored by Git.

Start the matching Early, Middle, or Late 1MCP service before executing runs for
that version. All three services may also run concurrently. Then execute:

```bash
.venv/bin/python scripts/run_experiment_matrix.py --execute
```

The runner performs the configuration and fairness preflight, skips a run only
when its exact task set and five Judge scores are already complete, and stops on
the first failure. Use `--keep-going` to finish independent runs and write a
machine-readable failure list. Use `--phase benchmark` or `--phase judge` to
separate the paid phases. Do not use `--rerun-completed` unless replacing an
entire consistently configured matrix.

Each benchmark call now records provider-reported prompt and completion tokens
without modifying the upstream benchmark. Each Judge task and the Judge batch
metadata record the same usage fields, including invalid Judge responses that
were billed before a retry.

## 4. Final audit and collection

```bash
.venv/bin/python scripts/audit_experiment_results.py
.venv/bin/python scripts/collect_results.py
```

The audit requires all 27 run directories, the exact fixed task IDs, five
successful Judge scores per task, matching benchmark/task/model/Judge settings,
complete harness hashes, all MCP servers connected, and non-null usage and
timing. Its result is `reports/d/final-experiment-audit.json`; do not use final
comparison claims unless `passed` is `true`.

The collector keeps benchmark and Judge usage separate and also reports their
combined token total when both are known.

## 5. Failure attribution

Low TF alone is not an under-update or over-update. Compare the same task and
run ID across all three strategies. An under-update needs evidence that the
selective patch missed a changed tool contract and another strategy handled it.
An over-update needs evidence that changed unrelated harness knowledge caused
a retention task to fail while the unchanged harness completed it. Preserve
the complete paired trajectories and Judge records for both examples. The
formal matrix contains no natural over-update failure; Task 260 is documented
only as an efficiency degradation. The supplementary controlled Task 235
ablation isolates an over-broad output-protocol rewrite that breaks normal
termination and is explicitly excluded from the formal statistics.
