"""Per-node latency instrumentation for the LangGraph agent.

Reason: before adding async/pooling/celery/concurrency limits, we need a
baseline of where time is actually spent in an investigation (planner vs.
SQL generation vs. analyst LLM call, etc). Without this, any later
performance change is an unverifiable guess ("it should be faster").

`timed_node` wraps a node function `(state) -> dict` and:
  1. Measures wall-clock duration with `time.perf_counter()`.
  2. Logs a structured line (thread_id, node, duration_ms, ok/error) to the
     `ops_agent.timing` logger.
  3. Merges a `node_timings` entry into the node's returned state update,
     so the full per-node breakdown for a run is queryable from state/DB
     without re-parsing logs.

Failures are re-raised after being timed/logged, so this never changes
node error behavior.
"""

import functools
import logging
import time

from langgraph.errors import GraphInterrupt

logger = logging.getLogger("ops_agent.timing")


def timed_node(node_name: str):
    def decorator(node_fn):
        @functools.wraps(node_fn)
        def wrapper_with_state_entry(state):
            thread_id = state.get("thread_id", "") if isinstance(state, dict) else ""
            start = time.perf_counter()

            try:
                result = node_fn(state)
            except GraphInterrupt:
                # Normal control flow (human-in-the-loop pause), not a
                # failure — don't log/count it as an error.
                duration_ms = round((time.perf_counter() - start) * 1000, 2)
                logger.info(
                    "node=%s thread_id=%s status=interrupted duration_ms=%s",
                    node_name,
                    thread_id,
                    duration_ms,
                )
                raise
            except Exception:
                duration_ms = round((time.perf_counter() - start) * 1000, 2)
                logger.info(
                    "node=%s thread_id=%s status=error duration_ms=%s",
                    node_name,
                    thread_id,
                    duration_ms,
                )
                raise

            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "node=%s thread_id=%s status=ok duration_ms=%s",
                node_name,
                thread_id,
                duration_ms,
            )

            result = dict(result or {})
            result.setdefault("node_timings", [])
            result["node_timings"] = result["node_timings"] + [
                {"node": node_name, "duration_ms": duration_ms}
            ]
            return result

        return wrapper_with_state_entry

    return decorator
