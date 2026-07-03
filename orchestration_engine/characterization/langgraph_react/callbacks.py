"""LangChain callbacks for wall-clock OpenAI / remote LLM spans."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks.base import BaseCallbackHandler

from orchestration_engine.characterization.profiler import Profiler
from orchestration_engine.characterization.taxonomy import Bucket

from .rate_limit import openai_rpm_limiter


class OpenAILLMCallback(BaseCallbackHandler):
    """Record remote LLM latency as external wait (not on-GPU inference)."""

    def __init__(self, prof: Profiler):
        self.prof = prof
        self._start: dict[UUID, float] = {}

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        t_queue = time.perf_counter()
        openai_rpm_limiter().acquire()
        queue_us = int((time.perf_counter() - t_queue) * 1_000_000)
        if queue_us > 0:
            self.prof.record(
                "openai_rpm_queue",
                Bucket.CPU_IO_WAIT,
                queue_us,
                backend="openai",
            )
        self._start[run_id] = time.perf_counter()
        self.prof.record("openai_tokenize_prompt", Bucket.CPU_TOKENIZE, 400)

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        t0 = self._start.pop(run_id, None)
        if t0 is None:
            return
        dur_us = int((time.perf_counter() - t0) * 1_000_000)
        model = "openai"
        if hasattr(response, "llm_output") and response.llm_output:
            model = str(response.llm_output.get("model_name", "openai"))
        self.prof.record(
            "openai_llm_call",
            Bucket.CPU_IO_WAIT,
            dur_us,
            backend="openai",
            model=model,
        )
