"""Host power-state capture for the manifest ``power_state`` block (spec §6.1, §3.2 item 1).

`analysis/aipc-c1/MACHINE.md` § "Pinned run conditions (MANDATORY)" states that a session run
outside AC power and the pinned power plan is **INVALID, not noisy**. `AUDIT_LOG.md` AF-005 records
that this exact condition was violated by an earlier session and went unrecorded in any manifest,
because nothing captured it.

This module captures the state; it does **not** gate on it. Two reasons:

1. The gate belongs in the run driver, and AF-005 assigns it to M2. Building it here would be
   scope creep into a milestone that has not started.
2. A recorded violation is more useful than a refused run at M1, in the same sense that spec §5.1
   treats an ``UNSUPPORTED`` preflight as a data point.

What it *does* do is compare the captured state against the pinned conditions in platform config
and emit a ``warning`` event on deviation, so a session can never violate them silently
(spec §9.6).
"""

from __future__ import annotations

import ctypes
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from typing import Any, Final

from seam.errors import PinnedConditionError
from seam.jsonlog import log_event

__all__ = [
    "PowerState",
    "assert_pinned_for_committed_result",
    "capture_power_state",
    "check_pinned_conditions",
    "manifest_power_state",
]

#: ``powercfg`` is a local query with no network or lock dependency, but bound it anyway so a
#: hung service cannot stall a run indefinitely.
_TIMEOUT_S: Final = 15

#: ``SYSTEM_POWER_STATUS.ACLineStatus``: 0 offline, 1 online, 255 unknown.
_AC_OFFLINE: Final = 0
_AC_ONLINE: Final = 1
#: ``SYSTEM_POWER_STATUS.BatteryLifePercent`` sentinel for "unknown".
_BATTERY_PCT_UNKNOWN: Final = 255
#: ``SYSTEM_POWER_STATUS.SystemStatusFlag`` bit 0: battery saver is engaged.
_BATTERY_SAVER_ON: Final = 0x1
#: ``SYSTEM_POWER_STATUS.BatteryFlag`` bit 3: the battery is charging.
_BATTERY_FLAG_CHARGING: Final = 0x8
#: ``SYSTEM_POWER_STATUS.BatteryFlag`` sentinel for "unknown".
_BATTERY_FLAG_UNKNOWN: Final = 255

_ACTIVE_SCHEME_RE: Final = re.compile(
    r"GUID:\s*([0-9a-fA-F-]{36})\s*\((?P<name>.+?)\)\s*$", re.MULTILINE
)


class _SystemPowerStatus(ctypes.Structure):
    """``SYSTEM_POWER_STATUS`` (winbase.h)."""

    _fields_ = (
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    )


@dataclass(frozen=True, slots=True)
class PowerState:
    """A snapshot of the host's power configuration.

    Every field is nullable because each is *recorded*, not required: an unreadable field must show
    up as an explicit ``null`` with a logged reason, never as a plausible default.
    """

    #: True on battery, False on AC, None if Windows reports ``ACLineStatus=255`` (unknown).
    on_battery: bool | None
    battery_pct: float | None
    #: True while the battery is taking bulk charge. Charging is a *load*: it consumes adapter
    #: headroom and adds chassis heat, both of which depress turbo. A measurement on AC at 50% is
    #: therefore taken under different conditions than the same measurement at 100%, and the
    #: difference is not visible from ``on_battery`` alone.
    charging: bool | None
    #: True if Windows battery saver is engaged. Battery saver clamps turbo, so a measurement taken
    #: under it is not comparable with one taken without it.
    battery_saver: bool | None
    power_plan_name: str | None
    power_plan_guid: str | None
    #: The Windows *power-mode overlay* (the Settings performance slider), which is a separate
    #: control from the power scheme and can clamp frequency independently of it. All-zero GUID
    #: means no overlay is in effect.
    overlay_guid: str | None


def _charging_from_battery_flag(battery_flag: int) -> bool | None:
    """Decode ``SYSTEM_POWER_STATUS.BatteryFlag`` into a charging state.

    Split out from the Win32 call so the decoding is unit-testable on any OS.

    Returns:
        True while charging, False when not, None when Windows reports the flag as unknown. Unknown
        becomes an explicit null rather than False, because "not observed" and "observed not
        charging" are different claims about the session.
    """
    if battery_flag == _BATTERY_FLAG_UNKNOWN:
        log_event(
            "powerstate.battery_flag_unknown",
            severity="warning",
            message="Windows reports BatteryFlag as unknown; recording null charging state",
            battery_flag=battery_flag,
        )
        return None
    return bool(battery_flag & _BATTERY_FLAG_CHARGING)


def _capture_system_power_status() -> tuple[bool | None, float | None, bool | None, bool | None]:
    """Read ``GetSystemPowerStatus``.

    Returns:
        ``(on_battery, battery_pct, charging, battery_saver)``, any of which may be None if Windows
        reports the value as unknown or the call fails.
    """
    if sys.platform != "win32":
        log_event(
            "powerstate.unavailable",
            severity="warning",
            message=f"GetSystemPowerStatus is Windows-only; running on {sys.platform!r}",
        )
        return None, None, None, None

    status = _SystemPowerStatus()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
    if not kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        log_event(
            "powerstate.system_power_status_failed",
            severity="warning",
            message="GetSystemPowerStatus failed; recording null AC and battery fields",
            win32_error=ctypes.get_last_error(),
        )
        return None, None, None, None

    if status.ACLineStatus == _AC_ONLINE:
        on_battery: bool | None = False
    elif status.ACLineStatus == _AC_OFFLINE:
        on_battery = True
    else:
        log_event(
            "powerstate.ac_line_status_unknown",
            severity="warning",
            message="Windows reports ACLineStatus as unknown; recording null rather than guessing",
            ac_line_status=int(status.ACLineStatus),
        )
        on_battery = None

    battery_pct = (
        None
        if status.BatteryLifePercent == _BATTERY_PCT_UNKNOWN
        else float(status.BatteryLifePercent)
    )

    charging = _charging_from_battery_flag(int(status.BatteryFlag))
    battery_saver = bool(status.SystemStatusFlag & _BATTERY_SAVER_ON)
    return on_battery, battery_pct, charging, battery_saver


def _capture_active_scheme() -> tuple[str | None, str | None]:
    """Read the active power scheme via ``powercfg /getactivescheme``.

    ``powercfg`` is used rather than ``PowerGetActiveScheme`` because the friendly name is part of
    what MACHINE.md pins, and the Win32 call returns only a GUID.

    Returns:
        ``(name, guid)``, both None if the command or the parse fails.
    """
    try:
        completed = subprocess.run(
            ["powercfg", "/getactivescheme"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_S,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        log_event(
            "powerstate.powercfg_failed",
            severity="warning",
            message="could not run powercfg /getactivescheme; recording null power plan",
            error=str(exc),
        )
        return None, None

    if completed.returncode != 0:
        log_event(
            "powerstate.powercfg_nonzero",
            severity="warning",
            message="powercfg /getactivescheme exited non-zero; recording null power plan",
            returncode=completed.returncode,
            stderr=completed.stderr.strip(),
        )
        return None, None

    match = _ACTIVE_SCHEME_RE.search(completed.stdout)
    if match is None:
        log_event(
            "powerstate.powercfg_unparsed",
            severity="warning",
            message="could not parse powercfg /getactivescheme output",
            stdout=completed.stdout.strip(),
        )
        return None, None

    return match.group("name").strip(), match.group(1).lower()


def _capture_overlay() -> str | None:
    """Read the effective power-mode overlay via ``PowerGetEffectiveOverlayScheme``.

    Returns:
        The overlay GUID as a lowercase string, or None if unavailable. The all-zero GUID is a real
        value meaning "no overlay in effect", so it is returned rather than nulled.
    """
    if sys.platform != "win32":
        return None

    raw = (ctypes.c_ubyte * 16)()
    try:
        powrprof = ctypes.WinDLL("powrprof", use_last_error=True)  # type: ignore[attr-defined]
        result = powrprof.PowerGetEffectiveOverlayScheme(ctypes.byref(raw))
    except (AttributeError, OSError) as exc:
        log_event(
            "powerstate.overlay_unavailable",
            severity="warning",
            message="PowerGetEffectiveOverlayScheme unavailable; recording null overlay",
            error=str(exc),
        )
        return None

    if result != 0:
        log_event(
            "powerstate.overlay_query_failed",
            severity="warning",
            message="PowerGetEffectiveOverlayScheme returned a non-zero status",
            status=int(result),
        )
        return None

    return str(uuid.UUID(bytes_le=bytes(raw)))


def capture_power_state() -> PowerState:
    """Capture the host power state.

    Never raises: power state is a *recorded property* of a run, in the same way
    :func:`seam.manifest.is_elevated` is, so an unreadable field becomes an explicit null plus a
    logged warning rather than a failed run.
    """
    on_battery, battery_pct, charging, battery_saver = _capture_system_power_status()
    plan_name, plan_guid = _capture_active_scheme()
    state = PowerState(
        on_battery=on_battery,
        battery_pct=battery_pct,
        charging=charging,
        battery_saver=battery_saver,
        power_plan_name=plan_name,
        power_plan_guid=plan_guid,
        overlay_guid=_capture_overlay(),
    )

    log_event(
        "powerstate.captured",
        message=(
            f"AC={'battery' if state.on_battery else 'online'} "
            f"battery={state.battery_pct}% charging={state.charging} "
            f"saver={state.battery_saver} "
            f"plan={state.power_plan_name!r} overlay={state.overlay_guid}"
        ),
        on_battery=state.on_battery,
        battery_pct=state.battery_pct,
        charging=state.charging,
        battery_saver=state.battery_saver,
        power_plan_name=state.power_plan_name,
        power_plan_guid=state.power_plan_guid,
        overlay_guid=state.overlay_guid,
    )
    return state


def manifest_power_state(
    state: PowerState, *, battery_pct_end: float | None = None
) -> dict[str, Any]:
    """Render a :class:`PowerState` into the manifest ``power_state`` block.

    ``charging`` is recorded alongside the two battery-percentage endpoints because charging draws
    adapter headroom and adds chassis heat, so an AC session under bulk charge is a different
    condition from one at full charge. Without it, ``on_battery: false`` reads as a single condition
    when it is at least two.

    ``display_brightness``, ``defender_realtime``, and ``windows_update_paused`` stay null: they are
    spec §3.2 quiescence controls that nothing yet measures, and a plausible value would be
    fabricated provenance (AM-006's reasoning applied to a different block).
    """
    return {
        "on_battery": state.on_battery,
        "battery_pct_start": state.battery_pct,
        "battery_pct_end": battery_pct_end,
        "charging": state.charging,
        "power_plan": (
            None
            if state.power_plan_guid is None
            else f"{state.power_plan_name} ({state.power_plan_guid})"
        ),
        "display_brightness": None,
        "defender_realtime": None,
        "windows_update_paused": None,
    }


def check_pinned_conditions(state: PowerState, *, pinned: dict[str, Any] | None) -> list[str]:
    """Compare a captured state against the pinned run conditions in platform config.

    Args:
        state: The captured power state.
        pinned: The ``power.pinned`` config block, or None if the platform declares none.

    Returns:
        A list of human-readable deviations, empty when the session is inside pinned conditions.
        Callers decide what to do with it; this function only records. Per AF-005 the enforcing
        gate is M2 scope, but a deviation is logged here so it cannot pass unnoticed.
    """
    deviations: list[str] = []

    if state.on_battery is not False:
        deviations.append(
            f"AC power required (ACLineStatus=1); observed on_battery={state.on_battery}"
        )
    if state.battery_saver:
        deviations.append("Windows battery saver is engaged, which clamps turbo")

    if pinned:
        expected_guid = str(pinned.get("power_plan_guid") or "").lower()
        expected_name = str(pinned.get("power_plan_name") or "")
        actual_guid = (state.power_plan_guid or "").lower()
        actual_name = state.power_plan_name or ""
        if expected_guid and actual_guid != expected_guid and actual_name != expected_name:
            deviations.append(
                f"pinned power plan is {expected_name!r} ({expected_guid}); "
                f"observed {actual_name!r} ({actual_guid or 'unknown'})"
            )

    log_event(
        "powerstate.pinned_conditions",
        severity="warning" if deviations else "info",
        message=(
            "session VIOLATES the pinned run conditions; MACHINE.md classifies such a session as "
            "INVALID, not noisy (AUDIT_LOG.md AF-005)"
            if deviations
            else "session is inside the pinned run conditions"
        ),
        deviations=deviations,
        on_battery=state.on_battery,
        battery_saver=state.battery_saver,
        power_plan_name=state.power_plan_name,
        power_plan_guid=state.power_plan_guid,
    )
    return deviations


def assert_pinned_for_committed_result(deviations: list[str]) -> None:
    """Refuse to persist a platform result measured outside the pinned run conditions.

    This is narrower than the run gate AF-005 defers to M2. A session outside pinned conditions may
    still run and still emit its manifest — the measurement is real, and discarding it would
    recreate the AF-006 traceability hole. What it may not do is write its result back into
    ``configs/platforms/`` and become the value every later run asserts.

    Raises:
        PinnedConditionError: If ``deviations`` is non-empty.
    """
    if not deviations:
        return

    raise PinnedConditionError(
        "refusing to write a measured result to platform config: this session violates "
        "MACHINE.md's pinned run conditions, which classifies it as INVALID, not noisy "
        f"({'; '.join(deviations)}). The run's manifest was still emitted, so the measurement "
        "remains citable as a diagnostic. Restore the pinned conditions and re-measure."
    )
