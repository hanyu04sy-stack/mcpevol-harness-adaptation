import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import rate_limit_retry  # noqa: E402


class HttpError(Exception):
    def __init__(self, status_code, headers=None):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code
        self.response = SimpleNamespace(
            status_code=status_code, headers=headers or {}
        )


class RateLimitRetryTest(unittest.TestCase):
    def test_retries_429_with_retry_after_and_exponential_backoff(self) -> None:
        outcomes = iter(
            [HttpError(429, {"Retry-After": "3"}), HttpError(429), "ok"]
        )
        sleeps = []
        audit = rate_limit_retry.new_retry_audit(3)

        def request():
            outcome = next(outcomes)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        result = rate_limit_retry.call_with_rate_limit_retry(
            request,
            max_retries=3,
            audit=audit,
            sleep=sleeps.append,
        )
        self.assertEqual(result, "ok")
        self.assertEqual(sleeps, [3.0, 2.0])
        self.assertEqual(audit["rate_limit_responses"], 2)
        self.assertEqual(audit["actual_retries"], 2)
        self.assertEqual(audit["total_backoff_seconds"], 5.0)
        self.assertEqual(audit["events"][0]["retry_after_seconds"], 3.0)

    def test_records_exhaustion_and_reraises_last_429(self) -> None:
        audit = rate_limit_retry.new_retry_audit(1)
        with self.assertRaises(HttpError):
            rate_limit_retry.call_with_rate_limit_retry(
                lambda: (_ for _ in ()).throw(HttpError(429)),
                max_retries=1,
                audit=audit,
                sleep=lambda _: None,
            )
        self.assertEqual(audit["actual_retries"], 1)
        self.assertEqual(audit["rate_limit_responses"], 2)
        self.assertEqual(audit["exhausted_requests"], 1)
        self.assertFalse(audit["events"][-1]["will_retry"])

    def test_does_not_retry_non_429_errors(self) -> None:
        audit = rate_limit_retry.new_retry_audit(3)
        with self.assertRaises(HttpError):
            rate_limit_retry.call_with_rate_limit_retry(
                lambda: (_ for _ in ()).throw(HttpError(500)),
                max_retries=3,
                audit=audit,
                sleep=lambda _: None,
            )
        self.assertEqual(audit["rate_limit_responses"], 0)


if __name__ == "__main__":
    unittest.main()
