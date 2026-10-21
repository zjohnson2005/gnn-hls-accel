"""P11-HANG-REGIME variant inputs (Task BA). Definitions fixed in
docs/amendments/DEMO2_PILOT_P11_HANG_REGIME_2026-10-20.md ("Cells").

Mac only, no model. Built for both possible stalling steps of entry 123 turn 0
(S = 0 and S = 1), because S is known only after phase L; the window script
picks the set by L's result. Every variant keeps the real prompt of step S
outside the replaced body:
  S = 1: the body of the largest tool response (get_stock_info, 31,705 chars,
         two 2,000-value float lists); prefix and suffix kept byte for byte.
  S = 0: the text between the "<|im_start|>system\\n" header and the final
         "<|im_end|>\\n<|im_start|>assistant" (the whole rendered prompt body,
         since N = prompt tokens at S = 0).
N_body = HF tokens of the real body. Targets are measured on the body alone
with the pinned HF tokenizer, accepted within +-0.5%.

Cells (file names):
  M1..M3   other real BFCL content: the 3 multi_turn_long_context entries (file
           order, excluding 123) with the largest single gold-path tool result;
           each one's result repeated and trimmed at a token boundary.
  M4       random tokens: uniform ids from the base vocabulary minus special
           ids, seed 20261020, decoded, re-tokenized, trimmed.
  M5       random floats in 123's format: same JSON keys and scalars; each float
           list replaced by uniform [200, 250] values with 2 decimals (seed
           20261020), list lengths scaled to hit N.
  S_real_f / S_rand_f  for f in 0.5 .. 1.5: real = 123's own float lists
           truncated (f < 1) or extended by repeating their own values (f > 1);
           rand = the M4 generator at f x N.
  M6 (real input, --only-step S) uses inputs_e123_t0.json itself.

Run: python tools/repro_hang123.py variants --tokenizer <dir> --bfcl-unpacked <dir> \\
         --inputs derived/repro_hang123/inputs_e123_t0.json --out derived/repro_hang123/variants
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any

SEED = 20261020
FRACTIONS = (0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5)
TOL = 0.005
MODEL_MAX = 40_960
EXCLUDE_ENTRY = "multi_turn_long_context_123"
TR = re.compile(r"<tool_response>\n(.*?)\n</tool_response>", re.S)
SYS_HDR = "<|im_start|>system\n"
ASSIST = "<|im_end|>\n<|im_start|>assistant"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def body_span(prompt: str, step: int) -> tuple[int, int]:
    if step >= 1:
        spans = [(m.start(1), m.end(1)) for m in TR.finditer(prompt)]
        if not spans:
            raise ValueError("no tool response in the step prompt")
        return max(spans, key=lambda s: s[1] - s[0])
    start = prompt.index(SYS_HDR) + len(SYS_HDR)
    return start, prompt.rindex(ASSIST)


class Fitter:
    def __init__(self, tok: Any) -> None:
        self.tok = tok

    def n(self, text: str) -> int:
        return len(self.tok(text, add_special_tokens=False)["input_ids"])

    def ok(self, got: int, target: int) -> bool:
        return abs(got - target) <= TOL * target

    def trim(self, text: str, target: int) -> str:
        """Token-boundary prefix of ``text`` with ~target tokens."""
        ids = self.tok(text, add_special_tokens=False)["input_ids"]
        if len(ids) < target:
            raise ValueError("text shorter than target")
        k = target
        for _ in range(40):
            out = self.tok.decode(ids[:k])
            got = self.n(out)
            if self.ok(got, target):
                return str(out)
            k += target - got
        raise ValueError("trim did not converge")

    def by_scale(self, make: Callable[[float], str], target: int, x0: float) -> str:
        lo, hi = x0 * 0.5, x0 * 2.0
        for _ in range(60):
            mid = (lo + hi) / 2
            text = make(mid)
            got = self.n(text)
            if self.ok(got, target):
                return text
            if got < target:
                lo = mid
            else:
                hi = mid
        raise ValueError("scale search did not converge")


def _scaled_lists(
    obj: dict[str, Any], x: float, values: Callable[[list[float], int], list[float]]
) -> str:
    out: dict[str, Any] = {}
    for k, v in obj.items():
        if isinstance(v, list):
            n = max(1, round(len(v) * x))
            out[k] = values(v, n)
        else:
            out[k] = v
    return json.dumps(out)


def _maker(
    obj: dict[str, Any], values: Callable[[list[float], int], list[float]]
) -> Callable[[float], str]:
    def make(x: float) -> str:
        return _scaled_lists(obj, x, values)

    return make


def _cyclic(v: list[float], n: int) -> list[float]:
    return [v[i % len(v)] for i in range(n)]


def _random_floats(v: list[float], n: int) -> list[float]:
    rng = random.Random(SEED + len(v))
    return [round(rng.uniform(200.0, 250.0), 2) for _ in range(n)]


def _random_token_stream(tok: Any, n_ids: int) -> list[int]:
    special = set(tok.all_special_ids)
    pool = [i for i in range(int(tok.vocab_size)) if i not in special]
    rng = random.Random(SEED)
    return [rng.choice(pool) for _ in range(n_ids)]


def _random_text(fit: Fitter, stream: list[int], target: int) -> str:
    lo, hi = 1, len(stream)
    for _ in range(60):
        k = (lo + hi) // 2
        text = str(fit.tok.decode(stream[:k]))
        got = fit.n(text)
        if fit.ok(got, target):
            return text
        if got < target:
            lo = k + 1
        else:
            hi = k - 1
    raise ValueError("random text did not converge")


def largest_results(tok: Any, bfcl_unpacked: Path) -> list[dict[str, Any]]:
    """Largest single gold-path tool result per long_context entry (file order)."""
    if "openvino_genai" not in sys.modules:
        sys.modules["openvino_genai"] = types.ModuleType("openvino_genai")
    import tools.bfcl_feasibility_probe as probe
    import tools.h1_context_sizing as hs

    data = bfcl_unpacked / "bfcl_eval" / "data"
    probe.BFCL_UNPACKED = bfcl_unpacked
    entries = hs.load_entries("multi_turn_long_context", data)
    rows = []
    for idx, entry in enumerate(entries):
        if entry["id"] == EXCLUDE_ENTRY:
            continue
        pipe = hs.GoldPipe()
        session = probe.MultiTurnAgentSession(pipe=pipe, tokenizer=tok, cfg=None)
        session.begin(entry)
        seen: list[tuple[str, str]] = []
        execute = session._execute_multi_turn_func_call

        def observed(
            decoded: list[str], *a: Any, _x: Any = execute, _s: Any = seen, **k: Any
        ) -> Any:
            results, inst = _x(decoded, *a, **k)
            for call, r in zip(decoded, results, strict=False):
                _s.append((call.split("(", 1)[0], str(r)))
            return results, inst

        session._execute_multi_turn_func_call = observed
        try:
            for t, gold in enumerate(entry["reference"]):
                calls = [str(c) for c in gold]
                pipe.queue = (
                    [probe.encode_execute_calls_as_qwen_tool_text(calls), hs.CLOSING_TEXT]
                    if calls
                    else [hs.CLOSING_TEXT]
                )
                session.run_user_turn(t)
                if session.force_quit:
                    break
        finally:
            session._finished = True
        if not seen:
            continue
        call, text = max(seen, key=lambda s: len(s[1]))
        rows.append({"file_index": idx, "entry_id": entry["id"], "call": call, "text": text})
    for r in rows:
        r["tokens"] = len(tok(r["text"], add_special_tokens=False)["input_ids"])
    rows.sort(key=lambda r: (-r["tokens"], r["file_index"]))
    return rows


def build_variants(
    tokenizer_dir: Path, bfcl_unpacked: Path, inputs: Path, out: Path
) -> dict[str, Any]:
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(str(tokenizer_dir))
    fit = Fitter(tok)
    base = json.loads(inputs.read_text(encoding="utf-8"))
    base_sha = hashlib.sha256(inputs.read_bytes()).hexdigest()
    others = largest_results(tok, bfcl_unpacked)[:3]
    out.mkdir(parents=True, exist_ok=True)
    index: dict[str, Any] = {
        "kind": "repro_hang123_variants_index",
        "base_inputs_sha256": base_sha,
        "seed": SEED,
        "tolerance": TOL,
        "model_max_position": MODEL_MAX,
        "m1_m3_sources": [{k: v for k, v in r.items() if k != "text"} for r in others],
        "sets": {},
    }
    stream = _random_token_stream(tok, 200_000)
    for st in base["steps"]:
        s = int(st["step"])
        prompt = str(st["prompt"])
        a, b = body_span(prompt, s)
        body = prompt[a:b]
        n_body = fit.n(body)
        cells: dict[str, str] = {}
        for i, r in enumerate(others, 1):
            reps = r["text"] * (n_body // max(1, r["tokens"]) + 2)
            cells[f"M{i}"] = fit.trim(reps, n_body)
        cells["M4"] = _random_text(fit, stream, n_body)
        if s >= 1:
            obj = json.loads(body)
            cells["M5"] = fit.by_scale(_maker(obj, _random_floats), n_body, 1.0)
        for f in FRACTIONS:
            tgt = round(f * n_body)
            tag = f"{f:.2f}".replace(".", "p")
            if s >= 1:
                obj = json.loads(body)
                cells[f"S_real_{tag}"] = (
                    body if f == 1.0 else fit.by_scale(_maker(obj, _cyclic), tgt, f)
                )
            else:
                # Truncated (f < 1) or extended by repeating its own text (f > 1).
                cells[f"S_real_{tag}"] = body if f == 1.0 else fit.trim(body * 2, tgt)
            cells[f"S_rand_{tag}"] = _random_text(fit, stream, tgt)
        rows = {}
        sdir = out / f"S{s}"
        sdir.mkdir(parents=True, exist_ok=True)
        for name, new_body in cells.items():
            p = prompt[:a] + new_body + prompt[b:]
            n_prompt = len(tok(p)["input_ids"])
            doc: dict[str, Any] = {
                "kind": "repro_hang123_variant",
                "cell": name,
                "stall_step": s,
                "base_inputs_sha256": base_sha,
                "body_tokens_target": round(n_body * _frac(name)),
                "body_tokens_hf": fit.n(new_body),
                "steps": [
                    {
                        "step": s,
                        "prompt": p,
                        "prompt_chars": len(p),
                        "prompt_tokens_hf": n_prompt,
                        "prompt_sha256": sha(p),
                    }
                ],
                "exceeds_model_max": n_prompt + 512 > MODEL_MAX,
            }
            path = sdir / f"{name}.json"
            path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            rows[name] = {
                "file": f"S{s}/{name}.json",
                "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "prompt_sha256": doc["steps"][0]["prompt_sha256"],
                "prompt_tokens_hf": n_prompt,
                "body_tokens_hf": doc["body_tokens_hf"],
                "body_tokens_target": doc["body_tokens_target"],
                "exceeds_model_max": doc["exceeds_model_max"],
            }
        index["sets"][f"S{s}"] = {
            "n_body_real": n_body,
            "real_body_chars": len(body),
            "cells": rows,
        }
    (out / "INDEX.json").write_text(
        json.dumps(index, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    index["index_sha256"] = hashlib.sha256((out / "INDEX.json").read_bytes()).hexdigest()
    return index


def _frac(name: str) -> float:
    m = re.search(r"_(\d)p(\d+)$", name)
    return float(f"{m.group(1)}.{m.group(2)}") if m else 1.0


# --- Task BB (pilot P11-B): X2 random-token chains and the reconstructed X3r input ---

P11B_N = (32_768, 40_960, 49_152, 65_536, 87_392)
P11B_SUFFIX_TOKENS = 55
USER_HDR = "<|im_start|>user\n"
ASSIST_OPEN = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
SUFFIX_HDR = "<|im_end|>\n<|im_start|>user\n<tool_response>\n"
SUFFIX_TAIL = "\n</tool_response>" + ASSIST_OPEN
# DERIVED in Task BB part 1 (analysis/demo2_pilots/BB/): the step-0 call set on
# 8af10211's own path that reproduces its logged sizes (125 text tokens, step-1
# prompt 87,392 HF tokens with a 5-character price). The exact text was not
# recorded; this uses the gold price 667.92 (step-1 prompt 87,394 tokens).
X3R_STEP0_CALLS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("get_account_info", {}),
    ("get_stock_info", {"symbol": "TSLA"}),
    ("get_transaction_history", {}),
    ("get_available_stocks", {"sector": "Technology"}),
    ("place_order", {"order_type": "Buy", "symbol": "TSLA", "price": 667.92, "amount": 150}),
)


def x3r_step0_text() -> str:
    return "\n".join(
        "<tool_call>\n" + json.dumps({"name": n, "arguments": a}) + "\n</tool_call>"
        for n, a in X3R_STEP0_CALLS
    )


def _fit_exact(fit: Fitter, stream: list[int], target: int, wrap: Callable[[str], str]) -> str:
    """Wrapped random text whose total HF token count is target (+-1)."""
    lo, hi = 1, len(stream)
    best = ""
    for _ in range(60):
        k = (lo + hi) // 2
        text = wrap(str(fit.tok.decode(stream[:k])))
        got = len(fit.tok(text)["input_ids"])
        if abs(got - target) <= 1:
            return text
        best = text
        if got < target:
            lo = k + 1
        else:
            hi = k - 1
    raise ValueError(f"exact fit did not converge (last {len(best)} chars)")


def _reconstructed_step1(tok: Any, bfcl_unpacked: Path) -> str:
    if "openvino_genai" not in sys.modules:
        sys.modules["openvino_genai"] = types.ModuleType("openvino_genai")
    import tools.bfcl_feasibility_probe as probe
    import tools.h1_context_sizing as hs

    probe.BFCL_UNPACKED = bfcl_unpacked
    entry = next(
        e
        for e in hs.load_entries("multi_turn_long_context", bfcl_unpacked / "bfcl_eval" / "data")
        if e["id"] == EXCLUDE_ENTRY
    )
    prompts: list[str] = []

    class CapturePipe(hs.GoldPipe):  # type: ignore[misc]
        def generate(self, ps: list[str], cfg: Any) -> Any:
            prompts.append(str(ps[0]))
            return super().generate(ps, cfg)

    pipe = CapturePipe()
    session = probe.MultiTurnAgentSession(pipe=pipe, tokenizer=tok, cfg=None)
    session.begin(entry)
    pipe.queue = [x3r_step0_text(), hs.CLOSING_TEXT]
    session.run_user_turn(0)
    session._finished = True
    return prompts[1]


def build_p11b(tokenizer_dir: Path, bfcl_unpacked: Path, out: Path) -> dict[str, Any]:
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(str(tokenizer_dir))
    fit = Fitter(tok)
    stream = _random_token_stream(tok, 200_000)
    out.mkdir(parents=True, exist_ok=True)
    # Suffix filler comes from the end of the stream, prompts from its start.
    suffix = _fit_exact(
        fit,
        stream[150_000:],
        P11B_SUFFIX_TOKENS,
        lambda body: SUFFIX_HDR + body + SUFFIX_TAIL,
    )
    suffix_tokens = len(tok(suffix, add_special_tokens=False)["input_ids"])
    chain = {"suffix": suffix, "suffix_sha256": sha(suffix), "suffix_tokens_hf": suffix_tokens}
    index: dict[str, Any] = {
        "kind": "repro_hang123_p11b_index",
        "seed": SEED,
        "model_max_position": MODEL_MAX,
        "chain": {k: v for k, v in chain.items() if k != "suffix"},
        "cells": {},
    }

    def write(name: str, prompt: str, note: str) -> None:
        n = len(tok(prompt)["input_ids"])
        doc = {
            "kind": "repro_hang123_p11b_input",
            "cell": name,
            "note": note,
            "chain": chain,
            "steps": [
                {
                    "step": 0,
                    "prompt": prompt,
                    "prompt_chars": len(prompt),
                    "prompt_tokens_hf": n,
                    "prompt_sha256": sha(prompt),
                }
            ],
        }
        path = out / f"{name}.json"
        path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        index["cells"][name] = {
            "file": path.name,
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "prompt_sha256": sha(prompt),
            "prompt_tokens_hf": n,
            "exceeds_model_max": n > MODEL_MAX,
        }

    for n_target in P11B_N:
        prompt = _fit_exact(fit, stream, n_target, lambda b: USER_HDR + b + ASSIST_OPEN)
        write(f"X2_N{n_target}", prompt, "random tokens (seed 20261020) in one user turn")
    write(
        "X3r_reconstructed",
        _reconstructed_step1(tok, bfcl_unpacked),
        "DERIVED: entry 123 turn-0 step-1 prompt rebuilt from the call set that reproduces "
        "8af10211's logged sizes; exact model text not recorded (gold price 667.92)",
    )
    (out / "INDEX.json").write_text(
        json.dumps(index, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    index["index_sha256"] = hashlib.sha256((out / "INDEX.json").read_bytes()).hexdigest()
    return index
