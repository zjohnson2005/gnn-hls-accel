import json, sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\zjohn\Projects\gnn-hls-accel")
from tools.run_q_8b_quality import ARMS, ARM_MODEL_SPECS, PLACEMENT_ARM, KV_EXPECTED, PRED_PATH
pred = json.loads(PRED_PATH.read_text(encoding="utf-8-sig"))
assert pred["status"] == "pre_registered_before_measurement"
assert pred["weight_precision"] == "int4"
assert pred["no_int8_8b_in_registry"] is True
for a in ARMS:
    p = ARM_MODEL_SPECS[a]
    assert p.is_file(), p
    print("ARM_SPEC_OK", a, p)
print("PLACEMENT", PLACEMENT_ARM, "KV", KV_EXPECTED)
print("PRED_UTC", pred.get("registered_utc"))
print("DRYRUN_OK")
