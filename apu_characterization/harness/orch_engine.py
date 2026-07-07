"""Python orchestration engine mirroring oe software-sim scatter/dispatch semantics."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable

from ..instr import timed
from ..taxonomy import Category


class NodeKind(IntEnum):
    COMPUTE = 0
    TOOL = 1
    COORDINATION = 2


class FireMode(IntEnum):
    ALL_OF = 0
    ANY_OF = 1


class NodeState(IntEnum):
    PENDING = 0
    READY = 1
    OUTSTANDING = 2
    DONE = 3


@dataclass
class NodeDesc:
    id: int
    kind: NodeKind
    fire_mode: FireMode = FireMode.ALL_OF
    preds_remaining: int = 0
    preds_total: int = 0
    state: NodeState = NodeState.PENDING
    predicted_latency: int = 1


@dataclass
class OrchEngine:
    """Minimal CSR-style graph + ready queue + scatter-on-completion."""

    nodes: list[NodeDesc] = field(default_factory=list)
    succ: dict[int, list[int]] = field(default_factory=dict)
    ready_q: list[int] = field(default_factory=list)
    live_tasks: int = 0
    stats_dispatch: int = 0
    stats_scatter: int = 0
    stats_setup_ops: int = 0

    def setup_session(
        self,
        session_id: str,
        tool_counts: list[int],
        on_dispatch: Callable[[NodeDesc], None] | None = None,
    ) -> None:
        """Build the ReAct task graph from the per-turn tool-call counts.

        Per turn: prev -> LLM compute node; if the turn has k > 0 tool
        calls, LLM fans out to k tool nodes which join on an ALL_OF
        coordination node (the fan-out/dispatch-burst structure). Turns
        with no tool calls chain LLM to LLM directly.
        """
        with timed(Category.ORCH_SETUP, session_id):
            self.nodes.clear()
            self.succ.clear()
            self.ready_q.clear()
            self.live_tasks = 0
            self.stats_dispatch = 0
            self.stats_scatter = 0
            self.stats_setup_ops = 0

            root = self._add_node(NodeKind.COORDINATION)
            prev = root
            for k in tool_counts:
                llm = self._add_node(NodeKind.COMPUTE)
                self._add_edge(prev, llm)
                self.stats_setup_ops += 2
                if k > 0:
                    join = self._add_node(NodeKind.COORDINATION)
                    for _ in range(k):
                        tool = self._add_node(NodeKind.TOOL)
                        self._add_edge(llm, tool)
                        self._add_edge(tool, join)
                        self.stats_setup_ops += 3
                    prev = join
                else:
                    prev = llm

            finish = self._add_node(NodeKind.COORDINATION)
            self._add_edge(prev, finish)
            self.stats_setup_ops += 1

            self.nodes[root].state = NodeState.READY
            self.ready_q.append(root)

    def _add_node(self, kind: NodeKind) -> int:
        nid = len(self.nodes)
        self.nodes.append(NodeDesc(id=nid, kind=kind))
        self.succ[nid] = []
        return nid

    def _add_edge(self, src: int, dst: int) -> None:
        self.succ.setdefault(src, []).append(dst)
        d = self.nodes[dst]
        d.preds_total += 1
        d.preds_remaining = d.preds_total

    def _mark_ready(self, nid: int) -> None:
        n = self.nodes[nid]
        if n.state in (NodeState.DONE, NodeState.OUTSTANDING):
            return
        n.state = NodeState.READY
        self.ready_q.append(nid)

    def _scatter(self, completed: int) -> None:
        self.stats_scatter += 1
        for succ in self.succ.get(completed, []):
            d = self.nodes[succ]
            if d.state == NodeState.DONE:
                continue
            if d.fire_mode == FireMode.ANY_OF:
                self._mark_ready(succ)
            else:
                if d.preds_remaining > 0:
                    d.preds_remaining -= 1
                if d.preds_remaining == 0:
                    self._mark_ready(succ)

    def dispatch_ready(self, session_id: str) -> list[NodeDesc]:
        """Pop ready queue, simulate dispatch decisions (Phase 0 steady path)."""
        dispatched: list[NodeDesc] = []
        with timed(Category.ORCH_DISPATCH, session_id):
            while self.ready_q:
                nid = self.ready_q.pop(0)
                n = self.nodes[nid]
                if n.state != NodeState.READY:
                    continue
                if n.kind == NodeKind.COORDINATION:
                    n.state = NodeState.DONE
                    self._scatter(nid)
                else:
                    n.state = NodeState.OUTSTANDING
                    dispatched.append(n)
                    self.live_tasks = min(self.live_tasks + 1, 512)
                self.stats_dispatch += 1
        return dispatched

    def complete_node(self, session_id: str, nid: int) -> None:
        with timed(Category.ORCH_DISPATCH, session_id):
            n = self.nodes[nid]
            if n.state != NodeState.OUTSTANDING:
                return
            n.state = NodeState.DONE
            self.live_tasks = max(0, self.live_tasks - 1)
            self._scatter(nid)
            self.stats_dispatch += 1
