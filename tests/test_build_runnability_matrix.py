import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SPEC = spec_from_file_location(
    "build_runnability_matrix",
    Path(__file__).parents[1] / "scripts/build_runnability_matrix.py",
)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def environment(status_by_version):
    return {
        "benchmark_commit": "abc",
        "versions": {
            version: {
                "validation_complete": True,
                "servers": [
                    {"name": name, "status": status}
                    for name, status in statuses.items()
                ],
            }
            for version, statuses in status_by_version.items()
        },
    }


class BuildRunnabilityMatrixTest(unittest.TestCase):
    def test_builds_task_by_version_matrix(self) -> None:
        tasks = [{"idx": 7, "servers": {"alpha": ["tool"]}}]
        report = environment(
            {
                "early": {"alpha": "connected"},
                "middle": {"alpha": "connected"},
                "late": {"alpha": "connected"},
            }
        )
        matrix = MODULE.build_matrix(tasks, report)
        self.assertTrue(matrix["all_tasks_runnable_in_all_versions"])
        self.assertEqual(matrix["version_summary"]["late"]["runnable_task_count"], 1)

    def test_marks_failed_or_unobserved_dependency_unrunnable(self) -> None:
        tasks = [{"idx": 7, "servers": {"alpha": ["tool"], "beta": ["tool"]}}]
        report = environment(
            {
                "early": {"alpha": "connected", "beta": "connected"},
                "middle": {"alpha": "connected", "beta": "failed"},
                "late": {"alpha": "connected"},
            }
        )
        matrix = MODULE.build_matrix(tasks, report)
        self.assertFalse(matrix["all_tasks_runnable_in_all_versions"])
        self.assertEqual(
            matrix["tasks"][0]["versions"]["middle"]["unavailable_servers"],
            ["beta"],
        )
        self.assertEqual(
            matrix["tasks"][0]["versions"]["late"]["server_statuses"]["beta"],
            "not_observed",
        )


if __name__ == "__main__":
    unittest.main()
