import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import verify_untouched  # noqa: E402


class VerifyUntouchedTest(unittest.TestCase):
    def make_project(self, root: Path) -> tuple[Path, Path, Path]:
        upstream = root / "external/MCPEvol-Bench"
        upstream.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=upstream, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=upstream, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=upstream, check=True)
        (upstream / "source.py").write_text("clean\n", encoding="utf-8")
        subprocess.run(["git", "add", "source.py"], cwd=upstream, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=upstream, check=True)
        task = root / "data/tasks.json"
        task.parent.mkdir()
        task.write_text("[]\n", encoding="utf-8")
        task_hash = hashlib.sha256(task.read_bytes()).hexdigest()
        config = {
            "benchmark": {"root": "external/MCPEvol-Bench", "commit": "abc"},
            "dataset": {"path": "data/tasks.json", "sha256": task_hash},
            "model": {"name": "gpt-4o", "temperature": 0.0},
            "judge": {"name": "gpt-4o", "temperature": 0.0},
        }
        config_path = root / "config.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        pins_path = root / "pins.json"
        pins_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "model.name": "gpt-4o",
                    "model.temperature": 0.0,
                    "judge.name": "gpt-4o",
                    "judge.temperature": 0.0,
                    "benchmark.commit": "abc",
                }
            ),
            encoding="utf-8",
        )
        return config_path, pins_path, task

    def check(self, root: Path, config: Path, pins: Path) -> dict:
        return verify_untouched.check_fairness(
            config_path=config,
            pins_path=pins,
            report_path=root / "report.json",
            root=root,
        )

    def test_clean_inputs_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, pins, _ = self.make_project(root)
            self.assertTrue(self.check(root, config, pins)["passed"])

    def test_changed_task_hash_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, pins, task = self.make_project(root)
            task.write_text("[1]\n", encoding="utf-8")
            self.assertFalse(self.check(root, config, pins)["task_sha256_match"])

    def test_dirty_upstream_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, pins, _ = self.make_project(root)
            (root / "external/MCPEvol-Bench/source.py").write_text("dirty\n", encoding="utf-8")
            self.assertFalse(self.check(root, config, pins)["upstream_clean"])


if __name__ == "__main__":
    unittest.main()
