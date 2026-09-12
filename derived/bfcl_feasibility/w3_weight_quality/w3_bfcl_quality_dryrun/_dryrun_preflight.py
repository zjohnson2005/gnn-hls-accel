import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\zjohn\Projects\gnn-hls-accel")
import tools.bfcl_feasibility_probe as probe

a621 = Path(r"C:\Users\zjohn\Projects\gnn-hls-accel\derived\bfcl_feasibility\session_residency\a621ff7d-2919-463d-aaf6-673f9e6bafbc\session_residency_entries_gpu_only_RESIDENT.json")
dry = Path(r"C:\Users\zjohn\Projects\gnn-hls-accel\derived\bfcl_feasibility\w3_weight_quality\w3_bfcl_quality_dryrun")
entries = probe.select_multi_turn_entries()[:20]
pin = dry / probe.PINNED_MULTI_TURN_ENTRIES
pin.write_text(json.dumps(entries, indent=2, default=str) + "\n", encoding="utf-8")
got = [e["id"] for e in entries]
ref = [e["id"] for e in json.loads(a621.read_text(encoding="utf-8-sig"))]
print("PIN_PATH", pin)
print("N_GOT", len(got), "N_REF", len(ref))
print("IDS_EQUAL", got == ref)
if got != ref:
    for i, (a, b) in enumerate(zip(got, ref)):
        if a != b:
            print("FIRST_MISMATCH", i, a, b)
            break
    raise SystemExit(3)
print("IDS", ",".join(got))
gold = probe.run_multi_turn_gold_selftest(entries)
(dry / "multi_turn_gold_selftest.json").write_text(
    json.dumps(gold, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
)
print("GOLD_N", gold.get("n"), "GOLD_N_VALID", gold.get("n_valid"))
print("GOLD_OK", gold.get("n_valid") == gold.get("n") == 20)
if gold.get("n_valid") != 20 or gold.get("n") != 20:
    raise SystemExit(3)
print("DUAL_WEIGHT_SAME_SESSION", False)
print(
    "DUAL_WEIGHT_NOTE",
    "probe binds one --model-spec per process; int4 not in this session",
)
