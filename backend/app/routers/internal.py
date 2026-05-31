"""
Endpoints internes appelés par le bot Telegram (pas exposés publiquement).
Pas d'auth Clerk — le bot s'authentifie avec le TELEGRAM_BOT_TOKEN partagé.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db
from app.models.event import Event, EventStatus
from app.models.group import Group, GroupMembership
from app.models.member import Member
from app.models.preference import Preference

router = APIRouter()


def _verify_bot_token(x_bot_token: str = Header(default="")) -> None:
    if x_bot_token != settings.telegram_bot_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


# ─── Enregistrement groupe / membre ──────────────────────────────────────────

@router.post("/register-group", status_code=status.HTTP_201_CREATED)
async def register_group(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_bot_token),
):
    """Enregistre ou met à jour un groupe Telegram et son initiateur."""
    chat_id: int = body["telegram_chat_id"]
    chat_title: str = body.get("chat_title", "Group")
    initiator_tg_id: int | None = body.get("initiator_telegram_id")
    initiator_name: str = body.get("initiator_name", "")

    # Upsert membre initiateur
    initiator = None
    if initiator_tg_id:
        result = await db.execute(select(Member).where(Member.telegram_user_id == initiator_tg_id))
        initiator = result.scalar_one_or_none()
        if not initiator:
            initiator = Member(
                telegram_user_id=initiator_tg_id,
                display_name=initiator_name or str(initiator_tg_id),
            )
            db.add(initiator)
            await db.flush()

    # Upsert groupe
    result = await db.execute(select(Group).where(Group.telegram_chat_id == chat_id))
    group = result.scalar_one_or_none()
    if not group:
        group = Group(
            telegram_chat_id=chat_id,
            name=chat_title,
            initiator_id=initiator.id if initiator else None,
        )
        db.add(group)
        await db.flush()

    # Upsert membership de l'initiateur
    if initiator:
        exists = await db.execute(
            select(GroupMembership).where(
                GroupMembership.group_id == group.id,
                GroupMembership.member_id == initiator.id,
            )
        )
        if not exists.scalar_one_or_none():
            db.add(GroupMembership(group_id=group.id, member_id=initiator.id, role="initiator"))

    await db.commit()
    return {"group_id": str(group.id)}


@router.post("/register-member", status_code=status.HTTP_201_CREATED)
async def register_member(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_bot_token),
):
    """Enregistre un membre Telegram et l'ajoute au groupe si besoin."""
    tg_id: int = body["telegram_user_id"]
    tg_name: str = body.get("display_name", str(body["telegram_user_id"]))
    chat_id: int | None = body.get("telegram_chat_id")

    result = await db.execute(select(Member).where(Member.telegram_user_id == tg_id))
    member = result.scalar_one_or_none()
    if not member:
        member = Member(telegram_user_id=tg_id, display_name=tg_name)
        db.add(member)
        await db.flush()
    else:
        if member.display_name != tg_name:
            member.display_name = tg_name

    if chat_id:
        group_result = await db.execute(select(Group).where(Group.telegram_chat_id == chat_id))
        group = group_result.scalar_one_or_none()
        if group:
            exists = await db.execute(
                select(GroupMembership).where(
                    GroupMembership.group_id == group.id,
                    GroupMembership.member_id == member.id,
                )
            )
            if not exists.scalar_one_or_none():
                db.add(GroupMembership(group_id=group.id, member_id=member.id, role="member"))

    await db.commit()
    return {"member_id": str(member.id)}


# ─── Création d'event ─────────────────────────────────────────────────────────

@router.post("/create-event", status_code=status.HTTP_201_CREATED)
async def create_event(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_bot_token),
):
    """Crée un event depuis le bot (après mention @Okeder)."""
    from datetime import datetime, timedelta, timezone

    chat_id: int = body["telegram_chat_id"]

    group_result = await db.execute(select(Group).where(Group.telegram_chat_id == chat_id))
    group = group_result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")

    # Chaque @OkederBot crée un nouvel event distinct (préremplissage par event_id)
    # Un event précédent reste en DB mais n'est plus actif
    deadline = datetime.now(timezone.utc) + timedelta(hours=48)
    event = Event(
        group_id=group.id,
        title=body.get("title"),
        location=body.get("location"),      # ex: "Paris", "Bastille", "London"
        wizard_mode=body.get("wizard_mode", True),
        constraint_deadline=deadline,
        created_by=group.initiator_id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    # Lancer la collecte de contraintes (DMs aux membres)
    from app.workers.jobs.collect_constraints import enqueue_collect_constraints
    await enqueue_collect_constraints(str(event.id))

    return {"event_id": str(event.id), "status": event.status}


# ─── Préférences ─────────────────────────────────────────────────────────────

@router.post("/submit-preferences")
async def submit_preferences_from_bot(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_bot_token),
):
    """Soumet les préférences d'un membre depuis le bot (après le FSM DM)."""
    from datetime import datetime, timezone

    from app.services.preference_parser import parse_budget, parse_availability

    tg_id: int = body["telegram_user_id"]
    event_id: str = body["event_id"]

    member_result = await db.execute(select(Member).where(Member.telegram_user_id == tg_id))
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    import uuid
    event_uuid = uuid.UUID(event_id)

    # Parser les réponses brutes
    budget_min, budget_max = parse_budget(body.get("budget_raw", ""))
    available_slots = parse_availability(body.get("availability_raw", ""))
    prefs_raw = body.get("preferences_raw", "")

    # Séparer hard constraints et soft prefs
    hard_keywords = ["no ", "not ", "without ", "never ", "wheelchair", "halal", "vegan", "kosher"]
    hard_constraints = [w.strip() for w in prefs_raw.split(",") if any(k in w.lower() for k in hard_keywords)]
    soft_preferences = [w.strip() for w in prefs_raw.split(",") if w.strip() and w.strip() not in hard_constraints]

    # Upsert préférence
    pref_result = await db.execute(
        select(Preference).where(
            Preference.event_id == event_uuid,
            Preference.member_id == member.id,
        )
    )
    pref = pref_result.scalar_one_or_none()
    if pref:
        pref.budget_min = budget_min
        pref.budget_max = budget_max
        pref.available_slots = available_slots
        pref.hard_constraints = hard_constraints
        pref.soft_preferences = soft_preferences
        pref.raw_answers = body
        pref.submitted_at = datetime.now(timezone.utc)
        pref.declined = False
    else:
        pref = Preference(
            event_id=event_uuid,
            member_id=member.id,
            budget_min=budget_min,
            budget_max=budget_max,
            available_slots=available_slots,
            hard_constraints=hard_constraints,
            soft_preferences=soft_preferences,
            raw_answers=body,
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(pref)

    await db.commit()

    # Vérifier quorum
    from app.workers.jobs.collect_constraints import check_and_trigger_engine
    await check_and_trigger_engine(event_id, db)

    return {"ok": True}


@router.post("/preference-declined")
async def preference_declined(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_bot_token),
):
    """Marque un membre comme ayant refusé de participer à l'event."""
    from datetime import datetime, timezone
    import uuid

    tg_id: int = body["telegram_user_id"]
    event_id: str = body["event_id"]

    member_result = await db.execute(select(Member).where(Member.telegram_user_id == tg_id))
    member = member_result.scalar_one_or_none()
    if not member:
        return {"ok": True}

    pref = Preference(
        event_id=uuid.UUID(event_id),
        member_id=member.id,
        declined=True,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(pref)
    await db.commit()
    return {"ok": True}


# ─── Commitment depuis bot ────────────────────────────────────────────────────

@router.post("/commitment")
async def commitment_from_bot(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_bot_token),
):
    """Enregistre un commitment depuis le clavier inline Telegram.
    proposal_prefix et event_prefix : 12 premiers chars de l'UUID sans tirets.
    """
    from sqlalchemy import text as sa_text
    from app.models.commitment import Commitment, CommitmentLevel
    from app.models.proposal import Proposal

    tg_id: int = body["telegram_user_id"]
    proposal_prefix: str = body["proposal_id"]   # peut être un prefix court ou un UUID complet
    event_prefix: str = body.get("event_id", "")
    level: str = body.get("level", CommitmentLevel.SOFT)

    member_result = await db.execute(select(Member).where(Member.telegram_user_id == tg_id))
    member = member_result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    # Retrouver la proposal par prefix (LIKE sur UUID sans tirets)
    prop_result = await db.execute(
        select(Proposal).where(
            sa_text(f"REPLACE(proposals.id::text, '-', '') LIKE '{proposal_prefix}%'")
        ).limit(1)
    )
    proposal = prop_result.scalar_one_or_none()
    if not proposal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    c_result = await db.execute(
        select(Commitment).where(
            Commitment.proposal_id == proposal.id,
            Commitment.member_id == member.id,
        )
    )
    commitment = c_result.scalar_one_or_none()
    if commitment:
        commitment.level = level
    else:
        commitment = Commitment(proposal_id=proposal.id, member_id=member.id, level=level)
        db.add(commitment)

    await db.commit()

    from app.routers.ws import broadcast_commitment_update
    await broadcast_commitment_update(str(proposal.id))

    # Retourner l'event_id pour le DM récapitulatif
    return {"ok": True, "event_id": str(proposal.event_id), "proposal_id": str(proposal.id)}


# ─── Résumé membre (pour DM après commitment) ────────────────────────────────

@router.get("/member-summary")
async def member_summary(
    telegram_user_id: int,
    event_id: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_bot_token),
):
    """Retourne les préférences + commitment d'un membre pour un event."""
    import uuid as _uuid

    result = await db.execute(select(Member).where(Member.telegram_user_id == telegram_user_id))
    member = result.scalar_one_or_none()
    if not member:
        return {"found": False}

    from app.models.commitment import Commitment
    from app.models.preference import Preference
    from app.models.proposal import Proposal

    try:
        event_uuid = _uuid.UUID(event_id)
    except ValueError:
        return {"found": False}

    # Préférences
    pref_result = await db.execute(
        select(Preference).where(
            Preference.event_id == event_uuid,
            Preference.member_id == member.id,
        )
    )
    pref = pref_result.scalar_one_or_none()

    # Proposal courante
    prop_result = await db.execute(
        select(Proposal)
        .where(Proposal.event_id == event_uuid, Proposal.published == True)  # noqa: E712
        .order_by(Proposal.version.desc()).limit(1)
    )
    proposal = prop_result.scalar_one_or_none()

    # Commitment
    commitment_level = None
    if proposal:
        c_result = await db.execute(
            select(Commitment).where(
                Commitment.proposal_id == proposal.id,
                Commitment.member_id == member.id,
            )
        )
        c = c_result.scalar_one_or_none()
        commitment_level = c.level if c else None

    raw = pref.raw_answers or {} if pref else {}

    return {
        "found": True,
        "member_name": member.display_name,
        "commitment_level": commitment_level,
        "proposal_id": str(proposal.id) if proposal else None,
        "preferences": {
            "vibe":            raw.get("vibe", []),
            "activity":        raw.get("activity", []),
            "departure_text":  raw.get("departure_text"),
            "travel_time_max": raw.get("travel_time_max"),
            "budget_min":      pref.budget_min if pref else None,
            "budget_max":      pref.budget_max if pref else None,
            "hard_constraints": pref.hard_constraints or [] if pref else [],
        } if pref else None,
    }


# ─── Rating depuis bot ────────────────────────────────────────────────────────

@router.post("/rating")
async def rating_from_bot(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_bot_token),
):
    """Enregistre une note post-event depuis le bot."""
    import uuid
    from app.models.event import Event

    tg_id: int = body["telegram_user_id"]
    event_id: str = body["event_id"]
    score: int = body["score"]

    member_result = await db.execute(select(Member).where(Member.telegram_user_id == tg_id))
    member = member_result.scalar_one_or_none()
    if not member:
        return {"ok": True}

    # TODO M6 : stocker le rating dans une table dédiée + déclencher update_behavioral_profile
    # Pour M1 : log seulement
    return {"ok": True, "score": score}
