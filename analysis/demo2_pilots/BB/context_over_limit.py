"""Task BB part 2: local generates with prompts above Qwen3-4B's 40,960 positions.

Mac only, no model. Committed data only.

Runs with local_turn_telemetry.jsonl and per-step raw text (--debug-raw-text):
every turn is replayed through the runner's own render path
(MultiTurnAgentSession + render_bfcl_tools_style, pinned HF tokenizer) with a
stub pipeline that returns the recorded step texts in order. Tool calls run
in the BFCL executor as in the run, so the per-step prompt is rebuilt
exactly. The replay is checked against what the run recorded: the step-0
prompt of every turn (prompt_tokens) must match, else the entry is marked
replay_mismatch and only the recorded step-0 values are used.

Runs without per-step raw text: the recorded step-0 prompt of each turn only
(a lower bound for the turn's later steps).

Runs with step_log.jsonl (8af10211): the logged pre-generate prompt tokens.

Run from the repo root:
  python analysis/demo2_pilots/BB/context_over_limit.py --tokenizer <dir> \\
      --bfcl-unpacked <dir> > analysis/demo2_pilots/BB/context_over_limit.json
"""

from __future__ import annotations

import argparse
import json
import sys
import types
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

MODEL_MAX = 40_960
QWEN3_NATIVE = 32_768
L2_STEP_LOG = (
    "derived/demo2_pilots/p11_l2_8af10211/"
    "interleaved_8af10211-c517-4fe5-9281-42800edf0278/step_log.jsonl"
)


def _plan(d: Path) -> dict[str, Any]:
    for c in (d, d.parent, d.parent.parent):
        if (c / "plan.json").is_file():
            return dict(json.loads((c / "plan.json").read_text(encoding="utf-8")))
    return {}


def _rows(d: Path) -> list[dict[str, Any]]:
    text = (d / "local_turn_telemetry.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _quality(d: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for p in sorted(d.glob("policies/*/turn_ledger.json")):
        for e in json.loads(p.read_text(encoding="utf-8")).get("entries") or []:
            out[str(e["entry_id"])] = {
                "local_pass": e.get("local_pass"),
                "stop_reason": e.get("stop_reason"),
                "status": e.get("status"),
            }
    return out


class Replayer:
    def __init__(self, tok: Any, bfcl: Path) -> None:
        if "openvino_genai" not in sys.modules:
            sys.modules["openvino_genai"] = types.ModuleType("openvino_genai")
        import tools.bfcl_feasibility_probe as probe
        import tools.h1_context_sizing as hs

        probe.BFCL_UNPACKED = bfcl
        self.probe, self.hs, self.tok = probe, hs, tok
        data = bfcl / "bfcl_eval" / "data"
        self.entries: dict[str, dict[str, Any]] = {}
        for cat in ("multi_turn_base", "multi_turn_long_context"):
            for e in hs.load_entries(cat, data):
                self.entries[str(e["id"])] = e

    def entry(self, eid: str, turns: list[dict[str, Any]]) -> dict[str, Any]:
        """Per-step prompt tokens for the recorded turns of one entry."""
        probe, hs = self.probe, self.hs
        s = probe.MultiTurnAgentSession(pipe=hs.GoldPipe(), tokenizer=self.tok, cfg=None)
        s.begin(self.entries[eid])
        steps: list[dict[str, Any]] = []
        ok = True
        try:
            for row in turns:
                t = int(row["turn"])
                texts = [str(st.get("raw_text", "")) for st in row.get("steps") or []]
                s.pipe.queue = list(texts)
                n0 = len(s.prompt_token_samples)
                s.run_user_turn(t)
                got = s.prompt_token_samples[n0:]
                if not got or got[0] != int(row["prompt_tokens"]) or len(got) < len(texts):
                    ok = False
                    break
                for i, st in enumerate(row.get("steps") or []):
                    steps.append(
                        {
                            "turn": t,
                            "step": int(st.get("step", i)),
                            "prompt_tokens": got[i],
                            "generated_tokens": st.get("generated_tokens"),
                            "wall_s": st.get("wall_s"),
                            "ttft_s": st.get("ttft_s"),
                        }
                    )
                if s.force_quit:
                    break
        finally:
            s._finished = True
        return {"ok": ok, "steps": steps}


def telemetry_run(d: Path, rep: Replayer | None) -> dict[str, Any]:
    plan = _plan(d)
    rows = [r for r in _rows(d) if r.get("policy", "local_only") == "local_only"]
    qual = _quality(d)
    by_entry: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_entry.setdefault(str(r["entry_id"]), []).append(r)
    has_raw = all("raw_text" in st for r in rows for st in r.get("steps") or [])
    entries = []
    for eid, turns in by_entry.items():
        turns.sort(key=lambda r: int(r["turn"]))
        rec: dict[str, Any] = {
            "entry_id": eid,
            "n_turns_recorded": len(turns),
            "max_step0_prompt": max(int(r["prompt_tokens"]) for r in turns),
            **qual.get(eid, {}),
        }
        if has_raw and rep is not None:
            res = rep.entry(eid, turns)
            rec["method"] = "replay" if res["ok"] else "replay_mismatch_step0_only"
            if res["ok"]:
                st = res["steps"]
                rec["n_steps"] = len(st)
                rec["max_prompt"] = max(x["prompt_tokens"] for x in st)
                big = [x for x in st if x["prompt_tokens"] > MODEL_MAX]
                rec["n_steps_over_40960"] = len(big)
                rec["n_steps_over_32768"] = sum(
                    1 for x in st if x["prompt_tokens"] > QWEN3_NATIVE
                )
                rec["steps_over_40960"] = big
        else:
            rec["method"] = "step0_only"
        if rec["method"] != "replay":
            rec["n_step0_over_40960"] = sum(1 for r in turns if r["prompt_tokens"] > MODEL_MAX)
            rec["n_step0_over_32768"] = sum(
                1 for r in turns if r["prompt_tokens"] > QWEN3_NATIVE
            )
        entries.append(rec)
    ov = plan.get("openvino") or {}
    return {
        "dir": str(d.relative_to(ROOT)),
        "run_id": plan.get("run_id"),
        "host": plan.get("platform_id"),
        "entry_pin": (plan.get("entry_pin") or {}).get("name"),
        "kv": ov.get("kv"),
        "residency": plan.get("residency"),
        "context_window": (ov.get("runtime_options") or {}).get("context_window"),
        "seal": (d / ".sealed").exists() or any(d.glob("*.sealed")),
        "has_raw_text": has_raw,
        "entries": entries,
    }


def ledger_run(d: Path) -> dict[str, Any]:
    plan = _plan(d)
    ov = plan.get("openvino") or {}
    out = []
    for e in json.loads((d / "turn_ledger.json").read_text(encoding="utf-8")).get("entries") or []:
        loc = [t for t in e.get("turns") or [] if t.get("placement") == "local"]
        n = [int(t["n_ctx"]) for t in loc if t.get("n_ctx") is not None]
        if not n:
            continue
        out.append(
            {
                "entry_id": e["entry_id"],
                "n_local_turns": len(loc),
                "max_step0_prompt": max(n),
                "n_step0_over_40960": sum(1 for x in n if x > MODEL_MAX),
                "n_step0_over_32768": sum(1 for x in n if x > QWEN3_NATIVE),
                "local_pass": e.get("local_pass"),
                "stop_reason": e.get("stop_reason"),
            }
        )
    return {
        "dir": str(d.relative_to(ROOT)),
        "run_id": plan.get("run_id"),
        "host": plan.get("platform_id"),
        "entry_pin": (plan.get("entry_pin") or {}).get("name"),
        "kv": ov.get("kv"),
        "residency": ov.get("residency") or plan.get("residency"),
        "method": "ledger_step0_only",
        "entries": out,
    }


def step_log_run(path: Path) -> dict[str, Any]:
    rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = [r for r in rows if r.get("event", "pre_generate") == "pre_generate"]
    big = [r for r in rows if int(r["prompt_tokens"]) > MODEL_MAX]
    return {
        "dir": str(path.parent.relative_to(ROOT)),
        "run_id": "8af10211-c517-4fe5-9281-42800edf0278",
        "host": "evo-t2",
        "method": "step_log",
        "n_steps": len(rows),
        "n_steps_over_40960": len(big),
        "n_steps_over_32768": sum(1 for r in rows if int(r["prompt_tokens"]) > QWEN3_NATIVE),
        "max_prompt": max(int(r["prompt_tokens"]) for r in rows),
        "outcome": "turn budget exceeded at turn 0 step 5 (600 s), steps progressing",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokenizer", type=Path, required=True)
    ap.add_argument("--bfcl-unpacked", type=Path, required=True)
    a = ap.parse_args()
    from transformers import AutoTokenizer

    rep = Replayer(AutoTokenizer.from_pretrained(str(a.tokenizer)), a.bfcl_unpacked)
    tele = sorted({p.parent for p in ROOT.glob("derived/**/local_turn_telemetry.jsonl")})
    runs = [telemetry_run(d, rep) for d in tele]
    ledgers = sorted(ROOT.glob("derived/h1_hybrid/*slo_escalate_*"))
    runs += [ledger_run(d) for d in ledgers if (d / "turn_ledger.json").is_file()]
    if (ROOT / L2_STEP_LOG).is_file():
        runs.append(step_log_run(ROOT / L2_STEP_LOG))
    doc = {
        "task": "BB part 2",
        "model_max_position_embeddings": MODEL_MAX,
        "qwen3_native_context": QWEN3_NATIVE,
        "runs": runs,
    }
    print(json.dumps(doc, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
