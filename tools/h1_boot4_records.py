"""Write the d482c621 addendum keys and the boot-4 pre-registrations. No model calls.

Runners must not import this module. It names the prereg files on purpose.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.h1_conformance import audit  # noqa: E402

RUN = ROOT / "derived" / "h1_hybrid" / "interleaved_d482c621-4292-4281-b6a1-8635e5eeb6da"
ADDENDUM = (
    ROOT
    / "derived"
    / "h1_hybrid"
    / "analysis_d482c621"
    / "closeout"
    / "PROVENANCE_ADDENDUM.json"
)


def _cloud_totals() -> dict[str, Any]:
    by_policy: dict[str, dict[str, float | int]] = {}
    total = 0.0
    n_cloud = 0
    for policy in ("slo_escalate", "emission_escalate", "full_signal_bounceback"):
        doc = json.loads((RUN / "policies" / policy / "turn_ledger.json").read_text(encoding="utf-8"))
        usd = 0.0
        n = 0
        for entry in doc.get("entries") or []:
            for turn in entry.get("turns") or []:
                if turn.get("placement") == "cloud":
                    usd += float(turn.get("cloud_usd") or 0.0)
                    n += 1
        by_policy[policy] = {"cloud_usd": usd, "n_cloud_turns": n}
        total += usd
        n_cloud += n
    return {
        "by_policy": by_policy,
        "cloud_usd_total": total,
        "n_cloud_turns": n_cloud,
        "mean_cloud_usd": (total / n_cloud) if n_cloud else None,
    }


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    costs = _cloud_totals()
    mean = float(costs["mean_cloud_usd"])
    v1_expected = 64.82314053260804
    slo_turns = 732
    cloud_only_cost = slo_turns * mean
    verdict = audit(RUN)
    addendum = json.loads(ADDENDUM.read_text(encoding="utf-8"))
    addendum["policy_conformance"] = {
        "verdict": (
            f"{verdict['n_conforming']}/{verdict['n']} turns match decide_* "
            "against sealed placement. All nonconforming rows are "
            "full_signal_bounceback cloud turns whose sealed signals no longer "
            "show the local trigger."
        ),
        **verdict,
    }
    addendum["quality_reconciliation"] = {
        "q8b_run_id": "72d270e2-1a87-40b6-860a-fb709ffcbe22",
        "q8b_int4_4b_trajectory_pass": "10/200",
        "h1_run_id": "d482c621-4292-4281-b6a1-8635e5eeb6da",
        "h1_slo_escalate_n_local_pass": "21/200",
        "why": (
            "These are different populations. q8b _quality_row sets trajectory_pass "
            "from score.valid on every entry, run fully local, KV_EXPECTED f16, "
            "pipeline_mode block_interleave_single_pipe. d482c621 attach_entry_quality "
            "copies the local probe score into local_pass and then forces local_pass "
            "False when any turn has placement cloud or escalated. The 21 counts "
            "entries that never escalated and passed the checker, on kv u8, RESIDENT, "
            "turn-wise MultiTurnAgentSession. The checker valid bit is the same family. "
            "The harness, KV pin, pipeline mode, and the escalation zeroing are not."
        ),
        "code": {
            "q8b_kv": "tools/run_q_8b_quality.py KV_EXPECTED = f16",
            "q8b_pipeline": "tools/run_q_8b_quality.py pipeline_mode = block_interleave_single_pipe",
            "q8b_score": "tools/run_q_8b_quality.py _quality_row trajectory_pass = bool(score.valid)",
            "h1_zero": (
                "tools/run_h1_hybrid.py attach_entry_quality: if _entry_escalated "
                "(placement cloud or escalated): local_pass = False"
            ),
            "h1_arm": "d482c621 policy summary arm_config kv u8, residency RESIDENT, placement gpu_only",
        },
    }
    _write(ADDENDUM, addendum)

    common = {
        "registered_before_any_cell": True,
        "measurement_status": "not_started",
        "runner_must_not_read_this_file": True,
    }
    _write(
        ROOT / "derived" / "delta_prefill" / "WARM_KV_PREREG.json",
        {
            "id": "WARM-KV",
            **common,
            "model": "Qwen3-4B-int4-ov",
            "placement": "GPU",
            "residency": "RESIDENT",
            "arms": ["gpu_only_f16", "gpu_only_u8", "gpu_only_u4"],
            "endpoint": "turn-2 delta-prefill TTFT limit",
            "prediction": "f16 > u8 >= u4 on turn-2 delta-prefill TTFT. f16 advantage 15-27 percent.",
            "source_run_id": "41e419bd-f3e9-43b1-8364-0ebd89fa086b",
            "derivation": (
                "Sealed 41e419bd Finding 2. That ordering is for turn-2 delta prefill. "
                "It is not a turn-1 bulk-prefill claim."
            ),
        },
    )
    _write(
        ROOT / "derived" / "c2_ttft" / "DECODE_MATCH_PREREG.json",
        {
            "id": "DECODE-MATCH",
            **common,
            "model_pair": ["Qwen3-4B-int4-ov", "Qwen3-4B-int8-ov"],
            "kv": "u8",
            "placement": "GPU",
            "n": [2000, 4000, 8000],
            "endpoint": "decode tok/s at identical n",
            "prediction": "int8 decode tok/s is 20-30 percent below int4 at each listed n.",
            "derivation": (
                "No sealed int4/int8 pair has a decode rate at n=2000, 4000, or 8000. "
                "The only shared rung of c2246b1f and a427233b is n=10500, and int8 "
                "has no decode there (memory_wall). This prediction is not a ratio "
                "computed from those tables."
            ),
        },
    )
    _write(
        ROOT / "derived" / "q8b" / "Q_TIER_CLEAN_PREREG.json",
        {
            "id": "Q-TIER-CLEAN",
            **common,
            "design": "q8b under the current sealer",
            "source_run_id": "72d270e2-1a87-40b6-860a-fb709ffcbe22",
            "source_seal": "MISMATCH",
            "prediction": "int4_8B trajectory passes about 29/200. int4_4B about 10/200. 8B passes more entries than 4B.",
            "derivation": "Unsealed Q8B_RESULTS.md headlines for that run. Not a sealed tree hash.",
        },
    )
    _write(
        ROOT / "derived" / "q_kv" / "Q_KV_CLEAN_PREREG.json",
        {
            "id": "Q-KV-CLEAN",
            **common,
            "design": "q_kv under the current sealer",
            "source_run_id": "137f6f46-cd3a-42d5-8479-4ff46a1074f1",
            "source_seal": "MISMATCH",
            "prediction": "gpu_only_f16, gpu_only_u8, and gpu_only_u4 trajectory passes stay within 3 of each other.",
            "unsealed_trajectory_pass": {"gpu_only_f16": "10/200", "gpu_only_u8": "13/200", "gpu_only_u4": "11/200"},
            "derivation": (
                "Unsealed Q_KV_RESULTS.md. The repro gap on q_repro_6dd387aa is "
                "trajectory 14/200 versus 11/200, a span of 3. The KV arms sit inside that span."
            ),
        },
    )
    _write(
        ROOT / "derived" / "h1_hybrid" / "H1_CPU_PREREG.json",
        {
            "id": "H1-CPU",
            **common,
            "policies": ["slo_escalate", "emission_escalate", "full_signal_bounceback", "local_only"],
            "placement": "CPU",
            "source_run_id": "d482c621-4292-4281-b6a1-8635e5eeb6da",
            "source_cloud_usd_total": costs["cloud_usd_total"],
            "source_mean_cloud_usd": mean,
            "source_by_policy": costs["by_policy"],
            "source_v1_expected_usd": v1_expected,
            "prediction_cost": (
                f"Three-policy cloud cost above the sealed GPU spend {costs['cloud_usd_total']} USD "
                f"and below the cloud-only prediction {cloud_only_cost} USD. local_only cloud cost 0."
            ),
            "prediction_pass": (
                "local_only scores every entry. Predict trajectory passes near the "
                "full-local 4B figure 10/200 (q8b_72d270e2), not the 21/200 "
                "slo_escalate local_pass count. That 21/200 already drops every escalated entry."
            ),
            "derivation": (
                "d482c621 sealed cloud_usd summed over placement cloud is the GPU spend. "
                "The cloud-only figure prices every slo turn at that mean. CPU prefill "
                "crosses the 10 s SLO at a much smaller n than GPU (7f232f86 limit 468 "
                "versus the GPU u8 ceiling), so slo_escalate sends more turns to cloud "
                "and the session cost sits between those two anchors. local_only never "
                "escalates, so its cloud cost is 0 and its pass count is a full-local score."
            ),
        },
    )
    _write(
        ROOT / "derived" / "h1_hybrid" / "R0_CLOUD_ONLY_PREREG.json",
        {
            "id": "R0",
            **common,
            "policy": "cloud_only",
            "source_run_id": "d482c621-4292-4281-b6a1-8635e5eeb6da",
            "source_mean_cloud_usd": mean,
            "source_n_slo_turns": slo_turns,
            "predicted_cloud_usd": cloud_only_cost,
            "prediction_pass": "Cloud replacement of the local trajectory. Pass count is not the 21/200 local-only figure.",
            "derivation": (
                f"predicted_cloud_usd = N_slo turns ({slo_turns}) * mean sealed cloud_usd "
                f"({mean}). N_slo is every slo_escalate turn, local and cloud. "
                "The mean is the pooled cloud turns of the three GPU policies."
            ),
        },
    )
    _write(
        ROOT / "derived" / "h1_hybrid" / "CACHE_ARM_PREREG.json",
        {
            "id": "CACHE",
            **common,
            "policies": ["slo_escalate", "emission_escalate", "full_signal_bounceback"],
            "caching_policy": "on",
            "source_run_id": "d482c621-4292-4281-b6a1-8635e5eeb6da",
            "source_cloud_usd_total": costs["cloud_usd_total"],
            "prediction_cost": f"Below the no-cache sealed total {costs['cloud_usd_total']} USD.",
            "prediction_pass": "Same pass counts as d482c621. Cache does not change the greedy decode.",
            "derivation": (
                "Anchor is the sealed three-policy cloud_usd total with caching off. "
                "Prompt caching bills repeated prefixes as cache reads. The sealed "
                "request records did not store a model id or a cache split that can "
                "support a tighter subtraction, so the prediction is the direction."
            ),
        },
    )
    _write(
        ROOT / "derived" / "h1_hybrid" / "LOCAL_QUALITY_PREREG.json",
        {
            "id": "LOCAL-QUALITY",
            **common,
            "policy": "local_only",
            "model": "Qwen3-4B-int4-ov",
            "placement": "GPU",
            "levers": {
                "cache_on_vs_off": "TTFT down with cache on. Pass count unchanged.",
                "check_and_retry": "Pass count up. A second sample can repair a missing tool call.",
                "best_of_3": "Pass count up. Three samples dominate one.",
                "thinking_on": "Latency up. Pass count down. Think tokens compete with the tool call under max_new_tokens.",
            },
            "anchor_full_local_trajectory_pass": "10/200",
            "anchor_run_id": "72d270e2-1a87-40b6-860a-fb709ffcbe22",
            "derivation": (
                "Directions only. The anchor is the full-local 4B trajectory count, "
                "because local_only scores every entry. Cache does not change greedy "
                "tokens. Retry and best-of-3 add samples. Thinking was off in "
                "d482c621 via render_bfcl_tools_style enable_thinking=False."
            ),
        },
    )
    print("addendum_nonconforming", verdict["n_nonconforming"])
    print("cloud_only_predicted_usd", cloud_only_cost)
    print("cloud_usd_total", costs["cloud_usd_total"])


if __name__ == "__main__":
    main()
