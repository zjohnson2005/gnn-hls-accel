#!/usr/bin/env python3
"""Re-audit stored MCP runs for G6 v10.1 without re-execution."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from apu_characterization.mcp_tax.analyze import _load_endpoint, _load_json
from apu_characterization.mcp_tax.audit import audit_run, endpoint_totals
from apu_characterization.mcp_tax.taxonomy import McpCategory

REPO = Path(__file__).resolve().parents[2]
P512_ROOT = REPO / "apu_characterization/out/mcp_tax/fixphase_resmoke_v10_p512/runs"
V10_ROOT = REPO / "apu_characterization/out/mcp_tax/fixphase_resmoke_v10/runs"
PRESMOKE = REPO / "apu_characterization/out/mcp_tax/fixphase_resmoke_v10/presmoke_answers.json"

P512_SUFFIX = "p-524288__s-flat_5__n-1__i-raw_jsonrpc__m-throttle"
SMOKE_STDIO_CELLS = (
    "t-stdio__p-256__s-flat_5__n-1__i-raw_jsonrpc__m-throttle",
    "t-stdio__p-256__s-flat_5__n-1__i-raw_jsonrpc__m-full",
)
TRANSPORTS = ("stdio", "http_sse_tls_off", "http_sse_tls_on")


def _message_provenance_transport(client: dict[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    prov = client.get("provenance") or client.get("provenance_cpu") or []
    if isinstance(prov, dict):
        items = []
        for mid, per_cat in prov.items():
            if isinstance(per_cat, dict):
                cat = per_cat.get(McpCategory.MSG_TRANSPORT_CPU.value) or per_cat.get(
                    "MSG_TRANSPORT_CPU"
                )
                if isinstance(cat, dict):
                    for name, amount in cat.items():
                        out[str(name)] = out.get(str(name), 0.0) + float(amount)
        return out
    if isinstance(prov, list):
        for item in prov:
            if not isinstance(item, dict):
                continue
            if item.get("category") not in (
                McpCategory.MSG_TRANSPORT_CPU.value,
                "MSG_TRANSPORT_CPU",
            ):
                continue
            label = str(item.get("label") or item.get("name") or "")
            out[label] = out.get(label, 0.0) + float(
                item.get("cpu_ns") or item.get("amount") or 0
            )
    messages = client.get("messages") or {}
    if isinstance(messages, dict):
        for _mid, msg in messages.items():
            if not isinstance(msg, dict):
                continue
            for key in ("provenance", "provenance_cpu"):
                block = msg.get(key)
                if not isinstance(block, dict):
                    continue
                cat_block = block.get(McpCategory.MSG_TRANSPORT_CPU.value) or block.get(
                    "MSG_TRANSPORT_CPU"
                )
                if isinstance(cat_block, dict):
                    for name, amount in cat_block.items():
                        out[str(name)] = out.get(str(name), 0.0) + float(amount)
    return out


def _lump_errors(g6_details: dict[str, Any]) -> list[str]:
    lumps: list[str] = []
    for msg in g6_details.get("messages") or []:
        if not isinstance(msg, dict):
            continue
        mid = msg.get("message_id", "?")
        for cat, info in (msg.get("dominant_provenance") or {}).items():
            if not isinstance(info, dict):
                continue
            share = float(info.get("named_provenance_share") or 1.0)
            if share < 0.80:
                lumps.append(
                    f"message {mid} category {cat}: named provenance {100 * share:.1f}%"
                )
    return lumps


def _reaudit_seed(seed_dir: Path) -> dict[str, Any]:
    plan = _load_json(seed_dir / "plan.json")
    manifest = _load_json(seed_dir / "manifest.json")
    client = _load_endpoint(seed_dir / "client")
    server = _load_endpoint(seed_dir / "server")
    audit = audit_run(client, server, plan=plan, manifest=manifest)
    g6 = audit["gates"]["G6"]
    coords = plan.get("coordinates") or manifest.get("coordinates") or {}
    client_norm = endpoint_totals(client)
    transport_cpu = client_norm["category_cpu_ns"].get(
        McpCategory.MSG_TRANSPORT_CPU.value, 0.0
    )
    measured = int(
        plan.get("measured_messages")
        or manifest.get("measured_messages")
        or len(client_norm.get("canonical_hashes") or [])
        or 1
    )
    median_transport = transport_cpu / measured if measured else transport_cpu
    prov_keys = _message_provenance_transport(client)
    g6_details = g6 if isinstance(g6, dict) else {}
    # g6 pass is in gate dict
    g6_pass = bool(g6.get("pass"))
    g6_errors = list(g6.get("errors") or [])
    cell_id = (
        manifest.get("cell_id")
        or coords.get("cell_id")
        or seed_dir.parent.name
    )
    return {
        "cell_id": cell_id,
        "transport": coords.get("transport") or seed_dir.parents[2].name,
        "mode": coords.get("mode"),
        "implementation": coords.get("implementation"),
        "payload_bytes": coords.get("payload_bytes"),
        "seed_dir": seed_dir.as_posix(),
        "G6_pass": g6_pass,
        "G6_errors": g6_errors,
        "lump_errors": _lump_errors(g6_details),
        "MSG_TRANSPORT_CPU_median_ns": median_transport,
        "provenance_MSG_TRANSPORT_CPU_keys_ns": prov_keys,
        "below_measurement_resolution": any(
            isinstance(m, dict) and m.get("below_measurement_resolution")
            for m in (g6_details.get("messages") or [])
        ),
        "audit_pass": bool(audit.get("pass")),
    }


def _find_cell_seed(runs_root: Path, transport: str, cell_name: str) -> Path:
    transport_dir = runs_root / transport
    seed = transport_dir / cell_name / "0"
    if seed.is_dir():
        return seed
    raise FileNotFoundError(f"missing seed dir for {transport}/{cell_name}")


def _find_p512_seed(runs_root: Path, transport: str) -> Path:
    transport_dir = runs_root / transport
    if not transport_dir.is_dir():
        raise FileNotFoundError(f"missing transport dir {transport_dir}")
    for cell_dir in sorted(transport_dir.iterdir()):
        if not cell_dir.is_dir():
            continue
        if P512_SUFFIX in cell_dir.name:
            seed = cell_dir / "0"
            if seed.is_dir():
                return seed
    raise FileNotFoundError(f"no p-524288 throttle raw cell under {transport_dir}")


def main() -> int:
    p512_cells: list[dict[str, Any]] = []
    print("=== p512 throttle raw 524288 (G6 re-audit) ===")
    for transport in TRANSPORTS:
        seed = _find_p512_seed(P512_ROOT, transport)
        row = _reaudit_seed(seed)
        p512_cells.append(row)
        print(f"{transport}: G6_pass={row['G6_pass']} errors={len(row['G6_errors'])}")
        for err in row["G6_errors"]:
            print(f"  - {err}")

    smoke_cells: list[dict[str, Any]] = []
    print("\n=== v10 smoke stdio raw throttle/full (G6 re-audit) ===")
    for cell_name in SMOKE_STDIO_CELLS:
        seed = _find_cell_seed(V10_ROOT, "stdio", cell_name)
        row = _reaudit_seed(seed)
        smoke_cells.append(row)
        print(
            f"{cell_name}: G6_pass={row['G6_pass']} errors={len(row['G6_errors'])}"
        )
        for err in row["G6_errors"]:
            print(f"  - {err}")

    payload = {
        "p512_throttle_raw": {
            "run_root": P512_ROOT.as_posix(),
            "cells": p512_cells,
        },
        "smoke_stdio_raw": {
            "run_root": V10_ROOT.as_posix(),
            "cells": smoke_cells,
        },
        "summary": {
            "p512_all_g6_pass": all(c["G6_pass"] for c in p512_cells),
            "smoke_stdio_raw_all_g6_pass": all(c["G6_pass"] for c in smoke_cells),
        },
    }

    if PRESMOKE.is_file():
        data = json.loads(PRESMOKE.read_text(encoding="utf-8"))
    else:
        data = {}
    data["Q3_after_g6_v10_1"] = payload
    PRESMOKE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {PRESMOKE.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
