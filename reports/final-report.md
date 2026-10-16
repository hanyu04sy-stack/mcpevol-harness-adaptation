# Tool Harness Adaptation under Environment Change

## Abstract

Long-lived tool-using agents can retain stale knowledge after tool names,
parameters, descriptions, or usage rules change. This project evaluates three
harness strategies on MCPEvol-Bench while keeping the base model, decoding
settings, tasks, environment endpoints, and Judge protocol fixed: No Update,
Full Rewrite, and a Selective Patch method that changes only knowledge linked
to detected tool changes. We run a fixed 30-task subset across Early, Middle,
and Late environments, with three independent runs and five Judge scores per
task. The final matrix contains 27 experiment cells, 810 trajectories, and
4,050 successful Judge scores. Full Rewrite achieves the strongest overall
result (mean TF 8.75, success 81.5%), while Selective Patch does not
significantly improve over No Update. Paired trajectories identify one
under-update failure in Selective Patch and a Full Rewrite efficiency
regression that remains above the success threshold. Because the formal matrix
contains no natural over-update failure, a separate controlled retention-task
ablation demonstrates how an over-broad output-protocol rewrite can break task
termination. The results show that selective adaptation can preserve
unaffected behavior, but its benefit depends on complete change detection.

## 1. Problem and research question

Tool harnesses contain system instructions, tool-use rules, routing guidance,
and assumptions about tool contracts. When the environment changes, stale
knowledge can cause invalid calls or poor planning. Updating everything may
recover changed tasks but can also disturb working behavior. Updating only the
affected knowledge should reduce that risk, but only if the change detector
has sufficient coverage.

The research question is:

> Can a selective harness patch recover performance on changed tools while
> preserving performance on tasks that should remain solvable?

Model fine-tuning and benchmark-label changes are outside the project scope.

## 2. Adaptation strategies

### 2.1 No Update

No Update uses the original harness knowledge after every environment change.
It is the stale-knowledge baseline.

### 2.2 Full Rewrite

The evaluated Full Rewrite replaces the complete original tool-use guidance
with one generic rule set. It instructs the agent to treat the live
`tools/list` names, descriptions, and schemas as the source of truth and to
discard remembered contracts. The replacement text is version-invariant: the
same prompt and rules are materialized under Early, Middle, and Late, while
the live tool list supplies the version-specific contracts at runtime.

This baseline is a complete harness rewrite, but it is not schema-generated
version-specific prose. This distinction is important when interpreting its
results and is preserved because the evaluated harness hashes are immutable
experiment evidence.

### 2.3 Selective Patch

Selective Patch compares exported tool schemas, identifies affected tools,
and appends targeted knowledge only for detected changes. It patches 0 tool
entries for Early, 22 for Middle, and 38 for Late. Generation is deterministic
and local. The method aims to preserve the original harness for unaffected
tasks while correcting renamed, removed, parameter-changed, or
description-changed tools.

## 3. Experimental protocol

- Benchmark: MCPEvol-Bench, commit
  `888c779a0fe735f612ca62bdd1fdd7c9e6bf8701`.
- Environments: Early (`original`), Middle (`iter3`), and Late (`iter5`).
- Tasks: fixed 30-task subset, comprising 24 affected and six retention tasks.
- Coverage: tool-, parameter-, and description-level changes are represented.
- Agent and Judge: `gpt-4o-mini`, temperature 0.0.
- Repeats: three independent runs per strategy/version cell.
- Scoring: five successful Judge scores per task.
- Scale: 3 strategies x 3 versions x 3 runs = 27 cells; 810 trajectories.
- Fairness controls: identical tasks, model, inference parameters, Judge,
  server mapping, benchmark commit, and task hashes across strategies.

The stock runner would retain only 23 of the 30 selected tasks. The project
overrides that filter in memory without modifying the pinned upstream source,
so all strategies use the same predeclared 30-task subset.

## 4. Metrics

- **Task Fulfillment (TF):** mean of five 1-10 completion scores.
- **Planning Effectiveness (PE):** mean of five 1-10 planning/efficiency
  scores.
- **Success:** TF >= 6.0.
- **Evolutionary Competency Score (ECS):** for each strategy/run/task,
  `mean(TF across versions) - population_sd(TF across versions)`.
- **Recovery rate:** success rate on the 24 affected tasks.
- **Retention rate:** success rate on the six retention tasks.
- **Update cost:** local harness-generation work plus recorded benchmark and
  Judge tokens, wall-clock time, and estimated API cost.

## 5. Main results

### 5.1 Strategy-level results

| Strategy | Mean TF ± SD | Mean PE ± SD | Success rate | Mean ECS |
|---|---:|---:|---:|---:|
| No Update | 8.25 ± 2.88 | 7.82 ± 2.92 | 75.2% | 7.98 |
| Full Rewrite | **8.75 ± 2.41** | **7.92 ± 2.81** | **81.5%** | **8.63** |
| Selective Patch | 8.21 ± 2.84 | 7.70 ± 2.95 | 75.2% | 7.82 |

Full Rewrite is the strongest strategy under the evaluated protocol.
Selective Patch has nearly the same overall success rate as No Update and a
slightly lower mean TF.

### 5.2 Strategy-by-version results

| Strategy | Early TF / PE | Middle TF / PE | Late TF / PE |
|---|---:|---:|---:|
| No Update | 8.22 / 8.10 | 8.24 / 7.62 | 8.28 / 7.76 |
| Full Rewrite | **8.74 / 7.88** | **8.79 / 7.96** | **8.73 / 7.91** |
| Selective Patch | 8.24 / 7.88 | 8.03 / 7.43 | 8.36 / 7.79 |

### 5.3 Recovery and retention

For affected tasks, the paired Selective Patch minus No Update TF difference
is +0.10 with a 95% bootstrap interval of -0.14 to +0.35. The interval
contains zero, so the experiment does not support a reliable Selective Patch
advantage. Selective Patch minus Full Rewrite is -0.51 with an interval of
-0.72 to -0.33, showing that Selective Patch is worse than Full Rewrite in
this matrix.

Five of six retention tasks remain successful under every strategy. Four are
perfect throughout. Task 161 fails under all strategies and therefore cannot
be attributed to an update. Task 260 remains successful but exposes a
systematic Full Rewrite efficiency regression described below.

## 6. Failure analysis

### 6.1 Under-update: Task 2

Task 2 depends on affected `pantheon-mcp/search_agents` behavior. The
Selective Patch inventory does not include `pantheon-mcp` or
`mcp-shrimp-task-manager`, even though the subset manifest marks them as
affected. Selective Patch repeatedly sends stale comma-combined keywords and
receives empty results. It fails in six of nine cells, similar to No Update.
Full Rewrite follows the current tool contract, sends individual keywords,
and scores TF 10.0 in all nine cells.

This is a confirmed under-update: the patch misses a changed contract, the
stale call is visible in the trajectory, and the paired Full Rewrite handles
the same task.

### 6.2 Efficiency degradation: Task 260

Task 260 is a retention task requiring two time-zone conversions. No Update
and Selective Patch both make exactly two `convert_time` calls, never call
`request_user_input`, and score TF/PE 10/10 in all nine cells.

Full Rewrite makes the same correct conversions but then calls
`request_user_input` in every cell, between 1 and 12 times. The aggressive
confirmation-tool description becomes salient under the broad rewrite,
causing repeated empty-input loops and qualified answers. In Late run 3, the
paired score falls from No Update 10.0/10.0 to Full Rewrite 6.4/2.8 after eight
redundant confirmation calls. Across all nine cells, Full Rewrite's mean TF is
8.67 instead of 10.0.

This is a repeated efficiency and answer-quality degradation, but it is not
classified as over-update. All Full Rewrite Task 260 cells retain TF >= 6, and
the paired trajectories do not isolate one explicitly incorrect rewritten
rule as the cause.

### 6.3 Controlled over-update ablation: Task 235

No natural retention failure in the 27-cell matrix satisfies the strict
over-update definition. A supplementary controlled ablation therefore applies
an intentionally over-broad rewrite to retention Task 235 in the Middle
environment. This ablation is stored outside the three formal strategy result
trees and is excluded from every aggregate and confidence interval.

The evaluated Full Rewrite baseline—the harness from which the ablation was
derived—completes Task 235 in one tool-call round containing three chart calls
and emits the required `[FINISH]` marker. Several deliberately incorrect tool-contract
injections were ignored because the model treated the live tool list as
authoritative. The effective ablation instead rewrites an unrelated output
protocol: final answers must be JSON-only and must not contain `[FINISH]`.
The agent obeys that rewrite, never terminates normally, repeats the three-call
chart sequence for 11 rounds (33 calls), exhausts the step budget
(`exceeded=True`), and returns an
empty answer. This paired trajectory is a confirmed over-update mechanism:
unrelated rewritten knowledge breaks a previously successful retention task.

The tool-call-oriented Judge still assigns TF 10.0 because the individual
chart calls succeed. The reported failure is therefore based on runner state,
termination, and final-answer evidence, not on the Judge score. Complete
evidence is preserved in `reports/d/evidence/task235-baseline-fr.json` and
`reports/d/evidence/task235-over-update-ablation.json`; frozen-file provenance
is recorded in `reports/d/ablation-provenance.md`.

## 7. Cost

The matrix records approximately 33.74 million tokens: 13.37 million for the
benchmark agent and 20.37 million for the Judge. At the pinned reference rates
of $0.15 per million input tokens and $0.60 per million output tokens, the
estimated total is $5.78 ($2.26 benchmark and $3.51 Judge). This is a
token-based estimate, not a provider invoice.

Benchmark wall-clock time is approximately 5.3 hours. Recorded Judge time is
at least 3.65 hours across 26 of 27 cells; one Judge cell lacks wall-clock
metadata and is excluded rather than inferred. Selective Patch and Full
Rewrite generation are local and record zero model-API tokens.

## 8. Discussion

Selective Patch preserves retention well, but it does not outperform No
Update because its change inventory misses an important affected contract.
The result supports a coverage-first view of selective adaptation: a smaller
patch is useful only when the dependency mapping from benchmark tasks to tool
changes is complete.

Full Rewrite performs best because it removes stale assumptions and defers to
live schemas. However, Task 260 shows that broad guidance can coexist with a
systematic efficiency regression even when the task remains successful. The
Task 235 ablation separately demonstrates a causal over-update mechanism:
rewriting an unrelated output protocol can break termination despite correct
tool calls. Recovery and retention therefore require both current contracts
and strict scope control over what the adaptation is allowed to rewrite.

The most difficult changes are not necessarily syntactically large schema
changes. Behavioral changes encoded in descriptions, query semantics, or
usage guidance can be missed by structural diffing and may require semantic
validation or trajectory-based tests.

## 9. Limitations

1. The fixed 30-task subset is course-allowable but smaller than the full
   201-task release.
2. Three independent runs are the recommended minimum; paired differences and
   bootstrap intervals are more appropriate than broad significance claims.
3. The agent and Judge use the same model family, which may introduce shared
   biases.
4. All formal runs were executed in one WSL/Linux environment.
5. Full Rewrite is version-invariant generic prose, not schema-generated
   version-specific knowledge.
6. The over-update example is a supplementary controlled ablation, not a
   naturally occurring cell in the formal matrix, and its Judge score does not
   detect the termination failure.
7. Only the final Task 235 ablation trajectory is preserved; earlier injected
   variants were overwritten and remain documented in work logs rather than
   as separate result directories.

## 10. Conclusion

Under the completed protocol, Full Rewrite provides the strongest recovery
and cross-version stability. The current Selective Patch does not reliably
improve over No Update because it misses at least one important changed tool
contract. Full Rewrite also introduces a measurable retention efficiency
regression on Task 260, while the controlled Task 235 ablation shows that an
over-broad rewrite can break termination entirely. The central lesson is that
selective adaptation needs high semantic coverage, while broad rewriting needs
strict scope and output-protocol safeguards.

## Appendix A. Assignment 4.2 traceability

| Minimum report requirement | Coverage in this report | Primary evidence |
|---|---|---|
| Main results: TF, PE, ECS for all three strategies | Sections 4 and 5 | `reports/d/final-comparison.csv` |
| Recovery and retention | Section 5.3 | `reports/d/comparison-analysis.json` |
| Update cost: tokens, time, API cost | Section 7 | `reports/d/cost-analysis.csv` |
| Under-update failure and example trajectory | Section 6.1 | `reports/d/evidence/task2-under-update-sp.json` and paired Full Rewrite evidence |
| Over-update failure and example trajectory | Section 6.3; explicitly labelled supplementary and excluded from formal statistics | `reports/d/evidence/task235-over-update-ablation.json` and paired baseline evidence |
| Discussion of when patching helps, fails, and difficult changes | Section 8 | Paired results, failure analysis, and limitations |

## Reproduction and evidence

- Final audit: `reports/d/final-experiment-audit.json`
- Aggregate results: `reports/d/final-comparison.csv` and
  `reports/d/comparison-analysis.json`
- Detailed scores: `results/summary.csv` and `results/summary.json`
- Failure evidence: `reports/d/failure-analysis.md`
- Cost analysis: `reports/d/cost-analysis.csv`
- Raw trajectories and Judge records: `results/{strategy}/{version}/run-XX/`
- Safe packaged submission: `deliverables/`
