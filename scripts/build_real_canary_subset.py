#!/usr/bin/env python3
"""Build the fixed two-task real-model canary subset."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "external/MCPEvol-Bench/src/custom/data/test_cases/test_cases.json"
OUTPUT = ROOT / "data/subsets/canary-real-2/test_cases.json"
INDICES = (142, 161)


def main() -> None:
    tasks = json.loads(SOURCE.read_text(encoding="utf-8"))
    by_id = {int(task["idx"]): task for task in tasks}
    missing = [idx for idx in INDICES if idx not in by_id]
    if missing:
        raise SystemExit(f"Missing upstream canary tasks: {missing}")
    selected = [by_id[idx] for idx in INDICES]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(selected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {OUTPUT.relative_to(ROOT)} with tasks {list(INDICES)}")


if __name__ == "__main__":
    main()
