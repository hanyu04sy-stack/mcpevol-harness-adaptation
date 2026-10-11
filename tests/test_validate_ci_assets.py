import hashlib
import json
import tempfile
import unittest
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SPEC = spec_from_file_location(
    "validate_ci_assets",
    Path(__file__).parents[1] / "scripts/validate_ci_assets.py",
)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ValidateCIAssetsTest(unittest.TestCase):
    def test_repository_assets_are_consistent(self) -> None:
        root = Path(__file__).parents[1]
        report = MODULE.validate_repository(root)
        self.assertTrue(report["passed"])
        self.assertFalse(report["server_bundles_used"])
        self.assertEqual(report["configs_checked"], 4)

    def test_rejects_task_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tasks.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "idx": 1,
                            "question": "test",
                            "servers": {"time": ["convert_time"]},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            wrong_hash = hashlib.sha256(b"different").hexdigest()
            with self.assertRaisesRegex(MODULE.ValidationError, "SHA-256"):
                MODULE.validate_tasks(path, 1, wrong_hash)


if __name__ == "__main__":
    unittest.main()
