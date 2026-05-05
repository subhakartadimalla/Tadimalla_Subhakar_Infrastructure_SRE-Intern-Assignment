from __future__ import annotations

import asyncio

from app.core.redis import close_redis, init_redis
from app.core.settings import settings
from app.services.cache_service import pop_signal_from_queue, push_signal_to_queue


async def main() -> None:
    await init_redis(settings.redis_url)

    sample_signal = {
        "component_id": "CACHE_CLUSTER_01",
        "component_type": "cache",
        "message": "latency spike",
        "payload": {"p95_ms": 420, "region": "us-east-1"},
    }

    pushed = await push_signal_to_queue(sample_signal)
    popped = await pop_signal_from_queue(timeout_seconds=2)

    print({"pushed": pushed, "popped": popped})

    await close_redis()


if __name__ == "__main__":
    asyncio.run(main())

