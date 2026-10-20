"""Per-turn wall-clock watchdog for hybrid local turns (Task AW, harness only).

Why: XPS run 841b84e4 (DEMO1_LONGCTX_30, 2026-10-19) stopped producing output
after its pipeline load for multi_turn_long_context_123 and ran for 3 h 17 min
with the GPU idle until it was stopped by hand. Nothing in the run recorded
where it stopped.

What it does when a turn runs longer than ``limit_s``:
1. writes a hang record (outcome "hang") to ``<out_dir>/hang_events.json``;
2. dumps every Python thread's stack (faulthandler) to
   ``<out_dir>/hang_stacks_<entry>_t<turn>.txt``;
3. runs ``dump_cmd`` if given (an argv list; "{pid}" is replaced, e.g.
   ``["py-spy", "dump", "--native", "--pid", "{pid}"]``),
   output to ``hang_dump_<entry>_t<turn>.txt``, with a timeout;
4. calls ``on_fire(record)`` so the runner can persist its checkpoints;
5. ends the worker with exit code ``HANG_EXIT_CODE``.

The stalled call is native (GenAI generate) and cannot be cancelled from
Python, so the watchdog cannot continue in the same process. "Moving on" is
the next launch: it starts at the next entry (``-EntryOffset``). Every
failure inside steps 1-4 is recorded in the record, never raised, so the exit
in step 5 always happens.

Off by default: the runner builds a watchdog only with --turn-watchdog-s.
"""

from __future__ import annotations

import faulthandler
import json
import os
import re
import subprocess
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

HANG_EXIT_CODE = 86
HANG_EVENTS_NAME = "hang_events.json"
DUMP_TIMEOUT_S = 120.0
_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe(text: str) -> str:
    return _SAFE.sub("_", text)


class TurnWatchdog:
    def __init__(
        self,
        *,
        limit_s: float,
        out_dir: Path,
        run_id: str | None = None,
        dump_cmd: list[str] | None = None,
        on_fire: Callable[[dict[str, Any]], None] | None = None,
        exit_fn: Callable[[int], Any] = os._exit,
        clock: Callable[[], float] = time.monotonic,
        poll_s: float = 1.0,
    ) -> None:
        if not limit_s > 0:
            raise ValueError("turn watchdog limit must be positive")
        self.limit_s = float(limit_s)
        self.out_dir = Path(out_dir)
        self.run_id = run_id
        self.dump_cmd = list(dump_cmd) if dump_cmd else None
        self.on_fire = on_fire
        self._exit = exit_fn
        self._clock = clock
        self.poll_s = float(poll_s)
        self._lock = threading.Lock()
        self._armed: dict[str, Any] | None = None
        self._fired = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def config(self) -> dict[str, Any]:
        return {
            "limit_s": self.limit_s,
            "dump_cmd": self.dump_cmd,
            "exit_code": HANG_EXIT_CODE,
            "poll_s": self.poll_s,
        }

    def arm(self, *, entry_id: str, policy: str, turn: int) -> None:
        with self._lock:
            self._armed = {
                "entry_id": str(entry_id),
                "policy": str(policy),
                "turn": int(turn),
                "t0": self._clock(),
                "armed_utc": _utc_now(),
            }

    def disarm(self) -> None:
        with self._lock:
            self._armed = None

    def check(self) -> dict[str, Any] | None:
        """Fire if the armed turn is over the limit. Returns the record if fired."""
        with self._lock:
            armed = dict(self._armed) if self._armed is not None else None
            if armed is None or self._fired:
                return None
            elapsed = self._clock() - float(armed["t0"])
            if elapsed <= self.limit_s:
                return None
            self._fired = True
        return self.fire(armed, elapsed)

    def fire(self, armed: dict[str, Any], elapsed_s: float) -> dict[str, Any]:
        tag = f"{_safe(armed['entry_id'])}_t{armed['turn']}"
        record: dict[str, Any] = {
            "outcome": "hang",
            "run_id": self.run_id,
            "entry_id": armed["entry_id"],
            "policy": armed["policy"],
            "turn": armed["turn"],
            "armed_utc": armed["armed_utc"],
            "fired_utc": _utc_now(),
            "elapsed_s": round(float(elapsed_s), 3),
            "limit_s": self.limit_s,
            "pid": os.getpid(),
            "exit_code": HANG_EXIT_CODE,
            "errors": [],
        }
        try:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            stacks = self.out_dir / f"hang_stacks_{tag}.txt"
            with stacks.open("w", encoding="utf-8") as fh:
                faulthandler.dump_traceback(file=fh, all_threads=True)
            record["stacks"] = stacks.name
        except Exception as exc:
            record["errors"].append(f"stacks: {type(exc).__name__}: {exc}")
        if self.dump_cmd:
            record["dump"] = self._run_dump(tag, record)
        self._append_record(record)
        if self.on_fire is not None:
            try:
                self.on_fire(record)
            except Exception as exc:
                record["errors"].append(f"on_fire: {type(exc).__name__}: {exc}")
                self._append_record(record, replace_last=True)
        print(
            f"TURN_WATCHDOG_HANG entry={record['entry_id']} policy={record['policy']} "
            f"turn={record['turn']} elapsed_s={record['elapsed_s']} limit_s={self.limit_s}",
            flush=True,
        )
        self._exit(HANG_EXIT_CODE)
        return record

    def _run_dump(self, tag: str, record: dict[str, Any]) -> dict[str, Any]:
        assert self.dump_cmd is not None
        cmd = [part.replace("{pid}", str(os.getpid())) for part in self.dump_cmd]
        out = self.out_dir / f"hang_dump_{tag}.txt"
        doc: dict[str, Any] = {"cmd": cmd, "path": out.name}
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=DUMP_TIMEOUT_S)
            out.write_text(proc.stdout + proc.stderr, encoding="utf-8")
            doc["returncode"] = proc.returncode
        except Exception as exc:
            doc["error"] = f"{type(exc).__name__}: {exc}"
            record["errors"].append(f"dump: {doc['error']}")
        return doc

    def _append_record(self, record: dict[str, Any], *, replace_last: bool = False) -> None:
        path = self.out_dir / HANG_EVENTS_NAME
        try:
            rows: list[Any] = []
            if path.is_file():
                rows = list(json.loads(path.read_text(encoding="utf-8")).get("events") or [])
            if replace_last and rows:
                rows[-1] = record
            else:
                rows.append(record)
            path.write_text(
                json.dumps({"events": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        except Exception as exc:
            record["errors"].append(f"events: {type(exc).__name__}: {exc}")

    def _run(self) -> None:
        while not self._stop.wait(self.poll_s):
            self.check()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="turn-watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
