#!/usr/bin/env python3
"""Validate tracked repository JSON documents against Draft 2020-12 schemas."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_FILES = {
    "experiment": "experiment-config.schema.json",
    "tasks": "task-list.schema.json",
    "manifest": "subset-manifest.schema.json",
    "report": "validation-report.schema.json",
    "tool_schema": "tool-schema-report.schema.json",
    "tool_changes": "tool-changes.schema.json",
    "summary": "summary.schema.json",
    "pricing": "pricing.schema.json",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validation_targets(root: Path) -> list[tuple[str, Path]]:
    targets: list[tuple[str, Path]] = []
    targets.extend(
        ("experiment", path)
        for path in sorted((root / "configs").glob("*.json"))
        if "experiment_name" in read_json(path)
    )
    targets.append(("pricing", root / "configs/pricing.json"))
    targets.extend(("tasks", path) for path in sorted((root / "data/subsets").glob("*/test_cases.json")))
    targets.extend(("manifest", path) for path in sorted((root / "data/subsets").glob("*/manifest.json")))
    targets.extend(
        ("report", root / path)
        for path in [
            "reports/environment-validation.json",
            "reports/pilot-30-coverage.json",
            "reports/pilot-30-environment-validation.json",
            "reports/pilot-30-runnability-matrix.json",
            "reports/pilot-30-startup-stability.json",
            "reports/smoke/summary.json",
            "reports/canary-local-qwen35-4b-2/summary.json",
        ]
    )
    targets.extend(
        ("tool_schema", root / f"reports/tool-schemas/{version}.json")
        for version in ("early", "middle", "late")
    )
    targets.append(("tool_changes", root / "reports/tool-changes.json"))
    result_summary = root / "results/summary.json"
    if result_summary.is_file():
        targets.append(("summary", result_summary))
    return targets


def format_path(parts: Any) -> str:
    return "$" + "".join(f"[{part}]" if isinstance(part, int) else f".{part}" for part in parts)


def validate_repository(root: Path) -> dict[str, Any]:
    validators: dict[str, Draft202012Validator] = {}
    schema_dir = root / "schemas"
    for name, filename in SCHEMA_FILES.items():
        schema = read_json(schema_dir / filename)
        Draft202012Validator.check_schema(schema)
        validators[name] = Draft202012Validator(schema, format_checker=FormatChecker())

    checked: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []
    for schema_name, path in validation_targets(root):
        if not path.is_file():
            failures.append({"file": str(path.relative_to(root)), "path": "$", "message": "file is missing"})
            continue
        document = read_json(path)
        errors = sorted(validators[schema_name].iter_errors(document), key=lambda error: list(error.path))
        relative = str(path.relative_to(root))
        if errors:
            failures.extend(
                {"file": relative, "path": format_path(error.absolute_path), "message": error.message}
                for error in errors
            )
        else:
            checked.append({"file": relative, "schema": SCHEMA_FILES[schema_name]})

    return {
        "schema_version": 1,
        "passed": not failures,
        "draft": "2020-12",
        "schemas_checked": len(validators),
        "documents_checked": len(checked),
        "checked": checked,
        "errors": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        report = validate_repository(args.root.resolve())
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from exc
    stream = sys.stdout if report["passed"] else sys.stderr
    print(json.dumps(report, ensure_ascii=False, indent=2), file=stream)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
