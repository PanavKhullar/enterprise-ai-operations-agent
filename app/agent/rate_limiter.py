"""Distributed concurrency limiter for Gemini LLM calls.

Reason: a single investigation already fires several Gemini calls in
parallel (`investigator.py` runs plan steps concurrently via
`asyncio.gather`), and multiple investigations can be in flight at once
(each is an independent Celery task). Nothing previously bounded how many
Gemini requests could be in flight *at the same time* across the whole
process/fleet of workers — under load this can blow through the API's
per-minute concurrent/RPM quota, turning into a wave of 429s that `llm_retry`
then has to burn its retry budget absorbing.

This module implements a distributed counting semaphore backed by Redis
(a sorted set keyed by a UUID per holder, scored by acquisition time), so
the limit is enforced across every Celery worker process, not just
in-process. It intentionally does NOT try to be a precise token-bucket
rate limiter (e.g. exact RPM) — bounding concurrent in-flight calls is a
simpler, robust proxy that directly caps worst-case burst load on the
API, which is what actually causes 429 storms.

Design notes:
- Slots carry a TTL (`SLOT_TTL_SECONDS`). If a worker crashes or hangs
  while holding a slot, the entry ages out of the sorted set instead of
  permanently shrinking the effective limit (classic Redis semaphore
  recipe: expire-then-count-then-add, all needed steps done per call).
- Fails open: if Redis is unreachable, calls proceed unthrottled rather
  than blocking investigations entirely — consistent with `app/cache.py`.
- Acquisition blocks with jittered polling up to `ACQUIRE_TIMEOUT_SECONDS`
  before giving up and letting the call proceed unthrottled (rather than
  hanging a request/task forever waiting for a slot that may never free).
"""

import logging
import os
import random
import time
import uuid
from contextlib import contextmanager

import redis

import app.telemetry as telemetry

logger = logging.getLogger("ops_agent.rate_limiter")

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# How many Gemini calls may be in flight at once, across all workers.
# Kept conservative by default since free-tier Gemini quotas are low.
MAX_CONCURRENT_LLM_CALLS = int(os.environ.get("GEMINI_MAX_CONCURRENT_CALLS", "3"))

# How long a slot is considered valid before it's treated as abandoned
# (e.g. the holder crashed without releasing).
SLOT_TTL_SECONDS = float(os.environ.get("GEMINI_SLOT_TTL_SECONDS", "30"))

# Max time to wait for a free slot before giving up and proceeding
# unthrottled anyway (a stuck queue must never mean a hung investigation).
ACQUIRE_TIMEOUT_SECONDS = float(os.environ.get("GEMINI_ACQUIRE_TIMEOUT_SECONDS", "45"))

_SEMAPHORE_KEY = "llm:gemini:semaphore"

# Atomically: expire stale slots, then only add the new holder if that
# leaves room under the limit. Must be a single Lua script — a
# pipeline'd zremrangebyscore + zcard + zadd is NOT atomic across
# concurrent callers (each step round-trips independently), which in
# practice let far more than `MAX_CONCURRENT_LLM_CALLS` holders through
# under concurrent load.
_ACQUIRE_SCRIPT = """
local key = KEYS[1]
local holder_id = ARGV[1]
local now = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
local max_slots = tonumber(ARGV[4])

redis.call('ZREMRANGEBYSCORE', key, 0, now - ttl)
local count = redis.call('ZCARD', key)

if count < max_slots then
    redis.call('ZADD', key, now, holder_id)
    return 1
else
    return 0
end
"""

_redis_client: "redis.Redis | bool | None" = None
_acquire_script = None


def _get_client():
    global _redis_client, _acquire_script

    if _redis_client is None:
        try:
            _redis_client = redis.Redis.from_url(
                REDIS_URL, decode_responses=True, socket_connect_timeout=1
            )
            _redis_client.ping()
            _acquire_script = _redis_client.register_script(_ACQUIRE_SCRIPT)
        except Exception as e:
            logger.warning("Redis unavailable, disabling LLM concurrency limit: %s", e)
            _redis_client = False

    return _redis_client or None


def _try_acquire(client: redis.Redis, holder_id: str) -> bool:
    now = time.time()
    result = _acquire_script(
        keys=[_SEMAPHORE_KEY],
        args=[holder_id, now, SLOT_TTL_SECONDS, MAX_CONCURRENT_LLM_CALLS],
    )
    return bool(result)


@contextmanager
def acquire_llm_slot():
    """Block until a concurrency slot is free, then hold it for the
    duration of the `with` block. Degrades gracefully (no-op) if Redis is
    unavailable or a slot never frees up within the timeout."""

    client = _get_client()
    if client is None:
        yield
        return

    holder_id = str(uuid.uuid4())
    wait_start = time.time()
    deadline = wait_start + ACQUIRE_TIMEOUT_SECONDS
    acquired = False

    try:
        while time.time() < deadline:
            try:
                if _try_acquire(client, holder_id):
                    acquired = True
                    break
            except Exception as e:
                logger.warning("Redis error acquiring LLM slot, proceeding unthrottled: %s", e)
                break
            time.sleep(0.1 + random.uniform(0, 0.2))

        wait_ms = (time.time() - wait_start) * 1000
        telemetry.rate_limiter_wait_duration.record(wait_ms, {"acquired": str(acquired)})

        if not acquired and time.time() >= deadline:
            telemetry.rate_limiter_timeout_counter.add(1)
            logger.warning(
                "Timed out after %.0fs waiting for a free Gemini call slot; proceeding anyway",
                ACQUIRE_TIMEOUT_SECONDS,
            )

        yield
    finally:
        if acquired:
            try:
                client.zrem(_SEMAPHORE_KEY, holder_id)
            except Exception as e:
                logger.warning("Redis error releasing LLM slot (will expire via TTL): %s", e)
