"""
Wizard of Oz endpoints — réservés à l'initiateur authentifié.
Permettent de piloter manuellement le cycle de coordination pendant M0–M2.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.database import get_db
from app.deps import get_current_member
from app.models.event import Event, EventStatus
from app.models.member import Member

router = APIRouter()

VALID_TRANSITIONS = {
    EventStatus.COLLECTING: [EventStatus.DECIDING],
    EventStatus.DECIDING: [EventStatus.PROPOSED],
    EventStatus.PROPOSED: [EventStatus.COMMITTING],
    EventStatus.COMMITTING: [EventStatus.BOOKING],
    EventStatus.BOOKING: [EventStatus.CONFIRMED],
    EventStatus.CONFIRMED: [EventStatus.COMPLETED],
}


@router.get("/events")
async def list_wizard_events(
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    result = await db.execute(select(Event).where(Event.created_by == current_member.id))
    events = result.scalars().all()
    return [{"id": str(e.id), "title": e.title, "status": e.status, "wizard_mode": e.wizard_mode} for e in events]


@router.get("/events/{event_id}")
async def get_wizard_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    """Vue complète Wizard : event + membres + préférences + proposal courante."""
    from sqlalchemy.future import select as sa_select

    from app.models.commitment import Commitment
    from app.models.group import Group, GroupMembership
    from app.models.preference import Preference
    from app.models.proposal import Proposal

    event_result = await db.execute(sa_select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    # Membres du groupe
    members_result = await db.execute(
        sa_select(Member, GroupMembership.role)
        .join(GroupMembership, Member.id == GroupMembership.member_id)
        .where(GroupMembership.group_id == event.group_id)
    )
    members_data = members_result.all()

    # Préférences soumises
    prefs_result = await db.execute(
        sa_select(Preference).where(Preference.event_id == event_id)
    )
    prefs = prefs_result.scalars().all()
    prefs_by_member = {str(p.member_id): p for p in prefs}

    members_list = []
    for member, role in members_data:
        pref = prefs_by_member.get(str(member.id))
        members_list.append({
            "id": str(member.id),
            "display_name": member.display_name,
            "telegram_id": member.telegram_user_id,
            "role": role,
            "preference_status": (
                "declined" if pref and pref.declined
                else "submitted" if pref and pref.submitted_at
                else "pending"
            ),
            "preference": {
                "budget_min": pref.budget_min,
                "budget_max": pref.budget_max,
                "category_prefs": pref.category_prefs,
                "hard_constraints": pref.hard_constraints,
                "soft_preferences": pref.soft_preferences,
                "available_slots": pref.available_slots,
            } if pref and not pref.declined else None,
        })

    # Proposal courante
    prop_result = await db.execute(
        sa_select(Proposal)
        .where(Proposal.event_id == event_id)
        .order_by(Proposal.version.desc())
        .limit(1)
    )
    proposal = prop_result.scalar_one_or_none()
    proposal_data = None
    if proposal:
        # Commitments
        c_result = await db.execute(
            sa_select(Commitment).where(Commitment.proposal_id == proposal.id)
        )
        commits = c_result.scalars().all()
        proposal_data = {
            "id": str(proposal.id),
            "version": proposal.version,
            "title": proposal.title,
            "venue_name": proposal.venue_name,
            "venue_address": proposal.venue_address,
            "date_time": proposal.date_time.isoformat() if proposal.date_time else None,
            "price_per_person": proposal.price_per_person,
            "category": proposal.category,
            "external_url": proposal.external_url,
            "pct_budget_satisfied": float(proposal.pct_budget_satisfied) if proposal.pct_budget_satisfied else None,
            "pct_time_satisfied": float(proposal.pct_time_satisfied) if proposal.pct_time_satisfied else None,
            "pct_prefs_satisfied": float(proposal.pct_prefs_satisfied) if proposal.pct_prefs_satisfied else None,
            "compromise_flagged": proposal.compromise_flagged,
            "compromise_explanation": proposal.compromise_explanation,
            "generated_by": proposal.generated_by,
            "published": proposal.published,
            "commitments": {
                "soft": sum(1 for c in commits if c.level == "soft"),
                "confirmed": sum(1 for c in commits if c.level == "confirmed"),
                "hard": sum(1 for c in commits if c.level == "hard"),
            },
        }

    return {
        "id": str(event.id),
        "title": event.title,
        "status": event.status,
        "wizard_mode": event.wizard_mode,
        "constraint_deadline": event.constraint_deadline.isoformat() if event.constraint_deadline else None,
        "members": members_list,
        "submitted_count": sum(1 for m in members_list if m["preference_status"] == "submitted"),
        "total_members": len(members_list),
        "proposal": proposal_data,
    }


@router.post("/events/{event_id}/advance-status")
async def advance_status(
    event_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    target = body.get("status")
    allowed = VALID_TRANSITIONS.get(event.status, [])
    if target not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition {event.status} → {target}. Allowed: {allowed}",
        )
    event.status = target
    await db.commit()
    return {"status": event.status}


@router.post("/events/{event_id}/toggle-auto")
async def toggle_auto_mode(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    """Bascule wizard_mode ON/OFF. Si OFF → le prochain quorum publie automatiquement."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    event.wizard_mode = not event.wizard_mode
    await db.commit()
    return {"wizard_mode": event.wizard_mode}


@router.post("/events/{event_id}/trigger-engine")
async def trigger_engine(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    """Déclencher manuellement le constraint engine (L3)."""
    from app.workers.jobs.run_decision_engine import enqueue_run_decision_engine
    await enqueue_run_decision_engine(str(event_id))
    return {"ok": True, "message": "Engine job enqueued"}


@router.post("/events/{event_id}/send-proposal")
async def wizard_send_proposal(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    """Publie la proposal courante dans le groupe Telegram."""
    from app.models.proposal import Proposal
    from app.workers.jobs.send_proposal import enqueue_send_proposal

    result = await db.execute(
        select(Proposal)
        .where(Proposal.event_id == event_id)
        .order_by(Proposal.version.desc())
        .limit(1)
    )
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No proposal for this event")

    proposal.published = True
    await db.commit()
    await enqueue_send_proposal(str(proposal.id))
    return {"ok": True, "proposal_id": str(proposal.id)}


@router.post("/events/{event_id}/proposals")
async def wizard_create_proposal(
    event_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    """Wizard: crée ou remplace la proposal manuellement."""
    from datetime import datetime

    from app.models.proposal import Proposal

    # Déterminer la version suivante
    result = await db.execute(
        select(Proposal).where(Proposal.event_id == event_id).order_by(Proposal.version.desc()).limit(1)
    )
    last = result.scalar_one_or_none()
    next_version = (last.version + 1) if last else 1

    date_time = None
    if body.get("date_time"):
        try:
            date_time = datetime.fromisoformat(body["date_time"])
        except ValueError:
            pass

    proposal = Proposal(
        event_id=event_id,
        version=next_version,
        title=body.get("title", "Group outing"),
        venue_name=body.get("venue_name"),
        venue_address=body.get("venue_address"),
        date_time=date_time,
        price_per_person=body.get("price_per_person"),
        category=body.get("category"),
        external_url=body.get("external_url"),
        pct_budget_satisfied=body.get("pct_budget_satisfied"),
        pct_time_satisfied=body.get("pct_time_satisfied"),
        pct_prefs_satisfied=body.get("pct_prefs_satisfied"),
        compromise_flagged=body.get("compromise_flagged", False),
        compromise_explanation=body.get("compromise_explanation"),
        generated_by="wizard",
        published=False,
    )
    db.add(proposal)

    # Mettre l'event en statut "proposed" si ce n'est pas déjà le cas
    event_result = await db.execute(select(Event).where(Event.id == event_id))
    event = event_result.scalar_one_or_none()
    if event and event.status in (EventStatus.COLLECTING, EventStatus.DECIDING):
        event.status = EventStatus.PROPOSED

    await db.commit()
    await db.refresh(proposal)
    return {"id": str(proposal.id), "version": proposal.version}


@router.patch("/proposals/{proposal_id}")
async def wizard_edit_proposal(
    proposal_id: uuid.UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_member: Member = Depends(get_current_member),
):
    """Wizard: édite une proposal non encore publiée."""
    from datetime import datetime

    from app.models.proposal import Proposal

    result = await db.execute(select(Proposal).where(Proposal.id == proposal_id))
    proposal = result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if proposal.published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot edit a published proposal. Create a new version instead.",
        )

    editable = ["title", "venue_name", "venue_address", "price_per_person", "category",
                "external_url", "pct_budget_satisfied", "pct_time_satisfied",
                "pct_prefs_satisfied", "compromise_flagged", "compromise_explanation"]
    for field in editable:
        if field in body:
            setattr(proposal, field, body[field])

    if "date_time" in body and body["date_time"]:
        try:
            proposal.date_time = datetime.fromisoformat(body["date_time"])
        except ValueError:
            pass

    await db.commit()
    return {"ok": True}
