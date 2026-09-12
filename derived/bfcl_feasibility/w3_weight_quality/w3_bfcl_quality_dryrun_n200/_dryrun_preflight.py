import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\zjohn\Projects\gnn-hls-accel")
import tools.bfcl_feasibility_probe as probe

a621 = Path(r"C:\Users\zjohn\Projects\gnn-hls-accel\derived\bfcl_feasibility\session_residency\a621ff7d-2919-463d-aaf6-673f9e6bafbc\session_residency_entries_gpu_only_RESIDENT.json")
dry = Path(r"C:\Users\zjohn\Projects\gnn-hls-accel\derived\bfcl_feasibility\w3_weight_quality\w3_bfcl_quality_dryrun_n200")
n_entries = int(200)
model_spec = r"C:\Users\zjohn\Projects\gnn-hls-accel\configs\models\Qwen3-4B-int4-ov.yaml"
entries = probe.select_multi_turn_entries()[:n_entries]
pin = dry / probe.PINNED_MULTI_TURN_ENTRIES
pin.write_text(json.dumps(entries, indent=2, default=str) + "\n", encoding="utf-8")
got = [str(e["id"]) for e in entries]
ref = [str(e["id"]) for e in json.loads(a621.read_text(encoding="utf-8-sig"))]
entry_assert = {"mode": "prefix", "n_reference": len(ref), "n_run": len(got)}
print("PIN_PATH", pin)
print("MODEL_SPEC", model_spec)
print("ENTRY_ASSERT", json.dumps(entry_assert, sort_keys=True))
print("N_GOT", len(got), "N_REF", len(ref))
prefix_ok = got[: len(ref)] == ref
print("PREFIX_OK", prefix_ok)
print("FIRST20_MATCH_A621", got[:20] == ref[:20] if len(got) >= 20 and len(ref) >= 20 else False)
if not prefix_ok:
    for i, (a, b) in enumerate(zip(got, ref)):
        if a != b:
            print("FIRST_MISMATCH", i, a, b)
            break
    if len(got) < len(ref):
        print("LENGTH_SHORTFALL", len(got), len(ref))
    raise SystemExit(3)
print("IDS_PREFIX", ",".join(got[: min(20, len(got))]))
gold = probe.run_multi_turn_gold_selftest(entries)
(dry / "multi_turn_gold_selftest.json").write_text(
    json.dumps(gold, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
)
print("GOLD_N", gold.get("n"), "GOLD_N_VALID", gold.get("n_valid"))
print("GOLD_OK", gold.get("n_valid") == gold.get("n") == n_entries)
if gold.get("n_valid") != n_entries or gold.get("n") != n_entries:
    raise SystemExit(3)
print("DUAL_WEIGHT_SAME_SESSION", False)
print(
    "DUAL_WEIGHT_NOTE",
    "probe binds one --model-spec per process; int4 via separate -ModelSpec launch",
)
print("ENTRY_POPULATION_NOTE",
      "select_multi_turn_entries applies no difficulty or API filter; "
      "plain file-order prefix â€” never biased relative to the benchmark.")
