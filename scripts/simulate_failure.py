#!/usr/bin/env python3
"""
simulate_failure.py
--------------------
Sends a burst of signals for a single component to test:
  - Signal ingestion throughput
  - Debouncing (many signals → 1 WorkItem)
  - Rate limiting (429 responses when limit hit)

Usage:
  python3 scripts/simulate_failure.py [--url URL] [--component COMPONENT_ID]
                                       [--count N] [--severity P0|P1|P2]

Defaults:
  --url       http://localhost:8000
  --component SIMULATE_FAILURE_01
  --count     20
  --severity  P1
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import sys

try:
    import httpx
except ImportError:
    print("httpx not installed. Run: pip install httpx")
    sys.exit(1)


async def send_signal(client: httpx.AsyncClient, url: str, component: str, severity: str, idx: int) -> tuple[int, dict]:
    payload = {
        "component_id": component,
        "severity": severity,
        "message": f"Simulated failure signal #{idx}",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    try:
        resp = await client.post(f"{url}/signals", json=payload, timeout=10)
        return resp.status_code, resp.json()
    except Exception as exc:
        return -1, {"error": str(exc)}


async def main(url: str, component: str, count: int, severity: str) -> None:
    print(f"Sending {count} signals for component={component} severity={severity} → {url}")
    limits = httpx.Limits(max_connections=50, max_keepalive_connections=20)
    async with httpx.AsyncClient(limits=limits) as client:
        tasks = [send_signal(client, url, component, severity, i) for i in range(1, count + 1)]
        results = await asyncio.gather(*tasks)

    accepted = sum(1 for c, _ in results if c == 200)
    rate_limited = sum(1 for c, _ in results if c == 429)
    errors = sum(1 for c, _ in results if c not in (200, 429))

    print(f"\n{'─'*40}")
    print(f"  Accepted (200):      {accepted}")
    print(f"  Rate-limited (429):  {rate_limited}")
    print(f"  Errors / other:      {errors}")
    print(f"{'─'*40}")

    if rate_limited > 0:
        print("\n✅  Rate limiting is working — 429 responses observed.")
    if accepted > 0:
        print(f"\n✅  Debouncing check: {accepted} signals accepted for 1 component.")
        print("    → Worker should create exactly 1 WorkItem (check GET /incidents).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simulate failure signals for IMS")
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--component", default="SIMULATE_FAILURE_01")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--severity", default="P1", choices=["P0", "P1", "P2"])
    args = parser.parse_args()
    asyncio.run(main(args.url, args.component, args.count, args.severity))
