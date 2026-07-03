"""Latency bucket taxonomy for agentic workload characterization.

Aligns with the five-way CPU-side split in the research brief and keeps GPU
inference separate (it is not part of the 50–90% CPU tool-processing bucket).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Bucket(str, Enum):
    """Top-level latency buckets."""

    GPU_INFERENCE = "gpu_inference"
    CPU_IO_WAIT = "cpu_io_wait"
    CPU_PARSE = "cpu_parse"
    CPU_TOKENIZE = "cpu_tokenize"
    CPU_ORCHESTRATION = "cpu_orchestration"
    CPU_STATE = "cpu_state"
    CPU_OTHER = "cpu_other"


CPU_TOOL_BUCKETS: tuple[Bucket, ...] = (
    Bucket.CPU_IO_WAIT,
    Bucket.CPU_PARSE,
    Bucket.CPU_TOKENIZE,
    Bucket.CPU_ORCHESTRATION,
    Bucket.CPU_STATE,
    Bucket.CPU_OTHER,
)

ACCELERABLE_CPU_BUCKETS: tuple[Bucket, ...] = (
    Bucket.CPU_PARSE,
    Bucket.CPU_TOKENIZE,
    Bucket.CPU_ORCHESTRATION,
    Bucket.CPU_STATE,
    Bucket.CPU_OTHER,
)

COORDINATION_BUCKET = Bucket.CPU_ORCHESTRATION


class CpuBucket(str, Enum):
    IO_WAIT = "io_wait"
    PARSE = "parse_format"
    TOKENIZE = "tokenize"
    ORCHESTRATION = "orchestration"
    STATE = "state_kv"
    OTHER = "other"


BUCKET_TO_CPU_LABEL: dict[Bucket, CpuBucket | None] = {
    Bucket.GPU_INFERENCE: None,
    Bucket.CPU_IO_WAIT: CpuBucket.IO_WAIT,
    Bucket.CPU_PARSE: CpuBucket.PARSE,
    Bucket.CPU_TOKENIZE: CpuBucket.TOKENIZE,
    Bucket.CPU_ORCHESTRATION: CpuBucket.ORCHESTRATION,
    Bucket.CPU_STATE: CpuBucket.STATE,
    Bucket.CPU_OTHER: CpuBucket.OTHER,
}


@dataclass
class SpanRecord:
    name: str
    bucket: Bucket
    start_us: int
    end_us: int
    agent_id: str = "agent_0"
    meta: dict[str, str] = field(default_factory=dict)

    @property
    def duration_us(self) -> int:
        return max(0, self.end_us - self.start_us)


@dataclass
class WorkloadProfile:
    name: str
    spans: list[SpanRecord]
    concurrency: int = 1
    meta: dict[str, str] = field(default_factory=dict)

    def bucket_totals_us(self) -> dict[Bucket, int]:
        totals: dict[Bucket, int] = {b: 0 for b in Bucket}
        for span in self.spans:
            totals[span.bucket] += span.duration_us
        return totals

    def total_us(self) -> int:
        return sum(s.duration_us for s in self.spans)

    def cpu_tool_phase_us(self) -> int:
        return sum(self.bucket_totals_us()[b] for b in CPU_TOOL_BUCKETS)

    def e2e_us(self) -> int:
        if not self.spans:
            return 0
        if self.concurrency <= 1:
            return self.total_us()
        return max(s.end_us for s in self.spans)
