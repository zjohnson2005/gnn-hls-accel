from __future__ import annotations

from apu_characterization.turntrace_v2.engines import EngineIdentity
from apu_characterization.turntrace_v2.harnesses import GraphStep, HarnessTurn, LangGraphHarness, RawPythonHarness
from apu_characterization.turntrace_v2.labeling import label_trajectory
from apu_characterization.turntrace_v2.mock_engine import MockEngine
from apu_characterization.turntrace_v2.engines import CompletionResult
from apu_characterization.turntrace_v2.workload.swebench_lite import write_fixture_subset, load_subset


class _MockEng:
    def __init__(self) -> None:
        self.identity = EngineIdentity(
            "CPU0", "mock", "n/a", "mock", "0", "ci", "off", True
        )
        self._m = MockEngine()

    def complete(self, prompt, **kwargs):
        text = prompt if isinstance(prompt, str) else " ".join(
            m.get("content", "") for m in prompt
        )
        r = self._m.complete(text or "x", max_tokens=4)
        return CompletionResult(
            text=r["text"],
            engine_tokens_in=r["context_tokens_in"],
            tokens_out=r["tokens_out"],
            t_prefill_ms=r["t_prefill_ms"],
            t_decode_ms=r["t_decode_ms"],
            t_network_ms=0.0,
            network_method="measured",
            prefill_method="direct",
            cache_state=r["cache_state"],
            prefix_hit_tokens=r["prefix_hit_tokens"],
            model_id="mock",
            quantization="n/a",
            engine="mock",
            engine_version="0",
            reasoning_mode="off",
            tokenizer_id="whitespace_v0",
            requested_tokens_in=r["context_tokens_in"],
            engine_token_ids=list(range(r["context_tokens_in"])),
        )

    def tokenize(self, text: str):
        return list(range(len(text.split())))

    def tokenize_messages(self, messages):
        text = " ".join(m.get("content", "") for m in messages)
        return self.tokenize(text)
    def close(self):
        return None


def test_raw_python_and_langgraph_fanout() -> None:
    eng = _MockEng()
    raw = RawPythonHarness(eng, tools={"read_file": lambda n, a: {"ok": True}})
    events, bundle = raw.run_trajectory(
        trajectory_id="h1",
        deployment_id="CPU0",
        workload_id="toy",
        turns=[
            HarnessTurn(
                messages=[{"role": "user", "content": "look"}],
                tool_name="read_file",
                tool_args={"path": "a.py"},
            )
        ],
    )
    assert events[0].harness_id == "raw_python"
    assert bundle.turns[0].tool_calls[0].name == "read_file"

    lg = LangGraphHarness(
        eng,
        tools={
            "read_file": lambda n, a: {"ok": 1},
            "grep": lambda n, a: {"ok": 2},
        },
    )
    events2, _ = lg.run_trajectory(
        trajectory_id="h2",
        deployment_id="CPU0",
        workload_id="toy",
        steps=[
            GraphStep(
                node_name="agent",
                messages=[{"role": "user", "content": "search"}],
                fanout_tools=[("read_file", {"p": "a"}), ("grep", {"q": "x"})],
            )
        ],
    )
    assert events2[0].graph_node == "agent"
    assert len(events2[0].tool_names) == 2
    from apu_characterization.turntrace_v2.labeling import RawTurnEvent

    labeled = label_trajectory(
        [
            RawTurnEvent(
                turn_index=0,
                tool_names=events2[0].tool_names,
                graph_node="agent",
                call_site_tag=None,
                expected_horizon=1,
            )
        ]
    )
    assert labeled[0][1].fanout_siblings == 1


def test_swebench_fixture_roundtrip(tmp_path) -> None:
    path = write_fixture_subset(tmp_path / "subset.json", n=2)
    tasks = load_subset(path)
    assert len(tasks) == 2
    assert tasks[0].instance_id.startswith("fixture__")
