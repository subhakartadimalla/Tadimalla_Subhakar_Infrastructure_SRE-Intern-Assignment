from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core import database
from app.core.settings import settings
from app.models.work_item import WorkItem
from app.utils.sample_data import create_sample_work_item


async def main() -> None:
    await database.init_engine(settings.database_url)
    if database.SessionLocal is None:
        raise RuntimeError("SessionLocal is not initialized")

    async with database.SessionLocal() as session:
        created = await create_sample_work_item(session)

        stmt = select(WorkItem).where(WorkItem.id == created.id)
        result = await session.execute(stmt)
        fetched = result.scalar_one()

        print(
            {
                "created_id": str(created.id),
                "fetched": {
                    "id": str(fetched.id),
                    "component_id": fetched.component_id,
                    "severity": fetched.severity.value,
                    "status": fetched.status.value,
                    "title": fetched.title,
                    "signal_count": fetched.signal_count,
                },
            }
        )

    await database.close_engine()


if __name__ == "__main__":
    asyncio.run(main())

