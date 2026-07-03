"""Process-wide OpenAI request pacing (RPM)."""

from __future__ import annotations

import os
import threading
import time


class RPMLimiter:
    """Space out API request starts so org RPM is not exceeded."""

    def __init__(self, rpm: int, *, headroom: float = 0.8):
        effective_rpm = max(1, int(rpm * headroom))
        self._interval = 60.0 / effective_rpm
        self._lock = threading.Lock()
        self._next_slot = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now < self._next_slot:
                time.sleep(self._next_slot - now)
            self._next_slot = max(time.monotonic(), self._next_slot) + self._interval


_limiter: RPMLimiter | None = None
_limiter_lock = threading.Lock()


def openai_rpm_limiter() -> RPMLimiter:
    global _limiter
    if _limiter is None:
        with _limiter_lock:
            if _limiter is None:
                rpm = int(os.getenv("OE_OPENAI_RPM_LIMIT", "500"))
                headroom = float(os.getenv("OE_OPENAI_RPM_HEADROOM", "0.8"))
                _limiter = RPMLimiter(rpm, headroom=headroom)
    return _limiter


def is_rate_limit_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "429" in text or "rate_limit" in text or "rate limit" in text
