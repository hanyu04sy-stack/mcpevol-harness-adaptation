#!/usr/bin/env python3
"""Materialize the frozen, version-invariant Full Rewrite baseline.

The evaluated baseline deliberately replaces all original tool-use guidance
with one generic rule set that defers to the live ``tools/list`` schema.  The
same text is materialized under each version directory so the matrix runner
can select it uniformly.  The schema snapshots are provenance/validation
inputs; this script does not synthesize schema-specific prose from them.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "harness/full_rewrite"
VERSIONS = ("early", "middle", "late")


def main() -> None:
    base = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    for version in VERSIONS:
        destination = SOURCE / version
        destination.mkdir(parents=True, exist_ok=True)
        for name in ("system_prompt.md", "tool_usage_rules.md"):
            shutil.copyfile(SOURCE / name, destination / name)
        manifest = dict(base)
        manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
        manifest["target_version"] = version
        manifest["source_files"] = [
            {"path": "harness/original/system_prompt.md"},
            {"path": "harness/original/tool_usage_rules.md"},
            {"path": f"reports/tool-schemas/{version}.json"},
            {"path": "configs/comparison-subset/experiment.json"},
            {"path": "configs/fairness-pins.json"},
        ]
        manifest["adaptation_cost"] = {
            "generation_mode": "deterministic_manual_template",
            "api_prompt_tokens": 0,
            "api_completion_tokens": 0,
            "api_cost_usd": 0,
            "notes": (
                "Version-invariant full-harness rewrite materialized for "
                f"{version}. It discards stale tool-specific guidance and defers "
                "to the live tools/list schema; the schema snapshot is retained "
                "for provenance, not transformed into version-specific prose. "
                "Runtime model and judge costs are recorded separately."
            ),
        }
        (destination / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {destination.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
