"""
Job : envoie la proposal publiée dans le groupe Telegram.
Proposal card enrichie : venue cliquable, distances, vibe, légitimité complète.
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

        prefix = ""
        if proposal.version > 1:
            prefix = f"🔄 <b>Updated proposal</b> (v{proposal.version} — more responses)\n\n"
        text = prefix + _format_proposal_card(proposal)
        keyboard = _build_commitment_keyboard(proposal_id, str(proposal.event_id))
        await send_telegram_message(group.telegram_chat_id, text, reply_markup=keyboard)


def _format_proposal_card(proposal) -> str:
    lj = proposal.legitimacy_json or {}
    lines = []

    # ─── En-tête ──────────────────────────────────────────────────────────────
    lines.append("<b>🎯 " + proposal.title + "</b>")

    # ─── Lieu ─────────────────────────────────────────────────────────────────
    if proposal.venue_name:
        lines.append("📍 <b>" + proposal.venue_name + "</b>")
    if proposal.venue_address:
        lines.append("🗺 " + proposal.venue_address)

    # Google Maps cliquable
    if proposal.external_url and "maps.google" in proposal.external_url:
        lines.append('<a href="' + proposal.external_url + '">📌 Open in Google Maps</a>')
    elif proposal.external_url:
        lines.append('<a href="' + proposal.external_url + '">🔗 More info</a>')

    # ─── Date / moment ────────────────────────────────────────────────────────
    if proposal.date_time:
        lines.append("🕐 " + proposal.date_time.strftime("%A %d %b, %H:%M"))
    elif lj.get("datetime_hint") and lj["datetime_hint"] not in ("TBD", ""):
        lines.append("📅 " + lj["datetime_hint"])

    if proposal.price_per_person and proposal.price_per_person > 0:
        lines.append("💶 ~€" + str(int(proposal.price_per_person / 100)) + "/person")

    lines.append("")
    lines.append("─────────────────")

    # ─── Légitimité (L4) ──────────────────────────────────────────────────────
    if proposal.pct_budget_satisfied is not None:
        pct = float(proposal.pct_budget_satisfied) * 100
        icon = "✅" if pct >= 70 else "⚠️"
        lines.append(icon + " Budget: " + str(int(pct)) + "% satisfied")

    if proposal.pct_time_satisfied is not None:
        pct = float(proposal.pct_time_satisfied) * 100
        icon = "✅" if pct >= 70 else "⚠️"
        lines.append(icon + " Timing: " + str(int(pct)) + "% satisfied")

    if proposal.pct_prefs_satisfied is not None:
        pct = float(proposal.pct_prefs_satisfied) * 100
        icon = "✅" if pct >= 70 else "⚠️"
        lines.append(icon + " Preferences: " + str(int(pct)) + "% match")

    # Vibe compatibility (#4)
    vibe = lj.get("vibe_proposed") or lj.get("vibe") or ""
    if vibe:
        lines.append("✅ Vibe: " + vibe.capitalize() + " ✓")

    # ─── Distances (#3) ───────────────────────────────────────────────────────
    distances = lj.get("distances", [])
    if distances:
        avg_km = sum(d["dist_km"] for d in distances) / len(distances)
        lines.append("🚶 Avg distance: " + str(round(avg_km, 1)) + " km")
        over = [d for d in distances if d.get("over_max") and d.get("max_min", 999) != 999]
        for d in over:
            lines.append(
                "⚠️ " + d["name"] + ": ~" + str(d["est_min"]) + " min"
                + " (max stated: " + str(d["max_min"]) + " min)"
            )

    # ─── Compromis ────────────────────────────────────────────────────────────
    if proposal.compromise_flagged and proposal.compromise_explanation:
        lines.append("⚠️ " + proposal.compromise_explanation)

    return "\n".join(lines)


def _build_commitment_keyboard(proposal_id: str, event_id: str) -> dict:
    p = proposal_id.replace("-", "")[:12]
    e = event_id.replace("-", "")[:12]
    return {
        "inline_keyboard": [[
            {"text": "👍 Interested", "callback_data": "commit:soft:" + p + ":" + e},
            {"text": "✅ I'm In",     "callback_data": "commit:confirmed:" + p + ":" + e},
            {"text": "🔒 Lock In",    "callback_data": "commit:hard:" + p + ":" + e},
        ]]
    }


async def enqueue_send_proposal(proposal_id: str) -> None:
    from app.workers.arq_settings import get_arq_pool
    pool = await get_arq_pool()
    await pool.enqueue_job("send_proposal_to_group", proposal_id)
