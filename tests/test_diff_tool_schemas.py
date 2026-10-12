import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import diff_tool_schemas  # noqa: E402


def tool(name: str, description: str, properties: dict | None = None) -> dict:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties or {},
        },
    }


def report(version: str, tools: list[dict]) -> dict:
    return {
        "version": version,
        "servers": [{"name": "weather", "status": "connected", "tools": tools}],
    }


class DiffToolSchemasTest(unittest.TestCase):
    def setUp(self) -> None:
        self.early = report(
            "early",
            [
                tool("removed", "Removed tool"),
                tool("described", "Old description"),
                tool(
                    "forecast",
                    "Forecast",
                    {
                        "city": {"type": "string"},
                        "units": {"type": "string"},
                    },
                ),
            ],
        )
        self.middle = report(
            "middle",
            [
                tool("added", "Added tool"),
                tool("described", "New description"),
                tool(
                    "forecast",
                    "Forecast",
                    {
                        "location": {"type": "string"},
                        "units": {"type": "string", "enum": ["metric", "imperial"]},
                        "days": {"type": "integer"},
                    },
                ),
            ],
        )

    def result(self) -> dict:
        return diff_tool_schemas.comparison(self.early, self.middle)["servers"][0]

    def test_detects_added_tool_with_complete_schema(self) -> None:
        added = self.result()["added_tools"]
        self.assertEqual([item["name"] for item in added], ["added"])
        self.assertIn("inputSchema", added[0])

    def test_detects_removed_tool_with_complete_schema(self) -> None:
        removed = self.result()["removed_tools"]
        self.assertEqual([item["name"] for item in removed], ["removed"])
        self.assertEqual(removed[0]["description"], "Removed tool")

    def test_detects_changed_description(self) -> None:
        changes = self.result()["changed_descriptions"]
        self.assertEqual(changes, [{"name": "described", "before": "Old description", "after": "New description"}])

    def test_detects_added_renamed_and_modified_parameters(self) -> None:
        change = self.result()["changed_parameters"][0]
        details = change["parameters"]
        self.assertEqual([item["name"] for item in details["added"]], ["days"])
        self.assertEqual(details["renamed"][0]["before"]["name"], "city")
        self.assertEqual(details["renamed"][0]["after"]["name"], "location")
        self.assertEqual([item["name"] for item in details["modified"]], ["units"])

    def test_detects_tool_rename_from_schema_and_description_prefix(self) -> None:
        description = "Look up the current weather for a requested location."
        old = report("early", [tool("weather_lookup", description)])
        new = report("middle", [tool("get_weather", description)])

        changes = diff_tool_schemas.comparison(old, new)["servers"][0]

        self.assertEqual(len(changes["renamed_tools"]), 1)
        self.assertEqual(
            changes["renamed_tools"][0]["before"]["name"], "weather_lookup"
        )
        self.assertEqual(
            changes["renamed_tools"][0]["after"]["name"], "get_weather"
        )


if __name__ == "__main__":
    unittest.main()
