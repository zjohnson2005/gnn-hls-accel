"""Phase 1 closeout + Phase 2 entry checklist."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

OE_ROOT = Path(__file__).resolve().parents[2]
GATE_DIR = OE_ROOT / "characterization" / "out" / "gate"


def _has_openai_key() -> bool:
    key = os.environ.get("OPENAI_API_KEY", "")
    return bool(key) and key.startswith("sk-")


def _repeat_coverage() -> dict[int, int]:
    counts: dict[int, int] = {}
    for path in GATE_DIR.glob("openai_action_heavy_c*_rep*.json"):
        base = path.stem.split("_rep")[0]
        c = int(base.split("_c")[-1])
        counts[c] = counts.get(c, 0) + 1
    return dict(sorted(counts.items()))


def _missing_repeats() -> list[str]:
    targets = {1: 10, 10: 3, 20: 3, 100: 3, 500: 3}
    have = _repeat_coverage()
    cmds: list[str] = []
    for level, want in targets.items():
        got = have.get(level, 0)
        if got < want:
            need = want - got
            cmds.append(
                f"py -3 -m orchestration_engine.characterization.phase1_gate.openai_scaling_sweep "
                f"--levels {level} --fast --force --repeats {need}"
            )
    return cmds


def main() -> int:
    print("=== Phase 1 closeout / Phase 2 entry ===\n")

    print("1. Regenerating Phase 1 gate report...")
    subprocess.run(
        [sys.executable, "-m", "orchestration_engine.characterization.phase1_gate.gate_report", "--skip-openai"],
        check=False,
    )

    print("\n2. Regenerating Phase 2 gate report...")
    subprocess.run(
        [sys.executable, "-m", "orchestration_engine.phase2_gate.gate_report"],
        check=False,
    )

    print("\n3. Repeat coverage:")
    reps = _repeat_coverage()
    if reps:
        for level, n in reps.items():
            print(f"   c={level}: {n} repeat file(s)")
    else:
        print("   No repeat files found.")

    missing = _missing_repeats()
    if missing:
        print("\n4. Error-bar runs still needed:")
        for cmd in missing:
            print(f"   {cmd}")
    else:
        print("\n4. Error-bar targets satisfied.")

    print("\n5. OpenAI-dependent:")
    if not _has_openai_key():
        print("   OPENAI_API_KEY not set. To finish Phase 1 anchors:")
        print(
            "   py -3 -m orchestration_engine.characterization.phase1_gate.openai_scaling_sweep "
            "--levels 1000 --fast --force"
        )
    else:
        print("   API key present — run c=1000 anchor if not done:")
        c1000 = GATE_DIR / "openai_action_heavy_c1000.json"
        if c1000.exists():
            print(f"   OK: {c1000.name}")
        else:
            print(
                "   py -3 -m orchestration_engine.characterization.phase1_gate.openai_scaling_sweep "
                "--levels 1000 --fast --force"
            )

    print("\n6. Vitis box (Phase 2 HLS + DSE):")
    print("   bash orchestration_engine/run_phase2.sh")

    print("\n7. Local software bench:")
    bench = OE_ROOT / "build" / "oe_bench.exe"
    if bench.exists():
        print(f"   OK: {bench}")
    else:
        print("   cd orchestration_engine; .\\build.ps1")

    p2 = OE_ROOT / "characterization" / "out" / "phase2" / "phase2_gate.md"
    if p2.exists():
        print(f"\nSee {p2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
