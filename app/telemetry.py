"""Central observability setup: structured logging, OpenTelemetry tracing,
and OpenTelemetry metrics, shared by the FastAPI process and Celery workers.

Design (Step 9 of the production roadmap):
- Structured JSON logs carry correlation IDs (request_id/thread_id/task_id)
  and the current agent node name via contextvars, so a single investigation
  can be grepped end-to-end across the API and worker log streams.
- Tracing/metrics use the stdlib OpenTelemetry SDK with the built-in
  Console exporters (no collector/Prometheus/Grafana required) so this
  works out of the box in local dev; point `OTEL_EXPORTER_OTLP_ENDPOINT`
  at a real backend later without touching instrumentation call sites.
- Kept intentionally small: one shared module instead of a package, since
  every piece (logging/tracing/metrics) is configured once per process.
"""

import contextvars
import json
import logging
import os
import time

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# --- Correlation context -----------------------------------------------

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
thread_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("thread_id", default="")
task_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("task_id", default="")
node_var: contextvars.ContextVar[str] = contextvars.ContextVar("node", default="")


class _CorrelationScope:
    """Context manager that sets one or more correlation vars and restores
    the previous values on exit, so nested scopes (e.g. a node running
    inside a Celery task running inside a resumed investigation) compose
    correctly."""

    _VARS = {
        "request_id": request_id_var,
        "thread_id": thread_id_var,
        "task_id": task_id_var,
        "node": node_var,
    }

    def __init__(self, **kwargs):
        self._tokens = {}
        self._values = kwargs

    def __enter__(self):
        for key, value in self._values.items():
            if value is not None:
                self._tokens[key] = self._VARS[key].set(value)
        return self

    def __exit__(self, *exc_info):
        for key, token in self._tokens.items():
            self._VARS[key].reset(token)


def correlation_context(**kwargs) -> _CorrelationScope:
    """Usage: `with correlation_context(thread_id=..., task_id=...): ...`"""
    return _CorrelationScope(**kwargs)


# --- Structured JSON logging --------------------------------------------

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
            "thread_id": thread_id_var.get(),
            "task_id": task_id_var.get(),
            "node": node_var.get(),
        }
        # Drop empty correlation fields to keep lines compact when a given
        # context doesn't apply (e.g. no request_id inside a Celery worker).
        payload = {k: v for k, v in payload.items() if v not in ("", None)}

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


_logging_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    """Idempotent: safe to call from both the API process and every Celery
    worker process without producing duplicate handlers/log lines."""

    global _logging_configured
    if _logging_configured:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    _logging_configured = True


# --- Tracing --------------------------------------------------------------

_tracing_configured = False


def setup_tracing(service_name: str) -> None:
    """Idempotent per-process tracer setup using the Console exporter.

    Swap in an OTLP exporter here (reading `OTEL_EXPORTER_OTLP_ENDPOINT`)
    to ship spans to a real backend (Jaeger/Tempo/etc.) without changing
    any instrumentation call sites elsewhere in the app.
    """

    global _tracing_configured
    if _tracing_configured:
        return

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)

    _tracing_configured = True


def get_tracer(name: str = "ops_agent"):
    return trace.get_tracer(name)


# --- Metrics ----------------------------------------------------------------

_metrics_configured = False
_meter = None

# Populated by `setup_metrics()`; module-level so every call site can just
# `from app.telemetry import record_*` without threading a meter through.
api_request_duration = None
api_request_counter = None
investigation_duration = None
investigation_counter = None
node_duration = None
gemini_call_duration = None
gemini_call_counter = None
gemini_token_counter = None
gemini_retry_counter = None
db_query_duration = None
db_error_counter = None
cache_counter = None
rate_limiter_wait_duration = None
rate_limiter_timeout_counter = None
celery_task_duration = None
celery_task_counter = None


def setup_metrics(service_name: str) -> None:
    global _metrics_configured, _meter
    global api_request_duration, api_request_counter
    global investigation_duration, investigation_counter, node_duration
    global gemini_call_duration, gemini_call_counter, gemini_token_counter, gemini_retry_counter
    global db_query_duration, db_error_counter, cache_counter
    global rate_limiter_wait_duration, rate_limiter_timeout_counter
    global celery_task_duration, celery_task_counter

    if _metrics_configured:
        return

    # 30s export interval keeps Console output readable during dev/manual
    # verification runs instead of flooding the log on every single call.
    reader = PeriodicExportingMetricReader(ConsoleMetricExporter(), export_interval_millis=30000)
    provider = MeterProvider(
        resource=Resource.create({"service.name": service_name}), metric_readers=[reader]
    )
    metrics.set_meter_provider(provider)
    _meter = metrics.get_meter("ops_agent")

    api_request_counter = _meter.create_counter("api.request.count")
    api_request_duration = _meter.create_histogram("api.request.duration_ms")

    investigation_counter = _meter.create_counter("investigation.count")
    investigation_duration = _meter.create_histogram("investigation.duration_ms")

    node_duration = _meter.create_histogram("agent.node.duration_ms")

    gemini_call_counter = _meter.create_counter("gemini.call.count")
    gemini_call_duration = _meter.create_histogram("gemini.call.duration_ms")
    gemini_token_counter = _meter.create_counter("gemini.tokens")
    gemini_retry_counter = _meter.create_counter("gemini.retry.count")

    db_query_duration = _meter.create_histogram("db.query.duration_ms")
    db_error_counter = _meter.create_counter("db.query.error.count")

    cache_counter = _meter.create_counter("cache.result.count")

    rate_limiter_wait_duration = _meter.create_histogram("rate_limiter.wait_ms")
    rate_limiter_timeout_counter = _meter.create_counter("rate_limiter.timeout.count")

    celery_task_counter = _meter.create_counter("celery.task.count")
    celery_task_duration = _meter.create_histogram("celery.task.duration_ms")

    _metrics_configured = True


def now_ms() -> float:
    return time.perf_counter() * 1000
