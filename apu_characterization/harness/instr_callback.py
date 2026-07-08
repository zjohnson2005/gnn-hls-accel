"""LangChain callbacks: tag OpenAI / LLM work with apu category timers."""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler

from ..instr import get_run_accumulator, timed
from ..taxonomy import Category


class InstrLLMCallback(BaseCallbackHandler):
    """Wrap each LLM call with TOKENIZATION, SERIALIZATION, HTTP_CLIENT timers.

    Uses thread_time_ns so blocking network wait costs ~zero CPU on the
    calling thread (same exclusion property as the mock asyncio sleep).
    """

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self._cpu0: dict[UUID, int] = {}
        self._wall0: dict[UUID, int] = {}

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        prompt_text = "\n".join(prompts)
        with timed(Category.PROMPT_ASSEMBLY, self.session_id, bytes_out=len(prompt_text)):
            pass
        with timed(Category.TOKENIZATION, self.session_id, bytes_in=len(prompt_text)):
            from ..harness.mock_llm import _count_tokens

            _count_tokens(prompt_text)
        with timed(Category.SERIALIZATION, self.session_id, bytes_out=len(prompt_text)):
            json.dumps({"prompts": prompts[:1]})
        self._cpu0[run_id] = time.thread_time_ns()
        self._wall0[run_id] = time.perf_counter_ns()

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        cpu0 = self._cpu0.pop(run_id, None)
        wall0 = self._wall0.pop(run_id, None)
        if cpu0 is None or wall0 is None:
            return

        cpu_ns = time.thread_time_ns() - cpu0
        wall_ns = time.perf_counter_ns() - wall0

        text = ""
        if hasattr(response, "generations") and response.generations:
            gen0 = response.generations[0]
            if gen0 and hasattr(gen0[0], "text"):
                text = gen0[0].text or ""
            elif gen0 and hasattr(gen0[0], "message"):
                text = str(getattr(gen0[0].message, "content", ""))

        acc = get_run_accumulator()
        use_v2 = acc is not None and acc.instr_version >= 2
        if not use_v2 and acc is not None:
            totals = acc.totals_for(Category.HTTP_CLIENT, self.session_id)
            with acc._lock:
                totals.add(cpu_ns, wall_ns, bytes_in=len(text), count=1)

        with timed(
            Category.CLIENT_PARSE if use_v2 else Category.SERIALIZATION,
            self.session_id,
            bytes_in=len(text),
        ):
            json.dumps({"response_len": len(text)})
        with timed(Category.TOKENIZATION, self.session_id, bytes_in=len(text)):
            from ..harness.mock_llm import _count_tokens

            _count_tokens(text)

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._cpu0.pop(run_id, None)
        self._wall0.pop(run_id, None)
