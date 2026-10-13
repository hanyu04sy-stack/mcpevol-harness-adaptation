import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import check_model_connection  # noqa: E402


class StatusError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


def chat_response():
    return SimpleNamespace(
        model="deepseek-chat",
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        usage=SimpleNamespace(prompt_tokens=5, completion_tokens=1),
    )


def tool_response(
    name="plan_trip",
    arguments=(
        '{"destinations":[{"city":"Beijing","days":2},'
        '{"city":"Shanghai","days":3}],'
        '"preferences":{"activities":["food","museums"]}}'
    ),
    call_id="call_plan_1",
):
    call = SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=None, tool_calls=[call])
            )
        ]
    )


def valid_tool_responses():
    return [
        tool_response(),
        tool_response(
            name="get_weather",
            arguments='{"city":"Beijing"}',
            call_id="call_weather_2",
        ),
    ]


def client_factory(chat_outcome=None, tool_outcome=None):
    tool_outcomes = iter(
        tool_outcome if isinstance(tool_outcome, list) else [tool_outcome]
    )

    def factory(**kwargs):
        class Completions:
            def create(self, **request):
                outcome = next(tool_outcomes) if "tools" in request else chat_outcome
                if isinstance(outcome, BaseException):
                    raise outcome
                return outcome

        return SimpleNamespace(chat=SimpleNamespace(completions=Completions()))

    return factory


class CheckModelConnectionTest(unittest.TestCase):
    def make_files(self, root: Path) -> tuple[Path, Path]:
        (root / "configs").mkdir()
        config = {
            "model": {
                "name": "deepseek-chat",
                "api_key_env": "MODEL_API_KEY",
                "base_url_env": "MODEL_BASE_URL",
                "max_completion_tokens": 100,
            },
            "judge": {"name": "deepseek-chat"},
            "dataset": {"size": 30, "path": "data/tasks.json"},
        }
        config_path = root / "configs/experiment.json"
        config_path.write_text(json.dumps(config), encoding="utf-8")
        (root / "configs/pricing.json").write_text(
            json.dumps(
                {
                    "models": {
                        "deepseek-chat": {
                            "prompt_per_mtok_usd": 0.27,
                            "completion_per_mtok_usd": 1.10,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        (root / "data").mkdir()
        task = {
            "question": "Use a tool to answer the question.",
            "answer": "Done.",
            "servers": {"example": ["lookup"]},
            "trajectory_messages": [
                {"role": "system", "content": "Use tools."},
                {"role": "user", "content": "Look this up."},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": "lookup"}}],
                },
                {"role": "tool", "content": "result"},
                {"role": "assistant", "content": "Done."},
            ],
        }
        (root / "data/tasks.json").write_text(
            json.dumps([task] * 30), encoding="utf-8"
        )
        env_path = root / ".env"
        env_path.write_text(
            "MODEL_API_KEY=secret\nMODEL_BASE_URL=https://api.deepseek.com\n",
            encoding="utf-8",
        )
        return config_path, env_path

    def run_case(self, root: Path, factory):
        config, env = self.make_files(root)
        output = io.StringIO()
        code = check_model_connection.run_self_check(
            config_path=config,
            env_file=env,
            client_factory=factory,
            environ={},
            stream=output,
        )
        return code, output.getvalue()

    def test_all_four_checks_pass_and_exit_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output = self.run_case(
                Path(directory),
                client_factory(chat_response(), valid_tool_responses()),
            )
        self.assertEqual(code, 0)
        self.assertIn("[PASS] 1. Chat completion", output)
        self.assertIn("[PASS] 4. Tool calling", output)
        self.assertIn("linked_tool_call_id=call_plan_1", output)
        self.assertIn("All checks passed", output)
        self.assertIn("429 retry audit: responses=0", output)
        self.assertNotIn("secret", output)

    def test_agent_and_judge_endpoints_are_checked_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, env = self.make_files(root)
            env.write_text(
                "MODEL_API_KEY=agent-key\n"
                "MODEL_BASE_URL=https://api.deepseek.com\n"
                "JUDGE_API_KEY=judge-key\n"
                "JUDGE_BASE_URL=https://judge.deepseek.com\n",
                encoding="utf-8",
            )
            tool_outcomes = iter(valid_tool_responses())

            def factory(**kwargs):
                class Completions:
                    def create(self, **request):
                        if kwargs["base_url"] == "https://judge.deepseek.com":
                            raise StatusError("Invalid judge key", 401)
                        return (
                            next(tool_outcomes)
                            if "tools" in request
                            else chat_response()
                        )

                return SimpleNamespace(
                    chat=SimpleNamespace(completions=Completions())
                )

            output = io.StringIO()
            code = check_model_connection.run_self_check(
                config_path=config,
                env_file=env,
                client_factory=factory,
                environ={},
                stream=output,
            )
        self.assertEqual(code, 1)
        self.assertIn("[FAIL] 3. Endpoint detection", output.getvalue())
        self.assertIn("Judge failed", output.getvalue())

    def test_self_check_disables_sdk_retries(self):
        seen = []
        delegate = client_factory(chat_response(), valid_tool_responses())

        def factory(**kwargs):
            seen.append(kwargs["max_retries"])
            return delegate(**kwargs)

        with tempfile.TemporaryDirectory() as directory:
            code, _ = self.run_case(Path(directory), factory)
        self.assertEqual(code, 0)
        self.assertTrue(seen)
        self.assertEqual(set(seen), {0})

    def test_chat_401_exits_one_with_fix(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output = self.run_case(
                Path(directory),
                client_factory(StatusError("Invalid API key", 401), valid_tool_responses()),
            )
        self.assertEqual(code, 1)
        self.assertIn("[FAIL] 1. Chat completion", output)
        self.assertIn("Fix: open .env", output)

    def test_malformed_tool_arguments_exits_one_with_compatibility_advice(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output = self.run_case(
                Path(directory),
                client_factory(
                    chat_response(),
                    tool_response(arguments="{city: Beijing}"),
                ),
            )
        self.assertEqual(code, 1)
        self.assertIn("[FAIL] 4. Tool calling", output)
        self.assertIn("DeepSeek tool calling compatibility", output)

    def test_missing_env_exits_two(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = io.StringIO()
            code = check_model_connection.run_self_check(
                config_path=root / "configs/experiment.json",
                env_file=root / ".env",
                client_factory=client_factory(None, None),
                environ={},
                stream=output,
            )
        self.assertEqual(code, 2)
        self.assertIn("cp .env.example .env first", output.getvalue())

    def test_cost_estimate_includes_five_judges_and_retry_reserve(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path, _ = self.make_files(root)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            estimate = check_model_connection.estimate_cost(config, root)
        self.assertIsNotNone(estimate)
        self.assertEqual(estimate["judge_runs_per_task"], 5)
        self.assertEqual(estimate["retry_attempt_reserve"], 300)
        self.assertGreater(estimate["agent_prompt_tokens"], 0)
        self.assertGreater(estimate["judge_prompt_tokens"], 0)
        self.assertGreater(
            estimate["total"], estimate["agent_cost"] + estimate["judge_cost"]
        )

    def test_cost_estimate_prefers_real_usage_calibration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path, _ = self.make_files(root)
            run = root / "results/canary/early/run-01"
            run.mkdir(parents=True)
            (run / "run-metadata.json").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "model": {"name": "deepseek-chat"},
                        "total_prompt_tokens": 100,
                        "total_completion_tokens": 20,
                    }
                ),
                encoding="utf-8",
            )
            (run / "judge-results.json").write_text(
                json.dumps({"tasks": [{"task_idx": 1}, {"task_idx": 2}]}),
                encoding="utf-8",
            )
            (run / "judge-metadata.json").write_text(
                json.dumps(
                    {
                        "valid_score_count": 10,
                        "usage": {
                            "judge_prompt_tokens": 500,
                            "judge_completion_tokens": 100,
                        },
                    }
                ),
                encoding="utf-8",
            )
            config = json.loads(config_path.read_text(encoding="utf-8"))
            estimate = check_model_connection.estimate_cost(config, root)
        self.assertEqual(estimate["estimation_method"], "calibrated_from_real_usage")
        self.assertEqual(estimate["agent_prompt_tokens"], 1500)
        self.assertEqual(estimate["judge_prompt_tokens"], 7500)
        self.assertIn("run-metadata.json", estimate["calibration_source"])

    def test_keyboard_interrupt_is_not_swallowed(self):
        def interrupted_factory(**kwargs):
            raise KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            check_model_connection.probe(
                "deepseek-chat",
                "secret",
                "https://api.deepseek.com",
                interrupted_factory,
            )


if __name__ == "__main__":
    unittest.main()
