"""Import/export JSON traces from instrumented agent runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .taxonomy import Bucket, SpanRecord, WorkloadProfile

EXAMPLE_TRACE = Path(__file__).resolve().parent / "traces" / "example_react.json"


class TraceNotFoundError(FileNotFoundError):
    """Raised when a trace path does not exist, with hints for the user."""


def bucket_from_str(name: str) -> Bucket:
    try:
        return Bucket(name)
    except ValueError:
        mapping = {
            "io_wait": Bucket.CPU_IO_WAIT,
            "parse": Bucket.CPU_PARSE,
            "parse_format": Bucket.CPU_PARSE,
            "tokenize": Bucket.CPU_TOKENIZE,
            "orchestration": Bucket.CPU_ORCHESTRATION,
            "state": Bucket.CPU_STATE,
            "state_kv": Bucket.CPU_STATE,
            "gpu_inference": Bucket.GPU_INFERENCE,
            "other": Bucket.CPU_OTHER,
        }
        return mapping.get(name, Bucket.CPU_OTHER)


def load_trace(path: Path) -> WorkloadProfile:
    path = path.expanduser()
    if not path.is_file():
        hints = [
            f"Trace file not found: {path.resolve()}",
            "",
            "Use an existing file, for example:",
            f"  --trace {EXAMPLE_TRACE}",
        ]
        out_dir = Path("orchestration_engine/characterization/out")
        if out_dir.is_dir():
            saved = sorted(out_dir.glob("*.json"))[:5]
            if saved:
                hints.append("")
                hints.append("Or a trace saved by --save-traces / --scaling:")
                for p in saved:
                    hints.append(f"  --trace {p}")
        hints.append("")
        hints.append(
            "Generate traces first: py -3 -m orchestration_engine.characterization.run "
            "--scaling --preset action_heavy --save-traces"
        )
        raise TraceNotFoundError("\n".join(hints))

    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    spans: list[SpanRecord] = []
    for row in payload.get("spans", []):
        spans.append(
            SpanRecord(
                name=row["name"],
                bucket=bucket_from_str(row["bucket"]),
                start_us=int(row["start_us"]),
                end_us=int(row["end_us"]),
                agent_id=row.get("agent_id", "agent_0"),
                meta=row.get("meta", {}),
            )
        )
    return WorkloadProfile(
        name=payload.get("name", path.stem),
        spans=spans,
        concurrency=int(payload.get("concurrency", 1)),
        meta=payload.get("meta", {}),
    )


def save_trace(profile: WorkloadProfile, path: Path) -> None:
    payload = {
        "name": profile.name,
        "concurrency": profile.concurrency,
        "meta": profile.meta,
        "spans": [
            {
                "name": s.name,
                "bucket": s.bucket.value,
                "start_us": s.start_us,
                "end_us": s.end_us,
                "agent_id": s.agent_id,
                "meta": s.meta,
            }
            for s in profile.spans
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def instrument_hook_example() -> str:
    """Return copy-paste pattern for LangGraph / custom agent loops."""
    return '''
# Instrumentation pattern (wall-clock microseconds):
from orchestration_engine.characterization.profiler import Profiler
from orchestration_engine.characterization.taxonomy import Bucket

prof = Profiler(name="my_agent_run")
prof.set_agent("session_123")

with prof.span("tool_web_search", Bucket.CPU_IO_WAIT, tool="web_search"):
    result = await run_tool(...)

prof.record("parse_tool_json", Bucket.CPU_PARSE, duration_us=...)
with prof.span("dispatch_subagent", Bucket.CPU_ORCHESTRATION):
    scheduler.fire(...)

profile = prof.finish()
# save: save_trace(profile, Path("trace.json"))
'''.strip()
