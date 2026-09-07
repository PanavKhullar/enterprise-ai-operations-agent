"""Redis-backed cache for repeated SQL evidence lookups.

Reason: the investigator often re-runs the same or overlapping generated
SQL across investigations of the same warehouse/date-range (e.g. two
questions about WH_03 both compute a 30/60/90-day rolling average). The
SQL itself is read-only and deterministic for a given query string over a
short window, so caching the query -> result mapping avoids redundant
round-trips to Postgres without touching the LangGraph
interrupt/resume/checkpointing flow at all.

Cache key: sha256(normalized query). Value: the JSON-serialized result
dict returned by `execute_sql`. TTL is short (5 min) since the underlying
data can change (new orders/shipments arrive continuously).
"""

import hashlib
import json
import logging
import os
from typing import Any, Optional

import redis

logger = logging.getLogger("ops_agent.cache")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Cached SQL results expire quickly since the underlying operational data
# is continuously updated; this is meant to absorb bursts of identical/
# overlapping queries within one investigation or across near-simultaneous
# investigations, not to serve stale data long-term.
QUERY_CACHE_TTL_SECONDS = 300

_redis_client: Optional[redis.Redis] = None


def _get_client() -> Optional[redis.Redis]:
    """Lazily create the Redis client. Returns None if Redis is unreachable
    so caching degrades gracefully (falls back to always querying Postgres)
    instead of breaking investigations if Redis is down."""

    global _redis_client

    if _redis_client is None:
        try:
            _redis_client = redis.Redis.from_url(
                REDIS_URL, decode_responses=True, socket_connect_timeout=1
            )
            _redis_client.ping()
        except Exception as e:
            logger.warning("Redis cache unavailable, disabling query cache: %s", e)
            _redis_client = False  # sentinel: don't retry every call

    return _redis_client or None


def _query_key(query: str) -> str:
    normalized = " ".join(query.strip().lower().split())
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    return f"sql_cache:{digest}"


def get_cached_query_result(query: str) -> Optional[dict[str, Any]]:
    client = _get_client()
    if client is None:
        return None

    try:
        cached = client.get(_query_key(query))
    except Exception as e:
        logger.warning("Redis GET failed, treating as cache miss: %s", e)
        return None

    if cached is None:
        logger.info("cache=miss query_hash=%s", _query_key(query))
        return None

    logger.info("cache=hit query_hash=%s", _query_key(query))
    try:
        return json.loads(cached)
    except (TypeError, ValueError):
        return None


def set_cached_query_result(query: str, result: dict[str, Any]) -> None:
    client = _get_client()
    if client is None:
        return

    try:
        client.setex(_query_key(query), QUERY_CACHE_TTL_SECONDS, json.dumps(result, default=str))
    except Exception as e:
        logger.warning("Redis SETEX failed, skipping cache write: %s", e)
