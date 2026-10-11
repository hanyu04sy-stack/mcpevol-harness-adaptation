import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import run_real_canary  # noqa: E402


class RealCanaryTest(unittest.TestCase):
    def test_redacts_secret(self) -> None:
        self.assertEqual(
            run_real_canary.redact("header secret-value end", "secret-value"),
            "header [REDACTED_API_KEY] end",
        )

    def test_redacts_provider_masked_key(self) -> None:
        self.assertEqual(
            run_real_canary.redact("invalid sk-example****tail value", ""),
            "invalid [REDACTED_API_KEY] value",
        )

    def test_trajectory_requires_successful_tool_use(self) -> None:
        valid = run_real_canary.validate_trajectory(
            {
                "stop": True,
                "exceeded": False,
                "answer": "done",
                "trajectory_messages": [
                    {"role": "tool", "content": "result"},
                ],
            }
        )
        invalid = run_real_canary.validate_trajectory(
            {
                "stop": True,
                "exceeded": False,
                "answer": "done",
                "trajectory_messages": [],
            }
        )
        self.assertTrue(valid["success"])
        self.assertFalse(invalid["success"])


if __name__ == "__main__":
    unittest.main()
