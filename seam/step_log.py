"""Per-step pre-generate log line (Task AZ, pilot P11-HANG-REGIME; default off).

One JSON line is written, flushed and fsynced BEFORE each local generate, so a
process that stalls inside the native generate (the entry-123 silent device
stall) still leaves the step index and the size of the prompt it was given.
The same line goes to stderr (the worker log).

``new_tokens_est`` is an estimate: prompt tokens minus (previous step's prompt
tokens + its generated tokens) in the same session, floored at 0; the first
step of a session counts its whole prompt. It assumes the prefix cache still
holds everything the session has seen; it is not read from the runtime.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO

STEP_LOG_NAME = "step_log.jsonl"
STDERR_TAG = "STEP_PRE_GENERATE"


@dataclass
class StepLog:
    path: Path
    entry_id: str
    policy: str
    stderr: TextIO | None = field(default=None, repr=False)
    _seen_tokens: int | None = field(default=None, init=False)

    def before_generate(
        self,
        *,
        turn: int,
        step: int,
        prompt_tokens: int,
        generate_input_tokens: int,
        input_kind: str,
    ) -> dict[str, Any]:
        seen = self._seen_tokens
        new_est = int(prompt_tokens) if seen is None else max(0, int(prompt_tokens) - seen)
        rec: dict[str, Any] = {
            "event": "pre_generate",
            "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "t_perf_s": round(time.perf_counter(), 6),
            "entry_id": self.entry_id,
            "policy": self.policy,
            "turn": int(turn),
            "step": int(step),
            "prompt_tokens": int(prompt_tokens),
            "generate_input_tokens": int(generate_input_tokens),
            "input_kind": input_kind,
            "new_tokens_est": new_est,
            "seen_tokens_before": seen,
        }
        line = json.dumps(rec, sort_keys=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        err = self.stderr if self.stderr is not None else sys.stderr
        err.write(f"{STDERR_TAG} {line}\n")
        err.flush()
        return rec

    def after_generate(self, *, prompt_tokens: int, generated_tokens: int | None) -> None:
        self._seen_tokens = int(prompt_tokens) + int(generated_tokens or 0)
