"""NPU-NATSTOP. Diagnostic, not a measurement. Nothing here is cited.

Asks whether the NPU ends or degenerates where the GPU writes text, and
whether the chat template causes it. 16 cells: NPU and GPU (same IR) x
SINGLE and DOUBLE template x 64, 768, 960, 1984 realized tokens. Greedy,
max_new_tokens 64, min_new_tokens not set. Each cell runs in its own child
process, one after another, so two NPU pipelines are never loaded at once.

Reuses the NPU-1 runner's load props, generation config, list-form generate
and rung prompt builder. This script does not open a preregistration,
amendment, prediction or rule file.

Final stdout line: NATSTOP_VERDICT <N1|N2|N3|N4> <out_dir>

--prompt-set chat is the NPU-NATSTOP-B scope check: the same devices and
templates on 2 fixed short chat prompts (8 cells), classified B1-B4 under the
real-token validity rule. Its final stdout line is
NATSTOP_B_VERDICT <B1|B2|B3|B4> <out_dir>. The prompt texts and the validity
constants are written here and in the amendment; this script does not open
the amendment.

--prompt-set f1 is the export-format test F1 (amendment 2026-10-13): the
chat prompts on another IR (--model-spec; the int4 default is refused), each
cell judged by the validity rule plus a fixed content check, classified
FA/FB/FC. Final stdout line: NATSTOP_F1_VERDICT <FA|FB|FC> <out_dir>.

Every run records the IR's quantization metadata in plan.json, read from the
IR (seam.ir_quantization), and a real run refuses when openvino_model.xml is
absent or does not match the spec's pin.
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from seam.ir_quantization import ir_quantization  # noqa: E402
from seam.npu_validity import REPEAT_FRACTION_MAX, fourgram_repeat_fraction  # noqa: E402
from seam.tools.boot4_text import id_count, render_user, rendered_exact_prompt  # noqa: E402
from tools.npu_maxlen_diag import (  # noqa: E402
    _git,
    _jsonable,
    dirty_tracked,
    live_versions,
    watchdog_state,
)
from tools.run_npu_profile import (  # noqa: E402
    MIN_RESPONSE_LEN,
    _filler,
    generate_once,
    generation_config,
    npu_load_props,
)

DIAGNOSTIC = "NPU-NATSTOP"
DEVICES = ("NPU", "GPU")
TEMPLATES = ("SINGLE", "DOUBLE")
LENGTHS = (64, 768, 960, 1984)
NPU_MAX_PROMPT_LEN = 2048
PREFILL_CHUNK_SIZE = 1024
MAX_NEW_TOKENS = 64
RECORDED_IDS = 64
MATCH_IDS = 16
CHILD_TIMEOUT_S = 600
SALT = "npu"
THINK_TAGS = ("<think>", "</think>")
DEFAULT_MODEL_SPEC = ROOT / "configs" / "models" / "Qwen3-4B-int4-ov.yaml"
DEFAULT_OUT = ROOT / "derived" / "npu"
DEFAULT_WATCHDOG_LOG = r"C:\apu\ovn\watchdog.log"

PROMPT_SETS = ("filler", "chat", "f1")
CHAT_SETS = ("chat", "f1")
# NPU-NATSTOP-B prompts (fixed text, user turn, thinking disabled).
CHAT_PROMPTS = {
    "chat1": "What is the capital of France? Answer in one sentence.",
    "chat2": "Give three tips for staying focused while studying.",
}
# Validity rule (amendment 2026-10-12), derived from the 8 GPU cells of
# natstop_6b39a76e: K = fewest real tokens in a GPU cell (62, DOUBLE: 64 ids
# less <think> and one newline); T = highest GPU id 4-gram repeat (27/61, GPU
# DOUBLE 64, which quotes the repeated filler).
VALID_MIN_REAL_TOKENS = 62
VALID_REPEAT_MAX = 27 / 61

# F1 content check (amendment 2026-10-13), on real_text:
# chat1 contains "paris" (case-insensitive); chat2 has at least 2 distinct tip
# lines, each a numeral or bullet line whose remainder has at least 5 words
# (whitespace pieces with an ASCII letter).
CHAT1_KEYWORD = "paris"
TIP_LINE = re.compile(r"^(?:#{1,6}\s*)?(?:\*\*)?(?:\d{1,2}[.)]|[-*+]|\u2022)(?:\*\*)?\s+(.+)$")
TIP_MIN_WORDS = 5
TIP_MIN_LINES = 2


def items_for(prompt_set: str = "filler") -> tuple[Any, ...]:
    """Lengths for the filler set; prompt ids for the chat set."""
    return LENGTHS if prompt_set == "filler" else tuple(CHAT_PROMPTS)


def cell_order(prompt_set: str = "filler") -> list[tuple[str, str, Any]]:
    """For each length (or prompt): NPU SINGLE, NPU DOUBLE, GPU SINGLE, GPU DOUBLE."""
    return [(d, t, n) for n in items_for(prompt_set) for d in DEVICES for t in TEMPLATES]


def cell_key(device: str, template: str, item: Any) -> str:
    return f"{device}_{template}_{item}"


# ---------------------------------------------------------------- definitions


def cell_ok(cell: dict[str, Any] | None) -> bool:
    """Child exit 0, complete record, loaded, generate returned, input count reported.

    SINGLE also needs the pipeline input count to equal the realized count.
    """
    if not isinstance(cell, dict):
        return False
    if cell.get("child_exit_code") != 0 or not cell.get("complete"):
        return False
    if cell.get("load_error") is not None or not cell.get("generate_returned"):
        return False
    reported = cell.get("pipeline_input_tokens")
    if not isinstance(reported, int):
        return False
    return not (cell.get("template") == "SINGLE" and reported != cell.get("realized_tokens"))


def completion_count(cell: dict[str, Any]) -> int | None:
    count = cell.get("completion_tokens")
    if isinstance(count, int):
        return count
    ids = cell.get("generated_ids")
    return len(ids) if isinstance(ids, list) else None


def stop_reason(cell: dict[str, Any]) -> str:
    """'error' when generate raised; 'max' at >= 64 completions; else 'EOS'."""
    if not cell.get("generate_returned"):
        return "error"
    count = completion_count(cell)
    if isinstance(count, int) and count >= MAX_NEW_TOKENS:
        return "max"
    return "EOS"


def real_text(text: str | None) -> str:
    """Full text with every <think> and </think> removed, whitespace stripped."""
    out = text or ""
    for tag in THINK_TAGS:
        out = out.replace(tag, "")
    return out.strip()


def id_repeat_fraction(cell: dict[str, Any]) -> float | None:
    """Repeat share over token-id 4-grams, not whitespace words."""
    ids = cell.get("generated_ids")
    return fourgram_repeat_fraction(list(ids) if isinstance(ids, list) else [])


def degenerate(cell: dict[str, Any] | None) -> bool:
    if not cell_ok(cell):
        return False
    assert cell is not None
    if not real_text(cell.get("text")):
        return True
    fraction = id_repeat_fraction(cell)
    return fraction is not None and fraction > REPEAT_FRACTION_MAX


def ends_at_once(cell: dict[str, Any] | None) -> bool:
    if not cell_ok(cell):
        return False
    assert cell is not None
    return stop_reason(cell) == "EOS" and not real_text(cell.get("text"))


def fails(cell: dict[str, Any] | None) -> bool:
    return ends_at_once(cell) or degenerate(cell)


def writes_text(cell: dict[str, Any] | None) -> bool:
    return cell_ok(cell) and not fails(cell)


def matches(npu: dict[str, Any] | None, gpu: dict[str, Any] | None) -> bool:
    """First 16 ids equal, or both shorter than 16 and equal in full."""
    if not cell_ok(npu) or not cell_ok(gpu):
        return False
    assert npu is not None and gpu is not None
    a = list(npu.get("generated_ids") or [])
    b = list(gpu.get("generated_ids") or [])
    if len(a) >= MATCH_IDS and len(b) >= MATCH_IDS:
        return a[:MATCH_IDS] == b[:MATCH_IDS]
    if len(a) < MATCH_IDS and len(b) < MATCH_IDS:
        return a == b
    return False


def derived_fields(cell: dict[str, Any]) -> dict[str, Any]:
    """The rule's per-cell terms, written beside the record for the reader."""
    return {
        "cell_ok": cell_ok(cell),
        "stop_reason": stop_reason(cell),
        "real_text": real_text(cell.get("text")),
        "id_repeat_fraction": id_repeat_fraction(cell),
        "degenerate": degenerate(cell),
        "ends_at_once": ends_at_once(cell),
        "fails": fails(cell),
        "writes_text": writes_text(cell),
    }


def classify(cells: dict[str, Any]) -> str:
    """The NPU-NATSTOP rule, by code. First match wins; else N4."""

    def get(device: str, template: str, n: int) -> dict[str, Any] | None:
        cell = cells.get(cell_key(device, template, n))
        return cell if isinstance(cell, dict) else None

    if not all(writes_text(get("GPU", "SINGLE", n)) for n in LENGTHS):
        return "N4"
    if all(matches(get("NPU", "SINGLE", n), get("GPU", "SINGLE", n)) for n in LENGTHS):
        return "N1"
    if all(
        fails(get("NPU", "SINGLE", n))
        and writes_text(get("GPU", "DOUBLE", n))
        and matches(get("NPU", "DOUBLE", n), get("GPU", "DOUBLE", n))
        for n in LENGTHS
    ):
        return "N2"
    if all(fails(get("NPU", "SINGLE", n)) and fails(get("NPU", "DOUBLE", n)) for n in LENGTHS):
        return "N3"
    return "N4"


def real_token_count(cell: dict[str, Any] | None) -> int | None:
    """Recorded by the child: generated ids that are not think tags, not in
    the stop set, and do not decode to whitespace only."""
    if not isinstance(cell, dict):
        return None
    count = cell.get("real_token_count")
    return count if isinstance(count, int) else None


def valid(cell: dict[str, Any] | None, reference: dict[str, Any] | None) -> bool:
    """Amendment 2026-10-12 validity rule.

    Cell ok, at least max(1, K_eff) real tokens, id 4-gram repeat <= T.
    K_eff = min(K, real tokens of the paired GPU cell) when that cell stopped
    by EOS (a short answer is the reference length); K when it hit max.
    """
    if not cell_ok(cell):
        return False
    assert cell is not None
    count = real_token_count(cell)
    if count is None:
        return False
    k_eff = VALID_MIN_REAL_TOKENS
    ref_count = real_token_count(reference)
    if cell_ok(reference) and stop_reason(reference) == "EOS" and ref_count is not None:
        k_eff = min(k_eff, ref_count)
    if count < max(1, k_eff):
        return False
    fraction = id_repeat_fraction(cell)
    return fraction is None or fraction <= VALID_REPEAT_MAX


def classify_scope(cells: dict[str, Any]) -> str:
    """NPU-NATSTOP-B rule, by code. First match wins.

    G: every GPU SINGLE chat cell is valid (its own reference); else B4.
    B1: every NPU chat cell (both templates, both prompts) is invalid.
    B2: NPU SINGLE valid on both prompts, or NPU DOUBLE valid on both.
    B3: anything else (mixed).
    """

    def get(device: str, template: str, item: str) -> dict[str, Any] | None:
        cell = cells.get(cell_key(device, template, item))
        return cell if isinstance(cell, dict) else None

    prompts = tuple(CHAT_PROMPTS)
    if not all(valid(get("GPU", "SINGLE", p), get("GPU", "SINGLE", p)) for p in prompts):
        return "B4"

    def npu_valid(template: str, p: str) -> bool:
        return valid(get("NPU", template, p), get("GPU", template, p))

    if not any(npu_valid(t, p) for t in TEMPLATES for p in prompts):
        return "B1"
    if any(all(npu_valid(t, p) for p in prompts) for t in TEMPLATES):
        return "B2"
    return "B3"


def tip_lines(text: str | None) -> list[str]:
    """Distinct tip-line remainders (lowercased, whitespace collapsed)."""
    found: list[str] = []
    for line in real_text(text).splitlines():
        match = TIP_LINE.match(line.strip())
        if match is None:
            continue
        body = match.group(1)
        words = [w for w in body.split() if re.search("[A-Za-z]", w)]
        key = " ".join(body.lower().split())
        if len(words) >= TIP_MIN_WORDS and key not in found:
            found.append(key)
    return found


def content_ok(prompt_id: str | None, text: str | None) -> bool:
    """F1 content check on the real text (think tags removed)."""
    if prompt_id == "chat1":
        return CHAT1_KEYWORD in real_text(text).lower()
    if prompt_id == "chat2":
        return len(tip_lines(text)) >= TIP_MIN_LINES
    return False


def passes(cell: dict[str, Any] | None, reference: dict[str, Any] | None) -> bool:
    """F1: valid under the 2026-10-12 rule and the content check holds."""
    if not valid(cell, reference):
        return False
    assert cell is not None
    return content_ok(cell.get("prompt_id"), cell.get("text"))


def classify_format(cells: dict[str, Any]) -> str:
    """F1 rule, by code. First match wins.

    FA: under some template the NPU cell passes on both prompts.
    FB: all NPU cells ok, none passes, and GPU SINGLE passes on both prompts.
    FC: anything else (an NPU cell not ok, a failing GPU reference, mixed).
    """

    def get(device: str, template: str, item: str) -> dict[str, Any] | None:
        cell = cells.get(cell_key(device, template, item))
        return cell if isinstance(cell, dict) else None

    prompts = tuple(CHAT_PROMPTS)

    def npu_passes(template: str, p: str) -> bool:
        return passes(get("NPU", template, p), get("GPU", template, p))

    if any(all(npu_passes(t, p) for p in prompts) for t in TEMPLATES):
        return "FA"
    npu_ok = all(cell_ok(get("NPU", t, p)) for t in TEMPLATES for p in prompts)
    none_pass = not any(npu_passes(t, p) for t in TEMPLATES for p in prompts)
    gpu_ref = all(passes(get("GPU", "SINGLE", p), get("GPU", "SINGLE", p)) for p in prompts)
    if npu_ok and none_pass and gpu_ref:
        return "FB"
    return "FC"


def ir_record(model_spec: Path) -> dict[str, Any]:
    """Spec pin plus the quantization metadata read from the IR itself."""
    from seam.model_provenance import load_local_spec

    try:
        spec = load_local_spec(Path(model_spec))
    except Exception as exc:
        return {"spec_error": f"{type(exc).__name__}: {exc}", "ir_quantization": None}
    ir = Path(str(spec["ir_dir"]))
    if not ir.is_absolute():
        ir = ROOT / ir
    pin = (spec.get("ir_files") or {}).get("openvino_model.xml")
    return {
        "spec_error": None,
        "name": spec.get("name"),
        "revision": spec.get("revision"),
        "ir_sha256": spec.get("ir_sha256"),
        "spec_publisher_quantization": spec.get("publisher_quantization"),
        "ir_quantization": ir_quantization(ir, pin),
    }


def ir_refusal(record: dict[str, Any]) -> str | None:
    """Why a real run must not start on this IR, or None."""
    if record.get("spec_error"):
        return f"model spec unreadable: {record['spec_error']}"
    quant = record.get("ir_quantization") or {}
    if not quant.get("xml_present"):
        return f"openvino_model.xml absent in {quant.get('ir_dir')}"
    if quant.get("xml_matches_pin") is not True:
        return "openvino_model.xml does not match the spec pin"
    return None


# ---------------------------------------------------------------- child


def _write(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def config_record(cfg: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name in ("max_new_tokens", "min_new_tokens", "do_sample", "apply_chat_template"):
        try:
            out[name] = _jsonable(getattr(cfg, name))
        except Exception as exc:
            out[name] = f"unreadable: {type(exc).__name__}"
    return out


def stop_ids(pipe: Any) -> dict[str, Any]:
    try:
        cfg = pipe.get_generation_config()
    except Exception as exc:
        return {"eos_token_id": None, "stop_token_ids": None, "error": f"{type(exc).__name__}"}
    eos = getattr(cfg, "eos_token_id", None)
    stops = getattr(cfg, "stop_token_ids", None)
    return {
        "eos_token_id": _jsonable(eos),
        "stop_token_ids": sorted(_jsonable(list(stops))) if stops else [],
        "error": None,
    }


def decode_one(tokenizer: Any, token_id: int | None) -> str | None:
    if token_id is None:
        return None
    try:
        return str(tokenizer.decode([int(token_id)]))
    except Exception as exc:
        return f"<decode error {type(exc).__name__}>"


def generation_fields(
    out: dict[str, Any], *, device: str, eos: dict[str, Any], tokenizer: Any
) -> dict[str, Any]:
    """Per-generate record from generate_once output."""
    returned = bool(out.get("ok", True))
    ids = [int(i) for i in out.get("token_ids") or []][:RECORDED_IDS]
    first = ids[0] if ids else None
    reported = out.get("prompt_tokens")
    stop_set = set(eos.get("stop_token_ids") or [])
    if isinstance(eos.get("eos_token_id"), int):
        stop_set.add(int(eos["eos_token_id"]))
    real_count = None
    if tokenizer is not None:
        real_count = 0
        for token in ids:
            if token in stop_set:
                continue
            piece = decode_one(tokenizer, token) or ""
            for tag in THINK_TAGS:
                piece = piece.replace(tag, "")
            if piece.strip():
                real_count += 1
    kv_room = None
    if device == "NPU" and isinstance(reported, int):
        kv_room = NPU_MAX_PROMPT_LEN + MIN_RESPONSE_LEN - reported
    return {
        "generate_returned": returned,
        "error": out.get("error"),
        "length_check_refusal": bool(out.get("length_check_refusal")),
        "text": out.get("text") if returned else None,
        "generated_ids": ids,
        "completion_tokens": out.get("completion_tokens"),
        "streamer_tokens": out.get("streamer_tokens"),
        "first_token_id": first,
        "first_token_text": decode_one(tokenizer, first),
        "real_token_count": real_count,
        "last_id_in_stop_set": bool(ids) and ids[-1] in stop_set,
        "ttft_s": out.get("prefill_s"),
        "ttft_source": out.get("ttft_source"),
        "pipeline_input_tokens": reported,
        "metric_error": out.get("metric_error"),
        "pipeline_stop_ids": eos,
        "kv_room": kv_room,
    }


def run_child(args: argparse.Namespace) -> int:
    rec: dict[str, Any] = {
        "device": args.device,
        "template": args.template,
        "n_tokens": None if args.prompt_id else int(args.n_tokens),
        "prompt_id": args.prompt_id,
        "complete": False,
    }
    if args.device == "NPU":
        rec["load_props"] = npu_load_props(NPU_MAX_PROMPT_LEN, PREFILL_CHUNK_SIZE)
    else:
        rec["load_props"] = {}
    _write(args.result, rec)
    if args.smoke:
        return _smoke_child(rec, args.result)

    import openvino_genai as ov_genai

    from seam.model_provenance import load_local_spec

    spec = load_local_spec(args.model_spec)
    ir = Path(str(spec["ir_dir"]))
    if not ir.is_absolute():
        ir = ROOT / ir
    rec["ir_dir"] = str(ir)
    tokenizer = ov_genai.Tokenizer(str(ir))
    try:
        if args.prompt_id:
            prompt = render_user(tokenizer, CHAT_PROMPTS[args.prompt_id])
        else:
            prompt = rendered_exact_prompt(tokenizer, int(args.n_tokens), unit=_filler(), salt=SALT)
        rec["realized_tokens"] = id_count(tokenizer, prompt)
    except Exception as exc:
        rec.update(realized_tokens=None, build_error=f"{type(exc).__name__}: {exc}")
        rec.update(load_error=None, generate_returned=False, complete=True)
        _write(args.result, rec)
        return 0
    _write(args.result, rec)

    pipe = None
    t0 = time.perf_counter()
    try:
        pipe = ov_genai.LLMPipeline(str(ir), args.device, **rec["load_props"])
        rec["load_error"] = None
    except Exception as exc:
        rec["load_error"] = f"{type(exc).__name__}: {exc}"
    rec["load_s"] = time.perf_counter() - t0
    _write(args.result, rec)
    if pipe is None:
        rec.update(generate_returned=False, complete=True)
        _write(args.result, rec)
        return 0

    cfg = generation_config(
        ov_genai,
        max_new_tokens=MAX_NEW_TOKENS,
        min_new_tokens=None,
        apply_chat_template=args.template == "DOUBLE",
    )
    rec["generation_config"] = config_record(cfg)
    eos = stop_ids(pipe)
    out = generate_once(ov_genai, pipe, prompt, cfg)
    rec.update(generation_fields(out, device=args.device, eos=eos, tokenizer=tokenizer))
    rec["complete"] = True
    _write(args.result, rec)
    return 0


def _smoke_child(rec: dict[str, Any], result_path: Path) -> int:
    """Plumbing only. No openvino. Synthetic, never a result."""
    n = 16 if rec.get("prompt_id") else int(rec["n_tokens"])
    reported = n + (8 if rec["template"] == "DOUBLE" else 0)
    ids = list(range(100, 100 + 20))
    rec.update(
        smoke=True,
        realized_tokens=n,
        load_error=None,
        load_s=0.0,
        generation_config={
            "max_new_tokens": MAX_NEW_TOKENS,
            "min_new_tokens": None,
            "do_sample": False,
            "apply_chat_template": rec["template"] == "DOUBLE",
        },
    )
    out = {
        "ok": True,
        "text": "smoke text",
        "token_ids": ids,
        "completion_tokens": len(ids),
        "streamer_tokens": len(ids),
        "prefill_s": 0.0,
        "ttft_source": "smoke",
        "prompt_tokens": reported,
    }
    eos = {"eos_token_id": 0, "stop_token_ids": [0], "error": None}
    rec.update(generation_fields(out, device=rec["device"], eos=eos, tokenizer=None))
    rec["first_token_text"] = "smoke"
    rec["real_token_count"] = len(ids)
    rec["complete"] = True
    _write(result_path, rec)
    return 0


# ---------------------------------------------------------------- parent


def run_cell(
    args: argparse.Namespace, device: str, template: str, n: Any, out_dir: Path
) -> dict[str, Any]:
    key = cell_key(device, template, n)
    result_path = out_dir / f"cell_{key}.json"
    chat = args.prompt_set in CHAT_SETS
    argv = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "--child",
        "--device",
        device,
        "--template",
        template,
        "--prompt-id" if chat else "--n-tokens",
        str(n),
        "--model-spec",
        str(args.model_spec),
        "--result",
        str(result_path),
    ]
    if args.smoke:
        argv.append("--smoke")
    started = time.perf_counter()
    timed_out = False
    code: int | None
    with (
        (out_dir / f"cell_{key}.stdout.log").open("w", encoding="utf-8") as so,
        (out_dir / f"cell_{key}.stderr.log").open("w", encoding="utf-8") as se,
    ):
        proc = subprocess.Popen(argv, cwd=ROOT, stdout=so, stderr=se)
        try:
            code = proc.wait(timeout=args.child_timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            proc.wait()
            code = None
    rec: dict[str, Any] = {}
    if result_path.is_file():
        try:
            rec = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            rec = {}
    if chat:
        rec.update(device=device, template=template, prompt_id=n, n_tokens=None)
    else:
        rec.update(device=device, template=template, n_tokens=n)
    rec["timed_out"] = timed_out
    rec["child_exit_code"] = code
    rec["child_exit_hex"] = None if code is None else f"0x{code & 0xFFFFFFFF:08X}"
    rec["child_wall_s"] = time.perf_counter() - started
    rec["command"] = argv
    _write(result_path, rec)
    return rec


def run_parent(args: argparse.Namespace) -> int:
    started = datetime.now(UTC)
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
    f1 = args.prompt_set == "f1"
    if f1 and Path(args.model_spec).resolve() == DEFAULT_MODEL_SPEC.resolve():
        print("REFUSED -- f1 runs on another IR; pass --model-spec (the int4 default is the basis)")
        return 1
    ir = ir_record(Path(args.model_spec))
    refusal = ir_refusal(ir)
    if refusal and not args.smoke:
        print(f"REFUSED -- {refusal}")
        return 1
    run_id = str(uuid.uuid4())
    chat = args.prompt_set in CHAT_SETS
    prefix = {"filler": "natstop_", "chat": "natstop_b_", "f1": "natstop_f1_"}[args.prompt_set]
    out_dir = Path(args.out) / f"{prefix}{run_id}"
    out_dir.mkdir(parents=True, exist_ok=False)
    diagnostic = {"filler": DIAGNOSTIC, "chat": "NPU-NATSTOP-B", "f1": "NPU-FORMAT-F1"}
    plan: dict[str, Any] = {
        "diagnostic": diagnostic[args.prompt_set],
        "run_id": run_id,
        "prompt_set": args.prompt_set,
        "measurement": False,
        "smoke": bool(args.smoke),
        "host": socket.gethostname(),
        "utc_start": started.isoformat(),
        "git_head": head,
        "git_status_short": status_short,
        "versions": {} if args.smoke else live_versions(),
        "watchdog": watchdog,
        "model_spec": str(args.model_spec),
        "model": ir,
        "devices": list(DEVICES),
        "templates": list(TEMPLATES),
        "lengths": [] if chat else list(LENGTHS),
        "cell_order": [cell_key(*c) for c in cell_order(args.prompt_set)],
        "npu_load_props": npu_load_props(NPU_MAX_PROMPT_LEN, PREFILL_CHUNK_SIZE),
        "max_new_tokens": MAX_NEW_TOKENS,
        "min_new_tokens": None,
        "do_sample": False,
        "generate_call_form": "list",
        "prompt_builder": (
            "render_user(tokenizer, CHAT_PROMPTS[id])"
            if chat
            else "rendered_exact_prompt(tokenizer, n, unit=delta_n filler, salt=npu)"
        ),
        "match_ids": MATCH_IDS,
        "child_timeout_s": args.child_timeout,
    }
    if chat:
        plan["chat_prompts"] = dict(CHAT_PROMPTS)
        plan["validity"] = {
            "min_real_tokens": VALID_MIN_REAL_TOKENS,
            "repeat_max": VALID_REPEAT_MAX,
        }
    if f1:
        plan["content_check"] = {
            "chat1_keyword": CHAT1_KEYWORD,
            "tip_line": TIP_LINE.pattern,
            "tip_min_words": TIP_MIN_WORDS,
            "tip_min_lines": TIP_MIN_LINES,
        }
    _write(out_dir / "plan.json", plan)
    quant = ir.get("ir_quantization") or {}
    print("IR_QUANT " + json.dumps({"summary": quant.get("summary"), "error": quant.get("error")}))
    cells: dict[str, Any] = {}
    summary: dict[str, Any] = {**plan, "cells": cells, "status": "running"}
    for device, template, n in cell_order(args.prompt_set):
        rec = run_cell(args, device, template, n, out_dir)
        rec["derived"] = derived_fields(rec)
        cells[cell_key(device, template, n)] = rec
        _write(out_dir / "summary.json", summary)
    if chat:
        for device, template, n in cell_order(args.prompt_set):
            cell = cells[cell_key(device, template, n)]
            reference = cells.get(cell_key("GPU", template, n))
            cell["derived"]["valid"] = valid(cell, reference)
            if f1:
                cell["derived"]["content_ok"] = content_ok(n, cell.get("text"))
                cell["derived"]["passes"] = passes(cell, reference)
    if f1:
        verdict = classify_format(cells)
        summary["scope_verdict"] = classify_scope(cells)
    else:
        verdict = classify_scope(cells) if chat else classify(cells)
    summary["verdict"] = verdict
    summary["status"] = "complete"
    summary["ended_utc"] = datetime.now(UTC).isoformat()
    _write(out_dir / "summary.json", summary)
    print(f"{verdict_tag(args.prompt_set)} {verdict} {out_dir}")
    return 0


def verdict_tag(prompt_set: str) -> str:
    return {"filler": "NATSTOP_VERDICT", "chat": "NATSTOP_B_VERDICT", "f1": "NATSTOP_F1_VERDICT"}[
        prompt_set
    ]


def classify_file(path: Path) -> int:
    """Re-read a finished summary.json and print its verdict."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    prompt_set = doc.get("prompt_set") or "filler"
    cells = doc.get("cells") or {}
    if prompt_set == "f1":
        verdict = classify_format(cells)
    elif prompt_set == "chat":
        verdict = classify_scope(cells)
    else:
        verdict = classify(cells)
    print(f"recorded {doc.get('verdict')}")
    print(f"{verdict_tag(prompt_set)} {verdict} {Path(path).parent}")
    return 0 if doc.get("verdict") == verdict else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model-spec", type=Path, default=DEFAULT_MODEL_SPEC)
    parser.add_argument("--watchdog-log", default=DEFAULT_WATCHDOG_LOG)
    parser.add_argument("--child-timeout", type=int, default=CHILD_TIMEOUT_S)
    parser.add_argument("--classify", type=Path, help="re-read a summary.json; no run")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--device", choices=DEVICES)
    parser.add_argument("--template", choices=TEMPLATES)
    parser.add_argument("--n-tokens", type=int, choices=LENGTHS)
    parser.add_argument(
        "--prompt-set",
        choices=PROMPT_SETS,
        default="filler",
        help=(
            "filler: the 16-cell NATSTOP run (default); chat: NPU-NATSTOP-B, 8 cells; "
            "f1: the export-format test on --model-spec, 8 cells"
        ),
    )
    parser.add_argument("--prompt-id", choices=tuple(CHAT_PROMPTS))
    parser.add_argument("--result", type=Path)
    args = parser.parse_args(argv)
    if args.classify is not None:
        return classify_file(args.classify)
    if args.child:
        if None in (args.device, args.template, args.result) or (
            args.n_tokens is None and args.prompt_id is None
        ):
            raise SystemExit(
                "REFUSED -- child needs --device --template --result and --n-tokens or --prompt-id"
            )
        return run_child(args)
    return run_parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
