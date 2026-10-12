import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import run_judge  # noqa: E402


class RunJudgeTest(unittest.TestCase):
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
                return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        client = SimpleNamespace(
            chat=SimpleNamespace(completions=Completions())
        )
        result = run_judge.judge_case(
            {"question": "q", "answer": "a", "trajectory_messages": []},
            client=client,
            prompt_builder=lambda *args, **kwargs: "Return JSON.",
            model="deepseek-chat",
            temperature=0.0,
            max_tokens=4096,
            num_runs=1,
            seed=6203,
        )
        self.assertEqual(result["aggregate"]["successful_runs"], 1)
        self.assertEqual(calls[0]["max_tokens"], 4096)
        self.assertNotIn("response_format", calls[0])


if __name__ == "__main__":
    unittest.main()
