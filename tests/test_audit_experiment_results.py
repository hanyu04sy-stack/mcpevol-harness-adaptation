import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_experiment_results", ROOT / "scripts/audit_experiment_results.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AuditExperimentResultsTest(unittest.TestCase):
    def make_project(self, root: Path) -> Path:
        tasks = root / "tasks.json"
        tasks.write_text(json.dumps([{"idx": 2}]), encoding="utf-8")
        config = {
            "benchmark": {"commit": "a" * 40},
            "dataset": {"path": "tasks.json", "sha256": MODULE.sha256(tasks)},
            "model": {
                "name": "gpt-4o-mini",
                "temperature": 0.0,
                "max_completion_tokens": 4096,
            },
            "judge": {"name": "gpt-4o-mini", "temperature": 0.0},
        }
        path = root / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def make_run(self, root: Path, strategy: str, version: str) -> None:
        run = root / "results" / strategy / version / "run-01"
        run.mkdir(parents=True)
        (run / "run-metadata.json").write_text(
            json.dumps(
                {
                    "strategy": strategy,
                    "version": version,
                    "run_id": 1,
                    "benchmark_commit": "a" * 40,
                    "task_sha256": MODULE.sha256(root / "tasks.json"),
                    "status": "completed",
                    "model": {
                        "name": "gpt-4o-mini",
                        "temperature": 0.0,
                        "max_completion_tokens": 4096,
                    },
                    "judge": {"name": "gpt-4o-mini", "temperature": 0.0},
                    "harness_manifest_sha256": "b" * 64,
                    "harness_files": [{}, {}, {}],
                    "mcp_status_at_start": {
                        "connected_servers": 26,
                        "observed_servers": 26,
                    },
                    "total_prompt_tokens": 100,
                    "total_completion_tokens": 10,
                    "wall_clock_seconds": 1.0,
                }
            ),
            encoding="utf-8",
        )
        (run / "judge-results.json").write_text(
            json.dumps(
                {
                    "tasks": [
                        {
                            "task_idx": 2,
                            "successful_judge_runs": 5,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (run / "judge-metadata.json").write_text(
            json.dumps(
                {
                    "num_runs_requested_per_task": 5,
                    "total_prompt_tokens": 50,
                    "total_completion_tokens": 5,
                }
            ),
            encoding="utf-8",
        )

    def test_complete_matrix_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.make_project(root)
            for strategy in MODULE.STRATEGIES:
                for version in MODULE.VERSIONS:
                    self.make_run(root, strategy, version)
            report = MODULE.audit(root, config, (1,), 5)
            self.assertTrue(report["passed"])
            self.assertEqual(report["config"], "config.json")
            self.assertEqual(report["completed_runs"], 9)
            self.assertEqual(report["scored_tasks"], 9)

    def test_missing_matrix_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.make_project(root)
            report = MODULE.audit(root, config, (1,), 5)
            self.assertFalse(report["passed"])
            self.assertEqual(len(report["issues"]), 9)


if __name__ == "__main__":
    unittest.main()
