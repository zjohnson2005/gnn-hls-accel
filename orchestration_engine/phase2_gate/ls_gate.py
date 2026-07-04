"""Strict validators for LightningSim / DSE artifacts (no synthetic shortcuts)."""

import json
from pathlib import Path

OE_ROOT = Path(__file__).resolve().parents[1]
REPO = OE_ROOT.parent
OUT_DIR = OE_ROOT / "characterization" / "out" / "phase2"


def _read_json(path):
    path = Path(path)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def resolve_solution_dir(solution_dir_str, repo=None):
    repo = repo or REPO
    if not solution_dir_str:
        return None
    sol = Path(solution_dir_str)
    if not sol.is_absolute():
        sol = (repo / sol).resolve()
    return sol


def gcn_ls_cosim_json_valid(data):
    """True only for real GNN_LS_LITE cosim (not csynth-only poison)."""
    if not data or data.get("latency_cycles") is None:
        return False, "missing latency_cycles"
    if not data.get("passed"):
        return False, "cosim did not pass"
    if data.get("status") == "csynth_only":
        return False, "csynth_only is not valid for C1"
    report_path = (data.get("report_path") or "").replace("\\", "/")
    if "cosim.rpt" not in report_path:
        return False, "report_path must reference *_cosim.rpt (got {0!r})".format(
            data.get("report_path")
        )
    return True, "ok"


def dse_report_valid(path, repo=None):
    """Return (ok, detail) — True only for trace-backed LightningSim DSE."""
    path = Path(path)
    data = _read_json(path)
    if data is None:
        return False, "missing or unreadable {0}".format(path)

    source = data.get("source")
    if source != "lightningsim":
        return False, "reject source={0!r} (need lightningsim)".format(source)

    deadlocks = data.get("deadlocks")
    if deadlocks not in (0, None):
        return False, "reject deadlocks={0}".format(deadlocks)

    sol = resolve_solution_dir(data.get("solution_dir"), repo)
    if sol is None:
        return False, "missing solution_dir"

    trace = sol / "trace.pkl"
    if not trace.is_file():
        return False, "missing {0}".format(trace)

    baseline = data.get("baseline_max_latency")
    detail = "{0} baseline={1} cyc trace={2}".format(
        path.name,
        baseline if baseline is not None else "?",
        sol.name,
    )
    return True, detail


def ls_validation_passed(path=None):
    path = Path(path or OUT_DIR / "ls_validation.json")
    data = _read_json(path)
    if not data:
        return False, "missing ls_validation.json"
    if not data.get("passed"):
        return False, str(path)
    return True, "C1+C2 within threshold"


def gcn_e2_cosim_done(path=None):
    path = Path(path or OUT_DIR / "cosim_gcn_stream.json")
    data = _read_json(path)
    if not data or not data.get("passed"):
        return False, "bash orchestration_engine/run_gcn_stream_cosim.sh"
    lat = data.get("latency_cycles")
    if lat is None:
        return False, "missing latency_cycles"
    return True, "E2 thesis cosim {0} cyc".format(lat)
