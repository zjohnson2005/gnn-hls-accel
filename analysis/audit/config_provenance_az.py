"""Task AZ part 2: configuration provenance of every number we cite.

Reads committed run directories only; changes no number. For each cited number
it records the run_id(s), date, tool, how the pipeline was constructed (from the
run's own spec / plan, cross-checked against the code at its git head where the
plan records one), prefix caching, max_num_batched_tokens, KV requested and
compiled, CACHE_DIR, residency, OpenVINO + GenAI version, GPU driver version at
the time, host, seal status, a class and a recommendation.

Classes (Task AZ prompt):
  TRUE_DEFAULT              LLMPipeline(model, device) with no property and no
                            SchedulerConfig: GenAI's latency scheduler
                            (prefix caching on, max_num_batched_tokens SIZE_MAX).
  PLAIN_PIPELINE_WITH_PROPS the same latency scheduler plus properties
                            (KV_CACHE_PRECISION, CPU pinning, NPU prompt length,
                            prompt_lookup).
  REPLACED_SCHEDULER        a bare SchedulerConfig() (struct defaults) with one
                            field set; it replaces the latency scheduler.
  EXPLICIT                  a full SchedulerConfig whose fields are all given.

Scheduler values: the latency default and the struct defaults are the GenAI
2026.2.1 values read back by P0a (597f40a9 XPS 2026-10-16; T2S 2026-10-20
readback in derived/demo2_pilots/p0a_readback_t2s_20261020/).

Run from the repo root:
  python analysis/audit/config_provenance_az.py > derived/audit/CONFIG_PROVENANCE.json
"""

from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "derived"

LATENCY = {
    "enable_prefix_caching": True,
    "max_num_batched_tokens": "SIZE_MAX (18446744073709551615)",
    "dynamic_split_fuse": True,
    "cache_size": 0,
    "use_cache_eviction": False,
}
STRUCT = {
    "enable_prefix_caching": False,
    "max_num_batched_tokens": 256,
    "max_num_seqs": 256,
    "dynamic_split_fuse": True,
    "cache_size": 0,
    "num_kv_blocks": 0,
    "use_cache_eviction": False,
}
# Compiled KV by request on GPU, OpenVINO 2026.2.1 (P0a readbacks): u8 -> int8.
KV_COMPILED = {None: "i8", "default": "i8", "u8": "i8", "i8": "i8", "u4": "u4", "f16": "f16"}
KV_BASIS = "DERIVED from P0a readback on the same OpenVINO build (597f40a9 XPS, T2S 2026-10-20); not read in this run"

# GPU driver readings (only these exist; everything else is UNKNOWN).
DRIVER_READINGS = {
    "aipc-c1": [
        (
            "2026-07-29",
            "32.0.101.8622",
            "analysis/aipc-c1/reprobe_af002_2026-07-29/drivers_probe.txt",
        ),
        (
            "2026-09-16",
            "32.0.101.8724",
            "2b3316b6 run_environment.gpu_driver_version (manifest.json)",
        ),
        (
            "2026-10-20",
            "32.0.101.8860",
            "~/seam_closeout_1013/xps/window_20261020_1733/drivers.txt (17:33 ET, before the window-2 reboot)",
        ),
    ],
    "evo-t2": [
        (
            "2026-10-20",
            "32.0.101.8509",
            "~/seam_closeout_1013/t2s/window_20261020_1733/a_drivers.txt (Arc B390; NPU 32.0.100.4512)",
        ),
    ],
}


def driver_at(host: str, date: str | None) -> str:
    rows = DRIVER_READINGS.get(host, [])
    if not date:
        return "UNKNOWN (run date not found)"
    for d, v, src in rows:
        if d == date[:10]:
            return f"{v} (read {d}: {src})"
    before = [r for r in rows if r[0] < date[:10]]
    after = [r for r in rows if r[0] > date[:10]]
    b = f"{before[-1][1]} on {before[-1][0]}" if before else "no earlier reading"
    a = f"{after[0][1]} on {after[0][0]}" if after else "no later reading"
    return f"UNKNOWN (not recorded; last before: {b}; next after: {a})"


def _find(rid: str) -> list[Path]:
    out = []
    for p in glob.glob(str(D / "**" / f"*{rid}*"), recursive=True):
        q = Path(p)
        if q.is_dir() and "_launches" not in q.parts and q.name.endswith(rid[-12:]) is False:
            pass
        if q.is_dir() and "_launches" not in q.parts:
            out.append(q)
    return sorted(set(out))


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _verify_crlf_restored(d: Path) -> str:
    """Seals written on Windows hash CRLF bytes; older commits stored LF. Verify a CRLF copy."""
    import shutil
    import tempfile

    from tools.seal_verify import verify_seal

    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / d.name
        shutil.copytree(d, dst)
        for f in dst.rglob("*"):
            if f.is_file() and f.name not in (".sealed", "manifest.sha256.json"):
                b = f.read_bytes()
                if b"\r\n" not in b:
                    f.write_bytes(b.replace(b"\n", b"\r\n"))
        return str(verify_seal(dst))


def _seal(dirs: list[Path]) -> str:
    sys.path.insert(0, str(ROOT))
    from tools.seal_verify import verify_seal

    res = []
    for d in dirs:
        if (d / ".sealed").exists():
            st = verify_seal(d)
            if st in ("MISMATCH", "MANIFEST_COVERAGE_GAP"):
                st2 = _verify_crlf_restored(d)
                st = f"{st} as checked out; {st2} after CRLF restore (committed LF-normalized)"
            res.append(f"{d.name}: {st}")
    hung = [d for d in dirs if "hung_" in str(d)]
    if not res and hung:
        return "UNSEALED (hang partial)"
    return "; ".join(res) or "UNSEALED"


def run_record(rid: str) -> dict[str, Any]:
    dirs = [d for d in _find(rid) if d.parent.name not in ("points", "work")]
    rec: dict[str, Any] = {"run_id": rid, "dirs": [str(d.relative_to(ROOT)) for d in dirs]}
    texts = ""
    specs: list[dict[str, Any]] = []
    plans: list[dict[str, Any]] = []
    for d in dirs:
        for f in ("plan.json", "summary.json", "manifest.json"):
            t = _read(d / f)
            texts += t
            if f == "plan.json" and t:
                try:
                    plans.append(json.loads(t))
                except json.JSONDecodeError:
                    pass
        for s in sorted((d / "work").glob("*.spec.json"))[:40]:
            try:
                specs.append(json.loads(_read(s)))
            except json.JSONDecodeError:
                pass
        for r in sorted((d / "work").glob("**/*.json"))[:12]:
            texts += _read(r)
        for r in sorted(d.parent.glob(f"*SOURCE_MANIFEST_{rid[:8]}*.txt")):
            texts += _read(r)
    if not texts:
        rec["found"] = False
        return rec
    rec["found"] = True
    ov = sorted(set(re.findall(r'"(?:ov_version|openvino)": "(20[0-9.]+-[^"]+)"', texts)))
    ga = sorted(set(re.findall(r'"(?:genai_version|openvino_genai)": "(20[0-9.]+[^"]*)"', texts)))
    rec["openvino"] = ov[0] if ov else "UNKNOWN (not recorded)"
    rec["openvino_genai"] = ga[0] if ga else "UNKNOWN (not recorded)"
    heads = sorted(set(re.findall(r'"git_head": "([0-9a-f]{40})"', texts)))
    rec["git_head"] = heads[0][:12] if heads else "not recorded"
    dates = sorted(
        re.findall(
            r'"(?:started_utc|created_utc|sealed_utc|ended_utc|armed_utc|ts)": "(20[0-9-]{8}T[^"]+)"',
            texts,
        )
        + re.findall(r"\|(20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z)", texts)
    )
    rec["date_utc"] = dates[0] if dates else None
    users = set(re.findall(r"C:\\\\Users\\\\(zjohn|zach)\\\\", texts))
    rec["host"] = (
        "aipc-c1 (XPS)"
        if users == {"zjohn"}
        else "evo-t2 (T2S)"
        if users == {"zach"}
        else f"UNKNOWN {sorted(users)}"
    )
    host_key = "aipc-c1" if users == {"zjohn"} else "evo-t2" if users == {"zach"} else ""
    rec["gpu_driver"] = driver_at(host_key, rec["date_utc"])
    if specs:
        rec["spec_arms"] = sorted({str(s.get("arm_id")) for s in specs})
        rec["spec_properties"] = sorted(
            {
                json.dumps(
                    [x.get("properties") for x in s.get("load_sequence", [])], sort_keys=True
                )
                for s in specs
            }
        )
        rec["spec_scheduler"] = sorted(
            {json.dumps(s.get("scheduler_config", "ABSENT_KEY")) for s in specs}
        )
        rec["spec_resident_two_turn"] = sorted({str(s.get("resident_two_turn")) for s in specs})
    for p in plans:
        t = json.dumps(p)
        for key in ("residency", "kv", "source", "enable_prefix_caching", "CACHE_DIR", "cache_dir"):
            vals = sorted(set(re.findall(r'"%s": ("[^"]*"|[^,}\]]+)' % key, t)))
            if vals:
                rec.setdefault("plan_" + key.lower(), vals[:4])
        ro = p.get("runtime_options") or (p.get("local") or {}).get("runtime_options")
        if ro:
            rec["plan_runtime_options"] = ro
    rec["seal"] = _seal(dirs)
    return rec


def item(
    num: str,
    what: str,
    rids: list[str],
    tool: str,
    cls: str,
    construct: str,
    sched: dict[str, Any],
    kv_req: str,
    residency: str,
    rec: str,
    notes: str = "",
) -> dict[str, Any]:
    runs = [run_record(r) for r in rids]
    kv_c = KV_COMPILED.get(kv_req if kv_req != "none" else None, "n/a")
    return {
        "number": num,
        "what": what,
        "run_ids": rids,
        "tool": tool,
        "class": cls,
        "constructed_as": construct,
        "scheduler": sched,
        "prefix_caching": sched.get("enable_prefix_caching"),
        "max_num_batched_tokens": sched.get("max_num_batched_tokens"),
        "kv_requested": kv_req,
        "kv_compiled": f"{kv_c} ({KV_BASIS})" if kv_c != "n/a" else "n/a",
        "cache_dir": "none",
        "residency": residency,
        "runs": runs,
        "recommendation": rec,
        "notes": notes,
    }


NA = {"note": "not applicable"}
NPU_S = {"note": "NPU LLMPipeline (static NPUW pipeline); no SchedulerConfig"}
PLAIN = "LLMPipeline(model_dir, device, **properties) (seam/tools/_delta_n_child.py; no scheduler key in the child spec)"


def build() -> dict[str, Any]:
    items = [
        item(
            "15,000",
            "XPS resident-session limit, f16 KV",
            ["553b3a5c-dd68-4502-bb3f-1b6a10a61eb1"],
            "run_resident_limit (delta_prefill)",
            "PLAIN_PIPELINE_WITH_PROPS",
            PLAIN,
            LATENCY,
            "f16",
            "RESIDENT two-turn",
            "LABEL: 'plain LLMPipeline, latency scheduler, KV f16 property'; driver UNKNOWN. Re-measure on driver 8860 to pair with a5d19dcc.",
        ),
        item(
            "20,000",
            "XPS resident-session limit, u8 KV request (compiles i8)",
            ["cf3555d5-1361-434f-b1fb-745fc17e6843"],
            "run_resident_limit",
            "PLAIN_PIPELINE_WITH_PROPS",
            PLAIN,
            LATENCY,
            "u8",
            "RESIDENT two-turn",
            "LABEL as plain pipeline + u8 property (= i8 compiled), not 'true default' and not 'bare SchedulerConfig' (Task AX). "
            "It is 2,000 above the true-default 18,000 (a5d19dcc) on a later driver: RE-MEASURE gpu_only_u8 on the current driver to split property vs driver.",
            "AX finding: plain LLMPipeline with a KV u8 property (_delta_n_child at 0e8aa5a), not the replaced config.",
        ),
        item(
            "26,500",
            "XPS resident-session limit, u4 KV",
            ["e4a22dac-6301-4dfa-ae12-882328b6ba7c"],
            "run_resident_limit",
            "PLAIN_PIPELINE_WITH_PROPS",
            PLAIN,
            LATENCY,
            "u4",
            "RESIDENT two-turn",
            "LABEL; re-measure u4 on driver 8860 (P3 u4 cells would also give it).",
        ),
        item(
            "18,000",
            "XPS resident-session limit, true default (no property)",
            ["a5d19dcc-e431-4fd5-8247-36cf96ad7387"],
            "run_resident_limit --arm gpu_only --high 50000 (P3 cell 0)",
            "TRUE_DEFAULT",
            "LLMPipeline(model_dir, 'GPU') (no property, no scheduler)",
            LATENCY,
            "none",
            "RESIDENT two-turn",
            "CITE as the true-default limit (driver 8860, 2026-10-20). First fail 18,500: turn-2 RuntimeError (not a hang).",
        ),
        item(
            "0.639 / 1.003 / 0.946 s",
            "XPS warm turn-2 TTFT at 12,000 cached, f16 / u8 / u4",
            [
                "72776603-7ea0-4279-a425-941d73a0bf57",
                "1587d2f4-b30f-4be9-9c1d-6d0d04690c4b",
                "dd2b0779-48c1-4ad6-9567-ed38e8e1fec9",
            ],
            "run_warm_kv (delta_prefill)",
            "PLAIN_PIPELINE_WITH_PROPS",
            PLAIN,
            LATENCY,
            "f16 / u8 / u4",
            "RESIDENT two-turn",
            "LABEL (plain pipeline + KV property each). The i8 point is u8-requested; a true-default (no property) point does not exist: RE-MEASURE run_warm_kv --arm gpu_only at 12,000 if the paper says 'default'.",
        ),
        item(
            "$0.184 vs $0.0129 per task",
            "DEMO-1 V4 hybrid cloud $/task, XPS vs T2S",
            ["a678926e-2681-4851-a386-8b7c83e971a3", "30caa847-d97a-4e4b-aa22-f152b95d08e9"],
            "run_h1_hybrid --policy slo_escalate (launch_h1)",
            "REPLACED_SCHEDULER",
            "LLMPipeline(model, 'GPU', {'scheduler_config': sc}, KV_CACHE_PRECISION=u8) with sc = SchedulerConfig(); sc.enable_prefix_caching = False (tools/bfcl_feasibility_probe.load_arm_pipeline, NON_RESIDENT branch)",
            {
                **STRUCT,
                "replaced": LATENCY,
                "fields_changed_vs_latency_default": {
                    "enable_prefix_caching": "True -> False",
                    "max_num_batched_tokens": "SIZE_MAX -> 256 (struct default)",
                },
            },
            "u8",
            "NON_RESIDENT",
            "LABEL exactly: 'NON_RESIDENT, bare SchedulerConfig (prefix caching off, max_num_batched_tokens 256), KV u8 = i8'. "
            "A re-measure needs cloud spend (not $0): not proposed here.",
            "Same construction for every DEMO-1 V cell (V1 f7343708, V2 1acc8c58, V3 71d33f7a+ab88f47f, T2S V1 b026f3fd, V3 a4284ab0).",
        ),
        item(
            "V1 local 0.0 / MATCH x3",
            "DEMO-1 V1 (XPS f7343708, T2S b026f3fd)",
            ["f7343708-a4a5-4984-93e5-ce5412a6c981", "b026f3fd-004e-4419-91bd-80c79f94e0f1"],
            "run_h1_hybrid --policy slo_escalate",
            "REPLACED_SCHEDULER",
            "as above (NON_RESIDENT bare SchedulerConfig, prefix caching off)",
            {**STRUCT, "replaced": LATENCY},
            "u8",
            "NON_RESIDENT",
            "LABEL as REPLACED_SCHEDULER. Contrast with DEMO-2 arm A (true default, RESIDENT) is two changes, not one.",
        ),
        item(
            "10,000 (9,750 HELD)",
            "XPS GPU cold edge at the 10 s TTFT SLO",
            ["c2246b1f-c588-4998-838a-5507da87e9ee"],
            "c2_ttft ladder (one child per repeat)",
            "PLAIN_PIPELINE_WITH_PROPS",
            PLAIN,
            LATENCY,
            "u8",
            "cold single generate per child",
            "LABEL; each repeat is a fresh process, so prefix caching cannot reuse a prompt. Re-measure under the true default only if the paper says 'default'.",
            "9,750 (c647f0c7) stays HELD in derived/WITHDRAWN.md.",
        ),
        item(
            "21.4x",
            "placement: GPU 10,000 vs CPU 468 tokens",
            ["c2246b1f-c588-4998-838a-5507da87e9ee", "7f232f86-2525-481b-a000-c6b8491bc224"],
            "c2_ttft",
            "PLAIN_PIPELINE_WITH_PROPS",
            PLAIN + "; CPU arm adds PCORE_ONLY, pinning, 4 threads",
            LATENCY,
            "u8 (GPU) / none (CPU)",
            "cold single generate per child",
            "LABEL.",
        ),
        item(
            "30-34% slower",
            "int8 vs int4 weights decode (DECODE-MATCH)",
            ["180dfbb9-5ad6-446e-a3f2-0d6fa8eea196"],
            "run_decode_match",
            "PLAIN_PIPELINE_WITH_PROPS",
            PLAIN,
            LATENCY,
            "u8",
            "cold single generate per child",
            "LABEL.",
        ),
        item(
            "46k cold turn 230-253 s",
            "CAP-4 cold-turn timing f16/u8/u4 (not the ~46,000 combined limit)",
            ["2b3316b6-7f6e-474f-9177-bd5a89aeb58c"],
            "cap4",
            "PLAIN_PIPELINE_WITH_PROPS",
            PLAIN,
            LATENCY,
            "f16 / u8 / u4",
            "RESIDENT (interleaved)",
            "LABEL; the only run with a recorded GPU driver (8724).",
        ),
        item(
            "~46,000 combined limit; C2 23-25x",
            "ISPASS I-5 and the C2 headline",
            [],
            "unknown",
            "UNKNOWN",
            "no run_id in this repo",
            NA,
            "unknown",
            "unknown",
            "NEEDS RUN_ID (Zach). Cannot be audited until the run is named.",
        ),
        item(
            "P0-v2 2.47/3.26 s GPU, 9.29/11.17 s CPU",
            "warm time-to-action at 4k/6k",
            ["ac4e5472-76a9-4999-bf0b-8274d27ce0ca"],
            "exchange_rate",
            "PLAIN_PIPELINE_WITH_PROPS",
            PLAIN,
            LATENCY,
            "u8",
            "RESIDENT two-turn",
            "LABEL.",
        ),
        item(
            "NPU 1024->960, 2048->1984, 4096->4032",
            "NPU toolchain cap (MAX_PROMPT_LEN)",
            [
                "faa14a31-c375-4c77-95a9-7e2fa58f5d49",
                "9acabbf7-474a-410a-9968-0ef88f76afa1",
                "2ffbd61c-470a-4d1f-98f1-3fe8eb61f5c4",
                "2972e8c4-7608-4c9f-9cee-4115d2098039",
            ],
            "npu limit ladder",
            "PLAIN_PIPELINE_WITH_PROPS",
            "NPU LLMPipeline with MAX_PROMPT_LEN, MIN_RESPONSE_LEN 8, NPUW_LLM_PREFILL_CHUNK_SIZE 1024",
            NPU_S,
            "n/a (INT8 weights)",
            "n/a",
            "LABEL with the host: these ran on the T2S (model path C:\\Users\\zach), after the 2026-10-14 Windows Update reboot; NPU driver at the time UNKNOWN (4512 on 2026-10-20).",
            "Their canary thresholds were derived from XPS data (threshold_derivation.platform_id aipc-c1).",
        ),
    ]
    return {
        "task": "AZ part 2",
        "generated_from": "committed run directories; no number changed",
        "latency_default_2026_2_1": LATENCY,
        "struct_default_2026_2_1": STRUCT,
        "driver_readings": DRIVER_READINGS,
        "items": items,
    }


if __name__ == "__main__":
    json.dump(build(), sys.stdout, indent=2, default=str)
    print()
