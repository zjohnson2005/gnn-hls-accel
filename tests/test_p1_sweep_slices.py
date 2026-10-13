"""Amendment 9: the A4 B-sweep slices each fit the cold window.

launch_boot1.ps1 defers a cell when 7200 s minus uptime is below its
estimate. Amendment 8's A4|10|0|83 (7168 s) could never launch. Every slice
is now at most 6000 s. Hardware-free; the launcher table is read as text.
"""

from __future__ import annotations

import itertools
import json
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOT = ROOT / "tools" / "launch_boot1.ps1"
SWEEP = ROOT / "tools" / "launch_p1_sweep.ps1"
AMEND9 = ROOT / "derived" / "h1_hybrid" / "LOCAL_QUALITY_AMENDMENT_9.json"
CAP_S = 6000
LOAD_S = 5.211120400010259
CANARY_S = 752.1359013
A0_SEALED = ROOT / "derived" / "p1_quality" / "sealed_8a529053-fc47-486d-8809-6c699d156b06"
A0_SWEEP = ROOT / "derived" / "p1_quality" / "sealed_bdc32a87-8f91-4cd5-9cb0-2daafe659fc8"


def _table() -> dict[tuple[str, int, int, int], int]:
    text = BOOT.read_text(encoding="utf-8")
    block = text[text.index("$sweepEstimates = @{") :]
    block = block[: block.index("}")]
    rows = re.findall(r'"(A0|A4)\|(\d+)\|(\d+)\|(\d+)" = (\d+)', block)
    return {(a, int(b), int(o), int(c)): int(e) for a, b, o, c, e in rows}


def test_every_row_fits_6000() -> None:
    table = _table()
    assert len(table) == 27
    assert all(est <= CAP_S for est in table.values()), table


@pytest.mark.parametrize("arm", ["A0", "A4"])
@pytest.mark.parametrize("budget", [10, 20, 30])
def test_slices_cover_0_200_without_overlap(arm: str, budget: int) -> None:
    slices = sorted((o, c) for (a, b, o, c) in _table() if a == arm and b == budget)
    covered: list[int] = []
    for offset, count in slices:
        covered.extend(range(offset, offset + count))
    assert covered == list(range(200)), (arm, budget, slices)
    for (o1, c1), (o2, _c2) in itertools.pairwise(slices):
        assert o1 + c1 == o2


def test_old_amendment_8_a4_slices_are_refused() -> None:
    table = _table()
    for key in (
        ("A4", 10, 0, 83),
        ("A4", 10, 83, 17),
        ("A4", 20, 0, 43),
        ("A4", 20, 43, 40),
        ("A4", 20, 83, 17),
        ("A4", 30, 0, 27),
        ("A4", 30, 27, 30),
        ("A4", 30, 57, 25),
        ("A4", 30, 82, 18),
    ):
        assert key not in table
    text = BOOT.read_text(encoding="utf-8")
    assert 'throw "REFUSED -- P1 sweep cell $sweepKey is not a registered boot"' in text
    assert 'throw "REFUSED -- P1 sweep seed $P1Seed is not registered"' in text


def test_table_equals_amendment_9() -> None:
    doc = json.loads(AMEND9.read_text(encoding="utf-8"))
    from_amend = {
        (b["arm"], b["budget_s"], b["entry_offset"], b["entry_count"]): b["estimate_s"]
        for b in doc["boots"]
    }
    assert from_amend == _table()
    assert doc["estimator"]["cap_s"] == CAP_S
    assert doc["runner_must_not_read_this_file"] is True


def test_sweep_code_does_not_name_the_amendment() -> None:
    boot = BOOT.read_text(encoding="utf-8")
    block = boot[boot.index('} elseif ($Profile -eq "p1-sweep") {') :]
    block = block[: block.index("} elseif ($Profile -eq")]
    for text in (block, SWEEP.read_text(encoding="utf-8")):
        assert "LOCAL_QUALITY_AMENDMENT" not in text


def test_sweep_header_lists_every_boot() -> None:
    text = SWEEP.read_text(encoding="utf-8")
    for arm, budget, offset, count in _table():
        args = "-Detach"
        if arm == "A4":
            args += " -Arm A4"
        if budget != 10:
            args += f" -BudgetS {budget}"
        if offset != 0:
            args += f" -EntryOffset {offset}"
        if count != 100:
            args += f" -EntryCount {count}"
        assert f"launch_p1_sweep.ps1 {args}'" in text, (arm, budget, offset, count)


@pytest.mark.skipif(
    not (A0_SEALED / "points").is_dir() or not (A0_SWEEP / "points").is_dir(),
    reason="sealed A0 points not present",
)
def test_a4_estimates_recompute_from_sealed_step_counts() -> None:
    def steps(run: Path) -> dict[str, int]:
        out = {}
        for path in (run / "points").glob("*.json"):
            point = json.loads(path.read_text(encoding="utf-8"))
            out[str(point["id"])] = len(point["steps"])
        return out

    a0 = steps(A0_SEALED)
    sweep = steps(A0_SWEEP)
    ids = sorted(a0)
    counts = [max(a0[i], sweep.get(i, 0)) for i in ids]
    # Amendment 8's formula on 8a529053 alone reproduces its own 7168.
    assert math.ceil(sum(a0[i] for i in ids[:83]) * 10 + LOAD_S + CANARY_S) == 7168
    for (arm, budget, offset, count), est in _table().items():
        if arm != "A4":
            continue
        n = sum(counts[offset : offset + count])
        assert math.ceil(n * budget + LOAD_S + CANARY_S) == est
