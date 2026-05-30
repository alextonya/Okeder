"""
Job : expire un event si la deadline de collecte est passée sans quorum.
"""
import uuid

from app.database import AsyncSessionLocal


async def expire_event(ctx: dict, event_id: str) -> None:
    async with AsyncSessionLocal() as db:
        from datetime import datetime, timezone

        from sqlalchemy.future import select

        from app.models.event import Event, EventStatus

        result = await db.execute(select(Event).where(Event.id == uuid.UUID(event_id)))
        event = result.scalar_one_or_none()
        if not event or event.status != EventStatus.COLLECTING:
            return

        if event.constraint_deadline and datetime.now(timezone.utc) >= event.constraint_deadline:
            # En mode non-wizard : tenter quand même avec les préférences disponibles
            if not event.wizard_mode:
                from app.workers.jobs.run_decision_engine import enqueue_run_decision_engine
                await enqueue_run_decision_engine(event_id)
            else:
                event.status = EventStatus.EXPIRED
                await db.commit()
