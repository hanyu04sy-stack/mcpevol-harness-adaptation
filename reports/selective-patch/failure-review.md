# Selective Patch failure review

This is an offline review of the completed C run. The 69 scored task rows contain 11 scores below the configured success threshold, across five distinct task IDs. The corresponding `failure_category` values remain `unknown` in `summary.json`: a low Judge score alone cannot establish that the patch caused a failure. Full trajectories and per-task Judge records are in `raw-results.zip` under `selective_patch/<version>/run-20/`.

| Task | Versions below threshold | Observed evidence | Current attribution |
| --- | --- | --- | --- |
| 161 | Early, Middle, Late | The architecture-documentation lookup found no projects; time conversion succeeded. This is a retention task, and the Early Selective Patch knowledge files are byte-identical to the original harness. | No evidence of over-update. |
| 2 | Early, Middle, Late | The agent searched for suitable AI agents and drafted a plan, but the search did not identify a suitable agent. | The record does not show a missed changed-tool rule. |
| 28 | Early, Middle, Late | Reads of `./anotation_path/txt/log_yesterday.txt` and `log_today.txt` returned missing-parent-directory errors. Early and Middle then repeated the failed reads until the step limit. | Input-path or environment failure is directly visible; patch causation is unproven. |
| 281 | Middle | `split_tasks` rejected ten `tasksRaw` values with an extra trailing `}`; removing that character makes the first value a valid five-task JSON array. The agent exhausted its steps. The patch audit has no change entry for `split_tasks`. | Tool-call formatting failure; not established as under-update. |
| 386 | Late | `split_tasks` rejected ten `tasksRaw` values with an extra trailing `}`; removing that character makes the first value a valid five-task JSON array. The agent exhausted its steps. The patch audit has no change entry for `split_tasks`. | Tool-call formatting failure; not established as under-update. |

The source benchmark checkout contains the text files requested by task 28, but the tool responses in this run resolved the path under the project checkout and reported that its parent directory was absent. Changing the input-file setup would change the experimental conditions; do not overwrite the archived results or silently reinterpret them.

The runner now creates a temporary local link to the benchmark assets at both the agent and tool-server working directories, then removes the links after the run. An offline path check confirms that task 28's text file can be read from both directories. This correction applies to future runs only; the archived trajectories and scores above remain unchanged.

## Targeted task 28 diagnostic after the path correction

Task 28 alone was rerun once in each environment, using the same Selective Patch harness and model/Judge settings. Its sanitized evidence is in `diagnostic-results.zip`, separate from the 23-task formal run; the original `summary.json` and `summary.csv` have not been replaced. Each new trajectory read both log files successfully and used `tasks_setup`/`tasks_add` to create a to-do entry. The first `tasks_setup` attempt in each trajectory had an invalid `source_path:` argument; the agent retried with the correct argument and created the task. There was one benchmark trajectory and one successful Judge scoring run per environment; each trajectory could involve multiple model requests.

| Version | Original TF / PE | Diagnostic TF / PE | Diagnostic outcome |
| --- | --- | --- | --- |
| Early | 1 / 3 | 10 / 8 | Judge success; file read and task creation succeeded. |
| Middle | 1 / 3 | 10 / 8 | Judge success; file read and task creation succeeded. |
| Late | 4 / 7 | 4 / 6 | Judge failure: the tools succeeded, but the final answer contained only `[FINISH]`, with no requested comparison or summary. |

These paired observations support the path failure as a cause of the original task 28 failures, while showing that the path fix alone does not guarantee Late task success. The Late trajectory has `stop=true` and `exceeded=false`, and its final assistant message is exactly `[FINISH]`; there is no evidence that the runner truncated a longer answer or hit the step limit. The final-answer omission cannot be attributed to the Selective Patch from this single trajectory. Judge scores are single-run observations, and the diagnostic must not be pooled with the original formal comparison. The generated `tasks.md` from each diagnostic was saved outside the repository and removed from the benchmark assets before the next environment ran.

The assignment asks for an under-update and an over-update example trajectory. These C records do not yet prove either category. In particular, task 161 cannot demonstrate damage from the patch because it also failed in Early, where the patch made no knowledge change. Any report using these trajectories should distinguish observed failures from causal examples. A controlled diagnostic or a new, consistently configured run would be needed if the group wants to establish patch-specific examples.
