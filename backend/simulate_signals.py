from __future__ import annotations

import asyncio
import os
import time
from datetime import UTC, datetime
from typing import Any

import httpx


API_BASE_URL = os.getenv("IMS_API_BASE_URL", "http://localhost:8000")
XFF = os.getenv("IMS_SIM_X_FORWARDED_FOR", "").strip()


def _payload(i: int) -> dict[str, Any]:
    fixed_component = os.getenv("IMS_SIM_COMPONENT_ID", "").strip()
    return {
        "component_id": fixed_component or f"CACHE_CLUSTER_{i % 10:02d}",
        "timestamp": datetime.now(UTC).isoformat(),
        "severity": "P2",
        "message": "simulated signal",
        "metadata": {"seq": i},
    }


async def main() -> None:
    total = int(os.getenv("IMS_SIM_COUNT", "1000"))
    concurrency = int(os.getenv("IMS_SIM_CONCURRENCY", "200"))
    timeout_s = float(os.getenv("IMS_SIM_TIMEOUT_SECONDS", "10"))

    ok = 0
    limited = 0
    unavailable = 0
    other = 0
    transport_errors = 0
    connect_timeouts = 0
    read_timeouts = 0

    sem = asyncio.Semaphore(concurrency)

    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    timeout = httpx.Timeout(timeout_s, connect=min(5.0, timeout_s))
    headers = {"x-forwarded-for": XFF} if XFF else None

    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=timeout, limits=limits, headers=headers) as client:
        start = time.perf_counter()

        async def one(i: int) -> None:
            nonlocal ok, limited, unavailable, other, transport_errors, connect_timeouts, read_timeouts
            async with sem:
                try:
                    r = await client.post("/signals", json=_payload(i))
                    if r.status_code == 200:
                        ok += 1
                    elif r.status_code == 429:
                        limited += 1
                    elif r.status_code == 503:
                        unavailable += 1
                    else:
                        other += 1
                except httpx.ConnectTimeout:
                    transport_errors += 1
                    connect_timeouts += 1
                except httpx.ReadTimeout:
                    transport_errors += 1
                    read_timeouts += 1
                except httpx.HTTPError:
                    transport_errors += 1

        await asyncio.gather(*(one(i) for i in range(total)))
        elapsed = time.perf_counter() - start

    rps = ok / elapsed if elapsed > 0 else 0.0
    print(
        {
            "base_url": API_BASE_URL,
            "total": total,
            "concurrency": concurrency,
            "elapsed_s": round(elapsed, 3),
            "accepted": ok,
            "rate_limited": limited,
            "redis_unavailable": unavailable,
            "other": other,
            "transport_errors": transport_errors,
            "connect_timeouts": connect_timeouts,
            "read_timeouts": read_timeouts,
            "accepted_rps": round(rps, 1),
        }
    )


if __name__ == "__main__":
    asyncio.run(main())

