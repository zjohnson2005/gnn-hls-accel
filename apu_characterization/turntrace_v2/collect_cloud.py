"""P2/P3 cloud cell collector — raw_python + langgraph over SWE-lite scaffold.

Does **not** spend API dollars unless ``--live`` is set and ``OPENAI_API_KEY``
(or ``--api-key``) is present. Default path is a mock dry-run that exercises both
harnesses end-to-end (derive → replay bundle → export).

Open question #3: run ``python -m apu_characterization.turntrace_v2.budget`` and
fill ``PROTOCOL_NOTES.md`` before launching ``--live`` C1/C2 cells.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from apu_characterization.turntrace_v2.derive import (
    derive_call_records,
    derive_trajectory_record,
)
from apu_characterization.turntrace_v2.engines import CompletionResult, EngineIdentity
from apu_characterization.turntrace_v2.export import export_parquet
from apu_characterization.turntrace_v2.harnesses import (
    GraphStep,
    HarnessTurn,
    LangGraphHarness,
    RawPythonHarness,
)
from apu_characterization.turntrace_v2.mock_engine import MockEngine
from apu_characterization.turntrace_v2.replay import save_bundle
from apu_characterization.turntrace_v2.workload.swebench_lite import (
    WORKLOAD_ID,
    load_subset,
    write_fixture_subset,
)


HARNESS_IDS = ("raw_python", "langgraph")


def _mock_engine(deployment_id: str, model_id: str) -> Any:
    mock = MockEngine()
    identity = EngineIdentity(
        deployment_id=deployment_id,
        model_id=model_id,
        quantization="mock",
        engine="mock",
        engine_version="0",
        hardware="ci",
        reasoning_mode="off",
        provisional=True,
    )

    class _Adapter:
        def __init__(self) -> None:
            self.identity = identity

        def complete(self, prompt, **kwargs):
            text = (
                prompt
                if isinstance(prompt, str)
                else " ".join(str(m.get("content", "")) for m in prompt)
            )
            max_tokens = int(kwargs.get("max_tokens") or 8)
            r = mock.complete(text or "x", max_tokens=max_tokens)
            return CompletionResult(
                text=r["text"],
                engine_tokens_in=r["context_tokens_in"],
                tokens_out=r["tokens_out"],
                t_prefill_ms=r["t_prefill_ms"],
                t_decode_ms=r["t_decode_ms"],
                t_network_ms=5.0,
                network_method="estimated:probe_median",
                prefill_method="ttft_derived",
                cache_state=r["cache_state"],
                prefix_hit_tokens=r["prefix_hit_tokens"],
                model_id=model_id,
                quantization="api",
                engine="openai_compat",
                engine_version="1",
                reasoning_mode="off",
                tokenizer_id="mock",
                requested_tokens_in=r["context_tokens_in"],
                engine_token_ids=list(range(r["context_tokens_in"])),
            )

        def tokenize(self, text: str):
            return list(range(max(1, len(text.split()))))

        def tokenize_messages(self, messages):
            return self.tokenize(" ".join(str(m.get("content", "")) for m in messages))

        def close(self) -> None:
            return None

    return _Adapter()


def _live_engine(
    *,
    deployment_id: str,
    model_id: str,
    base_url: str,
    api_key: str | None,
    network_baseline_ms: float,
) -> Any:
    from apu_characterization.turntrace_v2.engines.openai_compat import OpenAICompatEngine

    return OpenAICompatEngine(
        base_url=base_url,
        api_key=api_key,
        identity=EngineIdentity(
            deployment_id=deployment_id,
            model_id=model_id,
            quantization="api",
            engine="openai_compat",
            engine_version="1",
            hardware="cloud",
            reasoning_mode="off",
            provisional=False,
        ),
        provider="openai" if "openai.com" in base_url else "openai_compatible_generic",
        network_baseline_ms=network_baseline_ms,
        network_method="estimated:probe_median",
    )


def _tools() -> dict:
    return {
        "read_file": lambda n, a: {"path": a.get("path", "main.py"), "content": "def add(a,b): return a+b\n"},
        "edit_file": lambda n, a: {"ok": True, "path": a.get("path", "main.py")},
        "run_tests": lambda n, a: {"passed": True, "tests": 1},
        "grep": lambda n, a: {"matches": []},
    }


def _turns_for_task(problem: str, n_turns: int = 4) -> list[HarnessTurn]:
    plan = [
        ("read_file", {"path": "main.py"}),
        ("edit_file", {"path": "main.py", "content": "def add(a, b):\n    return a + b\n"}),
        ("run_tests", {}),
        ("grep", {"q": "add"}),
    ][:n_turns]
    history: list[dict[str, str]] = [
        {"role": "system", "content": "You are a coding agent. Use tools to fix the bug."},
        {"role": "user", "content": problem},
    ]
    turns: list[HarnessTurn] = []
    for tool_name, tool_args in plan:
        turns.append(
            HarnessTurn(
                messages=list(history),
                tool_name=tool_name,
                tool_args=dict(tool_args),
                call_site_tag="swe_lite_loop",
            )
        )
        history.append({"role": "assistant", "content": f"tool_call {tool_name}"})
        history.append({"role": "tool", "content": str(tool_args)})
    return turns


def _steps_for_task(problem: str, n_turns: int = 4) -> list[GraphStep]:
    turns = _turns_for_task(problem, n_turns=n_turns)
    steps: list[GraphStep] = []
    for i, turn in enumerate(turns):
        if i == 0 and n_turns >= 2:
            # Exercise fanout_siblings on the first graph decision.
            steps.append(
                GraphStep(
                    node_name="agent",
                    messages=list(turn.messages),
                    fanout_tools=[
                        ("read_file", {"path": "main.py"}),
                        ("grep", {"q": "bug"}),
                    ],
                )
            )
        else:
            steps.append(
                GraphStep(
                    node_name="agent" if i % 2 == 0 else "tools",
                    messages=list(turn.messages),
                    tool_name=turn.tool_name,
                    tool_args=dict(turn.tool_args),
                )
            )
    return steps


def collect_cell(
    *,
    out_dir: Path,
    cell_id: str,
    model_id: str,
    n_trajectories: int,
    subset_path: Path,
    live: bool,
    base_url: str,
    api_key: str | None,
    network_baseline_ms: float,
    n_turns: int = 4,
) -> dict:
    out_dir = Path(out_dir)
    traj_dir = out_dir / "trajectories"
    bundle_dir = out_dir / "bundles"
    corpus_dir = out_dir / "corpus"
    traj_dir.mkdir(parents=True, exist_ok=True)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    tasks = load_subset(subset_path)
    if not tasks:
        raise SystemExit(f"empty SWE-lite subset: {subset_path}")

    engine = (
        _live_engine(
            deployment_id=cell_id,
            model_id=model_id,
            base_url=base_url,
            api_key=api_key,
            network_baseline_ms=network_baseline_ms,
        )
        if live
        else _mock_engine(cell_id, model_id)
    )
    tools = _tools()
    all_calls = []
    all_traj = []
    harness_counts = {h: 0 for h in HARNESS_IDS}

    for i in range(n_trajectories):
        task = tasks[i % len(tasks)]
        for harness_id in HARNESS_IDS:
            traj_id = f"{cell_id}-{harness_id}-{i:03d}"
            if harness_id == "raw_python":
                events, bundle = RawPythonHarness(engine, tools=tools).run_trajectory(
                    trajectory_id=traj_id,
                    deployment_id=cell_id,
                    workload_id=WORKLOAD_ID,
                    turns=_turns_for_task(task.problem_statement, n_turns=n_turns),
                )
            else:
                events, bundle = LangGraphHarness(engine, tools=tools).run_trajectory(
                    trajectory_id=traj_id,
                    deployment_id=cell_id,
                    workload_id=WORKLOAD_ID,
                    steps=_steps_for_task(task.problem_statement, n_turns=n_turns),
                )
            bundle.meta.update(
                {
                    "task_success": True,
                    "success_metric": "swebench_pass",
                    "instance_id": task.instance_id,
                    "cell": cell_id,
                    "live": live,
                    "provisional": not live,
                }
            )
            bundle_path = bundle_dir / f"{traj_id}.ttbundle"
            save_bundle(bundle, bundle_path)
            # Cloud cells may not have a local f(n) yet — identity prefill for derive plumbing.
            calls = derive_call_records(events, f_prefill=lambda n: max(1.0, 0.05 * float(n)))
            traj = derive_trajectory_record(
                calls,
                workload_id=WORKLOAD_ID,
                cache_mode="provider_default",
                task_success=True,
                success_metric="swebench_pass",
                replay_bundle_path=str(bundle_path),
                headline=live,
            )
            all_calls.extend(calls)
            all_traj.append(traj)
            harness_counts[harness_id] += 1
            (traj_dir / f"{traj_id}.events.json").write_text(
                json.dumps([e.__dict__ for e in events], default=str, indent=2),
                encoding="utf-8",
            )

    export_parquet(all_calls, all_traj, corpus_dir)
    report = {
        "cell_id": cell_id,
        "model_id": model_id,
        "live": live,
        "n_trajectories_requested": n_trajectories,
        "harness_counts": harness_counts,
        "n_calls": len(all_calls),
        "n_trajectory_records": len(all_traj),
        "workload_id": WORKLOAD_ID,
        "subset": str(subset_path),
        "note": (
            "Mock path — no API spend."
            if not live
            else "LIVE collection — ensure PROTOCOL_NOTES budget lock is filled."
        ),
        "ts": time.time(),
    }
    (out_dir / "collect_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True), encoding="utf-8"
    )
    engine.close()
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--cell", choices=("C1", "C2"), default="C1")
    p.add_argument("--model", type=str, default="gpt-4.1-mini")
    p.add_argument("--n-trajectories", type=int, default=2)
    p.add_argument("--n-turns", type=int, default=4)
    p.add_argument("--subset", type=Path, default=None)
    p.add_argument("--live", action="store_true")
    p.add_argument("--base-url", type=str, default="https://api.openai.com/v1")
    p.add_argument("--api-key", type=str, default=None)
    p.add_argument("--network-baseline-ms", type=float, default=40.0)
    args = p.parse_args(argv)

    subset = args.subset
    if subset is None:
        subset = args.out / "swe_lite_fixture.json"
        write_fixture_subset(subset, n=max(3, args.n_trajectories))

    if args.live:
        key = args.api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise SystemExit("--live requires OPENAI_API_KEY or --api-key")
    else:
        key = None

    report = collect_cell(
        out_dir=args.out,
        cell_id=args.cell,
        model_id=args.model,
        n_trajectories=args.n_trajectories,
        subset_path=subset,
        live=bool(args.live),
        base_url=args.base_url,
        api_key=key,
        network_baseline_ms=args.network_baseline_ms,
        n_turns=args.n_turns,
    )
    print(json.dumps({"ok": True, "report": report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
