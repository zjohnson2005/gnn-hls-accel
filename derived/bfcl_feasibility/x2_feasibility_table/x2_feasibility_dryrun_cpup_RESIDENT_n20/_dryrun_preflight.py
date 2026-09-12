import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\zjohn\Projects\gnn-hls-accel")
import tools.bfcl_feasibility_probe as probe
from tools.run_x2_feasibility import ARM_CLI_TO_PROBE

a621 = Path(r"C:\Users\zjohn\Projects\gnn-hls-accel\derived\bfcl_feasibility\session_residency\a621ff7d-2919-463d-aaf6-673f9e6bafbc\session_residency_entries_gpu_only_RESIDENT.json")
dry = Path(r"C:\Users\zjohn\Projects\gnn-hls-accel\derived\bfcl_feasibility\x2_feasibility_table\x2_feasibility_dryrun_cpup_RESIDENT_n20")
n_entries = int(20)
model_spec = r"C:\Users\zjohn\Projects\gnn-hls-accel\configs\models\Qwen3-4B-int4-ov.yaml"
arm_cli = r"cpu-p"
residency = r"RESIDENT"
arm_id = ARM_CLI_TO_PROBE[arm_cli]
entries = probe.select_multi_turn_entries()[:n_entries]
pin = dry / probe.PINNED_MULTI_TURN_ENTRIES
pin.write_text(json.dumps(entries, indent=2, default=str) + "\n", encoding="utf-8")
got = [str(e["id"]) for e in entries]
ref = [str(e["id"]) for e in json.loads(a621.read_text(encoding="utf-8-sig"))]
entry_assert = {"mode": "exact", "n_reference": len(ref), "n_run": len(got)}
print("PIN_PATH", pin)
print("MODEL_SPEC", model_spec)
print("ARM_CLI", arm_cli)
print("ARM_ID", arm_id)
print("RESIDENCY", residency)
print("WATCHDOG_INTERVAL_S", 300)
print("ENTRY_ASSERT", json.dumps(entry_assert, sort_keys=True))
print("N_GOT", len(got), "N_REF", len(ref))
exact_ok = got == ref
print("EXACT_OK", exact_ok)
if not exact_ok:
    for i, (a, b) in enumerate(zip(got, ref)):
        if a != b:
            print("FIRST_MISMATCH", i, a, b)
            break
    if len(got) != len(ref):
        print("LENGTH_DIFF", len(got), len(ref))
    raise SystemExit(3)
print("IDS", ",".join(got))
gold = probe.run_multi_turn_gold_selftest(entries)
(dry / "multi_turn_gold_selftest.json").write_text(
    json.dumps(gold, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
)
print("GOLD_N", gold.get("n"), "GOLD_N_VALID", gold.get("n_valid"))
print("GOLD_OK", gold.get("n_valid") == gold.get("n") == n_entries)
if gold.get("n_valid") != n_entries or gold.get("n") != n_entries:
    raise SystemExit(3)
# Per-entry onset helpers must be callable (probe path used at generation).
onset = {
    "uptime_s": probe._host_uptime_s(),
    **probe._host_available_mb(),
}
print("ONSET_PROBE_SAMPLE", json.dumps(onset, sort_keys=True))
if onset.get("uptime_s") is None or onset.get("available_mb") is None:
    print("REFUSED -- per-entry onset helpers returned None")
    raise SystemExit(3)
print("ONSET_FIELDS", "uptime_s,available_mb,available_method")
print("FEASIBILITY_CELL", f"{arm_cli} x {residency}")
