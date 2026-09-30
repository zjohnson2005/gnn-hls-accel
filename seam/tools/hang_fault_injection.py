"""Kill a stub child that writes a result and spins, then continue the bisection."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.tools.delta_n import HANG_DISPOSITION, run_child  # noqa: E402
from tools.boot4_session import bisect_holds  # noqa: E402


def run_fault_injection() -> dict[str, Any]:
    """One hung high rung, then the search attempts the next rung."""
    with tempfile.TemporaryDirectory(prefix="hang-fault-") as tmp:
        work = Path(tmp)
        tag = "hang"
        out_path = work / f"{tag}.result.json"
        command = [
            sys.executable,
            "-u",
            "-m",
            "seam.tools._hang_stub_child",
            "--out",
            str(out_path),
        ]
        hung: dict[str, Any] = {}

        def attempt(n: int) -> dict[str, Any]:
            if n != 1000:
                return {"n_cached": n, "holds": True, "turn2_ttft_s": 0.01}
            record = run_child(
                root=ROOT,
                work_dir=work,
                spec={"fault_injection": True},
                timeout_s=120,
                tag=tag,
                command=command,
            )
            hung.update(record)
            return {"n_cached": n, "holds": False, "turn2_ttft_s": None}

        found = bisect_holds(low=0, high=1000, resolution=500, attempt=attempt)
    probed = [int(point["n_cached"]) for point in found["points"]]
    continued = len(probed) >= 3 and probed[1] == 1000
    ok = (
        hung.get("hang_disposition") == HANG_DISPOSITION
        and hung.get("outcome") == "fail"
        and hung.get("failure_mode") == "turn1:RuntimeError"
        and hung.get("kill_error") is None
        and float(hung.get("hang_duration_s") or 0) >= 30
        and float(hung.get("hang_duration_s") or 0) < 32
        and found["largest_n_cached"] == 500
        and continued
    )
    return {
        "event": "hang_fault_injection",
        "ok": ok,
        "hang_disposition": hung.get("hang_disposition"),
        "hang_duration_s": hung.get("hang_duration_s"),
        "outcome": hung.get("outcome"),
        "failure_mode": hung.get("failure_mode"),
        "probed": probed,
        "largest_n_cached": found["largest_n_cached"],
        "continued": continued,
    }


def main() -> int:
    report = run_fault_injection()
    print(json.dumps(report, sort_keys=True), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
