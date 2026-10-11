import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class LocalCanaryReportTest(unittest.TestCase):
    def test_all_versions_have_two_successful_real_model_trajectories(self) -> None:
        report = json.loads(
            (ROOT / "reports/canary-local-qwen35-4b-2/summary.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(report["all_passed"])
        self.assertFalse(report["external_api_used"])
        self.assertEqual(report["task_indices"], [144, 161])
        self.assertEqual(set(report["versions"]), {"early", "middle", "late"})
        for version in report["versions"].values():
            self.assertTrue(version["success"])
            self.assertEqual(len(version["tasks"]), 2)
            for task in version["tasks"].values():
                self.assertTrue(task["success"])
                self.assertEqual(task["tool_error_count"], 0)


if __name__ == "__main__":
    unittest.main()
