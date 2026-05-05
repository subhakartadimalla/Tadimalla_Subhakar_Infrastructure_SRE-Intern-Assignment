# Prompt Log — IMS Development

**Project:** Incident Management System (IMS)  
**Development Method:** AI-assisted engineering using iterative prompt-driven development  
**Total Prompts:** 44 (implementation) + 12 (debugging and verification)  

---

## Overview

This document captures the complete prompt log used to build the Incident Management System from an empty repository to a production-grade, fully integrated full-stack application.

Each prompt was written with a specific engineering goal. The prompts follow a layered approach: infrastructure and data foundations first, then business logic, then API surface, then observability, then frontend. Each layer was verified before the next was started.

The system was built iteratively. Several prompts were refinements of earlier ones — either because the initial output had a bug that surfaced during verification, or because a requirement needed to be tightened after seeing a working prototype. Those refinement cycles are documented inline.

This log is useful for:
- Understanding the order in which the system was assembled
- Replicating the development process on a similar project
- Reviewing which design decisions emerged during prompting versus which were specified upfront

---

## Prompt Categories

1. [Project Setup](#1-project-setup)
2. [Database Design](#2-database-design)
3. [Redis and Cache Layer](#3-redis-and-cache-layer)
4. [Signal Ingestion API](#4-signal-ingestion-api)
5. [Worker and Debouncing](#5-worker-and-debouncing)
6. [Workflow Engine — State Pattern](#6-workflow-engine--state-pattern)
7. [Alert System — Strategy Pattern](#7-alert-system--strategy-pattern)
8. [RCA and MTTR](#8-rca-and-mttr)
9. [Incident API Layer](#9-incident-api-layer)
10. [Observability](#10-observability)
11. [Frontend Setup](#11-frontend-setup)
12. [Live Dashboard](#12-live-dashboard)
13. [Incident Detail Page](#13-incident-detail-page)
14. [RCA Form](#14-rca-form)
15. [Final Integration and Audit](#15-final-integration-and-audit)

---

## 1. Project Setup

---

### Prompt 1: Full-stack project scaffold

**Goal:**  
Bootstrap a production-grade monorepo with all required services, directory structure, Docker Compose configuration, and a README stub. Establish the tech stack and project conventions before writing any feature code.

**Prompt Used:**
```
Create a production-grade, scalable full-stack project for an Incident Management System (IMS).
This system should simulate real-world tools used by companies like AWS and Google for handling
infrastructure incidents.

Tech stack:
- Backend: Python 3.11+, FastAPI, PostgreSQL, Redis, SQLAlchemy (async), Pydantic, Alembic
- Frontend: React (Vite), Tailwind CSS, Axios, Zustand
- Infrastructure: Docker + Docker Compose

Requirements:
- Async FastAPI with lifespan events for DB and Redis init
- Environment-based config using pydantic-settings
- CORS middleware
- Global exception handler
- /health endpoint
- Async DB and Redis connections with startup logging
- React frontend with Vite, Tailwind CSS base layout, Axios instance
- docker-compose.yml with all services connected
- README with architecture, tech stack, structure, and run instructions

The project should run with docker-compose up --build.
```

**Outcome:**  
Generated the complete project scaffold: `docker-compose.yml` with `postgres`, `redis`, `backend`, `worker`, and `frontend` services; `backend/main.py` with lifespan events, CORS, and exception handler; `backend/app/core/settings.py` with `pydantic-settings`; `backend/app/core/logging.py` with JSON formatter; `backend/app/core/database.py` and `backend/app/core/redis.py`; `frontend/` with Vite and Tailwind scaffolding; initial `README.md`.

---

### Prompt 2: Backend startup verification

**Goal:**  
Verify that the backend container starts without errors and that the `/health` endpoint is reachable.

**Prompt Used:**
```
Verify that the backend starts successfully and /health works. Fix any issues if present.
```

**Outcome:**  
Identified that `alembic/env.py` was using `localhost:5432` instead of the Docker service name `postgres`, causing connection failure on startup. Fixed `env.py` to read `IMS_DATABASE_URL` from the environment. Also identified a Pydantic settings parsing error: `cors_origins` was typed as `list[str]` but received a CSV string from Docker Compose, causing a `SettingsError`. Fixed by changing the type to `str` and adding a `cors_origins_list` property to parse CSV and JSON formats.

---

### Prompt 3: Connection logging

**Goal:**  
Confirm that PostgreSQL and Redis connections are established on startup and visible in structured logs.

**Prompt Used:**
```
Ensure PostgreSQL and Redis connections are working properly. Add logs to confirm connections.
```

**Outcome:**  
Added a `SELECT 1` ping in `init_engine()` and a `PING` call in `init_redis()` with structured log output on success and failure. Confirmed logs show `database connected` and `redis connected` on startup.

---

## 2. Database Design

---

### Prompt 4: Full database layer implementation

**Goal:**  
Implement the complete async database layer: SQLAlchemy 2 models for `WorkItem` and `RCA`, enums, relationships, indexes, Pydantic schemas, and Alembic migrations.

**Prompt Used:**
```
Implement the complete database layer for the Incident Management System.
This must be production-grade, async, and scalable.

Requirements:
- BaseModel with id (UUID), created_at, updated_at
- WorkItem model with: component_id, severity (enum: P0/P1/P2), status (enum: OPEN/INVESTIGATING/RESOLVED/CLOSED),
  title, description, first_signal_time, last_signal_time, signal_count
- RCA model with: work_item_id (FK + cascade delete), root_cause, fix_applied, prevention_steps,
  start_time, end_time, mttr
- One-to-one WorkItem → RCA relationship
- Indexes on component_id, severity, status, and compound (component_id, created_at)
- Pydantic schemas for both models
- Alembic migration to create both tables
- Async SQLAlchemy 2.0 session factory and FastAPI dependency
```

**Outcome:**  
Generated `app/models/work_item.py`, `app/models/rca_work_item.py`, `app/models/enums.py`, `app/schemas/work_item.py`, `app/schemas/rca.py`, and Alembic migration `0002_work_items_rca.py`. Migration included `DROP TABLE IF EXISTS rcas CASCADE` to handle idempotent re-runs.

---

### Prompt 5: Migration execution and verification

**Goal:**  
Run migrations inside the Docker container and verify both tables were created with correct schemas and indexes.

**Prompt Used:**
```
Run migrations and verify tables are created in PostgreSQL. Fix any issues.
```

**Outcome:**  
Migration ran successfully. Confirmed `work_items` and `rcas` tables with correct columns, indexes, and FK constraint via `\d work_items` and `\d rcas` in `psql`.

---

### Prompt 6: Sample data insertion

**Goal:**  
Verify the async session factory works end-to-end by inserting and fetching a sample `WorkItem`.

**Prompt Used:**
```
Insert a sample WorkItem and fetch it using async session.
```

**Outcome:**  
Created `app/utils/sample_work_item_demo.py`. Identified a module-level import issue where `SessionLocal` was `None` at import time. Fixed by importing the `database` module and accessing `database.SessionLocal` after `init_engine()` has been called.

---

## 3. Redis and Cache Layer

---

### Prompt 7: Redis layer implementation

**Goal:**  
Implement a production-grade Redis layer covering caching, debouncing, raw signal storage, distributed locks, and a simple queue.

**Prompt Used:**
```
Implement a production-grade Redis layer for caching, debouncing, and queue support in the
Incident Management System. This is a critical performance layer. Design it cleanly and async-first.

Requirements:
- Async redis-py client with connection retry logic and exponential back-off
- cache_service.py:
  - get/set dashboard cache (TTL configurable)
  - get/set incident detail cache (TTL configurable)
  - append_raw_signal / get_raw_signals (Redis list per incident)
  - check_duplicate_signal / set_debounce_key (active_incident:{component_id} TTL)
  - acquire_component_lock / release_component_lock (SET NX EX)
  - invalidate_dashboard_cache / invalidate_incident_cache
- queue_service.py:
  - push_signal (LPUSH)
  - pop_signal (BRPOP with timeout)
  - get_queue_length (LLEN)
  - is_rate_limited (Lua INCR/EXPIRE script)
- Error handling and logging on all operations
- POST /test/cache endpoint to verify Redis writes and reads
```

**Outcome:**  
Generated `app/services/cache_service.py`, `app/services/queue_service.py`, `app/core/redis.py` with retry logic, and `app/api/routes/test_cache.py`. All Redis operations wrapped in `safe_redis_call()` for consistent error logging and propagation.

---

### Prompt 8: Redis key verification

**Goal:**  
Confirm that Redis keys are being set and retrieved correctly.

**Prompt Used:**
```
Test Redis connection and ensure keys are being set properly.
```

**Outcome:**  
Used `docker-compose exec redis redis-cli KEYS '*'` and the `/test/cache` endpoint to verify key presence. Confirmed `dashboard:active_incidents` and `incident:{id}` keys with correct TTLs.

---

### Prompt 9: Queue push and pop

**Goal:**  
Verify that signals can be pushed to and popped from the Redis queue correctly.

**Prompt Used:**
```
Push sample signal into queue and pop it using a test script.
```

**Outcome:**  
Created `app/utils/queue_demo.py`. Verified `LPUSH` and `BRPOP` working correctly with correct JSON serialisation/deserialisation.

---

## 4. Signal Ingestion API

---

### Prompt 10: High-throughput ingestion endpoint

**Goal:**  
Implement `POST /signals` as a non-blocking, rate-limited, backpressure-aware endpoint designed for 10,000 signals per second.

**Prompt Used:**
```
Implement a high-throughput Signal Ingestion API for the Incident Management System.
This is the entry point of the system and must be designed for scale (10,000 signals/sec).

Requirements:
- POST /signals endpoint
- Non-blocking: push to Redis queue, return immediately
- Redis-based rate limiting: 1000 req/sec per client IP using Lua INCR/EXPIRE
- Backpressure: check queue length against configurable threshold, return 429 if exceeded
- Return 503 if Redis is unavailable
- Background metrics loop logging signals/sec and queue size every 5 seconds
- simulate_signals.py script for load testing with httpx async concurrency
```

**Outcome:**  
Generated `app/api/signal.py` with rate limiting, backpressure check, and queue push. Generated `app/core/metrics.py` with `Counters` dataclass, async-safe increment functions, and `metrics_loop` background task. Generated `backend/simulate_signals.py`.

---

### Prompt 11: Load test — 500–1000 signals

**Goal:**  
Verify the ingestion API handles burst traffic without crashing and that the Redis queue grows as expected.

**Prompt Used:**
```
Send 500–1000 signals quickly and verify: API responds fast, queue size increases, no crashes.
```

**Outcome:**  
Load test confirmed sub-5ms response times under concurrent load. Queue depth visible via `LLEN signal_queue` in Redis CLI. Metrics loop logged `signals_per_sec` correctly in backend logs.

---

### Prompt 12: Rate limit verification

**Goal:**  
Confirm that requests exceeding the configured rate limit receive `HTTP 429` responses.

**Prompt Used:**
```
Simulate rate limit breach and ensure 429 is returned.
```

**Outcome:**  
Initially, rate limiting was not triggering because `docker-compose.yml` was overriding `IMS_INGEST_RATE_LIMIT_PER_SEC` to a high value, and varying client IPs (IPv4/IPv6) were splitting traffic across multiple rate-limit buckets. Fixed by sending a fixed `X-Forwarded-For` header in the test script and temporarily lowering the rate limit in `docker-compose.yml`. Confirmed `429` responses at threshold.

---

## 5. Worker and Debouncing

---

### Prompt 13: Signal worker implementation

**Goal:**  
Implement the background async worker that consumes signals from the Redis queue and applies debouncing logic to create or update `WorkItem` records.

**Prompt Used:**
```
Implement a robust Workflow Engine for WorkItem lifecycle using the State Design Pattern.
This must be clean, extensible, and production-grade.

Worker requirements (separate from workflow engine):
- Async BRPOP consumer loop
- Per-component distributed lock (SET NX EX)
- Debounce check via active_incident:{component_id} Redis key
- Create new WorkItem on cache miss; update existing on cache hit
- Append raw signal to signals:{work_item_id} Redis list
- Invalidate incident detail cache after each signal
- Refresh dashboard cache after each signal
- Structured logging with service="ims-worker"
- Requeue signal on processing failure
```

**Outcome:**  
Generated `app/workers/signal_worker.py` with the full processing pipeline. Confirmed debouncing works: 6 signals for the same component within 10 seconds produce exactly 1 `WorkItem` with `signal_count = 6`.

**Debugging note:**  
During verification, the incident detail API was returning `signals: []` for newly created incidents. Root cause: the worker was calling `set_incident_cache(wi_id, _serialize_work_item(wi))` which wrote a cache entry containing only `WorkItem` fields — no `signals` list. The API cached this incomplete entry and returned it for up to 30 seconds. Fixed in two places: (1) worker changed to call `invalidate_incident_cache` instead of `set_incident_cache`, so the API always rebuilds a complete entry on the next read; (2) `incident_service.get_incident_detail_cached` updated to bypass cache entries with no signals and retry with exponential back-off (0.3s, 0.6s, 1.0s) before caching.

---

## 6. Workflow Engine — State Pattern

---

### Prompt 14: State machine implementation

**Goal:**  
Implement the incident lifecycle state machine using the State Design Pattern with no if-else logic on status strings.

**Prompt Used:**
```
Implement a robust Workflow Engine for WorkItem lifecycle using the State Design Pattern.
This must be clean, extensible, and production-grade.

Requirements:
- BaseState abstract class with to_investigating(), to_resolved(), to_closed() methods
- Each method raises InvalidTransitionError by default
- OpenState: permits only to_investigating()
- InvestigatingState: permits only to_resolved()
- ResolvedState: permits only to_closed()
- ClosedState: terminal — permits nothing
- WorkItemStateContext: holds current state, delegates all transitions
- workflow_service.py: integrates with DB, fetches WorkItem, applies transition, persists new status
- InvalidTransitionError raised and surfaced as HTTP 400
```

**Outcome:**  
Generated `app/services/workflow_engine.py` and `app/services/workflow_service.py`. No if-else chains — each state class is self-contained.

---

### Prompt 15: Valid transition verification

**Goal:**  
Confirm that valid state transitions update the database correctly.

**Prompt Used:**
```
Try valid state transitions and verify DB updates correctly.
```

**Outcome:**  
Confirmed `OPEN → INVESTIGATING → RESOLVED` updates `status` column in `work_items`. Verified via direct `psql` query.

---

### Prompt 16: Invalid transition verification

**Goal:**  
Confirm that invalid transitions are blocked with a clear error message.

**Prompt Used:**
```
Try invalid transitions and ensure proper errors are thrown.
```

**Outcome:**  
Confirmed `INVESTIGATING → CLOSED` returns `HTTP 400 Cannot move from INVESTIGATING to CLOSED`. `InvalidTransitionError` is caught by the global exception handler and returned as a structured JSON error response.

---

## 7. Alert System — Strategy Pattern

---

### Prompt 17: Alert strategy implementation

**Goal:**  
Implement severity-based alert routing using the Strategy Design Pattern with a configurable strategy map.

**Prompt Used:**
```
Implement an alerting system using the Strategy Design Pattern.

Requirements:
- AlertStrategy abstract base class with async send_alert(work_item) method
- EmailAlertStrategy: logs email alert event
- SlackAlertStrategy: logs Slack notification event
- CombinedAlertStrategy: runs multiple strategies concurrently via asyncio.gather
- Factory function get_alert_strategy(severity) reading from IMS_ALERT_STRATEGY_MAP_JSON env var
  default: {"P0": "combined", "P1": "slack", "P2": "email"}
- send_alert_non_blocking: fire via asyncio.create_task (non-blocking)
- Alert fires only on new WorkItem creation, not on signal updates
- Unit tests for strategy selection and alert firing
```

**Outcome:**  
Generated `app/services/alert_service.py` and `tests/test_alerting.py`. Tests initially failed because `pytest-asyncio` `caplog` defaults to `WARNING` level, missing `INFO` log assertions. Fixed by adding `caplog.set_level(logging.INFO)` in test functions.

---

## 8. RCA and MTTR

---

### Prompt 18: RCA enforcement and MTTR calculation

**Goal:**  
Implement the RCA service with full field validation, MTTR calculation, and the enforcement gate on incident closure.

**Prompt Used:**
```
Implement Root Cause Analysis (RCA) enforcement and MTTR calculation for the Incident
Management System. This is a critical business logic layer and must be strict, validated,
and production-grade.

Requirements:
- rca_service.py:
  - create_or_update_rca(session, work_item_id, rca_data): validate all fields,
    enforce end_time > start_time, calculate mttr as (end_time - start_time).total_seconds()
  - get_rca(session, work_item_id): return RCA or None
- workflow_service.transition_to_closed(): query rcas table, block closure if no RCA
- API endpoints:
  - POST /incidents/{id}/rca
  - GET /incidents/{id}/rca
- Unit tests for RCA validation and MTTR calculation
```

**Outcome:**  
Generated `app/services/rca_service.py`, `app/api/routes/rca.py`, and `tests/test_rca_enforcement.py`. Closure without RCA confirmed to return `HTTP 400 Cannot close incident without completed RCA`. MTTR calculated correctly.

**Debugging note:**  
`test_rca_enforcement.py` initially raised `RuntimeError: Task got Future attached to a different loop`. Caused by `pytest-asyncio` creating new event loops per test while the `AsyncEngine` was bound to the first loop. Fixed by applying `@pytest.mark.asyncio(scope="session")` to database-interacting tests.

---

### Prompt 19: Full closure flow verification

**Goal:**  
Verify the complete RCA submission and incident closure flow end-to-end.

**Prompt Used:**
```
Close WorkItem after RCA and verify status update.
```

**Outcome:**  
Confirmed: submit RCA → `POST /incidents/{id}/state {"action": "CLOSED"}` → status becomes `CLOSED` → `GET /incidents/{id}` shows `status: CLOSED` and full RCA object with correct `mttr`.

---

## 9. Incident API Layer

---

### Prompt 20: Production incident APIs

**Goal:**  
Implement the full incident API layer with Redis read-through caching for dashboard and detail endpoints.

**Prompt Used:**
```
Implement production-grade Incident APIs for the Incident Management System.
These APIs will power the frontend dashboard and must be fast, clean, and cache-optimised.

Requirements:
- GET /incidents: list active (non-closed) incidents, sorted by severity rank then updated_at DESC,
  with Redis dashboard cache (read-through, TTL from settings)
- GET /incidents/{id}: incident detail with signals (from Redis list), current state, RCA if exists,
  with Redis incident detail cache (read-through)
- POST /incidents/{id}/state: change state via workflow_service, invalidate both caches on success
- Connect POST/GET /incidents/{id}/rca
- Cache invalidation on every state transition
```

**Outcome:**  
Generated `app/api/incidents.py`, `app/services/incident_service.py`. Dashboard cache confirmed with `Cache hit cache=dashboard` log entries. Incident detail cache confirmed with `Cache hit cache=incident` on repeat requests.

---

### Prompt 21: Sorting verification

**Goal:**  
Verify that `GET /incidents` returns incidents sorted correctly by severity then recency.

**Prompt Used:**
```
Fetch /incidents and verify results are sorted correctly and cached.
```

**Outcome:**  
Confirmed P0 incidents appear before P1, P1 before P2, within same severity sorted by `updated_at DESC`. Cache hit confirmed on second request within TTL window.

---

### Prompt 22: Signal presence verification in detail

**Goal:**  
Verify that `GET /incidents/{id}` returns associated signals.

**Prompt Used:**
```
Fetch /incidents/{id} and verify signals + RCA appear correctly.
```

**Outcome:**  
Initially, signals were returning empty (`signals: []`). Root cause was the incomplete worker cache write (see Prompt 13 debugging note). After fix: confirmed signals present in detail response.

---

### Prompt 23: Cache invalidation on state change

**Goal:**  
Confirm that both caches are invalidated when state changes, and fresh data is returned immediately after.

**Prompt Used:**
```
Change state and verify cache invalidation works.
```

**Outcome:**  
Confirmed: state transition → cache invalidation logs appear → next `GET /incidents` shows updated status without stale data.

---

## 10. Observability

---

### Prompt 24: Enhanced observability

**Goal:**  
Implement production-grade observability: enhanced `/health`, structured JSON logging with `service` field, per-request middleware, and throughput metrics loop.

**Prompt Used:**
```
Implement production-grade observability for the Incident Management System.

Requirements:
- Enhanced GET /health: active DB (SELECT 1) and Redis (PING) probes, return
  {status: ok|degraded|down, services: {database, redis}, timestamp}, log CRITICAL on degraded/down
- Structured JSON logs: every line has timestamp, level, name, service, message, extra fields
  - Inject "service" field via a logging.Filter (ServiceFilter) so callers don't need to pass it
- HTTP request logging middleware: log method, path, status_code, duration_ms on every request
- metrics_loop background task: every 5s log signals_ingested, signals_per_sec,
  rejected_rate_limited, rejected_backpressure, rejected_redis_down, queue_length
- Configure log level via IMS_LOG_LEVEL env var
- Suppress Uvicorn default access logs (--no-access-log --log-level warning)
- Worker logs with service="ims-worker"
```

**Outcome:**  
Generated `app/core/logging.py` with `ServiceFilter`, `app/core/metrics.py` with `metrics_loop`, updated `app/api/routes/health.py`, updated `backend/main.py` with HTTP middleware and Uvicorn flag adjustments. Confirmed structured JSON output with `service` field on all log lines.

---

### Prompt 25: Health degraded verification

**Goal:**  
Confirm that `/health` returns `degraded` when Redis is stopped.

**Prompt Used:**
```
Stop Redis and check if health shows degraded.
```

**Outcome:**  
Confirmed: stopping the Redis container → `GET /health` returns `{status: degraded, services: {database: connected, redis: down}}` with `CRITICAL`-level log event.

---

## 11. Frontend Setup

---

### Prompt 26: React frontend scaffold

**Goal:**  
Set up the complete React frontend with Vite, Tailwind CSS, Axios, Zustand, React Router, base layout, and routing.

**Prompt Used:**
```
Set up a production-grade React frontend for the Incident Management System (IMS).

Requirements:
- React (Vite), Tailwind CSS, Axios, Zustand, React Router
- Directory structure: /src/{components,pages,services,store,hooks}
- Base layout: Navbar (top), Sidebar (left, links to Dashboard and Incidents), main content area
- Routing: / (Dashboard), /incident/:id (Incident Detail), /incident/:id/rca (RCA Form)
- Tailwind config with content paths
- Axios instance (api.js) with VITE_API_BASE_URL and response error interceptors
- Zustand store (useIncidentStore.js): activeIncidents, selectedIncident, fetchIncidents, fetchIncidentById
- Reusable components: IncidentCard (severity colour-coded), Loader
- .env.example with VITE_API_BASE_URL=http://localhost:8000
- Global error normalisation to prevent React rendering crashes on error objects
```

**Outcome:**  
Generated all frontend scaffold files. Identified Tailwind v4 incompatibility with Node 18 (v4 requires Node 20+). Fixed by downgrading to `tailwindcss@^3.4.17` and reverting `postcss.config.js` to use `tailwindcss: {}`. Frontend builds and runs successfully.

---

### Prompt 27: Frontend verification

**Goal:**  
Confirm that the layout renders, routing works, and no console errors are present.

**Prompt Used:**
```
Run frontend and verify: layout renders correctly, routing works, no console errors.
```

**Outcome:**  
Browser automation confirmed: Navbar and Sidebar render; navigation between Dashboard, Incident Detail, and RCA Form routes works; no console errors on load.

---

## 12. Live Dashboard

---

### Prompt 28: Dashboard page implementation

**Goal:**  
Implement the live incident dashboard with auto-refresh, sorting, and loading/error/empty states.

**Prompt Used:**
```
Implement the Live Incident Dashboard page for the Incident Management System.

Requirements:
- pages/Dashboard.jsx using GET /incidents
- Fetch incidents on mount, auto-refresh every 5 seconds via setInterval + useRef for cleanup
- Loading state (Loader component), error state with retry button, empty state message
- Display incidents as IncidentCard components
- Frontend sort: primary by severityRank (P0=0, P1=1, P2=2), secondary by last_updated DESC
- Cards clickable to /incident/:id
- Description: "Live active incidents (auto-refresh every 5s)"
```

**Outcome:**  
Generated `pages/Dashboard.jsx` with `useMemo` for sorted incidents, `useRef` for interval cleanup, and graceful handling of all three states (loading, error, empty). Auto-refresh confirmed working via browser automation.

---

## 13. Incident Detail Page

---

### Prompt 29: Incident detail page implementation

**Goal:**  
Implement the incident detail page with sections for summary, state controls, signals list, and RCA display.

**Prompt Used:**
```
Implement the Incident Detail Page for the Incident Management System.

Requirements:
- pages/IncidentDetail.jsx using GET /incidents/{id}
- Sections: Incident Summary, State Controls, Signals List (scrollable), RCA Section
- Summary: component ID, severity/status badges (colour-coded), signal count, timestamps
- State controls: buttons for INVESTIGATING, RESOLVED, CLOSED
  - Disable buttons based on current status
  - Call POST /incidents/{id}/state on click
  - Show actionError on invalid transitions or server errors
  - Require window.confirm for closure
- Signals: scrollable list, each entry shows message + timestamp
  - "JSON" toggle button to expand full raw payload
- RCA section: show summary if RCA exists, else "No RCA submitted yet" with Add RCA link
- Refresh data after every state change or RCA submission
- Error normalisation to prevent rendering crashes
```

**Outcome:**  
Generated `pages/IncidentDetail.jsx`. Initial rendering was blank due to the component expecting a nested `data.incident` field while the API returns incident data flat at the root. Fixed by extracting with `detail?.incident ?? detail ?? null`.

---

### Prompt 30: Signal display verification

**Goal:**  
Confirm that the signals list renders correctly on the detail page.

**Prompt Used:**
```
Open an incident and verify signals are displayed correctly.
```

**Outcome:**  
Confirmed signals list renders in the detail page. Debounce test: 6 signals for one component → detail shows 6 signal entries.

---

### Prompt 31: State transition UI verification

**Goal:**  
Confirm that state transition buttons work and the UI reflects updates immediately.

**Prompt Used:**
```
Trigger state transitions and verify updates reflect immediately.
```

**Outcome:**  
Confirmed: clicking "Start Investigation" → `POST /incidents/{id}/state {action: INVESTIGATING}` → detail refreshes → status badge updates to `INVESTIGATING`.

---

### Prompt 32: Close-without-RCA error UI verification

**Goal:**  
Confirm that attempting to close an incident without RCA shows a user-facing error message.

**Prompt Used:**
```
Try closing without RCA — ensure error is shown.
```

**Outcome:**  
Confirmed: "Close Incident" button on a `RESOLVED` incident without RCA → `HTTP 400` → `actionError` state rendered as red error message in the UI.

---

## 14. RCA Form

---

### Prompt 33: RCA form implementation

**Goal:**  
Implement the RCA form with prefill from existing RCA, client-side validation, submission flow, and redirect on success.

**Prompt Used:**
```
Implement the RCA (Root Cause Analysis) Form and complete the final integration.

Requirements:
- pages/RCAForm.jsx using POST /incidents/{id}/rca and GET /incidents/{id}/rca
- Fields: Start Time (datetime-local), End Time (datetime-local), Root Cause (textarea),
  Fix Applied (textarea), Prevention Steps (textarea)
- Frontend validation: all text fields required (trimmed), end_time > start_time
- Inline field-level error messages (fieldErrors state)
- Prefill existing RCA via GET /incidents/{id}/rca (404 = no RCA yet, not an error)
- Submit flow: validate → call API → on success show message + setTimeout redirect to /incident/{id}
- Prevent duplicate submissions (submitting state)
- Loading state for submit button
- Submit vs Update label based on whether RCA already exists
- toDatetimeLocal / toIso helpers for datetime-local input format conversion
```

**Outcome:**  
Generated `pages/RCAForm.jsx` with all validation, prefill, and submission logic. Fixed a `useFetch` issue where a 404 from `GET /incidents/{id}/rca` was being treated as a load error — replaced with manual `useEffect` that explicitly handles `err?.status === 404` as the "no existing RCA" state.

---

### Prompt 34: RCA prefill verification

**Goal:**  
Confirm that the RCA form prefills correctly for an incident that already has an RCA.

**Prompt Used:**
```
Open RCA form for an incident with an existing RCA and verify fields are prefilled.
```

**Outcome:**  
Confirmed: `GET /incidents/{id}/rca` returns RCA data → `toDatetimeLocal` converts ISO strings to `YYYY-MM-DDTHH:mm` format → form fields populate correctly.

---

### Prompt 35: RCA validation verification

**Goal:**  
Confirm that client-side validation blocks submission with inline error messages.

**Prompt Used:**
```
Open RCA form for an incident with no RCA. Submit without filling fields.
Verify inline validation errors appear for all required fields.
```

**Outcome:**  
Code inspection confirmed all validation logic is correct: `!values.root_cause?.trim()` checks and corresponding `fieldErrors` state rendering. Browser automation confirmed inline error messages appear on empty submission.

---

## 15. Final Integration and Audit

---

### Prompt 36: Complete end-to-end audit

**Goal:**  
Perform a senior SRE-level audit of the entire system: project structure, Docker, backend, signal ingestion, worker, debouncing, database, state machine, alert system, RCA, API layer, observability, frontend, full E2E flow, and README.

**Prompt Used:**
```
Act as a senior SRE + backend engineer and perform a COMPLETE end-to-end audit of this
Incident Management System project. Your goal is to verify that EVERYTHING works correctly,
is production-ready, and meets all assignment requirements. Do NOT assume anything — check
each part carefully.

[Full 17-section audit checklist covering project structure, Docker, backend, signal
ingestion, worker, debouncing, database models, workflow engine, alert system, RCA/MTTR,
API layer, observability, frontend, E2E flow, sample scripts, README, and performance.]
```

**Outcome:**  
Audit revealed and fixed three issues:

1. **Worker incomplete cache write (critical):** Worker was writing a partial incident detail cache (no `signals` field), causing the API to return empty signals for up to 30 seconds. Fixed by replacing `set_incident_cache` with `invalidate_incident_cache` in the worker.

2. **Insufficient retry in incident_service (moderate):** Single 0.2s retry before caching empty signal results was too short. Replaced with 3-step exponential back-off and conditional caching only when signals are present.

3. **Missing scripts/ directory and simulate_failure.py (low):** Created `scripts/simulate_failure.py` with full argument parsing, async `httpx` concurrency, and clear output formatting.

4. **Missing frontend/Dockerfile (low):** Created `frontend/Dockerfile` using Node 18 Alpine.

All 17 audit sections confirmed passing after fixes. Full E2E flow verified: signal ingestion → incident creation → debouncing → state transitions → RCA submission → MTTR calculation → closure.

---

### Prompt 37: Professional README generation

**Goal:**  
Replace the working README with a production-quality document structured for both technical reviewers and recruiters.

**Prompt Used:**
```
Generate a highly professional, production-grade README.md for my project: Incident Management System.
This is NOT a basic README. It should feel like a real system built by an SRE / backend engineer
at a top company.

[17-section specification covering: title, overview, architecture, tech stack, key features,
system flow, backpressure, scalability, non-functional characteristics, API reference, setup,
simulation, project structure, configuration, design decisions, future improvements, testing.]
```

**Outcome:**  
Generated a 463-line professional README with accurate architecture diagram, version-pinned tech stack table, detailed backpressure explanation, full configuration reference table, and reasoned design decision section.

---

### Prompt 38: Technical specification document

**Goal:**  
Generate formal engineering documentation (`docs/spec.md`) suitable for a production system design review.

**Prompt Used:**
```
Generate professional documentation for this project capturing SPEC, DESIGN, and PROMPTS.
Create /docs/spec.md: Technical Specification covering problem statement, goals, non-goals,
architecture, data flow, core concepts, design decisions, debouncing logic, workflow engine,
alerting system, backpressure, scalability, observability, data models, API contract,
configuration, limitations, and future improvements.
```

**Outcome:**  
Generated `docs/spec.md` — the document you are reading the companion to.

---

### Prompt 39: Prompt log document

**Goal:**  
Generate this document (`docs/prompts.md`) as a complete record of the development process.

**Prompt Used:**
```
Generate /docs/prompts.md: a complete prompt log capturing all prompts used to build the
system, grouped by category, with goal, prompt text, and outcome for each.
```

**Outcome:**  
This document.

---

## Notes on Iterative Development

**Verification after each layer.** Every major component was verified with a concrete test (curl command, Python script, browser automation, or psql query) before the next component was built on top of it. This prevented bug accumulation across layers.

**Debugging prompts.** Several components required dedicated debugging prompts after the implementation prompt. The most significant were: Alembic using localhost instead of Docker service name, Pydantic settings CSV parsing failure, pytest-asyncio event loop isolation, and the worker incomplete cache write that caused empty signals in the detail API.

**Refinement over replacement.** When a component had a bug, the fix was applied as a targeted patch to the specific function or module rather than regenerating the entire component. This preserved surrounding context and reduced the risk of introducing new issues.

**Production constraints surfaced late.** Some requirements that were implicit in the problem statement were only formalised during the final audit — for example, the strict requirement that the incident detail cache must not be populated with a partial entry. Auditing against the full specification checklist was necessary to surface these.
