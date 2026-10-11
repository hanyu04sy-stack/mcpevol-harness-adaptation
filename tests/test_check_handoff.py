import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import check_handoff  # noqa: E402


class CheckHandoffTest(unittest.TestCase):
    def test_repository_inventory_is_complete(self) -> None:
        report = check_handoff.check_inventory(ROOT)
        self.assertTrue(report["passed"], report)
        self.assertGreaterEqual(report["required_file_count"], 70)
        self.assertEqual(report["missing"], [])

    def test_inventory_reports_missing_and_empty_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "empty.json").touch()
            report = check_handoff.check_inventory(
                root, {"example": ["missing.json", "empty.json"]}
            )
        self.assertFalse(report["passed"])
        self.assertEqual(report["missing"], ["missing.json"])
        self.assertEqual(report["empty"], ["empty.json"])

    def test_command_failure_is_machine_readable(self) -> None:
        result = check_handoff.run_check(
            "example",
            [sys.executable, "-c", "import sys; print('broken'); sys.exit(3)"],
            ROOT,
        )
        self.assertFalse(result["passed"])
        self.assertEqual(result["returncode"], 3)
        self.assertIn("broken", result["output_tail"])


if __name__ == "__main__":
    unittest.main()
