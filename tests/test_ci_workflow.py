import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / ".github/workflows/ci.yml"


class CIWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_runs_the_same_gate_on_pinned_ubuntu_and_macos_images(self) -> None:
        self.assertIn("ubuntu-24.04", self.workflow)
        self.assertIn("macos-15", self.workflow)
        self.assertIn("runs-on: ${{ matrix.os }}", self.workflow)
        self.assertIn("fail-fast: false", self.workflow)
        self.assertIn("python scripts/check_handoff.py", self.workflow)

    def test_never_downloads_or_starts_large_environments(self) -> None:
        run_commands = "\n".join(
            line.strip().lower()
            for line in self.workflow.splitlines()
            if line.lstrip().startswith("run:")
        )
        forbidden_commands = (
            "scripts/setup_environment.py",
            "scripts/download_server_bundles.py",
            "scripts/run_smoke_tests.py",
            "scripts/run_local_canary.py",
            "pnpm run",
            "ollama",
        )
        for command in forbidden_commands:
            with self.subTest(command=command):
                self.assertNotIn(command, run_commands)


if __name__ == "__main__":
    unittest.main()
