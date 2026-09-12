import json
from pathlib import Path
p = Path("derived/mslice/affinity_matrix.partial.json")
if not p.exists():
    print("done=0/80 no_partial")
    raise SystemExit(0)
d = json.loads(p.read_text(encoding="utf-8"))
runs = d.get("runs") or {}
done = sum(len(v) for v in runs.values())
per = {k: len(v) for k, v in sorted(runs.items())}
print(f"done={done}/80 per={per} cooldown={d.get('cooldown_s')} seed={d.get('shuffle_seed')} interrupted={d.get('interrupted')}")
