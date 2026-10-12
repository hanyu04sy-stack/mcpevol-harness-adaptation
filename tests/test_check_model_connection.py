import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import check_model_connection  # noqa: E402


class FakeCompletions:
    def __init__(self, outcome):
        self.outcome = outcome

    def create(self, **kwargs):
        if isinstance(self.outcome, list):
            outcome = self.outcome.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def factory_for(outcome):
    def factory(**kwargs):
        return SimpleNamespace(
            chat=SimpleNamespace(completions=FakeCompletions(outcome))
        )

    return factory


class StatusError(Exception):
    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


class CheckModelConnectionTest(unittest.TestCase):
    def run_case(self, outcome):
        output = io.StringIO()
        with redirect_stdout(output):
            passed = check_model_connection.check_target(
                label="agent",
                model="configured-model",
                api_key="secret",
                base_url="https://example.invalid",
                credential_source="MODEL_API_KEY",
                client_factory=factory_for(outcome),
                connectivity_checker=lambda url: None,
            )
        return passed, output.getvalue()

    def test_success_prints_usage_and_returns_true(self):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=SimpleNamespace(prompt_tokens=8, completion_tokens=1),
        )
        passed, output = self.run_case(response)
        self.assertTrue(passed)
        self.assertIn("HTTP connectivity: ok", output)
        self.assertIn("prompt_tokens: 8", output)

    def test_401_has_actionable_advice(self):
        passed, output = self.run_case(StatusError("bad key", 401))
        self.assertFalse(passed)
        self.assertIn("replace the API key", output)

    def test_model_not_found_has_actionable_advice(self):
        passed, output = self.run_case(Exception("model not found"))
        self.assertFalse(passed)
        self.assertIn("verify model.name", output)

    def test_timeout_has_actionable_advice(self):
        passed, output = self.run_case(TimeoutError("timed out"))
        self.assertFalse(passed)
        self.assertIn("network/proxy", output)

    def test_tool_call_self_test_passes_for_valid_arguments(self):
        tool_call = SimpleNamespace(
            function=SimpleNamespace(
                name="get_weather", arguments='{"city": "Beijing"}'
            )
        )
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=None, tool_calls=[tool_call]
                    )
                )
            ]
        )
        output = io.StringIO()
        with redirect_stdout(output):
            passed = check_model_connection.tool_call_self_test(
                factory_for(response)(), "deepseek-chat"
            )
        self.assertTrue(passed)
        self.assertIn("Tool-calling self-test: PASS", output.getvalue())
        self.assertIn('"city": "Beijing"', output.getvalue())

    def test_tool_call_self_test_reports_malformed_json_as_compatibility_issue(self):
        tool_call = SimpleNamespace(
            function=SimpleNamespace(
                name="get_weather", arguments='{city: "Beijing"}'
            )
        )
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=None, tool_calls=[tool_call]
                    )
                )
            ]
        )
        output = io.StringIO()
        with redirect_stdout(output):
            passed = check_model_connection.tool_call_self_test(
                factory_for(response)(), "deepseek-chat"
            )
        self.assertFalse(passed)
        self.assertIn("malformed tool arguments", output.getvalue())
        self.assertIn("DeepSeek compatibility issue", output.getvalue())

    def test_bare_deepseek_url_probes_plain_then_v1(self):
        self.assertEqual(
            check_model_connection.endpoint_candidates("https://api.deepseek.com"),
            ["https://api.deepseek.com", "https://api.deepseek.com/v1"],
        )
        self.assertEqual(
            check_model_connection.endpoint_candidates(
                "https://api.deepseek.com/v1"
            ),
            ["https://api.deepseek.com/v1"],
        )

    def test_probe_uses_v1_when_plain_endpoint_fails(self):
        attempted = []
        success = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
            usage=SimpleNamespace(prompt_tokens=8, completion_tokens=1),
        )

        def factory(**kwargs):
            attempted.append(kwargs["base_url"])
            outcome = (
                Exception("404 not found")
                if kwargs["base_url"] == "https://api.deepseek.com"
                else success
            )
            return SimpleNamespace(
                chat=SimpleNamespace(completions=FakeCompletions(outcome))
            )

        output = io.StringIO()
        with redirect_stdout(output):
            passed = check_model_connection.check_target(
                label="agent",
                model="deepseek-chat",
                api_key="secret",
                base_url="https://api.deepseek.com",
                credential_source="MODEL_API_KEY",
                client_factory=factory,
                connectivity_checker=lambda url: None,
            )
        self.assertTrue(passed)
        self.assertEqual(
            attempted,
            ["https://api.deepseek.com", "https://api.deepseek.com/v1"],
        )
        self.assertIn(
            "Detected DeepSeek endpoint: https://api.deepseek.com/v1",
            output.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
