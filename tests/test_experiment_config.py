import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import experiment_config  # noqa: E402
import run_benchmark  # noqa: E402


class ExperimentConfigTest(unittest.TestCase):
    def make_project(self, root: Path) -> Path:
        (root / "benchmark/src").mkdir(parents=True)
        (root / "benchmark/src/runner.py").write_text("# test\n", encoding="utf-8")
        (root / "data").mkdir()
        task_file = root / "data/tasks.json"
        task_file.write_text('[{"idx": 1}]\n', encoding="utf-8")
        (root / "generated").mkdir()
        versions = {}
        for index, version in enumerate(experiment_config.VERSIONS, start=1):
            server_config = root / "generated" / f"{version}.json"
            server_config.write_text(
                '{"mcpServers": {"example": {}}}\n', encoding="utf-8"
            )
            versions[version] = {
                "url": f"http://127.0.0.1:{3050 + index}/mcp",
                "server_config": f"generated/{version}.json",
            }
        task_hash = hashlib.sha256(task_file.read_bytes()).hexdigest()
        config = {
            "schema_version": 1,
            "experiment_name": "test",
            "benchmark": {
                "root": "benchmark",
                "runner": "src/runner.py",
                "commit": "abc",
            },
            "dataset": {"path": "data/tasks.json", "sha256": task_hash, "size": 1},
            "model": {
                "name": "model",
                "temperature": 0,
                "max_completion_tokens": 100,
                "api_key_env": "MODEL_API_KEY",
                "base_url_env": "MODEL_BASE_URL",
            },
            "judge": {
                "name": "model",
                "temperature": 0,
                "api_key_env": "JUDGE_API_KEY",
                "base_url_env": "JUDGE_BASE_URL",
            },
            "runner": {"step": 3, "part_num": -1, "part_idx": 0, "fschat": False},
            "mcp": {"versions": versions},
            "output": {"root": "results", "layout": "{experiment_name}/{version}"},
            "environment": {"file": ".env"},
        }
        path = root / "experiment.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def test_resolves_one_shared_config_into_version_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.make_project(root)
            resolved = experiment_config.load_experiment(
                config, "middle", root=root, verify_checkout=False
            )
            self.assertEqual(resolved["temperature"], 0.0)
            self.assertEqual(resolved["task_count"], 1)
            self.assertEqual(resolved["mcp_url"], "http://127.0.0.1:3052/mcp")
            arguments = run_benchmark.upstream_arguments(resolved)
            self.assertIn(str(resolved["task_file"]), arguments)
            self.assertIn(str(resolved["output_dir"]), arguments)

    def test_rejects_changed_task_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.make_project(root)
            (root / "data/tasks.json").write_text("[]\n", encoding="utf-8")
            with self.assertRaises(experiment_config.ConfigError):
                experiment_config.load_experiment(
                    config, "early", root=root, verify_checkout=False
                )

    def test_dotenv_is_literal_and_does_not_override_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "MODEL_API_KEY='from-file'\nMODEL_BASE_URL=$(echo unsafe)\n",
                encoding="utf-8",
            )
            environ = {"MODEL_API_KEY": "already-set"}
            loaded = experiment_config.load_env_file(path, environ)
            self.assertEqual(environ["MODEL_API_KEY"], "already-set")
            self.assertEqual(environ["MODEL_BASE_URL"], "$(echo unsafe)")
            self.assertEqual(loaded, ["MODEL_BASE_URL"])

    def test_runtime_initializer_replaces_upstream_placeholders(self) -> None:
        captured = {}

        def upstream_init(instance: object, **kwargs: object) -> None:
            captured.update(kwargs)

        configured = run_benchmark.configured_initializer(
            upstream_init,
            {"temperature": 0.0, "max_completion_tokens": 4096},
            "secret",
            "https://example.invalid/v1",
        )
        configured(
            object(),
            api_key="your api key",
            model_url="your api base url",
            temperature=0.2,
            max_new_tokens=100,
        )
        self.assertEqual(captured["api_key"], "secret")
        self.assertEqual(captured["model_url"], "https://example.invalid/v1")
        self.assertEqual(captured["temperature"], 0.0)
        self.assertEqual(captured["max_new_tokens"], 4096)


if __name__ == "__main__":
    unittest.main()
