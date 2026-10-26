"""INV-1 tools: alloc probe, pinned balloon, commit sidecar. Hardware-free (fakes only)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.inv_alloc_probe as iap  # noqa: E402
import tools.inv_commit_sidecar as ics  # noqa: E402
import tools.pinned_balloon as pb  # noqa: E402

MIB = 1024 * 1024


class _FakeBackend:
    def __init__(self, fail_at: int | None, step: str, msg: str = "CL_OUT_OF_RESOURCES") -> None:
        self.fail_at = fail_at
        self.step = step
        self.msg = msg
        self.n_create = 0
        self.touched: list[int] = []

    def create(self, n_bytes: int) -> Any:
        i = self.n_create
        self.n_create += 1
        if self.fail_at == i and self.step == "create":
            raise RuntimeError(self.msg)
        return ("chunk", i, n_bytes)

    def touch(self, obj: Any, n_bytes: int) -> None:
        if self.fail_at == obj[1] and self.step == "touch":
            raise MemoryError(self.msg)
        self.touched.append(n_bytes)

    def start_info(self) -> dict[str, Any]:
        return {"GPU_DEVICE_TOTAL_MEM_SIZE": 123}

    def row_info(self) -> dict[str, Any]:
        return {"gpu_memory_statistics": {"usm_device": 1}, "dxgi": {"error": "not windows"}}


def _host() -> dict[str, Any]:
    return {"available_mb": 1000.0, "private_bytes": None}


@pytest.mark.parametrize("step", ["create", "touch"])
def test_probe_stops_at_first_failing_chunk(step: str) -> None:
    be = _FakeBackend(fail_at=3, step=step)
    res = iap.run_probe(
        be, mode="device", chunk_bytes=256 * MIB, max_bytes=16 * 1024 * MIB, host_mem=_host
    )
    assert res.ceiling_bytes == 3 * 256 * MIB
    assert res.stop_reason == "exception"
    assert res.failed_step == step
    assert res.failed_chunk == 3
    assert res.exception_type == ("RuntimeError" if step == "create" else "MemoryError")
    assert [r["i"] for r in res.rows] == [0, 1, 2]
    assert res.rows[-1]["cumulative_bytes"] == 3 * 256 * MIB
    assert res.rows[0]["available_mb"] == 1000.0
    assert res.start["GPU_DEVICE_TOTAL_MEM_SIZE"] == 123
    assert be.n_create == 4  # never allocates after the failure


def test_probe_max_gib_and_partial_last_chunk() -> None:
    be = _FakeBackend(fail_at=None, step="create")
    res = iap.run_probe(be, mode="ocl", chunk_bytes=256 * MIB, max_bytes=600 * MIB, host_mem=_host)
    assert res.stop_reason == "max_gib"
    assert res.ceiling_bytes == 600 * MIB
    assert be.touched == [256 * MIB, 256 * MIB, 88 * MIB]


def test_probe_message_truncated_and_summary_line() -> None:
    be = _FakeBackend(fail_at=0, step="create", msg="x" * 9000)
    res = iap.run_probe(be, mode="host", chunk_bytes=MIB, max_bytes=4 * MIB, host_mem=_host)
    assert res.ceiling_bytes == 0
    assert len(res.exception_message or "") == iap.MSG_CHARS
    line = iap.summary_line(res)
    assert line.startswith("ALLOC_RESULT {")
    s = json.loads(line[len("ALLOC_RESULT ") :])
    assert set(s) == {
        "mode",
        "chunk_mib",
        "ceiling_bytes",
        "ceiling_gib",
        "stop_reason",
        "exception_type",
        "exception_head",
    }
    assert len(s["exception_head"]) == iap.HEAD_CHARS
    assert s["mode"] == "host"
    assert s["chunk_mib"] == 1.0


def test_atomic_write_json(tmp_path: Path) -> None:
    p = tmp_path / "sub" / "r.json"
    iap.atomic_write_json(p, {"a": 1})
    iap.atomic_write_json(p, {"a": 2})
    assert json.loads(p.read_text()) == {"a": 2}
    assert not (tmp_path / "sub" / "r.json.tmp").exists()


def test_probe_main_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "o.json"
    rc = iap.main(
        ["--mode", "device", "--chunk-mib", "256", "--max-gib", "2", "--out", str(out)],
        backend_factory=lambda _m: _FakeBackend(fail_at=2, step="touch"),
    )
    assert rc == 0
    data = json.loads(out.read_text())
    assert data["ceiling_bytes"] == 512 * MIB
    assert data["failed_step"] == "touch"
    assert "ALLOC_RESULT" in capsys.readouterr().out

    def _boom(mode: str) -> Any:
        raise RuntimeError("no GPU")

    rc = iap.main(["--mode", "device", "--out", str(out)], backend_factory=_boom)
    assert rc == 2


def test_probe_rejects_bad_mode() -> None:
    with pytest.raises(SystemExit):
        iap.build_parser().parse_args(["--mode", "zzz", "--out", "x"])


# ---------------------------------------------------------------- pinned balloon


@pytest.mark.parametrize(
    "argv",
    [
        ["--gib", "1", "--stop-file", "s"],
        ["--gpu", "--cpu", "--gib", "1", "--stop-file", "s"],
        ["--cpu", "--gib", "0", "--stop-file", "s"],
        ["--cpu", "--gib", "-1", "--stop-file", "s"],
    ],
)
def test_balloon_args_rejected(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        pb.parse_args(argv)


def test_balloon_args_ok() -> None:
    a = pb.parse_args(["--cpu", "--gib", "1.5", "--stop-file", "s"])
    assert a.cpu and not a.gpu
    assert a.touch_period_ms == 10.0
    assert a.max_hours == 8.0


class _FakePlat:
    def __init__(self, lock_ok: bool) -> None:
        self.lock_ok = lock_ok
        self.calls: list[str] = []

    def virtual_alloc(self, n_bytes: int) -> tuple[int, int]:
        self.calls.append("alloc")
        return (0x10000, 0)

    def set_working_set(self, min_bytes: int, max_bytes: int) -> tuple[bool, int]:
        self.calls.append(f"ws {min_bytes} {max_bytes}")
        return (True, 0)

    def touch_pages(self, addr: int, n_bytes: int) -> None:
        self.calls.append("touch")

    def virtual_lock(self, addr: int, n_bytes: int) -> tuple[bool, int]:
        self.calls.append("lock")
        return (self.lock_ok, 0 if self.lock_ok else 1453)

    def release(self, addr: int, n_bytes: int) -> None:
        self.calls.append("release")


def test_balloon_cpu_lock_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    plat = _FakePlat(lock_ok=False)
    rc = pb.main(
        ["--cpu", "--gib", "1", "--stop-file", str(tmp_path / "stop")],
        cpu_platform=lambda: plat,
        counters=dict,
        sleep=lambda _s: None,
    )
    out = capsys.readouterr().out
    assert rc == 2
    assert "BALLOON_FAILED" in out
    assert "1453" in out
    assert "BALLOON_READY" not in out
    gib = 1024 * MIB
    assert plat.calls == [
        "alloc",
        f"ws {gib + 256 * MIB} {gib + 512 * MIB}",
        "touch",
        "lock",
        "release",
    ]


def test_balloon_cpu_ok_until_stop(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    stop = tmp_path / "stop"
    stop.write_text("x")
    rc = pb.main(
        ["--cpu", "--gib", "0.5", "--stop-file", str(stop)],
        cpu_platform=lambda: _FakePlat(lock_ok=True),
        counters=lambda: {"shared_usage_mb": 0.0},
        sleep=lambda _s: None,
    )
    lines = capsys.readouterr().out.splitlines()
    assert rc == 0
    ready = json.loads(lines[0][len("BALLOON_READY ") :])
    assert ready["method"] == "cpu_virtuallock"
    assert ready["locked"]["ok"] is True
    assert ready["working_set_result"]["ok"] is True
    assert lines[1].startswith("BALLOON_RELEASED ")


class _FakeGpu:
    def __init__(self, n_bytes: int, fail_from: int | None = None) -> None:
        self.chunks = [0, 1]
        self.bytes = n_bytes
        self.opset_name = "fake"
        self.n = 0
        self.fail_from = fail_from

    def infer_chunk(self, i: int) -> None:
        self.n += 1
        if self.fail_from is not None and self.n >= self.fail_from:
            raise RuntimeError("infer failed")

    def release(self) -> None:
        pass


def test_balloon_gpu_consecutive_failures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc = pb.main(
        ["--gpu", "--gib", "0.5", "--stop-file", str(tmp_path / "stop")],
        gpu_factory=lambda n: _FakeGpu(n, fail_from=2),
        counters=dict,
        sleep=lambda _s: None,
    )
    out = capsys.readouterr().out
    assert rc == 2
    assert "BALLOON_READY" in out
    assert "11 consecutive infer failures" in out


def test_balloon_gpu_release(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    stop = tmp_path / "stop"
    fake = _FakeGpu(512 * MIB)

    def _sleep(s: float) -> None:
        stop.write_text("x")

    rc = pb.main(
        ["--gpu", "--gib", "0.5", "--stop-file", str(stop)],
        gpu_factory=lambda _n: fake,
        counters=dict,
        sleep=_sleep,
    )
    lines = capsys.readouterr().out.splitlines()
    assert rc == 0
    ready = json.loads(lines[0][len("BALLOON_READY ") :])
    assert ready["method"] == "gpu_usm_device_gather_kernel"
    assert ready["infer_ok_first"] is True
    rel = json.loads(lines[1][len("BALLOON_RELEASED ") :])
    assert rel["n_infers"] == 3
    assert rel["errors"] == 0


def test_balloon_gpu_setup_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    def _boom(n: int) -> Any:
        raise RuntimeError("USM not supported")

    rc = pb.main(
        ["--gpu", "--gib", "1", "--stop-file", str(tmp_path / "s")],
        gpu_factory=_boom,
        counters=dict,
        sleep=lambda _s: None,
    )
    assert rc == 2
    assert "BALLOON_FAILED RuntimeError: USM not supported" in capsys.readouterr().out


# ---------------------------------------------------------------- commit sidecar


def test_sidecar_rows_and_stop(tmp_path: Path) -> None:
    out = tmp_path / "c.csv"
    stop = tmp_path / "stop"
    t = [1000.0]
    n_samples = [0]

    def clock() -> float:
        return t[0]

    def sleep(s: float) -> None:
        t[0] += 0.05
        if n_samples[0] >= 5:
            stop.write_text("x")

    def sampler() -> dict[str, int]:
        n_samples[0] += 1
        if n_samples[0] == 3:
            raise OSError("boom")
        return {k: i + n_samples[0] for i, k in enumerate(ics.FIELDS)}

    rows = ics.run(out, stop, hz=20.0, max_hours=1.0, sampler=sampler, clock=clock, sleep=sleep)
    assert rows == 5
    with out.open() as fh:
        data = list(csv.reader(fh))
    assert tuple(data[0]) == ics.HEADER
    assert len(data) == 6
    assert data[1][1] == "1"
    assert data[3][-1] == "OSError: boom"
    assert data[3][1] == ""


def test_sidecar_max_hours(tmp_path: Path) -> None:
    t = [0.0]

    def sleep(s: float) -> None:
        t[0] += 1.0

    rows = ics.run(
        tmp_path / "c.csv",
        tmp_path / "never",
        hz=1.0,
        max_hours=10.0 / 3600,
        sampler=lambda: dict.fromkeys(ics.FIELDS, 0),
        clock=lambda: t[0],
        sleep=sleep,
    )
    assert rows == 10


def test_sidecar_main_off_windows(tmp_path: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("checks the non-Windows refusal")
    rc = ics.main(["--out-csv", str(tmp_path / "c.csv"), "--stop-file", str(tmp_path / "s")])
    assert rc == 2
