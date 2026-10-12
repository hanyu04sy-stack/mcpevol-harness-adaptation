import copy
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import validate_json_schemas  # noqa: E402


class ValidateJSONSchemasTest(unittest.TestCase):
    def validator(self, filename: str) -> Draft202012Validator:
        schema = json.loads((ROOT / "schemas" / filename).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, format_checker=FormatChecker())

    def test_all_tracked_documents_match_their_schemas(self) -> None:
        report = validate_json_schemas.validate_repository(ROOT)
        self.assertTrue(report["passed"], report["errors"])
        self.assertEqual(report["schemas_checked"], 7)
        self.assertEqual(report["documents_checked"], 19)

    def test_config_schema_rejects_missing_late_version(self) -> None:
        config = json.loads((ROOT / "configs/experiment.json").read_text(encoding="utf-8"))
        invalid = copy.deepcopy(config)
        del invalid["mcp"]["versions"]["late"]
        errors = list(self.validator("experiment-config.schema.json").iter_errors(invalid))
        self.assertTrue(errors)

    def test_task_schema_rejects_invalid_tool_parameters(self) -> None:
        tasks = json.loads((ROOT / "data/subsets/smoke-1/test_cases.json").read_text(encoding="utf-8"))
        invalid = copy.deepcopy(tasks)
        invalid[0]["tool_calls"][0]["parameters"] = "not-an-object"
        errors = list(self.validator("task-list.schema.json").iter_errors(invalid))
        self.assertTrue(errors)

    def test_report_schema_rejects_invalid_hash(self) -> None:
        report = json.loads((ROOT / "reports/pilot-30-coverage.json").read_text(encoding="utf-8"))
        invalid = copy.deepcopy(report)
        invalid["task_file_sha256"] = "bad"
        errors = list(self.validator("validation-report.schema.json").iter_errors(invalid))
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
