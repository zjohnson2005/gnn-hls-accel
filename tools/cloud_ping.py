"""One minimal Anthropic request through the H1 runner's own cloud client.

The client and model id come from tools/run_h1_hybrid.py _make_live_cloud
(the same construction the detached H1 worker uses), and the request kwargs
from tools/bfcl_feasibility_probe.py _anthropic_create_kwargs (so the
temperature rule is the same). The request is max_tokens 8 with a few input
tokens; its cost is computed at the runner's price constants and recorded.

Writes one JSON record (--out) and prints it. Never records the API key or
request headers; error text is redacted. Exit 0 when the request returns,
1 when it fails, 2 when it cannot start (no key, no SDK). Opens no
preregistration.

  .venv-seam\\Scripts\\python.exe tools\\cloud_ping.py --out <dir>\\cloud_ping.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PING_MAX_TOKENS = 8
PING_TEXT = "Reply with: ok"
COST_CEILING_USD = 0.001
PROXY_ENV = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")


def proxy_env_present() -> dict[str, bool]:
    """Presence only (either case); proxy values are not recorded."""
    return {name: bool(os.environ.get(name) or os.environ.get(name.lower())) for name in PROXY_ENV}


def sdk_version() -> str | None:
    try:
        import anthropic
    except ImportError:
        return None
    return str(getattr(anthropic, "__version__", None))


def _default_backend(cloud_model: str | None) -> Any:
    from tools.run_h1_hybrid import _make_live_cloud

    return _make_live_cloud(cloud_model)


def ping(
    *,
    cloud_model: str | None = None,
    backend_factory: Callable[[str | None], Any] = _default_backend,
) -> dict[str, Any]:
    from tools.bfcl_feasibility_probe import (
        CLOUD_USD_PER_MTOK_IN,
        CLOUD_USD_PER_MTOK_OUT,
        _anthropic_create_kwargs,
    )
    from tools.h1_cloud_accounting import exception_fields, redact_secrets, usage_field

    record: dict[str, Any] = {
        "tool": "cloud_ping",
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "api_key_present": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "anthropic_sdk_version": sdk_version(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "platform_id": os.environ.get("SEAM_PLATFORM_ID") or None,
        "proxy_env_present": proxy_env_present(),
        "client_construction": "tools.run_h1_hybrid._make_live_cloud",
        "request_kwargs": "tools.bfcl_feasibility_probe._anthropic_create_kwargs",
        "max_tokens": PING_MAX_TOKENS,
        "model": None,
        "ok": False,
        "http_status": None,
        "error_class": None,
        "error_message": None,
        "request_id": None,
        "latency_s": None,
        "input_tokens": None,
        "output_tokens": None,
        "usd": 0.0,
        "usd_ceiling": COST_CEILING_USD,
        "price_per_mtok": {"in": CLOUD_USD_PER_MTOK_IN, "out": CLOUD_USD_PER_MTOK_OUT},
    }
    try:
        backend = backend_factory(cloud_model)
    except SystemExit as exc:
        record.update(error_class="SetupRefused", error_message=redact_secrets(str(exc)))
        record["exit_code"] = 2
        return record
    record["model"] = backend.cloud_model
    kwargs = _anthropic_create_kwargs(
        model=backend.cloud_model,
        max_tokens=PING_MAX_TOKENS,
        messages=[{"role": "user", "content": [{"type": "text", "text": PING_TEXT}]}],
        tools=[],
        caching_policy="none",
    )
    if not kwargs.get("tools"):
        kwargs.pop("tools", None)
    record["request_keys"] = sorted(kwargs)
    t0 = time.perf_counter()
    try:
        response = backend.client.messages.create(**kwargs)
    except Exception as exc:
        record["latency_s"] = time.perf_counter() - t0
        record.update(exception_fields(exc))
        record["exit_code"] = 1
        return record
    record["latency_s"] = time.perf_counter() - t0
    usage = getattr(response, "usage", None)
    tin = usage_field(usage, "input_tokens")
    tout = usage_field(usage, "output_tokens")
    record.update(
        ok=True,
        http_status=200,
        request_id=getattr(response, "_request_id", None)
        if isinstance(getattr(response, "_request_id", None), str)
        else None,
        input_tokens=tin,
        output_tokens=tout,
        stop_reason=getattr(response, "stop_reason", None),
        response_model=getattr(response, "model", None),
    )
    record["usd"] = (
        int(tin or 0) * CLOUD_USD_PER_MTOK_IN + int(tout or 0) * CLOUD_USD_PER_MTOK_OUT
    ) / 1e6
    record["usd_under_ceiling"] = record["usd"] < COST_CEILING_USD
    record["exit_code"] = 0
    return record


def main(
    argv: list[str] | None = None,
    *,
    backend_factory: Callable[[str | None], Any] = _default_backend,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None, help="Write the record here (JSON).")
    parser.add_argument(
        "--cloud-model",
        default=None,
        help="Same meaning as run_h1_hybrid --cloud-model; default is the runner's default.",
    )
    args = parser.parse_args(argv)
    record = ping(cloud_model=args.cloud_model, backend_factory=backend_factory)
    text = json.dumps(record, indent=2, sort_keys=True, default=str) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    status = "CLOUD_PING_OK" if record["exit_code"] == 0 else "CLOUD_PING_FAILED"
    print(
        f"{status} model={record['model']} http_status={record['http_status']} "
        f"error_class={record['error_class']} latency_s={record['latency_s']} usd={record['usd']}"
    )
    return int(record["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
