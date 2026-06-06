"""
Synthèse d'un event : qui a répondu / décliné / en attente, et la répartition
des engagements (Interested / I'm In / Locked In).

- compute_event_stats : utilisé par le dashboard PWA et la synthèse Telegram.
- update_initiator_synthesis : DM privé édité en temps réel à l'initiateur Telegram.
"""
import uuid

from sqlalchemy.future import select

from app.config import settings


def _bot_id() -> int | None:
    token = settings.telegram_bot_token
    if token and ":" in token:
        try:
            return int(token.split(":")[0])
        except ValueError:
            return None
    return None


async def compute_event_stats(event_id: str, db) -> dict | None:
    from app.models.commitment import Commitment
    from app.models.event import Event
    from app.models.group import Group, GroupMembership
    from app.models.member import Member
    from app.models.preference import Preference
    from app.models.proposal import Proposal

    try:
        event_uuid = uuid.UUID(event_id)
    except (ValueError, TypeError):
        return None

    ev = await db.execute(select(Event).where(Event.id == event_uuid))
    event = ev.scalar_one_or_none()
    if not event:
        return None

    grp = await db.execute(select(Group).where(Group.id == event.group_id))
    group = grp.scalar_one_or_none()

    bot_id = _bot_id()

    # Membres du groupe (hors bot)
    members_res = await db.execute(
        select(Member)
        .join(GroupMembership, Member.id == GroupMembership.member_id)
        .where(GroupMembership.group_id == event.group_id)
    )
    members = [m for m in members_res.scalars().all() if m.telegram_user_id != bot_id]
    members_by_id = {m.id: m for m in members}

    # Préférences de l'event
    prefs_res = await db.execute(
        select(Preference).where(Preference.event_id == event_uuid)
    )
    prefs = prefs_res.scalars().all()
    pref_by_member = {p.member_id: p for p in prefs}

    # Inclure aussi les membres qui ont une préférence sans appartenance enregistrée
    for p in prefs:
        if p.member_id not in members_by_id:
            mm = await db.execute(select(Member).where(Member.id == p.member_id))
            m = mm.scalar_one_or_none()
            if m and m.telegram_user_id != bot_id:
                members_by_id[m.id] = m

    # Proposal publiée + engagements
    prop_res = await db.execute(
        select(Proposal)
        .where(Proposal.event_id == event_uuid, Proposal.published == True)  # noqa: E712
        .order_by(Proposal.version.desc()).limit(1)
    )
    proposal = prop_res.scalar_one_or_none()

    commit_by_member: dict = {}
    counts = {"soft": 0, "confirmed": 0, "hard": 0}
    if proposal:
        c_res = await db.execute(
            select(Commitment).where(Commitment.proposal_id == proposal.id)
        )
        for c in c_res.scalars().all():
            commit_by_member[c.member_id] = c.level
            if c.level in counts:
                counts[c.level] += 1

    # Liste des participants avec statut
    participants = []
    responded = declined = 0
    for mid, m in members_by_id.items():
        p = pref_by_member.get(mid)
        if p and p.declined:
            status = "declined"
            declined += 1
        elif p and p.submitted_at is not None:
            status = "responded"
            responded += 1
        else:
            status = "pending"
        participants.append({
            "name": m.display_name,
            "status": status,
            "commitment": commit_by_member.get(mid),
        })

    if event.expected_participants and event.expected_participants > 0:
        total = event.expected_participants
    else:
        total = len(members_by_id)

    pending = max(0, total - responded - declined)

    # Participants "partants" = I'm In (confirmed) + Locked In (hard)
    going = counts["confirmed"] + counts["hard"]

    # État de la réservation (L6b)
    booking = None
    if proposal:
        from app.services.booking import latest_booking
        be = await latest_booking(proposal.id, db)
        if be:
            cd = be.confirmation_data or {}
            booking = {
                "status": be.status,
                "method": be.method,
                "open_url": cd.get("open_url") or be.external_url,
                "thefork_url": cd.get("thefork_url"),
                "message": cd.get("message"),
                "party_size": cd.get("party_size"),
            }

    # Trier : répondu, décliné, en attente
    order = {"responded": 0, "declined": 1, "pending": 2}
    participants.sort(key=lambda x: order.get(x["status"], 3))

    return {
        "event_id": str(event.id),
        "title": event.title or (group.name if group else "Group outing"),
        "total": total,
        "responded": responded,
        "declined": declined,
        "pending": pending,
        "has_proposal": proposal is not None,
        "proposal_id": str(proposal.id) if proposal else None,
        "venue_name": proposal.venue_name if proposal else None,
        "venue_address": proposal.venue_address if proposal else None,
        "when": proposal.date_time.strftime("%d/%m %H:%M") if (proposal and proposal.date_time) else None,
        "commitments": counts,
        "going": going,
        "booking": booking,
        "participants": participants,
        "initiator_id": group.initiator_id if group else None,
    }


def render_synthesis_text(stats: dict) -> str:
    lines = [
        f"📊 <b>{stats['title']}</b> — live status",
        "",
        f"✅ Responded: <b>{stats['responded']}</b>/{stats['total']}",
    ]
    if stats["declined"]:
        lines.append(f"🙅 Can't make it: <b>{stats['declined']}</b>")
    lines.append(f"⏳ Waiting: <b>{stats['pending']}</b>")

    if stats["has_proposal"]:
        c = stats["commitments"]
        lines += [
            "",
            "🎉 <b>The plan is set — who's coming?</b>",
            f"👍 Interested: <b>{c['soft']}</b>",
            f"✅ I'm in: <b>{c['confirmed']}</b>",
            f"🔒 Locked in: <b>{c['hard']}</b>",
        ]
        bk = stats.get("booking")
        if bk:
            if bk.get("status") == "success":
                lines += ["", "📌 <b>Booking confirmed ✅</b>"]
            elif bk.get("status") == "in_progress":
                lines += ["", "📌 Booking requested — awaiting venue"]
    return "\n".join(lines)


async def update_initiator_synthesis(event_id: str, db) -> None:
    """
    Envoie/édite le DM de synthèse à l'initiateur Telegram (en place, temps réel).
    No-op si l'initiateur n'a pas de chat privé Telegram (ex : initiateur web → dashboard).
    """
    from app.models.event import Event
    from app.models.member import Member
    from app.services.notification_service import send_or_edit_telegram

    stats = await compute_event_stats(event_id, db)
    if not stats or not stats.get("initiator_id"):
        return

    init_res = await db.execute(select(Member).where(Member.id == stats["initiator_id"]))
    initiator = init_res.scalar_one_or_none()
    if not initiator or not initiator.telegram_user_id:
        return  # initiateur web (pas de DM Telegram) → suivi via dashboard

    ev_res = await db.execute(select(Event).where(Event.id == uuid.UUID(event_id)))
    event = ev_res.scalar_one_or_none()
    if not event:
        return

    text = render_synthesis_text(stats)
    chat_id = initiator.telegram_user_id

    msg_id = await send_or_edit_telegram(chat_id, text, event.initiator_summary_msg_id)

    # Persister chat/message id si nouveau message
    if msg_id and event.initiator_summary_msg_id != msg_id:
        event.initiator_summary_chat_id = chat_id
        event.initiator_summary_msg_id = msg_id
        await db.commit()
