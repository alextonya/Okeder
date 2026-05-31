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
    form_url = f"{public_url}/form/{event_id}"

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
