import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SPEC = spec_from_file_location(
    "validate_subset_coverage",
    Path(__file__).parents[1] / "scripts/validate_subset_coverage.py",
)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ValidateSubsetCoverageTest(unittest.TestCase):
    def fixture(self):
        tasks = [
            {"idx": 1, "servers": {"changed": ["tool"]}},
            {"idx": 2, "servers": {"stable": ["tool"]}},
        ]
        manifest = {
            "benchmark_commit": "abc",
            "selected_indices": [1, 2],
            "affected_count": 1,
            "retention_count": 1,
            "change_type_task_counts": {
                "description": 1,
                "parameter": 1,
                "tool": 1,
            },
            "selected_task_details": [
                {
                    "idx": 1,
                    "status": "affected",
                    "affected_servers": ["changed"],
                    "change_types": ["description", "parameter", "tool"],
                    "required_servers": ["changed"],
                },
                {
                    "idx": 2,
                    "status": "retention",
                    "affected_servers": [],
                    "change_types": [],
                    "required_servers": ["stable"],
                },
            ],
        }
        return tasks, manifest

    def test_accepts_complete_coverage(self) -> None:
        tasks, manifest = self.fixture()
        report = MODULE.validate_coverage(tasks, manifest)
        self.assertTrue(report["passed"])
        self.assertTrue(all(report["requirements"].values()))

    def test_rejects_missing_retention(self) -> None:
        tasks, manifest = self.fixture()
        tasks.pop()
        manifest["selected_indices"].pop()
        manifest["selected_task_details"].pop()
        manifest["retention_count"] = 0
        with self.assertRaisesRegex(ValueError, "retention_tasks"):
            MODULE.validate_coverage(tasks, manifest)


if __name__ == "__main__":
    unittest.main()
