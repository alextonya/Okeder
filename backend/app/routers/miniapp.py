"""
Telegram Mini App — servi par le backend FastAPI.
Pas d'auth Clerk requise : identité validée via Telegram initData (HMAC-SHA256).
"""
import hashlib
import hmac
import json
import os
import uuid
from urllib.parse import parse_qs, unquote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db

router = APIRouter()

MINI_APP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <title>Okeder — Your preferences</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: var(--tg-theme-bg-color, #0f172a);
      color: var(--tg-theme-text-color, #f1f5f9);
      padding: 16px;
      min-height: 100vh;
    }}
    h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 4px; }}
    .subtitle {{ font-size: 13px; color: var(--tg-theme-hint-color, #94a3b8); margin-bottom: 24px; }}
    .section {{ margin-bottom: 20px; }}
    label {{ display: block; font-size: 13px; font-weight: 600;
             color: var(--tg-theme-hint-color, #94a3b8); margin-bottom: 8px; }}
    input, textarea {{
      width: 100%; padding: 12px; border-radius: 10px;
      border: 1px solid rgba(255,255,255,0.1);
      background: var(--tg-theme-secondary-bg-color, #1e293b);
      color: var(--tg-theme-text-color, #f1f5f9);
      font-size: 15px; outline: none;
    }}
    input:focus, textarea:focus {{ border-color: #6366f1; }}
    .row {{ display: flex; gap: 10px; }}
    .row input {{ flex: 1; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .chip {{
      padding: 8px 14px; border-radius: 20px; font-size: 13px; cursor: pointer;
      border: 1px solid rgba(255,255,255,0.15);
      background: var(--tg-theme-secondary-bg-color, #1e293b);
      color: var(--tg-theme-text-color, #f1f5f9);
      transition: all 0.15s;
      user-select: none;
    }}
    .chip.selected {{ background: #6366f1; border-color: #6366f1; color: white; }}
    .hint {{ font-size: 12px; color: var(--tg-theme-hint-color, #64748b); margin-top: 6px; }}
    .submit-btn {{
      width: 100%; padding: 16px; border-radius: 12px; border: none;
      background: var(--tg-theme-button-color, #6366f1);
      color: var(--tg-theme-button-text-color, white);
      font-size: 16px; font-weight: 600; cursor: pointer;
      margin-top: 8px; transition: opacity 0.15s;
    }}
    .submit-btn:active {{ opacity: 0.8; }}
    .submit-btn:disabled {{ opacity: 0.4; }}
    .success {{
      text-align: center; padding: 40px 20px;
      display: none; flex-direction: column; align-items: center; gap: 12px;
    }}
    .success .icon {{ font-size: 56px; }}
    .success h2 {{ font-size: 22px; font-weight: 700; }}
    .success p {{ color: var(--tg-theme-hint-color, #94a3b8); font-size: 14px; }}
  </style>
</head>
<body>
  <div id="form-view">
    <h1>Your preferences</h1>
    <p class="subtitle">Private — only used to find the best option for everyone.</p>

    <div class="section">
      <label>YOUR NAME</label>
      <input type="text" id="display-name" placeholder="First name or nickname">
    </div>

    <div class="section">
      <label>BUDGET PER PERSON (€)</label>
      <div class="row">
        <input type="number" id="budget-min" placeholder="Min (e.g. 20)" min="0">
        <input type="number" id="budget-max" placeholder="Max (e.g. 60)" min="0">
      </div>
    </div>

    <div class="section">
      <label>WHAT KIND OF OUTING?</label>
      <div class="chips" id="categories">
        <span class="chip" data-val="restaurant">🍽️ Restaurant</span>
        <span class="chip" data-val="bar">🍸 Bar</span>
        <span class="chip" data-val="concert">🎵 Concert</span>
        <span class="chip" data-val="sport">⚽ Sport</span>
        <span class="chip" data-val="escape room">🔐 Escape Room</span>
        <span class="chip" data-val="cinema">🎬 Cinema</span>
        <span class="chip" data-val="other">✨ Other</span>
      </div>
    </div>

    <div class="section">
      <label>HARD NOS <span style="font-weight:400;opacity:0.6">(optional)</span></label>
      <input type="text" id="hard-nos" placeholder="e.g. no sushi, wheelchair access, halal">
      <p class="hint">Separate with commas. These will be strictly respected.</p>
    </div>

    <div class="section">
      <label>NICE TO HAVE <span style="font-weight:400;opacity:0.6">(optional)</span></label>
      <input type="text" id="soft-prefs" placeholder="e.g. rooftop, outdoor, jazz">
    </div>

    <button class="submit-btn" id="submit-btn" onclick="submitPrefs()">
      Submit preferences
    </button>
  </div>

  <div class="success" id="success-view">
    <div class="icon">✅</div>
    <h2>Done!</h2>
    <p>Your preferences have been saved.<br>You'll be notified when the plan is ready.</p>
  </div>

  <script>
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();

    const EVENT_ID = "{event_id}";
    const BACKEND_URL = "{backend_url}";
    const selectedCats = new Set();

    // Chip selection
    document.querySelectorAll('.chip').forEach(chip => {{
      chip.addEventListener('click', () => {{
        chip.classList.toggle('selected');
        const val = chip.dataset.val;
        if (selectedCats.has(val)) selectedCats.delete(val);
        else selectedCats.add(val);
      }});
    }});

    async function submitPrefs() {{
      const btn = document.getElementById('submit-btn');
      btn.disabled = true;
      btn.textContent = 'Saving…';

      const displayName = document.getElementById('display-name').value.trim();
      const budgetMin = document.getElementById('budget-min').value;
      const budgetMax = document.getElementById('budget-max').value;
      const hardNos = document.getElementById('hard-nos').value;
      const softPrefs = document.getElementById('soft-prefs').value;

      const body = {{
        init_data: tg.initData || "",
        display_name: displayName,
        event_id: EVENT_ID,
        budget_min: budgetMin ? Math.round(parseFloat(budgetMin) * 100) : null,
        budget_max: budgetMax ? Math.round(parseFloat(budgetMax) * 100) : null,
        category_prefs: [...selectedCats],
        hard_constraints: hardNos ? hardNos.split(',').map(s => s.trim()).filter(Boolean) : [],
        soft_preferences: softPrefs ? softPrefs.split(',').map(s => s.trim()).filter(Boolean) : [],
      }};

      try {{
        const res = await fetch(BACKEND_URL + '/mini-app/submit', {{
          method: 'POST',
          headers: {{
            'Content-Type': 'application/json',
            'ngrok-skip-browser-warning': 'true',
          }},
          body: JSON.stringify(body),
        }});

        if (res.ok) {{
          document.getElementById('form-view').style.display = 'none';
          const sv = document.getElementById('success-view');
          sv.style.display = 'flex';
          setTimeout(() => tg.close(), 2000);
        }} else {{
          btn.disabled = false;
          btn.textContent = 'Submit preferences';
          alert('Something went wrong. Please try again.');
        }}
      }} catch(e) {{
        btn.disabled = false;
        btn.textContent = 'Submit preferences';
        alert('Network error. Please try again.');
      }}
    }}
  </script>
</body>
</html>"""


@router.get("/mini-app/{event_id}", response_class=HTMLResponse)
async def serve_mini_app(event_id: str):
    """Sert le Mini App Telegram pour un event donné."""
    public_url = os.environ.get("PUBLIC_URL", "http://localhost:8000")
    html = MINI_APP_HTML.format(event_id=event_id, backend_url=public_url)
    return HTMLResponse(content=html)


def _validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """
    Valide la signature HMAC du Telegram initData.
    Retourne les données parsées si valide, None sinon.
    Ref: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    try:
        parsed = parse_qs(unquote(init_data))
        hash_value = parsed.get("hash", [""])[0]

        # Construire la data_check_string (tous les champs sauf hash, triés)
        data_pairs = []
        for key, values in parsed.items():
            if key != "hash":
                data_pairs.append(f"{key}={values[0]}")
        data_check_string = "\n".join(sorted(data_pairs))

        # Calculer le secret_key et le hash attendu
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(expected_hash, hash_value):
            return None

        # Parser user
        user_str = parsed.get("user", ["{}"])[0]
        return json.loads(user_str)

    except Exception:
        return None


@router.post("/mini-app/submit")
async def submit_mini_app_preferences(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Reçoit les préférences du Mini App et les sauvegarde en base."""
    from datetime import datetime, timezone

    from app.models.member import Member
    from app.models.preference import Preference

    body = await request.json()
    init_data = body.get("init_data", "")
    event_id_str = body.get("event_id", "")
    display_name = body.get("display_name", "Anonymous")

    # Essaie de valider Telegram initData (disponible si ouvert depuis Telegram)
    user_data = _validate_telegram_init_data(init_data, settings.telegram_bot_token) if init_data else None

    if user_data:
        tg_user_id = user_data.get("id")
        tg_name = (user_data.get("first_name", "") + " " + user_data.get("last_name", "")).strip()
        result = await db.execute(select(Member).where(Member.telegram_user_id == tg_user_id))
        member = result.scalar_one_or_none()
        if not member:
            member = Member(telegram_user_id=tg_user_id, display_name=tg_name or display_name)
            db.add(member)
            await db.flush()
    else:
        # Pas d'initData (ouvert depuis navigateur) — créer membre par nom
        member = Member(display_name=display_name or "Anonymous")
        db.add(member)
        await db.flush()

    event_uuid = uuid.UUID(event_id_str)

    # Upsert préférence
    pref_result = await db.execute(
        select(Preference).where(
            Preference.event_id == event_uuid,
            Preference.member_id == member.id,
        )
    )
    pref = pref_result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if pref:
        pref.budget_min = body.get("budget_min")
        pref.budget_max = body.get("budget_max")
        pref.category_prefs = body.get("category_prefs", [])
        pref.hard_constraints = body.get("hard_constraints", [])
        pref.soft_preferences = body.get("soft_preferences", [])
        pref.submitted_at = now
        pref.declined = False
    else:
        pref = Preference(
            event_id=event_uuid,
            member_id=member.id,
            budget_min=body.get("budget_min"),
            budget_max=body.get("budget_max"),
            category_prefs=body.get("category_prefs", []),
            hard_constraints=body.get("hard_constraints", []),
            soft_preferences=body.get("soft_preferences", []),
            submitted_at=now,
        )
        db.add(pref)

    await db.commit()
    return {"ok": True}
