"""Task BS: Rithwik runbooks (tools/rithwik_runbooks, tools/build_rithwik_runbooks.py).

The PowerShell bisection must make the same decisions as tools/xrt_llamacpp.bisect_plan; the pins
must equal configs/xrt/llamacpp_pin.yaml; the scripts must parse and stay inside the PowerShell 5.1
subset. Tests that need pwsh skip with a reason when it is absent; the dry-run against the fake
server also needs loopback TCP.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_rithwik_runbooks as brr  # noqa: E402
from tools import xrt_llamacpp as xrt  # noqa: E402

PWSH = shutil.which("pwsh")
needs_pwsh = pytest.mark.skipif(PWSH is None, reason="pwsh not installed")
SRC = ROOT / "tools" / "rithwik_runbooks"
PS_FILES = ["common.ps1", "rtx4070.ps1", "evo_x2.ps1", "collect.ps1"]
FAKE = ROOT / "tests" / "fixtures" / "fake_llama_server.py"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    d = tmp_path_factory.mktemp("rb")
    out = {}
    for m in brr.MACHINES:
        p = d / f"run_{m}.ps1"
        p.write_text(brr.build_run_script(m), encoding="ascii")
        out[m] = p
        c = d / f"collect_{m}.ps1"
        c.write_text(brr.build_collect(m), encoding="ascii")
        out[f"collect_{m}"] = c
    return out


def _selftest(script: Path, low: int, high: int, res: int, thr: int, prior: str = "") -> Any:
    assert PWSH is not None
    cmd = [PWSH, "-NoProfile", "-File", str(script), "-SelfTest", "-SelfTestLow", str(low),
           "-SelfTestHigh", str(high), "-SelfTestRes", str(res), "-SelfTestThreshold", str(thr),
           "-SelfTestPrior", prior]  # fmt: skip
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    assert r.returncode == 0, r.stdout + r.stderr
    line = next(ln for ln in r.stdout.splitlines() if ln.startswith("SELFTEST "))
    return json.loads(line[len("SELFTEST ") :])


CASES = [
    (4096, 65536, 1024, 37000),  # E3 f16 range, limit inside
    (4096, 65536, 1024, 2000),  # below low rung
    (4096, 65536, 1024, 70000),  # above range
    (8192, 196608, 1024, 131000),  # E3 q4_0 range
    (4096, 4194304, 1024, 470000),  # E5 L f16 range
    (8192, 4194304, 1024, 1650000),  # E5 L q4_0 range
    (4096, 131072, 1024, 131071),  # E5 P: one step under high
    (4096, 5120, 1024, 4500),  # one step range
]


@needs_pwsh
@pytest.mark.parametrize("machine", list(brr.MACHINES))
@pytest.mark.parametrize(("low", "high", "res", "thr"), CASES)
def test_powershell_bisection_matches_bisect_plan(
    built: dict[str, Path], machine: str, low: int, high: int, res: int, thr: int
) -> None:
    got = _selftest(built[machine], low, high, res, thr)
    want = xrt.bisect_plan(low=low, high=high, resolution=res, attempt=lambda n: n <= thr)
    assert got["status"] == want["status"]
    assert got["largest_hold"] == want["largest_hold"]
    assert got["first_fail"] == want["first_fail"]
    assert [(p["n"], p["holds"]) for p in got["points"]] == [
        (p["n"], p["holds"]) for p in want["points"]
    ]
    steps = (high - low) // res
    assert got["max_trials"] == 2 + math.ceil(math.log2(steps))
    assert len(want["points"]) <= got["max_trials"]


@needs_pwsh
def test_resume_replays_prior_rows_without_attempting(built: dict[str, Path]) -> None:
    got = _selftest(built["rtx4070"], 4096, 65536, 1024, 37000, "4096:hold,65536:fail,34816:hold")
    assert got["largest_hold"] == 36864
    assert 4096 not in got["attempted"] and 34816 not in got["attempted"]
    assert got["attempted"][0] == 50176
    assert got["tiled"] == [5, 6, 7, 5, 6, 7, 5, 6]


@needs_pwsh
def test_server_args_match_xrt_llamacpp() -> None:
    assert PWSH is not None
    ps = f". '{SRC / 'common.ps1'}'; (Get-ServerArgs 'M.gguf' 20480 128 'q4_0' 'on' 8091) -join ' '"
    r = subprocess.run([PWSH, "-NoProfile", "-Command", ps], capture_output=True, text=True,
                       timeout=60, check=True)  # fmt: skip
    want = xrt.build_server_cmd(server_exe="X", model="M.gguf", ctx=20480, ubatch=128, kv="q4_0",
                                fa="on", ngl=99, port=8091)[1:]  # fmt: skip
    assert r.stdout.strip().split(" ") == want


@needs_pwsh
@pytest.mark.parametrize("name", ["run_rtx4070", "run_evo-x2", "collect_rtx4070", "collect_evo-x2"])
def test_built_scripts_parse(built: dict[str, Path], name: str) -> None:
    assert PWSH is not None
    key = name.replace("run_", "")
    path = built[key]
    ps = (
        "$e = $null; $t = $null; "
        f"[void][System.Management.Automation.Language.Parser]::ParseFile('{path}', [ref]$t, [ref]$e); "
        "$e.Count"
    )
    r = subprocess.run([PWSH, "-NoProfile", "-Command", ps], capture_output=True, text=True,
                       timeout=60, check=True)  # fmt: skip
    assert r.stdout.strip() == "0", r.stdout


@pytest.mark.parametrize("name", PS_FILES)
def test_sources_ascii_and_ps51_subset(name: str) -> None:
    raw = (SRC / name).read_bytes()
    assert all(b < 128 for b in raw), f"{name} is not ASCII"
    text = raw.decode("ascii")
    code = "\n".join(ln.split("#", 1)[0] for ln in text.splitlines())
    for tok in ("??", "?.", "&&", "||", "-Parallel"):
        assert tok not in code, f"{name}: PowerShell 7-only construct {tok!r}"
    assert not re.search(r"\bGet-Error\b", code), f"{name}: Get-Error is PowerShell 7-only"
    assert "ConvertFrom-Json -AsHashtable" not in text
    assert "Out-File" not in text or "-Encoding ascii" in text


@pytest.mark.parametrize("name", ["common.ps1", "rtx4070.ps1", "evo_x2.ps1"])
def test_native_calls_go_through_invoke_native(name: str) -> None:
    """Windows PowerShell 5.1 + ErrorActionPreference Stop: a redirected native stderr line is a
    terminating error, so 2>&1 appears only inside Invoke-Native (collect.ps1 relaxes per section)."""
    lines = [ln for ln in (SRC / name).read_text().splitlines() if "2>&1" in ln.split("#", 1)[0]]
    assert all("ForEach-Object { [string]$_ }" in ln for ln in lines), lines


def test_pins_match_pin_yaml() -> None:
    pin = yaml.safe_load((ROOT / "configs" / "xrt" / "llamacpp_pin.yaml").read_text())
    common = (SRC / "common.ps1").read_text()
    g = pin["gguf"]
    assert g["url"] in common and g["sha256"] in common and str(g["size_bytes"]) in common
    evo = (SRC / "evo_x2.ps1").read_text()
    a = pin["llamacpp"]["assets"]
    assert a["vulkan"]["url"] in evo and a["vulkan"]["sha256"] in evo
    assert str(a["vulkan"]["size_bytes"]) in evo
    ra = pin["rithwik_assets"]
    rtx = (SRC / "rtx4070.ps1").read_text()
    for key, text in (("cuda_12_4", rtx), ("cudart_12_4", rtx), ("rocm", evo)):
        assert ra[key]["url"] in text and ra[key]["sha256"] in text
        assert str(ra[key]["size_bytes"]) in text
        assert ra[key]["url"].startswith(
            f"https://github.com/ggml-org/llama.cpp/releases/download/{pin['llamacpp']['tag']}/"
        )


def test_budget_counts_in_readmes() -> None:
    def cells(name: str) -> list[tuple[int, int]]:
        text = (SRC / name).read_text()
        found = re.findall(r"low = (\d+); high = (\d+); res = 1024; repeats = 1", text)
        return [(int(lo), int(hi)) for lo, hi in found]

    def total(cs: list[tuple[int, int]]) -> int:
        return sum(2 + math.ceil(math.log2((hi - lo) / 1024)) + 2 for lo, hi in cs)

    assert total(cells("rtx4070.ps1")) == 52
    assert "at most 52 trials" in (SRC / "README_rtx4070.md").read_text()
    assert total(cells("evo_x2.ps1")) == 54
    assert "at most 54 trials" in (SRC / "README_evo_x2.md").read_text()


def test_markdown_renderer_subset() -> None:
    html = brr.markdown_to_html(
        "# T\n\npara `code` **b**\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n1. one\n   - sub\n2. two\n",
        "T",
    )
    assert "<h1>T</h1>" in html and "<code>code</code>" in html and "<b>b</b>" in html
    assert "<td>1</td>" in html and "<ol><li>one<ul><li>sub</li></ul></li><li>two</li></ol>" in html


def _loopback_ok() -> bool:
    try:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            s.listen(1)
            port = s.getsockname()[1]
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return True
    except OSError:
        return False


@needs_pwsh
@pytest.mark.skipif(not _loopback_ok(), reason="no loopback TCP (sandbox)")
def test_dry_run_cell_against_fake_server(tmp_path: Path) -> None:
    """Invoke-Cell end to end (load, prefill, fail_load, fail_prefill, repeats, resume)."""
    assert PWSH is not None
    driver = tmp_path / "drive.ps1"
    driver.write_text(
        "param([string]$Root, [string]$Exe, [string]$Mode, [string]$Run)\n"
        f". '{SRC / 'common.ps1'}'\n"
        "$runDir = Join-Path $Root $Run\n"
        "if (-not (Test-Path $runDir)) { [void](New-Item -ItemType Directory -Path $runDir) }\n"
        "$script:TRANSCRIPT = Join-Path $runDir 'transcript.txt'\n"
        "$ctx = @{ machine = 'test'; runId = $Run; runDir = $runDir; exe = $Exe; model = 'm.gguf';"
        " port = 18191; timeoutS = 60; rowsPath = (Join-Path $runDir 'trials.jsonl'); tokenIds = $null;"
        " shareLabel = $null; beforeTrial = $null; afterTrial = $null }\n"
        "$cell = @{ id = 'C_' + $Mode; mode = $Mode; kv = 'f16'; fa = 'on'; ub = 512; low = 4096;"
        " high = 16384; res = 1024; repeats = 1 }\n"
        "Invoke-Cell $ctx $cell\n",
        encoding="ascii",
    )
    env = dict(os.environ, FAKE_LOAD_MAX="12000", FAKE_PREFILL_MAX="9000")

    def run(mode: str, run_name: str) -> list[dict[str, Any]]:
        subprocess.run(
            [PWSH, "-NoProfile", "-File", str(driver), "-Root", str(tmp_path), "-Exe", str(FAKE),
             "-Mode", mode, "-Run", run_name],
            env=env, capture_output=True, text=True, timeout=300, check=True,
        )  # fmt: skip
        rows_path = tmp_path / run_name / "trials.jsonl"
        return [json.loads(ln) for ln in rows_path.read_text().splitlines() if ln.strip()]

    load = run("load", "r_load")
    done = next(r for r in load if r["mode"] == "cell_done")
    assert (done["largest_hold"], done["first_fail"]) == (11264, 12288)
    pre = run("prefill", "r_pre")
    trials = [r for r in pre if r["mode"] == "trial"]
    done = next(r for r in pre if r["mode"] == "cell_done")
    assert (done["largest_hold"], done["first_fail"]) == (8192, 9216)
    assert {r["status"] for r in trials} == {"hold", "fail_load", "fail_prefill"}
    held = [r for r in trials if r["status"] == "hold"]
    assert all(r["prompt_n"] == r["n_ctx"] - 64 for r in held)
    assert held[0]["buffers"]["kv"]["CUDA0"] == pytest.approx(held[0]["n_ctx"] * 147456 / 2**20)
    assert [r["cause"] for r in trials if r["status"] == "fail_load"] == ["memory"]
    # resume: keep the first 4 trial rows only; the rerun must replay them and run the rest
    (tmp_path / "r_res").mkdir()
    (tmp_path / "r_res" / "trials.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in trials[:4])
    )
    res = run("prefill", "r_res")
    new = [r for r in res if r["mode"] == "trial"][4:]
    assert [r["n_ctx"] for r in new] == [8192, 9216, 8192, 9216]
    assert next(r for r in res if r["mode"] == "cell_done")["largest_hold"] == 8192
