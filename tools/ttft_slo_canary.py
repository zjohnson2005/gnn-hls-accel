"""Drift canary for tools/run_c1_ceiling.py --criterion ttft_slo.

Reimplements docs/CANARY_PROTOCOL.md for the Python TTFT-SLO worker.
Fixed cell matches the matrix runner defaults (gpu_only_f16, n_cached=4000,
delta=400, RESIDENT) on the session's pinned model.

Interval N is derived from THIS run's observed probe wall times:
  N = floor(ONSET_S / mean_probe_wall_s)
with ONSET_S = 657 from session 7f569929 (protocol), not the inherited N=12.

A trip raises CanaryDriftAbort — it must not return a soft status the caller
can ignore (see tools/test_canary_drift_abort_enforcement.ps1 / Invoke-DriftCanary).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Shortest observed degradation onset (docs/CANARY_PROTOCOL.md / 7f569929).
ONSET_S = 657.0
CALIBRATION_C = 3
REL_DRIFT_FLOOR = 0.05
CANARY_ARM = "gpu_only_f16"
CANARY_N_CACHED = 4000
CANARY_DELTA = 400
CANARY_MODE = "RESIDENT"
FAIL_STATUS = "FAIL_CANARY_DRIFT"


class CanaryDriftAbort(Exception):
    """Session must stop; status = FAIL_CANARY_DRIFT."""

    def __init__(self, detail: str, *, canary_record: dict[str, Any] | None = None):
        super().__init__(detail)
        self.detail = detail
        self.canary_record = canary_record or {}


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _rel_drift(value: float, ref: float) -> float | None:
    if ref == 0.0:
        return None
    return abs(float(value) - float(ref)) / abs(float(ref))


def derive_canary_every_n(probe_wall_s: list[float], *, onset_s: float = ONSET_S) -> dict[str, Any]:
    """N from this run's cell times; onset window inherited from protocol."""
    walls = [float(w) for w in probe_wall_s if w is not None and float(w) > 0]
    if not walls:
        return {
            "n": None,
            "mean_probe_wall_s": None,
            "onset_s": onset_s,
            "derivable": False,
            "note": "waiting for at least one positive probe wall_s",
        }
    mean_w = float(statistics.mean(walls))
    n = max(1, int(onset_s // mean_w))
    return {
        "n": n,
        "mean_probe_wall_s": mean_w,
        "onset_s": onset_s,
        "n_probes_in_mean": len(walls),
        "derivable": True,
        "derivation": (
            f"N=floor(onset_s/mean_probe_wall_s)=floor({onset_s}/{mean_w:.4f})={n}; "
            f"onset_s={onset_s} from protocol session 7f569929; "
            f"mean_probe_wall_s from THIS run ({len(walls)} probes)."
        ),
    }


def update_canary_drift_bookkeeping(
    *,
    rec: dict[str, Any],
    gate: dict[str, Any],
    prior_ok_canaries: list[dict[str, Any]],
    calibration_c: int = CALIBRATION_C,
    rel_drift_floor: float = REL_DRIFT_FLOOR,
) -> dict[str, Any]:
    """Python port of tools/SeamPsCommon.ps1 Update-CanaryDriftBookkeeping."""
    if calibration_c < 2:
        raise ValueError("calibration_c must be >= 2")
    was_complete = bool(gate.get("calibration_complete"))
    rel_t1 = None
    rel_t2 = None
    tripped = False
    trip_detail = None

    t1 = rec.get("turn1_prefill_s")
    t2 = rec.get("turn2_prefill_s")
    ok = rec.get("classification") == "OK" and t1 is not None and t2 is not None

    if ok:
        if not gate.get("calibration_complete"):
            ok_cal = [
                c
                for c in prior_ok_canaries
                if c.get("classification") == "OK"
                and c.get("turn1_prefill_s") is not None
                and c.get("turn2_prefill_s") is not None
            ] + [rec]
            if len(ok_cal) >= calibration_c:
                # Same as PS: at arming, prior+rec has reached C; use that set.
                t1s = [float(c["turn1_prefill_s"]) for c in ok_cal]
                t2s = [float(c["turn2_prefill_s"]) for c in ok_cal]
                ref1 = float(statistics.median(t1s))
                ref2 = float(statistics.median(t2s))
                early1 = [_rel_drift(v, ref1) or 0.0 for v in t1s]
                early2 = [_rel_drift(v, ref2) or 0.0 for v in t2s]
                em1 = max(early1)
                em2 = max(early2)
                th1 = max(2.0 * em1, float(rel_drift_floor))
                th2 = max(2.0 * em2, float(rel_drift_floor))
                gate["armed"] = True
                gate["calibration_complete"] = True
                gate["ref_turn1_prefill_s"] = ref1
                gate["ref_turn2_prefill_s"] = ref2
                gate["early_max_rel_t1"] = em1
                gate["early_max_rel_t2"] = em2
                gate["threshold_t1"] = th1
                gate["threshold_t2"] = th2
                gate["derivation_applied"] = (
                    f"calib_n={calibration_c}; ref_t1={ref1:.6f} ref_t2={ref2:.6f}; "
                    f"early_max_rel_t1={em1:.6f} early_max_rel_t2={em2:.6f}; "
                    f"threshold_t1=max(2*early_max_t1,floor={rel_drift_floor})={th1:.6f}; "
                    f"threshold_t2={th2:.6f}"
                )
        else:
            rel_t1 = _rel_drift(float(t1), float(gate["ref_turn1_prefill_s"]))
            rel_t2 = _rel_drift(float(t2), float(gate["ref_turn2_prefill_s"]))
            if rel_t1 is not None and rel_t1 > float(gate["threshold_t1"]):
                tripped = True
                trip_detail = (
                    f"turn1 rel_drift={rel_t1:.6f} > threshold_t1={gate['threshold_t1']:.6f} "
                    f"(t1={t1} ref={gate['ref_turn1_prefill_s']})"
                )
            elif rel_t2 is not None and rel_t2 > float(gate["threshold_t2"]):
                tripped = True
                trip_detail = (
                    f"turn2 rel_drift={rel_t2:.6f} > threshold_t2={gate['threshold_t2']:.6f} "
                    f"(t2={t2} ref={gate['ref_turn2_prefill_s']})"
                )
    elif gate.get("calibration_complete"):
        tripped = True
        trip_detail = (
            f"canary classification={rec.get('classification')!r} "
            "(no usable turn1/turn2 after gate armed)"
        )

    rec["rel_drift_t1"] = rel_t1
    rec["rel_drift_t2"] = rel_t2
    rec["gate_armed"] = bool(gate.get("armed"))
    rec["threshold_t1"] = gate.get("threshold_t1")
    rec["threshold_t2"] = gate.get("threshold_t2")
    rec["drift_tripped"] = tripped
    rec["trip_detail"] = trip_detail

    return {
        "rec": rec,
        "tripped": tripped,
        "trip_detail": trip_detail,
        "just_armed": (not was_complete) and bool(gate.get("calibration_complete")),
        "derivation_applied": gate.get("derivation_applied"),
    }


def new_canary_gate(
    *,
    calibration_c: int = CALIBRATION_C,
    rel_drift_floor: float = REL_DRIFT_FLOOR,
) -> dict[str, Any]:
    return {
        "armed": False,
        "calibration_complete": False,
        "calibration_c": calibration_c,
        "rel_drift_floor": rel_drift_floor,
        "ref_turn1_prefill_s": None,
        "ref_turn2_prefill_s": None,
        "early_max_rel_t1": None,
        "early_max_rel_t2": None,
        "threshold_t1": None,
        "threshold_t2": None,
        "derivation_applied": None,
        "fixed_cell": {
            "arm": CANARY_ARM,
            "n_cached": CANARY_N_CACHED,
            "delta": CANARY_DELTA,
            "mode": CANARY_MODE,
        },
        "onset_s": ONSET_S,
        "protocol": "docs/CANARY_PROTOCOL.md",
    }


@dataclass
class TtftSloCanaryGuard:
    """Interleaves fixed delta-prefill canaries into a ttft_slo ceiling run."""

    root: Path
    model_spec: Path
    work_dir: Path
    plan_path: Path | None = None
    calibration_c: int = CALIBRATION_C
    rel_drift_floor: float = REL_DRIFT_FLOOR
    onset_s: float = ONSET_S
    gate: dict[str, Any] = field(default_factory=new_canary_gate)
    canaries: list[dict[str, Any]] = field(default_factory=list)
    n_every: int | None = None
    n_derivation: dict[str, Any] = field(default_factory=dict)
    probes_since_canary: int = 0
    opening_done: bool = False

    def __post_init__(self) -> None:
        self.gate = new_canary_gate(
            calibration_c=self.calibration_c,
            rel_drift_floor=self.rel_drift_floor,
        )
        self.gate["onset_s"] = self.onset_s
        self.n_derivation = derive_canary_every_n([], onset_s=self.onset_s)

    def plan_fragment(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "criterion_path": "ttft_slo",
            "fixed_cell": self.gate["fixed_cell"],
            "model_spec": str(self.model_spec),
            "calibration_c": self.calibration_c,
            "rel_drift_floor": self.rel_drift_floor,
            "onset_s": self.onset_s,
            "canary_every_n": self.n_every,
            "n_derivation": self.n_derivation,
            "canary_gate": self.gate,
            "n_canaries": len(self.canaries),
            "abort_on_trip": FAIL_STATUS,
            "enforcement": (
                "CanaryDriftAbort exception; session status FAIL_CANARY_DRIFT. "
                "Does not return a soft bool that a caller can ignore "
                "(Invoke-DriftCanary Write-Output bug class)."
            ),
        }

    def refresh_interval(self, probe_wall_s: list[float]) -> None:
        self.n_derivation = derive_canary_every_n(probe_wall_s, onset_s=self.onset_s)
        if self.n_derivation.get("derivable"):
            self.n_every = int(self.n_derivation["n"])

    def _run_cell(self) -> dict[str, Any]:
        from tools.smoke_delta_prefill import run_cell

        self.work_dir.mkdir(parents=True, exist_ok=True)
        raw = run_cell(
            "ttft_slo_canary",
            arm_id=CANARY_ARM,
            mode=CANARY_MODE,
            n_cached=CANARY_N_CACHED,
            delta=CANARY_DELTA,
            model_spec=self.model_spec,
            pipeline_type="llm",
        )
        t1 = (raw.get("turn1") or {}).get("prefill_s")
        t2 = (raw.get("turn2") or {}).get("prefill_s")
        classification = raw.get("classification") or "OTHER"
        if classification == "OK" or (raw.get("execute_ok") and t1 is not None and t2 is not None):
            classification = "OK"
        rec = {
            "is_canary": True,
            "canary_index": len(self.canaries),
            "after_probe_count": None,
            "utc": _utc(),
            "arm_id": CANARY_ARM,
            "n_cached": CANARY_N_CACHED,
            "delta": CANARY_DELTA,
            "mode": CANARY_MODE,
            "classification": classification,
            "turn1_prefill_s": t1,
            "turn2_prefill_s": t2,
            "available_mb_start": (raw.get("environment_start") or {}).get("available_mb"),
            "raw_classification": raw.get("classification"),
            "execute_ok": raw.get("execute_ok"),
            "execute_error": raw.get("execute_error"),
        }
        # Persist raw cell beside work for audit.
        out = self.work_dir / f"canary.{rec['canary_index']}.json"
        out.write_text(
            __import__("json").dumps({"record": rec, "cell": raw}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return rec

    def run_canary(self, *, after_probe_count: int) -> dict[str, Any]:
        """Run one canary. Raises CanaryDriftAbort on trip — never soft-fails."""
        print(
            f"[c2_canary] index={len(self.canaries)} after_probes={after_probe_count} "
            f"armed={self.gate.get('armed')} every_n={self.n_every}",
            flush=True,
        )
        rec = self._run_cell()
        rec["after_probe_count"] = after_probe_count
        prior_ok = [
            c
            for c in self.canaries
            if c.get("classification") == "OK"
            and c.get("turn1_prefill_s") is not None
            and c.get("turn2_prefill_s") is not None
        ]
        bk = update_canary_drift_bookkeeping(
            rec=rec,
            gate=self.gate,
            prior_ok_canaries=prior_ok,
            calibration_c=self.calibration_c,
            rel_drift_floor=self.rel_drift_floor,
        )
        rec = bk["rec"]
        self.canaries.append(rec)
        self.probes_since_canary = 0
        if bk.get("just_armed"):
            print(f"[c2_canary] gate ARMED: {bk.get('derivation_applied')}", flush=True)
        if bk["tripped"] or rec.get("drift_tripped"):
            detail = bk.get("trip_detail") or rec.get("trip_detail") or "drift tripped"
            print(f"REFUSED -- {FAIL_STATUS}: {detail}", flush=True)
            raise CanaryDriftAbort(str(detail), canary_record=rec)
        return rec

    def opening(self) -> None:
        if self.opening_done:
            return
        self.run_canary(after_probe_count=-1)
        self.opening_done = True

    def after_probe(self, probes_log: list[dict[str, Any]]) -> None:
        """Call once after each successful probe append."""
        walls = [
            float(p["wall_s"])
            for p in probes_log
            if p.get("wall_s") is not None and float(p["wall_s"]) > 0
        ]
        self.refresh_interval(walls)
        self.probes_since_canary += 1
        if self.n_every is None:
            return
        if self.probes_since_canary >= self.n_every:
            self.run_canary(after_probe_count=len(probes_log) - 1)
