import hashlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import repair_late_dataless  # noqa: E402


class RepairLateDatalessTest(unittest.TestCase):
    def test_dry_run_and_repeated_repair_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "archives/late.zip"
            archive.parent.mkdir()
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("node_modules/example/index.js", "ready\n")
            spec = {
                "filename": "late.zip",
                "directory": "iter5_servers",
                "size": archive.stat().st_size,
                "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            }
            with patch.dict(repair_late_dataless.BUNDLES, {"late": spec}, clear=True):
                plan = repair_late_dataless.repair_late(root, dry_run=True)
                self.assertEqual(plan["files_to_restore"], 1)
                first = repair_late_dataless.repair_late(root)
                second = repair_late_dataless.repair_late(root)
            self.assertEqual(first["repaired_files"], 1)
            self.assertEqual(second["repaired_files"], 0)


if __name__ == "__main__":
    unittest.main()
