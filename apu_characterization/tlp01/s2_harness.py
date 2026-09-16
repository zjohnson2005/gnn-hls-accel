"""S2 live harness with Tier-0 from_result / dep_refs instrumentation."""

from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from apu_characterization.tlp01.contracts import sha256_bytes


@dataclass
class ResultStore:
    """Thread-safe map from result_id (seq) → payload text."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    _by_id: dict[int, str] = field(default_factory=dict)
    next_seq: int = 1

    def allocate(self, payload: str) -> int:
        with self._lock:
            rid = self.next_seq
            self.next_seq += 1
            self._by_id[rid] = payload
            return rid

    def get(self, rid: int) -> str | None:
        with self._lock:
            return self._by_id.get(rid)


@dataclass
class CallLog:
    entries: list[dict[str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def append(self, entry: dict[str, Any]) -> None:
        with self._lock:
            self.entries.append(entry)


SYSTEM_PROMPT_TIER0 = """You are a careful tool-using agent.
Every tool accepts an optional integer argument from_result.
When a later tool call depends on a prior tool's output, you MUST pass
from_result=<prior result_id> instead of only pasting the prior text.
When calls are independent, omit from_result.
Each tool response JSON includes result_id for later reference.
Follow the user task's independence / serial instructions exactly.
Temperature is fixed externally; be deterministic."""


def build_tier0_tools(store: ResultStore, log: CallLog) -> list[Any]:
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    from apu_characterization.tools import run_tool

    class ToolInput(BaseModel):
        query: str = Field(description="Primary tool input")
        from_result: int | None = Field(
            default=None,
            description=(
                "Optional prior result_id this call depends on. "
                "Omit when the call is independent."
            ),
        )

    def make_fn(tool_name: str):
        def fn(query: str, from_result: int | None = None) -> str:
            t_issue = time.perf_counter_ns()
            dep_refs: list[int] = []
            resolved_query = query
            if from_result is not None:
                prior = store.get(int(from_result))
                if prior is None:
                    err = {
                        "error": f"unknown from_result id {from_result}",
                        "tool": tool_name,
                    }
                    payload = json.dumps(err)
                    rid = store.allocate(payload)
                    t_complete = time.perf_counter_ns()
                    log.append(
                        {
                            "tool": tool_name,
                            "query": query,
                            "from_result": from_result,
                            "dep_refs": [],
                            "result_id": rid,
                            "t_issue_ns": t_issue,
                            "t_complete_ns": t_complete,
                            "output": payload,
                            "error": True,
                        }
                    )
                    return payload
                dep_refs = [int(from_result)]
                resolved_query = (
                    f"{query}\n\n[from_result={from_result} resolved]\n{prior[:2000]}"
                )

            session_id = "tlp01-s2"
            try:
                result = run_tool(
                    tool_name, resolved_query, session_id, random.Random(0)
                )
            except Exception as exc:  # noqa: BLE001
                result = {"error": str(exc), "tool": tool_name, "query": query}

            body = json.dumps(result, ensure_ascii=True)
            rid = store.allocate(body)
            wrapped = {"result_id": rid, "tool": tool_name, "result": result}
            payload = json.dumps(wrapped, ensure_ascii=True)
            t_complete = time.perf_counter_ns()
            log.append(
                {
                    "tool": tool_name,
                    "query": query,
                    "resolved_query": resolved_query[:2000],
                    "from_result": from_result,
                    "dep_refs": dep_refs,
                    "result_id": rid,
                    "t_issue_ns": t_issue,
                    "t_complete_ns": t_complete,
                    "output": body,
                    "error": "error" in result,
                }
            )
            return payload

        return fn

    descriptions = {
        "search": "Search a text corpus. Input: keywords. Optional from_result.",
        "code_exec": (
            "Run Python assigning to `result`. Optional from_result for dependence."
        ),
        "retrieve": "Retrieve document chunks. Optional from_result.",
        "calculator": (
            "Evaluate a numeric expression. Optional from_result for dependence."
        ),
    }
    return [
        StructuredTool.from_function(
            func=make_fn(name),
            name=name,
            description=desc,
            args_schema=ToolInput,
        )
        for name, desc in descriptions.items()
    ]


def run_s2_session(
    *,
    task_id: str,
    goal: str,
    seed: int,
    model_name: str | None = None,
) -> dict[str, Any]:
    """Run one live OpenAI ReAct session with Tier-0 tools. Append-only log."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent

    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if len(key) < 20:
        raise RuntimeError(
            "OPENAI_API_KEY missing or too short for S2 collection "
            f"(len={len(key)}; refuse to call OpenAI)"
        )

    store = ResultStore()
    log = CallLog()
    tools = build_tier0_tools(store, log)
    model_name = model_name or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    model = ChatOpenAI(model=model_name, temperature=0)
    agent = create_react_agent(model, tools)

    wall0 = time.perf_counter()
    t0 = time.perf_counter_ns()
    inputs = {
        "messages": [
            SystemMessage(content=SYSTEM_PROMPT_TIER0),
            HumanMessage(content=goal),
        ]
    }
    config = {"recursion_limit": 40}
    final_text = ""
    try:
        for chunk in agent.stream(inputs, stream_mode="updates", config=config):
            node = next(iter(chunk.keys()))
            if node == "agent":
                update = chunk.get("agent") or {}
                for msg in update.get("messages", []):
                    content = getattr(msg, "content", None)
                    if isinstance(content, str) and content.strip():
                        final_text = content
    except Exception as exc:  # noqa: BLE001
        detail = str(exc)
        body = getattr(exc, "body", None)
        response = getattr(exc, "response", None)
        if body is not None:
            detail = f"{detail} | body={body!r}"
        elif response is not None:
            try:
                detail = f"{detail} | response={response.text!r}"
            except Exception:  # noqa: BLE001
                detail = f"{detail} | response={response!r}"
        return {
            "ok": False,
            "task_id": task_id,
            "seed": seed,
            "error": detail[:4000],
            "tool_log": list(log.entries),
            "model": model_name,
        }

    wall_s = time.perf_counter() - wall0
    prompt_hash = hashlib.sha256(
        (SYSTEM_PROMPT_TIER0 + "\n" + goal).encode("utf-8")
    ).hexdigest()
    return {
        "ok": True,
        "task_id": task_id,
        "seed": seed,
        "model": model_name,
        "temperature": 0,
        "prompt_sha256": prompt_hash,
        "wall_s": wall_s,
        "t_session_start_ns": t0,
        "final_text": final_text[:4000],
        "tool_log": list(log.entries),
        "tool_call_count": len(log.entries),
        "system_prompt_sha256": sha256_bytes(SYSTEM_PROMPT_TIER0.encode("utf-8")),
    }


def session_record_to_events(record: dict[str, Any], session_id: str) -> list[dict[str, Any]]:
    """Convert an S2 session record into schema v2 event dicts."""
    task_id = str(record["task_id"])
    task_class = task_id.split("-", 1)[0]
    seed = int(record["seed"])
    t0 = int(record.get("t_session_start_ns") or 0)
    events: list[dict[str, Any]] = []
    # Turn 0: model planning / goal ingest (synthetic envelope around tool log).
    first_issue = (
        min(int(e["t_issue_ns"]) for e in record["tool_log"])
        if record.get("tool_log")
        else t0
    )
    events.append(
        {
            "session_id": session_id,
            "seq": 0,
            "event_type": "turn",
            "t_issue_ns": 0,
            "t_complete_ns": max(first_issue - t0, 1),
            "inputs_hash": record.get("prompt_sha256") or "goal",
            "output_hash": hashlib.sha256(
                (record.get("final_text") or "").encode("utf-8")
            ).hexdigest()[:16],
            "output_text_ref": "final",
            "tool_name": None,
            "args_ref": None,
            "result_ref": None,
            "stage_timings": {"orch_ns": 0},
            "harness_order_index": 0,
            "task_class": task_class,
            "seed": seed,
            "input_text": "",
            "output_text": record.get("final_text") or "",
            "dep_refs": [],
        }
    )
    for order, entry in enumerate(record.get("tool_log") or [], start=1):
        issue = max(int(entry["t_issue_ns"]) - t0, 0)
        complete = max(int(entry["t_complete_ns"]) - t0, issue + 1)
        out = str(entry.get("output") or "")
        q = str(entry.get("query") or "")
        rid = int(entry["result_id"])
        deps = [int(x) for x in (entry.get("dep_refs") or [])]
        from_result = entry.get("from_result")
        # Include structured id in input_text so Tier-C can observe the same
        # edge Tier-0 proved (G-D extension calibration signal).
        if from_result is not None:
            input_text = f"{q}\nfrom_result={int(from_result)}"
        else:
            input_text = q
        # Map result_id space onto event seq: tool events use result_id as seq.
        seq = rid
        events.append(
            {
                "session_id": session_id,
                "seq": seq,
                "event_type": "tool_call",
                "t_issue_ns": issue,
                "t_complete_ns": complete,
                "inputs_hash": hashlib.sha256(input_text.encode("utf-8")).hexdigest()[
                    :16
                ],
                "output_hash": hashlib.sha256(out.encode("utf-8")).hexdigest()[:16],
                "output_text_ref": f"result-{rid}",
                "tool_name": entry.get("tool"),
                "args_ref": f"args-{rid}",
                "result_ref": f"result-{rid}",
                "stage_timings": {"orch_ns": 0},
                "harness_order_index": order,
                "task_class": task_class,
                "seed": seed,
                "result_ids": [str(rid)],
                # Planning turn is seq 0; tools are its control children.
                # M1 breaks control edges by design — this populates Tier-S
                # control edges for models that respect them / for audit.
                "control_parent_seq": 0,
                "input_text": input_text,
                "output_text": out[:4000],
                "dep_refs": deps,
            }
        )
    return events
