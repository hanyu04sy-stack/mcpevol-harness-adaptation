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
        self.assertEqual(report["schemas_checked"], 10)
        self.assertEqual(report["documents_checked"], 20)

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

    def test_judge_metadata_schema_requires_model_audit_fields(self) -> None:
        payload = {
            "schema_version": 1,
            "recorded_at": "2026-10-13T00:00:00+00:00",
            "judge": {
                "name": "deepseek-flash",
                "temperature": 0,
                "api_key_env": "JUDGE_API_KEY",
                "base_url_env": "JUDGE_BASE_URL",
            },
            "configured_model": "deepseek-flash",
            "provider_reported_model": "DeepSeek-V4.1-Flash",
            "provider_reported_models": ["DeepSeek-V4.1-Flash"],
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "attempt_count": 5,
            "valid_score_count": 5,
            "model_usage_audit": {},
            "rate_limit_retry": {},
            "rate_limit_retry_file": "judge-rate-limit-retry.json",
            "input_files": ["1/ANSWER/1.json"],
            "output_file": "judge-results.json",
            "usage": {
                "agent_prompt_tokens": 10,
                "agent_completion_tokens": 2,
                "judge_prompt_tokens": 100,
                "judge_completion_tokens": 20,
                "retry_prompt_tokens": 0,
                "retry_completion_tokens": 0,
                "responses_missing_usage": 0,
            },
            "costs": {
                "currency": "USD",
                "model": "deepseek-flash",
                "agent_est_cost_usd": 0.1,
                "judge_est_cost_usd": 0.1,
                "retry_est_cost_usd": 0,
                "total_est_cost_usd": 0.2,
            },
            "secrets_recorded": False,
        }
        validator = self.validator("judge-metadata.schema.json")
        self.assertEqual(list(validator.iter_errors(payload)), [])
        del payload["attempt_count"]
        self.assertTrue(list(validator.iter_errors(payload)))


if __name__ == "__main__":
    unittest.main()
