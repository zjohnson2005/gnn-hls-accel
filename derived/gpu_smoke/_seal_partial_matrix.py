"""One-shot diagnostic seal for the crashed gpu_only matrix. Not a harness."""
from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[2]
smoke = root / "derived" / "gpu_smoke"
tag = "gpu_only_matrix"
ctx = "ssh_foreground"
arms = ["A", "gpu_only"]
ns = [2000, 12000]
repeats = 3

run_id = str(uuid.uuid4())
out = smoke / f"matrix_partial_{run_id}"
out.mkdir(parents=True, exist_ok=False)
cells_dir = out / "cells"
cells_dir.mkdir()

plan_path = smoke / f"{tag}_plan.json"
plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))

# Verbatim Windows PowerShell exception text for the failing statement
# tools/run_gpu_only_matrix.ps1:279  $plan.cells = @($cellRecords)
exception_text = "System.ArgumentException: Argument types do not match"

manifest_cells: list[dict] = []
summary_cells: list[dict] = []
a_12000_decode: list[dict] = []

for n in ns:
    for r in range(repeats):
        for arm in arms:
            name = f"{tag}_{ctx}_arm{arm}_n{n}_r{r}.json"
            src = smoke / name
            if not src.is_file():
                raise SystemExit(f"missing cell {name}")
            rec = json.loads(src.read_text(encoding="utf-8"))
            # Harness repeat index: smoke_gpu_exec.ps1 -Repeat -> filename _r{N}.
            if not src.name.endswith(f"_r{r}.json"):
                raise SystemExit(f"repeat mismatch: {src.name} vs r={r}")
            dest = cells_dir / name
            shutil.copy2(src, dest)
            sha = hashlib.sha256(dest.read_bytes()).hexdigest()
            cell = {
                "arm_id": rec.get("arm_id", arm),
                "n_tokens": rec.get("n_tokens", n),
                "repeat_index": r,
                "repeat_index_source": (
                    "smoke_gpu_exec.ps1 -Repeat -> artifact filename _r{N} "
                    "(no repeat field inside cell JSON)"
                ),
                "process_id": rec.get("process_id"),
                "timestamp_utc": rec.get("timestamp_utc"),
                "classification": rec.get("classification"),
                "artifact": str(dest.relative_to(out)).replace("\\", "/"),
                "artifact_sha256": sha,
                "peak_ws_bytes": rec.get("peak_ws_bytes"),
                "free_physical_at_peak": rec.get("free_physical_at_peak"),
                "prefill_s": rec.get("prefill_s"),
                "decode_tok_s": rec.get("decode_tok_s"),
                "kv_bytes_expected": rec.get("kv_bytes_expected"),
                "execute_ok": rec.get("execute_ok"),
                "compile_ok": rec.get("compile_ok"),
            }
            manifest_cells.append(cell)
            summary_cells.append(
                {
                    "arm_id": cell["arm_id"],
                    "n_tokens": cell["n_tokens"],
                    "repeat_index": cell["repeat_index"],
                    "process_id": cell["process_id"],
                    "timestamp_utc": cell["timestamp_utc"],
                    "classification": cell["classification"],
                    "decode_tok_s": cell["decode_tok_s"],
                    "prefill_s": cell["prefill_s"],
                    "peak_ws_bytes": cell["peak_ws_bytes"],
                }
            )
            if arm == "A" and n == 12000:
                a_12000_decode.append(
                    {
                        "repeat_index": r,
                        "decode_tok_s": rec.get("decode_tok_s"),
                        "process_id": rec.get("process_id"),
                        "timestamp_utc": rec.get("timestamp_utc"),
                        "peak_ws_bytes": rec.get("peak_ws_bytes"),
                    }
                )

shutil.copy2(plan_path, out / "gpu_only_matrix_plan_as_found.json")

manifest = {
    "run_id": run_id,
    "status": "PARTIAL",
    "kind": "gpu_only_matrix",
    "seal_style": "derived_diagnostic",
    "sealed_utc": datetime.now(timezone.utc).isoformat(),
    "termination_reason": {
        "class": "aggregation_crash",
        "exception_type": "System.ArgumentException",
        "exception_text_verbatim": exception_text,
        "failing_file": "tools/run_gpu_only_matrix.ps1",
        "failing_line": 279,
        "failing_statement": "$plan.cells = @($cellRecords)",
        "argument": "$cellRecords",
        "argument_runtime_type": "System.Collections.Generic.List[object]",
        "null_field": None,
        "note": (
            "No console transcript retained under derived/ for the live SSH run. "
            "Exception text reproduced post-hoc by executing the same statement "
            "($plan.cells = @($cellRecords) with Generic.List[object] of OrderedDictionary "
            "cells) in Windows PowerShell after all 12 cell artifacts were already on disk; "
            "plan.json cells array remained empty and ended_utc was never written, matching "
            "a crash at this assignment before ConvertTo-Json / Invoke-Report."
        ),
        "reproduced_utc": datetime.now(timezone.utc).isoformat(),
    },
    "matrix": {
        "tag": tag,
        "launch_context": ctx,
        "arms": arms,
        "n_tokens": ns,
        "repeats": repeats,
        "plan_started_utc": plan.get("started_utc"),
        "plan_ssh_client": plan.get("ssh_client"),
        "plan_ssh_connection": plan.get("ssh_connection"),
        "pre_run_settle_s": plan.get("pre_run_settle_s"),
        "recovery_settle_s": plan.get("recovery_settle_s"),
        "cells_completed": len(manifest_cells),
        "cells_expected": len(arms) * len(ns) * repeats,
        "report_step_reached": False,
    },
    "cells": manifest_cells,
}

summary = {
    "run_id": run_id,
    "status": "PARTIAL",
    "kind": "gpu_only_matrix",
    "cells_completed": len(summary_cells),
    "termination_reason_exception_text_verbatim": exception_text,
    "arm_A_n12000_decode_tok_s": a_12000_decode,
    "cells": summary_cells,
}

(out / "manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
)
(out / "summary.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
)
print(f"run_id={run_id}")
print(f"out={out}")
print("A n=12000 decode_tok_s:")
for row in a_12000_decode:
    print(f"  r={row['repeat_index']} decode_tok_s={row['decode_tok_s']}")
