"""Shared retry policy for Gemini LLM calls made by the agent nodes.

`ChatGoogleGenerativeAI` (via the `google-genai` SDK) raises
`google.genai.errors.ClientError` / `ServerError` for HTTP error responses
(e.g. 429 rate limit, 5xx transient failures) rather than raw `httpx`
exceptions. The original retry decorators here only matched httpx transport
errors, so real API errors (like the 429 RESOURCE_EXHAUSTED seen from the
Gemini free tier) were never retried and instead raised immediately.

This module centralizes the retry predicate so every node treats these
errors consistently.
"""

import httpx
from google.genai.errors import APIError, ClientError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential


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


# Reused by every LLM-backed node (planner, sql_generator, hypothesis,
# analyst, recommender) to decorate their local `_invoke_llm` helper.
llm_retry = retry(
    retry=retry_if_exception(_is_retryable_llm_error),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=20),
    reraise=True,
)
