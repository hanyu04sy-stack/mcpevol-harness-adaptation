import hashlib
import tempfile
import unittest
import zipfile
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


SPEC = spec_from_file_location(
    "download_server_bundles", Path(__file__).parents[1] / "scripts/download_server_bundles.py"
)
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class DownloadServerBundlesTest(unittest.TestCase):
    def test_hash_verification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.zip"
            path.write_bytes(b"known content")
            expected = hashlib.sha256(b"known content").hexdigest()
            MODULE.verify(path, len(b"known content"), expected)
            with self.assertRaises(ValueError):
                MODULE.verify(path, len(b"known content"), "0" * 64)

    def test_rejects_zip_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "unsafe.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../escape.txt", "bad")
            with self.assertRaises(ValueError):
                MODULE.safe_extract(archive, root / "output")
            self.assertFalse((root / "escape.txt").exists())

    def test_repair_extract_restores_missing_and_truncated_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "bundle.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("nested/one.txt", "complete")
                bundle.writestr("two.txt", "restored")
            output = root / "output"
            output.mkdir()
            (output / "nested").mkdir()
            (output / "nested/one.txt").write_text("bad", encoding="utf-8")
            repaired = MODULE.repair_extract(archive, output)
            self.assertEqual(repaired, 2)
            self.assertEqual(
                (output / "nested/one.txt").read_text(encoding="utf-8"), "complete"
            )
            self.assertEqual(
                (output / "two.txt").read_text(encoding="utf-8"), "restored"
            )


if __name__ == "__main__":
    unittest.main()
