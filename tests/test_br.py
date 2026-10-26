"""Task BR: week-1 amendment predictions, runner options (default off) and STAT-1 tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.boot4_session as b4  # noqa: E402
import tools.run_resident_limit as rrl  # noqa: E402
from tools import br_predict as br  # noqa: E402
from tools import stat_cir  # noqa: E402


def test_prediction_files_match_generator() -> None:
    for name, doc in br.build_all().items():
        on_disk = json.loads((ROOT / "derived" / "br" / name).read_text(encoding="utf-8"))
        assert on_disk == json.loads(json.dumps(doc)), name


def test_budget_rule_and_session_law() -> None:
    rule = br.budget_rule()
    assert len(rule["cells"]) == 14
    assert 3.2e9 < rule["B_BR_bytes"] < 3.3e9
    s = br.build_sess()["held_out"]
    assert s["f16_T3072"]["L_hist"] == pytest.approx(17_300, rel=0.01)
    assert s["u4_T6144"]["L_hist"] == pytest.approx(51_700, rel=0.01)
    # in-sample, corrected lengths: within +-6%
    for row in br.build_sess()["in_sample_check_corrected_lengths"].values():
        assert abs(row["residual_pct"]) <= 6.0


def test_8b_a_rules_coincide() -> None:
    r = br.a_rules({"hidden_size": 4096, "intermediate_size": 12288})
    assert set(r.values()) == {114_688}
    assert br.build_m2b()["a_derivation"]["qwen3_8b"]["band_10pct"] == [103_219, 126_157]


def test_bcd_rule() -> None:
    b = 1 / 9
    assert b4.bcd_next(1000, False, 0.0, step=250, b=b, low=500, high=2000) == 750
    assert b4.bcd_next(1000, True, 0.05, step=250, b=b, low=500, high=2000) == 1250
    assert b4.bcd_next(1000, True, 0.5, step=250, b=b, low=500, high=2000) == 1000
    assert b4.bcd_next(500, False, 0.0, step=250, b=b, low=500, high=2000) == 500


def test_bcd_block_is_seeded_and_records_each_trial() -> None:
    def attempt(n: int) -> dict[str, Any]:
        return {"n_cached": n, "holds": n < 1500, "turn2_ttft_s": 1.0}

    a = b4.bcd_holds(
        start=1000,
        step=250,
        trials=12,
        target_hold=0.9,
        seed=7,
        low=0,
        high=4000,
        attempt=attempt,
    )
    b = b4.bcd_holds(
        start=1000,
        step=250,
        trials=12,
        target_hold=0.9,
        seed=7,
        low=0,
        high=4000,
        attempt=attempt,
    )
    assert a["bcd"]["sequence"] == b["bcd"]["sequence"]
    assert len(a["points"]) == 12 and all("bcd" in p for p in a["points"])
    assert a["bcd"]["next_level"] == a["points"][-1]["bcd"]["next_level"]
    assert stat_cir.next_start(a) == a["bcd"]["next_level"]


def test_cir_quantile_and_censoring() -> None:
    trials = [("s1", 1000, True)] * 10 + [("s1", 1250, True)] * 9 + [("s1", 1250, False)]
    trials += [("s2", 1500, False)] * 5 + [("s2", 1500, True)] * 5
    l90 = stat_cir.cir_quantile(trials, 0.9)
    l50 = stat_cir.cir_quantile(trials, 0.5)
    assert l90 is not None and l50 is not None and l90 < l50
    assert stat_cir.cir_quantile([("s", 1000, True)], 0.5) is None
    ci = stat_cir.bootstrap_ci(trials, 0.5, draws=200)
    assert ci["draws"] == 200
    assert stat_cir.reversals([1, 2, 3, 2, 2, 3]) == 2


BASE = ["--arm", "gpu_only_u4", "--model-spec", "configs/models/Qwen3-4B-int4-ov.yaml"]


def _cli(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> dict[str, Any]:
    seen: dict[str, Any] = {}

    def run(**_kw: Any) -> int:
        seen.update(b4.CC_OVERRIDE)
        seen["_sched"] = b4.SCHEDULER_OVERRIDE
        return 0

    monkeypatch.setattr(rrl, "run_resident_limit", run)
    monkeypatch.setattr(rrl, "run_cc_series", run)
    try:
        rrl.main(argv)
    finally:
        b4.set_pilot_overrides()
        b4.set_cc_overrides()
    return seen


def test_defaults_add_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _cli(monkeypatch, [*BASE, "--cc-cell", "CC-X", "--points", "1000"])
    assert "trial_telemetry" not in seen and "bcd" not in seen
    assert seen["_sched"] is None


def test_new_options(monkeypatch: pytest.MonkeyPatch) -> None:
    tel = ["--mem-trace-hz", "10", "--gpu-mem-stats", "--trial-telemetry"]
    seen = _cli(monkeypatch, [*BASE, "--cc-cell", "INV-1", "--points", "16384", *tel])
    assert seen["trial_telemetry"] is True
    seen = _cli(
        monkeypatch,
        [
            *BASE,
            "--cc-cell",
            "SESS-1",
            "--sched-max-batched-tokens",
            "18446744073709551615",
            "--sched-num-kv-blocks",
            "4086",
            "--grow-step",
            "2048",
            "--grow-max",
            "110000",
        ],
    )
    assert seen["_sched"]["num_kv_blocks"] == 4086
    seen = _cli(
        monkeypatch,
        [
            *BASE,
            "--cc-cell",
            "SESS-1",
            "--grow-step",
            "2048",
            "--grow-max",
            "61771",
            "--grow-final-step",
            "1024",
        ],
    )
    assert seen["grow"]["final_tokens"] == 1024
    seen = _cli(
        monkeypatch,
        [
            *BASE,
            "--cc-cell",
            "STAT-1",
            "--low",
            "20000",
            "--high",
            "30000",
            "--resolution",
            "250",
            "--bcd-start",
            "24000",
            "--bcd-trials",
            "6",
            "--bcd-seed",
            "11",
        ],
    )
    assert seen["bcd"]["start"] == 24000 and seen["bcd"]["step"] == 250


@pytest.mark.parametrize(
    "extra",
    [
        ["--trial-telemetry"],
        ["--grow-final-step", "512"],
        ["--sched-num-kv-blocks", "10"],
        ["--bcd-start", "24000", "--bcd-trials", "6", "--bcd-seed", "1"],
        [
            "--low",
            "20000",
            "--high",
            "30000",
            "--resolution",
            "250",
            "--bcd-start",
            "24100",
            "--bcd-trials",
            "6",
            "--bcd-seed",
            "1",
        ],
        [
            "--low",
            "20000",
            "--high",
            "30000",
            "--resolution",
            "250",
            "--bcd-start",
            "24000",
            "--bcd-trials",
            "3",
            "--bcd-seed",
            "1",
        ],
    ],
)
def test_new_options_refuse_bad_combinations(
    monkeypatch: pytest.MonkeyPatch, extra: list[str]
) -> None:
    with pytest.raises(SystemExit, match="REFUSED"):
        _cli(monkeypatch, [*BASE, "--cc-cell", "X", *extra])


def test_trial_telemetry_fields() -> None:
    child = {
        "parent_wall_s": 12.0,
        "child": {
            "exception": {"type": "RuntimeError", "message": "CL_OUT_OF_RESOURCES"},
            "memory_trace_at_failure": {"elapsed_to_exception_s": 3.5},
            "memory_trace_raw_at_failure": {"trace": [[1.0, 2.0, 3]]},
        },
    }
    f = b4.trial_telemetry_fields(child)
    assert f["time_to_fail_s"] == 3.5 and f["exception"]["type"] == "RuntimeError"
    assert f["memory_trace_raw_at_failure"]["trace"] == [[1.0, 2.0, 3]]


def test_pinned_balloon_counts_for_floor_credit(monkeypatch: pytest.MonkeyPatch) -> None:
    import psutil

    class _M:
        rss = 1
        private = 2**30

    class _P:
        def __init__(self, pid: int, cmd: list[str]) -> None:
            self.pid = pid
            self.info = {"pid": pid, "ppid": 1, "name": "python.exe", "cmdline": cmd}

        def memory_info(self) -> _M:
            return _M()

    procs = [_P(9, ["python.exe", "tools\\pinned_balloon.py", "--cpu", "--gib", "2"])]
    monkeypatch.setattr(psutil, "process_iter", lambda _a=None: iter(procs))
    assert b4.balloon_private_bytes()["balloon_pid"] == 9


def test_stat_session_tag_from_label(tmp_path: Path) -> None:
    f = tmp_path / "w1" / "stat_u4_unl_s2_b1" / "derived__x" / "summary.json"
    f.parent.mkdir(parents=True)
    f.write_text(json.dumps({"points": [{"n_cached": 24000, "holds": True}]}), encoding="utf-8")
    assert stat_cir.load_trials([f]) == [("s2", 24000, True)]


def test_child_trace_defaults_unchanged() -> None:
    """DEMO-2 and earlier CC specs never set trial_telemetry: the trace record keeps its keys."""
    from seam.tools import _delta_n_child as ch

    tr = ch.MemTrace(10.0, {}, read_gpu=False)
    assert set(tr.result()) == {
        "hz",
        "n",
        "errors",
        "available_min_mb",
        "gpu_stat_total_peak_bytes",
        "gpu_stat_total_first_bytes",
        "gpu_stat_total_last_bytes",
        "trace",
        "dxgi",
    }
    assert "type_trace" in ch.MemTrace(10.0, {}, read_gpu=False, types=True).result()
