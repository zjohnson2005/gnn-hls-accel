"""Task BR: tools/xrt_llamacpp.py pure helpers and loop logic (no GPU, no network, no llama.cpp)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import xrt_llamacpp as xrt  # noqa: E402

SYCL_LOG = """\
load_tensors: loading model tensors, this can take a while... (mmap = true)
load_tensors: offloading 36 repeating layers to GPU
load_tensors: offloaded 37/37 layers to GPU
load_tensors:        SYCL0 model buffer size =  2124.81 MiB
load_tensors:   CPU_Mapped model buffer size =   304.28 MiB
llama_context: n_ctx         = 16384
llama_context: flash_attn    = enabled
llama_context:  SYCL_Host  output buffer size =     0.58 MiB
llama_kv_cache:      SYCL0 KV buffer size =  2304.00 MiB
llama_kv_cache: size = 2304.00 MiB ( 16384 cells,  36 layers,  1/1 seqs), K (f16): 1152.00 MiB
llama_context:      SYCL0 compute buffer size =   300.75 MiB
llama_context:  SYCL_Host compute buffer size =    40.01 MiB
main: model loaded
main: server is listening on http://127.0.0.1:8091
"""

VULKAN_LOG = """\
ggml_vulkan: 0 = Intel(R) Graphics (Intel Corporation) | uma: 1 | fp16: 1
load_tensors:      Vulkan0 model buffer size =  2124.81 MiB
load_tensors:          CPU model buffer size =   304.28 MiB
llama_kv_cache:    Vulkan0 KV buffer size =   576.00 MiB
llama_kv_cache:    Vulkan0 KV buffer size =    64.00 MiB
llama_context:    Vulkan0 compute buffer size =  1200.50 MiB
llama_context: Vulkan_Host compute buffer size =    72.01 MiB
"""

REFUSAL_LOG = """\
load_tensors:        SYCL0 model buffer size =  2124.81 MiB
llama_init_from_model: quantized V cache requires flash_attn to be enabled
common_init_from_params: failed to create context with model 'Qwen3-4B-Q4_K_M.gguf'
srv    load_model: failed to load model, 'Qwen3-4B-Q4_K_M.gguf'
main: exiting due to model loading error
"""


def test_parse_buffers_sycl_multi_device() -> None:
    got = xrt.parse_buffers(SYCL_LOG)
    assert got == {
        "model": {"SYCL0": 2124.81, "CPU_Mapped": 304.28},
        "output": {"SYCL_Host": 0.58},
        "kv": {"SYCL0": 2304.0},
        "compute": {"SYCL0": 300.75, "SYCL_Host": 40.01},
    }


def test_parse_buffers_vulkan_sums_repeated_device() -> None:
    got = xrt.parse_buffers(VULKAN_LOG)
    assert got["model"] == {"Vulkan0": 2124.81, "CPU": 304.28}
    assert got["kv"] == {"Vulkan0": 640.0}
    assert got["compute"] == {"Vulkan0": 1200.5, "Vulkan_Host": 72.01}


def test_refusal_and_errors() -> None:
    assert xrt.find_refusal(REFUSAL_LOG) == (
        "llama_init_from_model: quantized V cache requires flash_attn to be enabled"
    )
    assert xrt.find_refusal("V cache quantization requires flash_attn\n") is not None
    assert xrt.find_refusal(SYCL_LOG) is None
    errs = xrt.error_lines(REFUSAL_LOG)
    assert any("failed to load model" in e for e in errs)
    assert xrt.error_lines(SYCL_LOG) == []
    assert xrt.parse_buffers(REFUSAL_LOG) == {"model": {"SYCL0": 2124.81}}


def test_build_server_cmd_exact() -> None:
    cmd = xrt.build_server_cmd(
        server_exe="llama-server.exe", model="m.gguf", ctx=16384, ubatch=4096, kv="q8_0",
        fa="off", ngl=99, port=8091,
    )  # fmt: skip
    assert cmd == [
        "llama-server.exe", "-m", "m.gguf", "-c", "16384", "-b", "4096", "-ub", "4096",
        "-ctk", "q8_0", "-ctv", "q8_0", "-fa", "off", "-ngl", "99", "--fit", "off",
        "-np", "1", "--cache-ram", "0", "--no-warmup", "--host", "127.0.0.1", "--port", "8091",
    ]  # fmt: skip
    small = xrt.build_server_cmd(
        server_exe="s", model="m", ctx=4096, ubatch=128, kv="f16", fa="on", ngl=99, port=1
    )
    assert small[small.index("-b") + 1] == "2048"
    with pytest.raises(ValueError):
        xrt.build_server_cmd(
            server_exe="s", model="m", ctx=4096, ubatch=128, kv="q4_1", fa="on", ngl=99, port=1
        )
    with pytest.raises(ValueError):
        xrt.build_server_cmd(
            server_exe="s", model="m", ctx=4096, ubatch=128, kv="f16", fa="auto", ngl=99, port=1
        )


def test_child_env_adds_sysman() -> None:
    env = xrt.build_child_env({"PATH": "x", "ZES_ENABLE_SYSMAN": "0"})
    assert env == {"PATH": "x", "ZES_ENABLE_SYSMAN": "1"}


def test_tile_tokens() -> None:
    assert xrt.tile_tokens([1, 2, 3], 7) == [1, 2, 3, 1, 2, 3, 1]
    assert xrt.tile_tokens([5], 0) == []
    assert len(xrt.tile_tokens(list(range(97)), 40_896)) == 40_896
    with pytest.raises(ValueError):
        xrt.tile_tokens([], 3)


def test_bisect_plan_matches_grid_semantics() -> None:
    calls: list[int] = []

    def attempt(n: int) -> bool:
        calls.append(n)
        return n <= 21_000

    got = xrt.bisect_plan(low=10_000, high=40_000, resolution=500, attempt=attempt)
    assert got["status"] == "complete"
    assert got["largest_hold"] == 21_000
    assert got["first_fail"] == 21_500
    assert calls[:2] == [10_000, 40_000]
    assert len(set(calls)) == len(calls)
    assert all((n - 10_000) % 500 == 0 for n in calls)


def test_bisect_plan_low_and_high_edges() -> None:
    below = xrt.bisect_plan(low=1000, high=2000, resolution=500, attempt=lambda _n: False)
    assert below["status"] == "below_low_rung"
    assert below["note"] == "below low rung"
    assert below["largest_hold"] is None
    assert [p["n"] for p in below["points"]] == [1000]
    above = xrt.bisect_plan(low=1000, high=2000, resolution=500, attempt=lambda _n: True)
    assert above["status"] == "above_range"
    assert above["largest_hold"] == 2000
    with pytest.raises(ValueError):
        xrt.bisect_plan(low=1000, high=2100, resolution=500, attempt=lambda _n: True)


# ---------------------------------------------------------------- fakes


class FakeProc:
    def __init__(self, server: FakeServer, cmd: list[str], log_path: Path) -> None:
        self.server = server
        self.cmd = cmd
        self.code: int | None = None
        ctx = int(cmd[cmd.index("-c") + 1])
        kv = cmd[cmd.index("-ctk") + 1]
        fa = cmd[cmd.index("-fa") + 1]
        self.ctx = ctx
        log_path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["load_tensors:        SYCL0 model buffer size =  2124.81 MiB"]
        if kv != "f16" and fa == "off":
            lines.append(
                "llama_init_from_model: quantized V cache requires flash_attn to be enabled"
            )
            lines.append("main: exiting due to model loading error")
            self.code = 1
        elif ctx > server.load_limit:
            lines.append("ggml_sycl: UR_RESULT_ERROR_OUT_OF_DEVICE_MEMORY")
            self.code = 3
        else:
            kv_mib = ctx * (144 if kv == "f16" else 77) / 1024
            lines.append(f"llama_kv_cache:      SYCL0 KV buffer size = {kv_mib:8.2f} MiB")
            lines.append("llama_context:      SYCL0 compute buffer size =   300.75 MiB")
            lines.append("main: model loaded")
        log_path.write_text("\n".join(lines) + "\n", encoding="ascii")

    def poll(self) -> int | None:
        return self.code

    def terminate(self) -> None:
        self.code = 1

    def kill(self) -> None:
        self.code = -9

    def wait(self, timeout: float | None = None) -> int:
        if self.code is None:
            raise subprocess.TimeoutExpired("x", timeout or 0)
        return self.code


class FakeServer:
    def __init__(self, load_limit: int = 10**9, prefill_limit: int = 10**9) -> None:
        self.load_limit = load_limit
        self.prefill_limit = prefill_limit
        self.procs: list[FakeProc] = []
        self.envs: list[dict[str, str]] = []
        self.tokenize_calls = 0
        self.t = 0.0

    def live(self) -> FakeProc | None:
        alive = [p for p in self.procs if p.code is None]
        return alive[-1] if alive else None

    def launcher(self, cmd: list[str], env: dict[str, str], log_path: Path) -> xrt.ServerHandle:
        self.envs.append(env)
        proc = FakeProc(self, cmd, log_path)
        self.procs.append(proc)
        return proc

    def http(self, method: str, url: str, body: Any, timeout_s: float) -> xrt.HttpResult:
        proc = self.live()
        if proc is None:
            return xrt.HttpResult(0, None, "refused")
        if url.endswith("/health"):
            return xrt.HttpResult(200, {"status": "ok"}, "{}")
        if url.endswith("/tokenize"):
            self.tokenize_calls += 1
            return xrt.HttpResult(200, {"tokens": list(range(1, 38))}, "{}")
        assert url.endswith("/completion")
        n = len(body["prompt"])
        assert body["n_predict"] == 1 and body["cache_prompt"] is False
        if proc.ctx > self.prefill_limit:
            proc.code = -1073741819
            return xrt.HttpResult(0, None, "URLError: connection reset")
        out = {"timings": {"prompt_n": n, "prompt_ms": 1.5 * n}, "tokens_evaluated": n}
        return xrt.HttpResult(200, out, json.dumps(out))

    def clock(self) -> float:
        self.t += 0.25
        return self.t

    def runtime(self) -> xrt.Runtime:
        return xrt.Runtime(
            launcher=self.launcher,
            http=self.http,
            sleep=lambda _s: None,
            clock=self.clock,
            env_base={"PATH": "p"},
        )


def _rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def test_census_loop_with_fake_server(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeServer()
    out = tmp_path / "census.jsonl"
    rc = xrt.main(
        [
            "census",
            "--server-exe",
            "llama-server.exe",
            "--model",
            "m.gguf",
            "--ctx-list",
            "4096,16384",
            "--ubatch-list",
            "512",
            "--kv-list",
            "f16,q8_0",
            "--fa-list",
            "on,off",
            "--log-dir",
            str(tmp_path / "logs"),
            "--out-jsonl",
            str(out),
            "--label",
            "t1",
        ],
        rt=fake.runtime(),
    )
    assert rc == 0
    rows = _rows(out)
    assert len(rows) == 8
    assert all(e["ZES_ENABLE_SYSMAN"] == "1" and e["PATH"] == "p" for e in fake.envs)
    by = {(r["ctx"], r["kv"], r["fa"]): r for r in rows}
    ref = by[(4096, "q8_0", "off")]
    assert ref["status"] == "refused"
    assert "requires flash_attn" in ref["error"]
    ok = by[(16384, "f16", "on")]
    assert ok["status"] == "ready"
    assert ok["error"] is None
    assert ok["buffers"]["kv"] == {"SYCL0": 2304.0}
    assert ok["buffers"]["compute"] == {"SYCL0": 300.75}
    assert "--fit" in ok["cmd"] and ok["cmd"][ok["cmd"].index("--fit") + 1] == "off"
    assert ok["batch"] == 2048
    assert Path(ok["log_path"]).exists()
    last = capsys.readouterr().out.strip().splitlines()[-1]
    assert last.startswith("XRT_DONE ")
    summary = json.loads(last[len("XRT_DONE ") :])
    assert summary["counts"] == {"ready": 6, "refused": 2}
    # same label again refuses rather than overwriting logs
    rc2 = xrt.main(
        [
            "census",
            "--server-exe",
            "s",
            "--model",
            "m",
            "--ctx-list",
            "4096",
            "--ubatch-list",
            "512",
            "--kv-list",
            "f16",
            "--fa-list",
            "on",
            "--log-dir",
            str(tmp_path / "logs"),
            "--out-jsonl",
            str(out),
            "--label",
            "t1",
        ],
        rt=fake.runtime(),
    )
    assert rc2 == 2


def test_census_timeout_status(tmp_path: Path) -> None:
    fake = FakeServer()

    def never_ready(method: str, url: str, body: Any, timeout_s: float) -> xrt.HttpResult:
        return (
            xrt.HttpResult(0, None, "refused")
            if fake.live() is None
            else xrt.HttpResult(503, {"error": {"message": "Loading model"}}, "{}")
        )

    rt = fake.runtime()
    rt.http = never_ready
    (tmp_path / "logs").mkdir()
    summary = xrt.run_census(
        server_exe="s", model="m", ctx_list=[4096], ub_list=[512], kv_list=["f16"],
        fa_list=["on"], ngl=99, port=8091, timeout_s=5.0, log_dir=tmp_path / "logs",
        out_jsonl=tmp_path / "o.jsonl", label="t2", rt=rt,
    )  # fmt: skip
    # the fake log says "model loaded" but not "listening on": readiness needs /health 200
    assert summary["counts"] == {"timeout": 1}


def test_boundary_with_fake_server(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fake = FakeServer(load_limit=30_000, prefill_limit=21_000)
    out = tmp_path / "bnd.jsonl"
    rc = xrt.main(
        [
            "boundary",
            "--server-exe",
            "s",
            "--model",
            "m",
            "--kv",
            "q4_0",
            "--low",
            "10000",
            "--high",
            "40000",
            "--resolution",
            "500",
            "--slider-pct",
            "57",
            "--repeats-at-boundary",
            "1",
            "--log-dir",
            str(tmp_path / "logs"),
            "--out-jsonl",
            str(out),
            "--label",
            "b1",
        ],
        rt=fake.runtime(),
    )
    assert rc == 0
    rows = _rows(out)
    assert fake.tokenize_calls == 1
    statuses = {r["status"] for r in rows}
    assert statuses == {"hold", "fail_load", "fail_prefill"}
    hold = next(r for r in rows if r["status"] == "hold")
    assert hold["prompt_n"] == hold["n_ctx"] - 64 == hold["n_prompt"]
    assert hold["slider_pct"] == 57 and hold["error"] is None
    assert hold["cmd"][hold["cmd"].index("-fa") + 1] == "on"
    fl = next(r for r in rows if r["status"] == "fail_load")
    assert fl["n_ctx"] == 40_000 and "OUT_OF_DEVICE_MEMORY" in fl["error"]
    rep = [r for r in rows if r["phase"] == "repeat"]
    assert [(r["n_ctx"], r["status"]) for r in rep] == [(21_000, "hold"), (21_500, "fail_prefill")]
    last = capsys.readouterr().out.strip().splitlines()[-1]
    summary = json.loads(last[len("XRT_DONE ") :])
    assert summary["largest_hold"] == 21_000
    assert summary["first_fail"] == 21_500
    assert summary["status"] == "complete"


def test_source_is_ascii() -> None:
    for p in (ROOT / "tools" / "xrt_llamacpp.py", Path(__file__)):
        p.read_bytes().decode("ascii")
