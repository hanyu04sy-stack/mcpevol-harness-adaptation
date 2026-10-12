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


def tool_response(arguments='{"city": "Beijing"}'):
    call = SimpleNamespace(
        function=SimpleNamespace(name="get_weather", arguments=arguments)
    )
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=None, tool_calls=[call])
            )
        ]
    )


def client_factory(chat_outcome=None, tool_outcome=None):
    def factory(**kwargs):
        class Completions:
            def create(self, **request):
                outcome = tool_outcome if "tools" in request else chat_outcome
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
            "dataset": {"size": 30},
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
                client_factory(chat_response(), tool_response()),
            )
        self.assertEqual(code, 0)
        self.assertIn("[PASS] 1. Chat completion", output)
        self.assertIn("[PASS] 4. Tool calling", output)
        self.assertIn("All checks passed", output)
        self.assertNotIn("secret", output)

    def test_chat_401_exits_one_with_fix(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output = self.run_case(
                Path(directory),
                client_factory(StatusError("Invalid API key", 401), tool_response()),
            )
        self.assertEqual(code, 1)
        self.assertIn("[FAIL] 1. Chat completion", output)
        self.assertIn("Fix: open .env", output)

    def test_malformed_tool_arguments_exits_one_with_compatibility_advice(self):
        with tempfile.TemporaryDirectory() as directory:
            code, output = self.run_case(
                Path(directory),
                client_factory(chat_response(), tool_response("{city: Beijing}")),
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


if __name__ == "__main__":
    unittest.main()
