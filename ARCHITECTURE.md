# Enterprise AI Operations Investigation Agent — Architecture

## MVP Architecture (Phase 1)

```
                    ┌──────────────┐
                    │    Client    │
                    │ (simple UI/  │
                    │  CLI/Postman)│
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │   FastAPI    │
                    │ POST /investigate
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │  LangGraph   │
                    │  Agent Graph │
                    └──────┬───────┘
                           ↓
                  (sequential calls)
                 ┌─────────┴─────────┐
                 ↓                   ↓
            SQL Tool           Analytics Tool
                 └─────────┬─────────┘
                           ↓
                     PostgreSQL
                (orders, warehouses,
              shipments, sla_events)
                           ↓
                     Gemini API
              (via LLMService abstraction)
                           ↓
                  Evidence-based Answer
```

No Redis, no Celery, no observability yet — deliberately simple so we can
measure real bottlenecks before adding anything.

---

## Target Production Architecture (End State)

```
                    ┌──────────────┐
                    │    Client    │
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │   FastAPI    │
                    │ Auth / Async │
                    └──────┬───────┘
                           ↓
                 ┌─────────┴─────────┐
                 ↓                   ↓
             LangGraph            Redis
             Agent Graph        (Cache + Rate Limit)
                 ↓
          ┌──────┼──────┐
          ↓      ↓       ↓
       SQL    Analytics  API Tool
       Tool     Tool     (optional, external)
          └──────┼──────┘
                 ↓         (parallel via asyncio.gather)
           Agent Synthesis
                 │
                 ↓
         ┌───────┴───────┐
         ↓               ↓
   Gemini API      Human-in-the-loop
 (LLMService:      Approval Gate
  Gemini/OpenAI/    (LangGraph interrupt/resume,
  Local providers)   only for recommended actions)
         │
         ↓
     PostgreSQL
 (orders, warehouses, shipments,
  sla_events, investigation history)

          Background Workloads (NOT in hot path)
                 ↓
              Celery
                 ↓
        ┌────────┴────────┐
        ↓                 ↓
  Scheduled Reports   Batch Anomaly Scans
  (weekly SLA digest)  (nightly, all warehouses)

Cross-cutting (applies to every layer above):
─────────────────────────────────────────────
Docker (API + Postgres + Redis + Celery worker, docker-compose)
OpenTelemetry (tracing: agent steps, tool calls, DB/Redis ops, LLM calls)
Structured Logging (request/correlation IDs)
Metrics (latency, token usage, cache hit/miss, cost/request)
Evaluation Harness (question → expected evidence/answer, versioned scoring)
Load Testing (Locust/k6: 10 → 50 → 100 → 500 concurrent requests)
GitHub Actions CI/CD (lint → test → build image → deploy)
```

## Key Architectural Decisions & Why

| Decision | Reason |
|---|---|
| LangGraph for orchestration | Need conditional routing (which tools to call), multi-step planning, and human-in-the-loop interrupt/resume — not a fixed pipeline |
| LLMService abstraction (Gemini first) | Avoid coupling agent logic to one provider; free-tier development; provider swap should touch only the adapter layer |
| Parallel tool calls (asyncio.gather) | Independent evidence-gathering steps (SQL query + analytics + external API) don't need to be sequential — real latency win |
| Redis for cache + rate limit | Overlapping analyst questions shouldn't recompute identical work; protects system under concurrent load |
| Celery only for background jobs | Report generation / batch scans are slow and non-interactive — must not block the real-time investigation path |
| Human-in-the-loop gate | Recommended actions have real business consequences; agent must not auto-execute them |
| PostgreSQL (no pgvector) | Data is structured/relational (orders, SLAs) — no genuine retrieval-over-embeddings need, so no vector store added just for resume keywords |
| OpenTelemetry + structured logs | Need to explain, per request, exactly what the agent did and how long each step took — both for debugging and for the interview "observability" story |
| Docker Compose | Reproducible from a fresh machine; matches how the app would actually be run/deployed |

## Evolution Story (MVP → Production)
1. **MVP**: sequential tool calls, no cache, no queue → measure baseline latency
2. **Bottleneck 1**: sequential SQL + analytics calls add up → fix: parallelize → remeasure
3. **Bottleneck 2**: repeated/overlapping questions recompute identical work → fix: Redis cache → measure hit rate + latency delta
4. **Bottleneck 3**: full reports too slow for a live request → fix: move to Celery background job
5. **Bottleneck 4**: no visibility into where time/cost goes → fix: add OpenTelemetry tracing + token/cost logging
6. **Validation**: load test before/after each major change; evaluation harness scores correctness/tool-selection across versions
