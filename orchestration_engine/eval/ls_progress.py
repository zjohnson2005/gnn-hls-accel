"""Print a one-screen LightningSim debug checklist from ls_probe.log + solution dir."""

from __future__ import annotations

import sys
from pathlib import Path


def _grep(path: Path, needle: str) -> list[str]:
    if not path.is_file():
        return []
    return [ln.rstrip() for ln in path.read_text(errors="replace").splitlines() if needle in ln]


def report(repo: Path, log: Path, sol: Path) -> int:
    print("=== LightningSim debug progress ===\n")

    rows = [
        ("Toolchain env (XILINX_HLS, conda CXX)", "LightningSim link CXX=" in log.read_text(errors="replace") if log.is_file() else False),
        ("Patch script runs cleanly", "runner ready:" in (log.read_text(errors="replace") if log.is_file() else "")),
        ("LS-lite source (uint16_t idx_t)", "typedef uint16_t idx_t;" in (repo / "src/gnn_config.h").read_text(errors="replace")),
        ("Vitis csim + csynth built", (sol / "syn/report/gcn_layer_stream_csynth.rpt").is_file()),
        ("Stamp tag df-u16", "GNN_LS_LITE=df-u16" in (sol / ".oe_lightningsim_vitis").read_text(errors="replace") if (sol / ".oe_lightningsim_vitis").is_file() else False),
        ("Bitcode FIFO hooks (i512)", any("_autotb_FifoRead_i512" in ln for ln in _grep(log, "autotb"))),
        ("Instrumented TB links (rc=0 make)", any("[rc=0] make" in ln and "testbench_" in ln for ln in _grep(log, "[rc="))),
        ("Instrumented TB runs (not -11)", not any("testbench exit code: -11" in ln for ln in _grep(log, "testbench exit code"))),
        ("Functional: Vitis csim TEST PASSED", "TEST PASSED" in (log.read_text(errors="replace") if log.is_file() else "") and "CSIM finish" in (log.read_text(errors="replace") if log.is_file() else "")),
        ("Functional: LS TB golden match", "testbench exit code: 0" in (log.read_text(errors="replace") if log.is_file() else "")),
        ("Trace capture", "TRACE OK:" in (log.read_text(errors="replace") if log.is_file() else "")),
        ("trace.pkl written", (sol / "trace.pkl").is_file()),
    ]

    done = 0
    for label, ok in rows:
        mark = "DONE" if ok else "...."
        if ok:
            done += 1
        print(f"  [{mark}] {label}")
    print(f"\nProgress: {done}/{len(rows)}")

    trace_lines = _grep(log, "TRACE ")
    if trace_lines:
        print("\nTrace resolution:")
        for ln in trace_lines[-3:]:
            print(f"  {ln}")

    tb_rc = [ln for ln in _grep(log, "testbench exit code:")]
    if tb_rc:
        print(f"\nLatest: {tb_rc[-1]}")

    objcopy = [ln for ln in _grep(log, "objcopy") if "gcn_layer_stream" in ln]
    if objcopy:
        sym = objcopy[-1]
        if "ap_uintILi16E" in sym:
            print("\nWARN: objcopy still shows ap_uint<16> — stale build")
        elif "PKt" in sym:
            print("\nOK: objcopy shows uint16_t (PKt) top signature")

    if (sol / "trace.pkl").is_file():
        print(f"\ntrace.pkl: { (sol / 'trace.pkl').stat().st_size } bytes")
    else:
        print("\ntrace.pkl: missing")

    print("\nCurrent blocker: instrumented kernel runs but Y stays zero → FIFO seam or pointer/map issue")
    print("Next: paste output of  bash orchestration_engine/run_ls_tb_rerun.sh")
    return 0


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    log = repo / "ls_probe.log"
    sol = repo / "gcn_stream_proj/sol1"
    if len(sys.argv) > 1:
        sol = Path(sys.argv[1])
    return report(repo, log, sol)


if __name__ == "__main__":
    sys.exit(main())
