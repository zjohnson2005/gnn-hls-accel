"""Task AZ part 1: registered pilot rules on the 2026-10-20 XPS window 2 and T2S block.

Sealed or committed data only. Rules as written in
docs/amendments/DEMO2_PILOTS_2026-10-16.md (P2, P4, P6, P8, P9); P4, P8 and P9
call tools/demo2_pilot_analysis.py, P6 and P2 are computed here because the
tool has no rule step for them (P6 prints buckets only; P2 has no subcommand).

Run from the repo root: python analysis/demo2_pilots/AZ/pilots_az.py > analysis/demo2_pilots/AZ/pilots_az.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tools import aq_sealed_analyses as aq  # noqa: E402
from tools import demo2_pilot_analysis as pa  # noqa: E402
from tools import demo2_true_default_predict as pred  # noqa: E402

H = ROOT / "derived" / "h1_hybrid"
DP = ROOT / "derived" / "demo2_pilots"


def run(rid: str) -> Path:
    return H / f"interleaved_{rid}"


RUNS = {
    "xps_i8_base30": "39c1c131-f09b-4357-bde3-f39e36947300",
    "xps_i8_long_1_14": "841b84e4-0eb8-436d-89f6-c5b558848991",
    "xps_i8_long_rest": "15367c3a-5b8d-4be0-9db5-a6538b6e8c56",
    "t2s_i8_base30": "b90f1d5b-6e35-4060-ad72-05e62f22803e",
    "t2s_i8_long_0_13": "1a634610-a762-4710-8bbe-08edd4665067",
    "t2s_i8_long_15_29": "daa6c026-ff57-4b19-a9c9-832dc2a48261",
    "t2s_u4_base30": "6c610aa6-aad4-4b24-a089-1c3a7fce107d",
    "t2s_u4_long_0_13": "3aa565da-d877-464b-8160-c987cc3dee96",
    "t2s_u4_long_15_29": "108d5f43-ed31-4e90-a62b-adaf8dc019b3",
    "t2s_p4_off": "16996cdb-6a1b-4c94-b8f6-4e9cb9f98ec0",
    "t2s_p4_k3": "4d8e2fb1-73d6-4fb9-a017-6933fc347bf8",
    "t2s_p4_k5": "cc32619a-2698-4677-b8ce-e0d08cf8e8d6",
    "t2s_p9": "63b2567a-a999-4d65-aa7b-c5427480f73f",
    "t2s_p2_i8": "29209e26-879e-4b31-9892-9b90c535b856",
    "t2s_p2_u4": "0a55c316-e438-4460-96c2-267e243ae8c9",
}
HANG_123 = {
    "xps": ["841b84e4 (stalled, killed)", "24c1abc0", "027a07b7 (P10 C1)"],
    "t2s": ["bbdd1c0d"],
}


def _dir(key: str) -> Path:
    rid = RUNS[key]
    if key == "xps_i8_long_1_14":
        return DP / "hung_841b84e4" / f"interleaved_{rid}"
    return run(rid)


def _entries(key: str) -> list[dict[str, Any]]:
    return pa._entries(_dir(key))


# --- P6 (registered rule, pilots doc row P6) -------------------------------
A_LIMIT_REGISTERED = 20_000  # "A's limit - 10% (18,000)" in the rule text; cf3555d5
A_LIMIT_P3_CELL0 = 18_000  # a5d19dcc, true default, 2026-10-20 (sensitivity only)
BC_WINDOW_XPS = pred.XPS_B_WINDOW["point"]  # 23,850
CLOUD_PASS = 22 / 30  # V2 1acc8c58
P6_MAX_LOST = 6


def _max_nctx(e: dict[str, Any]) -> int:
    return max((int(t.get("n_ctx") or 0) for t in e.get("turns") or []), default=0)


def p6() -> dict[str, Any]:
    ents = _entries("xps_i8_base30") + _entries("xps_i8_long_1_14") + _entries("xps_i8_long_rest")
    ids = [e["entry_id"] for e in ents]
    assert len(set(ids)) == len(ids) == 59, len(ids)
    rows = [(e["entry_id"], _max_nctx(e), bool(e.get("local_pass"))) for e in ents]

    def band(lo: int) -> dict[str, Any]:
        inb = [r for r in rows if lo < r[1] <= BC_WINDOW_XPS]
        rate = (sum(r[2] for r in inb) / len(inb)) if inb else 0.0
        lost = len(inb) * (CLOUD_PASS - rate)
        return {
            "band": f"({lo}, {BC_WINDOW_XPS}]",
            "n_in_band": len(inb),
            "entries": [r[0] for r in inb],
            "local_pass_in_band": sum(r[2] for r in inb),
            "expected_passes_lost": round(lost, 3),
            "exceeds_6_of_60": lost > P6_MAX_LOST,
        }

    reg = band(A_LIMIT_REGISTERED)
    return {
        "pilot": "P6",
        "runs": [RUNS["xps_i8_base30"], RUNS["xps_i8_long_1_14"], RUNS["xps_i8_long_rest"]],
        "n_entries": 60,
        "entry_123": "local fail, outcome hang (24c1abc0; counted by 15367c3a --skip-entries); "
        "max n_ctx unknown (stalled in turn 0; gold step 1 = 34,050 > 23,850, outside the band)",
        "local_pass_total": sum(r[2] for r in rows),
        "registered": reg,
        "verdict": "SET_WINDOW_18000" if reg["exceeds_6_of_60"] else "NO_CHANGE",
        "sensitivity_not_registered_A_limit_18000_a5d19dcc": band(A_LIMIT_P3_CELL0),
        "n_ctx_over_window": sorted(r[1] for r in rows if r[1] > BC_WINDOW_XPS),
    }


# --- P8 T2S (pooled over BASE_30 + LONGCTX_30, as in Task AY) ---------------
def p8_t2s() -> dict[str, Any]:
    parts = {
        "BASE_30": ("t2s_i8_base30", "t2s_u4_base30"),
        "LONGCTX_0_13": ("t2s_i8_long_0_13", "t2s_u4_long_0_13"),
        "LONGCTX_15_29": ("t2s_i8_long_15_29", "t2s_u4_long_15_29"),
    }
    out: dict[str, Any] = {"pilot": "P8", "host": "T2S", "parts": {}}
    tot = {"i8": [0, 0], "u4": [0, 0]}
    for name, (ki8, ku4) in parts.items():
        a, b = aq.per_entry(_entries(ki8)), aq.per_entry(_entries(ku4))
        ids = sorted(set(a) & set(b))
        part: dict[str, Any] = {"i8_run": RUNS[ki8], "u4_run": RUNS[ku4], "n_paired": len(ids)}
        for kv, d in (("i8", a), ("u4", b)):
            cls = [aq.classify_local(d[i]) for i in ids]
            ne = [c for c in cls if c != "escalated"]
            part[f"silent_{kv}"] = f"{ne.count('silent')}/{len(ne)}"
            part[f"local_pass_{kv}"] = sorted(i for i in ids if aq.classify_local(d[i]) == "pass")
            tot[kv][0] += ne.count("silent")
            tot[kv][1] += len(ne)
        part["tool"] = pa.p8(_dir(ki8), _dir(ku4))
        out["parts"][name] = part
    out["pooled_silent_i8"] = f"{tot['i8'][0]}/{tot['i8'][1]}"
    out["pooled_silent_u4"] = f"{tot['u4'][0]}/{tot['u4'][1]}"
    out["keep_u4"] = tot["u4"][0] / tot["u4"][1] <= tot["i8"][0] / tot["i8"][1]
    out["entry_123"] = "not paired: i8 hung (bbdd1c0d), u4 not run (block stopped)"
    return out


# --- P2 T2S (registered rule; model from tools/demo2_true_default_predict) ---
def _p2_points(rid: str) -> dict[int, float]:
    d = DP / f"sealed_{rid}" / "points"
    return {
        int(p["n"]): float(p["median_decode_tok_s"])
        for p in (json.loads(f.read_text(encoding="utf-8")) for f in sorted(d.glob("*.json")))
    }


def p2_t2s(f16_rid: str | None) -> dict[str, Any]:
    i8 = _p2_points(RUNS["t2s_p2_i8"])
    u4 = _p2_points(RUNS["t2s_p2_u4"])
    kvb = pred.KV_BYTES_PER_TOKEN
    bw = i8[3500] * (pred.WEIGHT_BYTES + 3500 * kvb["i8"])
    model = {n: bw / (pred.WEIGHT_BYTES + n * kvb["i8"]) for n in (12_000, 20_000)}
    dev = {n: (i8[n] - model[n]) / model[n] for n in model}
    gain = u4[12_000] / i8[12_000]
    out: dict[str, Any] = {
        "pilot": "P2",
        "host": "T2S",
        "runs": {"i8": RUNS["t2s_p2_i8"], "u4": RUNS["t2s_p2_u4"], "f16": f16_rid},
        "decode_tok_s_median": {"i8": i8, "u4": u4},
        "model": "tok/s = BW / (W + n * KV bytes/token), W 2.353e9, i8 73,728 B/token "
        "(tools/demo2_true_default_predict.py), BW calibrated on i8 at 3,500",
        "bw_calibrated_gb_s": round(bw / 1e9, 2),
        "model_tok_s": {n: round(v, 3) for n, v in model.items()},
        "deviation": {n: round(v, 4) for n, v in dev.items()},
        "bandwidth_model_holds": all(abs(v) <= 0.15 for v in dev.values()),
        "u4_over_i8_at_12000": round(gain, 4),
        "u4_gain_supported": gain >= 1.05,
        "u4_over_i8": {n: round(u4[n] / i8[n], 4) for n in i8},
    }
    if f16_rid:
        out["decode_tok_s_median"]["f16"] = _p2_points(f16_rid)
    return out


def main() -> int:
    f16 = sys.argv[1] if len(sys.argv) > 1 else None
    res = {
        "task": "AZ",
        "basis": "sealed runs; rules from docs/amendments/DEMO2_PILOTS_2026-10-16.md",
        "P6_xps": p6(),
        "P8_t2s": p8_t2s(),
        "P4_t2s": {
            "K3": pa.p4(_dir("t2s_p4_off"), _dir("t2s_p4_k3")),
            "K5": pa.p4(_dir("t2s_p4_off"), _dir("t2s_p4_k5")),
            "runs": {k: RUNS[f"t2s_p4_{k}"] for k in ("off", "k3", "k5")},
        },
        "P9_t2s": {"run": RUNS["t2s_p9"], **pa.p9(DP / f"sealed_{RUNS['t2s_p9']}")},
        "P2_t2s": p2_t2s(f16),
        "hangs_entry_123": HANG_123,
    }
    print(json.dumps(res, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
