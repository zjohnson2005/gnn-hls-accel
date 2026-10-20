"""Task AY part 5: u4 vs i8 (arm A default) local_only, XPS. Sealed or committed data only.

P8 silent-failure share uses tools/aq_sealed_analyses.classify_local, the same
code as tools/demo2_pilot_analysis.py p8. Per-turn timing is a DERIVED preview
for P2: pairs step 0 of each (entry, turn) whose prompt token count is equal in
both runs, so the two runs saw the same prompt length.

Run from the repo root: python analysis/demo2_pilots/AY/u4_vs_i8.py > u4_vs_i8.json
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tools import aq_sealed_analyses as aq  # noqa: E402

H = ROOT / "derived" / "h1_hybrid"
PAIRS = {
    "BASE_30": {
        "i8": ("39c1c131-f09b-4357-bde3-f39e36947300", H / "interleaved_39c1c131-f09b-4357-bde3-f39e36947300"),
        "u4": ("1f3a261a-b28f-4e87-b3bf-aa8ccca6c3f1", H / "interleaved_1f3a261a-b28f-4e87-b3bf-aa8ccca6c3f1"),
    },
    "LONGCTX_1_14": {
        "i8": (
            "841b84e4-0eb8-436d-89f6-c5b558848991 (UNSEALED partial, first 14)",
            ROOT
            / "derived/demo2_pilots/hung_841b84e4/interleaved_841b84e4-0eb8-436d-89f6-c5b558848991",
        ),
        "u4": ("162a9b5c-1e43-4e43-a315-f1c84135cb37", H / "interleaved_162a9b5c-1e43-4e43-a315-f1c84135cb37"),
    },
}


def _ledger(run: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = json.loads(
        (run / "policies/local_only/turn_ledger.json").read_text(encoding="utf-8")
    )["entries"]
    return rows


def _quality(run: Path) -> dict[str, Any]:
    rows = json.loads((run / "policies/local_only/entry_quality.json").read_text(encoding="utf-8"))
    return {str(r["entry_id"]): r for r in rows["entries"]}


def _telemetry(run: Path) -> list[dict[str, Any]]:
    text = (run / "local_turn_telemetry.jsonl").read_text(encoding="utf-8")
    return [json.loads(x) for x in text.splitlines() if x.strip()]


def _med(xs: list[float]) -> float | None:
    return round(statistics.median(xs), 4) if xs else None


def compare(pair: dict[str, Any]) -> dict[str, Any]:
    a8, a4 = aq.per_entry(_ledger(pair["i8"][1])), aq.per_entry(_ledger(pair["u4"][1]))
    ids = sorted(set(a8) & set(a4))
    c8 = {i: aq.classify_local(a8[i]) for i in ids}
    c4 = {i: aq.classify_local(a4[i]) for i in ids}

    def counts(c: dict[str, str]) -> dict[str, int]:
        out: dict[str, int] = {}
        for v in c.values():
            out[v] = out.get(v, 0) + 1
        return dict(sorted(out.items()))

    q8, q4 = _quality(pair["i8"][1]), _quality(pair["u4"][1])
    pass8 = sorted(i for i in ids if q8.get(i, {}).get("local_pass") is True)
    pass4 = sorted(i for i in ids if q4.get(i, {}).get("local_pass") is True)

    t8 = {(r["entry_id"], r["turn"]): r for r in _telemetry(pair["i8"][1])}
    t4 = {(r["entry_id"], r["turn"]): r for r in _telemetry(pair["u4"][1])}
    ttft_ratio: list[float] = []
    dec_ratio: list[float] = []
    by_bucket: dict[str, dict[str, list[float]]] = {}
    for key in sorted(set(t8) & set(t4)):
        r8, r4 = t8[key], t4[key]
        if r8.get("prompt_tokens") != r4.get("prompt_tokens"):
            continue
        s8, s4 = (r8.get("steps") or [{}])[0], (r4.get("steps") or [{}])[0]
        if not s8.get("ttft_s") or not s4.get("ttft_s"):
            continue
        ttft_ratio.append(float(s4["ttft_s"]) / float(s8["ttft_s"]))
        b = "<8k" if int(r8["prompt_tokens"]) < 8000 else ">=8k"
        slot = by_bucket.setdefault(b, {"ttft_i8": [], "ttft_u4": [], "dec_i8": [], "dec_u4": []})
        slot["ttft_i8"].append(float(s8["ttft_s"]))
        slot["ttft_u4"].append(float(s4["ttft_s"]))
        g8, g4 = int(s8.get("generated_tokens") or 0), int(s4.get("generated_tokens") or 0)
        if g8 >= 16 and g4 >= 16 and s8.get("decode_tok_s") and s4.get("decode_tok_s"):
            dec_ratio.append(float(s4["decode_tok_s"]) / float(s8["decode_tok_s"]))
            slot["dec_i8"].append(float(s8["decode_tok_s"]))
            slot["dec_u4"].append(float(s4["decode_tok_s"]))

    def all_decode(run: Path) -> list[float]:
        return [
            float(s["decode_tok_s"])
            for r in _telemetry(run)
            for s in r.get("steps") or []
            if s.get("decode_tok_s") and int(s.get("generated_tokens") or 0) >= 16
        ]

    non8 = [v for v in c8.values() if v != "escalated"]
    non4 = [v for v in c4.values() if v != "escalated"]
    return {
        "run_ids": {"i8": pair["i8"][0], "u4": pair["u4"][0]},
        "n_paired_entries": len(ids),
        "class_counts": {"i8": counts(c8), "u4": counts(c4)},
        "silent_non_escalated": {
            "i8": [non8.count("silent"), len(non8)],
            "u4": [non4.count("silent"), len(non4)],
        },
        "class_differs": {i: {"i8": c8[i], "u4": c4[i]} for i in ids if c8[i] != c4[i]},
        "local_pass": {"i8": [len(pass8), len(ids), pass8], "u4": [len(pass4), len(ids), pass4]},
        "timing_preview_DERIVED": {
            "n_step0_pairs_same_prompt": len(ttft_ratio),
            "median_ttft_ratio_u4_over_i8": _med(ttft_ratio),
            "n_decode_pairs_ge16_tokens": len(dec_ratio),
            "median_decode_ratio_u4_over_i8": _med(dec_ratio),
            "by_prompt_bucket": {
                b: {
                    "n_ttft": len(v["ttft_i8"]),
                    "median_ttft_s": {"i8": _med(v["ttft_i8"]), "u4": _med(v["ttft_u4"])},
                    "n_decode": len(v["dec_i8"]),
                    "median_decode_tok_s": {"i8": _med(v["dec_i8"]), "u4": _med(v["dec_u4"])},
                }
                for b, v in sorted(by_bucket.items())
            },
            "all_steps_median_decode_tok_s_ge16": {
                "i8": _med(all_decode(pair["i8"][1])),
                "u4": _med(all_decode(pair["u4"][1])),
            },
        },
    }


def main() -> None:
    out = {k: compare(v) for k, v in PAIRS.items()}
    s8 = sum(v["silent_non_escalated"]["i8"][0] for v in out.values())
    n8 = sum(v["silent_non_escalated"]["i8"][1] for v in out.values())
    s4 = sum(v["silent_non_escalated"]["u4"][0] for v in out.values())
    n4 = sum(v["silent_non_escalated"]["u4"][1] for v in out.values())
    out["P8_pooled_so_far"] = {
        "silent_share_i8": [s8, n8, round(s8 / n8, 4) if n8 else None],
        "silent_share_u4": [s4, n4, round(s4 / n4, 4) if n4 else None],
        "keep_u4_rule_on_data_so_far": (s4 / n4) <= (s8 / n8) if n4 and n8 else None,
        "missing": "LONGCTX_30 entries 15-30 on both sides (i8 needs window 2; u4 not scheduled)",
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
