"""One delta-N ladder repeat, isolated in its own process.

Process isolation is the safety property that makes the ceiling search survivable. A rung at
or past the ceiling exhausts memory, and the failure arrives as an allocation throw, an access
violation, or the OS killing the process outright. A child takes only its own repeat with it;
the parent records the failure mode and the ladder continues. It also makes teardown between
rungs total rather than best-effort, since process exit returns everything the allocator was
holding.

Nothing here touches ``raw/``. The child reports JSON on a path the parent chose, and the
parent owns every sealed artifact.

Output is rewritten after each phase so that a child which is killed mid-generation still
leaves behind the phase it reached. A missing field is therefore evidence, not a gap.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

import psutil

MB = 1024.0 * 1024.0
_REPLACE_POLICY: tuple[int, float] | None = None


def cc_mem_snapshot(stage: str, cores: dict[str, Any]) -> dict[str, Any]:
    """CC cells (Task BJ; spec gpu_mem_stats): one memory record, outside any timed generate.

    GPU_MEMORY_STATISTICS is read through the Core used for the load (same plugin state as the
    KV readback). Whether it sees GenAI's allocations is UNVERIFIED until a smoke shows bytes
    that grow with n; any read that fails is recorded as an error string, never raised.
    """
    import os

    from seam.turn_memory import read_gpu_counters

    stats: dict[str, Any] = {}
    for device, core in cores.items():
        try:
            raw = core.get_property(device, "GPU_MEMORY_STATISTICS")
            stats[device] = {str(k): int(v) for k, v in dict(raw).items()}
        except Exception as exc:  # recorded, never raised
            stats[device] = {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}
    return {
        "stage": stage,
        "t_unix": time.time(),
        "system": _mem(),
        "gpu_memory_statistics": stats,
        "gpu_process_counters": read_gpu_counters(os.getpid()),
    }


# CC cells (Task BL): cores of the load, for the memory records and the 10 Hz trace.
_CC_CORES: dict[str, Any] = {}
_LAST_TRACE: dict[str, Any] | None = None
_LAST_TRACE_RAW: dict[str, Any] | None = None
DEVICE_MEM_PROPS = ("GPU_DEVICE_MAX_ALLOC_MEM_SIZE", "GPU_DEVICE_TOTAL_MEM_SIZE")


def device_mem_props(core: Any, device: str) -> dict[str, Any]:
    """CL max single allocation and total device memory as the plugin reports them."""
    out: dict[str, Any] = {}
    for name in DEVICE_MEM_PROPS:
        try:
            out[name] = int(core.get_property(device, name))
        except Exception as exc:  # recorded, never raised
            out[name] = f"error: {type(exc).__name__}: {str(exc)[:200]}"
    return out


def _gpu_stat_types(cores: dict[str, Any]) -> dict[str, int] | None:
    """Task BR (--trial-telemetry): GPU_MEMORY_STATISTICS per allocation type, summed over
    the loaded devices; None when no device answered."""
    out: dict[str, int] = {}
    seen = False
    for device, core in cores.items():
        try:
            raw = dict(core.get_property(device, "GPU_MEMORY_STATISTICS"))
        except Exception:
            continue
        for k, v in raw.items():
            out[str(k)] = out.get(str(k), 0) + int(v)
        seen = True
    return out if seen else None


def _gpu_stat_total(cores: dict[str, Any]) -> int | None:
    total = 0
    seen = False
    for device, core in cores.items():
        try:
            raw = dict(core.get_property(device, "GPU_MEMORY_STATISTICS"))
        except Exception:
            continue
        total += sum(int(v) for v in raw.values())
        seen = True
    return total if seen else None


class MemTrace:
    """CC cells (spec mem_trace_hz): sample system available memory and the summed
    GPU_MEMORY_STATISTICS at about hz while a generate runs (background thread).

    Thread safety of the plugin property read during inference is UNVERIFIED; the
    rehearsal cell exercises it. Read errors are counted, never raised.
    """

    MAX_SAMPLES = 20000

    def __init__(
        self,
        hz: float,
        cores: dict[str, Any],
        read_gpu: bool = True,
        dxgi: bool = False,
        types: bool = False,
    ) -> None:
        import threading

        self.period = 1.0 / float(hz)
        self.hz = float(hz)
        self.cores = cores
        self.read_gpu = read_gpu
        self.samples: list[tuple[float, float, int | None]] = []
        # Task BR (--trial-telemetry): per-type GPU bytes per sample, and DXGI usage per sample.
        self.types = bool(types)
        self.type_samples: list[tuple[float, dict[str, int] | None]] = []
        self.dxgi_samples: list[tuple[float, dict[str, Any]]] = []
        self.errors = 0
        # Task BM A19: this process's DXGI budget / usage and budget-change events.
        self.watch: Any = None
        self.dxgi_peak: dict[str, int] = {}
        self.dxgi_first: dict[str, Any] = {}
        self.dxgi_last: dict[str, Any] = {}
        if dxgi:
            from seam.dxgi_budget import BudgetWatch

            self.watch = BudgetWatch()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                avail = psutil.virtual_memory().available / MB
                now = time.time()
                if self.types and self.read_gpu:
                    per = _gpu_stat_types(self.cores)
                    gpu = sum(per.values()) if per is not None else None
                    if len(self.type_samples) < self.MAX_SAMPLES:
                        self.type_samples.append((now, per))
                else:
                    gpu = _gpu_stat_total(self.cores) if self.read_gpu else None
                if len(self.samples) < self.MAX_SAMPLES:
                    self.samples.append((now, round(avail, 1), gpu))
                if self.watch is not None and not self.watch.error:
                    self.watch.poll()
                    q = self.watch.query()
                    if not self.dxgi_first:
                        self.dxgi_first = dict(q)
                    self.dxgi_last = dict(q)
                    if self.types and len(self.dxgi_samples) < self.MAX_SAMPLES:
                        self.dxgi_samples.append((now, dict(q)))
                    for seg, val in q.items():
                        if isinstance(val, tuple):
                            self.dxgi_peak[seg] = max(self.dxgi_peak.get(seg, 0), int(val[1]))
            except Exception:
                self.errors += 1
            self._stop.wait(self.period)

    def __enter__(self) -> MemTrace:
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self._stop.set()
        self._thread.join(timeout=5.0)
        if self.watch is not None:
            self.watch.close()

    def result(self) -> dict[str, Any]:
        gpus = [g for _, _, g in self.samples if g is not None]
        avails = [a for _, a, _ in self.samples]
        return {
            "hz": self.hz,
            "n": len(self.samples),
            "errors": self.errors,
            "available_min_mb": min(avails) if avails else None,
            "gpu_stat_total_peak_bytes": max(gpus) if gpus else None,
            "gpu_stat_total_first_bytes": gpus[0] if gpus else None,
            "gpu_stat_total_last_bytes": gpus[-1] if gpus else None,
            "trace": self.samples,
            **(
                {"type_trace": self.type_samples, "dxgi_trace": self.dxgi_samples}
                if self.types
                else {}
            ),
            "dxgi": None
            if self.watch is None
            else {
                "error": self.watch.error,
                "budget_change_events": self.watch.count,
                "first_budget_usage": self.dxgi_first,
                "last_budget_usage": self.dxgi_last,
                "peak_current_usage": self.dxgi_peak,
            },
        }


def _traced(spec: dict[str, Any], fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Run one generate, under a MemTrace when the spec asks for one."""
    global _LAST_TRACE, _LAST_TRACE_RAW
    hz = spec.get("mem_trace_hz")
    if not hz:
        return fn()
    telemetry = bool(spec.get("trial_telemetry"))
    tr = MemTrace(
        float(hz),
        _CC_CORES,
        read_gpu=bool(spec.get("gpu_mem_stats")),
        dxgi=bool(spec.get("dxgi_trace")),
        types=telemetry,
    )
    t0 = time.time()
    try:
        with tr:
            rec = fn()
    except BaseException:
        # Task BM A32: keep the trace (peak usage at failure) for _fail_turn.
        _LAST_TRACE = tr.result()
        if telemetry:
            # Task BR: time-to-fail and the raw samples through the failure.
            _LAST_TRACE["elapsed_to_exception_s"] = time.time() - t0
            _LAST_TRACE_RAW = {k: _LAST_TRACE.get(k) for k in ("trace", "type_trace", "dxgi_trace")}
        raise
    rec["mem_trace"] = tr.result()
    return rec


def compiled_kv_mismatch(
    spec: dict[str, Any], requested: str | None, compiled: dict[str, Any] | None
) -> str | None:
    """Task BM A31: with spec reject_kv_mismatch, a reason string when the compiled KV type
    (GenAI load log) is unknown or differs from the request; None when it matches or the
    check is off or nothing was requested."""
    if not spec.get("reject_kv_mismatch") or requested is None:
        return None
    from seam.genai_runtime import normalize_kv

    want = normalize_kv(str(requested))
    got = (compiled or {}).get("kv_cache_precision")
    if got is None:
        return f"compiled KV type not read back (requested {want}); A31 rejects unknown"
    if normalize_kv(str(got)) != want:
        return f"compiled KV {got} != requested {want}"
    return None


def result_replace_policy() -> tuple[int, float]:
    """How many times to retry a result-file replace after WinError 5.

    e4a22dac n30000 and d4f66bbc gpu-n6000-r2 died in Path.replace while the
    parent was polling the same file. The attempts and the wait live in
    configs/delta_n.yaml.
    """
    global _REPLACE_POLICY
    if _REPLACE_POLICY is None:
        import yaml

        path = Path(__file__).resolve().parents[2] / "configs" / "delta_n.yaml"
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        generation = loaded["generation"]
        _REPLACE_POLICY = (
            int(generation["result_replace_attempts"]),
            float(generation["result_replace_wait_s"]),
        )
    return _REPLACE_POLICY


def replace_result_file(
    tmp: Path,
    dest: Path,
    *,
    attempts: int,
    wait_s: float,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Replace dest with tmp. Retry PermissionError, then raise the last one."""
    last: PermissionError | None = None
    for _ in range(int(attempts)):
        try:
            tmp.replace(dest)
        except PermissionError as exc:
            last = exc
            sleep(float(wait_s))
        else:
            return
    if last is not None:
        raise last
    raise RuntimeError("result replace made no attempt")


def _mem() -> dict[str, float]:
    virtual = psutil.virtual_memory()
    return {
        "rss_mb": psutil.Process().memory_info().rss / MB,
        "available_mb": virtual.available / MB,
        "used_mb": virtual.used / MB,
        "percent": virtual.percent,
    }


class _Writer:
    """Rewrite the result file after every phase so a killed child still reports progress."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self.state: dict[str, Any] = {
            "phase": "start",
            "completed": False,
            "failure_mode": None,
            "exception": None,
        }

    def update(self, **fields: Any) -> None:
        self.state.update(fields)
        self.flush()

    def flush(self) -> None:
        tmp = self._path.with_suffix(".partial")
        tmp.write_text(json.dumps(self.state, indent=2, sort_keys=True), encoding="utf-8")
        attempts, wait_s = result_replace_policy()
        replace_result_file(tmp, self._path, attempts=attempts, wait_s=wait_s)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    writer = _Writer(args.out)

    # Baseline is taken before any OpenVINO import so the reservation attributed to a backend
    # includes the runtime it drags in, which is part of what enabling that backend costs.
    writer.update(phase="baseline", memory_baseline=_mem(), spec=spec)

    try:
        return _run(spec, writer)
    except BaseException as exc:
        writer.update(
            phase="failed",
            completed=False,
            failure_mode=f"exception:{type(exc).__name__}",
            exception={
                "type": type(exc).__name__,
                "message": str(exc)[:4000],
                "traceback": traceback.format_exc()[:8000],
            },
            memory_at_failure=_mem(),
        )
        return 1


def _run(spec: dict[str, Any], writer: _Writer) -> int:
    from seam.tools._winpower import assert_system_required

    # Hold PowerRequestSystemRequired for the life of this measurement child so Modern
    # Standby cannot suspend the repeat. Cleared on every exit path, including exceptions.
    power_req = assert_system_required(
        reason="SEAM measurement child; PowerRequestSystemRequired for generate window",
        role="measurement_child",
    )
    writer.update(phase="power_request", power_request=dict(power_req.record))

    try:
        return _run_with_power(spec, writer)
    finally:
        power_req.release()
        writer.update(power_request=dict(power_req.record))


def _run_with_power(spec: dict[str, Any], writer: _Writer) -> int:
    from seam.telemetry.rss import RssSampler
    from seam.tools._winmem import lock_working_set, read_working_set_limits

    affinity = spec.get("affinity_cpus")
    if affinity:
        psutil.Process().cpu_affinity([int(cpu) for cpu in affinity])
    writer.update(affinity_readback=[int(c) for c in psutil.Process().cpu_affinity()])

    # Requested before the model is compiled: a hard minimum granted after the weights are
    # already resident does not protect them from having been trimmed on the way in.
    wslock = dict(spec.get("wslock") or {})
    if str(wslock.get("mode")) == "request":
        lock_record = lock_working_set(
            minimum_bytes=int(wslock["minimum_bytes"]),
            maximum_bytes=int(wslock["maximum_bytes"]),
        )
    else:
        lock_record = {
            "requested": False,
            "granted": False,
            "mode": str(wslock.get("mode", "off")),
            "before": read_working_set_limits(),
        }
    writer.update(phase="wslock", working_set_lock=lock_record)

    import openvino as ov
    import openvino_genai as ov_genai

    from seam.ov_kv_precision import (
        enforce_kv_cache_precision,
        materialize_pipeline_properties,
        requested_kv_cache_precision,
    )

    writer.update(phase="imported", memory_after_import=_mem())

    model_dir = str(spec["model_dir"])
    # DEMO-2 pilots (Task AS): an explicit SchedulerConfig from the spec; it replaces
    # GenAI's latency defaults. Absent = plain LLMPipeline, unchanged.
    sched_spec = spec.get("scheduler_config")
    if sched_spec is not None and len(spec["load_sequence"]) != 1:
        raise SystemExit("REFUSED -- scheduler_config needs a single-device load_sequence")
    loads: list[dict[str, Any]] = []
    pipes: dict[str, Any] = {}
    kv_precision_records: list[dict[str, Any]] = []
    cores: dict[str, Any] = {}

    # Load order matters and is declared by the parent: the standing accelerator is compiled
    # first, because "enabled" means resident before the measured work begins.
    # One Core per device load so set_property + LLMPipeline + get_property share sticky state.
    for entry in spec["load_sequence"]:
        device = str(entry["device"])
        properties_raw = dict(entry.get("properties") or {})
        properties = materialize_pipeline_properties(properties_raw)
        requested_kv = requested_kv_cache_precision(properties_raw)
        before = _mem()
        t0 = time.perf_counter()
        core = ov.Core()
        if requested_kv is not None:
            core.set_property(device, {"KV_CACHE_PRECISION": properties["KV_CACHE_PRECISION"]})
        cores[device] = core
        _CC_CORES[device] = core
        capture: contextlib.AbstractContextManager[dict[str, Any]] = contextlib.nullcontext(
            {"text": None}
        )
        if spec.get("compiled_readback"):
            from seam.genai_runtime import capture_native_output

            capture = capture_native_output()
        with capture as captured:
            if sched_spec is not None:
                from seam.genai_runtime import build_scheduler_config

                sched = {"scheduler_config": build_scheduler_config(ov_genai, dict(sched_spec))}
                pipes[device] = ov_genai.LLMPipeline(model_dir, device, sched, **properties)
            else:
                pipes[device] = ov_genai.LLMPipeline(model_dir, device, **properties)
        compile_s = time.perf_counter() - t0
        after = _mem()
        kv_check = enforce_kv_cache_precision(device=device, requested=requested_kv, core=core)
        kv_precision_records.append(kv_check)
        load_rec: dict[str, Any] = {
            "device": device,
            "properties": {
                k: (str(v) if hasattr(v, "to_string") else v) for k, v in properties.items()
            },
            "properties_requested": properties_raw,
            "compile_s": compile_s,
            "memory_before": before,
            "memory_after": after,
            "rss_delta_mb": after["rss_mb"] - before["rss_mb"],
            "available_delta_mb": before["available_mb"] - after["available_mb"],
            "kv_cache_precision": kv_check,
        }
        if sched_spec is not None:
            load_rec["scheduler_config"] = dict(sched_spec)
        if spec.get("compiled_readback"):
            from seam.genai_runtime import parse_genai_load_log

            load_rec["compiled"] = parse_genai_load_log(str(captured.get("text") or ""))
            load_rec["versions"] = {
                "openvino": str(ov.get_version()),
                "openvino_genai": str(getattr(ov_genai, "__version__", "unknown")),
            }
        if spec.get("gpu_mem_stats"):
            load_rec["device_mem_props"] = device_mem_props(core, device)
        loads.append(load_rec)
        writer.update(
            phase=f"loaded:{device}",
            loads=list(loads),
            kv_cache_precision_readback=list(kv_precision_records),
        )
        if not kv_check["match"]:
            writer.update(
                phase="failed",
                completed=False,
                failure_mode=kv_check["failure_mode"],
                exception={
                    "type": "KvCachePrecisionMismatch",
                    "message": str(kv_check["failure_mode"]),
                    "traceback": "",
                },
                memory_at_failure=_mem(),
            )
            return 1
        reason = compiled_kv_mismatch(spec, requested_kv, load_rec.get("compiled"))
        if reason:
            # Task BM A31: the applied (compiled) KV type must equal the request.
            writer.update(
                phase="failed",
                completed=False,
                failure_mode="kv_compiled_mismatch",
                exception={"type": "KvCompiledMismatch", "message": reason, "traceback": ""},
                memory_at_failure=_mem(),
            )
            return 1

    # The standing reservation: everything resident after all backends are enabled and before a
    # single token of the measured prompt has been processed.
    baseline = writer.state["memory_baseline"]
    resident = _mem()
    writer.update(
        phase="resident",
        memory_resident_before_inference=resident,
        standing_reservation={
            "rss_delta_mb": resident["rss_mb"] - baseline["rss_mb"],
            "available_delta_mb": baseline["available_mb"] - resident["available_mb"],
            "basis": (
                "delta from process baseline (pre-import) to all backends compiled and resident, "
                "before any measured generation; rss and system-available disagree when weights "
                "are file-backed or shared, and both are reported without attribution"
            ),
        },
    )

    generate_device = str(spec["generate_device"])
    pipe = pipes[generate_device]

    if spec.get("cc_grow"):
        return _cc_grow(spec, writer, pipe, ov_genai)
    if spec.get("cc_conc"):
        return _cc_conc(spec, writer, pipe, ov_genai)

    if spec.get("resident_two_turn"):
        mem_probe = None
        if spec.get("gpu_mem_stats"):
            cc_mem: list[dict[str, Any]] = [cc_mem_snapshot("loaded", cores)]
            writer.update(cc_mem=list(cc_mem))

            def mem_probe(stage: str) -> None:
                cc_mem.append(cc_mem_snapshot(stage, cores))
                writer.update(cc_mem=list(cc_mem))

        return _resident_two_turn(spec, writer, pipe, ov_genai, mem_probe=mem_probe)

    if spec.get("build_exact_n") is not None:
        from seam.tools.boot4_text import rendered_exact_prompt

        prompt = rendered_exact_prompt(
            pipe.get_tokenizer(),
            int(spec["build_exact_n"]),
            unit=str(spec["filler_unit"]),
            salt=str(spec.get("prompt_salt") or "p"),
        )
    else:
        prompt = Path(spec["prompt_path"]).read_text(encoding="utf-8")

    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = int(spec["max_new_tokens"])
    if spec.get("min_new_tokens") is not None:
        cfg.min_new_tokens = int(spec["min_new_tokens"])
    cfg.do_sample = False
    cfg.ignore_eos = True
    # The prompt arrives fully rendered so that every arm sees byte-identical input; letting the
    # pipeline re-template it would make prompt length a function of the backend.
    cfg.apply_chat_template = False

    # Same dual-source TTFT instrument the rest of the project uses; the prefill/decode split
    # is not reimplemented here.
    from seam.backends.local_openvino import _make_ttft_streamer, resolve_ttft_ns

    sampler = RssSampler(interval_s=float(spec.get("rss_interval_s", 0.05)))
    writer.update(phase="generating", memory_before_generate=_mem())

    streamer = _make_ttft_streamer(ov_genai)
    sampler.start()
    t0 = time.perf_counter()
    streamer.t0_ns = time.perf_counter_ns()
    try:
        result = pipe.generate([prompt], cfg, streamer)
    finally:
        wall_s = time.perf_counter() - t0
        window = sampler.stop()

    texts = getattr(result, "texts", None)
    text = str(texts[0]) if texts else str(result)
    metrics = getattr(result, "perf_metrics", None)
    prompt_tokens = None
    completion_tokens = None
    metrics_ttft_ns = None
    if metrics is not None:
        try:
            prompt_tokens = int(metrics.get_num_input_tokens())
            completion_tokens = int(metrics.get_num_generated_tokens())
        except Exception:  # optional metric; absence is recorded, never invented
            prompt_tokens = None
            completion_tokens = None
        try:
            ttft_ms = float(metrics.get_ttft().mean)
            metrics_ttft_ns = int(ttft_ms * 1_000_000) if ttft_ms > 0.0 else None
        except Exception:
            metrics_ttft_ns = None

    ttft_ns, ttft_source = resolve_ttft_ns(metrics_ttft_ns, streamer.ttft_ns)
    prefill_s = (ttft_ns / 1e9) if ttft_ns else None
    r_prefill = None
    r_decode = None
    decode_s = None
    if ttft_ns and prompt_tokens:
        r_prefill = prompt_tokens / (ttft_ns / 1e9)
    if ttft_ns and completion_tokens and completion_tokens > 1:
        decode_s = wall_s - (ttft_ns / 1e9)
        if decode_s > 0:
            r_decode = (completion_tokens - 1) / decode_s
        else:
            decode_s = None

    decode_span = None
    if spec.get("decode_span_rate"):
        from seam.tools.boot4_text import decode_span_tok_s

        first_ns = getattr(streamer, "first_token_ns", None)
        last_ns = getattr(streamer, "last_token_ns", None)
        if first_ns is None or last_ns is None:
            raise RuntimeError("decode span requires a first and a last token timestamp")
        r_decode = decode_span_tok_s(t_first_ns=int(first_ns), t_last_ns=int(last_ns))
        decode_s = (int(last_ns) - int(first_ns)) / 1e9
        decode_span = {
            "t_first_ns": int(first_ns),
            "t_last_ns": int(last_ns),
            "numerator": 63,
            "span_s": decode_s,
        }

    writer.update(
        phase="done",
        completed=True,
        failure_mode=None,
        generation={
            "wall_s": wall_s,
            "ttft_ns": ttft_ns,
            "ttft_source": ttft_source,
            "prefill_s": prefill_s,
            "decode_s": decode_s,
            "decode_tok_s": r_decode,
            "decode_span": decode_span,
            "r_prefill_tok_s": r_prefill,
            "r_decode_tok_s": r_decode,
            "prompt_tokens_reported": prompt_tokens,
            "completion_tokens_reported": completion_tokens,
            "completion_chars": len(text),
            "text_head": text[:200],
            **window.to_record(),
        },
        memory_after_generate=_mem(),
        working_set_limits_after=read_working_set_limits(),
    )
    return 0


def _chat_once(
    pipe: Any,
    history: Any,
    cfg: Any,
    ov_genai: Any,
) -> dict[str, Any]:
    """One ChatHistory generate. TTFT is the turn's prefill."""
    from seam.backends.local_openvino import _make_ttft_streamer, resolve_ttft_ns

    streamer = _make_ttft_streamer(ov_genai)
    t0 = time.perf_counter()
    streamer.t0_ns = time.perf_counter_ns()
    result = pipe.generate(history, cfg, streamer)
    wall_s = time.perf_counter() - t0
    texts = getattr(result, "texts", None)
    text = str(texts[0]) if texts else str(result)
    metrics = getattr(result, "perf_metrics", None)
    prompt_tokens = None
    completion_tokens = None
    metrics_ttft_ns = None
    if metrics is not None:
        try:
            prompt_tokens = int(metrics.get_num_input_tokens())
            completion_tokens = int(metrics.get_num_generated_tokens())
        except Exception:
            prompt_tokens = None
            completion_tokens = None
        try:
            ttft_ms = float(metrics.get_ttft().mean)
            metrics_ttft_ns = int(ttft_ms * 1_000_000) if ttft_ms > 0.0 else None
        except Exception:
            metrics_ttft_ns = None
    ttft_ns, ttft_source = resolve_ttft_ns(metrics_ttft_ns, streamer.ttft_ns)
    prefill_s = (ttft_ns / 1e9) if ttft_ns else None
    return {
        "wall_s": wall_s,
        "ttft_ns": ttft_ns,
        "ttft_source": ttft_source,
        "prefill_s": prefill_s,
        "prompt_tokens_reported": prompt_tokens,
        "completion_tokens_reported": completion_tokens,
        "completion_chars": len(text),
        "text_head": text[:200],
    }


def _fail_turn(writer: _Writer, turn: str, exc: BaseException) -> int:
    writer.update(
        phase="failed",
        completed=False,
        failure_mode=f"{turn}:{type(exc).__name__}",
        exception={
            "type": type(exc).__name__,
            "message": str(exc)[:4000],
            "traceback": traceback.format_exc()[:8000],
        },
        memory_at_failure=_mem(),
    )
    if _LAST_TRACE is not None:
        trace = {
            k: v for k, v in _LAST_TRACE.items() if k not in ("trace", "type_trace", "dxgi_trace")
        }
        writer.update(memory_trace_at_failure=trace)
    if _LAST_TRACE_RAW is not None:
        writer.update(memory_trace_raw_at_failure=_LAST_TRACE_RAW)
    return 1


TURN2_PATHS = ("user_followup", "assistant_then_user")


def common_prefix_len(a: list[int], b: list[int]) -> int:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n


def _rendered_ids(tokenizer: Any, history: Any) -> list[int] | None:
    """Token ids of the rendered history (generation prompt on); None if unavailable."""
    try:
        text = str(tokenizer.apply_chat_template(history, True))
        ids = tokenizer.encode(text).input_ids.data
        return [int(x) for x in ids.flatten().tolist()]
    except Exception:
        return None


def _resident_two_turn(
    spec: dict[str, Any],
    writer: _Writer,
    pipe: Any,
    ov_genai: Any,
    mem_probe: Callable[[str], None] | None = None,
) -> int:
    """One turn-1 fill, then turn-2 repeats on histories that share only that prefix.

    turn2_path "user_followup" (default, sealed WARM-KV): turn 2 = turn-1 user
    message + a new user message. "assistant_then_user" (DEMO-1 V5-CAL): turn 2
    = turn-1 user message + the turn-1 reply as an assistant message + a new
    user message, the H1 agent's shape. With record_prefix, each repeat records
    the rendered token prefix it shares with turn 1 and the tokens after it.
    """
    from seam.tools.boot4_text import raw_exact_text, user_content_for_rendered_tokens

    tokenizer = pipe.get_tokenizer()
    unit = str(spec["filler_unit"])
    n_cached = int(spec["n_cached"])
    delta_tokens = int(spec["delta_tokens"])
    repeats = int(spec["turn2_repeats"])
    turn2_path = str(spec.get("turn2_path") or "user_followup")
    if turn2_path not in TURN2_PATHS:
        raise RuntimeError(f"unknown turn2_path {turn2_path!r}")
    record_prefix = bool(spec.get("record_prefix"))
    turn1_content = user_content_for_rendered_tokens(tokenizer, n_cached, unit=unit, salt="f")
    deltas = [
        raw_exact_text(tokenizer, delta_tokens, unit=unit, salt=f"d{i}") for i in range(repeats)
    ]
    if len(set(deltas)) != repeats:
        raise RuntimeError("turn-2 delta texts are not distinct")

    cfg1 = ov_genai.GenerationConfig()
    cfg1.max_new_tokens = int(spec.get("turn1_max_new_tokens", 1))
    cfg1.do_sample = False
    cfg1.ignore_eos = True
    cfg2 = ov_genai.GenerationConfig()
    cfg2.max_new_tokens = int(spec.get("turn2_max_new_tokens", 1))
    cfg2.do_sample = False
    cfg2.ignore_eos = True

    history = ov_genai.ChatHistory()
    history.set_extra_context({"enable_thinking": False})
    history.append({"role": "user", "content": turn1_content})
    writer.update(phase="generating", memory_before_generate=_mem())
    try:
        turn1 = _traced(spec, lambda: _chat_once(pipe, history, cfg1, ov_genai))
    except Exception as exc:
        return _fail_turn(writer, "turn1", exc)
    if mem_probe is not None:
        mem_probe("after_turn1")
    reported = turn1.get("prompt_tokens_reported")
    if reported is not None and int(reported) != n_cached:
        return _fail_turn(
            writer,
            "turn1",
            RuntimeError(f"turn-1 prompt tokens {reported} do not equal n_cached {n_cached}"),
        )
    base = json.loads(json.dumps(history.get_messages()))
    if turn2_path == "assistant_then_user":
        base = [*base, {"role": "assistant", "content": str(turn1.get("text_head") or "")}]
    turn1_ids = _rendered_ids(tokenizer, history) if record_prefix else None
    turn2s: list[dict[str, Any]] = []
    for i, delta in enumerate(deltas):
        branch = ov_genai.ChatHistory()
        branch.set_extra_context({"enable_thinking": False})
        branch.set_messages(base)
        branch.append({"role": "user", "content": delta})
        prefix_rec: dict[str, Any] = {}
        if record_prefix:
            ids2 = _rendered_ids(tokenizer, branch)
            if turn1_ids is not None and ids2 is not None:
                common = common_prefix_len(turn1_ids, ids2)
                prefix_rec = {
                    "turn1_rendered_tokens": len(turn1_ids),
                    "turn2_rendered_tokens": len(ids2),
                    "common_prefix_tokens": common,
                    "measured_delta_tokens": len(ids2) - common,
                }
            else:
                prefix_rec = {"prefix_record_error": "rendered ids unavailable"}
        try:
            rec = _chat_once(pipe, branch, cfg2, ov_genai)
        except Exception as exc:
            return _fail_turn(writer, "turn2", exc)
        if mem_probe is not None:
            mem_probe(f"after_turn2_{i}")
        rec["repeat"] = i
        rec["delta_tokens"] = delta_tokens
        rec.update(prefix_rec)
        turn2s.append(rec)
    writer.update(
        phase="done",
        completed=True,
        failure_mode=None,
        generation={
            "resident_two_turn": True,
            "n_cached": n_cached,
            "delta_tokens": delta_tokens,
            "turn2_path": turn2_path,
            "turn1": turn1,
            "turn2": turn2s,
        },
        memory_after_generate=_mem(),
    )
    return 0


def _cc_grow(spec: dict[str, Any], writer: _Writer, pipe: Any, ov_genai: Any) -> int:
    """CC-GROW (Task BL): grow one ChatHistory session by step-token user turns until an
    error or max_tokens. Each turn generates new_tokens; prefix reuse follows the
    pipeline's scheduler (prefix caching as configured). Records every turn.
    """
    from seam.tools.boot4_text import raw_exact_text

    tokenizer = pipe.get_tokenizer()
    unit = str(spec["filler_unit"])
    g = dict(spec["cc_grow"])
    step = int(g["step_tokens"])
    max_tokens = int(g["max_tokens"])
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = int(g.get("new_tokens", 1))
    cfg.do_sample = False
    cfg.ignore_eos = True
    history = ov_genai.ChatHistory()
    history.set_extra_context({"enable_thinking": False})
    turns: list[dict[str, Any]] = []
    writer.update(phase="generating", memory_before_generate=_mem())
    k = 0
    while True:
        history.append(
            {"role": "user", "content": raw_exact_text(tokenizer, step, unit=unit, salt=f"g{k}")}
        )
        try:
            rec = _traced(spec, lambda: _chat_once(pipe, history, cfg, ov_genai))
        except Exception as exc:
            writer.update(generation={"cc_grow": True, "turns": turns})
            return _fail_turn(writer, f"grow_turn{k}", exc)
        rec["turn"] = k
        rec["system_after"] = _mem()
        if spec.get("trial_telemetry"):
            rec["gpu_stats_end"] = _gpu_stat_types(_CC_CORES)
        rec.pop("text_head", None)
        turns.append(rec)
        history.append({"role": "assistant", "content": "ok"})
        writer.update(generation={"cc_grow": True, "turns": turns})
        reported = rec.get("prompt_tokens_reported")
        if reported is not None and int(reported) >= max_tokens:
            break
        if reported is None and (k + 1) * step >= max_tokens:
            break
        k += 1
    final = g.get("final_tokens")
    if final:
        # Task BR SESS-1 sub-turn bisection: one final turn of `final` tokens on the history
        # the series reached (the same deterministic turns as the uninterrupted series).
        history.append(
            {
                "role": "user",
                "content": raw_exact_text(tokenizer, int(final), unit=unit, salt=f"g{k + 1}"),
            }
        )
        try:
            rec = _traced(spec, lambda: _chat_once(pipe, history, cfg, ov_genai))
        except Exception as exc:
            writer.update(generation={"cc_grow": True, "turns": turns, "reached_max": True})
            return _fail_turn(writer, f"grow_final{int(final)}", exc)
        rec.update({"turn": k + 1, "final": True, "final_tokens": int(final)})
        rec["system_after"] = _mem()
        if spec.get("trial_telemetry"):
            rec["gpu_stats_end"] = _gpu_stat_types(_CC_CORES)
        rec.pop("text_head", None)
        turns.append(rec)
    writer.update(
        phase="done",
        completed=True,
        failure_mode=None,
        generation={"cc_grow": True, "turns": turns, "reached_max": True},
        memory_after_generate=_mem(),
    )
    return 0


def _cc_conc(spec: dict[str, Any], writer: _Writer, pipe: Any, ov_genai: Any) -> int:
    """CC-CONC (Task BL): one generate over N unique prompts of tokens each (a batch the
    continuous-batching scheduler admits per its config). Records wall time and memory.
    """
    from seam.tools.boot4_text import raw_exact_text

    tokenizer = pipe.get_tokenizer()
    unit = str(spec["filler_unit"])
    c = dict(spec["cc_conc"])
    n = int(c["sessions"])
    tokens = int(c["tokens"])
    prompts = [raw_exact_text(tokenizer, tokens, unit=unit, salt=f"c{i}") for i in range(n)]
    if len(set(prompts)) != n:
        raise RuntimeError("concurrent prompts are not unique")
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = int(c.get("new_tokens", 16))
    cfg.do_sample = False
    cfg.ignore_eos = True
    if hasattr(cfg, "apply_chat_template"):
        cfg.apply_chat_template = False
    writer.update(phase="generating", memory_before_generate=_mem())

    def run() -> dict[str, Any]:
        t0 = time.perf_counter()
        result = pipe.generate(prompts, cfg)
        wall = time.perf_counter() - t0
        texts = getattr(result, "texts", None)
        return {"wall_s": wall, "n_texts": len(texts) if texts is not None else None}

    try:
        rec = _traced(spec, run)
    except Exception as exc:
        return _fail_turn(writer, f"conc_n{n}", exc)
    rec.update({"sessions": n, "tokens_per_session": tokens, "system_after": _mem()})
    writer.update(
        phase="done",
        completed=True,
        failure_mode=None,
        generation={"cc_conc": True, **rec},
        memory_after_generate=_mem(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
