import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts/dump_tool_schemas.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("dump_tool_schemas", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class DumpToolSchemasTest(unittest.TestCase):
    def test_groups_aggregated_tools_by_server_and_removes_prefix(self) -> None:
        grouped = MODULE.split_aggregated_tools(
            [
                {
                    "name": "alpha_1mcp_lookup",
                    "description": "Lookup",
                    "inputSchema": {"type": "object"},
                },
                {
                    "name": "alpha-long_1mcp_search",
                    "description": "Search",
                    "inputSchema": {"type": "object"},
                },
            ],
            ["alpha", "alpha-long"],
        )
        self.assertEqual(grouped["alpha"][0]["name"], "lookup")
        self.assertEqual(grouped["alpha-long"][0]["name"], "search")

    def test_diff_classifies_added_removed_description_and_schema_changes(self) -> None:
        old = {
            "version": "early",
            "servers": [
                {
                    "name": "server",
                    "tools": [
                        {"name": "removed", "description": "old", "inputSchema": {}},
                        {"name": "changed", "description": "old", "inputSchema": {}},
                    ],
                }
            ],
        }
        new = {
            "version": "middle",
            "servers": [
                {
                    "name": "server",
                    "tools": [
                        {"name": "added", "description": "new", "inputSchema": {}},
                        {
                            "name": "changed",
                            "description": "new",
                            "inputSchema": {"type": "object"},
                        },
                    ],
                }
            ],
        }
        result = MODULE.diff_reports(old, new)
        self.assertEqual(result["summary"]["added_tool_count"], 1)
        self.assertEqual(result["summary"]["removed_tool_count"], 1)
        self.assertEqual(result["summary"]["changed_tool_count"], 1)
        self.assertTrue(result["changed_tools"][0]["description_changed"])
        self.assertTrue(result["changed_tools"][0]["input_schema_changed"])

    def test_unmatched_aggregated_tool_is_rejected(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "cannot map"):
            MODULE.split_aggregated_tools(
                [{"name": "unknown", "description": "", "inputSchema": {}}],
                ["server"],
            )


if __name__ == "__main__":
    unittest.main()
