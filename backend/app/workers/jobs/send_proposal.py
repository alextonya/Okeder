"""
Job : envoie la proposal publiée dans le groupe Telegram.
"""
import uuid

from app.database import AsyncSessionLocal


async def send_proposal_to_group(ctx: dict, proposal_id: str) -> None:
    async with AsyncSessionLocal() as db:
        from sqlalchemy.future import select

        from app.models.event import Event
        from app.models.group import Group
        from app.models.proposal import Proposal
        from app.services.notification_service import send_telegram_message

        proposal_result = await db.execute(
            select(Proposal).where(Proposal.id == uuid.UUID(proposal_id))
        )
        proposal = proposal_result.scalar_one_or_none()
        if not proposal:
            return

        event_result = await db.execute(select(Event).where(Event.id == proposal.event_id))
        event = event_result.scalar_one_or_none()
        if not event:
            return

        group_result = await db.execute(select(Group).where(Group.id == event.group_id))
        group = group_result.scalar_one_or_none()
        if not group or not group.telegram_chat_id:
            return

        text = _format_proposal_card(proposal)
        keyboard = _build_commitment_keyboard(proposal_id, str(proposal.event_id))
        await send_telegram_message(group.telegram_chat_id, text, reply_markup=keyboard)


def _format_proposal_card(proposal) -> str:
    lines = [f"<b>📅 {proposal.title}</b>"]
    if proposal.venue_name:
        lines.append(f"📍 {proposal.venue_name}")
    if proposal.date_time:
        lines.append(f"🕐 {proposal.date_time.strftime('%A %d %b, %H:%M')}")
    if proposal.price_per_person:
        lines.append(f"💶 €{proposal.price_per_person / 100:.0f}/person")

    lines.append("")
    lines.append("─────────────────")

    # Bloc légitimité (L4)
    if proposal.pct_budget_satisfied is not None:
        lines.append(f"✅ Budget: {float(proposal.pct_budget_satisfied) * 100:.0f}% satisfied")
    if proposal.pct_time_satisfied is not None:
        lines.append(f"✅ Timing: {float(proposal.pct_time_satisfied) * 100:.0f}% satisfied")
    if proposal.pct_prefs_satisfied is not None:
        lines.append(f"✅ Preferences: {float(proposal.pct_prefs_satisfied) * 100:.0f}% satisfied")
    if proposal.compromise_flagged and proposal.compromise_explanation:
        lines.append(f"⚠️ Compromise: {proposal.compromise_explanation}")

    return "\n".join(lines)


def _build_commitment_keyboard(proposal_id: str, event_id: str) -> dict:
    # Telegram limite callback_data à 64 chars — on utilise les 12 premiers chars des IDs
    p = proposal_id.replace("-", "")[:12]
    e = event_id.replace("-", "")[:12]
    return {
        "inline_keyboard": [[
            {"text": "👍 Interested", "callback_data": f"commit:soft:{p}:{e}"},
            {"text": "✅ I'm In",     "callback_data": f"commit:confirmed:{p}:{e}"},
            {"text": "🔒 Lock In",    "callback_data": f"commit:hard:{p}:{e}"},
        ]]
    }


async def enqueue_send_proposal(proposal_id: str) -> None:
    from app.workers.arq_settings import get_arq_pool
    pool = await get_arq_pool()
    await pool.enqueue_job("send_proposal_to_group", proposal_id)
