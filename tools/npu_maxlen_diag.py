"""NPU-MAXLEN-DIAG. Diagnostic, not a measurement. Nothing here is cited.

Asks why 28cf811d (request 2048) read back 1024. Two arms, each in its own
child process, run one after the other, so two pipelines are never loaded
at once:

  doc   LLMPipeline config MAX_PROMPT_LEN + MIN_RESPONSE_LEN
  npuw  NPUW_LLM_MAX_PROMPT_LEN, as tools/run_npu_profile.py passes it

Each arm records load time, every readback source, then generates one prompt
per band directly, with no length check of ours in front of generate. This
script does not open a preregistration, amendment, prediction or rule file.

Rule v2 by default (--rule-version 1 reproduces run 1; --classify re-reads output).
Final stdout line: DIAG_VERDICT <D1|D2|D3|D4> <subcase> <out_dir>
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.backends.local_openvino import (  # noqa: E402
    _make_ttft_streamer,
    _text_from_generate_result,
    resolve_ttft_ns,
)
from seam.npu_validity import (  # noqa: E402
    REPEAT_FRACTION_MAX,
    fourgram_repeat_fraction,
    output_parses,
    whitespace_tokens,
)
from seam.tools.boot4_text import id_count, rendered_exact_prompt  # noqa: E402
from tools.run_npu_profile import MAX_NEW_TOKENS, _filler, _metrics  # noqa: E402
from tools.t2s_queue_watchdog import is_idle, is_neutral, parse_log_line  # noqa: E402

ARMS = ("doc", "npuw")
ARM_LABEL = {"doc": "K-DOC", "npuw": "K-NPUW"}
CHILD_TIMEOUT_S = 600
PREFILL_CHUNK_SIZE = 1024
DEFAULT_MODEL_SPEC = ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml"
DEFAULT_WATCHDOG_LOG = r"C:\apu\ovn\watchdog.log"
READBACK_TOKENS = ("PROMPT", "RESPONSE", "NPUW_LLM")
SALT = "npu"
RULE_VERSION = 2
BANDS_BY_VERSION = {
    1: "850-950,1450-1550",
    2: "850-950,1450-1550,2100-2150",
}
LENGTH_CHECK_TEXT = "m_max_prompt_len"
# v2: the runner leaves apply_chat_template at its default (True). Kept, and set
# explicitly, so the pipeline sees the prompt as the runner sends it.
APPLY_CHAT_TEMPLATE = True


# ---------------------------------------------------------------- decision


def arm_props(arm: str, request: int) -> dict[str, Any]:
    """Load config per arm. Both pass the runner's prefill chunk size."""
    props: dict[str, Any] = {"NPUW_LLM_PREFILL_CHUNK_SIZE": PREFILL_CHUNK_SIZE}
    if arm == "doc":
        props["MAX_PROMPT_LEN"] = int(request)
        props["MIN_RESPONSE_LEN"] = int(MAX_NEW_TOKENS)
    elif arm == "npuw":
        props["NPUW_LLM_MAX_PROMPT_LEN"] = int(request)
    else:
        raise SystemExit(f"REFUSED -- unknown arm {arm!r}")
    return props


def prompt_status(row: dict[str, Any]) -> str:
    """refused, truncated, truncation_unknown, or accepted."""
    if row.get("exception") is not None or not row.get("generate_returned"):
        return "refused"
    reported = row.get("pipeline_input_tokens")
    realized = row.get("realized_tokens")
    if not isinstance(reported, int) or not isinstance(realized, int):
        return "truncation_unknown"
    if reported < realized:
        return "truncated"
    return "accepted"


def _band_row(arm: dict[str, Any], index: int) -> dict[str, Any] | None:
    prompts = arm.get("prompts")
    if not isinstance(prompts, list) or len(prompts) <= index:
        return None
    row = prompts[index]
    return row if isinstance(row, dict) else None


def _in_band(row: dict[str, Any]) -> bool:
    realized = row.get("realized_tokens")
    band = row.get("band")
    if not isinstance(realized, int) or not isinstance(band, list) or len(band) != 2:
        return False
    return int(band[0]) <= realized <= int(band[1])


def _ok(row: dict[str, Any] | None) -> bool:
    return row is not None and prompt_status(row) == "accepted" and row.get("valid") is True


def _arm_broken(arm: dict[str, Any] | None) -> bool:
    if not isinstance(arm, dict):
        return True
    if not arm.get("result_present") or arm.get("timed_out"):
        return True
    if arm.get("child_exit_code") != 0:
        return True
    return arm.get("load_error") is not None


def length_check_refusal(row: dict[str, Any] | None) -> bool:
    """v2: generate raised and the message names the runtime length check."""
    if row is None or row.get("generate_returned"):
        return False
    exc = row.get("exception")
    if not isinstance(exc, dict):
        return False
    return LENGTH_CHECK_TEXT in str(exc.get("message") or "")


def stated_cap(message: str | None) -> int | None:
    """The cap the runtime states ("up to N tokens"). Recorded, outside the rule."""
    match = re.search(r"up to (\d+) tokens", message or "")
    return None if match is None else int(match.group(1))


def classify(results: dict[str, Any]) -> tuple[str, str]:
    """The rule in derived/npu/diag, by code. Returns (verdict, subcase).

    ``rule_version`` absent means 1 (run 1 output predates the field).
    """
    version = int(results.get("rule_version") or 1)
    if version not in BANDS_BY_VERSION:
        raise SystemExit(f"REFUSED -- unknown rule version {version}")
    n_bands = len(parse_bands(BANDS_BY_VERSION[version], version))
    request = int(results["request"])
    arms = results.get("arms") or {}
    for name in ARMS:
        arm = arms.get(name)
        if _arm_broken(arm):
            return "D4", "-"
        for index in range(n_bands):
            row = _band_row(arm, index)
            if row is None or not _in_band(row):
                return "D4", "-"
        if not _ok(_band_row(arm, 0)):
            return "D4", "-"
    b_rows = {name: _band_row(arms[name], 1) for name in ARMS}
    b_ok = {name: _ok(row) for name, row in b_rows.items()}
    if version == 1:
        d1_arm = b_ok
    else:
        d1_arm = {
            name: b_ok[name] and length_check_refusal(_band_row(arms[name], 2)) for name in ARMS
        }
    if any(d1_arm.values()):
        subs: list[str] = []
        if not d1_arm["npuw"]:
            subs.append("key_fix")
        for name in ARMS:
            if d1_arm[name] and arms[name].get("r1_after_value") != request:
                subs.append("readback_fix")
                break
        return "D1", "+".join(subs) if subs else "none"
    statuses = {name: prompt_status(row) for name, row in b_rows.items() if row is not None}
    if all(statuses[name] in ("refused", "truncated") for name in ARMS):
        return "D2", "-"
    accepted = [name for name in ARMS if statuses[name] == "accepted"]
    if accepted and all(b_rows[name].get("valid") is not True for name in accepted):
        return "D3", "-"
    return "D4", "-"


# ---------------------------------------------------------------- readback


def runner_readback(pipe: Any, core: Any) -> dict[str, Any]:
    """Verbatim copy of the runner's inline readback (run_npu_profile.py).

    tests/test_npu_maxlen_diag.py pins this to the runner's source. With no
    pipeline (before load) only the core fallback runs.
    """
    max_prompt_len = None
    read_errors: list[str] = []
    source = None
    if pipe is not None:
        try:
            max_prompt_len = int(pipe.get_property("NPUW_LLM_MAX_PROMPT_LEN"))
            source = "pipeline"
        except Exception as exc:
            read_errors.append(f"pipeline: {type(exc).__name__}: {exc}")
            try:
                max_prompt_len = int(core.get_property("NPU", "NPUW_LLM_MAX_PROMPT_LEN"))
                source = "core"
            except Exception as exc2:
                read_errors.append(f"core: {type(exc2).__name__}: {exc2}")
    else:
        try:
            max_prompt_len = int(core.get_property("NPU", "NPUW_LLM_MAX_PROMPT_LEN"))
            source = "core"
        except Exception as exc2:
            read_errors.append(f"core: {type(exc2).__name__}: {exc2}")
    return {"value": max_prompt_len, "source": source, "read_errors": read_errors}


def _jsonable(value: Any) -> Any:
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return str(value)


def readback_names(core: Any) -> tuple[list[str], str | None]:
    try:
        supported = core.get_property("NPU", "SUPPORTED_PROPERTIES")
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"
    names = sorted({str(name) for name in supported})
    return [n for n in names if any(tok in n.upper() for tok in READBACK_TOKENS)], None


def core_readback(core: Any, names: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in names:
        try:
            out[name] = {"value": _jsonable(core.get_property("NPU", name)), "error": None}
        except Exception as exc:
            out[name] = {"value": None, "error": f"{type(exc).__name__}: {exc}"}
    return out


def pipeline_readback(pipe: Any, names: list[str]) -> dict[str, Any]:
    """r3: whatever the loaded pipeline exposes. Every attempt is recorded."""
    attempts: list[dict[str, Any]] = []
    public = sorted(n for n in dir(pipe) if not n.startswith("_"))
    if hasattr(pipe, "get_property"):
        keys = sorted(
            set(names) | {"NPUW_LLM_MAX_PROMPT_LEN", "MAX_PROMPT_LEN", "MIN_RESPONSE_LEN"}
        )
        for key in keys:
            try:
                value = _jsonable(pipe.get_property(key))
                attempts.append({"call": f"get_property({key!r})", "value": value, "error": None})
            except Exception as exc:
                attempts.append(
                    {
                        "call": f"get_property({key!r})",
                        "value": None,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
    else:
        attempts.append({"call": "get_property", "value": None, "error": "not exposed"})
    if hasattr(pipe, "get_generation_config"):
        try:
            cfg = pipe.get_generation_config()
            fields = {
                n: _jsonable(getattr(cfg, n))
                for n in dir(cfg)
                if not n.startswith("_") and not callable(getattr(cfg, n, None))
            }
            attempts.append({"call": "get_generation_config()", "value": fields, "error": None})
        except Exception as exc:
            attempts.append(
                {
                    "call": "get_generation_config()",
                    "value": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    else:
        attempts.append({"call": "get_generation_config", "value": None, "error": "not exposed"})
    return {"public_attributes": public, "attempts": attempts}


# ---------------------------------------------------------------- child


def parse_bands(text: str, version: int = RULE_VERSION) -> list[list[int]]:
    """Bands A, B (v1) or A, B, C (v2), as "lo-hi,lo-hi[,lo-hi]"."""
    bands: list[list[int]] = []
    for part in text.split(","):
        lo, hi = (int(x) for x in part.strip().split("-", 1))
        if hi < lo:
            raise SystemExit(f"REFUSED -- band {part!r} is reversed")
        bands.append([lo, hi])
    want = 2 if int(version) == 1 else 3
    if len(bands) != want:
        raise SystemExit(f"REFUSED -- rule v{version} needs exactly {want} bands")
    return bands


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validity(text: str) -> dict[str, Any]:
    """docs/NPU_PROTOCOL.md: parses with the GPU parser, repeat share <= 0.5."""
    parses = output_parses(text)
    fraction = fourgram_repeat_fraction(whitespace_tokens(text))
    degenerate = fraction is not None and fraction > REPEAT_FRACTION_MAX
    return {
        "parses": parses,
        "repeat_4gram_fraction": fraction,
        "valid": bool(parses and not degenerate),
    }


def greedy_config(ov_genai: Any) -> tuple[Any, dict[str, Any]]:
    """v2: explicit greedy config, fresh per call, and the record of it."""
    cfg = ov_genai.GenerationConfig()
    cfg.max_new_tokens = MAX_NEW_TOKENS
    cfg.do_sample = False
    cfg.apply_chat_template = APPLY_CHAT_TEMPLATE
    record: dict[str, Any] = {}
    for name in dir(cfg):
        if name.startswith("_"):
            continue
        try:
            value = getattr(cfg, name)
        except Exception as exc:
            record[name] = f"unreadable: {type(exc).__name__}"
            continue
        if not callable(value):
            record[name] = _jsonable(value)
    return cfg, record


def generate_direct(
    ov_genai: Any, pipe: Any, prompt: str, *, version: int = RULE_VERSION
) -> dict[str, Any]:
    """generate with no length check in front.

    v1 passed the prompt as a str, which returns a str with no perf_metrics on
    openvino-genai 2026.2.1. v2 passes a one-element list, which returns
    DecodedResults whose perf_metrics reports the input-token count.
    """
    if version == 1:
        cfg = ov_genai.GenerationConfig()
        cfg.max_new_tokens = MAX_NEW_TOKENS
        cfg.do_sample = False
        config_record: dict[str, Any] | None = None
        inputs: Any = prompt
    else:
        cfg, config_record = greedy_config(ov_genai)
        inputs = [prompt]
    streamer = _make_ttft_streamer(ov_genai)
    streamer.t0_ns = time.perf_counter_ns()
    t0 = time.perf_counter()
    try:
        result = pipe.generate(inputs, cfg, streamer)
    except Exception as exc:
        message = str(exc)
        return {
            "generate_returned": False,
            "exception": {"class": type(exc).__name__, "message": message},
            "length_check_refusal": LENGTH_CHECK_TEXT in message,
            "stated_cap": stated_cap(message),
            "wall_s": time.perf_counter() - t0,
            "output_text": None,
            "pipeline_input_tokens": None,
            "ttft_s": None,
            "generation_config": config_record,
            "input_form": type(inputs).__name__,
        }
    wall_s = time.perf_counter() - t0
    text = _text_from_generate_result(result)
    measured = _metrics(result)
    metric_error = measured.get("metric_error")
    if getattr(result, "perf_metrics", None) is None and metric_error is None:
        metric_error = f"no perf_metrics on {type(result).__name__}"
    ttft_ns, ttft_source = resolve_ttft_ns(None, streamer.ttft_ns)
    return {
        "generate_returned": True,
        "exception": None,
        "length_check_refusal": False,
        "stated_cap": None,
        "wall_s": wall_s,
        "output_text": text,
        "result_type": type(result).__name__,
        "input_form": type(inputs).__name__,
        "generation_config": config_record,
        "pipeline_input_tokens": measured.get("prompt_tokens"),
        "pipeline_completion_tokens": measured.get("completion_tokens"),
        "perf_metrics_ttft_s": measured.get("prefill_s"),
        "metric_error": metric_error,
        "ttft_s": None if not ttft_ns else ttft_ns / 1e9,
        "ttft_source": ttft_source if ttft_ns else None,
        "streamer_tokens": int(getattr(streamer, "tokens_written", 0)),
        **validity(text),
    }


def run_child(args: argparse.Namespace) -> int:
    result_path: Path = args.result
    version = int(args.rule_version)
    bands = parse_bands(args.prompt_bands, version)
    rec: dict[str, Any] = {
        "rule_version": version,
        "arm": args.arm,
        "label": ARM_LABEL[args.arm],
        "request": int(args.request),
        "props": arm_props(args.arm, int(args.request)),
        "complete": False,
    }
    _write(result_path, rec)
    if args.smoke:
        return _smoke_child(rec, bands, result_path)

    import openvino as ov
    import openvino_genai as ov_genai

    from seam.model_provenance import load_local_spec

    spec = load_local_spec(args.model_spec)
    ir = Path(str(spec["ir_dir"]))
    if not ir.is_absolute():
        ir = ROOT / ir
    rec["ir_dir"] = str(ir)
    core = ov.Core()
    names, names_error = readback_names(core)
    rec["r2_names"] = names
    rec["r2_names_error"] = names_error
    rec["r1_before"] = runner_readback(None, core)
    rec["r2_before"] = core_readback(core, names)
    _write(result_path, rec)

    pipe = None
    t0 = time.perf_counter()
    try:
        pipe = ov_genai.LLMPipeline(str(ir), "NPU", **rec["props"])
        rec["load_error"] = None
    except Exception as exc:
        rec["load_error"] = f"{type(exc).__name__}: {exc}"
    rec["load_s"] = time.perf_counter() - t0
    _write(result_path, rec)
    if pipe is None:
        rec["complete"] = True
        _write(result_path, rec)
        return 0

    rec["r1_after"] = runner_readback(pipe, core)
    rec["r1_after_value"] = rec["r1_after"]["value"]
    rec["r2_after"] = core_readback(core, names)
    rec["r3_after"] = pipeline_readback(pipe, names)
    _write(result_path, rec)

    tokenizer = ov_genai.Tokenizer(str(ir))
    filler = _filler()
    rec["prompts"] = []
    for band in bands:
        target = (band[0] + band[1]) // 2
        row: dict[str, Any] = {"band": band, "target_tokens": target}
        try:
            prompt = rendered_exact_prompt(tokenizer, target, unit=filler, salt=SALT)
            row["realized_tokens"] = id_count(tokenizer, prompt)
        except Exception as exc:
            row["realized_tokens"] = None
            row["build_error"] = f"{type(exc).__name__}: {exc}"
            row.update(generate_returned=False, exception=None)
            rec["prompts"].append(row)
            _write(result_path, rec)
            continue
        row.update(generate_direct(ov_genai, pipe, prompt, version=version))
        row["status"] = prompt_status(row)
        rec["prompts"].append(row)
        _write(result_path, rec)
    rec["complete"] = True
    _write(result_path, rec)
    return 0


def _smoke_child(rec: dict[str, Any], bands: list[list[int]], result_path: Path) -> int:
    """Plumbing only. No openvino. Synthetic, never a result."""
    rec.update(smoke=True, load_error=None, load_s=0.0, r1_after_value=None)
    rec["prompts"] = []
    for index, band in enumerate(bands):
        target = (band[0] + band[1]) // 2
        row = {
            "band": band,
            "target_tokens": target,
            "realized_tokens": target,
            "generate_returned": True,
            "exception": None,
            "pipeline_input_tokens": target,
            "output_text": "smoke",
            **validity("smoke"),
        }
        if index == 2:
            message = f"smoke {LENGTH_CHECK_TEXT} up to 2048 tokens"
            row.update(
                generate_returned=False,
                exception={"class": "RuntimeError", "message": message},
                pipeline_input_tokens=None,
                output_text=None,
                length_check_refusal=True,
                stated_cap=stated_cap(message),
            )
        row["status"] = prompt_status(row)
        rec["prompts"].append(row)
    rec["complete"] = True
    _write(result_path, rec)
    return 0


# ---------------------------------------------------------------- parent


def _git(*argv: str) -> str:
    done = subprocess.run(["git", *argv], cwd=ROOT, capture_output=True, text=True, check=False)
    return done.stdout


def dirty_tracked(status_short: str) -> list[str]:
    return [line for line in status_short.splitlines() if line and not line.startswith("??")]


def watchdog_state(log_path: str) -> dict[str, Any]:
    """Read-only. Last non-digest line must be empty_flag or paused."""
    path = Path(log_path)
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
            text = handle.read()
    except OSError as exc:
        return {"path": log_path, "last_line": None, "idle": False, "error": str(exc)}
    last_line = None
    last_entry = None
    for line in text.splitlines():
        parsed = parse_log_line(line)
        if parsed is not None and not is_neutral(parsed):
            last_line, last_entry = line.strip(), parsed
    idle = last_entry is not None and is_idle(last_entry)
    return {
        "path": log_path,
        "last_line": last_line,
        "action": None if last_entry is None else last_entry.get("action"),
        "idle": idle,
        "error": None,
    }


def live_versions() -> dict[str, Any]:
    from importlib import metadata

    out: dict[str, Any] = {}
    for dist in ("openvino", "openvino-genai", "openvino-tokenizers"):
        try:
            out[dist] = metadata.version(dist)
        except Exception as exc:
            out[dist] = f"unavailable: {type(exc).__name__}"
    try:
        import openvino as ov

        out["openvino.get_version"] = str(ov.get_version())
    except Exception as exc:
        out["openvino.get_version"] = f"unavailable: {type(exc).__name__}"
    try:
        import openvino_genai as ov_genai

        out["openvino_genai.__version__"] = str(getattr(ov_genai, "__version__", None))
    except Exception as exc:
        out["openvino_genai.__version__"] = f"unavailable: {type(exc).__name__}"
    return out


def run_arm(args: argparse.Namespace, arm: str, out_dir: Path) -> dict[str, Any]:
    result_path = out_dir / f"arm_{arm}.json"
    argv = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "--child",
        "--arm",
        arm,
        "--request",
        str(args.request),
        "--prompt-bands",
        args.prompt_bands,
        "--rule-version",
        str(args.rule_version),
        "--model-spec",
        str(args.model_spec),
        "--result",
        str(result_path),
    ]
    if args.smoke:
        argv.append("--smoke")
    stdout_path = out_dir / f"arm_{arm}.stdout.log"
    stderr_path = out_dir / f"arm_{arm}.stderr.log"
    started = time.perf_counter()
    timed_out = False
    code: int | None
    with (
        stdout_path.open("w", encoding="utf-8") as so,
        stderr_path.open("w", encoding="utf-8") as se,
    ):
        proc = subprocess.Popen(argv, cwd=ROOT, stdout=so, stderr=se)
        try:
            code = proc.wait(timeout=args.child_timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            proc.wait()
            code = None
    wall_s = time.perf_counter() - started
    rec: dict[str, Any] = {}
    if result_path.is_file():
        try:
            rec = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            rec = {}
    rec["result_present"] = bool(rec.get("complete"))
    rec["timed_out"] = timed_out
    rec["child_exit_code"] = code
    rec["child_exit_hex"] = None if code is None else f"0x{code & 0xFFFFFFFF:08X}"
    rec["child_wall_s"] = wall_s
    rec["command"] = argv
    for row in rec.get("prompts") or []:
        row["child_exit_hex"] = rec["child_exit_hex"]
    return rec


def run_parent(args: argparse.Namespace) -> int:
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    if sorted(arms) != sorted(ARMS):
        raise SystemExit("REFUSED -- the rule needs both arms: doc,npuw")
    version = int(args.rule_version)
    bands = parse_bands(args.prompt_bands, version)
    started = datetime.now(UTC)
    stamp = started.strftime("%Y%m%dT%H%M%SZ")
    head = _git("rev-parse", "HEAD").strip()
    status_short = _git("status", "--short")
    dirty = dirty_tracked(status_short)
    if dirty and not args.smoke:
        print("REFUSED -- tracked files are modified:\n" + "\n".join(dirty))
        return 1
    if args.smoke:
        watchdog: dict[str, Any] = {"path": args.watchdog_log, "smoke": True, "idle": None}
    else:
        watchdog = watchdog_state(args.watchdog_log)
        if not watchdog["idle"]:
            print(f"REFUSED -- watchdog not idle: {watchdog.get('last_line') or watchdog}")
            return 1
    out_dir = Path(args.out) / f"diag_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    doc: dict[str, Any] = {
        "diagnostic": "NPU-MAXLEN-DIAG",
        "rule_version": version,
        "measurement": False,
        "smoke": bool(args.smoke),
        "host": socket.gethostname(),
        "utc_start": started.isoformat(),
        "git_head": head,
        "git_status_short": status_short,
        "versions": {} if args.smoke else live_versions(),
        "watchdog": watchdog,
        "request": int(args.request),
        "prompt_bands": bands,
        "max_new_tokens": MAX_NEW_TOKENS,
        "do_sample": False,
        "apply_chat_template": APPLY_CHAT_TEMPLATE if version >= 2 else None,
        "child_timeout_s": args.child_timeout,
        "arms": {},
    }
    _write(out_dir / "diag.json", doc)
    for arm in arms:
        doc["arms"][arm] = run_arm(args, arm, out_dir)
        _write(out_dir / "diag.json", doc)
    for rec in doc["arms"].values():
        prompts = rec.get("prompts") or []
        if prompts and isinstance(prompts[0], dict):
            rec["band_a_ttft_s"] = prompts[0].get("ttft_s")
            rec["band_a_perf_metrics_ttft_s"] = prompts[0].get("perf_metrics_ttft_s")
    doc["band_a_ttft_reference"] = "flat ~1.30 s prefill near 1024 in 680b031a; outside the rule"
    verdict, subcase = classify(doc)
    doc["verdict"] = verdict
    doc["subcase"] = subcase
    doc["utc_end"] = datetime.now(UTC).isoformat()
    _write(out_dir / "diag.json", doc)
    print(f"DIAG_VERDICT {verdict} {subcase} {out_dir}")
    return 0


def classify_file(path: Path) -> int:
    """Re-read a finished diag.json (any rule version) and print its verdict."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    verdict, subcase = classify(doc)
    version = int(doc.get("rule_version") or 1)
    recorded = (doc.get("verdict"), doc.get("subcase"))
    print(f"rule v{version} recorded {recorded[0]} {recorded[1]}")
    print(f"DIAG_VERDICT {verdict} {subcase} {Path(path).parent}")
    return 0 if recorded == (verdict, subcase) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=int, default=2048)
    parser.add_argument("--arms", default="doc,npuw")
    parser.add_argument("--rule-version", type=int, choices=(1, 2), default=RULE_VERSION)
    parser.add_argument("--prompt-bands", default=None)
    parser.add_argument("--classify", type=Path, help="re-read a diag.json; no run")
    parser.add_argument("--out", type=Path, default=ROOT / "derived" / "npu" / "diag")
    parser.add_argument("--model-spec", type=Path, default=DEFAULT_MODEL_SPEC)
    parser.add_argument("--watchdog-log", default=DEFAULT_WATCHDOG_LOG)
    parser.add_argument("--child-timeout", type=int, default=CHILD_TIMEOUT_S)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--arm", choices=ARMS)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args(argv)
    if args.classify is not None:
        return classify_file(args.classify)
    if args.prompt_bands is None:
        args.prompt_bands = BANDS_BY_VERSION[int(args.rule_version)]
    if args.child:
        if args.arm is None or args.result is None:
            raise SystemExit("REFUSED -- child needs --arm and --result")
        return run_child(args)
    return run_parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
