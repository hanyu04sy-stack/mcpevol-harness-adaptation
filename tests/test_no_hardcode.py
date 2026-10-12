import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
import sys

sys.path.insert(0, str(ROOT / "scripts"))
import run_benchmark  # noqa: E402


class NoHardcodeTest(unittest.TestCase):
    def test_runner_step_is_read_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "experiment.json"
            path.write_text(json.dumps({"runner": {"step": 5}}), encoding="utf-8")
            configured_step = json.loads(path.read_text(encoding="utf-8"))["runner"]["step"]
        resolved = {
            "benchmark_runner": "runner.py",
            "runner_step": configured_step,
            "model_name": "model",
            "task_file": "tasks.json",
            "mcp_url": "http://127.0.0.1:3051/mcp",
            "output_dir": "results",
            "runner_part_num": -1,
            "runner_part_idx": 0,
            "runner_fschat": False,
        }
        arguments = run_benchmark.upstream_arguments(resolved)
        self.assertEqual(arguments[arguments.index("--step") + 1], "5")


if __name__ == "__main__":
    unittest.main()
