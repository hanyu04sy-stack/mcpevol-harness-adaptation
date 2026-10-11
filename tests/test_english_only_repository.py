import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


class EnglishOnlyRepositoryTest(unittest.TestCase):
    def test_tracked_paths_and_contents_contain_no_han_characters(self) -> None:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        paths = [Path(item.decode("utf-8")) for item in result.stdout.split(b"\0") if item]
        violations: list[str] = []

        for relative_path in paths:
            if HAN.search(relative_path.as_posix()):
                violations.append(f"path: {relative_path}")

            content = (ROOT / relative_path).read_bytes().decode("utf-8", errors="ignore")
            match = HAN.search(content)
            if match:
                line = content.count("\n", 0, match.start()) + 1
                violations.append(f"content: {relative_path}:{line}")

        self.assertEqual([], violations, "Non-English tracked content found")


if __name__ == "__main__":
    unittest.main()
