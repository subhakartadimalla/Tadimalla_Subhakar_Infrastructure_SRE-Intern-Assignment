# Incident Management System (IMS)

**A production-grade, async-first incident lifecycle platform — from signal ingestion to root cause closure.**

---

## Overview

Modern infrastructure systems generate thousands of health signals per second. Without a structured pipeline, these signals become noise: duplicate alerts fire, on-call engineers are flooded, and mean time to resolution (MTTR) balloons.

The Incident Management System (IMS) solves this by providing a complete, production-ready platform that ingests raw signals at high throughput, debounces them into actionable incidents, enforces a structured resolution workflow, and mandates a root cause analysis before an incident can be closed. The entire system is built with the same architectural principles used by SRE teams at large-scale infrastructure companies.

**What it does:**

- Accepts high-frequency health signals from any probe or monitoring agent via a rate-limited HTTP API
- Collapses burst signals for the same component into a single active incident using Redis-backed debouncing
- Walks incidents through a strictly enforced state machine: `OPEN → INVESTIGATING → RESOLVED → CLOSED`
- Blocks incident closure until a complete Root Cause Analysis is submitted and MTTR is calculated
- Surfaces everything through a live React dashboard with auto-refresh, drill-down views, and inline RCA forms

---

## Architecture


![Incident Management System Architecture](./docs/architecture.png)

```
  Monitoring Probes / Load Generators
              |
              |  POST /signals
              |  (rate-limited per client IP, backpressure on queue depth)
              v
  +--------------------------+
  |   FastAPI Ingestion API  |   async, non-blocking
  +--------------------------+
              |
              |  LPUSH  (Redis List)
              v
  +--------------------------+
  |      Redis Signal Queue  |   bounded, backpressure threshold = 50 000
  +--------------------------+
              |
              |  BRPOP (blocking pop, timeout = 5 s)
              v
  +--------------------------+
  |   Async Signal Worker    |   separate Docker service, stateless
  +--------------------------+
        |              |
        |              |  append_raw_signal  (Redis List per incident)
        |              v
        |   +---------------------+
        |   |  Redis Signal Store |   signals:{incident_id}  (LRANGE for detail view)
        |   +---------------------+
        |
        |  debounce check  →  active_incident:{component_id}  (TTL = 10 s)
        |
        |  upsert WorkItem / increment signal_count
        v
  +--------------------------+
  |      PostgreSQL 16       |   source of truth for incidents, workflow state, RCA
  |  work_items + rcas       |
  +--------------------------+
        |
        |  read-through cache  (dashboard TTL = 5 s, incident TTL = 30 s)
        v
  +--------------------------+
  |      Redis Cache Layer   |   dashboard:active_incidents  /  incident:{id}
  +--------------------------+
        |
        v
  +--------------------------+
  |   React 18 Dashboard     |   Vite + Tailwind CSS + Zustand + React Router
  |   Auto-refresh 5 s       |   Dashboard  /  Detail  /  RCA Form
  +--------------------------+
```

> A high-resolution architecture diagram is available at [`./docs/architecture.png`](./docs/architecture.png).

---

## Tech Stack

### Backend

| Component | Technology | Version |
|---|---|---|
| API framework | FastAPI (async) | 0.115 |
| ORM | SQLAlchemy (async) | 2.0 |
| Database | PostgreSQL | 16 |
| Cache / Queue | Redis | 7 |
| Migrations | Alembic | 1.13 |
| Validation | Pydantic v2 | 2.8 |
| Runtime | Python | 3.11+ |
| ASGI server | Uvicorn | 0.30 |

### Frontend

| Component | Technology |
|---|---|
| Framework | React 18 (Vite) |
| Styling | Tailwind CSS 3 |
| HTTP client | Axios |
| State management | Zustand |
| Routing | React Router v6 |

### Infrastructure

| Component | Technology |
|---|---|
| Containerisation | Docker + Docker Compose v2 |
| Database persistence | Named Docker volume |
| Service discovery | Docker internal DNS |

---

## Key Features

**High-throughput signal ingestion**
The ingestion endpoint is intentionally minimal and non-blocking. It validates the payload, checks the rate limit via an atomic Lua script in Redis, optionally enforces backpressure, pushes the signal to a Redis list, and returns in under 1 ms. No database writes happen on the hot path.

**Debouncing — N signals become 1 incident**
When the worker pops a signal it checks for a Redis key `active_incident:{component_id}` with a configurable TTL (default 10 seconds). If the key exists the signal is attached to the existing incident and `signal_count` is incremented atomically. If the key is absent a new incident is created. A burst of 1 000 signals for the same component within the window produces exactly one incident.

**Strict incident lifecycle — State Design Pattern**
`WorkItem` state transitions are enforced by a classic State Design Pattern. Each state class (`OpenState`, `InvestigatingState`, `ResolvedState`, `ClosedState`) exposes only the transitions it permits. Calling `to_closed()` from `INVESTIGATING` raises `InvalidTransitionError` — no if-else chains, no raw string comparisons.

**Alert routing — Strategy Design Pattern**
When a new incident is created the worker fires an alert asynchronously via `asyncio.create_task` (non-blocking). The strategy is selected from a configurable JSON map: `P0 → Slack + Email (combined)`, `P1 → Slack`, `P2 → Email`. Strategies share the `AlertStrategy` ABC, making it trivial to add PagerDuty, OpsGenie, or any other channel.

**Mandatory RCA enforcement**
A `POST /incidents/{id}/state` request with `action: CLOSED` is rejected with `HTTP 400` unless a complete RCA record exists for the incident. The RCA requires `root_cause`, `fix_applied`, `prevention_steps`, `start_time`, and `end_time`. MTTR is calculated automatically as `(end_time − start_time)` in seconds and persisted alongside the RCA.

**Redis read-through caching**
`GET /incidents` is served from a Redis dashboard cache with a 5-second TTL. `GET /incidents/{id}` is served from a per-incident cache with a 30-second TTL. Both caches are invalidated on every state transition and refreshed by the worker after each signal is processed, ensuring stale reads are bounded.

**Structured observability**
Every log line is emitted as JSON with fields `asctime`, `levelname`, `name`, `service`, `message`, and any structured `extra` fields. A per-request HTTP middleware logs `method`, `path`, `status_code`, and `duration_ms` for every call. A background `metrics_loop` emits `signals_ingested`, `signals_per_sec`, `queue_length`, and rejection counters every 5 seconds.

---

## System Flow

**1. Signal arrives**
A probe or synthetic monitor posts to `POST /signals`. The API extracts the client IP, checks the Redis rate limit (1 000 req/s per IP by default), verifies queue depth is below the backpressure threshold (50 000), and pushes the serialised signal onto the `signal_queue` Redis list. The response is returned immediately — no database interaction.

**2. Queue buffering**
The Redis list acts as a durable, ordered buffer between the ingestion API and the processing worker. The list is bounded via application-level backpressure. If the API pod crashes mid-flight, signals already in the queue are preserved until the worker reconnects.

**3. Worker processing**
A separate Docker service runs an `asyncio` event loop that repeatedly calls `BRPOP signal_queue` with a 5-second timeout. When a signal arrives the worker acquires a per-component distributed lock (Redis `SET NX EX`) to prevent concurrent processing of the same component across multiple worker instances.

**4. Debouncing and incident creation**
Inside the lock the worker checks `active_incident:{component_id}`. On a hit the existing `WorkItem` is updated (`signal_count`, `last_signal_time`, severity). On a miss a new `WorkItem` is inserted into PostgreSQL, the debounce key is set with the configured TTL, and an alert task is spawned. Raw signal JSON is appended to `signals:{work_item_id}` in Redis for later retrieval.

**5. Incident triage (dashboard → detail)**
The React dashboard polls `GET /incidents` every 5 seconds. Incidents are sorted by severity (`P0 → P1 → P2`) then by most recently updated. Clicking an incident opens `GET /incidents/{id}`, which returns the full `WorkItem`, the paginated signal list (up to 200 entries from Redis), the current state, and the RCA if one exists.

**6. State transitions**
From the detail page an engineer clicks a transition button. The frontend calls `POST /incidents/{id}/state`. The backend instantiates the current state object, calls the requested transition method, persists the new status to PostgreSQL, and invalidates all related caches. Invalid transitions return `HTTP 400` with a human-readable message.

**7. RCA submission and closure**
The engineer navigates to the RCA form, fills in timeline fields and written analysis, and submits. `POST /incidents/{id}/rca` validates all fields, calculates MTTR, and persists the record. The engineer then transitions to `CLOSED`. The backend verifies the RCA exists before committing the final status change.

---

## Backpressure and Resilience

The system is designed to degrade gracefully rather than crash under load.

**Rate limiting**
An atomic Lua script (`INCR` + `EXPIRE`) maintains a per-client-IP counter in Redis that resets every second. Requests exceeding the threshold (`IMS_INGEST_RATE_LIMIT_PER_SEC`, default 1 000) receive `HTTP 429 Rate limit exceeded`. Because the counter is maintained in Redis, the limit is enforced consistently across multiple API replicas without any shared in-process state.

**Queue backpressure**
Before pushing to the queue the API reads the current queue depth with `LLEN`. If the depth exceeds `IMS_SIGNAL_QUEUE_MAX_LENGTH` (default 50 000) the request is rejected with `HTTP 429 Queue overloaded`. This prevents the Redis instance from consuming unbounded memory when the worker falls behind the ingestion rate.

**Redis unavailability**
If the Redis client is not initialised or a connection attempt fails, the ingestion endpoint returns `HTTP 503 Redis unavailable` rather than silently dropping or misrouting signals. The worker retries `BRPOP` in a tight loop with exception logging, resuming automatically when Redis recovers.

**Worker crash recovery**
If the worker raises an unhandled exception while processing a signal, the signal is re-pushed to the queue before the exception propagates. This means no signal is silently lost due to a transient processing error.

**Connection retry on startup**
Both the database engine and the Redis client implement exponential back-off with jitter on startup (up to `IMS_REDIS_MAX_RETRIES` attempts, base delay `IMS_REDIS_RETRY_BASE_DELAY_MS` ms). The backend container will not mark itself healthy until connections are established, and Docker Compose health checks on PostgreSQL and Redis prevent premature startup.

---

## Scalability Design

**Async-first throughout**
Every I/O operation — database queries, Redis calls, HTTP responses — uses `await`. The FastAPI process runs a single-threaded event loop that can handle thousands of concurrent connections without spawning OS threads. Blocking calls in the hot path do not exist.

**Hot path is Redis-only**
Signal ingestion touches Redis once (rate limit check) and once more (queue push). PostgreSQL is never in the critical path for ingestion. This means the ingestion API can sustain extremely high request rates as long as the Redis instance is healthy, regardless of database load.

**Separation of ingestion and processing**
The API and worker are deployed as independent Docker services. Under sustained load the worker can be horizontally scaled by running multiple replicas — each replica competes for signals via `BRPOP` and the per-component distributed lock prevents duplicate processing. The ingestion API can be scaled independently behind a load balancer.

**Read-through cache for dashboard**
The React dashboard never issues a cold PostgreSQL query under normal operation. The dashboard cache is refreshed by the worker after each signal and expires after 5 seconds, meaning the worst-case read latency is a single Redis `GET` plus a bounded PostgreSQL query every 5 seconds regardless of how many API instances are running.

---

## Non-Functional Characteristics

| Characteristic | Implementation |
|---|---|
| Distributed locking | Redis `SET NX EX` per `component_id`; prevents duplicate incident creation under concurrent workers |
| Retry with back-off | Exponential back-off with jitter for Redis and PostgreSQL connection establishment at startup |
| Structured logging | JSON logs via `python-json-logger`; every line includes `service`, `level`, `name`, and structured `extra` fields |
| Request tracing | HTTP middleware records `method`, `path`, `status_code`, `duration_ms` for every request |
| Throughput metrics | Background loop emits `signals/sec`, `queue_length`, `rejected_rate_limited`, `rejected_backpressure` every 5 seconds |
| Health monitoring | `GET /health` actively pings PostgreSQL (`SELECT 1`) and Redis (`PING`); returns `ok / degraded / down` with per-service detail |
| Graceful shutdown | FastAPI lifespan events close database engine and Redis connection pool on `SIGTERM` |
| Schema validation | Pydantic v2 validates all request and response payloads; field-level errors are surfaced to the client |

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/signals` | Ingest a raw signal. Rate-limited. Non-blocking. Returns immediately. |
| `GET` | `/health` | Service health check. Returns status of database and Redis. |
| `GET` | `/incidents` | List active (non-closed) incidents. Sorted by severity then recency. Redis-cached. |
| `GET` | `/incidents/{id}` | Full incident detail: metadata, signal list (up to 200), current state, RCA. |
| `POST` | `/incidents/{id}/state` | Transition incident state. Body: `{"action": "INVESTIGATING" | "RESOLVED" | "CLOSED"}`. |
| `POST` | `/incidents/{id}/rca` | Submit or update Root Cause Analysis. Calculates and persists MTTR. |
| `GET` | `/incidents/{id}/rca` | Retrieve the RCA record for an incident. |

Interactive API docs are available at `http://localhost:8000/docs` when the system is running.

---

## Getting Started

### Prerequisites

- Docker Desktop (macOS / Windows) or Docker Engine + Docker Compose v2 (Linux)
- No local Python or Node installation required — everything runs inside containers

### Run the full stack

```bash
git clone <repository-url>
cd ims-project
docker-compose up --build
```

Docker Compose will:
1. Start PostgreSQL 16 and Redis 7, waiting for their health checks to pass
2. Run Alembic migrations to create the `work_items` and `rcas` tables
3. Start the FastAPI backend on port `8000`
4. Start the async signal worker
5. Start the React frontend dev server on port `5173`

| Service | URL |
|---|---|
| Frontend dashboard | `http://localhost:5173` |
| Backend API | `http://localhost:8000` |
| Health endpoint | `http://localhost:8000/health` |
| Interactive API docs | `http://localhost:8000/docs` |

### Stop the stack

```bash
docker-compose down
```

To also remove the persisted database volume:

```bash
docker-compose down -v
```

---

## Simulating Failures and Load

### Quick signal injection

```bash
curl -X POST http://localhost:8000/signals \
  -H 'Content-Type: application/json' \
  -d '{
    "component_id": "RDBMS_PRIMARY_01",
    "severity": "P0",
    "message": "Connection pool exhausted",
    "timestamp": "2026-05-05T12:00:00+00:00"
  }'
```

### Debounce verification script

The `scripts/simulate_failure.py` script sends a configurable burst of signals for a single component and reports how many were accepted, rate-limited, or errored. Use it to verify that N signals produce exactly one incident.

```bash
# Requires httpx: pip install httpx
python3 scripts/simulate_failure.py --count 50 --severity P0 --component RDBMS_PRIMARY_01
```

Expected output:

```
Sending 50 signals for component=RDBMS_PRIMARY_01 severity=P0 → http://localhost:8000
----------------------------------------
  Accepted (200):      50
  Rate-limited (429):  0
  Errors / other:      0
----------------------------------------

Debouncing check: 50 signals accepted for 1 component.
  → Worker should create exactly 1 WorkItem (check GET /incidents).
```

### High-throughput load test

```bash
docker-compose exec backend python simulate_signals.py
```

This script uses `httpx` with async concurrency to saturate the ingestion endpoint and reports throughput, rejection rates, and latency percentiles.

### Database migrations

```bash
# Apply all pending migrations
docker-compose exec backend alembic upgrade head

# Create a new migration from model changes
docker-compose exec backend alembic revision --autogenerate -m "description"
```

---

## Project Structure

```
ims-project/
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI route handlers
│   │   │   ├── incidents.py        # GET /incidents, GET /incidents/{id}, POST state
│   │   │   ├── signal.py           # POST /signals (ingestion hot path)
│   │   │   └── routes/
│   │   │       ├── health.py       # GET /health
│   │   │       └── rca.py          # POST/GET /incidents/{id}/rca
│   │   ├── core/
│   │   │   ├── database.py         # Async SQLAlchemy engine + session factory
│   │   │   ├── redis.py            # Async Redis client with retry logic
│   │   │   ├── settings.py         # Pydantic-settings environment config
│   │   │   ├── logging.py          # Structured JSON logging setup
│   │   │   └── metrics.py          # Background throughput metrics loop
│   │   ├── models/
│   │   │   ├── work_item.py        # WorkItem SQLAlchemy model
│   │   │   └── rca_work_item.py    # RCA SQLAlchemy model (1-to-1, cascade delete)
│   │   ├── schemas/
│   │   │   ├── work_item.py        # Pydantic request/response schemas
│   │   │   ├── rca.py              # RCA schemas with field validation
│   │   │   └── signal.py           # SignalIn ingestion schema
│   │   ├── services/
│   │   │   ├── workflow_engine.py  # State Design Pattern (Open/Investigating/Resolved/Closed)
│   │   │   ├── workflow_service.py # DB-integrated state transition orchestration
│   │   │   ├── rca_service.py      # RCA creation, validation, MTTR calculation
│   │   │   ├── alert_service.py    # Strategy Design Pattern (Email/Slack/Combined)
│   │   │   ├── incident_service.py # List + detail queries with cache read-through
│   │   │   ├── cache_service.py    # Redis caching, debouncing, signal store, locks
│   │   │   └── queue_service.py    # LPUSH/BRPOP queue + Lua rate limiter
│   │   └── workers/
│   │       └── signal_worker.py    # Async BRPOP consumer; debounce + upsert + cache
│   ├── alembic/                    # Database migration scripts
│   ├── tests/                      # pytest unit tests (workflow, RCA, alerting, cache)
│   ├── main.py                     # FastAPI app, CORS, middleware, lifespan events
│   ├── simulate_signals.py         # High-throughput load test script
│   ├── requirements.txt
│   ├── Dockerfile
│   └── start.sh                    # Container entrypoint: migrate then start uvicorn
├── frontend/
│   ├── src/
│   │   ├── components/             # Navbar, Sidebar, IncidentCard, Loader
│   │   ├── pages/                  # Dashboard, IncidentDetail, RCAForm
│   │   ├── services/               # Axios instance + incidentService API calls
│   │   ├── store/                  # Zustand store (activeIncidents, selectedIncident)
│   │   └── hooks/                  # useFetch utility hook
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   ├── vite.config.js
│   └── Dockerfile
├── scripts/
│   └── simulate_failure.py         # Standalone debounce + rate-limit test script
├── docs/
│   └── architecture.png            # System architecture diagram
├── docker-compose.yml
└── README.md
```

---

## Configuration Reference

All settings are read from environment variables with the `IMS_` prefix. Defaults are suitable for local development.

| Variable | Default | Description |
|---|---|---|
| `IMS_DATABASE_URL` | `postgresql+asyncpg://ims:ims@localhost:5432/ims` | PostgreSQL connection string |
| `IMS_REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `IMS_LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `IMS_INGEST_RATE_LIMIT_PER_SEC` | `2000` | Max signals accepted per client IP per second |
| `IMS_SIGNAL_QUEUE_MAX_LENGTH` | `50000` | Queue depth threshold before backpressure activates |
| `IMS_DEBOUNCE_WINDOW_SECONDS` | `10` | Duration during which signals for a component map to one incident |
| `IMS_DASHBOARD_CACHE_TTL_SECONDS` | `5` | TTL for the active incidents dashboard cache |
| `IMS_INCIDENT_CACHE_TTL_SECONDS` | `30` | TTL for the per-incident detail cache |
| `IMS_METRICS_PRINT_INTERVAL_SECONDS` | `5` | How often throughput metrics are logged |
| `IMS_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed CORS origins |

---

## Design Decisions

**Why Redis for the queue instead of Kafka?**
Kafka adds significant operational overhead (ZooKeeper or KRaft, topic partitioning, consumer groups) that is disproportionate for a single-team deployment. Redis provides `LPUSH` / `BRPOP` semantics with sub-millisecond latency and integrates naturally with the cache and rate-limiting layers already present in the system. The architecture is intentionally designed so that replacing the Redis list with a Kafka topic would require changes only to `queue_service.py` and the worker's pop loop — no business logic changes are needed.

**Why FastAPI over Django or Flask?**
FastAPI is built on `asyncio` natively. Both signal ingestion and dashboard reads are I/O-bound workloads. Using an async framework means a single process can handle thousands of concurrent in-flight requests without thread-per-request overhead. Pydantic v2 integration provides zero-cost request validation, and the automatic OpenAPI schema generation reduces documentation burden.

**Why async SQLAlchemy instead of synchronous ORM calls?**
Synchronous database calls in an async web framework block the event loop for the duration of the query, destroying concurrency. `asyncpg` with SQLAlchemy's async session provides true non-blocking database I/O, meaning a single worker thread can interleave dozens of in-flight queries. All ORM calls in this project use `await session.execute(...)` — no synchronous calls exist.

**Why a separate worker process instead of FastAPI background tasks?**
FastAPI `BackgroundTask` runs in the same event loop as the request handler. A slow or CPU-bound processing step would degrade API latency for all concurrent requests. A dedicated worker process isolates processing load entirely, can be scaled independently, and can be restarted without affecting the API.

---

## Future Improvements

| Improvement | Description |
|---|---|
| Kafka integration | Replace the Redis queue with a Kafka topic for persistent, replayable signal streams and consumer group semantics across many worker replicas |
| WebSocket push | Replace the 5-second polling loop in the React dashboard with a WebSocket channel so incidents appear instantly without any client-driven polling |
| PagerDuty / OpsGenie alerts | Add concrete alert strategy implementations; the `AlertStrategy` ABC requires only a single `send_alert` method to be implemented |
| Signal deduplication | Add a bloom filter or content hash check to drop exact duplicate signals before they enter the queue |
| Prometheus metrics | Expose `signals_ingested_total`, `queue_depth`, and `mttr_seconds` as a `/metrics` endpoint for scraping by Prometheus and visualisation in Grafana |
| Incident search | Full-text search over `component_id`, `title`, and RCA fields using PostgreSQL `tsvector` or Elasticsearch |
| Authentication | JWT-based auth with role separation (viewer, responder, admin) and audit log for all state transitions |
| Multi-tenancy | Namespace all resources by organisation ID to support multiple teams on a shared deployment |

---

## Running Tests

```bash
docker-compose exec backend pytest tests/ -v
```

The test suite covers:
- Workflow state machine: valid and invalid transitions
- RCA enforcement: closure blocked without RCA, MTTR calculation
- Alert strategy selection: P0/P1/P2 routing
- Incident service cache: read-through behaviour

---

## License

MIT
