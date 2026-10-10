import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SPEC = spec_from_file_location(
    "validate_tool_environments",
    Path(__file__).parents[1] / "scripts/validate_tool_environments.py",
)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ValidateToolEnvironmentsTest(unittest.TestCase):
    def test_summary_counts_servers_tools_and_failures(self) -> None:
        servers = [
            {"server": "ok", "status": "connected", "available": True, "toolCount": 3},
            {"server": "bad", "status": "failed", "available": False, "toolCount": 0},
        ]
        result = MODULE.summarize(
            "early", 3051, 2, servers,
            "Failed to connect to bad: Connection closed\n", 1.25,
        )
        self.assertTrue(result["validation_complete"])
        self.assertEqual(result["connected_server_count"], 1)
        self.assertEqual(result["failed_server_count"], 1)
        self.assertEqual(result["tool_count"], 3)
        self.assertEqual(result["servers"][0]["failure_reason"], "Connection closed")

    def test_timeout_counts_loading_server_as_unavailable(self) -> None:
        servers = [
            {"server": "ok", "status": "connected", "available": True, "toolCount": 2},
            {"server": "slow", "status": "loading", "available": False, "toolCount": 0},
        ]
        result = MODULE.summarize(
            "late", 3053, 2, servers, "", 900.0, timed_out=True,
        )
        self.assertTrue(result["validation_complete"])
        self.assertFalse(result["settled"])
        self.assertEqual(result["failed_server_count"], 1)
        self.assertEqual(result["unresolved_servers"], ["slow"])
        self.assertIn("timeout", result["servers"][1]["failure_reason"].lower())


if __name__ == "__main__":
    unittest.main()
