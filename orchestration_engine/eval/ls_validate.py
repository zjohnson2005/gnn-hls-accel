"""Compare Vitis cosim cycle counts with LightningSim (C1 GCN + C2 OE)."""

import argparse
import json
import sys
from pathlib import Path

OE_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = OE_ROOT / "characterization" / "out" / "phase2"
REPO = OE_ROOT.parent

C1_THRESHOLD = 5.0
C2_THRESHOLD = 15.0  # cross-toolchain: 2025.2.1 OE cosim vs 2023.1 LS trace


def _read_json(path):
    path = Path(path)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _eval_matches_dse(captured, dse):
    """Eval JSON must come from the same solution the DSE trace ran on."""
    from orchestration_engine.phase2_gate.ls_gate import resolve_solution_dir

    eval_sol = resolve_solution_dir(captured.get("solution_dir"), REPO)
    dse_sol = resolve_solution_dir(dse.get("solution_dir"), REPO)
    return eval_sol is not None and dse_sol is not None and eval_sol == dse_sol


def _ls_gcn_latency():
    from orchestration_engine.phase2_gate.ls_gate import dse_report_valid

    ok, detail = dse_report_valid(OUT_DIR / "dse_report.json", REPO)
    if not ok:
        return None, "invalid dse_report.json: {0}".format(detail)

    captured = _read_json(OUT_DIR / "ls_gcn_eval.json")
    if not captured or captured.get("lightningsim_cycles") is None:
        return None, "missing ls_gcn_eval.json — run run_ls_validate_gcn.sh (no live-eval fallback)"

    dse = _read_json(OUT_DIR / "dse_report.json")
    if not _eval_matches_dse(captured, dse):
        return None, (
            "ls_gcn_eval.json solution_dir does not match dse_report.json trace solution "
            "— rerun run_ls_validate_gcn.sh"
        )
    return int(captured["lightningsim_cycles"]), str(OUT_DIR / "ls_gcn_eval.json")


def _ls_oe_latency():
    from orchestration_engine.phase2_gate.ls_gate import dse_report_valid

    ok, detail = dse_report_valid(OUT_DIR / "dse_report_oe.json", REPO)
    if not ok:
        return None, "invalid dse_report_oe.json: {0}".format(detail)

    dse = _read_json(OUT_DIR / "dse_report_oe.json")
    captured = _read_json(OUT_DIR / "ls_oe_eval.json")
    if captured and captured.get("lightningsim_cycles") is not None:
        if _eval_matches_dse(captured, dse):
            return int(captured["lightningsim_cycles"]), str(OUT_DIR / "ls_oe_eval.json")
        return None, (
            "ls_oe_eval.json solution_dir does not match dse_report_oe.json trace solution "
            "— rerun run_phase2_lightningsim_oe.sh"
        )

    if dse and dse.get("baseline_max_latency") is not None:
        return int(dse["baseline_max_latency"]), str(OUT_DIR / "dse_report_oe.json") + " baseline_max_latency"
    return None, "run ls_capture_oe_eval after C2 DSE"


def _find_gcn_vitis_cycles(mode):
    from orchestration_engine.phase2_gate.ls_gate import gcn_ls_cosim_json_valid

    if mode == "ls_lite":
        cached = _read_json(OUT_DIR / "cosim_gcn_stream_ls.json")
        if cached and cached.get("latency_cycles") is not None:
            ok, detail = gcn_ls_cosim_json_valid(cached)
            if ok:
                return int(cached["latency_cycles"]), str(OUT_DIR / "cosim_gcn_stream_ls.json")
            return None, "{0} ({1})".format(OUT_DIR / "cosim_gcn_stream_ls.json", detail)
        root = REPO / "gcn_stream_ls_cosim_proj"
    else:
        cached = _read_json(OUT_DIR / "cosim_gcn_stream.json")
        if cached and cached.get("passed") and cached.get("latency_cycles") is not None:
            return int(cached["latency_cycles"]), str(OUT_DIR / "cosim_gcn_stream.json")
        root = REPO / "gcn_stream_cosim_proj"

    reports = list(root.glob("**/sim/report/*_cosim.rpt")) if root.exists() else []
    if not reports:
        return None, "bash orchestration_engine/run_ls_validate_gcn.sh"

    from orchestration_engine.phase2_gate.cosim_parser import parse_cosim_report

    rep = parse_cosim_report(sorted(reports)[0])
    if rep.passed and rep.latency_cycles is not None:
        return int(rep.latency_cycles), str(sorted(reports)[0])
    return None, str(sorted(reports)[0])


def _oe_vitis_scatter_cycles():
    scatter = _read_json(OUT_DIR / "cosim_stream.json")
    if not scatter or not scatter.get("passed"):
        return None, str(OUT_DIR / "cosim_stream.json") + " (need passed cosim)"
    lat = scatter.get("per_transaction_cycles") or scatter.get("latency_cycles")
    if lat is None:
        return None, "cosim_stream.json missing cycle count"
    return float(lat), str(OUT_DIR / "cosim_stream.json")


def _row(name, vitis_cycles, ls_cycles, vitis_source, ls_source, comparison):
    if vitis_cycles is None or ls_cycles is None:
        return {
            "kernel": name,
            "comparison": comparison,
            "vitis_cycles": vitis_cycles,
            "lightningsim_cycles": ls_cycles,
            "delta_cycles": None,
            "error_percent": None,
            "vitis_source": vitis_source,
            "ls_source": ls_source,
            "status": "pending",
        }
    delta = float(ls_cycles) - float(vitis_cycles)
    err = 100.0 * delta / float(vitis_cycles) if vitis_cycles else None
    return {
        "kernel": name,
        "comparison": comparison,
        "vitis_cycles": vitis_cycles,
        "lightningsim_cycles": ls_cycles,
        "delta_cycles": delta,
        "error_percent": round(err, 3) if err is not None else None,
        "vitis_source": vitis_source,
        "ls_source": ls_source,
        "status": "ok",
    }


def _gate_ok(rows, kernel, threshold):
    for r in rows:
        if r.get("kernel") != kernel or not r.get("counts_for_gate", True):
            continue
        if r.get("status") != "ok":
            return False, None
        err = r.get("error_percent")
        if err is None or abs(err) > threshold:
            return False, err
        return True, err
    return False, None


def _purge_stale_gcn_cosim_json():
    from orchestration_engine.phase2_gate.ls_gate import gcn_ls_cosim_json_valid

    path = OUT_DIR / "cosim_gcn_stream_ls.json"
    cached = _read_json(path)
    if not cached:
        return
    ok, detail = gcn_ls_cosim_json_valid(cached)
    if ok:
        return
    try:
        path.unlink()
    except OSError:
        pass
    eval_path = OUT_DIR / "ls_gcn_eval.json"
    if eval_path.is_file():
        try:
            eval_path.unlink()
        except OSError:
            pass
    print(
        "Removed stale cosim_gcn_stream_ls.json ({0}) — rerun run_ls_validate_gcn.sh".format(
            detail
        ),
        file=sys.stderr,
    )


def build_validation(mode):
    rows = []

    ls_gcn, ls_gcn_src = _ls_gcn_latency()
    vitis_gcn, vitis_gcn_src = _find_gcn_vitis_cycles(mode)
    c1_row = _row(
        "gcn_stream",
        vitis_gcn,
        ls_gcn,
        vitis_gcn_src,
        ls_gcn_src,
        "C1: GNN_LS_LITE Vitis cosim vs LS eval (same RTL stamp, {0}% max)".format(C1_THRESHOLD),
    )
    c1_row["counts_for_gate"] = True
    c1_row["threshold_percent"] = C1_THRESHOLD
    rows.append(c1_row)

    vitis_oe, vitis_oe_src = _oe_vitis_scatter_cycles()
    ls_oe, ls_oe_src = _ls_oe_latency()
    c2_row = _row(
        "oe_hls_scatter_stream",
        vitis_oe,
        ls_oe,
        vitis_oe_src,
        ls_oe_src,
        "C2: OE scatter cosim (2025.2.1) vs LS on OE trace (2023.1, {0}% max cross-build)".format(
            C2_THRESHOLD
        ),
    )
    c2_row["counts_for_gate"] = True
    c2_row["threshold_percent"] = C2_THRESHOLD
    rows.append(c2_row)

    thesis = _read_json(OUT_DIR / "cosim_gcn_stream.json")
    if thesis and thesis.get("latency_cycles") is not None:
        t_row = _row(
            "gcn_stream_thesis_apfixed_e2",
            int(thesis["latency_cycles"]),
            ls_gcn,
            str(OUT_DIR / "cosim_gcn_stream.json"),
            ls_gcn_src,
            "E2 hardware anchor only — not LightningSim validation",
        )
        t_row["counts_for_gate"] = False
        rows.append(t_row)

    return rows


def main():
    parser = argparse.ArgumentParser(description="LightningSim effectiveness (C1 + C2)")
    parser.add_argument("--mode", choices=("ls_lite", "thesis_cross"), default="ls_lite")
    parser.add_argument("--output", type=Path, default=OUT_DIR / "ls_validation.json")
    args = parser.parse_args()

    _purge_stale_gcn_cosim_json()
    rows = build_validation(args.mode)
    c1_ok, c1_err = _gate_ok(rows, "gcn_stream", C1_THRESHOLD)
    c2_ok, c2_err = _gate_ok(rows, "oe_hls_scatter_stream", C2_THRESHOLD)

    from orchestration_engine.phase2_gate.ls_gate import dse_report_valid

    dse_gcn_ok, dse_gcn_detail = dse_report_valid(OUT_DIR / "dse_report.json", REPO)
    dse_oe_ok, dse_oe_detail = dse_report_valid(OUT_DIR / "dse_report_oe.json", REPO)

    payload = {
        "mode": args.mode,
        "c1_threshold_percent": C1_THRESHOLD,
        "c2_threshold_percent": C2_THRESHOLD,
        "rows": rows,
        "c1_passed": c1_ok and dse_gcn_ok,
        "c2_passed": c2_ok and dse_oe_ok,
        "passed": c1_ok and c2_ok and dse_gcn_ok and dse_oe_ok,
        "gcn_stream_validated": c1_ok and dse_gcn_ok,
        "oe_scatter_validated": c2_ok and dse_oe_ok,
        "dse_gcn_valid": dse_gcn_ok,
        "dse_gcn_detail": dse_gcn_detail,
        "dse_oe_valid": dse_oe_ok,
        "dse_oe_detail": dse_oe_detail,
        "note": (
            "Thesis requires C1 (GCN cosim vs LS) and C2 (OE cosim vs LS on traced OE engine) "
            "with trace-backed dse_report*.json (source=lightningsim only). "
            "Synthetic/offline DSE never satisfies the gate."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))

    if not payload["passed"]:
        if not dse_gcn_ok:
            print("BLOCKED: dse_report.json invalid — {0}".format(dse_gcn_detail), file=sys.stderr)
        if not dse_oe_ok:
            print("BLOCKED: dse_report_oe.json invalid — {0}".format(dse_oe_detail), file=sys.stderr)
        if not c1_ok:
            msg = "C1 FAILED (threshold {0}%, err={1})".format(C1_THRESHOLD, c1_err)
            for r in rows:
                if r.get("kernel") != "gcn_stream":
                    continue
                if r.get("status") == "pending":
                    msg += " — pending vitis={0} ls={1}".format(
                        r.get("vitis_source"), r.get("ls_source")
                    )
                elif (
                    r.get("vitis_cycles") is not None
                    and r.get("lightningsim_cycles") is not None
                    and r["vitis_cycles"] < 80
                    and r["lightningsim_cycles"] > 200
                ):
                    msg += (
                        " — Vitis {0} cyc looks like csynth min vs LS {1} cyc; "
                        "need real cosim (run_ls_validate_gcn.sh)"
                    ).format(r["vitis_cycles"], r["lightningsim_cycles"])
                break
            print(msg, file=sys.stderr)
        if not c2_ok:
            print("C2 FAILED (threshold {0}%, err={1})".format(C2_THRESHOLD, c2_err), file=sys.stderr)
        return 1
    print("LightningSim C1+C2 validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
