"""Probe LightningSim trace capture: expose testbench rc/output + subprocess logs.

LightningSim's CLI hides the instrumented testbench's stdout and exit code and
never checks them; an empty trace then surfaces as the misleading error
"kernel did not run". This runs LS's Runner directly (debug=True keeps the
tempdirs) and prints everything needed to localize the failure:
  - each build subprocess command + rc (+ output when nonzero)
  - the testbench's exit code and stdout
  - the kept intermediate-object directory (for nm symbol inspection)

Usage:
  python -m orchestration_engine.eval.ls_probe <solution_dir>

If XILINX_HLS is unset, the ARCHIVE Vitis env is sourced automatically via
orchestration_engine/hls_env_lightningsim.sh (same as run_ls_probe.sh).
"""

import asyncio
import sys
from pathlib import Path

from orchestration_engine.eval.ls_env import ensure_lightningsim_env


async def probe(solution_dir: Path) -> int:
    from lightningsim.model import Solution
    from lightningsim.runner import Runner, RunnerStep

    solution = Solution(solution_dir.resolve())
    runner = Runner(solution, debug=True)

    for step in RunnerStep:
        runner.steps[step].on_start(
            lambda _s, name=step.name: print(f"[step] {name}", flush=True)
        )

    failed = None
    try:
        trace = await runner.run()
        print(f"\nTRACE OK: {trace.line_count} lines, {len(trace.fifos)} FIFOs")
    except Exception as exc:  # noqa: BLE001 - report everything, then exit nonzero
        failed = exc
        print(f"\nTRACE FAILED: {type(exc).__name__}: {exc}")

    print("\n=== build subprocesses (last 10) ===")
    for proc in runner.processes[-10:]:
        cmd = proc.command
        if len(cmd) > 160:
            cmd = cmd[:80] + " ... " + cmd[-60:]
        print(f"[rc={proc.returncode}] {cmd}")
        if proc.returncode != 0 and proc.output:
            print("--- output ---")
            print(proc.output[-3000:])
            print("--------------")

    tb = runner.testbench
    if tb is None:
        print("\n=== testbench: NEVER RAN (failure was before the run step) ===")
    else:
        print(f"\n=== testbench exit code: {tb.returncode} ===")
        print("=== testbench stdout/stderr ===")
        out = tb.output or "(empty)"
        print(out[-4000:])
        print("=== end testbench output ===")

    return 1 if failed else 0


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    ensure_lightningsim_env()
    return asyncio.run(probe(Path(sys.argv[1])))


if __name__ == "__main__":
    sys.exit(main())
