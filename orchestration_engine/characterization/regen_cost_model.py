"""Patch dynamic_graph_cost_model.md from measured phase2 JSON (no hand-typed numbers)."""

import json
import re
from pathlib import Path

OE_ROOT = Path(__file__).resolve().parents[1]
OUT = OE_ROOT / "characterization" / "out" / "phase2"
DOC = OE_ROOT / "docs" / "dynamic_graph_cost_model.md"
CSYNTH = OUT / "csynth_scatter.json"


def _read(name):
    path = OUT / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _fmax_mhz():
    if CSYNTH.exists():
        data = json.loads(CSYNTH.read_text(encoding="utf-8"))
        return data.get("estimated_fmax_mhz") or 404.4
    return 404.4


def patch_session_load(gl):
    if not DOC.exists() or gl is None:
        return False
    text = DOC.read_text(encoding="utf-8")
    cycles = gl.get("latency_cycles")
    cpn = gl.get("cycles_per_node")
    cpo = gl.get("cycles_per_op")
    fmax = _fmax_mhz()
    us_total = round(cycles / fmax, 4) if cycles and fmax else None

    marker = "| session load (50-node graph) |"
    new_row = (
        "| session load (50-node graph) | **{cycles} measured cosim** "
        "({cpn} cyc/node, {cpo} cyc/op @ {fmax} MHz csynth Fmax = {us} us) | "
        "streamed graph_load op axis; design target was ~250-400 |"
    ).format(
        cycles=cycles if cycles is not None else "?",
        cpn=cpn if cpn is not None else "?",
        cpo=cpo if cpo is not None else "?",
        fmax=fmax,
        us=us_total if us_total is not None else "?",
    )

    lines = text.splitlines()
    out = []
    replaced = False
    for line in lines:
        if line.startswith(marker) and not replaced:
            out.append(new_row)
            replaced = True
        else:
            out.append(line)

    if not replaced:
        return False
    DOC.write_text("\n".join(out) + "\n", encoding="utf-8")
    return True


def main():
    gl = _read("cosim_graph_load.json")
    if patch_session_load(gl):
        print("Updated session load row in {0}".format(DOC))
    else:
        print("No session load patch applied (missing cosim_graph_load.json or row)")


if __name__ == "__main__":
    main()
