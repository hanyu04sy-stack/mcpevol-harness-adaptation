import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SPEC = spec_from_file_location(
    "build_subset", Path(__file__).parents[1] / "scripts/build_subset.py"
)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def make_task(idx: int, server: str) -> dict:
    return {"idx": idx, "question": f"task {idx}", "servers": {server: ["tool"]}}


class BuildSubsetTest(unittest.TestCase):
    def test_subset_is_deterministic_and_contains_retention(self) -> None:
        tasks = [
            make_task(0, "tool-change"),
            make_task(1, "parameter-change"),
            make_task(2, "description-change"),
            make_task(3, "tool-change"),
            make_task(4, "unchanged-a"),
            make_task(5, "unchanged-b"),
        ]
        server_types = {
            "tool-change": {"tool"},
            "parameter-change": {"parameter"},
            "description-change": {"description"},
        }
        first, manifest = MODULE.select_subset(tasks, server_types, size=5, seed=6203)
        second, _ = MODULE.select_subset(tasks, server_types, size=5, seed=6203)
        self.assertEqual([x["idx"] for x in first], [x["idx"] for x in second])
        self.assertEqual(manifest["affected_count"], 4)
        self.assertEqual(manifest["retention_count"], 1)
        self.assertEqual(
            set(manifest["change_type_task_counts"]),
            {"tool", "parameter", "description"},
        )

    def test_connected_servers_requires_real_connected_status(self) -> None:
        report = {
            "versions": {
                version: {
                    "servers": [
                        {"name": "stable", "status": "connected", "available": True},
                        {"name": "failed", "status": "failed", "available": False},
                    ]
                }
                for version in ("early", "middle", "late")
            }
        }
        result = MODULE.connected_servers(report)
        self.assertEqual(result["late"], {"stable"})


if __name__ == "__main__":
    unittest.main()
