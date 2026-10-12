import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from experiment_config import (  # noqa: E402
    ConfigError,
    parse_env_file,
    validate_endpoint_model_consistency,
)


class EndpointConsistencyTest(unittest.TestCase):
    def test_deepseek_endpoint_rejects_openai_model_slug(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "MODEL_BASE_URL=https://api.deepseek.com\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(
                ConfigError,
                "MODEL_BASE_URL points to DeepSeek.*model.name is still 'gpt-4o'",
            ):
                validate_endpoint_model_consistency(
                    "gpt-4o", parse_env_file(env_file)["MODEL_BASE_URL"]
                )

    def test_openai_or_openrouter_endpoint_rejects_deepseek_slug(self) -> None:
        for endpoint in (
            "https://api.openai.com/v1",
            "https://openrouter.ai/api/v1",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaisesRegex(
                ConfigError, "but model.name is 'deepseek-chat'"
            ):
                validate_endpoint_model_consistency("deepseek-chat", endpoint)

    def test_matching_deepseek_endpoint_and_model_pass(self) -> None:
        validate_endpoint_model_consistency(
            "deepseek-chat", "https://api.deepseek.com/v1"
        )


if __name__ == "__main__":
    unittest.main()
