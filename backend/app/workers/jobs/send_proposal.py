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


def _format_proposal_card(proposal) -> str:  # noqa: C901
    import urllib.parse as _ul
    from datetime import timedelta as _td

    lj = proposal.legitimacy_json or {}
    lines = []

    # ═══════════════════════════════════════════════════════════
    # BLOC 1 — LE QUOI & LE QUAND
    # ═══════════════════════════════════════════════════════════
    VIBE_ICONS = {
        "casual": "😌", "professional": "💼", "festive": "🎉",
        "cosy": "🍵", "outdoor": "🌿", "cultural": "🎨",
    }
    ACTIVITY_ICONS = {
        "dinner": "🍽", "drinks": "🍸", "brunch": "☕",
        "lunch": "🥗", "cinema": "🎬", "concert": "🎵", "activity": "🎮",
    }

    vibe     = lj.get("vibe_proposed") or lj.get("vibe") or ""
    activity = lj.get("activity") or ""

    vibe_icon = VIBE_ICONS.get(vibe, "🎯")
    act_icon  = ACTIVITY_ICONS.get(activity, "")

    what = vibe_icon + " " + vibe.capitalize() if vibe else "🎯 Group Outing"
    if activity and activity != vibe:
        what += "  " + act_icon + " " + activity.capitalize()
    lines.append("<b>" + what + "</b>")

    # Date
    date_label = ""
    cal_start = cal_end = ""
    if proposal.date_time:
        dt = proposal.date_time
        date_label = dt.strftime("%A %d %B at %H:%M")
        cal_start  = dt.strftime("%Y%m%dT%H%M%S")
        cal_end    = (dt + _td(hours=2)).strftime("%Y%m%dT%H%M%S")
    elif lj.get("datetime_hint") and lj["datetime_hint"] not in ("TBD", ""):
        date_label = lj["datetime_hint"]
        date_iso   = lj.get("proposed_date_iso")
        hour       = int(lj.get("proposed_hour", 19))
        if date_iso:
            from datetime import date as _d
            d = _d.fromisoformat(date_iso)
            cal_start = d.strftime("%Y%m%d") + "T" + str(hour).zfill(2) + "0000"
            cal_end   = d.strftime("%Y%m%d") + "T" + str(min(hour + 2, 23)).zfill(2) + "0000"

    if date_label:
        lines.append("📅 " + date_label)

    lines.append("")

    # ═══════════════════════════════════════════════════════════
    # BLOC 2 — LE OÙ (lieu physique)
    # ═══════════════════════════════════════════════════════════
    if proposal.venue_name:
        lines.append("<b>📍 " + proposal.venue_name + "</b>")
    if proposal.venue_address:
        lines.append("🗺 " + proposal.venue_address)

    # Lien Google Maps vers le lieu physique exact
    v_lat = lj.get("venue_lat")
    v_lng = lj.get("venue_lng")
    if v_lat and v_lng:
        # Coordonnées GPS → pointe directement sur le bâtiment
        gmaps = "https://maps.google.com/?q=" + str(v_lat) + "," + str(v_lng) + "&z=17"
    elif proposal.venue_name and proposal.venue_address:
        # Nom + adresse → recherche Google Maps
        q = _ul.quote(proposal.venue_name + ", " + proposal.venue_address)
        gmaps = "https://maps.google.com/?q=" + q
    elif proposal.venue_name:
        gmaps = "https://maps.google.com/?q=" + _ul.quote(proposal.venue_name)
    else:
        gmaps = ""

    if gmaps:
        lines.append('<a href="' + gmaps + '">📌 Open in Google Maps</a>')

    if proposal.price_per_person and proposal.price_per_person > 0:
        lines.append("💶 ~€" + str(int(proposal.price_per_person / 100)) + "/person")

    # Lien calendrier
    if cal_start and cal_end:
        venue_loc = _ul.quote((proposal.venue_name or "") + " " + (proposal.venue_address or ""))
        cal_title = _ul.quote("Okeder: " + (proposal.venue_name or "Group Outing"))
        cal_url = (
            "https://calendar.google.com/calendar/render?action=TEMPLATE"
            "&text=" + cal_title
            + "&dates=" + cal_start + "/" + cal_end
            + "&location=" + venue_loc
        )
        lines.append('<a href="' + cal_url + '">📆 Add to Google Calendar</a>')

    lines.append("")
    lines.append("─────────────────")

    # ═══════════════════════════════════════════════════════════
    # BLOC 3 — POURQUOI (métriques)
    # ═══════════════════════════════════════════════════════════
    if proposal.pct_budget_satisfied is not None:
        pct = float(proposal.pct_budget_satisfied) * 100
        lines.append(("✅" if pct >= 70 else "⚠️") + " Budget: " + str(int(pct)) + "% satisfied")

    if proposal.pct_time_satisfied is not None:
        pct = float(proposal.pct_time_satisfied) * 100
        lines.append(("✅" if pct >= 70 else "⚠️") + " Timing: " + str(int(pct)) + "% satisfied")

    pct_v = float(proposal.pct_prefs_satisfied or 0) * 100
    if vibe:
        act_cap  = activity.capitalize() if activity and activity != vibe else ""
        label    = vibe.capitalize() + (" + " + act_cap if act_cap else "")
        lines.append(("✅" if pct_v >= 70 else "⚠️") + " Vibe & Activity (" + label + "): " + str(int(pct_v)) + "% match")

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
            lines.append("🚶 Travel to venue: " + str(min_t) + "–" + str(max_t) + " min (avg " + str(avg_t) + " min, " + str(avg_d) + " km)")
        over = [d for d in distances if d.get("over_max") and d.get("max_min", 999) != 999]
        if over:
            n = len(over)
            lines.append("⚠️ " + str(n) + " participant" + ("s" if n > 1 else "") + " exceed" + ("" if n > 1 else "s") + " their stated travel maximum")

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
