"""TLP-01: limits of turn-level parallelism (trace-driven limit study, v2)."""

from apu_characterization.tlp01.analyze import (
    analyze_experiment,
    select_ceiling_rung,
    select_claim_rung,
)
from apu_characterization.tlp01.contracts import PROTOCOL_VERSION, load_protocol
from apu_characterization.tlp01.extract import (
    make_synthetic_chain_session,
    make_synthetic_parallel_session,
)
from apu_characterization.tlp01.phase_diagram import sweep_phase_diagram
from apu_characterization.tlp01.schema import validate_trace_events

__all__ = [
    "PROTOCOL_VERSION",
    "analyze_experiment",
    "load_protocol",
    "make_synthetic_chain_session",
    "make_synthetic_parallel_session",
    "select_ceiling_rung",
    "select_claim_rung",
    "sweep_phase_diagram",
    "validate_trace_events",
]
