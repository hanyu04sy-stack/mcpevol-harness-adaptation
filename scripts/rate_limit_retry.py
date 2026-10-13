"""Auditable, explicit retry handling for OpenAI-compatible HTTP 429 responses."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any


BASE_DELAY_SECONDS = 1.0
MAX_DELAY_SECONDS = 60.0


def new_retry_audit(max_retries: int) -> dict[str, Any]:
    return {
        "policy": "exponential_backoff_with_retry_after",
        "sdk_max_retries": 0,
        "max_retries_per_request": max_retries,
        "base_delay_seconds": BASE_DELAY_SECONDS,
        "max_delay_seconds": MAX_DELAY_SECONDS,
        "rate_limit_responses": 0,
        "actual_retries": 0,
        "exhausted_requests": 0,
        "total_backoff_seconds": 0.0,
        "events": [],
    }


def _status_code(exc: BaseException) -> int | None:
    value = getattr(exc, "status_code", None)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _retry_after_seconds(exc: BaseException, now: float | None = None) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    value = headers.get("retry-after") or headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        try:
            target = parsedate_to_datetime(str(value))
            if target.tzinfo is None:
                target = target.replace(tzinfo=timezone.utc)
            current = time.time() if now is None else now
            return max(0.0, target.timestamp() - current)
        except (TypeError, ValueError, OverflowError):
            return None


def call_with_rate_limit_retry(
    request: Callable[[], Any],
    *,
    max_retries: int,
    audit: dict[str, Any],
    lock: Any = None,
    sleep: Callable[[float], None] = time.sleep,
    on_record: Callable[[dict[str, Any]], None] | None = None,
) -> Any:
    """Call request, explicitly retrying only HTTP 429 and recording every wait."""

    def record(event: dict[str, Any], *, retried: bool, exhausted: bool) -> None:
        if lock is not None:
            lock.acquire()
        try:
            audit["rate_limit_responses"] += 1
            if retried:
                audit["actual_retries"] += 1
                audit["total_backoff_seconds"] = round(
                    float(audit["total_backoff_seconds"])
                    + float(event["applied_delay_seconds"]),
                    3,
                )
            if exhausted:
                audit["exhausted_requests"] += 1
            audit["events"].append(event)
        finally:
            if lock is not None:
                lock.release()
        if on_record is not None:
            on_record(audit)

    retry_number = 0
    while True:
        try:
            return request()
        except Exception as exc:
            if _status_code(exc) != 429:
                raise
            retry_after = _retry_after_seconds(exc)
            exponential = min(
                MAX_DELAY_SECONDS, BASE_DELAY_SECONDS * (2**retry_number)
            )
            exhausted = retry_number >= max_retries
            delay = (
                0.0
                if exhausted
                else min(MAX_DELAY_SECONDS, max(exponential, retry_after or 0.0))
            )
            event = {
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "retry_number": retry_number + 1,
                "retry_after_seconds": retry_after,
                "exponential_delay_seconds": exponential,
                "applied_delay_seconds": round(delay, 3),
                "will_retry": not exhausted,
            }
            record(event, retried=not exhausted, exhausted=exhausted)
            if exhausted:
                raise
            sleep(delay)
            retry_number += 1
