"""
Job : exécute le constraint engine (L3+L4) et crée la proposal en DB.
"""
import uuid

from app.database import AsyncSessionLocal


async def run_decision_engine(ctx: dict, event_id: str) -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy.future import select

        from app.models.event import Event, EventStatus
        from app.models.preference import Preference
        from app.models.proposal import Proposal
        from app.services.constraint_engine import run_engine

        # Charger les préférences soumises
        prefs_result = await db.execute(
            select(Preference).where(
                Preference.event_id == uuid.UUID(event_id),
                Preference.submitted_at != None,  # noqa: E711
                Preference.declined == False,  # noqa: E712
            )
        )
        preferences = [
            {
                "budget_min": p.budget_min,
                "budget_max": p.budget_max,
                "available_slots": p.available_slots or [],
                "category_prefs": p.category_prefs or [],
                "hard_constraints": p.hard_constraints or [],
            }
            for p in prefs_result.scalars().all()
        ]

        spec = run_engine(preferences)

        # Déterminer la version suivante
        version_result = await db.execute(
            select(Proposal).where(Proposal.event_id == uuid.UUID(event_id))
            .order_by(Proposal.version.desc()).limit(1)
        )
        last = version_result.scalar_one_or_none()
        next_version = (last.version + 1) if last else 1

        proposal = Proposal(
            event_id=uuid.UUID(event_id),
            version=next_version,
            title=spec.title,
            category=spec.category,
            price_per_person=spec.budget_target_cents,
            pct_budget_satisfied=spec.pct_budget_satisfied,
            pct_time_satisfied=spec.pct_time_satisfied,
            pct_prefs_satisfied=spec.pct_prefs_satisfied,
            hard_constraints_met=spec.hard_constraints_met,
            compromise_flagged=spec.compromise_flagged,
            compromise_explanation=spec.compromise_explanation,
            legitimacy_json=spec.legitimacy_json,
            generated_by="engine",
            published=False,
        )
        db.add(proposal)

        # Mettre à jour le statut de l'event
        event_result = await db.execute(select(Event).where(Event.id == uuid.UUID(event_id)))
        event = event_result.scalar_one_or_none()
        if event:
            event.status = EventStatus.PROPOSED
        await db.commit()
        await db.refresh(proposal)

        # Publier automatiquement si pas en mode wizard
        if event and not event.wizard_mode:
            proposal.published = True
            await db.commit()
            from app.workers.jobs.send_proposal import enqueue_send_proposal
            await enqueue_send_proposal(str(proposal.id))


async def enqueue_run_decision_engine(event_id: str) -> None:
    from app.workers.arq_settings import get_arq_pool
    pool = await get_arq_pool()
    await pool.enqueue_job("run_decision_engine", event_id)
