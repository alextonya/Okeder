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

    # ─── Date avec lien calendrier ────────────────────────────────────────────
    import urllib.parse as _ul
    cal_url = ""
    if proposal.date_time:
        dt = proposal.date_time
        date_label = dt.strftime("%A %d %B at %H:%M")
        cal_start = dt.strftime("%Y%m%dT%H%M%S")
        from datetime import timedelta as _td
        cal_end = (dt + _td(hours=2)).strftime("%Y%m%dT%H%M%S")
        venue_loc = _ul.quote((proposal.venue_name or "") + " " + (proposal.venue_address or ""))
        cal_url = (
            "https://calendar.google.com/calendar/render?action=TEMPLATE"
            "&text=" + _ul.quote("Okeder: " + (proposal.venue_name or "Group Outing"))
            + "&dates=" + cal_start + "/" + cal_end
            + "&location=" + venue_loc
        )
    elif lj.get("datetime_hint") and lj["datetime_hint"] not in ("TBD", ""):
        date_label = lj["datetime_hint"]
        # Construire lien calendrier depuis la date ISO si disponible
        date_iso = lj.get("proposed_date_iso")
        hour = lj.get("proposed_hour", 19)
        if date_iso:
            from datetime import date as _date, timedelta as _td
            d = _date.fromisoformat(date_iso)
            cal_start = d.strftime("%Y%m%d") + "T" + f"{hour:02d}0000"
            cal_end   = d.strftime("%Y%m%d") + "T" + f"{min(hour+2, 23):02d}0000"
            venue_loc = _ul.quote((proposal.venue_name or "") + " " + (proposal.venue_address or ""))
            cal_url = (
                "https://calendar.google.com/calendar/render?action=TEMPLATE"
                "&text=" + _ul.quote("Okeder: " + (proposal.venue_name or "Group Outing"))
                + "&dates=" + cal_start + "/" + cal_end
                + "&location=" + venue_loc
            )
    else:
        date_label = ""

    if date_label:
        lines.append("📅 " + date_label)
    if cal_url:
        lines.append('<a href="' + cal_url + '">📆 Add to Google Calendar</a>')

    if proposal.price_per_person and proposal.price_per_person > 0:
        lines.append("💶 ~€" + str(int(proposal.price_per_person / 100)) + "/person")

    lines.append("")
    lines.append("─────────────────")

    # ─── Vibe en exergue ──────────────────────────────────────────────────────
    VIBE_DISPLAY = {
        "casual":       "😌 Casual & Relaxed",
        "professional": "💼 Professional",
        "festive":      "🎉 Festive",
        "cosy":         "🍵 Cosy & Intimate",
        "outdoor":      "🌿 Outdoor",
        "cultural":     "🎨 Cultural",
    }
    ACTIVITY_DISPLAY = {
        "dinner":   "🍽 Dinner",
        "drinks":   "🍸 Drinks",
        "brunch":   "☕ Brunch",
        "lunch":    "🥗 Lunch",
        "cinema":   "🎬 Cinema",
        "concert":  "🎵 Concert",
        "activity": "🎮 Activity",
    }

    vibe     = lj.get("vibe_proposed") or lj.get("vibe") or ""
    activity = lj.get("activity") or ""
    pct_v    = float(proposal.pct_prefs_satisfied or 0) * 100
    vibe_lbl = VIBE_DISPLAY.get(vibe, vibe.capitalize() if vibe else "")
    act_lbl  = ACTIVITY_DISPLAY.get(activity, activity.capitalize() if activity else "")

    if vibe_lbl:
        lines.append("<b>" + vibe_lbl + "</b>  " + act_lbl)
        agree_icon = "✅" if pct_v >= 70 else "⚠️"
        lines.append(agree_icon + " " + str(int(pct_v)) + "% of the group agree on this vibe")

    lines.append("")

    # ─── Légitimité (L4) ──────────────────────────────────────────────────────
    if proposal.pct_budget_satisfied is not None:
        pct = float(proposal.pct_budget_satisfied) * 100
        icon = "✅" if pct >= 70 else "⚠️"
        lines.append(icon + " Budget: " + str(int(pct)) + "% satisfied")

    if proposal.pct_time_satisfied is not None:
        pct = float(proposal.pct_time_satisfied) * 100
        icon = "✅" if pct >= 70 else "⚠️"
        lines.append(icon + " Timing: " + str(int(pct)) + "% satisfied")

    # ─── Distances anonymisées — min/max/avg (#3) ─────────────────────────────
    distances = lj.get("distances", [])
    if distances:
        times = [d["est_min"] for d in distances]
        dists = [d["dist_km"] for d in distances]
        avg_t = int(sum(times) / len(times))
        avg_d = round(sum(dists) / len(dists), 1)
        min_t, max_t = min(times), max(times)

        if min_t == max_t:
            lines.append("🚶 Travel to venue: ~" + str(avg_t) + " min (" + str(avg_d) + " km avg)")
        else:
            lines.append(
                "🚶 Travel to venue: " + str(min_t) + "–" + str(max_t) + " min"
                + " (avg " + str(avg_t) + " min, " + str(avg_d) + " km)"
            )

        over = [d for d in distances if d.get("over_max") and d.get("max_min", 999) != 999]
        if over:
            n = len(over)
            lines.append(
                "⚠️ " + str(n) + " participant" + ("s" if n > 1 else "")
                + " exceed" + ("" if n > 1 else "s") + " their stated travel maximum"
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
