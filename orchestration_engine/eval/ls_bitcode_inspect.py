"""List FIFO-related symbols in an HLS solution bitcode (LightningSim hook targets)."""

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python -m orchestration_engine.eval.ls_bitcode_inspect <solution_dir>")
        return 2

    solution = Path(sys.argv[1]).resolve()
    bc_path = solution / ".autopilot/db/a.o.3.bc"
    if not bc_path.is_file():
        print(f"ERROR: bitcode not found: {bc_path}")
        return 1

    import llvmlite.binding as llvm

    mod = llvm.parse_bitcode(bc_path.read_bytes())
    names = sorted(f.name for f in mod.functions if f.name)
    fifo = [n for n in names if "Fifo" in n or "fifo" in n]
    autotb = [n for n in names if "autotb" in n]

    print(f"bitcode: {bc_path}")
    print(f"functions: {len(names)} total")
    print(f"FIFO-related ({len(fifo)}):")
    for n in fifo[:40]:
        print(f"  {n}")
    if len(fifo) > 40:
        print(f"  ... ({len(fifo) - 40} more)")
    print(f"autotb ({len(autotb)}):")
    for n in autotb[:20]:
        print(f"  {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
