# Enterprise AI Operations Investigation Agent — Project Plan

## Problem Statement
Ops/business users need to ask natural-language diagnostic questions about
operational metrics (e.g., "Why did our order-processing SLA drop yesterday?")
and get an evidence-backed root-cause answer, instead of manually running SQL
and cross-referencing data by hand. The agent plans its own investigation,
gathers evidence via tools (SQL, analytics, optional external APIs), and
synthesizes a defensible answer — with human approval required before any
recommended action is treated as executed.

## Target Users
Ops analysts / managers at an e-commerce or logistics-style company.

## Domain / Data Model (to finalize before coding)
Synthetic but realistic e-commerce operations data:
- `orders` (order_id, customer_id, warehouse_id, created_at, status, sla_due_at, fulfilled_at)
- `warehouses` (warehouse_id, name, region, capacity)
- `shipments` (shipment_id, order_id, carrier, picked_up_at, delivered_at, delay_reason)
- `sla_events` (event_id, order_id, breached BOOL, breach_reason, recorded_at)
- Seed with realistic messiness: nulls, skew, seasonal patterns, and a few
  deliberately injected anomalies (e.g., one warehouse's SLA drops on one day
  due to a carrier pickup delay spike) so investigations have real answers.

## Architecture (target end-state)
Client → FastAPI (auth/async) → LangGraph (agent/tools/memory) → Gemini API
                                      │
                         ┌────────────┼────────────┐
                         ↓            ↓             ↓
                    SQL Tool   Analytics Tool   API Tool (optional)
                         └────────────┬────────────┘
                                PostgreSQL
Redis: cache + rate limit (alongside request path)
Celery: background reports / batch anomaly scans (NOT in hot path)
Observability: OpenTelemetry + structured logs across all of the above

LLM access abstracted behind `LLMService` (GeminiProvider now; OpenAI/Local
adapters possible later) — LangGraph logic not tightly coupled to Gemini.

## Key Features
1. Natural-language investigation (agent plans its own steps per question)
2. Multi-tool evidence gathering (SQL, analytics, optional external API)
3. Evidence-based synthesis (answer cites what data was checked)
4. Multi-turn drill-down (persistent investigation state)
5. Recommended actions gated by human-in-the-loop approval (LangGraph interrupt/resume)
6. Caching of repeated/overlapping investigations (Redis, measured hit/miss)
7. Background report generation (Celery, polled/streamed results)
8. Rate limiting & per-user session isolation
9. Retries/timeouts/fallback around LLM + external calls
10. Observability: full per-request trace (tools called, durations, tokens, cost)
11. Evaluation harness (question → expected evidence/answer pairs, versioned comparison)
12. Load-tested, stateless, horizontally scalable API (Locust/k6, real p50/p95/p99)
13. Dockerized, reproducible stack + GitHub Actions CI/CD

## Build Philosophy
MVP first (simple, sequential, no cache/queue) → measure → find real bottleneck
→ introduce one production improvement → measure again → document why.
Never claim a number that wasn't measured.

## Phased Plan (~16-19 days)

### Phase 0 — Setup (0.5 day)
- Repo init, README skeleton, Docker Compose shell (Postgres, Redis placeholders)
- First commit: `feat: initialize project architecture`

### Phase 1 — MVP (5-6 days)
- Postgres schema + seed script (synthetic data w/ injected anomalies)
- FastAPI app skeleton (modular: routers/services/schemas, not one file)
- LLMService abstraction + GeminiProvider
- LangGraph: single-path agent → SQL tool → analytics tool → synthesize answer
- One working endpoint: `POST /investigate {question}` → answer + evidence
- Manual test: ask MVP questions, confirm plausible answers
- Commits: `feat: add FastAPI application layer`, `feat: add PostgreSQL persistence`,
  `feat: implement LangGraph workflow`, `feat: add agent tools`
- **Checkpoint**: measure baseline latency (single request, sequential tools)

### Phase 2 — Concurrency & Caching (2 days)
- Parallelize independent tool calls (asyncio.gather)
- Add Redis: cache repeated question/date-range lookups, rate limiting
- Load test baseline vs parallel+cached (Locust, small scale e.g. 10-50 users)
- Commits: `feat: add asynchronous execution`, `feat: add Redis caching`, `perf: parallelize tool calls`
- **Checkpoint**: measure latency before/after, report actual cache hit rate

### Phase 3 — Background Jobs & Human-in-the-loop (2 days)
- Celery worker: full weekly report / batch anomaly scan (background, not hot path)
- LangGraph interrupt/resume: recommended actions require explicit approval
- Commits: `feat: add background workers`, `feat: add human-in-the-loop approval`

### Phase 4 — Reliability (1 day)
- Retries/backoff + timeouts around LLM and tool calls
- Graceful degradation (partial evidence if a tool fails)
- Commit: `feat: add retries and fallback handling`

### Phase 5 — Observability (2 days)
- OpenTelemetry tracing across agent/tools/DB/Redis
- Structured logging, token/cost tracking per request
- Commit: `feat: add observability`

### Phase 6 — Evaluation (1-2 days)
- Build ~20-30 question eval set with expected evidence/answers
- Score tool-selection accuracy, correctness, latency, cost across versions
- Commit: `test: add agent evaluation harness`

### Phase 7 — Docker & Reproducibility (1 day)
- Full docker-compose (API, Postgres, Redis, Celery worker)
- Fresh-machine test
- Commit: `feat: dockerize application`

### Phase 8 — Load Testing (2 days)
- Locust/k6: 10 → 50 → 100 → 500 (→1000 if feasible) concurrent requests
- Record actual p50/p95/p99, error rate, throughput — no invented numbers
- Commit: `test: add concurrent load testing`

### Phase 9 — CI/CD & Deployment (1-2 days)
- GitHub Actions: lint → test → build image → (deploy)
- Deploy to low-cost/free tier (Azure candidate, evaluate alternatives)
- Commits: `ci: add GitHub Actions pipeline`, `docs: add architecture and deployment documentation`

## Resume Bullet Targets (fill in only with measured results)
- Built an AI agent (LangGraph + FastAPI) that investigates operational
  anomalies via concurrent multi-tool reasoning, reducing p95 latency by
  measured __% through caching and parallel tool execution.
- Load-tested the system to ___ concurrent requests (Locust), achieving
  ___ p95 latency and ___% error rate; designed for horizontal scaling
  via stateless API workers and pooled connections.
- Implemented human-in-the-loop approval and reliability safeguards
  (retries, timeouts, fallback) around agent tool execution; built an
  evaluation harness showing ___% tool-selection accuracy.

## Open Decisions (finalize before coding starts)
- [ ] Confirm domain/schema above or adjust
- [ ] Define first 5-10 MVP investigation questions
- [ ] Choose deployment target (Azure vs alternative)
