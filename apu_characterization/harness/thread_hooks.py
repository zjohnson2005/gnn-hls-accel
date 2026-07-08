"""Thread-level and httpx hooks for instrumentation v2/v3."""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from typing import Any, Callable

import httpx

from ..instr import get_run_accumulator, timed
from ..taxonomy import Category

_hooks_installed = False
_orig_executor_submit: Callable[..., Any] | None = None
_orig_httpx_send: Callable[..., Any] | None = None
_orig_asyncio_run: Callable[..., Any] | None = None
_orig_async_send: Callable[..., Any] | None = None


def _session_id() -> str:
    from ..session_context import get_session_id

    return get_session_id()


def _instr_version() -> int:
    acc = get_run_accumulator()
    return acc.instr_version if acc is not None else 1


def _register_executor_thread(session_id: str) -> None:
    if _instr_version() < 3:
        return
    from ..thread_identity import ThreadRole, get_thread_registry

    get_thread_registry().register_current(ThreadRole.EXECUTOR, session_id)


def _wrap_executor_submit(original: Callable[..., Any]) -> Callable[..., Any]:
    def submit(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any):
        sid = _session_id()

        def wrapped() -> Any:
            from ..session_context import session_id_ctx

            tok = session_id_ctx.set(sid)
            reg = None
            try:
                if _instr_version() >= 3:
                    from ..thread_identity import get_thread_registry

                    reg = get_thread_registry()
                    _register_executor_thread(sid)
                    return fn(*args, **kwargs)
                with timed(Category.THREADPOOL, sid):
                    return fn(*args, **kwargs)
            finally:
                if _instr_version() >= 3 and reg is not None:
                    # Book this worker's remaining untagged CPU while its TID
                    # is still alive. A full-registry sample here is redundant
                    # (session-end sampling covers live threads) and its /proc
                    # reads add measurable per-task overhead on fan-out pools.
                    reg.finalize_current_thread()
                session_id_ctx.reset(tok)

        return original(self, wrapped)

    return submit


def _wrap_httpx_send(original: Callable[..., Any]) -> Callable[..., Any]:
    # v3 uses the same timed path as v2: thread_time captures the calling
    # thread's SSL/serialization CPU at ns resolution, and the tagged-CPU
    # ledger prevents double counting against psutil thread sampling.
    # (Permanently relabeling the calling thread as HTTP_TRANSPORT was wrong:
    # LLM calls run on the session main thread, which then booked all its
    # CPU to CLIENT_HTTP.)
    def send(self, request: httpx.Request, *args: Any, **kwargs: Any) -> httpx.Response:
        sid = _session_id()
        with timed(Category.CLIENT_HTTP, sid, bytes_out=len(request.content or b"")):
            response = original(self, request, *args, **kwargs)
        with timed(Category.CLIENT_PARSE, sid):
            try:
                response.read()
            except Exception:
                pass
        return response

    return send


def _wrap_asyncio_run(original: Callable[..., Any]) -> Callable[..., Any]:
    def run(coro: Any, *args: Any, **kwargs: Any) -> Any:
        sid = _session_id()
        with timed(Category.EVENT_LOOP, sid):
            return original(coro, *args, **kwargs)

    return run


def submit_unwrapped(executor: Any, fn: Callable[..., Any], /, *args: Any, **kwargs: Any):
    """Submit bypassing the THREADPOOL wrapper.

    The batch harness runs whole sessions on a pool; wrapping those submits
    would book each entire session's thread CPU to THREADPOOL (double count).
    """
    orig = _orig_executor_submit or concurrent.futures.ThreadPoolExecutor.submit
    return orig(executor, fn, *args, **kwargs)


def install_thread_hooks() -> None:
    global _hooks_installed, _orig_executor_submit, _orig_httpx_send, _orig_asyncio_run
    global _orig_async_send
    if _hooks_installed:
        return
    _orig_executor_submit = concurrent.futures.ThreadPoolExecutor.submit
    concurrent.futures.ThreadPoolExecutor.submit = _wrap_executor_submit(  # type: ignore[method-assign]
        _orig_executor_submit
    )
    _orig_httpx_send = httpx.Client.send
    httpx.Client.send = _wrap_httpx_send(httpx.Client.send)  # type: ignore[method-assign]
    if hasattr(httpx, "AsyncClient"):
        _orig_async_send = httpx.AsyncClient.send

        async def _async_send(self, request: httpx.Request, *args: Any, **kwargs: Any):
            sid = _session_id()
            with timed(Category.CLIENT_HTTP, sid, bytes_out=len(request.content or b"")):
                response = await _orig_async_send(self, request, *args, **kwargs)
            with timed(Category.CLIENT_PARSE, sid):
                try:
                    await response.aread()
                except Exception:
                    pass
            return response

        httpx.AsyncClient.send = _async_send  # type: ignore[method-assign]
    _orig_asyncio_run = asyncio.run
    asyncio.run = _wrap_asyncio_run(asyncio.run)  # type: ignore[assignment]
    _hooks_installed = True


def uninstall_thread_hooks() -> None:
    global _hooks_installed, _orig_executor_submit, _orig_httpx_send, _orig_asyncio_run
    global _orig_async_send
    if not _hooks_installed:
        return
    if _orig_executor_submit is not None:
        concurrent.futures.ThreadPoolExecutor.submit = _orig_executor_submit  # type: ignore[method-assign]
    if _orig_httpx_send is not None:
        httpx.Client.send = _orig_httpx_send  # type: ignore[method-assign]
    if _orig_async_send is not None and hasattr(httpx, "AsyncClient"):
        httpx.AsyncClient.send = _orig_async_send  # type: ignore[method-assign]
    if _orig_asyncio_run is not None:
        asyncio.run = _orig_asyncio_run  # type: ignore[assignment]
    _hooks_installed = False
    _orig_executor_submit = None
    _orig_httpx_send = None
    _orig_async_send = None
    _orig_asyncio_run = None
