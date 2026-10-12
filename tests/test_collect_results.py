import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import collect_results  # noqa: E402


class CollectResultsTest(unittest.TestCase):
    def make_run(self, root: Path, strategy: str, tf: float, pe: float) -> None:
        run = root / strategy / "late" / "run-01"
        run.mkdir(parents=True)
        (run / "run-metadata.json").write_text(
            json.dumps(
                {
                    "strategy": strategy,
                    "version": "late",
                    "run_id": 1,
                    "model": {"name": "deepseek-chat"},
                    "judge": {"name": "deepseek-chat"},
                    "mcp_status_at_start": {"connected_servers": 26},
                    "total_prompt_tokens": 100,
                    "total_completion_tokens": 20,
                    "wall_clock_seconds": 2.5,
                }
            ),
            encoding="utf-8",
        )
        (run / "judge-results.json").write_text(
            json.dumps(
                {
                    "tasks": [
                        {
                            "task_idx": 161,
                            "tf": tf,
                            "pe": pe,
                            "failure_category": "" if tf >= 6 else "under_update",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

    def test_collects_csv_rows_and_group_means(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_run(root, "original", 8, 6)
            self.make_run(root, "full_rewrite", 4, 5)
            details, aggregates = collect_results.collect(root, 6)
            csv_path = root / "summary.csv"
            json_path = root / "summary.json"
            collect_results.write_outputs(
                details,
                aggregates,
                output_csv=csv_path,
                output_json=json_path,
                success_threshold=6,
            )
            with csv_path.open(encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 2)
            self.assertEqual(tuple(rows[0]), collect_results.CSV_FIELDS)
            original = next(item for item in aggregates if item["strategy"] == "original")
            self.assertEqual(original["mean_tf"], 8.0)
            self.assertEqual(original["total_cost_tokens"], 120)
            self.assertAlmostEqual(original["est_cost_usd"], 0.000049)


if __name__ == "__main__":
    unittest.main()
