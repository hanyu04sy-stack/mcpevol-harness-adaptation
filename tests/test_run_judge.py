import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import run_judge  # noqa: E402


class RunJudgeTest(unittest.TestCase):
    def test_model_usage_audit_includes_attempts_and_all_tokens(self) -> None:
        audit = run_judge.judge_audit_summary(
            "deepseek-flash",
            ["DeepSeek-V4.1-Flash"],
            {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "retry_prompt_tokens": 30,
                "retry_completion_tokens": 5,
            },
            attempt_count=6,
            valid_score_count=5,
        )
        self.assertEqual(
            audit,
            {
                "configured_model": "deepseek-flash",
                "provider_reported_model": "DeepSeek-V4.1-Flash",
                "prompt_tokens": 130,
                "completion_tokens": 25,
                "attempt_count": 6,
                "valid_score_count": 5,
            },
        )

    def test_judge_uses_configured_model_and_token_limit(self) -> None:
        calls = []

        class Completions:
            def create(self, **kwargs):
                calls.append(kwargs)
                message = SimpleNamespace(
                    content=(
                        '{"task_fulfillment": 8, "grounding": 9, '
                        '"planning_and_efficiency": 7}'
                    )
                )
                return SimpleNamespace(
                    model="DeepSeek-V4.1-Flash",
                    choices=[SimpleNamespace(message=message)],
                    usage=SimpleNamespace(prompt_tokens=20, completion_tokens=8),
                )

        client = SimpleNamespace(
            chat=SimpleNamespace(completions=Completions())
        )
        result = run_judge.judge_case(
            {"question": "q", "answer": "a", "trajectory_messages": []},
            client=client,
            prompt_builder=lambda *args, **kwargs: "Return JSON.",
            model="deepseek-flash",
            temperature=0.0,
            max_tokens=4096,
            num_runs=1,
            seed=6203,
        )
        self.assertEqual(result["aggregate"]["successful_runs"], 1)
        self.assertEqual(calls[0]["max_tokens"], 4096)
        self.assertNotIn("response_format", calls[0])
        self.assertEqual(result["usage"]["prompt_tokens"], 20)
        self.assertEqual(result["usage"]["completion_tokens"], 8)
        self.assertEqual(result["usage"]["retry_prompt_tokens"], 0)
        self.assertEqual(
            result["provider_reported_models"], ["DeepSeek-V4.1-Flash"]
        )

    def test_invalid_judge_response_usage_is_counted_as_retry(self) -> None:
        contents = iter(
            [
                "not json",
                '{"task_fulfillment": 8, "grounding": 9, '
                '"planning_and_efficiency": 7}',
            ]
        )

        class Completions:
            def create(self, **kwargs):
                return SimpleNamespace(
                    model="DeepSeek-V4.1-Flash",
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content=next(contents))
                        )
                    ],
                    usage=SimpleNamespace(prompt_tokens=10, completion_tokens=3),
                )

        result = run_judge.judge_case(
            {"question": "q", "answer": "a", "trajectory_messages": []},
            client=SimpleNamespace(
                chat=SimpleNamespace(completions=Completions())
            ),
            prompt_builder=lambda *args, **kwargs: "Return JSON.",
            model="deepseek-flash",
            temperature=0.0,
            max_tokens=4096,
            num_runs=1,
            seed=6203,
        )
        self.assertEqual(result["usage"]["prompt_tokens"], 10)
        self.assertEqual(result["usage"]["completion_tokens"], 3)
        self.assertEqual(result["usage"]["retry_prompt_tokens"], 10)
        self.assertEqual(result["usage"]["retry_completion_tokens"], 3)
        self.assertTrue(result["runs"][0]["counted_as_retry"])


if __name__ == "__main__":
    unittest.main()
