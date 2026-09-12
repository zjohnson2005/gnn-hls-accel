"""Item A2: empirically determine whether llama.cpp's server retains KV state
across independent HTTP requests.

Discriminator (from tools/server/server-context.cpp:501-503):
  timings.cache_n  = slot.n_prompt_tokens_cache     -> tokens REUSED, not recomputed
  timings.prompt_n = slot.n_prompt_tokens_processed -> tokens actually PREFILLED

Sequence per server configuration:
  R1  prompt P                      cold baseline
  R2  prompt P + suffix             persists => prompt_n ~ |suffix|
  R3  unrelated prompt U            occupies / evicts the slot
  R4  prompt P + suffix (again)     does the state survive an intervening request?

Run outside the sandbox. Requires llama-server.exe and a GGUF; paths via CLI.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis" / "characterization"


def build_prompt(tag: str, n_lines: int) -> str:
    """Deterministic filler. Distinct `tag` guarantees a distinct token prefix."""
    lines = [f"{tag} line {i:05d}: the quick brown fox jumps over the lazy dog." for i in range(n_lines)]
    return "\n".join(lines)


def wait_health(port: int, timeout_s: float = 180.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(0.5)
    return False


def completion(port: int, prompt: str, **extra: Any) -> dict[str, Any]:
    body = {"prompt": prompt, "n_predict": 1, "temperature": 0.0, "cache_prompt": True}
    body.update(extra)
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/completion",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read().decode("utf-8"))


def run_config(
    server: Path,
    model: Path,
    port: int,
    label: str,
    extra_args: list[str],
    n_lines: int,
) -> dict[str, Any]:
    cmd = [
        str(server), "-m", str(model),
        "--host", "127.0.0.1", "--port", str(port),
        "-c", "16384", "-t", "8", "--no-webui",
        *extra_args,
    ]
    print(f"\n=== CONFIG {label} ===")
    print("  " + " ".join(cmd[1:]))
    log_path = OUT / f"_server_{label}.log"
    OUT.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        try:
            if not wait_health(port):
                proc.terminate()
                return {"label": label, "error": "server did not become healthy", "args": extra_args}

            p = build_prompt("ALPHA", n_lines)
            p_plus = p + "\nALPHA suffix: summarize the above in one word."
            u = build_prompt("OMEGA", n_lines)

            steps = [
                ("R1_cold_P", p),
                ("R2_P_plus_suffix", p_plus),
                ("R3_unrelated_U", u),
                ("R4_P_plus_suffix_again", p_plus),
            ]
            rows = []
            for name, text in steps:
                r = completion(port, text)
                t = r["timings"]
                cache_n = int(t.get("cache_n", 0))
                prompt_n = int(t["prompt_n"])
                rows.append({
                    "step": name,
                    "total_prompt_tokens": cache_n + prompt_n,
                    "cache_n_reused": cache_n,
                    "prompt_n_processed": prompt_n,
                    "prompt_ms": round(float(t["prompt_ms"]), 2),
                    "prompt_per_second": round(float(t.get("prompt_per_second", 0.0)), 2),
                    "reuse_fraction": round(cache_n / max(1, cache_n + prompt_n), 4),
                })
                print(
                    f"  {name:<26} total={rows[-1]['total_prompt_tokens']:>6} "
                    f"reused={cache_n:>6} prefilled={prompt_n:>6} "
                    f"prompt_ms={rows[-1]['prompt_ms']:>9.2f}"
                )
            return {"label": label, "args": extra_args, "steps": rows}
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True, type=Path)
    ap.add_argument("--model", required=True, type=Path)
    ap.add_argument("--lines", type=int, default=260, help="filler lines (~15 tok each)")
    ap.add_argument("--port", type=int, default=18234)
    args = ap.parse_args()

    # The server overrides n_parallel to 4 when left on auto (tools/server/server.cpp:152-154),
    # so "default" has FOUR slots and an unrelated request does not evict anything.
    # parallel1_* force genuine slot contention, which is the only way to test
    # whether slot reassignment destroys retained state.
    configs = [
        ("default", []),
        ("cache_ram_off", ["--cache-ram", "0"]),
        ("parallel2", ["--parallel", "2"]),
        ("parallel1_cacheram_on", ["--parallel", "1"]),
        ("parallel1_cacheram_off", ["--parallel", "1", "--cache-ram", "0"]),
    ]
    results = []
    for i, (label, extra) in enumerate(configs):
        results.append(
            run_config(args.server, args.model, args.port + i, label, extra, args.lines)
        )

    OUT.mkdir(parents=True, exist_ok=True)
    meta = {
        "server_binary": str(args.server),
        "model": str(args.model),
        "filler_lines": args.lines,
        "results": results,
    }
    (OUT / "kv_persistence_raw.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\nWrote {OUT / 'kv_persistence_raw.json'}")


if __name__ == "__main__":
    sys.exit(main())
