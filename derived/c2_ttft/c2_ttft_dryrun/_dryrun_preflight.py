import json, sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\zjohn\Projects\gnn-hls-accel")
from transformers import AutoTokenizer
from seam.config import resolve_config
from seam.tools.delta_n import build_exact_prompt, _PLATFORM_PATH, _MEASUREMENT_PATH, _DELTA_N_PATH
from tools.run_c1_ceiling import (
    _ttft_slo_predictions, ARMS, CRITERION_TTFT_SLO, SLO_S_DEFAULT
)

root = Path(r"C:\Users\zjohn\Projects\gnn-hls-accel")
resolved = resolve_config(
    [root / _PLATFORM_PATH, root / _MEASUREMENT_PATH, root / _DELTA_N_PATH],
    repo_root=root,
)
cfg = resolved.data
arms_by_id = {a["id"]: a for a in cfg["arms"]}
for aid in ARMS:
    assert aid in arms_by_id, aid
props = arms_by_id["gpu_only_f16"].get("properties") or {}
assert str(props.get("KV_CACHE_PRECISION")).lower() == "f16", props
print("ARM_PIN_OK gpu_only_f16 KV_CACHE_PRECISION=f16")
for aid in ("gpu_only_u8", "gpu_only_u4"):
    props = arms_by_id[aid].get("properties") or {}
    print("ARM", aid, "KV_CACHE_PRECISION", props.get("KV_CACHE_PRECISION"))
tok = AutoTokenizer.from_pretrained(str(root / "models" / "Qwen3-4B-int4-ov"))
unit = cfg["ladder"]["filler_unit"]
for n in (8000, 10000, 12000):
    text, realized = build_exact_prompt(tok, target_tokens=n, unit=unit)
    assert realized == n, (n, realized)
    print("PROMPT_OK", n, "chars", len(text))
pred = _ttft_slo_predictions(slo_s=float(10), repeats=int(3))
print("CRITERION", CRITERION_TTFT_SLO)
print("ACTIVE_ORDER", pred["primary_prediction"]["order"])
print("ACTIVE_FALSIFIED_IF", pred["primary_prediction"]["falsified_if"])
print("WITHDRAWN_ORDER", pred["withdrawn_prediction"]["order"])
print("SEPARATE_NOT_C2", pred["separate_experiment_not_c2"]["name"])
print("SLO_S", SLO_S_DEFAULT)
print("DRYRUN_OK")
