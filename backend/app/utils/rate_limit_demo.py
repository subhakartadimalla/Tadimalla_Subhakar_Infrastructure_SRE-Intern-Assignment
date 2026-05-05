from __future__ import annotations

import asyncio

from app.core.redis import close_redis, init_redis
from app.core.settings import settings
from app.services.queue_service import is_rate_limited


async def main() -> None:
    await init_redis(settings.redis_url)

    client_ip = "203.0.113.10"
    limit = 50
    limited_count = 0

    # Run quickly within ~1s window
    for i in range(1, 80):
        limited = await is_rate_limited(client_ip, limit_per_sec=limit)
        if limited:
            limited_count += 1
        if i in (1, limit, limit + 1, 79):
            print({"i": i, "limited": limited})

    print({"limit": limit, "calls": 79, "limited_count": limited_count})
    await close_redis()


if __name__ == "__main__":
    asyncio.run(main())

