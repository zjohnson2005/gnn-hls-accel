"""Instrumented tools for LangGraph ReAct agent."""

from __future__ import annotations

import json
import random
import time
from typing import Callable

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from .context import get_profiler
from .timing import AgentTiming
from orchestration_engine.characterization.taxonomy import Bucket


class QueryInput(BaseModel):
    query: str = Field(description="Search or action query")


def _emit_delay(prof, name: str, bucket: Bucket, duration_us: int, **meta: str) -> None:
    if prof is not None:
        prof.record(name, bucket, duration_us, **meta)
        return
    time.sleep(max(0, duration_us) / 1_000_000)


def _tool_io_delay(timing: AgentTiming, rng: random.Random, prof) -> None:
    delay = timing.tool_io_mean_us + rng.randint(0, timing.tool_io_jitter_us)
    _emit_delay(prof, "tool_io", Bucket.CPU_IO_WAIT, delay)


def _instrumented_fn(
    name: str,
    timing: AgentTiming,
    rng: random.Random,
    body: Callable[[str], dict],
    wall_clock: bool,
) -> Callable[[str], str]:
    def run(query: str) -> str:
        prof = get_profiler()
        delay = timing.tool_io_mean_us + rng.randint(0, timing.tool_io_jitter_us)

        if prof is not None and wall_clock:
            prof.record(f"{name}_parse_request", Bucket.CPU_PARSE, timing.parse_request_us)
            with prof.span(f"{name}_io", Bucket.CPU_IO_WAIT, tool=name):
                time.sleep(max(0, delay) / 1_000_000)
            result = body(query)
            prof.record(f"{name}_parse_response", Bucket.CPU_PARSE, timing.parse_response_us)
            prof.record(f"{name}_state_update", Bucket.CPU_STATE, timing.state_update_us)
            return json.dumps(result)

        if prof is not None:
            prof.record(f"{name}_parse_request", Bucket.CPU_PARSE, timing.parse_request_us)
            prof.record(f"{name}_io", Bucket.CPU_IO_WAIT, delay, tool=name)
            result = body(query)
            prof.record(f"{name}_parse_response", Bucket.CPU_PARSE, timing.parse_response_us)
            prof.record(f"{name}_state_update", Bucket.CPU_STATE, timing.state_update_us)
            return json.dumps(result)

        _emit_delay(None, f"{name}_parse_request", Bucket.CPU_PARSE, timing.parse_request_us)
        _emit_delay(None, f"{name}_io", Bucket.CPU_IO_WAIT, delay, tool=name)
        result = body(query)
        _emit_delay(None, f"{name}_parse_response", Bucket.CPU_PARSE, timing.parse_response_us)
        _emit_delay(None, f"{name}_state_update", Bucket.CPU_STATE, timing.state_update_us)
        return json.dumps(result)

    return run


def build_tools(timing: AgentTiming, seed: int = 0, wall_clock: bool = False) -> list[StructuredTool]:
    rng = random.Random(seed)

    specs: list[tuple[str, str, Callable[[str], dict]]] = [
        (
            "web_search",
            "Search the web for live information.",
            lambda q: {"results": [f"result for {q}"], "source": "web"},
        ),
        (
            "run_python",
            "Execute a short Python snippet in a sandbox.",
            lambda q: {"stdout": f"ok:{q}", "exit_code": 0},
        ),
        (
            "call_api",
            "Call an external HTTP API.",
            lambda q: {"status": 200, "body": {"echo": q}},
        ),
        (
            "retrieve_docs",
            "Retrieve documents from a vector store.",
            lambda q: {"chunks": [f"doc:{q}"], "scores": [0.92]},
        ),
    ]

    tools: list[StructuredTool] = []
    for tool_name, description, body in specs:
        tools.append(
            StructuredTool.from_function(
                func=_instrumented_fn(tool_name, timing, rng, body, wall_clock),
                name=tool_name,
                description=description,
                args_schema=QueryInput,
            )
        )
    return tools
