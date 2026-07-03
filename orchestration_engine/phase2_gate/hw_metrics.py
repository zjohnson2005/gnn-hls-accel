"""Canonical hardware scatter metrics from csynth + cosim artifacts."""

import json
from pathlib import Path

from orchestration_engine.phase2_gate.csynth_parser import DEFAULT_CLOCK_MHZ, load_or_parse

OE_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = OE_ROOT / "characterization" / "out" / "phase2"


def _load_cosim_json():
    path = OUT_DIR / "cosim_scatter.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_stream_json():
    """Streaming-kernel cosim (N completions/invocation -> steady-state cycles)."""
    path = OUT_DIR / "cosim_stream.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("passed") or not data.get("per_transaction_cycles"):
        return None
    return data


def load_hw_scatter_metrics(fan_out=2, batch_width=1):
    csynth = load_or_parse()
    cosim = _load_cosim_json()
    stream = _load_stream_json()

    analytic_cycles = 1 + (fan_out + batch_width - 1) // batch_width
    if csynth and csynth.is_measured:
        clock_mhz = csynth.clock_mhz
        csynth_source = csynth.report_path
    else:
        clock_mhz = DEFAULT_CLOCK_MHZ
        csynth_source = None

    cosim_latency = None
    cosim_ii = None
    cosim_source = None
    cosim_passed = False
    if cosim and cosim.get("passed"):
        cosim_passed = True
        cosim_source = cosim.get("report_path")
        cosim_latency = cosim.get("latency_cycles")
        cosim_ii = cosim.get("interval_min")

    stream_cycles = None
    stream_source = None
    if stream is not None:
        stream_cycles = float(stream["per_transaction_cycles"])
        stream_source = stream.get("report_path")

    if stream_cycles is not None:
        steady_cycles = stream_cycles
        source = "cosim_stream"
    elif cosim_passed and cosim_ii is not None:
        steady_cycles = int(cosim_ii)
        source = "cosim_ii"
    elif cosim_passed and cosim_latency is not None:
        steady_cycles = int(cosim_latency)
        source = "cosim_latency"
    elif csynth and csynth.is_measured:
        steady_cycles = analytic_cycles
        source = "csynth_analytic"
    else:
        steady_cycles = analytic_cycles
        source = "analytic"

    steady_us = steady_cycles / clock_mhz

    if source == "cosim_stream":
        note = (
            "steady-state {0} cycles/completion from streaming cosim "
            "({1} completions/invocation @ {2:.1f} MHz); one-shot latency "
            "{3} cycles (ap_ctrl_hs overhead)"
        ).format(
            steady_cycles,
            stream.get("transactions"),
            clock_mhz,
            cosim_latency if cosim_latency is not None else "?",
        )
    elif source == "cosim_ii":
        note = (
            "steady-state II from multi-transaction cosim ({0} cycles @ {1:.1f} MHz); "
            "one-shot latency {2} cycles (ap_ctrl_hs overhead)"
        ).format(
            steady_cycles,
            clock_mhz,
            cosim_latency if cosim_latency is not None else "?",
        )
    elif source == "cosim_latency":
        note = (
            "one-shot cosim latency {0} cycles @ {1:.1f} MHz "
            "(includes ap_ctrl_hs; run multi-transaction cosim for II)"
        ).format(steady_cycles, clock_mhz)
    elif source == "csynth_analytic":
        note = (
            "analytic scatter ({0} cycles @ {1:.1f} MHz csynth Fmax); "
            "cosim pending or not parsed"
        ).format(steady_cycles, clock_mhz)
    else:
        note = "analytic target pending csynth"

    return {
        "fan_out": fan_out,
        "clock_mhz": round(clock_mhz, 1),
        "analytic_cycles": analytic_cycles,
        "cosim_latency_cycles": cosim_latency,
        "cosim_ii_cycles": cosim_ii,
        "steady_state_cycles": steady_cycles,
        "steady_state_us": round(steady_us, 4),
        "source": source,
        "note": note,
        "csynth_source": csynth_source,
        "cosim_source": cosim_source,
        "stream_source": stream_source,
        "stream_cycles_per_completion": stream_cycles,
        "cosim_verified": (cosim_passed and cosim_latency is not None)
        or stream_cycles is not None,
    }
