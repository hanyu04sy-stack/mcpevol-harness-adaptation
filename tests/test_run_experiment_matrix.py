import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_experiment_matrix", ROOT / "scripts/run_experiment_matrix.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RunExperimentMatrixTest(unittest.TestCase):
    def test_default_matrix_has_twenty_seven_benchmark_runs(self) -> None:
        specs = MODULE.build_specs(
            MODULE.STRATEGIES, MODULE.VERSIONS, (1, 2, 3)
        )
        self.assertEqual(len(specs), 27)
        selective = [spec for spec in specs if spec.strategy == "selective_patch"]
        self.assertEqual(len(selective), 9)
        self.assertTrue(
            all(spec.harness_dir.endswith("/" + spec.version) for spec in selective)
        )

    def test_judge_command_pins_five_runs(self) -> None:
        spec = MODULE.RunSpec(
            "selective_patch", "late", 3, "harness/selective_patch/late"
        )
        command = MODULE.judge_command(
            spec, "configs/comparison-subset/experiment.json", 5
        )
        self.assertEqual(command[command.index("--num-runs") + 1], "5")
        self.assertEqual(command[command.index("--run-id") + 1], "3")

    def test_completion_requires_exact_task_set_and_judge_count(self) -> None:
        original_root = MODULE.ROOT
        try:
            with tempfile.TemporaryDirectory() as directory:
                MODULE.ROOT = Path(directory)
                spec = MODULE.RunSpec("no_update", "early", 1, "harness/no_update")
                run = MODULE.result_dir(spec)
                answers = run / "gpt-4o-mini/ANSWER"
                answers.mkdir(parents=True)
                (run / "run-metadata.json").write_text(
                    json.dumps({"status": "completed"}), encoding="utf-8"
                )
                for idx in (2, 28):
                    (answers / f"{idx}.json").write_text(
                        json.dumps({"idx": idx}), encoding="utf-8"
                    )
                self.assertTrue(MODULE.benchmark_complete(spec, {2, 28}))
                (run / "judge-results.json").write_text(
                    json.dumps(
                        {
                            "tasks": [
                                {"task_idx": 2, "successful_judge_runs": 5},
                                {"task_idx": 28, "successful_judge_runs": 5},
                            ]
                        }
                    ),
                    encoding="utf-8",
                )
                self.assertTrue(MODULE.judge_complete(spec, {2, 28}, 5))
                self.assertFalse(MODULE.judge_complete(spec, {2, 28}, 6))
        finally:
            MODULE.ROOT = original_root


if __name__ == "__main__":
    unittest.main()
