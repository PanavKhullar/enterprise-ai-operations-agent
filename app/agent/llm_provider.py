"""
Round-robins across multiple Gemini API keys so that exhausting one key's
quota doesn't stop the agent — `llm_retry.py` rotates to the next key and
keeps going instead of surfacing a 429 to the caller.

Configure keys with EITHER of:
- `GEMINI_API_KEYS="key1,key2,key3"` (comma-separated), or
- `GEMINI_API_KEY_1`, `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`, ... (numbered)

Falls back to the single `GEMINI_API_KEY` / `GOOGLE_API_KEY` the SDK
normally reads, so existing single-key setups keep working unchanged.
"""

import logging
import os
import threading

from dotenv import load_dotenv
from google.genai.errors import ClientError
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

logger = logging.getLogger("ops_agent.llm_provider")

_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


def _load_keys() -> list[str]:
    raw = os.getenv("GEMINI_API_KEYS", "")
    keys = [k.strip() for k in raw.split(",") if k.strip()]

    i = 1
    while True:
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if not key:
            break
        keys.append(key.strip())
        i += 1

    if not keys:
        single = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if single:
            keys.append(single.strip())

    if not keys:
        raise RuntimeError(
            "No Gemini API key found. Set GEMINI_API_KEYS (comma-separated), "
            "GEMINI_API_KEY_1 / GEMINI_API_KEY_2 / ..., or GEMINI_API_KEY / "
            "GOOGLE_API_KEY."
        )

    return keys


_keys = _load_keys()
_lock = threading.Lock()
_current_index = 0
_clients: dict[int, ChatGoogleGenerativeAI] = {}

if len(_keys) > 1:
    logger.info("event=gemini_key_pool_loaded key_count=%s", len(_keys))


def _build_client(index: int) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(model=_MODEL, google_api_key=_keys[index])


def get_llm() -> ChatGoogleGenerativeAI:
    """Return the currently-active Gemini client. Built lazily and cached
    per key index, so switching keys doesn't reconnect on every call."""

    with _lock:
        idx = _current_index
        if idx not in _clients:
            _clients[idx] = _build_client(idx)
        return _clients[idx]


def is_quota_error(exc: BaseException) -> bool:
    """True for HTTP 429s — covers both short-lived per-minute rate limits
    and hard daily-quota exhaustion; rotating keys helps most with the
    latter (a per-minute limit would often resolve on its own too, but
    trying another key immediately is strictly faster)."""

    return isinstance(exc, ClientError) and exc.code == 429


def rotate_key() -> bool:
    """Switch to the next configured API key (round-robin).

    Returns True if there was another key to rotate to, False if only one
    key is configured (nothing to rotate to — caller should just let the
    normal backoff/retry handle it).
    """

    global _current_index

    with _lock:
        if len(_keys) <= 1:
            return False

        previous = _current_index
        _current_index = (_current_index + 1) % len(_keys)
        logger.warning(
            "event=gemini_key_rotated from_index=%s to_index=%s of %s keys",
            previous,
            _current_index,
            len(_keys),
        )
        return True
