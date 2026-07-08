"""Mock remote API call: HTTP_CLIENT envelope CPU around pure I/O wait.

Models what a real HTTP client costs the host CPU: building the request
(URL, headers, body encode) and parsing the response envelope. The network
round trip itself is an asyncio sleep, which costs zero thread CPU, so
AH-01 style tasks verify the I/O-wait exclusion end to end.
"""

from __future__ import annotations

import asyncio
import json
import math
import random
from typing import Any

from ..instr import timed
from ..taxonomy import Category

API_MEDIAN_S = 0.30
API_SIGMA = 0.40

# Remote search/retrieve round trips: same envelope model as mock API.
SEARCH_REMOTE_MEDIAN_S = 0.35
RETRIEVE_REMOTE_MEDIAN_S = 0.40


def sync_mock_remote_call(
    endpoint: str,
    rng: random.Random,
    session_id: str,
    *,
    latency_scale: float = 1.0,
    median_s: float = API_MEDIAN_S,
    sigma: float = API_SIGMA,
) -> dict[str, Any]:
    """Synchronous mock remote call for LangGraph sync tool nodes.

    Request build and response parse are tagged HTTP_CLIENT; the round trip
    is time.sleep (zero thread CPU), matching the async mock_api_call model.
    """
    import time

    with timed(Category.HTTP_CLIENT, session_id, bytes_out=len(endpoint)):
        request = {
            "method": endpoint.split(" ")[0] if " " in endpoint else "GET",
            "url": endpoint.split(" ")[-1],
            "headers": {
                "accept": "application/json",
                "user-agent": "apu-harness/1.0",
                "x-request-id": f"{rng.getrandbits(64):016x}",
                "authorization": "Bearer mock-token",
            },
        }
        raw_request = json.dumps(request)

    mu = math.log(max(median_s * latency_scale, 1e-6))
    with timed(Category.HTTP_CLIENT, session_id):
        time.sleep(rng.lognormvariate(mu, sigma))

    body = {
        "endpoint": request["url"],
        "status": 200,
        "data": {"value": rng.random() * 100, "unit": "mock", "ts": rng.getrandbits(32)},
    }
    raw_response = json.dumps(body)

    with timed(Category.HTTP_CLIENT, session_id, bytes_in=len(raw_response)):
        parsed = json.loads(raw_response)
        _status_ok = parsed["status"] == 200

    return parsed


async def mock_api_call(
    endpoint: str,
    rng: random.Random,
    session_id: str,
    latency_scale: float = 1.0,
) -> dict[str, Any]:
    with timed(Category.HTTP_CLIENT, session_id, bytes_out=len(endpoint)):
        request = {
            "method": endpoint.split(" ")[0] if " " in endpoint else "GET",
            "url": endpoint.split(" ")[-1],
            "headers": {
                "accept": "application/json",
                "user-agent": "apu-harness/1.0",
                "x-request-id": f"{rng.getrandbits(64):016x}",
                "authorization": "Bearer mock-token",
            },
        }
        raw_request = json.dumps(request)

    mu = math.log(max(API_MEDIAN_S * latency_scale, 1e-6))
    await asyncio.sleep(rng.lognormvariate(mu, API_SIGMA))

    body = {
        "endpoint": request["url"],
        "status": 200,
        "data": {"value": rng.random() * 100, "unit": "mock", "ts": rng.getrandbits(32)},
    }
    raw_response = json.dumps(body)

    with timed(Category.HTTP_CLIENT, session_id, bytes_in=len(raw_response)):
        parsed = json.loads(raw_response)
        _status_ok = parsed["status"] == 200

    return parsed
