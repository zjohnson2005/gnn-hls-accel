"""Compare v1 vs v3 artifact environments (numpy/BLAS/python versions)."""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path("apu_characterization/out")

for name in ("replication_remote_search.json", "replication_remote_search_v3.json"):
    d = json.loads((OUT / name).read_text(encoding="utf-8"))
    a0 = d["per_seed_artifacts"][0]
    env = a0.get("env") or a0.get("run", {}).get("env") or {}
    print(f"=== {name}")
    for k in sorted(env):
        v = env[k]
        if isinstance(v, (str, int, float, bool)) and len(str(v)) < 100:
            print(f"  {k}: {v}")
    cfg = a0.get("config", {})
    print(f"  config keys: {sorted(cfg.keys())}")
    for k in ("instr_version", "seed", "backend", "search_locality"):
        if k in cfg:
            print(f"  config.{k}: {cfg[k]}")
