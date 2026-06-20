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
from app.services.session import member_id_from_request

router = APIRouter()

_NO_CACHE = {"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"}


async def _current_account(request: Request, db: AsyncSession):
    """Retourne le Member du compte connecté (email vérifié) ou None."""
    from app.models.member import Member
    mid = member_id_from_request(request)
    if not mid:
        return None
    try:
        res = await db.execute(select(Member).where(Member.id == uuid.UUID(mid)))
        return res.scalar_one_or_none()
    except ValueError:
        return None


def _auth_gate_page(next_url: str = "/events") -> HTMLResponse:
    """Page de connexion / création de compte (email + OTP). Redirige vers next_url."""
    from app.routers._pwa_ui import shell
    body = (
        "<div class='wrap'>"
        "<div class='brand' style='margin-bottom:22px'><span class='dot'></span>Okeder</div>"
        "<span class='eyebrow'>Sign in</span>"
        "<h1 style='margin-top:12px'>Your account.</h1>"
        "<p class='lead'>Plan outings and follow who's in — in real time. "
        "We'll email you a one-time code, no password.</p>"

        "<div id='step-email' style='margin-top:26px'>"
        "<div class='section'><label class='fld'>Email <span class='req'>*</span></label>"
        "<input type='email' id='email' placeholder='you@email.com' autocomplete='email'></div>"
        "<button class='btn btn-primary' id='send-btn' onclick='sendCode()'>Send me a code →</button>"
        "</div>"

        "<div id='step-code' style='display:none;margin-top:26px'>"
        "<p id='code-intro' class='muted' style='font-size:14px;margin-bottom:14px'></p>"
        "<div class='section'><label class='fld'>Enter the 6-digit code</label>"
        "<input type='text' id='code' inputmode='numeric' maxlength='6' placeholder='______' "
        "style='letter-spacing:8px;text-align:center;font-size:24px;font-weight:800'></div>"
        "<div class='section' id='name-row'><label class='fld'>Your name <span class='req'>*</span></label>"
        "<input type='text' id='name' placeholder='Your first name' autocomplete='given-name'></div>"
        "<button class='btn btn-primary' id='verify-btn' onclick='verifyCode()'>Verify &amp; continue →</button>"
        "<p class='hint center' id='resend' style='margin-top:14px;cursor:pointer'>Didn't get it? Send again</p>"
        "</div>"

        "<p id='msg' class='hint center' style='margin-top:16px;color:var(--accent)'></p>"

        "<script>"
        "var EMAIL='';var KNOWN=false;var NEXT='" + next_url + "';"
        "function msg(t){document.getElementById('msg').textContent=t||'';}"
        "async function sendCode(){"
        "  var e=document.getElementById('email').value.trim();"
        "  if(!e){msg('Enter your email');return;}"
        "  EMAIL=e; var b=document.getElementById('send-btn'); b.disabled=true; b.textContent='Sending…'; msg('');"
        "  try{var r=await fetch('/pwa/auth/request-otp',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:e})});"
        "    var d=await r.json();"
        "    if(!r.ok||!d.ok){b.disabled=false;b.textContent='Send me a code →';msg(d.error||'Could not send code');return;}"
        "    KNOWN=!!d.known;"
        "    document.getElementById('step-email').style.display='none';"
        "    document.getElementById('step-code').style.display='block';"
        "    var ci=document.getElementById('code-intro');"
        "    if(KNOWN){document.getElementById('name-row').style.display='none';"
        "      ci.textContent='Welcome back'+(d.display_name?', '+d.display_name:'')+'! Enter the code we emailed to '+e+'.';}"
        "    else{document.getElementById('name-row').style.display='block';"
        "      ci.textContent='Almost there — enter the code we emailed to '+e+' and tell us your name.';}"
        "    if(d.dev_code){document.getElementById('code').value=d.dev_code;}"
        "  }catch(err){b.disabled=false;b.textContent='Send me a code →';msg('Network error');}"
        "}"
        "async function verifyCode(){"
        "  var c=document.getElementById('code').value.trim();"
        "  var n=document.getElementById('name').value.trim();"
        "  if(!c){msg('Enter the code');return;}"
        "  if(!KNOWN && !n){msg('Enter your name');return;}"
        "  var b=document.getElementById('verify-btn'); b.disabled=true; b.textContent='Verifying…'; msg('');"
        "  try{var r=await fetch('/pwa/auth/verify-otp',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:EMAIL,code:c,name:n})});"
        "    var d=await r.json();"
        "    if(!r.ok||!d.ok){b.disabled=false;b.textContent='Verify & continue →';msg(d.error||'Wrong code');return;}"
        "    window.location.href=NEXT;"
        "  }catch(err){b.disabled=false;b.textContent='Verify & continue →';msg('Network error');}"
        "}"
        "document.getElementById('resend').onclick=function(){document.getElementById('step-code').style.display='none';document.getElementById('step-email').style.display='block';document.getElementById('send-btn').disabled=false;document.getElementById('send-btn').textContent='Send me a code →';};"
        "</script>"
        "</div>"
    )
    return HTMLResponse(content=shell("Okeder — Sign in", body), headers=_NO_CACHE)

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

@router.get("/events", response_class=HTMLResponse)
async def events_home(request: Request, db: AsyncSession = Depends(get_db)):
    """Accueil connecté : liste des événements créés par le compte."""
    from app.routers._pwa_ui import shell
    from app.models.event import Event
    from app.models.group import Group
    from app.services.synthesis import compute_event_stats

    account = await _current_account(request, db)
    if not account:
        return _auth_gate_page("/events")

    ev_res = await db.execute(
        select(Event)
        .join(Group, Event.group_id == Group.id)
        .where(Group.initiator_id == account.id)
        .order_by(Event.created_at.desc())
    )
    events = ev_res.scalars().all()

    safe_name = (account.display_name or "").replace("'", "&#39;").replace('"', "&quot;")

    cards = ""
    for ev in events:
        stats = await compute_event_stats(str(ev.id), db)
        if not stats:
            continue
        if stats["has_proposal"]:
            status = "<span class='pill'>🎉 Plan ready</span>"
        elif stats["responded"] >= 1 or stats["declined"] >= 1:
            status = (f"<span class='tag'>⏳ {stats['responded']}/{stats['total']} responded</span>")
        else:
            status = "<span class='tag'>✍️ Awaiting responses</span>"
        when = ev.created_at.strftime("%d %b %Y") if ev.created_at else ""
        title = (stats["title"] or "Group outing").replace("<", "&lt;")
        cards += (
            f"<a class='role' href='/dashboard/{ev.id}' style='display:flex'>"
            f"<div><div style='font-weight:700;font-size:16px'>{title}</div>"
            f"<div class='meta'>{when} · 🙅 {stats['declined']} · ⏳ {stats['pending']}</div></div>"
            f"<div>{status}</div></a>"
        )
    if not cards:
        cards = ("<div class='card soft center' style='margin-top:18px;padding:34px 20px'>"
                 "<div style='font-size:40px'>🗓️</div>"
                 "<p class='lead' style='margin-top:8px'>No outings yet.</p></div>")

    body = (
        "<div class='wrap'>"
        "<nav style='display:flex;justify-content:space-between;align-items:center;margin-bottom:14px'>"
        "<div class='brand'><span class='dot'></span>Okeder</div>"
        f"<span class='muted' style='font-weight:600;font-size:14px'>👤 {safe_name} · "
        "<a href='#' onclick='logout()' style='color:var(--accent);text-decoration:none'>Sign out</a></span></nav>"
        "<span class='eyebrow'>Your outings</span>"
        "<h1 style='margin-top:10px;font-size:32px'>Welcome back.</h1>"
        "<a class='btn btn-primary' href='/create' style='margin-top:20px'>＋ Plan a new outing</a>"
        "<div class='divider'></div>"
        + cards +
        "<script>async function logout(){await fetch('/pwa/auth/logout',{method:'POST'});window.location.href='/events';}</script>"
        "</div>"
    )
    return HTMLResponse(content=shell("Okeder — Your outings", body), headers=_NO_CACHE)


@router.get("/create", response_class=HTMLResponse)
async def create_page(request: Request, db: AsyncSession = Depends(get_db)):
    """Étape 1 : titre + nombre d'invités. Réservé aux comptes connectés."""
    from app.routers._pwa_ui import shell

    account = await _current_account(request, db)
    if not account:
        return _auth_gate_page()

    head = (
        "<style>"
        "nav{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}"
        ".gchips{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}"
        ".gchips input{position:absolute;opacity:0;pointer-events:none}"
        ".gchips label{padding:12px 0;border-radius:14px;border:1.5px solid var(--line);"
        "background:#fff;font-weight:700;font-size:15px;cursor:pointer;text-align:center;transition:all .12s}"
        ".gchips input:checked+label{background:var(--ink);border-color:var(--ink);color:#fff}"
        "</style>"
    )
    guests = "".join(
        f"<input type='radio' name='guests' id='g{n}' value='{n}' {'checked' if n==3 else ''}>"
        f"<label for='g{n}'>{n}</label>"
        for n in range(1, 11)
    )
    safe_name = (account.display_name or "").replace("'", "&#39;").replace('"', "&quot;")
    body = (
        "<div class='wrap'>"
        "<nav><div class='brand'><span class='dot'></span>Okeder</div>"
        f"<span class='muted' style='font-weight:600;font-size:14px'>"
        "<a href='/events' style='color:var(--ink);text-decoration:none'>← My events</a> · "
        f"👤 {safe_name} · "
        "<a href='#' onclick='logout()' style='color:var(--accent);text-decoration:none'>Sign out</a></span></nav>"
        "<span class='eyebrow'>New outing</span>"
        "<h1 style='margin-top:12px'>Plan a group outing.</h1>"
        "<p class='lead'>You'll add your own preferences right after, then invite your people.</p>"
        "<form method='GET' action='/pwa/do-create' style='margin-top:26px'>"
        "<div class='section'><label class='fld'>What are you planning? <span class='opt'>(optional)</span></label>"
        "<input type='text' name='title' placeholder='Friday drinks, Team dinner…'></div>"
        "<div class='section'><label class='fld'>How many are you inviting? <span class='opt'>(not counting you)</span></label>"
        "<div class='gchips'>" + guests + "</div></div>"
        "<button class='btn btn-primary' type='submit'>Continue&nbsp;→&nbsp;add my preferences</button>"
        "</form>"
        "<script>async function logout(){await fetch('/pwa/auth/logout',{method:'POST'});window.location.href='/create';}</script>"
        "</div>"
    )
    return HTMLResponse(content=shell("Okeder — Plan an outing", body, head_extra=head), headers=_NO_CACHE)


@router.get("/pwa/do-create")
async def pwa_do_create(
    request: Request,
    title: str = "Group Outing",
    guests: int = 3,
    db: AsyncSession = Depends(get_db),
):
    """
    Crée l'event avec l'organisateur = compte connecté (pas de doublon de membre).
    Redirige vers le Mini App pour que l'organisateur soumette ses préférences,
    puis vers /dashboard/{event_id} (son tableau de bord de suivi).
    """
    from datetime import datetime, timedelta, timezone
    from fastapi.responses import RedirectResponse
    from app.models.event import Event
    from app.models.group import Group, GroupMembership

    account = await _current_account(request, db)
    if not account:
        return RedirectResponse(url="/create")

    # Le groupe est initié par le compte connecté (réutilisé, pas recréé)
    group = Group(name=title or "Group Outing", initiator_id=account.id)
    db.add(group)
    await db.flush()
    db.add(GroupMembership(group_id=group.id, member_id=account.id, role="initiator"))

    # expected = organisateur (1) + invités
    expected = max(2, int(guests) + 1)

    deadline = datetime.now(timezone.utc) + timedelta(hours=48)
    event = Event(
        group_id=group.id,
        title=title or "Group Outing",
        wizard_mode=False,
        constraint_deadline=deadline,
        created_by=account.id,
        expected_participants=expected,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    public_url = os.environ.get("PUBLIC_URL", "http://localhost:8000")

    # Mini App pré-identifié (mid + name) → pas de redemande du nom ; après soumission → dashboard
    next_url = f"{public_url}/dashboard/{event.id}"
    import urllib.parse as _ul
    q = _ul.urlencode({"next": next_url, "mid": str(account.id), "name": account.display_name or ""})
    mini_app_url = f"{public_url}/mini-app/{event.id}?{q}"

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

    from app.routers._pwa_ui import shell
    body = (
        "<div class='wrap'>"
        "<div class='brand' style='margin-bottom:18px'><span class='dot'></span>Okeder</div>"
        "<span class='pill'>✅ Preferences saved</span>"
        "<h1 style='margin-top:14px'>Now invite<br>your people.</h1>"
        "<p class='lead'>Share this link — they answer on any device, no app needed.</p>"

        "<div class='card' style='margin-top:22px;display:flex;align-items:center;gap:16px'>"
        "<div style='flex:1'><div class='muted' style='font-size:13px;font-weight:600'>Responses received</div>"
        f"<div class='progress' style='margin-top:10px'><i style='width:{progress_pct}%'></i></div></div>"
        f"<div style='font-size:24px;font-weight:800'>{submitted}<span class='muted' style='font-size:16px'>/{expected}</span></div>"
        "</div>"

        "<div style='margin-top:18px'>"
        "<button class='btn btn-primary' id='share-btn' onclick='doShare()'>🔗 Share with your contacts</button>"
        "<div id='fallbacks' style='display:none;margin-top:10px' class='stack'>"
        f"<a class='btn btn-ghost' href='{wa_url}' target='_blank'>📱 WhatsApp</a>"
        f"<a class='btn btn-ghost' href='{tg_url}' target='_blank'>✈️ Telegram</a>"
        "<button class='btn btn-ghost' id='copy-btn' onclick='copyLink()'>📋 Copy link</button>"
        "</div></div>"
        "<div class='linkbox' style='margin-top:12px'>" + join_url + "</div>"

        f"<a class='btn btn-dark' href='{result_url}' style='margin-top:18px'>See the proposal when ready →</a>"
        "<div class='divider'></div>"
        "<p class='muted center' style='font-size:13px'>This page updates automatically every 15s</p>"

        "<script>"
        "const JOIN_URL='" + join_url + "';"
        "function doShare(){if(navigator.share){navigator.share({title:'Okeder',text:'Respond in 30s so we can plan our outing!',url:JOIN_URL}).catch(function(){});}"
        "else{document.getElementById('fallbacks').style.display='block';document.getElementById('share-btn').style.display='none';}}"
        "function copyLink(){navigator.clipboard.writeText(JOIN_URL);var b=document.getElementById('copy-btn');"
        "b.innerHTML='✅ Copied!';setTimeout(function(){b.innerHTML='📋 Copy link';},1800);}"
        "</script>"
        "</div>"
    )
    return HTMLResponse(
        content=shell("Okeder — Share", body, head_extra="<meta http-equiv='refresh' content='15'>")
    )


def _booking_card(stats: dict) -> str:
    """Carte réservation (L6b) sur le dashboard."""
    party = stats.get("going") or stats.get("responded") or 0
    venue = (stats.get("venue_name") or "the venue").replace("<", "&lt;")
    when = stats.get("when") or "TBD"
    bk = stats.get("booking")
    eid = stats["event_id"]

    head = ("<div class='card' style='margin-top:16px'><div class='label'>Booking</div>"
            f"<div style='font-weight:700;font-size:16px'>🍽️ {venue}</div>"
            f"<div class='muted' style='font-size:13px;margin-top:3px'>📅 {when} · 👥 party of {party}</div>")

    if not bk or bk.get("status") in (None, "pending"):
        return (head +
            "<p class='muted' style='font-size:13.5px;margin-top:12px'>Generate a pre-filled reservation "
            "request you can send to the venue (or open its booking page).</p>"
            "<button class='btn btn-primary' style='margin-top:12px' onclick='doBook()'>📩 Prepare the booking</button>"
            "<script>async function doBook(){var b=event.target;b.disabled=true;b.textContent='Preparing…';"
            f"await fetch('/pwa/dashboard/{eid}/book',{{method:'POST'}});setTimeout(()=>location.reload(),800);}}</script>"
            "</div>")

    if bk.get("status") == "success":
        return (head +
            "<div class='pill' style='margin-top:12px'>✅ Booking confirmed</div>"
            f"<a class='btn btn-ghost sm' style='margin-top:12px' href='{bk.get('open_url','#')}' target='_blank'>Open venue page</a>"
            "</div>")

    # status in_progress (requested) → afficher les assets
    msg = (bk.get("message") or "").replace("<", "&lt;").replace("'", "&#39;")
    open_url = bk.get("open_url") or "#"
    tf = bk.get("thefork_url") or ""
    tf_btn = f"<a class='btn btn-ghost sm' style='margin-top:8px' href='{tf}' target='_blank'>🍴 Search on TheFork</a>" if tf else ""
    return (head +
        "<p class='muted' style='font-size:13px;margin-top:12px'>Send this to the venue (WhatsApp, call, or its page):</p>"
        f"<div class='linkbox' id='resamsg' style='margin-top:8px;white-space:pre-wrap'>{msg}</div>"
        "<button class='btn btn-ghost sm' style='margin-top:8px' onclick='copyMsg()'>📋 Copy message</button>"
        f"<a class='btn btn-ghost sm' style='margin-top:8px' href='{open_url}' target='_blank'>📍 Open booking page</a>"
        + tf_btn +
        "<button class='btn btn-primary' style='margin-top:12px' onclick='confirmBook()'>✅ Mark as confirmed</button>"
        "<script>"
        "function copyMsg(){navigator.clipboard.writeText(document.getElementById('resamsg').textContent);event.target.textContent='✅ Copied';}"
        f"async function confirmBook(){{var b=event.target;b.disabled=true;b.textContent='Saving…';await fetch('/pwa/dashboard/{eid}/book/confirm',{{method:'POST'}});setTimeout(()=>location.reload(),800);}}"
        "</script></div>")


@router.post("/pwa/deposit")
async def pwa_deposit(request: Request, db: AsyncSession = Depends(get_db)):
    """L6a — crée une session Stripe Checkout pour le dépôt 'Lock In' (web)."""
    from app.models.member import Member
    from app.services.stripe_service import create_deposit_checkout, stripe_enabled

    if not stripe_enabled():
        return JSONResponse({"ok": False, "error": "stripe_disabled"}, status_code=503)

    body = await request.json()
    event_id = body.get("event_id", "")
    member_id_in = (body.get("member_id") or "").strip() or None

    proposal = await _published_proposal(event_id, db)
    if not proposal:
        return JSONResponse({"ok": False, "error": "no proposal"}, status_code=404)

    # Résoudre le membre (session connectée > member_id fourni > invité)
    member = await _current_account(request, db)
    if not member and member_id_in:
        try:
            r = await db.execute(select(Member).where(Member.id == uuid.UUID(member_id_in)))
            member = r.scalar_one_or_none()
        except ValueError:
            member = None
    if not member:
        member = Member(display_name="Web guest")
        db.add(member)
        await db.flush()
        await db.commit()

    base = os.environ.get("PUBLIC_URL", "http://localhost:8000").rstrip("/")
    success_url = f"{base}/pay/success?session_id={{CHECKOUT_SESSION_ID}}&event_id={event_id}"
    cancel_url = f"{base}/result/{event_id}"
    try:
        url = await create_deposit_checkout(proposal, member, db, success_url, cancel_url)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    return JSONResponse({"ok": True, "url": url, "member_id": str(member.id)})


@router.get("/pay/success", response_class=HTMLResponse)
async def pay_success(session_id: str = "", event_id: str = "", db: AsyncSession = Depends(get_db)):
    """Retour de Stripe Checkout : confirme le paiement et renvoie vers /result."""
    from app.routers._pwa_ui import shell
    from app.services.stripe_service import confirm_checkout_session

    info = await confirm_checkout_session(session_id, db) if session_id else {"paid": False}
    ev = info.get("event_id") or event_id
    result_url = f"/result/{ev}" if ev else "/"
    mid = info.get("member_id") or ""

    if info.get("paid"):
        body = (
            "<div class='wrap center' style='min-height:100vh;display:flex;flex-direction:column;justify-content:center'>"
            "<div style='font-size:54px'>🔒</div><h1 style='margin-top:14px'>You're locked in!</h1>"
            "<p class='lead'>Your deposit is confirmed. See you there 🎉</p>"
            f"<a class='btn btn-primary' href='{result_url}' style='margin-top:24px'>Back to the plan →</a>"
            "<script>try{if('" + mid + "'&&'" + (ev or "") + "')localStorage.setItem('okeder_member_'+'" + (ev or "") + "','" + mid + "');}catch(e){}"
            f"setTimeout(function(){{window.location.href='{result_url}';}},2500);</script>"
            "</div>"
        )
    else:
        body = (
            "<div class='wrap center' style='min-height:100vh;display:flex;flex-direction:column;justify-content:center'>"
            "<div style='font-size:54px'>⚠️</div><h1 style='margin-top:14px'>Payment not completed</h1>"
            "<p class='lead'>No worries — you can try again.</p>"
            f"<a class='btn btn-ghost' href='{result_url}' style='margin-top:24px'>Back to the plan</a></div>"
        )
    return HTMLResponse(content=shell("Okeder — Payment", body), headers=_NO_CACHE)


@router.get("/dashboard/{event_id}", response_class=HTMLResponse)
async def dashboard_page(event_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Tableau de bord de l'organisateur — réservé au compte initiateur."""
    from app.routers._pwa_ui import shell
    from app.services.synthesis import compute_event_stats

    account = await _current_account(request, db)
    if not account:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/create")

    stats = await compute_event_stats(event_id, db)
    if not stats:
        return HTMLResponse(shell("Okeder", "<div class='wrap'><p>Event not found.</p></div>"), status_code=404)

    if stats.get("initiator_id") != account.id:
        return HTMLResponse(
            shell("Okeder", "<div class='wrap center' style='padding-top:80px'>"
                  "<h2>Not your event</h2><p class='lead'>Only the organiser can see this dashboard.</p>"
                  "<a class='btn btn-ghost' href='/create' style='margin-top:20px'>← Plan your own</a></div>"),
            status_code=403,
        )

    base = os.environ.get("PUBLIC_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    join_url   = f"{base}/join/{event_id}"
    result_url = f"{base}/result/{event_id}"

    pct = int(stats["responded"] / stats["total"] * 100) if stats["total"] else 0

    # Liste des participants
    badge = {
        "responded": "<span style='color:var(--ok);font-weight:700'>✅ Responded</span>",
        "declined":  "<span style='color:var(--muted);font-weight:700'>🙅 Can't make it</span>",
        "pending":   "<span style='color:var(--warn);font-weight:700'>⏳ Waiting</span>",
    }
    commit_lbl = {"soft": "👍 Interested", "confirmed": "✅ I'm In", "hard": "🔒 Locked In"}
    rows = ""
    for p in stats["participants"]:
        safe = (p["name"] or "Guest").replace("<", "&lt;")
        extra = ""
        if p.get("commitment"):
            extra = f"<div class='muted' style='font-size:12.5px;margin-top:2px'>{commit_lbl.get(p['commitment'], '')}</div>"
        rows += (
            "<div style='display:flex;justify-content:space-between;align-items:center;"
            "padding:13px 0;border-bottom:1px solid var(--line)'>"
            f"<div><div style='font-weight:700'>{safe}</div>{extra}</div>"
            f"<div style='font-size:13px'>{badge.get(p['status'], '')}</div></div>"
        )
    if not rows:
        rows = "<p class='muted' style='padding:14px 0'>No participants yet — share the link below.</p>"

    # Bloc engagements (si proposition publiée)
    commit_block = ""
    if stats["has_proposal"]:
        c = stats["commitments"]
        commit_block = (
            "<div class='card' style='margin-top:16px'>"
            "<div class='label'>Who's coming</div>"
            f"<div class='metric'><span class='dot-ok'>👍</span> Interested · <b>{c['soft']}</b></div>"
            f"<div class='metric'><span class='dot-ok'>✅</span> I'm In · <b>{c['confirmed']}</b></div>"
            f"<div class='metric'><span class='dot-ok'>🔒</span> Locked In · <b>{c['hard']}</b></div>"
            f"<a class='btn btn-dark' href='{result_url}' style='margin-top:14px'>View the plan →</a>"
            "</div>"
        )
        commit_block += _booking_card(stats)
    else:
        commit_block = (
            "<div class='card soft' style='margin-top:16px'>"
            "<p class='muted' style='font-size:14px'>The proposal is generated automatically once enough "
            "people respond. You can also generate it now with the current responses.</p>"
            "<button class='btn btn-ghost' style='margin-top:12px' onclick='genNow()'>⚡ Generate proposal now</button>"
            "</div>"
        )

    body = (
        "<div class='wrap'>"
        "<nav style='display:flex;justify-content:space-between;align-items:center;margin-bottom:14px'>"
        "<div class='brand'><span class='dot'></span>Okeder</div>"
        "<span class='muted' style='font-weight:600;font-size:14px'>"
        "<a href='/events' style='color:var(--ink);text-decoration:none'>← My events</a> · "
        "<a href='/create' style='color:var(--accent);text-decoration:none'>+ New</a></span></nav>"
        "<span class='eyebrow'>Organiser dashboard</span>"
        f"<h1 style='margin-top:10px;font-size:30px'>{(stats['title'] or 'Your outing')}</h1>"

        "<div class='card' style='margin-top:20px;display:flex;align-items:center;gap:16px'>"
        "<div style='flex:1'><div class='muted' style='font-size:13px;font-weight:600'>Responses</div>"
        f"<div class='progress' style='margin-top:10px'><i style='width:{pct}%'></i></div>"
        f"<div class='muted' style='font-size:12.5px;margin-top:8px'>🙅 {stats['declined']} declined · ⏳ {stats['pending']} waiting</div></div>"
        f"<div style='font-size:26px;font-weight:800'>{stats['responded']}<span class='muted' style='font-size:16px'>/{stats['total']}</span></div>"
        "</div>"

        + commit_block +

        "<div class='card' style='margin-top:16px'>"
        "<div class='label'>Participants</div>"
        + rows +
        "</div>"

        "<div class='divider'></div>"
        "<div class='label'>Invite more people</div>"
        "<div class='linkbox' style='margin-top:6px'>" + join_url + "</div>"
        "<div class='row' style='margin-top:10px'>"
        "<button class='btn btn-ghost sm' onclick='copyLink()' style='width:100%'>📋 Copy link</button>"
        "<button class='btn btn-primary sm' onclick='shareLink()' style='width:100%'>🔗 Share</button>"
        "</div>"

        "<p class='muted center' style='font-size:12.5px;margin-top:20px'>This page refreshes automatically</p>"

        "<script>"
        "const JOIN_URL='" + join_url + "';"
        "function copyLink(){navigator.clipboard.writeText(JOIN_URL);event.target.textContent='✅ Copied';}"
        "function shareLink(){if(navigator.share){navigator.share({title:'Okeder',text:'Join our outing — respond in 30s',url:JOIN_URL});}else{copyLink();}}"
        "async function genNow(){var b=event.target;b.disabled=true;b.textContent='Generating…';"
        "await fetch('/pwa/dashboard/" + event_id + "/generate',{method:'POST'});setTimeout(()=>location.reload(),2500);}"
        "</script>"
        "</div>"
    )
    return HTMLResponse(content=shell("Okeder — Dashboard", body, head_extra="<meta http-equiv='refresh' content='12'>"), headers=_NO_CACHE)


@router.post("/pwa/dashboard/{event_id}/generate")
async def dashboard_generate(event_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Force la génération de la proposition (organisateur uniquement)."""
    from app.services.synthesis import compute_event_stats

    account = await _current_account(request, db)
    if not account:
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)

    stats = await compute_event_stats(event_id, db)
    if not stats or stats.get("initiator_id") != account.id:
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)

    try:
        from app.workers.jobs.run_decision_engine import enqueue_run_decision_engine
        await enqueue_run_decision_engine(event_id)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    return JSONResponse({"ok": True})


async def _published_proposal(event_id: str, db):
    from app.models.proposal import Proposal
    res = await db.execute(
        select(Proposal)
        .where(Proposal.event_id == uuid.UUID(event_id), Proposal.published == True)  # noqa: E712
        .order_by(Proposal.version.desc()).limit(1)
    )
    return res.scalar_one_or_none()


@router.post("/pwa/dashboard/{event_id}/book")
async def dashboard_book(event_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """L6b — prépare la demande de réservation restaurant (organisateur)."""
    from app.services.booking import request_restaurant_booking
    from app.services.synthesis import compute_event_stats

    account = await _current_account(request, db)
    if not account:
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)
    stats = await compute_event_stats(event_id, db)
    if not stats or stats.get("initiator_id") != account.id:
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    proposal = await _published_proposal(event_id, db)
    if not proposal:
        return JSONResponse({"ok": False, "error": "no proposal"}, status_code=404)

    party = stats.get("going") or stats.get("responded") or 1
    be = await request_restaurant_booking(proposal, account.display_name, party, db)
    return JSONResponse({"ok": True, "status": be.status, "assets": be.confirmation_data})


@router.post("/pwa/dashboard/{event_id}/book/confirm")
async def dashboard_book_confirm(event_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Marque la réservation confirmée et notifie le groupe."""
    from app.services.booking import confirm_booking
    from app.services.synthesis import compute_event_stats, update_initiator_synthesis

    account = await _current_account(request, db)
    if not account:
        return JSONResponse({"ok": False, "error": "auth"}, status_code=401)
    stats = await compute_event_stats(event_id, db)
    if not stats or stats.get("initiator_id") != account.id:
        return JSONResponse({"ok": False, "error": "forbidden"}, status_code=403)
    proposal = await _published_proposal(event_id, db)
    if not proposal:
        return JSONResponse({"ok": False, "error": "no proposal"}, status_code=404)

    await confirm_booking(proposal.id, db)

    # Notifier le groupe Telegram si présent + maj synthèse initiateur
    try:
        from app.models.event import Event
        from app.models.group import Group
        from app.services.notification_service import send_telegram_message
        ev = (await db.execute(select(Event).where(Event.id == uuid.UUID(event_id)))).scalar_one_or_none()
        if ev:
            grp = (await db.execute(select(Group).where(Group.id == ev.group_id))).scalar_one_or_none()
            if grp and grp.telegram_chat_id:
                when = proposal.date_time.strftime("%d/%m at %H:%M") if proposal.date_time else "soon"
                await send_telegram_message(
                    grp.telegram_chat_id,
                    f"✅ <b>It's booked!</b>\n{proposal.venue_name or 'The venue'} — {when}.\nSee you there! 🎉",
                )
        await update_initiator_synthesis(event_id, db)
    except Exception:
        pass

    return JSONResponse({"ok": True})


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

    from app.routers._pwa_ui import shell
    body = (
        "<div class='wrap center' style='min-height:100vh;display:flex;flex-direction:column;justify-content:center'>"
        "<div style='font-size:54px;line-height:1'>🎉</div>"
        "<h1 style='margin-top:16px'>You're invited!</h1>"
        f"<p class='lead' style='margin-top:12px'>Someone from <b>{group_name}</b> is planning a group "
        "outing and wants to know what works for you.</p>"
        "<p class='muted' style='margin-top:10px;font-size:14px'>30 seconds · no account needed</p>"
        f"<a class='btn btn-primary' href='{form_url}' style='margin-top:28px'>Add my preferences&nbsp;→</a>"
        "<p class='muted' style='margin-top:20px;font-size:12px'>Powered by Okeder</p>"
        "</div>"
    )
    return HTMLResponse(content=shell("Okeder — You're invited", body))


# ─── Commitment depuis le web (page /result) ─────────────────────────────────

@router.post("/pwa/commit")
async def pwa_commit(request: Request, db: AsyncSession = Depends(get_db)):
    """Enregistre un engagement depuis /result (sans Telegram/Clerk).
    Le navigateur fournit le member_id stocké lors de la soumission du formulaire ;
    à défaut, un membre invité anonyme est créé."""
    from app.models.commitment import Commitment, CommitmentLevel
    from app.models.member import Member
    from app.models.proposal import Proposal

    body = await request.json()
    event_id_str = body.get("event_id", "")
    level = body.get("level", CommitmentLevel.SOFT)
    member_id_str = body.get("member_id") or ""

    if level not in (CommitmentLevel.SOFT, CommitmentLevel.CONFIRMED, CommitmentLevel.HARD):
        return JSONResponse({"ok": False, "error": "invalid level"}, status_code=400)

    try:
        event_uuid = uuid.UUID(event_id_str)
    except ValueError:
        return JSONResponse({"ok": False, "error": "invalid event"}, status_code=400)

    # Proposal publiée la plus récente
    prop_result = await db.execute(
        select(Proposal)
        .where(Proposal.event_id == event_uuid, Proposal.published == True)  # noqa: E712
        .order_by(Proposal.version.desc()).limit(1)
    )
    proposal = prop_result.scalar_one_or_none()
    if not proposal:
        return JSONResponse({"ok": False, "error": "no published proposal"}, status_code=404)

    # Résoudre le membre : id fourni, sinon invité anonyme
    member = None
    if member_id_str:
        try:
            m_res = await db.execute(select(Member).where(Member.id == uuid.UUID(member_id_str)))
            member = m_res.scalar_one_or_none()
        except ValueError:
            member = None
    if not member:
        member = Member(display_name="Web guest")
        db.add(member)
        await db.flush()

    # Upsert commitment (contrainte unique proposal_id+member_id)
    c_res = await db.execute(
        select(Commitment).where(
            Commitment.proposal_id == proposal.id,
            Commitment.member_id == member.id,
        )
    )
    commitment = c_res.scalar_one_or_none()
    if commitment:
        commitment.level = level
    else:
        db.add(Commitment(proposal_id=proposal.id, member_id=member.id, level=level))
    await db.commit()

    # Compter les engagements
    all_c = await db.execute(select(Commitment).where(Commitment.proposal_id == proposal.id))
    counts = {"soft": 0, "confirmed": 0, "hard": 0}
    for c in all_c.scalars().all():
        if c.level in counts:
            counts[c.level] += 1

    # Diffuser la mise à jour temps réel (best-effort)
    try:
        from app.routers.ws import broadcast_commitment_update
        await broadcast_commitment_update(str(proposal.id))
    except Exception:
        pass

    # Synthèse temps réel à l'initiateur Telegram (si applicable)
    try:
        from app.services.synthesis import update_initiator_synthesis
        await update_initiator_synthesis(str(proposal.event_id), db)
    except Exception:
        pass

    return JSONResponse({"ok": True, "member_id": str(member.id), "counts": counts})


# ─── Concierge : réservation côté membre (page /result) ──────────────────────

async def _organiser_and_party(event_id: str, db) -> tuple[str, int]:
    """Nom de l'organisateur + taille du groupe (going > responded > 2)."""
    from app.models.event import Event
    from app.models.member import Member
    from app.services.synthesis import compute_event_stats

    organiser = "Okeder"
    ev = (await db.execute(select(Event).where(Event.id == uuid.UUID(event_id)))).scalar_one_or_none()
    if ev and ev.created_by:
        cm = (await db.execute(select(Member).where(Member.id == ev.created_by))).scalar_one_or_none()
        if cm and cm.display_name:
            organiser = cm.display_name
    stats = await compute_event_stats(event_id, db) or {}
    party = stats.get("going") or stats.get("responded") or 2
    return organiser, int(party)


@router.post("/pwa/result/{event_id}/book")
async def result_book(event_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Prépare la cascade de réservation. Ouvert à tout membre (confirmation distribuée)."""
    from app.services.booking import request_restaurant_booking

    proposal = await _published_proposal(event_id, db)
    if not proposal:
        return JSONResponse({"ok": False, "error": "no proposal"}, status_code=404)
    organiser, party = await _organiser_and_party(event_id, db)
    be = await request_restaurant_booking(proposal, organiser, party, db)
    return JSONResponse({"ok": True, "assets": be.confirmation_data})


@router.post("/pwa/result/{event_id}/book/sent")
async def result_book_sent(event_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Un membre a déclenché l'envoi via un canal → avance la machine à états."""
    from app.services.booking import mark_outreach_sent

    body = await request.json()
    channel = (body.get("channel") or "")[:40]
    proposal = await _published_proposal(event_id, db)
    if not proposal:
        return JSONResponse({"ok": False, "error": "no proposal"}, status_code=404)
    await mark_outreach_sent(proposal.id, channel, db)
    return JSONResponse({"ok": True})


@router.post("/pwa/result/{event_id}/book/confirm")
async def result_book_confirm(event_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Marque la réservation confirmée + notifie le groupe. Ouvert à tout membre."""
    from app.services.booking import confirm_booking

    proposal = await _published_proposal(event_id, db)
    if not proposal:
        return JSONResponse({"ok": False, "error": "no proposal"}, status_code=404)
    await confirm_booking(proposal.id, db)

    try:
        from app.models.event import Event
        from app.models.group import Group
        from app.services.notification_service import send_telegram_message
        from app.services.synthesis import update_initiator_synthesis
        ev = (await db.execute(select(Event).where(Event.id == uuid.UUID(event_id)))).scalar_one_or_none()
        if ev:
            grp = (await db.execute(select(Group).where(Group.id == ev.group_id))).scalar_one_or_none()
            if grp and grp.telegram_chat_id:
                when = proposal.date_time.strftime("%d/%m at %H:%M") if proposal.date_time else "soon"
                await send_telegram_message(
                    grp.telegram_chat_id,
                    f"✅ <b>It's booked!</b>\n{proposal.venue_name or 'The venue'} — {when}.\nSee you there! 🎉",
                )
        await update_initiator_synthesis(event_id, db)
    except Exception:
        pass

    return JSONResponse({"ok": True})


@router.post("/pwa/result/{event_id}/autobook")
async def result_autobook(event_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Déclenche l'agent navigateur (zéro-clic). Disclosé, auto-submit sauf paiement.
    Ouvert à tout membre. Sert aussi au test live (sans passer par l'acompte)."""
    from datetime import datetime, timezone
    from app.models.event import Event
    from app.models.member import Member
    from app.models.booking_execution import BookingExecution, BookingMethod, BookingStatus
    from app.services.ai_booking_agent import attempt_booking
    from app.services.booking import build_cascade, BookingState

    proposal = await _published_proposal(event_id, db)
    if not proposal:
        return JSONResponse({"ok": False, "error": "no proposal"}, status_code=404)

    organiser_name, party = await _organiser_and_party(event_id, db)
    organiser = {"name": organiser_name, "email": "", "phone": ""}
    ev = (await db.execute(select(Event).where(Event.id == uuid.UUID(event_id)))).scalar_one_or_none()
    if ev and ev.created_by:
        cm = (await db.execute(select(Member).where(Member.id == ev.created_by))).scalar_one_or_none()
        if cm:
            organiser = {"name": cm.display_name or organiser_name, "email": cm.email or "", "phone": cm.phone or ""}

    assets = await build_cascade(proposal, organiser["name"], party)
    agent = await attempt_booking(proposal, assets, organiser)

    if agent.get("attempted") and agent.get("success"):
        now = datetime.now(timezone.utc)
        db.add(BookingExecution(
            proposal_id=proposal.id,
            method=BookingMethod.AI_BROWSER_AGENT,
            status=BookingStatus.SUCCESS,
            external_url=assets.get("open_url"),
            confirmation_data={**assets, "state": BookingState.CONFIRMED,
                               "agent": {k: v for k, v in agent.items() if k != "screenshot_b64"}},
            agent_disclosed=True,
            attempted_at=now,
            completed_at=now,
        ))
        await db.commit()

    return JSONResponse({"ok": True, "agent": agent})


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

    from app.routers._pwa_ui import shell

    if not proposal:
        wbody = (
            "<div class='wrap center' style='min-height:100vh;display:flex;flex-direction:column;justify-content:center'>"
            "<style>@keyframes spin{to{transform:rotate(360deg)}}</style>"
            "<div style='font-size:46px;display:inline-block;animation:spin 2.4s linear infinite'>⏳</div>"
            "<h1 style='margin-top:18px'>Collecting preferences…</h1>"
            "<p class='lead'>The proposal appears here once everyone has responded. "
            "This page refreshes automatically.</p>"
            "</div>"
        )
        return HTMLResponse(
            content=shell("Okeder — Waiting", wbody, head_extra="<meta http-equiv='refresh' content='30'>")
        )

    # ── Formatter la proposal ────────────────────────────────────────────────
    lj = proposal.legitimacy_json or {}

    venue_block = ""
    if proposal.venue_name:
        venue_block += f"<div style='font-size:17px;font-weight:700'>📍 {proposal.venue_name}</div>"
    if proposal.venue_address:
        venue_block += f"<div class='muted' style='font-size:13.5px;margin-top:4px'>{proposal.venue_address}</div>"
    if proposal.external_url:
        venue_block += (
            f"<a class='btn btn-ghost sm' href='{proposal.external_url}' target='_blank' "
            "style='margin-top:14px'>📌 Open in Google Maps</a>"
        )

    date_str = ""
    if proposal.date_time:
        date_str = proposal.date_time.strftime("%A %d %B at %H:%M")
    elif lj.get("datetime_hint") and lj["datetime_hint"] != "TBD":
        date_str = lj["datetime_hint"]

    vibe = lj.get("vibe_proposed") or lj.get("vibe") or ""
    activity = lj.get("activity") or ""
    public_url = os.environ.get("PUBLIC_URL", "http://localhost:8000")
    vapid_key = settings.vapid_public_key

    title_line = vibe.capitalize() if vibe else "Your group outing"
    if activity and activity != vibe:
        title_line += " · " + activity.capitalize()

    tags = ""
    if date_str:
        tags += f"<span class='tag'>📅 {date_str}</span>"
    if proposal.price_per_person:
        tags += f"<span class='tag'>💶 ~€{int(proposal.price_per_person / 100)} pp</span>"
    tags_block = f"<div style='margin-top:14px;display:flex;flex-wrap:wrap;gap:8px'>{tags}</div>" if tags else ""

    venue_card = f"<div class='card' style='margin-top:16px'>{venue_block}</div>" if venue_block else ""

    metrics = ""
    if proposal.pct_budget_satisfied is not None:
        metrics += (
            "<div class='metric'><span class='dot-ok'>✅</span> Budget · "
            f"{int(float(proposal.pct_budget_satisfied or 0) * 100)}% satisfied</div>"
        )
    if proposal.pct_time_satisfied is not None:
        _ok = float(proposal.pct_time_satisfied or 0) >= 0.7
        metrics += (
            f"<div class='metric'><span class='{'dot-ok' if _ok else 'dot-warn'}'>{'✅' if _ok else '⚠️'}</span> "
            f"Timing · {int(float(proposal.pct_time_satisfied or 0) * 100)}% satisfied</div>"
        )
    if vibe:
        _vibe_lbl = vibe.capitalize() + ((" + " + activity.capitalize()) if activity != vibe else "")
        metrics += (
            f"<div class='metric'><span class='dot-ok'>✅</span> Vibe ({_vibe_lbl}) · "
            f"{int(float(proposal.pct_prefs_satisfied or 0) * 100)}% match</div>"
        )

    head = (
        "<style>"
        ".commit-row{display:flex;gap:8px;margin-top:8px}"
        ".commit-row .btn{flex:1;padding:15px 6px;font-size:14px;border-radius:14px;box-shadow:none}"
        ".pushbar{display:flex;align-items:center;gap:12px}"
        ".pushbar p{flex:1;font-size:13.5px}"
        "</style>"
    )

    # JS Concierge (chaîne normale → accolades littérales, pas d'échappement f-string)
    booking_js = """
    async function loadBooking() {
      const memberId = localStorage.getItem('okeder_member_' + EVENT_ID) || '';
      const btn = document.getElementById('book-prep');
      const box = document.getElementById('booking-actions');
      if (btn) btn.textContent = '…';
      try {
        const r = await fetch(BACKEND + '/pwa/result/' + EVENT_ID + '/book', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ member_id: memberId }),
        });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const d = await r.json();
        if (!d || !d.assets) throw new Error('no assets in response');
        renderBooking(d.assets);
      } catch (e) {
        // Erreur visible inline (diagnostic) plutôt qu'une alerte vague
        if (box) {
          box.style.display = 'block';
          box.innerHTML = '<div style="color:#b91c1c;font-size:13px;white-space:pre-wrap">⚠️ ' +
            (e && e.message ? e.message : e) + '</div>';
        }
        if (btn) btn.textContent = '📅 Prepare reservation';
      }
    }
    function _bkBtn(label, href, channel, cls) {
      return '<a class="btn ' + cls + '" target="_blank" rel="noopener" href="' + href +
             '" onclick="markSent(\\'' + channel + '\\')" style="display:block;margin-top:8px">' + label + '</a>';
    }
    function renderBooking(a) {
      const c = a.channels || {};
      const rec = a.recommended || '';
      const items = [];
      if (c.reserve) {
        const lbl = '🍽️ Reserve at ' + (a.venue_name || 'the venue') +
                    (a.party_size ? ' · ' + a.party_size + ' ppl' : '');
        items.push([lbl, c.reserve, 'reserve']);
      }
      if (c.thefork)  items.push(['🍴 Book on TheFork', c.thefork, 'thefork']);
      if (c.call)     items.push(['📞 Call the venue', c.call, 'call']);
      if (c.whatsapp) items.push(['💬 WhatsApp the venue', c.whatsapp, 'whatsapp']);
      if (c.email)    items.push(['✉️ Email the venue', c.email, 'email']);
      items.push(['📍 Open venue page', c.open_url || '#', 'open']);
      let html = '';
      items.forEach(function (it) {
        const isRec = it[2] === rec;
        html += _bkBtn(it[0] + (isRec ? '  ⭐' : ''), it[1], it[2], isRec ? 'btn-primary' : 'btn-ghost');
      });
      if (a.message) {
        html += '<div class="label" style="margin-top:14px">Message ready to send</div>';
        html += '<textarea id="bk-msg" style="width:100%;min-height:92px;border-radius:12px;padding:10px;border:1px solid var(--line,#e5e5e5);font:inherit;box-sizing:border-box">' + a.message + '</textarea>';
        html += '<button class="btn btn-ghost sm" onclick="copyMsg()" style="margin-top:8px">📋 Copy message</button>';
      }
      html += '<button class="btn btn-primary" onclick="autoBook(this)" style="margin-top:12px;width:100%">🤖 Let Okeder book it (beta)</button>';
      html += '<div id="autobook-result" style="margin-top:10px"></div>';
      html += '<button class="btn btn-dark" onclick="markBooked()" style="margin-top:10px;width:100%">✅ Mark as booked</button>';
      const box = document.getElementById('booking-actions');
      box.innerHTML = html; box.style.display = 'block';
      const btn = document.getElementById('book-prep'); if (btn) btn.style.display = 'none';
    }
    function copyMsg() {
      const t = document.getElementById('bk-msg'); if (!t) return;
      t.select();
      if (navigator.clipboard) navigator.clipboard.writeText(t.value).catch(function(){});
      else { try { document.execCommand('copy'); } catch (e) {} }
    }
    function markSent(channel) {
      const memberId = localStorage.getItem('okeder_member_' + EVENT_ID) || '';
      fetch(BACKEND + '/pwa/result/' + EVENT_ID + '/book/sent', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ member_id: memberId, channel: channel }),
      }).catch(function(){});
    }
    async function autoBook(btn) {
      const out = document.getElementById('autobook-result');
      btn.disabled = true; btn.textContent = '🤖 Booking…';
      if (out) out.innerHTML = '<div class="muted" style="font-size:13px">Okeder is filling the reservation form…</div>';
      try {
        const r = await fetch(BACKEND + '/pwa/result/' + EVENT_ID + '/autobook', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
        });
        const d = await r.json();
        const a = d.agent || {};
        let html;
        if (a.success) {
          html = '<div style="color:#16a34a;font-weight:700">✅ Booked automatically!' +
                 (a.confirmation ? ' (' + a.confirmation + ')' : '') + '</div>';
        } else if (!a.attempted) {
          html = '<div style="color:#b45309;font-size:13px">ℹ️ Auto-book unavailable (' +
                 (a.reason || 'n/a') + '). Use a link above instead.</div>';
        } else {
          html = '<div style="color:#b45309;font-size:13px">⚠️ Stopped: ' +
                 (a.stopped_reason || 'unknown') + ' — use a link above.</div>';
        }
        if (a.screenshot_b64) {
          html += '<img alt="agent view" src="data:image/png;base64,' + a.screenshot_b64 +
                  '" style="margin-top:10px;width:100%;border-radius:10px;border:1px solid #eee">';
        }
        if (out) out.innerHTML = html;
      } catch (e) {
        if (out) out.innerHTML = '<div style="color:#b91c1c;font-size:13px">⚠️ ' + (e.message || e) + '</div>';
      }
      btn.disabled = false; btn.textContent = '🤖 Let Okeder book it (beta)';
    }
    async function markBooked() {
      const memberId = localStorage.getItem('okeder_member_' + EVENT_ID) || '';
      try {
        const r = await fetch(BACKEND + '/pwa/result/' + EVENT_ID + '/book/confirm', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ member_id: memberId }),
        });
        if (!r.ok) throw new Error('http ' + r.status);
        const box = document.getElementById('booking-actions');
        box.innerHTML = '<div style="text-align:center;color:var(--ok,#16a34a);font-weight:700">✅ Booked! Everyone has been notified.</div>';
      } catch (e) { alert('Could not mark as booked.'); }
    }
    """

    body = f"""
<div class="wrap">
  <div class="brand" style="margin-bottom:18px"><span class="dot"></span>Okeder</div>
  <span class="pill">🎉 The plan is ready</span>
  <h1 style="margin-top:14px">{title_line}</h1>
  {tags_block}

  {venue_card}

  <div class="card" style="margin-top:16px">
    <div class="label">Why this works</div>
    {metrics}
  </div>

  <div class="card soft pushbar" id="push-banner" style="margin-top:16px">
    <p>🔔 Get notified when things update</p>
    <button class="btn btn-ghost sm" onclick="subscribePush()">Enable</button>
  </div>
  <div id="push-done" class="center muted" style="display:none;margin-top:10px">✅ Notifications enabled</div>

  <div class="label" style="margin-top:24px">Are you in?</div>
  <div class="commit-row">
    <button class="btn btn-ghost" onclick="commit('soft')">👍 Interested</button>
    <button class="btn btn-primary" onclick="commit('confirmed')">✅ I'm In</button>
    <button class="btn btn-dark" onclick="commit('hard')">🔒 Lock In</button>
  </div>

  <div class="label" style="margin-top:24px">Lock the table</div>
  <div class="card" style="margin-top:8px">
    <p class="muted" style="font-size:13.5px">Okeder preps the reservation for this venue — pick a channel, one tap. Anyone in the group can do it.</p>
    <button class="btn btn-primary" id="book-prep" onclick="loadBooking()" style="margin-top:12px">📅 Prepare reservation</button>
    <div id="booking-actions" style="display:none;margin-top:4px"></div>
  </div>

  <script>
    const EVENT_ID = "{event_id}";
    const BACKEND  = "{public_url}";
    const VAPID_KEY = "{vapid_key}";

    async function subscribePush() {{
      if (!('serviceWorker' in navigator) || !('PushManager' in window)) {{
        alert('Push not supported on this browser'); return;
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
      const memberId = localStorage.getItem('okeder_member_' + EVENT_ID) || '';
      if (level === 'hard') {{
        try {{
          const dr = await fetch(BACKEND + '/pwa/deposit', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' }},
            body: JSON.stringify({{ event_id: EVENT_ID, member_id: memberId }}),
          }});
          if (dr.ok) {{ const dd = await dr.json(); if (dd.url) {{ window.location.href = dd.url; return; }} }}
        }} catch (e) {{ /* repli: enregistrer l'engagement sans paiement */ }}
      }}
      try {{
        const res = await fetch(BACKEND + '/pwa/commit', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' }},
          body: JSON.stringify({{ event_id: EVENT_ID, level: level, member_id: memberId }}),
        }});
        if (!res.ok) throw new Error('http ' + res.status);
        const data = await res.json();
        if (data.member_id) localStorage.setItem('okeder_member_' + EVENT_ID, data.member_id);
        _renderCommit(level, data.counts);
      }} catch (e) {{
        alert('Could not record your response. Please try again.');
      }}
    }}

    function _renderCommit(level, counts) {{
      const labels = {{ soft: "👍 Interested", confirmed: "✅ I'm In", hard: "🔒 Locked In" }};
      const order = {{ soft: 0, confirmed: 1, hard: 2 }};
      const row = document.querySelector('.commit-row');
      const btns = document.querySelectorAll('.commit-row .btn');
      btns.forEach((b, i) => {{ b.style.outline = (i === order[level]) ? '2.5px solid var(--accent)' : 'none'; b.style.outlineOffset='2px'; }});
      let st = document.getElementById('commit-status');
      if (!st && row) {{
        st = document.createElement('div');
        st.id = 'commit-status';
        st.style.cssText = 'text-align:center;color:var(--ok);font-weight:700;margin-top:14px;font-size:14px';
        row.parentNode.insertBefore(st, row.nextSibling);
      }}
      if (st) st.textContent = (labels[level] || 'Recorded') + ' — saved! Tap another to change.';
      if (counts) {{
        let el = document.getElementById('commit-counts');
        if (!el && st) {{
          el = document.createElement('div');
          el.id = 'commit-counts';
          el.style.cssText = 'text-align:center;color:var(--muted);font-size:13px;margin-top:6px';
          st.parentNode.insertBefore(el, st.nextSibling);
        }}
        if (el) el.textContent = '👍 ' + counts.soft + '    ✅ ' + counts.confirmed + '    🔒 ' + counts.hard;
      }}
    }}

    {booking_js}

    function urlBase64ToUint8Array(base64String) {{
      const padding = '='.repeat((4 - base64String.length % 4) % 4);
      const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
      const raw = window.atob(base64);
      return new Uint8Array([...raw].map(c => c.charCodeAt(0)));
    }}

    if ('serviceWorker' in navigator) {{
      navigator.serviceWorker.register('/sw.js').catch(() => {{}});
    }}
    if (Notification && Notification.permission === 'granted') {{
      document.getElementById('push-banner').style.display = 'none';
    }}
  </script>
</div>"""
    return HTMLResponse(content=shell("Okeder — Your group outing", body, head_extra=head))
