"""Endpoint-local accounting for the MCP protocol-tax experiment.

This module deliberately does not reuse :class:`apu_characterization.instr.RunAccumulator`.
An MCP endpoint owns one accumulator and one process role, so client and server
measurements cannot accidentally share a session or thread ledger.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .contracts import InstrMode, ProcessRole
from .taxonomy import McpCategory

LEDGER_VERSION = "mcp_endpoint_ledger_v1"
WAIT_KINDS = frozenset(
    {
        "transport_blocked",
        "runqueue",
        "synthetic_tool_delay",
        "unattributed_wait",
    }
)
VALID_MODES = frozenset({"full", "throttle", "stripped"})
VALID_ROLES = frozenset({"client", "server"})


def _nonnegative_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


@dataclass
class LedgerTotals:
    """One additive CPU category or wait-axis cell."""

    cpu_ns: int = 0
    wall_ns: int = 0
    bytes_in: int = 0
    bytes_out: int = 0
    count: int = 0
    provenance: dict[str, int] = field(default_factory=dict)

    @property
    def bytes(self) -> int:
        """Direction-agnostic byte total required by the ledger contract."""

        return self.bytes_in + self.bytes_out

    def add(
        self,
        cpu_ns: int,
        *,
        wall_ns: int = 0,
        bytes_in: int = 0,
        bytes_out: int = 0,
        count: int = 1,
        provenance: str = "measured",
    ) -> None:
        _nonnegative_int("cpu_ns", cpu_ns)
        _nonnegative_int("wall_ns", wall_ns)
        _nonnegative_int("bytes_in", bytes_in)
        _nonnegative_int("bytes_out", bytes_out)
        _nonnegative_int("count", count)
        if not provenance:
            raise ValueError("provenance must be non-empty")
        self.cpu_ns += cpu_ns
        self.wall_ns += wall_ns
        self.bytes_in += bytes_in
        self.bytes_out += bytes_out
        self.count += count
        self.provenance[provenance] = self.provenance.get(provenance, 0) + cpu_ns

    def as_dict(self) -> dict[str, Any]:
        return {
            "cpu_ns": self.cpu_ns,
            "wall_ns": self.wall_ns,
            "bytes": self.bytes,
            "bytes_in": self.bytes_in,
            "bytes_out": self.bytes_out,
            "count": self.count,
            "provenance": dict(sorted(self.provenance.items())),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "LedgerTotals":
        bytes_in = _nonnegative_int("bytes_in", value.get("bytes_in", 0))
        bytes_out = _nonnegative_int("bytes_out", value.get("bytes_out", 0))
        if "bytes" in value:
            total_bytes = _nonnegative_int("bytes", value["bytes"])
            if bytes_in + bytes_out == 0:
                bytes_out = total_bytes
            elif bytes_in + bytes_out != total_bytes:
                raise ValueError("bytes must equal bytes_in + bytes_out")
        totals = cls(
            cpu_ns=_nonnegative_int("cpu_ns", value.get("cpu_ns", 0)),
            wall_ns=_nonnegative_int("wall_ns", value.get("wall_ns", 0)),
            bytes_in=bytes_in,
            bytes_out=bytes_out,
            count=_nonnegative_int("count", value.get("count", 0)),
        )
        provenance = value.get("provenance", {})
        if not isinstance(provenance, Mapping):
            raise ValueError("provenance must be an object")
        totals.provenance = {
            str(key): _nonnegative_int(f"provenance[{key!r}]", amount)
            for key, amount in provenance.items()
        }
        return totals


@dataclass
class ScopeObservation:
    """Process-clock and timestamp envelope for a measured scope."""

    start_wall_ns: int
    end_wall_ns: int
    process_cpu_ns: int
    wall_ns: int
    thread_schedstat_cpu_ns: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "start_wall_ns": self.start_wall_ns,
            "end_wall_ns": self.end_wall_ns,
            "process_cpu_ns": self.process_cpu_ns,
            "wall_ns": self.wall_ns,
            "metadata": self.metadata,
        }
        if self.thread_schedstat_cpu_ns is not None:
            result["thread_schedstat_cpu_ns"] = self.thread_schedstat_cpu_ns
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ScopeObservation":
        schedstat = value.get("thread_schedstat_cpu_ns")
        if schedstat is not None:
            schedstat = _nonnegative_int("thread_schedstat_cpu_ns", schedstat)
        metadata = value.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ValueError("observation metadata must be an object")
        return cls(
            start_wall_ns=_nonnegative_int("start_wall_ns", value["start_wall_ns"]),
            end_wall_ns=_nonnegative_int("end_wall_ns", value["end_wall_ns"]),
            process_cpu_ns=_nonnegative_int("process_cpu_ns", value["process_cpu_ns"]),
            wall_ns=_nonnegative_int("wall_ns", value["wall_ns"]),
            thread_schedstat_cpu_ns=schedstat,
            metadata=dict(metadata),
        )


@dataclass(frozen=True)
class _ScopeStart:
    start_wall_ns: int
    start_process_cpu_ns: int
    start_schedstat_cpu_ns: int | None
    metadata: dict[str, Any]


@dataclass
class McpMessageAccumulator:
    """Independent ledger for one MCP client or server process.

    Message category cells are keyed by ``(category, message_id, process_role)``.
    Session setup and waits have separate ledgers and therefore cannot be
    mistaken for per-message CPU categories.
    """

    process_role: ProcessRole
    mode: InstrMode = "throttle"
    by_key: dict[tuple[str, str, str], LedgerTotals] = field(default_factory=dict)
    setup_by_key: dict[tuple[str, str], LedgerTotals] = field(default_factory=dict)
    waits_by_key: dict[tuple[str, str, str], LedgerTotals] = field(default_factory=dict)
    messages: dict[str, ScopeObservation] = field(default_factory=dict)
    setup_observation: ScopeObservation | None = None
    endpoint_observation: ScopeObservation | None = None
    sdk_coverage: list[dict[str, Any]] = field(default_factory=list)
    canonical_hashes: list[str] = field(default_factory=list)
    message_diagnostics: dict[str, dict[str, Any]] = field(default_factory=dict)
    wire_captures: list[dict[str, Any]] = field(default_factory=list)
    _active_messages: dict[str, _ScopeStart] = field(
        default_factory=dict, init=False, repr=False
    )
    _active_setup: _ScopeStart | None = field(default=None, init=False, repr=False)
    _active_endpoint: _ScopeStart | None = field(default=None, init=False, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.process_role not in VALID_ROLES:
            raise ValueError("process_role must be 'client' or 'server'")
        if self.mode not in VALID_MODES:
            raise ValueError("mode must be full, throttle, or stripped")

    @property
    def category_hooks_enabled(self) -> bool:
        return self.mode != "stripped"

    def _role(self, process_role: ProcessRole | None) -> ProcessRole:
        role = process_role or self.process_role
        if role != self.process_role:
            raise ValueError(
                f"endpoint role is {self.process_role!r}, not {role!r}; "
                "use an independent accumulator for the other endpoint"
            )
        return role

    def book(
        self,
        category: McpCategory | str,
        ns: int,
        *,
        message_id: str | None = None,
        process_role: ProcessRole | None = None,
        wall_ns: int = 0,
        bytes: int = 0,
        bytes_in: int = 0,
        bytes_out: int = 0,
        count: int = 1,
        provenance: str = "measured",
    ) -> bool:
        """Book exclusive thread CPU to a frozen MCP category.

        ``False`` means the observation was intentionally suppressed by
        stripped mode. The argument name ``ns`` is retained as the compact
        frozen contract; it always denotes CPU, never elapsed wall time.
        """

        cat = category if isinstance(category, McpCategory) else McpCategory(category)
        role = self._role(process_role)
        _nonnegative_int("ns", ns)
        _nonnegative_int("bytes", bytes)
        if bytes and (bytes_in or bytes_out):
            raise ValueError("use either bytes or directional bytes_in/bytes_out")
        if bytes:
            bytes_out = bytes
        if not self.category_hooks_enabled and cat is not McpCategory.RESIDUAL:
            return False
        if cat is McpCategory.SESSION_SETUP:
            if message_id is not None:
                raise ValueError("SESSION_SETUP must not be attached to a message")
            key = (cat.value, role)
            with self._lock:
                totals = self.setup_by_key.setdefault(key, LedgerTotals())
                totals.add(
                    ns,
                    wall_ns=wall_ns,
                    bytes_in=bytes_in,
                    bytes_out=bytes_out,
                    count=count,
                    provenance=provenance,
                )
            return True
        if message_id is None:
            from .message_context import get_message_context

            context = get_message_context()
            if context is not None and context.process_role == role:
                message_id = context.message_id
        if message_id is None or not str(message_id):
            raise ValueError(f"{cat.value} requires a non-empty message_id")
        key = (cat.value, str(message_id), role)
        with self._lock:
            totals = self.by_key.setdefault(key, LedgerTotals())
            totals.add(
                ns,
                wall_ns=wall_ns,
                bytes_in=bytes_in,
                bytes_out=bytes_out,
                count=count,
                provenance=provenance,
            )
        return True

    def book_wait(
        self,
        kind: str,
        ns: int,
        *,
        message_id: str | None = None,
        process_role: ProcessRole | None = None,
        count: int = 1,
        provenance: str = "measured",
    ) -> None:
        """Book elapsed non-CPU time on the separate wait axis."""

        if kind not in WAIT_KINDS:
            raise ValueError(f"unknown wait kind {kind!r}")
        role = self._role(process_role)
        _nonnegative_int("ns", ns)
        if message_id is None:
            from .message_context import get_message_context

            context = get_message_context()
            if context is not None and context.process_role == role:
                message_id = context.message_id
        if message_id is None or not str(message_id):
            raise ValueError("wait booking requires a non-empty message_id")
        key = (kind, str(message_id), role)
        with self._lock:
            totals = self.waits_by_key.setdefault(key, LedgerTotals())
            totals.add(0, wall_ns=ns, count=count, provenance=provenance)

    def totals_for(
        self,
        category: McpCategory | str,
        message_id: str,
        process_role: ProcessRole | None = None,
    ) -> LedgerTotals:
        cat = category if isinstance(category, McpCategory) else McpCategory(category)
        role = self._role(process_role)
        if cat is McpCategory.SESSION_SETUP:
            raise ValueError("use setup_totals() for SESSION_SETUP")
        with self._lock:
            return self.by_key.setdefault((cat.value, str(message_id), role), LedgerTotals())

    def setup_totals(self) -> LedgerTotals:
        with self._lock:
            return self.setup_by_key.setdefault(
                (McpCategory.SESSION_SETUP.value, self.process_role), LedgerTotals()
            )

    def wait_totals(self, kind: str, message_id: str) -> LedgerTotals:
        if kind not in WAIT_KINDS:
            raise ValueError(f"unknown wait kind {kind!r}")
        with self._lock:
            return self.waits_by_key.setdefault(
                (kind, str(message_id), self.process_role), LedgerTotals()
            )

    def categories_for_message(self, message_id: str) -> dict[str, LedgerTotals]:
        with self._lock:
            return {
                category: totals
                for (category, mid, role), totals in self.by_key.items()
                if mid == str(message_id) and role == self.process_role
            }

    def waits_for_message(self, message_id: str) -> dict[str, LedgerTotals]:
        with self._lock:
            return {
                kind: totals
                for (kind, mid, role), totals in self.waits_by_key.items()
                if mid == str(message_id) and role == self.process_role
            }

    @staticmethod
    def _begin_scope(
        *,
        schedstat_cpu_ns: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> _ScopeStart:
        return _ScopeStart(
            start_wall_ns=time.perf_counter_ns(),
            start_process_cpu_ns=time.process_time_ns(),
            start_schedstat_cpu_ns=schedstat_cpu_ns,
            metadata=dict(metadata or {}),
        )

    @staticmethod
    def _finish_scope(
        start: _ScopeStart,
        *,
        schedstat_cpu_ns: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ScopeObservation:
        end_process_cpu_ns = time.process_time_ns()
        end_wall_ns = time.perf_counter_ns()
        schedstat_delta = None
        if start.start_schedstat_cpu_ns is not None and schedstat_cpu_ns is not None:
            schedstat_delta = max(0, schedstat_cpu_ns - start.start_schedstat_cpu_ns)
        merged_metadata = dict(start.metadata)
        merged_metadata.update(metadata or {})
        return ScopeObservation(
            start_wall_ns=start.start_wall_ns,
            end_wall_ns=end_wall_ns,
            process_cpu_ns=max(0, end_process_cpu_ns - start.start_process_cpu_ns),
            wall_ns=max(0, end_wall_ns - start.start_wall_ns),
            thread_schedstat_cpu_ns=schedstat_delta,
            metadata=merged_metadata,
        )

    def begin_message(
        self,
        message_id: str,
        *,
        schedstat_cpu_ns: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        mid = str(message_id)
        if not mid:
            raise ValueError("message_id must be non-empty")
        with self._lock:
            if mid in self._active_messages:
                raise RuntimeError(f"message {mid!r} is already active")
            if mid in self.messages:
                raise RuntimeError(f"message {mid!r} was already recorded")
            self._active_messages[mid] = self._begin_scope(
                schedstat_cpu_ns=schedstat_cpu_ns, metadata=metadata
            )

    def end_message(
        self,
        message_id: str,
        *,
        schedstat_cpu_ns: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ScopeObservation:
        mid = str(message_id)
        with self._lock:
            try:
                start = self._active_messages.pop(mid)
            except KeyError as exc:
                raise RuntimeError(f"message {mid!r} is not active") from exc
            observation = self._finish_scope(
                start, schedstat_cpu_ns=schedstat_cpu_ns, metadata=metadata
            )
            self.messages[mid] = observation
            return observation

    def begin_setup(
        self,
        *,
        schedstat_cpu_ns: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        with self._lock:
            if self._active_setup is not None or self.setup_observation is not None:
                raise RuntimeError("setup scope is already active or recorded")
            self._active_setup = self._begin_scope(
                schedstat_cpu_ns=schedstat_cpu_ns, metadata=metadata
            )

    def end_setup(
        self,
        *,
        schedstat_cpu_ns: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ScopeObservation:
        with self._lock:
            if self._active_setup is None:
                raise RuntimeError("setup scope is not active")
            start = self._active_setup
            self._active_setup = None
            self.setup_observation = self._finish_scope(
                start, schedstat_cpu_ns=schedstat_cpu_ns, metadata=metadata
            )
            return self.setup_observation

    def begin_endpoint(self, *, metadata: Mapping[str, Any] | None = None) -> None:
        with self._lock:
            if self._active_endpoint is not None or self.endpoint_observation is not None:
                raise RuntimeError("endpoint scope is already active or recorded")
            self._active_endpoint = self._begin_scope(metadata=metadata)

    def end_endpoint(
        self, *, metadata: Mapping[str, Any] | None = None
    ) -> ScopeObservation:
        with self._lock:
            if self._active_endpoint is None:
                raise RuntimeError("endpoint scope is not active")
            start = self._active_endpoint
            self._active_endpoint = None
            self.endpoint_observation = self._finish_scope(start, metadata=metadata)
            return self.endpoint_observation

    def set_message_observation(
        self,
        message_id: str,
        *,
        process_cpu_ns: int,
        wall_ns: int,
        start_wall_ns: int = 0,
        end_wall_ns: int | None = None,
        thread_schedstat_cpu_ns: int | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Install a known observation (primarily for replay and tests)."""

        mid = str(message_id)
        if not mid:
            raise ValueError("message_id must be non-empty")
        if end_wall_ns is None:
            end_wall_ns = start_wall_ns + wall_ns
        observation = ScopeObservation(
            start_wall_ns=_nonnegative_int("start_wall_ns", start_wall_ns),
            end_wall_ns=_nonnegative_int("end_wall_ns", end_wall_ns),
            process_cpu_ns=_nonnegative_int("process_cpu_ns", process_cpu_ns),
            wall_ns=_nonnegative_int("wall_ns", wall_ns),
            thread_schedstat_cpu_ns=(
                None
                if thread_schedstat_cpu_ns is None
                else _nonnegative_int(
                    "thread_schedstat_cpu_ns", thread_schedstat_cpu_ns
                )
            ),
            metadata=dict(metadata or {}),
        )
        with self._lock:
            if mid in self._active_messages:
                raise RuntimeError(f"message {mid!r} is active")
            self.messages[mid] = observation

    def record_sdk_coverage(self, value: Mapping[str, Any]) -> None:
        with self._lock:
            self.sdk_coverage.append(dict(value))

    def record_canonical_hash(self, value: str) -> None:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("canonical hash must be a lowercase SHA-256 digest")
        with self._lock:
            self.canonical_hashes.append(value)

    def record_message_diagnostic(
        self, message_id: str, key: str, value: Any
    ) -> None:
        mid = str(message_id)
        with self._lock:
            self.message_diagnostics.setdefault(mid, {})[key] = value

    def record_wire_capture(
        self,
        *,
        message_id: str,
        label: str,
        path: str,
        byte_count: int,
    ) -> None:
        with self._lock:
            self.wire_captures.append(
                {
                    "message_id": str(message_id),
                    "label": label,
                    "path": path,
                    "bytes": _nonnegative_int("bytes", byte_count),
                }
            )

    def message_booked_cpu_ns(self, message_id: str) -> int:
        mid = str(message_id)
        with self._lock:
            return sum(
                totals.cpu_ns
                for (category, booked_id, role), totals in self.by_key.items()
                if booked_id == mid
                and role == self.process_role
                and category != McpCategory.RESIDUAL.value
            )

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            if self._active_messages or self._active_setup or self._active_endpoint:
                raise RuntimeError("cannot serialize an accumulator with active scopes")
            return {
                "ledger_version": LEDGER_VERSION,
                "process_role": self.process_role,
                "mode": self.mode,
                "category_hooks_enabled": self.category_hooks_enabled,
                "endpoint_observation": (
                    self.endpoint_observation.as_dict()
                    if self.endpoint_observation is not None
                    else None
                ),
                "setup_observation": (
                    self.setup_observation.as_dict()
                    if self.setup_observation is not None
                    else None
                ),
                "messages": {
                    message_id: observation.as_dict()
                    for message_id, observation in sorted(self.messages.items())
                },
                "categories": [
                    {
                        "category": category,
                        "message_id": message_id,
                        "process_role": role,
                        "totals": totals.as_dict(),
                    }
                    for (category, message_id, role), totals in sorted(self.by_key.items())
                ],
                "setup": [
                    {
                        "category": category,
                        "process_role": role,
                        "totals": totals.as_dict(),
                    }
                    for (category, role), totals in sorted(self.setup_by_key.items())
                ],
                "waits": [
                    {
                        "kind": kind,
                        "message_id": message_id,
                        "process_role": role,
                        "totals": totals.as_dict(),
                    }
                    for (kind, message_id, role), totals in sorted(
                        self.waits_by_key.items()
                    )
                ],
                "sdk_coverage": list(self.sdk_coverage),
                "canonical_hashes": list(self.canonical_hashes),
                "message_diagnostics": {
                    message_id: dict(values)
                    for message_id, values in sorted(self.message_diagnostics.items())
                },
                "wire_captures": list(self.wire_captures),
            }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "McpMessageAccumulator":
        if value.get("ledger_version") != LEDGER_VERSION:
            raise ValueError("unsupported MCP endpoint ledger version")
        acc = cls(process_role=value["process_role"], mode=value.get("mode", "throttle"))
        endpoint = value.get("endpoint_observation")
        if endpoint is not None:
            acc.endpoint_observation = ScopeObservation.from_dict(endpoint)
        setup_observation = value.get("setup_observation")
        if setup_observation is not None:
            acc.setup_observation = ScopeObservation.from_dict(setup_observation)
        messages = value.get("messages", {})
        if not isinstance(messages, Mapping):
            raise ValueError("messages must be an object")
        acc.messages = {
            str(message_id): ScopeObservation.from_dict(observation)
            for message_id, observation in messages.items()
        }
        for cell in value.get("categories", []):
            category = McpCategory(cell["category"])
            if category is McpCategory.SESSION_SETUP:
                raise ValueError("SESSION_SETUP cannot appear in message categories")
            role = acc._role(cell["process_role"])
            message_id = str(cell["message_id"])
            acc.by_key[(category.value, message_id, role)] = LedgerTotals.from_dict(
                cell["totals"]
            )
        for cell in value.get("setup", []):
            category = McpCategory(cell["category"])
            if category is not McpCategory.SESSION_SETUP:
                raise ValueError("only SESSION_SETUP can appear in setup ledger")
            role = acc._role(cell["process_role"])
            acc.setup_by_key[(category.value, role)] = LedgerTotals.from_dict(
                cell["totals"]
            )
        for cell in value.get("waits", []):
            kind = str(cell["kind"])
            if kind not in WAIT_KINDS:
                raise ValueError(f"unknown wait kind {kind!r}")
            role = acc._role(cell["process_role"])
            totals = LedgerTotals.from_dict(cell["totals"])
            if totals.cpu_ns != 0:
                raise ValueError("wait ledger CPU must be zero")
            acc.waits_by_key[(kind, str(cell["message_id"]), role)] = totals
        sdk_coverage = value.get("sdk_coverage", [])
        if not isinstance(sdk_coverage, list):
            raise ValueError("sdk_coverage must be an array")
        acc.sdk_coverage = [dict(item) for item in sdk_coverage]
        hashes = value.get("canonical_hashes", [])
        if not isinstance(hashes, list):
            raise ValueError("canonical_hashes must be an array")
        for digest in hashes:
            acc.record_canonical_hash(str(digest))
        diagnostics = value.get("message_diagnostics", {})
        if diagnostics:
            if not isinstance(diagnostics, Mapping):
                raise ValueError("message_diagnostics must be an object")
            acc.message_diagnostics = {
                str(message_id): dict(items)
                for message_id, items in diagnostics.items()
            }
        wire_captures = value.get("wire_captures", [])
        if wire_captures:
            if not isinstance(wire_captures, list):
                raise ValueError("wire_captures must be an array")
            acc.wire_captures = [dict(item) for item in wire_captures]
        return acc

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, indent=indent)

    @classmethod
    def from_json(cls, text: str | bytes) -> "McpMessageAccumulator":
        if isinstance(text, bytes):
            text = text.decode("utf-8")
        value = json.loads(text)
        if not isinstance(value, Mapping):
            raise ValueError("endpoint ledger JSON must contain an object")
        return cls.from_dict(value)

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(self.to_json() + "\n", encoding="utf-8")
        temporary.replace(destination)
        return destination

    @classmethod
    def load(cls, path: str | Path) -> "McpMessageAccumulator":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))
