"""Executable WSL/debug smoke for mandatory MCP-01 transports and modes."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .analyze import analyze_root, write_aggregate
from .contracts import CellCoordinates
from .execute import execute_cell
from .figures import render_transport_cpu_figure
from .plan import build_cell_plan
from .report import append_died_claim, write_report
from .runner import McpTaxRunner
from .fixphase import evaluate_exit_criteria, render_fixphase_report
from .validate import validate_mcp_tax

REPO_ROOT = Path(__file__).resolve().parents[2]
DIED_LEDGER = Path(__file__).with_name("died_ledger.json")
MANDATORY_TRANSPORTS = ("stdio", "http_sse_tls_off", "http_sse_tls_on")
MODES = ("full", "throttle", "stripped")
IMPLEMENTATIONS = ("raw_jsonrpc", "reference_sdk")


def _plans(*, warmup: int, measured: int) -> list[Any]:
    plans = [
        build_cell_plan(
            CellCoordinates(
                transport=transport,  # type: ignore[arg-type]
                payload_bytes=256,
                schema_profile="flat_5",
                tool_count=1,
                implementation=implementation,  # type: ignore[arg-type]
                mode=mode,  # type: ignore[arg-type]
            ),
            seed=0,
            warmup_messages=warmup,
            measured_messages=measured,
        )
        for transport in MANDATORY_TRANSPORTS
        for implementation in IMPLEMENTATIONS
        for mode in MODES
    ]
    hashes = {
        tuple(plan.request_hashes()[plan.warmup_messages :]) for plan in plans
    }
    if len(hashes) != 1:
        raise RuntimeError("debug smoke plans are not canonical matched pairs")
    return plans


def _tax_summary(aggregate: Mapping[str, Any]) -> list[dict[str, Any]]:
    from .analyze import cell_steady_cpu_ns_per_message

    grouped: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = {}
    for cell in aggregate.get("cells") or []:
        coordinates = cell["coordinates"]
        key = (
            coordinates["transport"],
            coordinates["implementation"],
            coordinates["payload_bytes"],
            coordinates["schema_profile"],
            coordinates["tool_count"],
        )
        grouped.setdefault(key, {})[coordinates["mode"]] = cell
    result = []
    for key, modes in sorted(grouped.items()):
        if not {"throttle", "stripped"} <= set(modes):
            continue
        throttle = cell_steady_cpu_ns_per_message(modes["throttle"])
        stripped = cell_steady_cpu_ns_per_message(modes["stripped"])
        result.append(
            {
                "transport": key[0],
                "implementation": key[1],
                "throttle_cpu_ns_per_message": throttle,
                "stripped_cpu_ns_per_message": stripped,
                "throttle_minus_stripped_ns_per_message": throttle - stripped,
                "excludes_session_setup": True,
            }
        )
    return result


def _record_streamable_status() -> None:
    claim = "Streamable HTTP is admitted to the MCP-01 primary matrix"
    corrected = (
        "symbol probe positive on pinned SDK; executable cross-arm smoke not executed"
    )
    ledger = json.loads(DIED_LEDGER.read_text(encoding="utf-8"))
    if any(
        entry.get("claim") == claim and corrected in (entry.get("evidence") or [])
        for entry in ledger.get("entries") or []
    ):
        return
    append_died_claim(
        DIED_LEDGER,
        claim=claim,
        reason=(
            "Out of scope for MCP-01: stable SDK symbols alone are insufficient; "
            "the executable cross-arm smoke has not passed for this transport."
        ),
        evidence=[corrected],
    )


def _record_fixphase_ledger() -> None:
    retired = [
        (
            "Per-cell TLS fixture creation for MCP-01 matrix runs",
            "Replaced by one CA/certificate set scoped to the run root and passed "
            "into every TLS cell.",
            ["smoke aggregate previously showed multiple ca_sha256 values"],
        ),
        (
            "register_mcp_tax_hook pathway for official MCP SDK instrumentation",
            "official mcp==1.28.1 exposes no instrumentation hook API; "
            "harness-boundary timers adopted instead.",
            ["sdk_hooks.register_mcp_tax_hook unavailable on pinned SDK"],
        ),
        (
            "TLS handshake/cert CPU booked under MSG_VALIDATE",
            "Retired in mcp_tax_v1.2: TLS handshake books MSG_TRANSPORT_CPU "
            "(provenance transport_tls_handshake). MSG_VALIDATE is JSON Schema "
            "validation only so the DFA amenability claim is not crypto-contaminated.",
            [
                "transport_instrument.validate previously booked MSG_VALIDATE",
                "replaced by tls_handshake -> MSG_TRANSPORT_CPU",
            ],
        ),
    ]
    ledger = json.loads(DIED_LEDGER.read_text(encoding="utf-8"))
    existing = {entry.get("claim") for entry in ledger.get("entries") or []}
    for claim, reason, evidence in retired:
        if claim in existing:
            continue
        append_died_claim(DIED_LEDGER, claim=claim, reason=reason, evidence=evidence)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--debug-smoke",
        action="store_true",
        help="required acknowledgement that reduced WSL runs are debug_only",
    )
    parser.add_argument("--warmup-messages", type=int, default=1)
    parser.add_argument("--measured-messages", type=int, default=20)
    parser.add_argument("--output-root", type=Path)
    args = parser.parse_args()
    if not args.debug_smoke:
        parser.error("--debug-smoke is required; smoke can never be publication data")
    if args.warmup_messages < 0 or args.measured_messages < 1:
        parser.error("warmup must be non-negative and measured must be positive")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_root = args.output_root or (
        REPO_ROOT / "apu_characterization" / "out" / "mcp_tax" / f"debug_smoke_{stamp}"
    )
    run_root = output_root / "runs"
    plans = _plans(
        warmup=args.warmup_messages, measured=args.measured_messages
    )
    outcomes = McpTaxRunner(run_root=run_root, execute=execute_cell).run(
        plans, resume=True
    )
    aggregate = analyze_root(run_root, workers=1)
    aggregate["result_validity"] = "debug_only"
    aggregate["debug_smoke"] = {
        "explicit_override": True,
        "warmup_messages": args.warmup_messages,
        "measured_messages": args.measured_messages,
        "canonical_matched_pair_sha256": plans[0].request_hashes()[
            plans[0].warmup_messages :
        ],
        "throttle_stripped_tax": _tax_summary(aggregate),
    }
    aggregate_path = output_root / "mcp_tax_debug_aggregate.json"
    write_aggregate(aggregate_path, aggregate)
    _record_streamable_status()
    _record_fixphase_ledger()
    write_report(
        output_root / "mcp_tax_debug_report.md",
        aggregate,
        died_ledger_path=DIED_LEDGER,
        aggregate_name=aggregate_path.name,
    )
    figure_path = output_root / "mcp_tax_debug_figure.png"
    try:
        render_transport_cpu_figure(aggregate, figure_path)
        figure_status = str(figure_path)
    except ImportError as exc:
        figure_status = f"not generated: {exc}"
    checks = evaluate_exit_criteria(aggregate)
    fixphase_path = output_root / "mcp_tax_fixphase_report.md"
    fixphase_path.write_text(
        render_fixphase_report(aggregate, checks=checks, output_root=output_root),
        encoding="utf-8",
    )
    errors = validate_mcp_tax(aggregate, debug_smoke=True)
    print(f"output_root={output_root}")
    print(
        "completed_runs="
        f"{sum(item.status in {'completed', 'skipped_complete'} for item in outcomes)}"
    )
    print(f"canonical_matched_pairs={len(plans)}")
    print(f"throttle_stripped_pairs={len(aggregate['debug_smoke']['throttle_stripped_tax'])}")
    print(f"figure={figure_status}")
    if errors:
        raise SystemExit("debug smoke validation failed: " + "; ".join(errors))
    print("debug_smoke_validation=PASS")


if __name__ == "__main__":
    main()
