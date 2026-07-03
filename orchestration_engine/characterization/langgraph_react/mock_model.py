"""Mock chat model that drives a ReAct tool loop (offline, no API key)."""

from __future__ import annotations

import time
import uuid
from typing import Any, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from .context import get_profiler
from .timing import AgentTiming
from orchestration_engine.characterization.taxonomy import Bucket


class MockReActChatModel(BaseChatModel):
    """Returns sequential tool calls, then a final answer. Simulates GPU prefill/decode."""

    timing: AgentTiming
    tools: list[BaseTool]
    _step: int = 0

    @property
    def _llm_type(self) -> str:
        return "mock_react_chat"

    def _simulate_gpu(self) -> None:
        prof = get_profiler()
        if prof is not None and prof.wall_clock:
            with prof.span("llm_gpu_prefill", Bucket.GPU_INFERENCE):
                time.sleep(self.timing.gpu_prefill_us / 1_000_000)
            prof.record("llm_tokenize_prompt", Bucket.CPU_TOKENIZE, self.timing.tokenize_us)
            with prof.span("llm_gpu_decode", Bucket.GPU_INFERENCE):
                time.sleep(self.timing.gpu_decode_us / 1_000_000)
            return
        if prof is not None:
            prof.record("llm_gpu_prefill", Bucket.GPU_INFERENCE, self.timing.gpu_prefill_us)
            prof.record("llm_tokenize_prompt", Bucket.CPU_TOKENIZE, self.timing.tokenize_us)
            prof.record("llm_gpu_decode", Bucket.GPU_INFERENCE, self.timing.gpu_decode_us)
            return
        time.sleep(
            (self.timing.gpu_prefill_us + self.timing.gpu_decode_us + self.timing.tokenize_us)
            / 1_000_000
        )

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._simulate_gpu()
        tool_idx = self._step
        self._step += 1

        if tool_idx < self.timing.react_steps:
            tool = self.tools[tool_idx % len(self.tools)]
            call_id = str(uuid.uuid4())[:8]
            msg = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": tool.name,
                        "args": {"query": f"step_{tool_idx}"},
                        "id": f"call_{call_id}",
                        "type": "tool_call",
                    }
                ],
            )
        else:
            msg = AIMessage(content="Task complete.")

        return ChatResult(generations=[ChatGeneration(message=msg)])

    @property
    def _identifying_params(self) -> dict[str, Any]:
        return {"model": "mock_react", "steps": self.timing.react_steps}

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | callable | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[Any, AIMessage]:
        bound_tools = [t for t in tools if isinstance(t, BaseTool)]
        return self.model_copy(update={"tools": bound_tools or list(self.tools)})
