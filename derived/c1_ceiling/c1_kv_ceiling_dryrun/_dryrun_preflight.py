import json, sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\zjohn\Projects\gnn-hls-accel")
from transformers import AutoTokenizer
from seam.config import resolve_config
from seam.tools.delta_n import build_exact_prompt, _PLATFORM_PATH, _MEASUREMENT_PATH, _DELTA_N_PATH
from tools.run_c1_ceiling import _predictions, ARMS

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
tok = AutoTokenizer.from_pretrained(str(root / "models" / "Qwen3-4B-int4-ov"))
unit = cfg["ladder"]["filler_unit"]
for n in (12000, 45000):
    text, realized = build_exact_prompt(tok, target_tokens=n, unit=unit)
    assert realized == n, (n, realized)
    print("PROMPT_OK", n, "chars", len(text))
pred = _predictions(float(2839))
print("PREDICTIONS", json.dumps(pred["arms"], indent=2, sort_keys=True))
print("PRIMARY", pred["primary_prediction"]["claim"][:80], "...")
print("DRYRUN_OK")
