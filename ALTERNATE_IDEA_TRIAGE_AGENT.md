# Alternate Idea (Not Selected): Support Triage + Autonomous Resolution Agent

> Kept for reference only. The selected flagship project is the **Enterprise
> AI Operations Investigation Agent** (see `PROJECT_PLAN.md` / `ARCHITECTURE.md`).
> One idea from this concept — human-in-the-loop approval before executing
> sensitive actions — has already been folded into the selected project.

## Problem
Support tickets need classification, prioritization, and for a subset,
autonomous resolution (refund lookup, order status, account reset) via real
backend "tools," escalating to humans when uncertain.

## Target Users
Support ops teams at a SaaS/e-commerce company.

## Why an Agent Is Needed
Must decide classify → route → attempt tool-based resolution →
escalate/wait-for-human — a genuine decision tree, not simple Q&A.

## Tools
- `classify_ticket`
- `order_lookup`
- `refund_processor` (mock but stateful in Postgres)
- `kb_search` (lightweight retrieval, not centerpiece)
- `escalate_to_human`
- `send_notification`

## Why LangGraph
Human-in-the-loop is a first-class feature here — pause the graph, wait for
human approval on refunds above a threshold, resume. This is one of
LangGraph's actual differentiators, more so than a plain routing graph.

## Where Redis Fits
- Distributed lock / idempotency for ticket processing (avoid double-refunds
  if two workers pick up the same event)
- Pub/sub for real-time ticket status to a dashboard
- Rate limiting per customer

## Where Celery Fits
- Ticket ingestion pipeline (webhook → queue → async processing)
- SLA breach checker (periodic task)
- Bulk re-triage jobs

## How Concurrency Appears
Many tickets processed concurrently; must guarantee no duplicate actions
(idempotency keys) — a strong, defensible reliability story.

## How Latency Becomes an Engineering Problem
Less about raw speed, more about throughput and correctness under
concurrent load — a different flavor than a pure latency-optimization story.

## How It Scales
Event-driven architecture (webhook → queue → worker) is naturally
horizontally scalable; ticket ingestion is straightforward to load test.

## MVP Scope
Classify ticket + single tool action (e.g., order lookup), no human-in-loop yet.

## Production Phase Additions
Approval workflows, idempotency guarantees, SLA monitoring, escalation
paths, evaluation on classification accuracy + resolution success rate.

## Why Attractive for ₹12–20 LPA Roles
Support automation is a large, real-world category (Intercom Fin, Sierra,
Decagon are funded startups doing exactly this) — very relatable to
interviewers, and idempotency-under-concurrency is a rarer, senior-signal
differentiator most candidates don't demonstrate.

## Interview Questions It Enables
- "How do you prevent double-refunds under concurrent processing?"
- "How do you design human-in-the-loop approval without blocking the whole system?"
- "How do you guarantee idempotency across distributed workers?"

## Why It Was Not Selected as the Flagship
- More "workflow automation / backend ops engineer" flavored than "AI agent
  reasoning" flavored — harder to demo live and impressively in 5-10 minutes.
- Its standout value (no double-actions, idempotency) is something you
  *explain*, not something you *show* — weaker as an interview live-demo.
- The Ops Investigation Agent gives a comparable (arguably stronger)
  concurrency/reliability story (parallel tool calls, caching, background
  jobs) while also being visibly more "agentic" (multi-step reasoning over
  evidence) — a better match for "AI Engineer" role framing specifically.
- Its best single differentiator (human-in-the-loop approval gate) was
  folded into the Ops Investigation Agent instead of building a second,
  separate project.
