"""
PWA pages — accessibles sans Telegram.
/join/{event_id}       : page d'invitation (WhatsApp, SMS, email...)
/form/{event_id}       : formulaire préférences (same as Mini App + email field)
/result/{event_id}     : proposal visible en web
/push/subscribe        : enregistrer un abonnement push
/push/vapid-public-key : exposer la clé publique VAPID
"""
import os
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db

router = APIRouter()

# ─── Clé VAPID publique ───────────────────────────────────────────────────────

@router.get("/push/vapid-public-key")
async def vapid_public_key():
    return JSONResponse({"publicKey": settings.vapid_public_key})


# ─── Enregistrement abonnement push ──────────────────────────────────────────

@router.post("/push/subscribe")
async def subscribe_push(request: Request, db: AsyncSession = Depends(get_db)):
    from app.models.member import Member
    from app.models.push_subscription import PushSubscription

    body = await request.json()
    endpoint = body.get("endpoint", "")
    keys     = body.get("keys", {})
    member_id_str = body.get("member_id")  # UUID du membre si connu

    if not endpoint or not keys:
        return JSONResponse({"ok": False, "error": "Missing endpoint or keys"}, status_code=400)

    # Upsert subscription
    result = await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.keys = keys
    else:
        member_uuid = uuid.UUID(member_id_str) if member_id_str else None
        if not member_uuid:
            # Créer un membre anonyme
            m = Member(display_name="Anonymous", consent_level=1)
            db.add(m)
            await db.flush()
            member_uuid = m.id
        sub = PushSubscription(member_id=member_uuid, endpoint=endpoint, keys=keys)
        db.add(sub)

    await db.commit()
    return JSONResponse({"ok": True})


# ─── Page d'invitation ────────────────────────────────────────────────────────

@router.get("/create", response_class=HTMLResponse)
async def create_page():
    """Étape 1 : titre + nom + nombre d'invités."""
    CSS = (
        "*{box-sizing:border-box;margin:0;padding:0}"
        "body{font-family:-apple-system,sans-serif;background:#0f172a;color:#f1f5f9;"
        "min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}"
        ".card{max-width:400px;width:100%}"
        "h1{font-size:26px;font-weight:800;margin-bottom:6px}"
        ".sub{color:#64748b;font-size:14px;margin-bottom:28px;line-height:1.5}"
        "label{display:block;font-size:11px;font-weight:700;letter-spacing:.08em;"
        "color:#64748b;text-transform:uppercase;margin-bottom:8px}"
        "input[type=text]{width:100%;padding:14px;border-radius:12px;"
        "border:1.5px solid rgba(255,255,255,.1);background:#1e293b;"
        "color:#f1f5f9;font-size:16px;outline:none;margin-bottom:20px}"
        "input[type=text]:focus{border-color:#6366f1}"
        ".chips{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:24px}"
        ".chip{padding:10px 16px;border-radius:20px;border:1.5px solid rgba(255,255,255,.1);"
        "background:#1e293b;color:#f1f5f9;font-size:15px;font-weight:600;cursor:pointer}"
        "input[type=radio]{display:none}"
        "input[type=radio]:checked+label.chip{background:#6366f1;border-color:#6366f1}"
        "button{width:100%;padding:16px;border-radius:14px;border:none;"
        "background:#6366f1;color:white;font-size:16px;font-weight:600;cursor:pointer;margin-top:4px}"
        "button:active{opacity:.8}"
    )
    html = (
        "<!DOCTYPE html><html lang='en'><head>"
        "<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Okeder — Plan an outing</title>"
        "<style>" + CSS + "</style></head><body>"
        "<div class='card'>"
        "<h1>🎯 Okeder</h1>"
        "<p class='sub'>Plan a group outing — no app needed. You'll fill your preferences right after.</p>"
        "<form method='GET' action='/pwa/do-create'>"
        "<label>What are you planning? (optional)</label>"
        "<input type='text' name='title' placeholder='e.g. Friday drinks, Team dinner...'>"
        "<label>Your name</label>"
        "<input type='text' name='name' placeholder='Your first name' required>"
        "<label>How many people are you inviting? (not counting yourself)</label>"
        "<div class='chips'>"
        + "".join(
            f"<input type='radio' name='guests' id='g{n}' value='{n}' {'checked' if n==3 else ''}>"
            f"<label class='chip' for='g{n}'>{n}</label>"
            for n in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        ) +
        "</div>"
        "<button type='submit'>Continue — fill my preferences &#8594;</button>"
        "</form>"
        "</div></body></html>"
    )
    return HTMLResponse(content=html)


@router.get("/pwa/do-create", response_class=HTMLResponse)
async def pwa_do_create(
    title: str = "Group Outing",
    name: str = "Organiser",
    guests: int = 3,
    db: AsyncSession = Depends(get_db),
):
    """
    Crée l'event avec le bon expected_participants.
    Redirige vers le Mini App pour que l'organisateur soumette ses préférences.
    Après soumission, l'organisateur atterrit sur /share/{event_id}.
    """
    from datetime import datetime, timedelta, timezone
    from fastapi.responses import RedirectResponse
    from app.models.event import Event
    from app.models.group import Group, GroupMembership
    from app.models.member import Member

    # Créer l'organisateur
    organiser = Member(display_name=name)
    db.add(organiser)
    await db.flush()

    # Créer le groupe
    group = Group(name=title or "Group Outing", initiator_id=organiser.id)
    db.add(group)
    await db.flush()
    db.add(GroupMembership(group_id=group.id, member_id=organiser.id, role="initiator"))

    # expected = organisateur (1) + invités
    expected = max(2, int(guests) + 1)

    deadline = datetime.now(timezone.utc) + timedelta(hours=48)
    event = Event(
        group_id=group.id,
        title=title or "Group Outing",
        wizard_mode=False,
        constraint_deadline=deadline,
        created_by=organiser.id,
        expected_participants=expected,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    public_url = os.environ.get("PUBLIC_URL", "http://localhost:8000")

    # Redirige vers le Mini App pour que l'organisateur soumette ses préférences.
    # next_url indique où aller après soumission → /share/{event_id}
    next_url = f"{public_url}/share/{event.id}"
    mini_app_url = f"{public_url}/mini-app/{event.id}?next={next_url}"

    return RedirectResponse(url=mini_app_url)


@router.get("/share/{event_id}", response_class=HTMLResponse)
async def share_page(event_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Page de partage — boutons + compteur de réponses."""
    from app.models.event import Event
    from app.models.preference import Preference

    import urllib.parse as _ul
    base = os.environ.get("PUBLIC_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    join_url   = f"{base}/join/{event_id}"
    result_url = f"{base}/result/{event_id}"
    wa_result_url = "https://wa.me/?text=" + _ul.quote(f"The plan is ready! See it here: {result_url}")

    # Vérifier si la proposal est déjà publiée → rediriger directement
    from app.models.proposal import Proposal
    prop_check = await db.execute(
        select(Proposal).where(
            Proposal.event_id == uuid.UUID(event_id),
            Proposal.published == True,  # noqa: E712
        ).limit(1)
    )
    if prop_check.scalar_one_or_none():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=result_url)

    # Compteur de réponses
    try:
        ev_result = await db.execute(
            select(Event).where(Event.id == uuid.UUID(event_id))
        )
        event = ev_result.scalar_one_or_none()
        expected = event.expected_participants if event else 0
        pref_result = await db.execute(
            select(Preference).where(
                Preference.event_id == uuid.UUID(event_id),
                Preference.submitted_at.isnot(None),
                Preference.declined == False,  # noqa: E712
            )
        )
        submitted = len(pref_result.scalars().all())
    except Exception:
        expected = 0
        submitted = 0

    counter_text = f"{submitted}/{expected} preferences received" if expected else f"{submitted} preferences received"
    progress_pct = int(submitted / expected * 100) if expected else 0

    import urllib.parse as _ul
    msg = _ul.quote(f"You're invited to plan a group outing! Submit your preferences: {join_url}")
    wa_url  = f"https://wa.me/?text={msg}"
    tg_url  = f"https://t.me/share/url?url={_ul.quote(join_url)}&text={_ul.quote('You are invited to plan a group outing!')}"

    css = (
        "*{box-sizing:border-box;margin:0;padding:0}"
        "body{font-family:-apple-system,sans-serif;background:#0f172a;color:#f1f5f9;"
        "min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}"
        ".card{max-width:400px;width:100%}"
        "h1{font-size:22px;font-weight:700;margin-bottom:6px}"
        ".sub{color:#64748b;font-size:14px;margin-bottom:20px;line-height:1.5}"
        ".counter{background:#1e293b;border-radius:12px;padding:14px;margin-bottom:20px;"
        "display:flex;align-items:center;justify-content:space-between}"
        ".counter-text{font-size:14px;color:#94a3b8}"
        ".counter-num{font-size:22px;font-weight:800;color:#6366f1}"
        ".progress{height:6px;background:rgba(255,255,255,.08);border-radius:3px;margin-top:8px}"
        ".progress-fill{height:6px;background:#6366f1;border-radius:3px;transition:width .5s}"
        ".link-box{background:#1e293b;border:1px solid rgba(255,255,255,.08);border-radius:10px;"
        "padding:12px 14px;font-size:12px;color:#64748b;word-break:break-all;margin-bottom:16px}"
        ".btn{display:flex;align-items:center;gap:12px;width:100%;padding:14px 16px;"
        "border-radius:14px;border:none;font-size:15px;font-weight:600;cursor:pointer;"
        "text-decoration:none;margin-bottom:10px;transition:opacity .15s}"
        ".btn:active{opacity:.8}"
        ".wa{background:#25D366;color:white}"
        ".tg{background:#229ED9;color:white}"
        ".cp{background:#1e293b;color:#f1f5f9;border:1.5px solid rgba(255,255,255,.1)}"
        ".result{background:#6366f1;color:white;justify-content:center;margin-top:8px}"
        ".icon{font-size:20px}"
    )
    html = (
        "<!DOCTYPE html><html lang='en'><head>"
        "<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta http-equiv='refresh' content='15'>"
        "<title>Okeder — Share</title>"
        "<style>" + css + "</style></head><body>"
        "<div class='card'>"
        "<h1>✅ Your preferences saved!</h1>"
        "<p class='sub'>Now share this link with the people you're inviting. They can respond on any device — no app needed.</p>"

        # Compteur
        "<div class='counter'>"
        f"<div><div class='counter-text'>Responses received</div>"
        f"<div class='progress'><div class='progress-fill' style='width:{progress_pct}%'></div></div></div>"
        f"<div class='counter-num'>{submitted}/{expected}</div>"
        "</div>"

        # Bouton share natif (Web Share API) + fallbacks
        "<div id='share-zone'>"
        # Bouton principal : ouvre la feuille de partage native de l'OS
        f"<button class='btn wa' id='share-btn' onclick='doShare()'>"
        "<span class='icon'>🔗</span> Share with your contacts</button>"
        # Fallbacks visibles si Web Share non disponible
        "<div id='fallbacks' style='display:none'>"
        f"<a class='btn wa' href='{wa_url}' target='_blank'><span class='icon'>📱</span> WhatsApp</a>"
        f"<a class='btn tg' href='{tg_url}' target='_blank'><span class='icon'>✈️</span> Telegram</a>"
        "<button class='btn cp' id='copy-btn' onclick=\"navigator.clipboard.writeText('" + join_url + "');"
        "document.getElementById('copy-btn').innerHTML='<span class=\\'icon\\'>✅</span> Copied!';setTimeout(()=>document.getElementById('copy-btn').innerHTML='<span class=\\'icon\\'>📋</span> Copy link',2000)\">"
        "<span class='icon'>📋</span> Copy link</button>"
        "</div>"
        "</div>"
        "<div class='link-box' style='margin-top:10px'>" + join_url + "</div>"

        f"<a class='btn result' href='{result_url}'>See proposal when ready →</a>"
        "<hr style='border:1px solid rgba(255,255,255,.06);margin:16px 0'>"
        "<p style='font-size:13px;color:#64748b;margin-bottom:10px'>When the proposal is ready, share it:</p>"
        f"<button class='btn' style='background:#0f172a;border:1.5px solid rgba(255,255,255,.1);color:#94a3b8;justify-content:center'"
        f" onclick='doShareResult()'>📤 Share result with group</button>"
        "<p style='font-size:12px;color:#475569;margin-top:12px;text-align:center'>Page refreshes every 15s</p>"
        f"<script>"
        f"const JOIN_URL='{join_url}';const RESULT_URL='{result_url}';"
        "function doShare(){if(navigator.share){navigator.share({title:'Okeder',text:'Respond in 30s so we can plan our outing! 👉',url:JOIN_URL}).catch(()=>{});}"
        "else{document.getElementById('fallbacks').style.display='block';document.getElementById('share-btn').style.display='none';}}"
        "function doShareResult(){if(navigator.share){navigator.share({title:'Okeder — The plan is ready!',text:'The plan is ready! See it here 👉',url:RESULT_URL}).catch(()=>{});}"
        f"else{{window.open('{wa_result_url}','_blank');}}}"
        "</script>"
        "</div></body></html>"
    )
    return HTMLResponse(content=html)


@router.get("/join/{event_id}", response_class=HTMLResponse)
async def join_page(event_id: str, db: AsyncSession = Depends(get_db)):
    from app.models.event import Event
    from app.models.group import Group

    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        return HTMLResponse("<p>Invalid link</p>", status_code=400)

    event_result = await db.execute(select(Event).where(Event.id == event_uuid))
    event = event_result.scalar_one_or_none()
    if not event:
        return HTMLResponse("<p>Event not found</p>", status_code=404)

    group_result = await db.execute(select(Group).where(Group.id == event.group_id))
    group = group_result.scalar_one_or_none()
    group_name = group.name if group else "a group"
    public_url = os.environ.get("PUBLIC_URL", "http://localhost:8000")
    # /mini-app/{event_id} est la page de formulaire existante
    form_url = f"{public_url}/mini-app/{event_id}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Okeder — You're invited!</title>
  <style>
    * {{box-sizing:border-box;margin:0;padding:0}}
    body {{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
           background:#0f172a;color:#f1f5f9;min-height:100vh;
           display:flex;align-items:center;justify-content:center;padding:24px}}
    .card {{max-width:400px;width:100%;text-align:center}}
    .logo {{font-size:48px;margin-bottom:16px}}
    h1 {{font-size:24px;font-weight:700;margin-bottom:8px}}
    p {{color:#94a3b8;margin-bottom:32px;font-size:15px;line-height:1.6}}
    a {{display:block;background:#6366f1;color:white;text-decoration:none;
        padding:16px;border-radius:14px;font-weight:600;font-size:16px;
        transition:opacity 0.15s}}
    a:active {{opacity:0.8}}
    .sub {{font-size:12px;color:#475569;margin-top:16px}}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">🎉</div>
    <h1>You're invited!</h1>
    <p>Someone from <strong>{group_name}</strong> is planning a group outing and wants to know your preferences.</p>
    <p>It takes 30 seconds — no account needed.</p>
    <a href="{form_url}">Submit my preferences →</a>
    <p class="sub">Powered by Okeder · okeder.app</p>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


# ─── Page de résultat (proposal web) ─────────────────────────────────────────

@router.get("/result/{event_id}", response_class=HTMLResponse)
async def result_page(event_id: str, db: AsyncSession = Depends(get_db)):
    from app.models.proposal import Proposal
    from app.models.event import Event

    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        return HTMLResponse("<p>Invalid link</p>", status_code=400)

    prop_result = await db.execute(
        select(Proposal)
        .where(Proposal.event_id == event_uuid, Proposal.published == True)  # noqa: E712
        .order_by(Proposal.version.desc()).limit(1)
    )
    proposal = prop_result.scalar_one_or_none()

    if not proposal:
        # Pas encore de proposal — page d'attente
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="refresh" content="30">
  <title>Okeder — Waiting for proposal</title>
  <style>*{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,sans-serif;background:#0f172a;color:#f1f5f9;
          display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px}}
    .card{{max-width:400px;text-align:center}}
    .spin{{font-size:48px;animation:spin 2s linear infinite;display:inline-block}}
    @keyframes spin{{to{{transform:rotate(360deg)}}}}
    h1{{font-size:20px;margin:16px 0 8px}}
    p{{color:#94a3b8;font-size:14px}}
  </style>
</head>
<body>
  <div class="card">
    <div class="spin">⏳</div>
    <h1>Collecting preferences...</h1>
    <p>The proposal will appear here once everyone has responded.<br>This page refreshes automatically.</p>
  </div>
</body>
</html>"""
        return HTMLResponse(content=html)

    # Formatter la proposal
    lj = proposal.legitimacy_json or {{}}
    import urllib.parse as _ul

    venue_block = ""
    if proposal.venue_name:
        venue_block += f"<p class='venue-name'>📍 <strong>{proposal.venue_name}</strong></p>"
    if proposal.venue_address:
        venue_block += f"<p class='venue-addr'>🗺 {proposal.venue_address}</p>"
    if proposal.external_url:
        venue_block += f'<a class="maps-btn" href="{proposal.external_url}" target="_blank">📌 Open in Google Maps</a>'

    date_str = ""
    if proposal.date_time:
        date_str = proposal.date_time.strftime("%A %d %B at %H:%M")
    elif lj.get("datetime_hint") and lj["datetime_hint"] != "TBD":
        date_str = lj["datetime_hint"]

    vibe = lj.get("vibe_proposed") or lj.get("vibe") or ""
    activity = lj.get("activity") or ""

    public_url = os.environ.get("PUBLIC_URL", "http://localhost:8000")
    vapid_key = settings.vapid_public_key

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Okeder — Group Outing Proposal</title>
  <link rel="manifest" href="/manifest.json">
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
          background:#0f172a;color:#f1f5f9;padding:16px;min-height:100vh}}
    .header{{text-align:center;padding:24px 0 16px}}
    .logo{{font-size:32px;margin-bottom:8px}}
    h1{{font-size:22px;font-weight:700;color:#6366f1}}
    .card{{background:#1e293b;border-radius:16px;padding:20px;margin:12px 0}}
    .vibe{{font-size:20px;font-weight:700;margin-bottom:8px}}
    .date{{color:#94a3b8;font-size:14px;margin-bottom:4px}}
    .venue-name{{font-size:17px;font-weight:600;margin-bottom:4px}}
    .venue-addr{{color:#94a3b8;font-size:13px;margin-bottom:12px}}
    .maps-btn{{display:inline-block;background:#0f172a;color:#6366f1;
               text-decoration:none;padding:10px 16px;border-radius:10px;
               font-size:13px;font-weight:600;border:1px solid #334155}}
    .price{{font-size:15px;margin-top:12px;color:#94a3b8}}
    .metric{{display:flex;align-items:center;gap:8px;padding:8px 0;
             border-bottom:1px solid rgba(255,255,255,0.06);font-size:14px}}
    .metric:last-child{{border-bottom:none}}
    .commit-row{{display:flex;gap:8px;margin-top:16px}}
    .btn{{flex:1;padding:14px 8px;border:none;border-radius:12px;
          font-weight:600;font-size:14px;cursor:pointer;transition:opacity 0.15s}}
    .btn:active{{opacity:0.8}}
    .btn-soft{{background:#1e293b;color:#94a3b8;border:1px solid #334155}}
    .btn-confirm{{background:#6366f1;color:white}}
    .btn-hard{{background:#059669;color:white}}
    .push-banner{{background:#1e293b;border:1px solid #334155;border-radius:12px;
                  padding:14px;margin:12px 0;display:flex;align-items:center;gap:12px}}
    .push-banner p{{font-size:13px;color:#94a3b8;flex:1}}
    .push-btn{{background:#6366f1;color:white;border:none;padding:8px 14px;
               border-radius:8px;font-size:13px;cursor:pointer;white-space:nowrap}}
    #push-done{{display:none;color:#34d399;font-size:13px;text-align:center;padding:8px}}
  </style>
</head>
<body>
  <div class="header">
    <div class="logo">🎯</div>
    <h1>Your group outing</h1>
  </div>

  <!-- Bloc 1: Quoi & Quand -->
  <div class="card">
    <div class="vibe">{vibe.capitalize() if vibe else "Group Outing"} {'• ' + activity.capitalize() if activity and activity != vibe else ''}</div>
    {('<div class="date">📅 ' + date_str + '</div>') if date_str else ''}
    {('<div class="price">💶 ~€' + str(int(proposal.price_per_person / 100)) + '/person</div>') if proposal.price_per_person else ''}
  </div>

  <!-- Bloc 2: Où -->
  {('<div class="card">' + venue_block + '</div>') if venue_block else ''}

  <!-- Bloc 3: Métriques -->
  <div class="card">
    {'<div class="metric">✅ Budget: ' + str(int(float(proposal.pct_budget_satisfied or 0)*100)) + '% satisfied</div>' if proposal.pct_budget_satisfied is not None else ''}
    {'<div class="metric">'+('✅' if float(proposal.pct_time_satisfied or 0)>=0.7 else '⚠️')+' Timing: ' + str(int(float(proposal.pct_time_satisfied or 0)*100)) + '% satisfied</div>' if proposal.pct_time_satisfied is not None else ''}
    {'<div class="metric">✅ Vibe & Activity (' + vibe.capitalize() + (' + ' + activity.capitalize() if activity != vibe else '') + '): ' + str(int(float(proposal.pct_prefs_satisfied or 0)*100)) + '% match</div>' if vibe else ''}
  </div>

  <!-- Push notification opt-in -->
  <div class="push-banner" id="push-banner">
    <p>🔔 Get notified when updates arrive</p>
    <button class="push-btn" onclick="subscribePush()">Enable</button>
  </div>
  <div id="push-done">✅ Notifications enabled!</div>

  <!-- Commitment buttons -->
  <div class="commit-row">
    <button class="btn btn-soft" onclick="commit('soft')">👍 Interested</button>
    <button class="btn btn-confirm" onclick="commit('confirmed')">✅ I'm In</button>
    <button class="btn btn-hard" onclick="commit('hard')">🔒 Lock In</button>
  </div>

  <script>
    const EVENT_ID = "{event_id}";
    const BACKEND  = "{public_url}";
    const VAPID_KEY = "{vapid_key}";

    // Push subscription
    async function subscribePush() {{
      if (!('serviceWorker' in navigator) || !('PushManager' in window)) {{
        alert('Push not supported on this browser');
        return;
      }}
      const reg = await navigator.serviceWorker.ready;
      const perm = await Notification.requestPermission();
      if (perm !== 'granted') return;

      const sub = await reg.pushManager.subscribe({{
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_KEY),
      }});

      await fetch(BACKEND + '/push/subscribe', {{
        method: 'POST',
        headers: {{'Content-Type':'application/json'}},
        body: JSON.stringify({{
          endpoint: sub.endpoint,
          keys: {{ p256dh: btoa(String.fromCharCode(...new Uint8Array(sub.getKey('p256dh')))),
                   auth: btoa(String.fromCharCode(...new Uint8Array(sub.getKey('auth')))) }},
        }}),
      }});

      document.getElementById('push-banner').style.display = 'none';
      document.getElementById('push-done').style.display = 'block';
    }}

    async function commit(level) {{
      alert('Commitment "' + level + '" recorded! (Full commitment flow coming soon)');
    }}

    function urlBase64ToUint8Array(base64String) {{
      const padding = '='.repeat((4 - base64String.length % 4) % 4);
      const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
      const raw = window.atob(base64);
      return new Uint8Array([...raw].map(c => c.charCodeAt(0)));
    }}

    // Enregistrer le service worker
    if ('serviceWorker' in navigator) {{
      navigator.serviceWorker.register('/sw.js').catch(() => {{}});
    }}
    // Masquer la bannière push si déjà accordé
    if (Notification && Notification.permission === 'granted') {{
      document.getElementById('push-banner').style.display = 'none';
    }}
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)
