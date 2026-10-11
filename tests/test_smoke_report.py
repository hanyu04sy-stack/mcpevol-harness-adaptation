import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class SmokeReportTest(unittest.TestCase):
    def test_all_versions_have_successful_raw_trajectories(self) -> None:
        report = json.loads(
            (ROOT / "reports/smoke/summary.json").read_text(encoding="utf-8")
        )
        self.assertTrue(report["all_passed"])
        self.assertFalse(report["external_api_used"])
        self.assertEqual(set(report["versions"]), {"early", "middle", "late"})
        for version, result in report["versions"].items():
            self.assertTrue(result["success"], version)
            self.assertEqual(result["tool_message_count"], 4)
            self.assertEqual(result["tool_errors"], [])
            trajectory = json.loads(
                (ROOT / result["trajectory"]).read_text(encoding="utf-8")
            )
            self.assertTrue(trajectory["stop"])
            self.assertFalse(trajectory["exceeded"])


if __name__ == "__main__":
    unittest.main()
