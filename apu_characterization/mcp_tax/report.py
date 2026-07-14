"""Markdown reporting and append-only claim-death ledger for MCP-01."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import PROTOCOL_VERSION

EXTERNAL_ANCHORS = (12.4, 23.7, 8.3)
DERIVED_TURN_RANGE = (3.9, 7.0)

DISPATCH_MECHANISM_NOTE = (
    "**MSG_DISPATCH mechanism note (frozen paths):** "
    "server `MSG_DISPATCH` = method lookup / response assembly "
    "(`server_process.raw_handle`, provenance `measured`); "
    "client `client_result_dispatch` = routing `response['result']` to the call site; "
    "client `client_call_inter_region_gaps` = residual CPU inside the client call "
    "boundary not covered by nested SERIAL/FRAME/TRANSPORT/VALIDATE/result-dispatch "
    "timers. v8 raw throttle: gaps ≈99.5–99.8% of client DISPATCH; true method "
    "lookup / result routing only a few µs/msg. "
    "**Retired claim:** TurnTrace echo as method-dispatch dominance (died-ledger #6). "
    "**Surviving echo candidate:** diffuseness — cost between named regions, not "
    "inside a named dispatcher. G6 now requires named provenance ≥80% for any "
    "category >50% of booked steady CPU (opaque `measured` lumps fail). "
    "Do not quote DISPATCH as protocol-dispatch silicon; do not quote a 2–3 ms "
    "floor-class tax until v9 attributes the gaps."
)

HONEST_HEADLINE_NOTE = (
    "**Honest headline (until v9 gap split):** named, provenance-backed protocol "
    "work is ~350–450 µs/msg on stdio, ~500 µs on plain SSE, ~1.5 ms on TLS SSE "
    "(of which ~1.36 ms is connection-pattern handshake crypto). The former "
    "2–3 ms 'floor-class tax' figure is majority gap-fill of unknown nature — "
    "do not quote it. Front-rank defensible finding: connection-per-message TLS "
    "(~949 µs handshake + ~415 µs syscall under v8 throttle) — named work, "
    "deployment-relevant, software-fixable via reuse, hardware-relevant via "
    "inline TLS. Diffuse residue (~1.6 ms/msg) dominates and is under active "
    "attribution; mechanisms are pre-registered in OPEN_QUESTIONS before data."
)

CONNECTION_SEMANTICS_NOTE = (
    "**HTTP/SSE connection semantics:** the primary SSE transport opens one "
    "TCP(/TLS) connection per measured message (`Connection: close`, "
    "`HttpSseTransport.exchange` → `create_connection` + optional "
    "`tls_handshake`, then close). "
    "TLS CPU booked under `MSG_TRANSPORT_CPU` with provenance "
    "`transport_tls_handshake` is therefore a **per-message handshake tax of "
    "this connection pattern**, not AES-GCM record encryption cost on a "
    "reused session. Connection reuse would move handshake into "
    "`SESSION_SETUP` and shrink per-message TRANSPORT to syscall/record work. "
    "Label findings as connection-pattern cost; do not cite as 'TLS costs X ms/msg' "
    "without that qualifier."
)

VALIDATE_PREREG_NOTE = (
    "**MSG_VALIDATE / DFA pre-registration:** at flat_5 × 256 B × 1 tool, "
    "VALIDATE is near-free in software (~9 µs/msg). The DFA/automaton "
    "motivation for VALIDATE is deferred to the matrix axes "
    "`pathological_large` and payload up to 512 KiB. "
    "If those cells do not inflate VALIDATE, the honest MPE pitch reweights "
    "toward dispatch/routing + framing/connection-pattern crypto, and "
    "serialization+framing remain the DFA-adjacent slice. "
    "Matrix outcome is a pre-registered test of that claim, not a rescue."
)


def validity_banner(aggregate: Mapping[str, Any]) -> str:
    validity = aggregate.get("result_validity", "unknown")
    audit_pass = bool((aggregate.get("audit") or {}).get("pass"))
    if validity == "protocol_microbenchmark" and audit_pass:
        return (
            "> **VALIDITY: CONTROLLED PROTOCOL MICROBENCHMARK.** Native-Linux, "
            "clean, n=5 G1-G5 validation is still required before citation. "
            "This is not a production-agent CPU-share result."
        )
    return (
        "> **VALIDITY: DEBUG/INELIGIBLE. DO NOT CITE.** This artifact may be "
        "used only to debug the MCP-01 harness."
    )


def render_report(
    aggregate: Mapping[str, Any],
    *,
    died_ledger: Mapping[str, Any] | None = None,
    aggregate_name: str = "mcp_tax.matrix.json",
) -> str:
    cells = list(aggregate.get("cells") or [])
    audit = aggregate.get("audit") or {}
    lines = [
        validity_banner(aggregate),
        "",
        "# MCP-01 protocol-tax report",
        "",
        f"- Protocol: `{aggregate.get('protocol_version')}`",
        f"- Retained runs: **{aggregate.get('run_count', 0)}**",
        f"- Cells: **{aggregate.get('cell_count', 0)}**",
        f"- G1-G7 aggregate audit: **{'PASS' if audit.get('pass') else 'FAIL'}**",
        f"- Source aggregate: `{aggregate_name}`",
        "",
        "## Claim rung",
        "",
        _claim_rung(aggregate),
        "",
        "The allowed claim is per-message MCP protocol/transport tax only. It is "
        "not production agent CPU share, model cost, tool-body cost, or production latency.",
        "",
        "## Observer-effect bracket",
        "",
    ]
    lines.extend(_band_lines(cells))
    lines.extend(["", "## Steady-state category decomposition", ""])
    lines.extend(_category_table(cells))
    lines.extend(["", DISPATCH_MECHANISM_NOTE, ""])
    lines.extend(["", HONEST_HEADLINE_NOTE, ""])
    lines.extend(["", CONNECTION_SEMANTICS_NOTE, ""])
    lines.extend(["", VALIDATE_PREREG_NOTE, ""])
    lines.extend(["", "## Provenance breakdown (inspectable)", ""])
    lines.extend(_provenance_tables(cells))
    lines.extend(["", "## Gap decomposition (v9)", ""])
    lines.extend(_gap_decomposition_section(aggregate, cells))
    lines.extend(["", "## One-time session setup", ""])
    lines.extend(_setup_table(cells))
    lines.extend(["", "## Category coverage by arm", ""])
    lines.extend(_coverage_table(cells))
    lines.extend(["", "## CPU / wait split", ""])
    lines.extend(_cpu_wait_table(cells))
    lines.extend(["", "## SDK minus raw (setup vs steady)", ""])
    lines.extend(_sdk_raw_table(aggregate.get("sdk_raw_delta") or []))
    lines.extend(["", "## Bare-metal validation flags", ""])
    lines.extend(_bare_metal_flags(aggregate))
    lines.extend(["", "## Gate matrix", ""])
    lines.extend(_gate_matrix(audit))
    g4 = (audit.get("gates") or {}).get("G4") or {}
    observer_cells = g4.get("observer_cells")
    if observer_cells is not None:
        lines.extend(
            [
                "",
                "G4 evaluated the protocol observer subsample (20% of primary bases). "
                f"Eligible observer bases in this aggregate: **{observer_cells}**. "
                "Debug smoke may exercise all three modes on every transport×implementation "
                "without satisfying that subsample count.",
            ]
        )
    diagnostics = aggregate.get("diagnostics") or {}
    if diagnostics:
        lines.extend(["", "## Audit diagnostics (non-gating)", ""])
        lines.append(
            f"- TLS CA fingerprints: {len(diagnostics.get('tls_ca_fingerprints') or [])} "
            f"(unique across run root: {diagnostics.get('tls_ca_unique')})"
        )
        zero_bytes = diagnostics.get("zero_byte_messages") or []
        lines.append(f"- Zero-byte measured messages flagged: {len(zero_bytes)}")
        outliers = diagnostics.get("wait_outliers") or []
        lines.append(f"- Wait outliers (>10× cell median): {len(outliers)}")
    lines.extend(
        [
            "",
            "## Scaling results",
            "",
            f"- Payload exponent fits: {len(aggregate.get('payload_exponents') or [])}.",
            f"- Tool-count setup-curve points: {len(aggregate.get('setup_tool_count_curve') or [])}.",
            f"- Matched SDK-minus-raw steady/setup delta pairs: "
            f"{len(aggregate.get('sdk_raw_delta') or [])}.",
            "",
            "## External anchors and derived composite",
            "",
            "**External anchors — not measured by MCP-01:** 12.4 ms/message "
            "(stdio), 23.7 ms/message (HTTP/SSE), and 8.3 ms/message "
            "(authentication extension). They are contextual inputs only and "
            "must never be presented as results from this artifact.",
            "",
            "The external TurnTrace agent-level strict-floor range is "
            "**3.9–7.0 ms/turn**. "
            "The only permitted composition is:",
            "",
            "`derived_total_per_turn = external_baseline_(3.9_to_7.0) + "
            "calls_per_turn * measured_MCP_tax_per_call`",
            "",
            "Keep `calls_per_turn` explicit; MCP-01 does not measure or assume it.",
            "",
            "## Died / retired claims (append-only)",
            "",
        ]
    )
    lines.extend(_ledger_lines(died_ledger or {"entries": []}))
    return "\n".join(lines).rstrip() + "\n"


def write_report(
    path: Path,
    aggregate: Mapping[str, Any],
    *,
    died_ledger_path: Path | None = None,
    aggregate_name: str = "mcp_tax.matrix.json",
) -> None:
    ledger = (
        json.loads(died_ledger_path.read_text(encoding="utf-8"))
        if died_ledger_path and died_ledger_path.is_file()
        else {"entries": []}
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_report(aggregate, died_ledger=ledger, aggregate_name=aggregate_name),
        encoding="utf-8",
    )


def append_died_claim(
    ledger_path: Path,
    *,
    claim: str,
    reason: str,
    evidence: Sequence[str] = (),
) -> dict[str, Any]:
    """Append one immutable ledger entry; existing entries are never rewritten."""
    ledger = (
        json.loads(ledger_path.read_text(encoding="utf-8"))
        if ledger_path.is_file()
        else {
            "protocol_version": PROTOCOL_VERSION,
            "entries": [],
            "policy": "Append-only. Retire unsupported claims or arms with evidence; never delete prior entries.",
        }
    )
    entries = ledger.setdefault("entries", [])
    entry = {
        "id": len(entries) + 1,
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "claim": claim,
        "reason": reason,
        "evidence": list(evidence),
    }
    entries.append(entry)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    return entry


def _claim_rung(aggregate: Mapping[str, Any]) -> str:
    if (
        aggregate.get("result_validity") == "protocol_microbenchmark"
        and (aggregate.get("audit") or {}).get("pass")
    ):
        return (
            "**Rung 1 — controlled protocol microbenchmark:** protocol tax may be "
            "reported after the standalone validator confirms native Linux, clean "
            "git, pins, all gates, and n=5. Quote named provenance-backed work and "
            "connection-pattern TLS; do not quote gap-dominated aggregates as "
            "floor-class tax until gap attribution lands."
        )
    return (
        "**Rung 0 — smoke/debug:** no quantitative publication claim is licensed. "
        "Earned narrative shape only: named protocol work is sub-ms at benign "
        "points; connection-pattern TLS adds ~1.3 ms/msg under connection-per-message "
        "HTTP/SSE; ~1.6 ms/msg diffuse residue dominates and awaits v9 attribution. "
        "Do not cite 2–3 ms floor-class tax."
    )


def _band_lines(cells: Sequence[Mapping[str, Any]]) -> list[str]:
    from .analyze import cell_steady_cpu_ns_per_message

    by_key: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = {}
    for cell in cells:
        coordinates = cell.get("coordinates") or {}
        key = tuple(
            coordinates.get(field)
            for field in (
                "transport",
                "payload_bytes",
                "schema_profile",
                "tool_count",
                "implementation",
            )
        )
        by_key.setdefault(key, {})[str(coordinates.get("mode"))] = cell
    pairs = [
        (modes["stripped"], modes["throttle"])
        for modes in by_key.values()
        if "stripped" in modes and "throttle" in modes
    ]
    if not pairs:
        return [
            "No matched stripped/throttle observer pair is available. The strict "
            "observer bracket is therefore not estimable."
        ]
    stripped = sorted(cell_steady_cpu_ns_per_message(pair[0]) for pair in pairs)
    throttle = sorted(cell_steady_cpu_ns_per_message(pair[1]) for pair in pairs)
    return [
        "Matched **steady-state** process-CPU medians across observer pairs "
        "(SESSION_SETUP excluded): "
        f"**stripped {_median(stripped) / 1000:.3f} µs/message; "
        f"throttle {_median(throttle) / 1000:.3f} µs/message**.",
        "This is an observer-effect bracket, not an ordered confidence interval "
        "or protocol floor. Negative paired throttle-minus-stripped values are "
        "retained. Full instrumentation is observer-only and is never promoted. "
        "One-time SESSION_SETUP is reported separately and is not part of this bracket.",
    ]


def _category_table(cells: Sequence[Mapping[str, Any]]) -> list[str]:
    primary = [
        cell
        for cell in cells
        if (cell.get("coordinates") or {}).get("mode") == "throttle"
        and int((cell.get("coordinates") or {}).get("tool_count", 0)) == 1
        and (cell.get("coordinates") or {}).get("implementation") == "raw_jsonrpc"
    ]
    if not primary:
        return ["No raw_jsonrpc throttle primary cells."]
    categories = sorted(
        name
        for name in (primary[0].get("category_cpu_ns_per_message") or {}).keys()
        if name != "SESSION_SETUP"
    )
    lines = [
        "Population: **raw_jsonrpc × throttle × tool_count=1** "
        f"(n={len(primary)} cells); median of cell medians; "
        "client+server combined; SESSION_SETUP excluded.",
        "",
        "| Category | Median cell CPU (µs/message) |",
        "|---|---:|",
    ]
    for category in categories:
        values = [
            float((cell.get("category_cpu_ns_per_message") or {}).get(category, {}).get("median", 0))
            for cell in primary
        ]
        lines.append(f"| {category} | {_median(values) / 1000:.3f} |")
    return lines


def _setup_table(cells: Sequence[Mapping[str, Any]]) -> list[str]:
    primary = [
        cell
        for cell in cells
        if (cell.get("coordinates") or {}).get("mode") == "throttle"
    ]
    if not primary:
        return ["No setup observations."]
    cpu_values = [
        float(cell.get("session_setup_cpu_ns", {}).get("median", 0)) for cell in primary
    ]
    raw_values = [
        float(cell.get("session_setup_cpu_ns", {}).get("median", 0))
        for cell in primary
        if (cell.get("coordinates") or {}).get("implementation") == "raw_jsonrpc"
    ]
    sdk_values = [
        float(cell.get("session_setup_cpu_ns", {}).get("median", 0))
        for cell in primary
        if (cell.get("coordinates") or {}).get("implementation") == "reference_sdk"
    ]
    lines = [
        "| Scope | Median CPU (µs/cell) |",
        "|---|---:|",
        f"| SESSION_SETUP (all throttle) | {_median(cpu_values) / 1000:.3f} |",
    ]
    if raw_values:
        lines.append(f"| SESSION_SETUP (raw_jsonrpc) | {_median(raw_values) / 1000:.3f} |")
    if sdk_values:
        lines.append(f"| SESSION_SETUP (reference_sdk) | {_median(sdk_values) / 1000:.3f} |")
    return lines


def _sdk_raw_table(deltas: Sequence[Mapping[str, Any]]) -> list[str]:
    if not deltas:
        return ["No matched SDK/raw pairs."]
    lines = [
        "Steady delta excludes SESSION_SETUP; setup delta is one-time CPU per cell.",
        "",
        "| Transport | Mode | Steady Δ µs/msg | Steady ratio | Setup Δ µs/cell |",
        "|---|---|---:|---:|---:|",
    ]
    for item in deltas:
        steady = float(item.get("sdk_minus_raw_steady_cpu_ns_per_message", 0)) / 1000.0
        ratio = item.get("sdk_over_raw_steady_ratio")
        ratio_s = f"{float(ratio):.2f}×" if ratio else "—"
        setup = float(item.get("sdk_minus_raw_setup_cpu_ns", 0)) / 1000.0
        lines.append(
            f"| {item.get('transport')} | {item.get('mode')} | "
            f"{steady:.3f} | {ratio_s} | {setup:.3f} |"
        )
    return lines


def _gap_decomposition_section(
    aggregate: Mapping[str, Any],
    cells: Sequence[Mapping[str, Any]],
) -> list[str]:
    audit = aggregate.get("audit") or {}
    verdict = audit.get("diffuseness_verdict") or {}
    by_arm = audit.get("diffuseness_verdict_by_arm") or {}
    g7_live = audit.get("g7_live_cells") or []
    g7_phrase = (
        f"LIVE evaluation ({len(g7_live)} cells with gap_decomposition)"
        if g7_live
        else "no-op (no decompositions)"
    )
    lines = [
        f"**G7 status:** {g7_phrase}.",
        "",
    ]
    raw = [
        cell
        for cell in cells
        if (cell.get("coordinates") or {}).get("implementation") == "raw_jsonrpc"
        and (cell.get("coordinates") or {}).get("mode") in {"throttle", "full"}
        and (cell.get("gap_decomposition_ns_per_message") or {})
    ]
    if not raw:
        lines.append("No raw full/throttle cells with gap_decomposition.")
    else:
        lines.extend(
            [
                "| Transport | Mode | parent | (a) | (b) | (c) | (d) | "
                "d_meas | d_adj | (e) | e% of parent |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for cell in raw:
            gap = cell.get("gap_decomposition_ns_per_message") or {}
            coords = cell.get("coordinates") or {}

            def _us(key: str) -> float:
                raw_v = gap.get(key) or 0
                if isinstance(raw_v, Mapping):
                    return float(raw_v.get("median", raw_v.get("mean", 0))) / 1000.0
                return float(raw_v or 0) / 1000.0

            def _sub_us(field: str) -> float:
                sub = gap.get("gap_syscall_return_subprovenance") or {}
                if not isinstance(sub, Mapping):
                    return 0.0
                raw_v = sub.get(field) or 0
                if isinstance(raw_v, Mapping):
                    return float(raw_v.get("median", raw_v.get("mean", 0))) / 1000.0
                return float(raw_v or 0) / 1000.0

            parent = _us("parent_cpu_ns")
            e = _us("gap_unattributed")
            d = _us("gap_syscall_return")
            d_meas = _sub_us("measured_ns")
            d_adj = _sub_us("adjacent_segments_ns")
            # Pre-v1.5 artifacts booked (d) as adjacent-only; surface that honestly.
            if d > 0 and d_meas == 0 and d_adj == 0:
                d_adj = d
            e = _us("gap_unattributed")
            e_pct = (100.0 * e / parent) if parent > 0 else 0.0
            lines.append(
                f"| {coords.get('transport')} | {coords.get('mode')} | "
                f"{parent:.3f} | {_us('gap_event_loop'):.3f} | "
                f"{_us('gap_instrumentation'):.3f} | {_us('gap_gc'):.3f} | "
                f"{d:.3f} | {d_meas:.3f} | {d_adj:.3f} | {e:.3f} | {e_pct:.1f}% |"
            )
        lines.append("")
        lines.append(
            "**e% base:** `100 × gap_unattributed / parent_cpu_ns`, where "
            "`parent_cpu_ns` is the `client_call_inter_region_gaps` total for the "
            "cell (Σ(a..e) = parent). Not a share of named-only time."
        )
        lines.append("")
        lines.append(
            "**(d) split:** `d_meas` = named post-return sites still inside the "
            "gap; `d_adj` = transport-adjacent inter-region intervals (relabeled "
            "gap segments). Post-return close/wrap tightened into "
            "`MSG_TRANSPORT_CPU`/`transport_syscall_return` has left the gap and "
            "is not double-counted in (d). If `d_adj` dominates (d) without named "
            "sites, treat (d) as presumptive adjacent gap-fill pending tighter "
            "measurement — same G6 spirit one level down."
        )
        lines.append("")
        lines.append(
            "Units: µs/message (cell medians). `gap_event_loop` is unmeasured on "
            "the sync raw path (honest zero). `gap_gc` is CPython cyclic GC only."
        )

    lines.extend(["", "### Diffuseness verdict (per arm)", ""])
    lines.append(
        "Verdicts are **scoped per implementation**. Do not pool raw and SDK: "
        "raw is synchronous (`gap_event_loop` unmeasured) and cannot answer the "
        "TurnTrace async-framework echo; SDK can. Raw answers whether a lean "
        "sync path still carries smeared residue (syscall-adjacent + "
        "unattributed vs framework machinery)."
    )
    lines.append("")
    if by_arm:
        for arm_name, arm in sorted(by_arm.items()):
            lines.append(f"#### Arm `{arm_name}`")
            lines.append("")
            vname = arm.get("verdict", "absent")
            if vname == "deferred_insufficient_population" or not arm.get("binding"):
                lines.append(
                    "> **ADVISORY — verdict deferred to bare-metal n≥3.**"
                )
                lines.append("")
                lines.append(f"- Field: `{vname}` (non-binding)")
                lines.append(f"- Reason: {arm.get('reason', 'population floor')}")
                advisory = arm.get("advisory_only")
                if advisory:
                    lines.append("- Advisory-only classifications (debug, do not quote):")
                    for item in advisory if isinstance(advisory, list) else [advisory]:
                        if not item:
                            continue
                        label = item.get("transport") or item.get("cell_id") or ""
                        prefix = f"{label}: " if label else ""
                        lines.append(
                            f"  - {prefix}`{item.get('verdict')}`: "
                            f"{item.get('reason', '')}"
                        )
            else:
                lines.append(
                    f"**Binding verdict:** `{vname}` — {arm.get('reason', '')}"
                )
            lines.append("")
    else:
        verdict_name = verdict.get("verdict", "absent")
        lines.append(f"- Top-level field: `{verdict_name}`")
        lines.append(f"- Reason: {verdict.get('reason', '')}")

    lines.extend(["", "### Observer instrumentation cross-check (Task 3)", ""])
    checks = audit.get("observer_instrumentation_crosscheck") or []
    if not checks:
        lines.append("No stripped/throttle pairs available.")
    else:
        lines.extend(
            [
                "| Transport | Implementation | Bracket µs/msg | Booked (b) µs/msg | Flag |",
                "|---|---|---:|---:|---|",
            ]
        )
        for item in checks:
            lines.append(
                f"| {item.get('transport')} | {item.get('implementation')} | "
                f"{float(item.get('observer_bracket_delta_ns') or 0) / 1000:.3f} | "
                f"{float(item.get('booked_gap_instrumentation_ns') or 0) / 1000:.3f} | "
                f"{item.get('flag')} |"
            )
            if item.get("flag") == "OBSERVER_ATTRIBUTION_SUSPECT":
                lines.append(f"| | | | | _{item.get('diagnosis')}_ |")
    return lines


def _provenance_tables(cells: Sequence[Mapping[str, Any]]) -> list[str]:
    primary = [
        cell
        for cell in cells
        if (cell.get("coordinates") or {}).get("mode") == "throttle"
        and int((cell.get("coordinates") or {}).get("tool_count", 0)) == 1
        and (cell.get("coordinates") or {}).get("implementation") == "raw_jsonrpc"
    ]
    if not primary:
        return ["No raw throttle cells with provenance."]
    lines = [
        "Population: raw_jsonrpc × throttle × tool_count=1.",
        "",
        "### MSG_DISPATCH (median across transports)",
        "",
        "| Provenance | Median µs/message |",
        "|---|---:|",
    ]
    dispatch_names: set[str] = set()
    for cell in primary:
        dispatch_names.update(
            (cell.get("provenance_cpu_ns_per_message") or {}).get("MSG_DISPATCH") or {}
        )
    for name in sorted(dispatch_names):
        values = [
            float(
                ((cell.get("provenance_cpu_ns_per_message") or {}).get("MSG_DISPATCH") or {})
                .get(name, {})
                .get("median", 0)
            )
            for cell in primary
        ]
        lines.append(f"| `{name}` | {_median(values) / 1000:.3f} |")
    lines.extend(
        [
            "",
            "### MSG_TRANSPORT_CPU (per transport — handshake is TLS-only)",
            "",
            "| Transport | `transport_syscall` µs/msg | `transport_tls_handshake` µs/msg |",
            "|---|---:|---:|",
        ]
    )
    for cell in sorted(
        primary, key=lambda item: str((item.get("coordinates") or {}).get("transport"))
    ):
        transport = (cell.get("coordinates") or {}).get("transport")
        prov = (cell.get("provenance_cpu_ns_per_message") or {}).get("MSG_TRANSPORT_CPU") or {}
        syscall = float((prov.get("transport_syscall") or {}).get("median", 0)) / 1000.0
        handshake = float((prov.get("transport_tls_handshake") or {}).get("median", 0)) / 1000.0
        lines.append(f"| {transport} | {syscall:.3f} | {handshake:.3f} |")
    lines.append("")
    return lines


def _bare_metal_flags(aggregate: Mapping[str, Any]) -> list[str]:
    lines = [
        "Pre-registered checks for the 120×5 bare-metal promotion run:",
        "",
        "1. **Observer pair sign:** any stripped > throttle pair at n=1 WSL "
        "(e.g. stdio raw in v8) must not survive n=5 bare metal without explanation.",
        "2. **SDK−raw steady sign:** mixed-sign steady deltas (SDK cheaper than raw "
        "on some transports) require a raw-arm efficiency check; do not treat "
        "`raw_jsonrpc` as an automatic lean floor without profiling.",
        "3. **SESSION_SETUP variance:** SDK setup moved ~0.88 s → ~2.5 s across "
        "v7/v8 re-smokes on the same cell class; bare metal must report setup "
        "median and IQR (or seed spread), not a single point estimate.",
        "4. **Connection-pattern TLS:** HTTP/SSE TLS handshake provenance must "
        "remain labeled as per-message connection tax unless a reuse arm is added.",
        "5. **VALIDATE stress:** pathological_large / 512 KiB axes decide whether "
        "the DFA story for VALIDATE survives; benign flat_5×256 B near-zero is expected.",
        "6. **DISPATCH / gap provenance:** `client_call_inter_region_gaps` share "
        "must stay visible; v9 gap split is pre-registered (OPEN_QUESTIONS §4) "
        "before interpreting. G6 flags opaque dominant categories without named "
        "provenance ≥80%.",
        "7. **No floor-class quote:** do not promote a 2–3 ms/msg floor until "
        "gaps are attributed; named work + connection-pattern TLS + diffuse "
        "residue is the earned ladder position.",
        "8. **Diffuseness verdict:** apply only the pre-registered confirm/refute "
        "criteria in OPEN_QUESTIONS §4 / protocol `diffuseness_verdict`; do not "
        "invent a post-hoc call after seeing the distribution.",
        "9. **G7 gap-split conservation:** when a decomposition is present, "
        "Σ(sub-mechanisms) must equal the parent gap within G3 slack.",
    ]
    pairs = (aggregate.get("debug_smoke") or {}).get("throttle_stripped_tax") or []
    negative = [
        item
        for item in pairs
        if float(item.get("throttle_minus_stripped_ns_per_message", 0)) < 0
    ]
    if negative:
        lines.extend(["", "Negative observer pairs in this artifact:"])
        for item in negative:
            lines.append(
                f"- {item.get('transport')} / {item.get('implementation')}: "
                f"Δ={float(item.get('throttle_minus_stripped_ns_per_message', 0)) / 1000:.1f} µs/msg"
            )
    return lines


def _coverage_table(cells: Sequence[Mapping[str, Any]]) -> list[str]:
    from .coverage import RAW_COVERAGE, SDK_COVERAGE

    implementations = sorted(
        {
            str((cell.get("coordinates") or {}).get("implementation"))
            for cell in cells
            if (cell.get("coordinates") or {}).get("implementation")
        }
    )
    mapping = {
        "raw_jsonrpc": RAW_COVERAGE,
        "reference_sdk": SDK_COVERAGE,
    }
    if not implementations:
        return ["No coverage metadata recorded."]
    categories = sorted(RAW_COVERAGE.keys())
    header = "| Category | " + " | ".join(implementations) + " |"
    sep = "|---|" + "|".join(["---:"] * len(implementations)) + "|"
    lines = [header, sep]
    for category in categories:
        row = [category]
        for implementation in implementations:
            row.append(mapping.get(implementation, {}).get(category, "—"))
        lines.append("| " + " | ".join(row) + " |")
    lines.append(
        "SDK-vs-raw category deltas are rendered only when both arms are "
        "`harness_owned` for that category."
    )
    return lines


def _cpu_wait_table(cells: Sequence[Mapping[str, Any]]) -> list[str]:
    lines = [
        "Population: **raw_jsonrpc × throttle × tool_count=1** (matches category table).",
        "",
        "| Transport | CPU µs/message | Wait µs/message |",
        "|---|---:|---:|",
    ]
    transports = sorted(
        {
            str((cell.get("coordinates") or {}).get("transport"))
            for cell in cells
            if (cell.get("coordinates") or {}).get("mode") == "throttle"
            and (cell.get("coordinates") or {}).get("implementation") == "raw_jsonrpc"
        }
    )
    for transport in transports:
        selected = [
            cell
            for cell in cells
            if (cell.get("coordinates") or {}).get("transport") == transport
            and (cell.get("coordinates") or {}).get("mode") == "throttle"
            and (cell.get("coordinates") or {}).get("implementation") == "raw_jsonrpc"
            and int((cell.get("coordinates") or {}).get("tool_count", 0)) == 1
        ]
        from .analyze import cell_steady_cpu_ns_per_message

        cpu = _median([cell_steady_cpu_ns_per_message(cell) for cell in selected])
        wait = _median([float(cell["wait_ns_per_message"]["median"]) for cell in selected])
        lines.append(f"| {transport} | {cpu / 1000:.3f} | {wait / 1000:.3f} |")
    return lines


def _gate_matrix(audit: Mapping[str, Any]) -> list[str]:
    gates = audit.get("gates") or {}
    lines = ["| Gate | Result | Violations |", "|---|---|---:|"]
    for gate_name in ("G1", "G2", "G3", "G4", "G5", "G6", "G7"):
        gate = gates.get(gate_name)
        if gate is None:
            lines.append(f"| {gate_name} | NOT EVALUATED | — |")
        else:
            lines.append(
                f"| {gate_name} | {'PASS' if gate.get('pass') else 'FAIL'} | "
                f"{len(gate.get('errors') or [])} |"
            )
    return lines


def _ledger_lines(ledger: Mapping[str, Any]) -> list[str]:
    entries = ledger.get("entries") or []
    if not entries:
        return ["No retired claims recorded."]
    lines = ["| ID | Claim | Reason | Evidence |", "|---:|---|---|---|"]
    for entry in entries:
        evidence = ", ".join(str(item) for item in entry.get("evidence") or []) or "—"
        lines.append(
            f"| {entry.get('id')} | {entry.get('claim')} | {entry.get('reason')} | {evidence} |"
        )
    return lines


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return float((ordered[middle - 1] + ordered[middle]) / 2)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("aggregate", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--died-ledger",
        type=Path,
        default=Path("apu_characterization/mcp_tax/died_ledger.json"),
    )
    args = parser.parse_args()
    aggregate = json.loads(args.aggregate.read_text(encoding="utf-8"))
    write_report(
        args.output,
        aggregate,
        died_ledger_path=args.died_ledger,
        aggregate_name=args.aggregate.name,
    )
    print(args.output)


if __name__ == "__main__":
    main()
