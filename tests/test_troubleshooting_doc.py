import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
DOCUMENT = ROOT / "docs/TROUBLESHOOTING.md"


class TroubleshootingDocumentTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = DOCUMENT.read_text(encoding="utf-8")

    def test_covers_required_failure_categories_and_platforms(self) -> None:
        required = (
            "macOS",
            "Linux",
            "端口被占用",
            "版本错误",
            "SHA-256",
            "server 加载失败",
            "check_handoff.py",
        )
        for phrase in required:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_documents_all_isolated_port_ranges(self) -> None:
        for port in range(3051, 3054):
            self.assertIn(str(port), self.text)
        for port in range(3151, 3154):
            self.assertIn(str(port), self.text)
        for port in range(3251, 3254):
            self.assertIn(str(port), self.text)
        for port in range(3351, 3354):
            self.assertIn(str(port), self.text)

    def test_avoids_irrecoverable_cleanup_commands(self) -> None:
        self.assertNotIn("rm -rf", self.text)
        self.assertNotIn("git reset --hard", self.text)


if __name__ == "__main__":
    unittest.main()
