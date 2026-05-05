# Incident Management System (IMS) — Technical Specification

**Version:** 1.0  
**Status:** Production  
**Authors:** Infrastructure / SRE Engineering  

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Goals](#2-goals)
3. [Non-Goals](#3-non-goals)
4. [High-Level Architecture](#4-high-level-architecture)
5. [Data Flow](#5-data-flow)
6. [Core Concepts](#6-core-concepts)
7. [Key Design Decisions](#7-key-design-decisions)
8. [Debouncing Logic](#8-debouncing-logic)
9. [Workflow Engine](#9-workflow-engine)
10. [Alerting System](#10-alerting-system)
11. [Backpressure Handling](#11-backpressure-handling)
12. [Scalability Approach](#12-scalability-approach)
13. [Observability](#13-observability)
14. [Data Models](#14-data-models)
15. [API Contract](#15-api-contract)
16. [Configuration Reference](#16-configuration-reference)
17. [Limitations](#17-limitations)
18. [Future Improvements](#18-future-improvements)

---

## 1. Problem Statement

Modern infrastructure systems — databases, message brokers, load balancers, compute clusters — emit continuous streams of health signals. These signals arrive in high volume and are often correlated: a single degraded database primary can generate hundreds of timeout errors per second from every dependent service simultaneously.

Without a structured pipeline to process these signals, three problems compound each other:

**Alert flooding.** On-call engineers receive hundreds of duplicate pages for the same underlying failure. Context is lost in noise, and response time increases proportionally.

**Lack of lifecycle structure.** Without a defined state machine, incidents live informally in chat channels and runbooks. There is no single source of truth for whether a problem is being investigated, has been resolved, or is confirmed closed.

**No enforced post-mortems.** Without mandatory Root Cause Analysis at closure, the same failures recur. MTTR (Mean Time To Repair) is never calculated systematically, making it impossible to track reliability improvements over time.

The Incident Management System (IMS) addresses all three problems. It provides a complete, production-grade pipeline from raw signal ingestion through structured incident lifecycle management to enforced RCA closure, surfaced through a live React dashboard.

---

## 2. Goals

**G1 — High-throughput ingestion.** Accept up to 10,000 signals per second per deployment without degrading API response latency. The ingestion endpoint must be non-blocking; no database writes should occur on the hot path.

**G2 — Intelligent signal grouping (debouncing).** Multiple signals for the same component within a configurable time window must be collapsed into a single active incident. A burst of 1,000 signals for one component must create exactly one WorkItem with an incrementing `signal_count`.

**G3 — Structured incident lifecycle.** Incidents must progress through a formally defined state machine: `OPEN → INVESTIGATING → RESOLVED → CLOSED`. Invalid transitions must be rejected at the API layer with a clear error. No out-of-order transitions are permitted.

**G4 — Mandatory RCA enforcement.** Transitioning an incident to `CLOSED` must be blocked unless a complete Root Cause Analysis record exists. RCA must include root cause, fix applied, prevention steps, a time range, and MTTR calculated from that range.

**G5 — Real-time dashboard.** The frontend must display active incidents sorted by severity, auto-refresh at a maximum interval of 5 seconds, and provide drill-down to signal history, current state, and RCA.

**G6 — Observability.** The system must expose structured JSON logs, a `/health` endpoint that actively probes all dependencies, and throughput metrics emitted on a regular interval.

**G7 — Resilience under partial failure.** If Redis becomes temporarily unavailable, the API must return a clear `503` rather than silently dropping signals. Worker crashes must not result in lost signals.

---

## 3. Non-Goals

**NG1 — Distributed message queue.** This system uses a Redis list as a work queue. There is no Kafka cluster, consumer group management, topic partitioning, or message replay. The architecture is intentionally designed so that the queue layer is an isolated module that could be swapped for Kafka without touching business logic.

**NG2 — Real alert delivery.** The `EmailAlertStrategy` and `SlackAlertStrategy` implementations log the alert intent rather than making external HTTP calls. No SMTP server, Slack webhook, or PagerDuty API key is required to run the system.

**NG3 — Multi-tenancy.** All resources (incidents, RCAs, signals) share a single namespace. There is no per-organisation isolation.

**NG4 — Authentication and authorisation.** The API is unauthenticated. In a production deployment, JWT-based auth with role separation (viewer, responder, admin) would be layered in front of these endpoints.

**NG5 — Long-term signal storage.** Raw signals are stored in a Redis list per incident with a practical limit of 2,000 entries. There is no cold storage tier, no archival pipeline, and no full-text search over historical signals.

---

## 4. High-Level Architecture

```
  Monitoring Probes / Load Generators
              |
              |  POST /signals
              |  (per-IP rate limit via Redis Lua INCR/EXPIRE)
              |  (backpressure if queue depth > threshold)
              v
  +----------------------------------+
  |      FastAPI Ingestion API       |   async, stateless, horizontally scalable
  |      (backend Docker service)    |
  +----------------------------------+
              |
              |  LPUSH  →  signal_queue  (Redis List)
              v
  +----------------------------------+
  |         Redis 7                  |   rate limit counters, debounce keys,
  |                                  |   signal queue, signal store, caches
  +----------------------------------+
              |
              |  BRPOP  (blocking pop, timeout 5 s)
              v
  +----------------------------------+
  |      Async Signal Worker         |   separate Docker service
  |      (worker Docker service)     |   stateless, horizontally scalable
  +----------------------------------+
        |                   |
        |                   |  LPUSH  signals:{work_item_id}
        |                   v
        |       +-------------------------+
        |       |   Redis Signal Store    |   raw signal JSON per incident
        |       +-------------------------+
        |
        |  SETNX  active_incident:{component_id}  TTL=debounce_window
        |
        |  upsert work_items / increment signal_count
        v
  +----------------------------------+
  |         PostgreSQL 16            |   work_items table, rcas table
  |   (source of truth for state)    |   async SQLAlchemy 2, Alembic migrations
  +----------------------------------+
        |
        |  read-through cache on API reads
        v
  +----------------------------------+
  |       Redis Cache Layer          |   dashboard:active_incidents  TTL=5s
  |                                  |   incident:{id}               TTL=30s
  +----------------------------------+
        |
        v
  +----------------------------------+
  |       React 18 Dashboard         |   Vite + Tailwind CSS 3 + Zustand
  |   (frontend Docker service)      |   Dashboard / Detail / RCA Form
  |   auto-refresh every 5 seconds   |
  +----------------------------------+
```

> Reference diagram: [`./architecture.png`](./architecture.png)

---

## 5. Data Flow

### 5.1 Signal ingestion path

1. A monitoring probe or synthetic monitor sends `POST /signals` with a JSON payload containing `component_id`, `severity`, `message`, and `timestamp`.
2. The API handler extracts the client IP (or `X-Forwarded-For` header behind a proxy).
3. A Redis Lua script atomically increments a per-IP counter with a 1-second expiry. If the counter exceeds `IMS_INGEST_RATE_LIMIT_PER_SEC`, the request is rejected with `HTTP 429`.
4. The API reads the Redis queue length via `LLEN signal_queue`. If it exceeds `IMS_SIGNAL_QUEUE_MAX_LENGTH`, the request is rejected with `HTTP 429 Queue overloaded`.
5. The signal payload is serialised to JSON and pushed to the Redis list via `LPUSH signal_queue`.
6. The API returns `HTTP 200 {"accepted": true}` immediately. Total API-side time is sub-millisecond under normal conditions.

### 5.2 Worker processing path

1. The worker calls `BRPOP signal_queue` with a 5-second timeout. This is a blocking call that returns immediately when a signal is available.
2. The worker attempts to acquire a per-component distributed lock: `SET lock:component:{component_id} {token} NX EX 8`. If the lock is not acquired (another worker replica is processing the same component), the signal is re-queued and skipped.
3. Inside the lock, the worker checks `GET active_incident:{component_id}`. If the key exists, its value is the UUID of an active `WorkItem`.
4. **On cache hit (debounce):** The existing `WorkItem` is updated — `signal_count` is incremented, `last_signal_time` is updated, severity is upgraded if the new signal is higher priority.
5. **On cache miss (new incident):** A new `WorkItem` is inserted into PostgreSQL with status `OPEN`. The Redis key `active_incident:{component_id}` is set with TTL equal to `IMS_DEBOUNCE_WINDOW_SECONDS`. An alert task is spawned asynchronously via `asyncio.create_task`.
6. The raw signal JSON is appended to the Redis list `signals:{work_item_id}` via `LPUSH`.
7. The per-incident detail cache (`incident:{work_item_id}`) is invalidated so the next API read rebuilds it with complete data.
8. The dashboard cache (`dashboard:active_incidents`) is refreshed with the latest active incident list from PostgreSQL.
9. The distributed lock is released.

### 5.3 Dashboard read path

1. The React frontend polls `GET /incidents` every 5 seconds.
2. The API checks `GET dashboard:active_incidents` in Redis.
3. On cache hit: the serialised incident list is returned directly. No database query is executed.
4. On cache miss: the API queries PostgreSQL for all non-closed `WorkItem` records ordered by severity rank and `updated_at DESC`, serialises the result, writes it to Redis with a 5-second TTL, and returns it.

### 5.4 Incident detail read path

1. The frontend calls `GET /incidents/{id}`.
2. The API checks `GET incident:{id}` in Redis. If the cached entry contains a non-empty `signals` list, it is returned directly.
3. On cache miss (or stale entry with no signals): the API fetches the `WorkItem` from PostgreSQL, retrieves up to 200 raw signals from `LRANGE signals:{id}`, fetches the RCA record if it exists, and assembles the complete response. If signals are still empty (worker has not processed the signal yet), the API retries with exponential back-off (0.3 s, 0.6 s, 1.0 s) before caching the result.
4. The assembled response is written to Redis with a 30-second TTL.

### 5.5 State transition path

1. The frontend calls `POST /incidents/{id}/state` with `{"action": "INVESTIGATING"}`.
2. The API fetches the current `WorkItem` from PostgreSQL.
3. The workflow service instantiates the current state object (e.g., `OpenState`) and calls the requested transition method (e.g., `to_investigating()`). If the transition is not permitted by the current state, `InvalidTransitionError` is raised and the API returns `HTTP 400`.
4. For the `CLOSED` transition, the workflow service additionally verifies that an RCA record exists for the incident. If not, the transition is blocked with `HTTP 400 Cannot close incident without completed RCA`.
5. The new status is committed to PostgreSQL.
6. Both the dashboard cache and the incident detail cache are invalidated.

---

## 6. Core Concepts

### Signal

A signal is a single observability event emitted by a monitored component. It carries a `component_id` (identifying the source), a `severity` (`P0`, `P1`, or `P2`), a human-readable `message`, and a UTC `timestamp`. Signals are ephemeral — they are stored in Redis for retrieval but are not the primary persistence target. PostgreSQL stores the aggregated `WorkItem`, not individual signals.

### WorkItem (Incident)

A `WorkItem` is the primary entity in the system. It represents a single active or resolved incident for a given component. Key fields:

| Field | Description |
|---|---|
| `id` | UUID primary key |
| `component_id` | Identifier of the affected component |
| `severity` | Highest severity observed across all signals (`P0`, `P1`, `P2`) |
| `status` | Current lifecycle state (`OPEN`, `INVESTIGATING`, `RESOLVED`, `CLOSED`) |
| `signal_count` | Total number of signals received for this incident |
| `first_signal_time` | Timestamp of the first signal that created this incident |
| `last_signal_time` | Timestamp of the most recently received signal |
| `title` | Human-readable summary (populated from the first signal's message) |

### RCA (Root Cause Analysis)

An RCA record has a one-to-one relationship with a `WorkItem`. It is created or updated via `POST /incidents/{id}/rca` and is required before an incident can transition to `CLOSED`. Fields:

| Field | Description |
|---|---|
| `root_cause` | Description of what caused the incident |
| `fix_applied` | Description of the remediation applied |
| `prevention_steps` | Steps to prevent recurrence |
| `start_time` | UTC timestamp when the incident began affecting users |
| `end_time` | UTC timestamp when service was restored |
| `mttr` | Calculated as `(end_time − start_time).total_seconds()` |

### MTTR

Mean Time To Repair is calculated deterministically from the RCA time range: `mttr = (end_time − start_time)` in seconds. This is a per-incident measurement, not a rolling average. Aggregated MTTR statistics over time windows are a planned future feature.

---

## 7. Key Design Decisions

### Redis list as work queue vs. Kafka

A Redis list provides `LPUSH` / `BRPOP` semantics with sub-millisecond latency and zero additional infrastructure. For a single-team deployment processing up to 10,000 signals per second with a single worker, this is more than sufficient. Kafka's operational overhead (broker cluster, ZooKeeper or KRaft, topic and partition management, consumer group coordination) is disproportionate to the current scale requirement.

The queue layer is isolated in `app/services/queue_service.py`. Replacing it with a Kafka consumer requires changes only to that module and the worker's pop loop — no business logic, state machine, or database code changes.

### Async FastAPI over Django or Flask

Both signal ingestion and dashboard reads are I/O-bound workloads. Using a synchronous framework would require a thread pool for concurrency, introducing per-thread memory overhead and context switching. FastAPI on `asyncio` allows a single event loop to multiplex thousands of in-flight I/O operations. Every database call uses `await session.execute(...)` via `asyncpg`; every Redis call uses the `redis-py` async client. There are no blocking calls in the hot path.

### Separate ingestion API and processing worker

Combining ingestion and processing in a single FastAPI background task would tie processing latency to API response latency. A slow or crash-looping processing step would degrade ingestion throughput. Separating them into independent Docker services means each can be scaled, restarted, and resource-limited independently. The Redis queue acts as a durable buffer between the two, absorbing bursts without any coupling.

### Read-through Redis cache for dashboard and detail

The React dashboard polls every 5 seconds. Without a cache, each poll would issue a PostgreSQL query under active incident load. The dashboard cache (5-second TTL) means the worst-case database load from N frontend clients is one query every 5 seconds regardless of N. The incident detail cache (30-second TTL) similarly bounds per-incident query load. Both caches are invalidated immediately on state transitions, ensuring consistency within the TTL window.

---

## 8. Debouncing Logic

Debouncing prevents a single component failure from generating thousands of separate incidents. The implementation uses a Redis key with a TTL as a deduplication token.

**Key:** `active_incident:{component_id}`  
**Value:** The UUID of the active `WorkItem` for this component  
**TTL:** `IMS_DEBOUNCE_WINDOW_SECONDS` (default: 10 seconds)

**New incident:** When the worker processes a signal and finds no key for the component, it creates a new `WorkItem` in PostgreSQL and writes the key with the configured TTL. An alert is fired once, at creation time.

**Existing incident:** When the worker finds the key, it updates the existing `WorkItem` — incrementing `signal_count`, updating `last_signal_time`, and potentially upgrading `severity`. No new `WorkItem` is created and no alert is fired.

**TTL expiry:** If no signals arrive for a component within the debounce window, the Redis key expires. The next signal for that component will create a new `WorkItem`. This models the real-world assumption that a sustained absence of signals indicates recovery.

**Concurrency safety:** The worker acquires a per-component distributed lock (`SET lock:component:{component_id} {token} NX EX 8`) before the debounce check. This prevents two worker replicas from simultaneously creating duplicate `WorkItem` records for the same component.

---

## 9. Workflow Engine

### State Pattern implementation

The incident lifecycle is implemented using the State Design Pattern. Each state is a class that inherits from `BaseState` and implements the three transition methods: `to_investigating()`, `to_resolved()`, and `to_closed()`. The base implementation of each method raises `InvalidTransitionError`. Subclasses override only the transitions they permit.

```
BaseState (abstract)
├── OpenState          permits: to_investigating()
├── InvestigatingState permits: to_resolved()
├── ResolvedState      permits: to_closed()
└── ClosedState        permits: (none — terminal state)
```

`WorkItemStateContext` holds a reference to the current state instance and delegates all transition calls to it. The calling code never contains conditional logic on the current status value. Adding a new state (e.g., `ESCALATED`) requires only a new class and updates to the states it connects to — no changes to existing state classes or the API layer.

### Valid transitions

| From | To | Permitted |
|---|---|---|
| OPEN | INVESTIGATING | Yes |
| OPEN | RESOLVED | No |
| OPEN | CLOSED | No |
| INVESTIGATING | RESOLVED | Yes |
| INVESTIGATING | CLOSED | No |
| INVESTIGATING | OPEN | No |
| RESOLVED | CLOSED | Yes (requires RCA) |
| RESOLVED | INVESTIGATING | No |
| CLOSED | any | No (terminal) |

### RCA gate on closure

The `workflow_service.transition_to_closed()` function queries the `rcas` table for a record with `work_item_id` matching the incident before delegating to the state machine. If no record exists, the function raises `ValueError("Cannot close incident without completed RCA")` before any state transition is attempted. This enforcement is at the service layer, not the state machine layer, keeping the two concerns separate.

---

## 10. Alerting System

### Strategy Pattern implementation

Alert delivery is implemented using the Strategy Design Pattern. The `AlertStrategy` abstract base class defines a single method: `async def send_alert(work_item: WorkItem) -> None`. Three concrete strategies are provided:

**`EmailAlertStrategy`** — logs an email alert event with recipient, subject, and severity metadata.  
**`SlackAlertStrategy`** — logs a Slack notification event with channel and severity metadata.  
**`CombinedAlertStrategy`** — composes any number of strategies and executes them concurrently via `asyncio.gather`.

### Severity-based strategy selection

The active strategy for each severity level is determined by the `IMS_ALERT_STRATEGY_MAP_JSON` environment variable, which accepts a JSON object:

```json
{"P0": "combined", "P1": "slack", "P2": "email"}
```

The factory function `get_alert_strategy(severity)` reads this map and returns the appropriate strategy instance. This allows alert routing to be reconfigured at deployment time without code changes. Adding PagerDuty or OpsGenie requires only a new class implementing `AlertStrategy`.

### Non-blocking delivery

Alerts are fired via `asyncio.create_task(send_alert_non_blocking(wi))` inside the worker. The task runs concurrently in the same event loop but does not block signal processing. If an alert strategy raises an exception, it is caught and logged — it does not cause the worker to requeue the signal.

---

## 11. Backpressure Handling

The system has three independent layers of backpressure, applied in order during signal ingestion:

**Layer 1 — Per-IP rate limiting.**  
A Redis Lua script atomically executes `INCR rate_limit:{client_ip}` followed by `EXPIRE rate_limit:{client_ip} 1` (only on the first increment). If the returned counter exceeds `IMS_INGEST_RATE_LIMIT_PER_SEC` (default: 2,000), the API returns `HTTP 429 Rate limit exceeded`. Because the counter lives in Redis, the limit is enforced consistently across all API replicas without any shared in-process state. The Lua script ensures the INCR and EXPIRE are atomic.

**Layer 2 — Queue depth threshold.**  
Before pushing to the queue the API reads `LLEN signal_queue`. If the queue depth exceeds `IMS_SIGNAL_QUEUE_MAX_LENGTH` (default: 50,000), the API returns `HTTP 429 Queue overloaded`. This prevents Redis from consuming unbounded memory when the worker falls behind the ingestion rate. The threshold is a soft limit — a brief overshoot is possible in concurrent scenarios, but the average is bounded.

**Layer 3 — Redis unavailability.**  
If the Redis client is not initialised or a connection error occurs during the rate limit check or queue push, the API returns `HTTP 503 Redis unavailable`. Signals are not silently dropped — the client receives an explicit error and can retry.

**Why the system does not crash under load:**  
The ingestion API process never allocates unbounded memory for incoming signals. Every signal is immediately serialised and pushed to Redis or rejected. Under sustained overload, requests are rejected with clear HTTP status codes and the `rejected_backpressure` metric counter is incremented. The processing worker runs at its own pace and is never directly in the request-response cycle.

---

## 12. Scalability Approach

### Horizontal scaling of the ingestion API

The ingestion API is stateless — all state lives in Redis and PostgreSQL. Running N replicas behind a load balancer increases ingestion throughput linearly. The Redis-based rate limiter is cluster-aware because the counters live in shared Redis, not in-process.

### Horizontal scaling of the worker

Multiple worker replicas can run concurrently. Each replica issues `BRPOP` independently; Redis distributes signals across replicas. The per-component distributed lock (`SET NX EX`) prevents two replicas from creating duplicate incidents for the same component. Adding replicas increases processing throughput for distinct components with no code changes.

### Cache as throughput multiplier

Under read-heavy dashboard load (many engineers viewing incidents simultaneously), the Redis cache absorbs all reads after the first cache population. The database sees at most one query per TTL window per cache key, regardless of the number of API instances or active dashboard clients.

### Async architecture limits thread overhead

A single FastAPI process running on a multi-core host with `uvicorn --workers N` can handle tens of thousands of concurrent connections. Each in-flight request is a coroutine, not a thread, consuming kilobytes of stack rather than megabytes.

---

## 13. Observability

### Health endpoint

`GET /health` actively probes both PostgreSQL and Redis before responding. The database check issues `SELECT 1` via a new connection acquired from the async engine pool. The Redis check issues `PING`. The response includes:

```json
{
  "status": "ok | degraded | down",
  "services": {
    "database": "connected | down",
    "redis": "connected | down"
  },
  "timestamp": "<ISO 8601 UTC>"
}
```

`degraded` is returned when exactly one service is reachable. `down` is returned when neither is reachable. Both states log a `CRITICAL`-level structured event for external alerting.

### Structured JSON logging

All log output uses `python-json-logger` with a consistent schema:

```json
{
  "asctime": "2026-05-05 17:21:51,242",
  "levelname": "INFO",
  "name": "app.services.cache_service",
  "service": "ims-backend",
  "message": "Cache hit",
  "cache": "dashboard"
}
```

A `ServiceFilter` on the root logger injects the `service` field (`ims-backend` or `ims-worker`) into every record without requiring callers to pass it explicitly. The log level is controlled by `IMS_LOG_LEVEL` at runtime.

### Per-request HTTP middleware

A FastAPI middleware records `method`, `path`, `status_code`, and `duration_ms` for every HTTP request at `INFO` level. This provides request tracing without an external APM agent.

### Throughput metrics loop

A background `asyncio` task (`metrics_loop`) runs every `IMS_METRICS_PRINT_INTERVAL_SECONDS` seconds (default: 5). It snapshots and resets atomic counters, fetches the current queue depth, and emits a single structured log event:

```json
{
  "message": "Throughput metrics",
  "interval_s": 5,
  "signals_ingested": 312,
  "signals_per_sec": 62.4,
  "rejected_rate_limited": 0,
  "rejected_backpressure": 0,
  "rejected_redis_down": 0,
  "queue_length": 14
}
```

---

## 14. Data Models

### work_items

```sql
CREATE TABLE work_items (
    id                UUID PRIMARY KEY,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    component_id      VARCHAR(128) NOT NULL,
    severity          severity_level NOT NULL,
    status            work_item_status NOT NULL DEFAULT 'OPEN',
    title             VARCHAR(160) NOT NULL,
    description       TEXT,
    first_signal_time TIMESTAMPTZ NOT NULL,
    last_signal_time  TIMESTAMPTZ NOT NULL,
    signal_count      INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX ix_work_items_component_id ON work_items (component_id);
CREATE INDEX ix_work_items_severity ON work_items (severity);
CREATE INDEX ix_work_items_status ON work_items (status);
CREATE INDEX ix_work_items_component_id_created_at ON work_items (component_id, created_at);
```

### rcas

```sql
CREATE TABLE rcas (
    id                UUID PRIMARY KEY,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    work_item_id      UUID NOT NULL UNIQUE REFERENCES work_items(id) ON DELETE CASCADE,
    root_cause        TEXT NOT NULL,
    fix_applied       TEXT NOT NULL,
    prevention_steps  TEXT NOT NULL,
    start_time        TIMESTAMPTZ NOT NULL,
    end_time          TIMESTAMPTZ NOT NULL,
    mttr              DOUBLE PRECISION NOT NULL
);

CREATE INDEX ix_rcas_work_item_id ON rcas (work_item_id);
```

---

## 15. API Contract

### POST /signals

**Request:**
```json
{
  "component_id": "RDBMS_PRIMARY_01",
  "severity": "P0",
  "message": "Connection pool exhausted",
  "timestamp": "2026-05-05T12:00:00+00:00"
}
```

**Response 200:**
```json
{"accepted": true}
```

**Response 429:** Rate limit exceeded or queue overloaded.  
**Response 503:** Redis unavailable.

---

### GET /health

**Response 200:**
```json
{
  "status": "ok",
  "services": {"database": "connected", "redis": "connected"},
  "timestamp": "2026-05-05T17:21:47.351066+00:00"
}
```

---

### GET /incidents

**Response 200:** Array of active `WorkItem` summaries sorted by severity rank then `updated_at DESC`.

```json
[
  {
    "id": "uuid",
    "component_id": "RDBMS_PRIMARY_01",
    "severity": "P0",
    "status": "INVESTIGATING",
    "signal_count": 47,
    "last_updated": "2026-05-05T17:00:00+00:00"
  }
]
```

---

### GET /incidents/{id}

**Response 200:** Full incident detail including signals and RCA.

```json
{
  "id": "uuid",
  "component_id": "RDBMS_PRIMARY_01",
  "severity": "P0",
  "status": "RESOLVED",
  "title": "Connection pool exhausted",
  "signal_count": 47,
  "first_signal_time": "...",
  "last_signal_time": "...",
  "signals": [{"component_id": "...", "message": "...", "timestamp": "..."}],
  "rca": null
}
```

**Response 404:** Incident not found.

---

### POST /incidents/{id}/state

**Request:**
```json
{"action": "INVESTIGATING"}
```

**Response 200:** Updated `WorkItem` with new status.  
**Response 400:** Invalid transition or missing RCA for CLOSED.  
**Response 404:** Incident not found.

---

### POST /incidents/{id}/rca

**Request:**
```json
{
  "root_cause": "...",
  "fix_applied": "...",
  "prevention_steps": "...",
  "start_time": "2026-05-05T14:00:00+00:00",
  "end_time": "2026-05-05T15:30:00+00:00"
}
```

**Response 200:** Persisted RCA record including calculated `mttr` in seconds.  
**Response 400:** Validation failure (missing fields, `end_time` before `start_time`).

---

## 16. Configuration Reference

| Environment Variable | Default | Description |
|---|---|---|
| `IMS_DATABASE_URL` | `postgresql+asyncpg://ims:ims@localhost:5432/ims` | Async PostgreSQL connection string |
| `IMS_REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `IMS_LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |
| `IMS_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed CORS origins |
| `IMS_INGEST_RATE_LIMIT_PER_SEC` | `2000` | Max signals per client IP per second before 429 |
| `IMS_SIGNAL_QUEUE_MAX_LENGTH` | `50000` | Queue depth threshold for backpressure |
| `IMS_DEBOUNCE_WINDOW_SECONDS` | `10` | Duration during which signals for a component map to one incident |
| `IMS_DASHBOARD_CACHE_TTL_SECONDS` | `5` | TTL for the active incidents dashboard cache |
| `IMS_INCIDENT_CACHE_TTL_SECONDS` | `30` | TTL for the per-incident detail cache |
| `IMS_METRICS_PRINT_INTERVAL_SECONDS` | `5` | Interval for throughput metrics emission |
| `IMS_REDIS_MAX_RETRIES` | `5` | Redis connection retry attempts on startup |
| `IMS_REDIS_RETRY_BASE_DELAY_MS` | `200` | Base delay for Redis retry back-off in milliseconds |
| `IMS_REDIS_SOCKET_TIMEOUT_SECONDS` | `15` | Redis socket timeout (must exceed BRPOP timeout) |
| `IMS_ALERT_STRATEGY_MAP_JSON` | `{"P0":"combined","P1":"slack","P2":"email"}` | JSON map of severity to alert strategy |

---

## 17. Limitations

**No persistent signal storage beyond Redis.**  
Raw signals are stored in Redis lists with a practical cap of 2,000 entries per incident. Signals beyond this cap are dropped from the store (LTRIM). Historical signal data older than the Redis TTL or beyond the list limit is not recoverable. A production deployment would require a time-series database or cold storage tier.

**No message replay on worker crash.**  
If the worker process crashes after popping a signal from the queue but before completing processing, that signal is lost. The current implementation re-pushes on processing errors, but a mid-crash scenario is not covered. A Kafka-based queue with consumer group offsets would provide at-least-once delivery guarantees.

**No real alert delivery.**  
Alert strategies log their intent but do not make external HTTP calls. Integrating real delivery requires implementing the `send_alert` method on new strategy classes and providing API credentials via environment variables.

**Single Redis instance.**  
There is no Redis Sentinel or Redis Cluster configuration. If the Redis instance becomes unavailable, signal ingestion returns `503` and the worker pauses. A production deployment should use Redis Sentinel (for failover) or Redis Cluster (for sharding).

**Debounce window is fixed per deployment.**  
The debounce window is a global setting. Different components with different expected recovery times cannot have different windows. A per-component configurable window would require a lookup layer.

---

## 18. Future Improvements

| Improvement | Rationale |
|---|---|
| Kafka-backed queue | At-least-once delivery, consumer group semantics, message replay, and independent scaling of ingestion from processing |
| WebSocket push | Replace 5-second polling with server-push for zero-latency incident updates on the dashboard |
| Prometheus `/metrics` endpoint | Expose `signals_ingested_total`, `queue_depth`, `mttr_seconds_histogram` for Grafana dashboards |
| PagerDuty / OpsGenie integration | Implement concrete `AlertStrategy` subclasses that call external paging APIs |
| Signal deduplication | Add a bloom filter keyed on signal content hash to drop byte-for-byte duplicate signals before they enter the queue |
| JWT authentication | Role-based access: `viewer` (read-only), `responder` (state transitions), `admin` (all) |
| Per-component debounce window | Store debounce window overrides in PostgreSQL or a config service, looked up by `component_id` at processing time |
| Aggregated MTTR reporting | Rolling MTTR averages by component, severity, and time window for reliability trend analysis |
| Multi-tenancy | Namespace all resources by organisation; partition Redis keys and PostgreSQL rows by `org_id` |
| Elasticsearch signal index | Full-text search over signal messages and RCA text fields for post-incident investigation |
