# Selective Patch Harness

C's deterministic method compares Early tool contracts directly with each target version. It copies the original system prompt byte for byte and adds only changed-tool rules inside the existing Injected rules section. Early remains unchanged. Tool names are scoped by server. Renames remain separate removal/addition events; no replacement is guessed. Parameter differences retain their current field contracts, including nested constraints. Changed description lines are preserved. JSON braces are escaped for the upstream prompt formatter. At runtime the runner selects only rules for the task's available tools and removals from its servers; the full version file remains the audit catalog.

## Generate and run

```bash
.venv/bin/python scripts/build_selective_patch.py --target early
.venv/bin/python scripts/build_selective_patch.py --target middle
.venv/bin/python scripts/build_selective_patch.py --target late
.venv/bin/python scripts/check_experiment_config.py --config configs/comparison-subset/experiment.json
.venv/bin/python scripts/verify_untouched.py --config configs/comparison-subset/experiment.json
.venv/bin/python scripts/run_benchmark.py --version middle --config configs/comparison-subset/experiment.json --harness-dir harness/selective_patch/middle --dry-run --print-resolved-prompt
```

Start the matching MCP server using docs/HANDOFF.md before a real run. The exact paid run and Judge commands, plus the completed C run evidence, are in `reports/selective-patch/README.md`. The runner integration places all versions under results/selective_patch/<version>/run-XX, and rejects mismatched versions and incomplete evidence. `--print-resolved-prompt` shows the complete catalog; the actual task prompt selects its relevant sections and is visible in the trajectory. A shared completion protocol tells every strategy to emit `[FINISH]` after finishing tool work, matching the upstream agent stop condition. The OpenRouter adapter maps the pinned canonical `gpt-4o-mini` name to `openai/gpt-4o-mini` at the API boundary for model and judge.

Each version contains system_prompt.md, tool_usage_rules.md, manifest.json and patch-audit.json. The manifest records source hashes, target version, unknown servers, changed-tool count, generation time and patch bytes. Adaptation makes no API calls, so adaptation API cost and API tokens are zero. Bytes are not token counts. Runtime inference and judging costs are separate. C's formal run used one Judge pass per task to limit calls; the repository report records this protocol and its comparison limits.

## Late schema refresh

The original committed Late snapshot had only 12/26 connected servers. It has now been refreshed with isolated per-server discovery and contains 26/26 connected servers and 318 tools. The regenerated Late patch has 38 changed tools and is marked formal_run_ready=true. The updated snapshot and change reports are included in this checkout. Source report hashes in the manifest bind this patch to those files. If the snapshot is regenerated again, rebuild the patch before running experiments.

The generator still rejects an incomplete snapshot by default. `--allow-incomplete` is an inspection-only option; it marks the resulting manifest formal_run_ready=false, which the formal runner and judge reject.

## Validation and method limitations

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python scripts/check_handoff.py
```

Offline tests cover discovery failures, change categories, unchanged Early rules, exact prompt preservation, actual injection and prompt formatting, version guards and strategy output paths. TF/PE/ECS for C's completed formal run are in `reports/selective-patch/summary.json`.

The original harness contains generic rules rather than per-tool memory: this method adds focused changed-tool knowledge. State this assumption in the report. Future tool-specific original rules could conflict with appended patches and would require explicit rule ownership. No semantic rename mappings are inferred. Updated description lines are copied verbatim (ASCII JSON escaped). Added-tool purpose text is capped at 240 characters because the full live description is already passed in the MCP tool list. The patch is tool-granular and the runtime selector is task-specific.

## C deliverables

C provides the generated Early/Middle/Late harnesses, generator, schema evidence, patch audit, adaptation timing records, and the result report with raw trajectories. The earlier one-task pilot (task 218 in Middle) was only a smoke check and is not included in the formal summary. The task 28 diagnostic is kept separate from the formal result; see `reports/selective-patch/failure-review.md` and `diagnostic-results.zip` in that report directory.
