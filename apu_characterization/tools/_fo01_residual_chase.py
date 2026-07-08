"""FO-01 residual chase: per-seed session + category breakdown."""

from __future__ import annotations

import json
from pathlib import Path

ART = Path("apu_characterization/out/replication_remote_search_v3.json")


def main() -> None:
    data = json.loads(ART.read_text(encoding="utf-8"))
    print("=== FO-01 per seed ===\n")
    for art in data["per_seed_artifacts"]:
        seed = art["config"]["seed"]
        for s in art["run"]["per_session"]:
            if s["task_id"] != "FO-01":
                continue
            prov = s.get("provenance") or {}
            host_ns = s["process_cpu_ns"]
            res_ns = prov.get("residual", 0)
            print(f"seed {seed}  wall={s['wall_s']:.2f}s  host={host_ns/1e6:.1f}ms")
            print(
                f"  residual={res_ns/1e6:.2f}ms ({100*res_ns/host_ns:.1f}%)  "
                f"trim={s.get('parallel_cpu_trim_ns',0)/1e6:.1f}ms  "
                f"instr={s.get('instrumented_cpu_ns',0)/1e6:.1f}ms"
            )
            print(f"  tools={s.get('tool_call_counts')}  turns={s.get('turns')}")
            pt = art["per_task"].get("FO-01", {})
            cats = pt.get("categories", {})
            print("  categories (cpu ms / wall s):")
            for c, v in sorted(cats.items(), key=lambda kv: -kv[1].get("cpu_ns", 0)):
                cpu = v.get("cpu_ns", 0)
                if cpu <= 0 and v.get("wall_ns", 0) <= 0:
                    continue
                print(f"    {c:24s} cpu={cpu/1e6:7.2f}ms  wall={v.get('wall_ns',0)/1e9:6.2f}s")
            # per-session category if available
            psc = art["run"].get("per_session_category") or {}
            sid = s["session_id"]
            if sid in psc:
                print(f"  per_session_category ({sid}):")
                for c, v in sorted(psc[sid].items(), key=lambda kv: -kv[1].get("cpu_ns", 0)):
                    if v.get("cpu_ns", 0) > 0:
                        print(f"    {c:24s} {v['cpu_ns']/1e6:.2f}ms")
            prov_detail = art["run"].get("provenance_detail") or {}
            fo_keys = [k for k in prov_detail if "|FO-01|" in k or sid in k]
            if prov_detail:
                print("  provenance_detail (FO-01 session categories):")
                for k, ns in sorted(prov_detail.items(), key=lambda kv: -kv[1]):
                    if sid.replace("agent_", "") in k or "FO-01" in k or sid in k:
                        pass
                for k, ns in sorted(
                    ((k, v) for k, v in prov_detail.items() if sid in k.split("|")[1:2] or k.endswith(f"|{sid}|")),
                    key=lambda kv: -kv[1],
                ):
                    if ns > 1000:
                        print(f"    {k}: {ns/1e6:.2f}ms")
            print()


if __name__ == "__main__":
    main()
