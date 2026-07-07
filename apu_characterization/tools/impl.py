"""Local tool implementations with real CPU work."""

from __future__ import annotations

import contextvars
import hashlib
import json
import math
import random
import re
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote

import numpy as np

from ..harness.mock_api import RETRIEVE_REMOTE_MEDIAN_S, SEARCH_REMOTE_MEDIAN_S, sync_mock_remote_call
from ..instr import timed
from ..taxonomy import Category

LocalityMode = Literal["local", "remote"]

LOCALITY_LOCAL: LocalityMode = "local"
LOCALITY_REMOTE: LocalityMode = "remote"

_tool_locality: contextvars.ContextVar[dict[str, LocalityMode]] = contextvars.ContextVar(
    "apu_tool_locality", default={}
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
CORPUS_PATH = FIXTURES_DIR / "corpus.txt"
VECTORS_PATH = FIXTURES_DIR / "vectors.npy"

_corpus_cache: str | None = None
_vectors_mmap: np.ndarray | None = None


def _load_corpus() -> str:
    global _corpus_cache
    if _corpus_cache is None:
        from ..fixtures.generate_fixtures import ensure_fixtures

        ensure_fixtures()
        _corpus_cache = CORPUS_PATH.read_text(encoding="utf-8", errors="replace")
    return _corpus_cache


def _load_vectors() -> np.ndarray:
    global _vectors_mmap
    if _vectors_mmap is None:
        from ..fixtures.generate_fixtures import ensure_fixtures

        ensure_fixtures()
        _vectors_mmap = np.load(VECTORS_PATH, mmap_mode="r")
    return _vectors_mmap


def tool_search(query: str, session_id: str, rng: random.Random, top_k: int = 5) -> dict[str, Any]:
    """Regex scan: exact phrase first, then word alternation over the corpus."""
    corpus = _load_corpus()
    words = [re.escape(w) for w in query.split()[:6] if w]
    phrase_pat = re.compile(re.escape(query[:64]), re.IGNORECASE) if query else None
    alt_pat = re.compile(r"\b(" + "|".join(words) + r")\b", re.IGNORECASE) if words else None

    hits: list[tuple[int, str]] = []
    with timed(Category.TOOL_COMPUTE, session_id, bytes_in=len(query)):
        for pattern in (p for p in (phrase_pat, alt_pat) if p is not None):
            for m in pattern.finditer(corpus):
                start = max(0, m.start() - 120)
                end = min(len(corpus), m.end() + 120)
                hits.append((m.start(), corpus[start:end]))
                if len(hits) >= top_k * 20:
                    break
            if len(hits) >= top_k:
                break
        hits.sort(key=lambda x: x[0])
        snippets = [h[1] for h in hits[:top_k]]
    return {"query": query, "snippets": snippets, "matches_scanned": len(hits)}


def _seeded_snippets(query: str, top_k: int) -> list[str]:
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
    base = int(digest[:8], 16)
    snippets: list[str] = []
    for i in range(top_k):
        inner = random.Random(base + i * 9973)
        snippets.append(
            f"... {query[:48]} ... excerpt {inner.randint(1000, 9999)} ..."
        )
    return snippets


def tool_search_remote(
    query: str, session_id: str, rng: random.Random, top_k: int = 5
) -> dict[str, Any]:
    """Mock hosted search: HTTP envelope + I/O wait, no local corpus scan."""
    endpoint = f"GET /v1/search?q={quote(query[:128])}"
    sync_mock_remote_call(
        endpoint,
        rng,
        session_id,
        median_s=SEARCH_REMOTE_MEDIAN_S,
    )
    snippets = _seeded_snippets(query, top_k)
    return {
        "query": query,
        "snippets": snippets,
        "matches_scanned": len(snippets),
        "locality": "remote",
    }


def tool_code_exec(query: str, session_id: str, rng: random.Random) -> dict[str, Any]:
    """Execute Python that assigns `result`. Non-code input runs a fallback loop."""
    if "result" in query and any(k in query for k in ("=", "for ", "def ", "import ")):
        code = query
        fallback = False
    else:
        n = rng.randint(500, 5000)
        code = f"""
total = 0
for i in range({n}):
    total += (i * i) % 997
result = total
"""
        fallback = True
    loc: dict[str, Any] = {}
    safe_builtins = {
        "range": range, "sum": sum, "enumerate": enumerate, "int": int,
        "max": max, "min": min, "len": len, "sorted": sorted, "abs": abs,
    }
    with timed(Category.TOOL_COMPUTE, session_id, bytes_in=len(code)):
        try:
            exec(code, {"__builtins__": safe_builtins}, loc)  # noqa: S102
        except Exception as exc:
            return {
                "stdout": "",
                "exit_code": 1,
                "error": str(exc),
                "code_bytes": len(code),
                "query": query,
            }
    return {
        "stdout": str(loc.get("result", 0)),
        "exit_code": 0,
        "code_bytes": len(code),
        "fallback": fallback,
        "query": query,
    }


def _embed_query(query: str) -> np.ndarray:
    """Deterministic pseudo-embedding: hash of the query text seeds the vector,
    so the same question always retrieves the same chunks."""
    import hashlib

    digest = hashlib.sha256(query.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "little")
    gen = np.random.default_rng(seed)
    q = gen.standard_normal(384).astype(np.float32)
    q /= max(float(np.linalg.norm(q)), 1e-6)
    return q


def tool_retrieve(query: str, session_id: str, rng: random.Random, top_k: int = 5) -> dict[str, Any]:
    mat = _load_vectors()
    q = _embed_query(query)

    with timed(Category.TOOL_COMPUTE, session_id, bytes_in=len(query)):
        # Full scan over the 100k x 384 matrix: genuine memory-bound compute.
        scores = mat @ q
        top = np.argpartition(scores, -top_k)[-top_k:]
        top = top[np.argsort(scores[top])[::-1]]
        chunks = [
            {"id": int(i), "score": float(scores[i]), "text": f"chunk_{int(i)}"}
            for i in top
        ]
    return {"query": query, "chunks": chunks}


def tool_retrieve_remote(
    query: str, session_id: str, rng: random.Random, top_k: int = 5
) -> dict[str, Any]:
    """Mock hosted vector index: HTTP envelope + I/O wait, no local matmul."""
    endpoint = f"POST /v1/retrieve body={quote(query[:128])}"
    sync_mock_remote_call(
        endpoint,
        rng,
        session_id,
        median_s=RETRIEVE_REMOTE_MEDIAN_S,
    )
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
    base = int(digest[:8], 16)
    chunks = [
        {
            "id": (base + i * 7919) % 100_000,
            "score": round(0.99 - i * 0.05, 4),
            "text": f"chunk_{(base + i * 7919) % 100_000}",
        }
        for i in range(top_k)
    ]
    return {"query": query, "chunks": chunks, "locality": "remote"}


_MATH_EXPR = re.compile(r"^[\d+\-*/().^ \t.eE]+$")


def _eval_arithmetic(expr: str) -> tuple[float | None, str, str | None]:
    """Try to evaluate expr as arithmetic. Returns (value, engine, error)."""
    cleaned = expr.strip()
    if not cleaned:
        return None, "none", "empty expression"

    candidates: list[str] = [cleaned]
    for m in re.finditer(r"[\d+\-*/().^ ]{3,}", cleaned):
        s = m.group().strip()
        if any(op in s for op in "+-*/") and _MATH_EXPR.match(s):
            candidates.append(s)

    seen: set[str] = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        if not _MATH_EXPR.match(cand):
            continue
        try:
            import sympy

            val = float(sympy.sympify(cand))
            return val, "sympy", None
        except Exception:
            pass
        try:
            allowed = {"sqrt": math.sqrt, "pi": math.pi, "e": math.e}
            val = float(eval(cand, {"__builtins__": {}}, allowed))  # noqa: S307
            return val, "eval", None
        except Exception:
            continue

    return None, "none", f"not a parseable arithmetic expression: {cleaned[:120]!r}"


def tool_calculator(query: str, session_id: str, rng: random.Random) -> dict[str, Any]:
    # Real agents often send natural language; return a structured error instead
    # of raising so the ReAct loop continues.
    expr = query.strip() or f"{rng.randint(2, 50)} + {rng.randint(2, 50)} * {rng.uniform(1, 3):.2f}"
    with timed(Category.TOOL_COMPUTE, session_id, bytes_in=len(expr)):
        val, engine, err = _eval_arithmetic(expr)
    out: dict[str, Any] = {"expression": expr, "engine": engine, "query": query}
    if err:
        out["error"] = err
        out["value"] = None
    else:
        out["value"] = val
    return out


TOOL_FNS = {
    "search": tool_search,
    "code_exec": tool_code_exec,
    "retrieve": tool_retrieve,
    "calculator": tool_calculator,
}

REMOTE_TOOL_FNS = {
    "search": tool_search_remote,
    "retrieve": tool_retrieve_remote,
}


def set_tool_locality(**overrides: LocalityMode) -> contextvars.Token:
    """Override locality for named tools in this context (local vs remote)."""
    current = dict(_tool_locality.get())
    current.update(overrides)
    return _tool_locality.set(current)


def reset_tool_locality(token: contextvars.Token) -> None:
    _tool_locality.reset(token)


def active_locality(name: str) -> LocalityMode:
    return _tool_locality.get().get(name, LOCALITY_LOCAL)


def resolve_tool_fn(name: str):
    if active_locality(name) == LOCALITY_REMOTE and name in REMOTE_TOOL_FNS:
        return REMOTE_TOOL_FNS[name]
    return TOOL_FNS[name]


def run_tool(name: str, query: str, session_id: str, rng: random.Random) -> dict[str, Any]:
    return resolve_tool_fn(name)(query, session_id, rng)
