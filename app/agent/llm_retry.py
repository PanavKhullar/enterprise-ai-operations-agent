"""Shared retry policy for Gemini LLM calls made by the agent nodes.

`ChatGoogleGenerativeAI` (via the `google-genai` SDK) raises
`google.genai.errors.ClientError` / `ServerError` for HTTP error responses
(e.g. 429 rate limit, 5xx transient failures) rather than raw `httpx`
exceptions. The original retry decorators here only matched httpx transport
errors, so real API errors (like the 429 RESOURCE_EXHAUSTED seen from the
Gemini free tier) were never retried and instead raised immediately.

This module centralizes the retry predicate so every node treats these
errors consistently.

It also gates every call through `acquire_llm_slot` (see
`app/agent/rate_limiter.py`) so the number of Gemini requests in flight at
once is bounded across all Celery workers/investigations, not just
retried when the API pushes back with a 429.
"""

import functools
import logging
import time

import httpx
from google.genai.errors import APIError, ClientError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

import app.telemetry as telemetry
from app.agent.rate_limiter import acquire_llm_slot
from app.telemetry import get_tracer

logger = logging.getLogger("ops_agent.llm")
tracer = get_tracer(__name__)


def _is_retryable_llm_error(exc: BaseException) -> bool:
    # Transport-level hiccups.
    if isinstance(exc, (httpx.RemoteProtocolError, httpx.ReadTimeout, httpx.ConnectError)):
        return True

    # Any Gemini 5xx (ServerError) is presumed transient (e.g. temporarily
    # overloaded) and worth a bounded retry with backoff.
    if isinstance(exc, APIError) and not isinstance(exc, ClientError):
        return True

    # 429 (rate limit / quota) can be a short-lived per-minute limit, in
    # which case a short backoff can succeed. A hard daily-quota exhaustion
    # will simply keep failing and `reraise=True` below lets it surface
    # after the retry budget is spent, instead of hanging indefinitely.
    if isinstance(exc, ClientError) and exc.code == 429:
        return True

    return False


def _log_retry(retry_state):
    caller = retry_state.fn.__module__ if retry_state.fn else "unknown"
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    telemetry.gemini_retry_counter.add(
        1, {"caller": caller, "exception": type(exc).__name__ if exc else ""}
    )
    logger.warning(
        "event=gemini_retry caller=%s attempt=%s exception=%s",
        caller,
        retry_state.attempt_number,
        exc,
    )


_with_retry = retry(
    retry=retry_if_exception(_is_retryable_llm_error),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    reraise=True,
    before_sleep=_log_retry,
)


def llm_retry(func):
    """Reused by every LLM-backed node (planner, sql_generator, hypothesis,
    analyst, recommender) to decorate their local `_invoke_llm` helper.

    Each retry attempt acquires its own concurrency slot rather than
    holding one for the whole retry loop (including backoff sleeps) — a
    slow/retrying call shouldn't sit on a slot other callers are waiting
    for while it's not even talking to the API.

    Also records a span + call count/duration/error metrics per attempt,
    tagged with the calling node's module, so latency/error/token-usage
    can be broken down by which node (planner/sql_generator/hypothesis/
    analyst/recommender) is driving Gemini cost.
    """

    caller = func.__module__

    @functools.wraps(func)
    def _slot_gated(*args, **kwargs):
        with acquire_llm_slot():
            start = time.perf_counter()
            with tracer.start_as_current_span("gemini.call") as span:
                span.set_attribute("caller", caller)
                try:
                    result = func(*args, **kwargs)
                except Exception as exc:
                    duration_ms = (time.perf_counter() - start) * 1000
                    span.set_attribute("status", "error")
                    span.record_exception(exc)
                    telemetry.gemini_call_counter.add(
                        1, {"caller": caller, "status": "error", "error": type(exc).__name__}
                    )
                    telemetry.gemini_call_duration.record(
                        duration_ms, {"caller": caller, "status": "error"}
                    )
                    raise

                duration_ms = (time.perf_counter() - start) * 1000
                span.set_attribute("status", "ok")
                span.set_attribute("duration_ms", duration_ms)

                usage = getattr(result, "usage_metadata", None)
                if usage:
                    span.set_attribute("tokens.input", usage.get("input_tokens", 0))
                    span.set_attribute("tokens.output", usage.get("output_tokens", 0))
                    telemetry.gemini_token_counter.add(
                        usage.get("input_tokens", 0), {"caller": caller, "type": "input"}
                    )
                    telemetry.gemini_token_counter.add(
                        usage.get("output_tokens", 0), {"caller": caller, "type": "output"}
                    )

                telemetry.gemini_call_counter.add(1, {"caller": caller, "status": "ok"})
                telemetry.gemini_call_duration.record(duration_ms, {"caller": caller, "status": "ok"})
                logger.info(
                    "event=gemini_call caller=%s status=ok duration_ms=%.2f",
                    caller,
                    duration_ms,
                )
                return result

    return _with_retry(_slot_gated)
