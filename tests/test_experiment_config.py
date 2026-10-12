import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import experiment_config  # noqa: E402
import run_benchmark  # noqa: E402


class ExperimentConfigTest(unittest.TestCase):
    def test_repository_external_configs_pin_deepseek_chat(self) -> None:
        root = SCRIPTS.parent
        for relative in ("configs/experiment.json", "configs/canary-real.json"):
            config = json.loads((root / relative).read_text(encoding="utf-8"))
            self.assertEqual(config["model"]["provider"], "openai_compatible")
            self.assertEqual(config["model"]["name"], "deepseek-chat")
            self.assertEqual(config["judge"]["name"], "deepseek-chat")
        env_example = (root / ".env.example").read_text(encoding="utf-8")
        self.assertIn("MODEL_BASE_URL=https://api.deepseek.com", env_example)
        self.assertIn("JUDGE_BASE_URL=", env_example)

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
        harness = root / "harness/original"
        harness.mkdir(parents=True)
        (harness / "system_prompt.md").write_text(
            "System {SET_TIME}\nFiles: {FILE_EXISTS}\n", encoding="utf-8"
        )
        (harness / "tool_usage_rules.md").write_text(
            "Use the available tools.\n", encoding="utf-8"
        )
        (harness / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "benchmark_commit": "abc",
                    "source_files": [{"path": "src/agent.py"}],
                }
            ),
            encoding="utf-8",
        )
        config = {
            "schema_version": 1,
            "experiment_name": "test",
            "benchmark": {
                "root": "benchmark",
                "runner": "src/runner.py",
                "commit": "abc",
            },
            "dataset": {"path": "data/tasks.json", "sha256": task_hash, "size": 1},
            "harness": {"default_dir": "harness/original"},
            "model": {
                "provider": "openai_compatible",
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
            "openai_client": {"timeout_seconds": 120, "max_retries": 3},
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
            self.assertEqual(
                resolved["harness_dir"], (root / "harness/original").resolve()
            )
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

    def test_rejects_matrix_with_unavailable_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = self.make_project(root)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            task_hash = config["dataset"]["sha256"]
            matrix = {
                "benchmark_commit": "abc",
                "task_file_sha256": task_hash,
                "all_tasks_runnable_in_all_versions": False,
                "tasks": [
                    {
                        "idx": 1,
                        "versions": {
                            version: {
                                "runnable": False,
                                "unavailable_servers": ["example"],
                            }
                            for version in experiment_config.VERSIONS
                        },
                    }
                ],
            }
            matrix_path = root / "matrix.json"
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            config["dataset"]["runnability_matrix"] = "matrix.json"
            config["dataset"]["runnability_matrix_sha256"] = hashlib.sha256(
                matrix_path.read_bytes()
            ).hexdigest()
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(
                experiment_config.ConfigError, "unavailable task dependencies"
            ):
                experiment_config.load_experiment(
                    config_path, "early", root=root, verify_checkout=False
                )

    def test_rejects_unstable_repeated_startup_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = self.make_project(root)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            stability = {
                "benchmark_commit": "abc",
                "trial_count": 3,
                "all_versions_stable": False,
                "versions": {},
            }
            report_path = root / "stability.json"
            report_path.write_text(json.dumps(stability), encoding="utf-8")
            config["dataset"]["startup_stability_report"] = "stability.json"
            config["dataset"]["startup_stability_report_sha256"] = hashlib.sha256(
                report_path.read_bytes()
            ).hexdigest()
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(
                experiment_config.ConfigError, "intermittent failures"
            ):
                experiment_config.load_experiment(
                    config_path, "early", root=root, verify_checkout=False
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
            instance.client = SimpleNamespace(
                timeout=None,
                max_retries=None,
                chat=SimpleNamespace(
                    completions=SimpleNamespace(create=lambda **request: request)
                ),
            )
            instance.model_name = "model"

        configured = run_benchmark.configured_initializer(
            upstream_init,
            {
                "temperature": 0.0,
                "max_completion_tokens": 4096,
                "openai_timeout_seconds": 120.0,
                "openai_max_retries": 3,
            },
            "secret",
            "https://example.invalid/v1",
        )
        configured(
            SimpleNamespace(),
            api_key="your api key",
            model_url="your api base url",
            temperature=0.2,
            max_new_tokens=100,
        )
        self.assertEqual(captured["api_key"], "secret")
        self.assertEqual(captured["model_url"], "https://example.invalid/v1")
        self.assertEqual(captured["temperature"], 0.0)
        self.assertEqual(captured["max_new_tokens"], 4096)

    def test_initializer_applies_timeout_retry_and_max_tokens(self) -> None:
        class Completions:
            def create(self, **kwargs: object) -> object:
                return kwargs

        class Client:
            class Chat:
                completions = Completions()

            chat = Chat()
            timeout = None
            max_retries = None

        class Instance:
            pass

        def upstream_init(instance: object, **kwargs: object) -> None:
            instance.client = Client()
            instance.model_name = "deepseek-chat"

        configured = run_benchmark.configured_initializer(
            upstream_init,
            {
                "temperature": 0.0,
                "max_completion_tokens": 4096,
                "openai_timeout_seconds": 120.0,
                "openai_max_retries": 3,
            },
            "secret",
            "https://api.deepseek.com",
        )
        instance = Instance()
        configured(instance)
        self.assertEqual(instance.chat.keywords["max_tokens"], 4096)
        self.assertNotIn("max_completion_tokens", instance.chat.keywords)
        self.assertEqual(instance.client.timeout, 120.0)
        self.assertEqual(instance.client.max_retries, 3)

    def test_judge_credentials_fall_back_to_same_model_credentials(self) -> None:
        resolved = {
            "model_name": "deepseek-chat",
            "judge_name": "deepseek-chat",
            "model_api_key_env": "MODEL_API_KEY",
            "model_base_url_env": "MODEL_BASE_URL",
            "judge_api_key_env": "JUDGE_API_KEY",
            "judge_base_url_env": "JUDGE_BASE_URL",
        }
        experiment_config.resolve_runtime_credentials(
            resolved,
            {
                "MODEL_API_KEY": "model-secret",
                "MODEL_BASE_URL": "https://provider.invalid",
                "JUDGE_API_KEY": "",
                "JUDGE_BASE_URL": "",
            },
        )
        self.assertEqual(resolved["judge_api_key_resolved"], "model-secret")
        self.assertEqual(
            resolved["judge_base_url_resolved"], "https://provider.invalid"
        )

    def test_harness_loader_audits_files_and_deduplicates_original_rule(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            harness = root / "harness"
            harness.mkdir()
            rule = "Call tools directly."
            prompt = f"Base prompt.\n{rule}\nTime: {{SET_TIME}}\nFiles: {{FILE_EXISTS}}\n"
            (harness / "system_prompt.md").write_text(prompt, encoding="utf-8")
            (harness / "tool_usage_rules.md").write_text(
                f"# Rules\n\n## Injected rules\n\n{rule}\n\n## Routing reference\n\nAudit only.\n",
                encoding="utf-8",
            )
            (harness / "manifest.json").write_text(
                json.dumps(
                    {
                        "benchmark_commit": "abc",
                        "source_files": [{"path": "src/agent.py"}],
                    }
                ),
                encoding="utf-8",
            )
            loaded = run_benchmark.load_harness(harness, "abc")
            self.assertEqual(loaded["harness_prompt"], prompt)
            self.assertEqual(len(loaded["harness_files"]), 3)
            self.assertEqual(len(loaded["harness_manifest_sha256"]), 64)

    def test_harness_loader_rejects_wrong_benchmark_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.make_project(root)
            resolved = experiment_config.load_experiment(
                config, "early", root=root, verify_checkout=False
            )
            with self.assertRaisesRegex(
                experiment_config.ConfigError, "benchmark commit"
            ):
                run_benchmark.load_harness(resolved["harness_dir"], "different")

    def test_live_mcp_check_rejects_unavailable_dependency(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def read(self):
                return json.dumps(
                    {
                        "servers": [
                            {
                                "server": "example",
                                "status": "failed",
                                "available": False,
                                "toolCount": 0,
                            }
                        ]
                    }
                ).encode()

        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "servers.json"
            config.write_text('{"mcpServers":{"example":{}}}', encoding="utf-8")
            resolved = {
                "mcp_url": "http://127.0.0.1:3051/mcp",
                "server_config": config,
            }
            with patch("run_benchmark.urllib.request.urlopen", return_value=Response()):
                with self.assertRaisesRegex(
                    experiment_config.ConfigError, "example\\(failed\\)"
                ):
                    run_benchmark.check_mcp(resolved)


if __name__ == "__main__":
    unittest.main()
