import unittest
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
SPEC = spec_from_file_location(
    "validate_startup_stability",
    Path(__file__).parents[1] / "scripts/validate_startup_stability.py",
)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def trial(alpha="connected", beta="connected"):
    servers = [
        {"name": "alpha", "status": alpha},
        {"name": "beta", "status": beta},
    ]
    failed = sum(server["status"] != "connected" for server in servers)
    return {
        "configured_server_count": 2,
        "validation_complete": True,
        "connected_server_count": 2 - failed,
        "failed_server_count": failed,
        "servers": servers,
    }


class ValidateStartupStabilityTest(unittest.TestCase):
    def test_reports_all_trials_stable(self) -> None:
        result = MODULE.summarize_trials([trial(), trial(), trial()])
        self.assertTrue(result["all_trials_successful"])
        self.assertEqual(result["stable_connected_server_count"], 2)
        self.assertEqual(result["flaky_or_unavailable_servers"], [])

    def test_reports_intermittent_failure(self) -> None:
        result = MODULE.summarize_trials([trial(), trial(beta="failed"), trial()])
        self.assertFalse(result["all_trials_successful"])
        self.assertEqual(result["flaky_or_unavailable_servers"], ["beta"])
        self.assertEqual(
            result["servers"]["beta"]["statuses"],
            ["connected", "failed", "connected"],
        )


if __name__ == "__main__":
    unittest.main()
