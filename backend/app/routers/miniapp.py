"""
Telegram Mini App — servi par le backend FastAPI.
Identité validée via Telegram initData (HMAC-SHA256).
Formulaire : ambiance, activité, point de départ, temps de trajet, budget, hard nos.
"""
import hashlib
import hmac
import json
import os
import uuid
from urllib.parse import parse_qs, unquote

from fastapi import APIRouter, Depends, Request
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
  <title>Okeder — Preferences</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: var(--tg-theme-bg-color, #0f172a);
      color: var(--tg-theme-text-color, #f1f5f9);
      padding: 16px 16px 32px;
      min-height: 100vh;
    }}
    h1 {{ font-size: 20px; font-weight: 700; margin-bottom: 4px; }}
    .subtitle {{ font-size: 13px; color: var(--tg-theme-hint-color, #94a3b8); margin-bottom: 24px; }}
    .section {{ margin-bottom: 20px; }}
    .section-label {{
      display: block; font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
      color: var(--tg-theme-hint-color, #64748b); text-transform: uppercase; margin-bottom: 10px;
    }}
    .required {{ color: #f43f5e; margin-left: 2px; }}
    /* Chips */
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .chip {{
      padding: 8px 14px; border-radius: 20px; font-size: 14px; cursor: pointer;
      border: 1.5px solid rgba(255,255,255,0.12);
      background: var(--tg-theme-secondary-bg-color, #1e293b);
      color: var(--tg-theme-text-color, #f1f5f9);
      transition: all 0.15s; user-select: none; -webkit-tap-highlight-color: transparent;
    }}
    .chip.selected {{ background: #6366f1; border-color: #6366f1; color: white; }}
    .chip.single.selected {{ background: #0ea5e9; border-color: #0ea5e9; }}
    /* Input */
    input, textarea {{
      width: 100%; padding: 12px 14px; border-radius: 12px;
      border: 1.5px solid rgba(255,255,255,0.1);
      background: var(--tg-theme-secondary-bg-color, #1e293b);
      color: var(--tg-theme-text-color, #f1f5f9);
      font-size: 15px; outline: none; transition: border-color 0.15s;
    }}
    input:focus, textarea:focus {{ border-color: #6366f1; }}
    .row {{ display: flex; gap: 10px; }}
    .row input {{ flex: 1; }}
    .hint {{ font-size: 12px; color: var(--tg-theme-hint-color, #64748b); margin-top: 6px; }}
    /* Departure extra */
    #departure-extra {{ display: none; margin-top: 10px; }}
    /* Submit */
    .submit-btn {{
      width: 100%; padding: 16px; border-radius: 14px; border: none;
      background: var(--tg-theme-button-color, #6366f1);
      color: var(--tg-theme-button-text-color, white);
      font-size: 16px; font-weight: 600; cursor: pointer; margin-top: 8px;
      transition: opacity 0.15s; -webkit-tap-highlight-color: transparent;
    }}
    .submit-btn:active {{ opacity: 0.8; }}
    .submit-btn:disabled {{ opacity: 0.4; }}
    /* Success */
    .success {{
      display: none; flex-direction: column; align-items: center;
      justify-content: center; min-height: 60vh; text-align: center; gap: 14px;
    }}
    .success .icon {{ font-size: 60px; }}
    .success h2 {{ font-size: 24px; font-weight: 700; }}
    .success p {{ color: var(--tg-theme-hint-color, #94a3b8); font-size: 14px; line-height: 1.5; }}
    /* Divider */
    .divider {{ height: 1px; background: rgba(255,255,255,0.07); margin: 4px 0 20px; }}
  </style>
</head>
<body>
  <div id="form-view">
    <h1>Your preferences</h1>
    <p class="subtitle">Private — takes 30 seconds.</p>

    <!-- VIBE -->
    <div class="section">
      <span class="section-label">Vibe<span class="required">*</span></span>
      <div class="chips" id="vibe-chips">
        <span class="chip" data-group="vibe" data-val="casual">😌 Casual</span>
        <span class="chip" data-group="vibe" data-val="professional">💼 Pro</span>
        <span class="chip" data-group="vibe" data-val="festive">🎉 Festif</span>
        <span class="chip" data-group="vibe" data-val="cosy">🍵 Cosy</span>
        <span class="chip" data-group="vibe" data-val="outdoor">🌿 Outdoor</span>
        <span class="chip" data-group="vibe" data-val="cultural">🎨 Culturel</span>
      </div>
    </div>

    <!-- ACTIVITÉ -->
    <div class="section">
      <span class="section-label">Type d'activité <span style="font-weight:400;text-transform:none">(optionnel)</span></span>
      <div class="chips" id="activity-chips">
        <span class="chip" data-group="activity" data-val="dinner">🍽️ Dîner</span>
        <span class="chip" data-group="activity" data-val="drinks">🍸 Apéro</span>
        <span class="chip" data-group="activity" data-val="concert">🎵 Concert</span>
        <span class="chip" data-group="activity" data-val="activity">🎮 Activité</span>
        <span class="chip" data-group="activity" data-val="cinema">🎬 Ciné</span>
        <span class="chip" data-group="activity" data-val="brunch">☕ Brunch</span>
      </div>
    </div>

    <div class="divider"></div>

    <!-- POINT DE DÉPART -->
    <div class="section">
      <span class="section-label">Tu pars d'où ?<span class="required">*</span></span>
      <div class="chips" id="departure-chips">
        <span class="chip single" data-group="departure" data-val="home">🏠 De chez moi</span>
        <span class="chip single" data-group="departure" data-val="work">🏢 Du bureau</span>
        <span class="chip single" data-group="departure" data-val="center">🎯 Centre-ville</span>
        <span class="chip single" data-group="departure" data-val="other">📍 Autre</span>
      </div>
      <div id="departure-extra">
        <input type="text" id="departure-text" placeholder="Station de métro, quartier, adresse…">
      </div>
    </div>

    <!-- TEMPS DE TRAJET -->
    <div class="section">
      <span class="section-label">Temps de trajet max<span class="required">*</span></span>
      <div class="chips" id="travel-chips">
        <span class="chip single" data-group="travel" data-val="15">⚡ 15 min</span>
        <span class="chip single" data-group="travel" data-val="30">🚶 30 min</span>
        <span class="chip single" data-group="travel" data-val="45">🚇 45 min</span>
        <span class="chip single" data-group="travel" data-val="999">🌍 Peu importe</span>
      </div>
    </div>

    <div class="divider"></div>

    <!-- BUDGET -->
    <div class="section">
      <span class="section-label">Budget par personne (€) <span style="font-weight:400;text-transform:none">(optionnel)</span></span>
      <div class="row">
        <input type="number" id="budget-min" placeholder="Min (ex: 20)" min="0">
        <input type="number" id="budget-max" placeholder="Max (ex: 60)" min="0">
      </div>
    </div>

    <!-- HARD NOS -->
    <div class="section">
      <span class="section-label">À éviter absolument <span style="font-weight:400;text-transform:none">(optionnel)</span></span>
      <input type="text" id="hard-nos" placeholder="ex: pas de sushi, accès PMR, halal">
      <p class="hint">Sépare par des virgules. Ces contraintes seront strictement respectées.</p>
    </div>

    <!-- NOM -->
    <div class="section">
      <span class="section-label">Ton prénom</span>
      <input type="text" id="display-name" placeholder="Prénom ou surnom">
    </div>

    <button class="submit-btn" id="submit-btn" onclick="submitPrefs()">
      Envoyer mes préférences
    </button>
  </div>

  <div class="success" id="success-view">
    <div class="icon">✅</div>
    <h2>C'est noté !</h2>
    <p>Tes préférences ont été enregistrées.<br>Tu seras notifié dès que le plan est prêt.</p>
  </div>

  <script>
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();

    const EVENT_ID = "{event_id}";
    const BACKEND_URL = "{backend_url}";

    // Sélections courantes
    const selected = {{ vibe: new Set(), activity: new Set() }};
    const singleSelected = {{ departure: null, travel: null }};

    // Préremplir prénom depuis Telegram
    window.addEventListener('load', () => {{
      const user = tg.initDataUnsafe?.user;
      if (user?.first_name) {{
        const f = document.getElementById('display-name');
        f.value = user.first_name;
        f.placeholder = user.first_name;
      }}
    }});

    // Chips multi-select (vibe, activity)
    document.querySelectorAll('.chip:not(.single)').forEach(chip => {{
      chip.addEventListener('click', () => {{
        chip.classList.toggle('selected');
        const group = chip.dataset.group;
        const val = chip.dataset.val;
        if (selected[group].has(val)) selected[group].delete(val);
        else selected[group].add(val);
      }});
    }});

    // Chips single-select (departure, travel)
    document.querySelectorAll('.chip.single').forEach(chip => {{
      chip.addEventListener('click', () => {{
        const group = chip.dataset.group;
        // Désélectionner l'ancien
        document.querySelectorAll(`.chip.single[data-group="${{group}}"]`).forEach(c => c.classList.remove('selected'));
        chip.classList.add('selected');
        singleSelected[group] = chip.dataset.val;

        // Afficher le champ texte si "autre" pour le départ
        if (group === 'departure') {{
          document.getElementById('departure-extra').style.display =
            chip.dataset.val === 'other' ? 'block' : 'none';
        }}
      }});
    }});

    async function submitPrefs() {{
      // Validation
      if (selected.vibe.size === 0) {{
        alert('Choisis au moins une ambiance (Vibe)');
        return;
      }}
      if (!singleSelected.departure) {{
        alert('Indique ton point de départ');
        return;
      }}
      if (!singleSelected.travel) {{
        alert('Indique ton temps de trajet maximum');
        return;
      }}

      const btn = document.getElementById('submit-btn');
      btn.disabled = true;
      btn.textContent = 'Envoi…';

      const budgetMin = document.getElementById('budget-min').value;
      const budgetMax = document.getElementById('budget-max').value;
      const hardNos   = document.getElementById('hard-nos').value;
      const name      = document.getElementById('display-name').value.trim();
      const depText   = document.getElementById('departure-text').value.trim();

      const body = {{
        init_data:        tg.initData || "",
        display_name:     name,
        event_id:         EVENT_ID,
        // Ambiance + activité
        vibe:             [...selected.vibe],
        activity:         [...selected.activity],
        // Localisation
        departure_type:   singleSelected.departure,
        departure_text:   depText || null,
        travel_time_max:  parseInt(singleSelected.travel),
        // Budget
        budget_min:  budgetMin ? Math.round(parseFloat(budgetMin) * 100) : null,
        budget_max:  budgetMax ? Math.round(parseFloat(budgetMax) * 100) : null,
        // Contraintes
        hard_constraints: hardNos ? hardNos.split(',').map(s => s.trim()).filter(Boolean) : [],
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
          setTimeout(() => tg.close(), 2500);
        }} else {{
          btn.disabled = false;
          btn.textContent = 'Envoyer mes préférences';
          const err = await res.json().catch(() => ({{}}));
          alert(err.detail || 'Erreur. Réessaie.');
        }}
      }} catch(e) {{
        btn.disabled = false;
        btn.textContent = 'Envoyer mes préférences';
        alert('Erreur réseau. Réessaie.');
      }}
    }}
  </script>
</body>
</html>"""


@router.get("/mini-app/{event_id}", response_class=HTMLResponse)
async def serve_mini_app(event_id: str):
    public_url = os.environ.get("PUBLIC_URL", "http://localhost:8000")
    html = MINI_APP_HTML.format(event_id=event_id, backend_url=public_url)
    return HTMLResponse(content=html)


def _validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    try:
        parsed = parse_qs(unquote(init_data))
        hash_value = parsed.get("hash", [""])[0]
        data_pairs = [f"{k}={v[0]}" for k, v in parsed.items() if k != "hash"]
        data_check_string = "\n".join(sorted(data_pairs))
        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        expected = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, hash_value):
            return None
        return json.loads(parsed.get("user", ["{}"])[0])
    except Exception:
        return None


@router.post("/mini-app/submit")
async def submit_mini_app_preferences(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone

    from app.models.member import Member
    from app.models.preference import Preference

    body = await request.json()
    init_data    = body.get("init_data", "")
    event_id_str = body.get("event_id", "")
    display_name = body.get("display_name", "").strip() or "Anonymous"

    # Identification via Telegram initData ou fallback nom
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
            if display_name and display_name != "Anonymous":
                member.display_name = display_name
    else:
        member = Member(display_name=display_name)
        db.add(member)
        await db.flush()

    event_uuid = uuid.UUID(event_id_str)

    # Construction des données structurées
    vibe     = body.get("vibe", [])
    activity = body.get("activity", [])
    category_prefs = vibe + activity  # stocké ensemble

    raw_answers = {
        "vibe":            vibe,
        "activity":        activity,
        "departure_type":  body.get("departure_type"),
        "departure_text":  body.get("departure_text"),
        "travel_time_max": body.get("travel_time_max"),
        "budget_min":      body.get("budget_min"),
        "budget_max":      body.get("budget_max"),
        "hard_constraints": body.get("hard_constraints", []),
        "display_name":    display_name,
    }

    # Upsert préférence
    pref_result = await db.execute(
        select(Preference).where(
            Preference.event_id == event_uuid,
            Preference.member_id == member.id,
        )
    )
    pref = pref_result.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    fields = dict(
        budget_min       = body.get("budget_min"),
        budget_max       = body.get("budget_max"),
        category_prefs   = category_prefs,
        hard_constraints = body.get("hard_constraints", []),
        soft_preferences = vibe,          # vibe → soft prefs pour le constraint engine
        raw_answers      = raw_answers,
        submitted_at     = now,
        declined         = False,
    )

    if pref:
        for k, v in fields.items():
            setattr(pref, k, v)
    else:
        pref = Preference(event_id=event_uuid, member_id=member.id, **fields)
        db.add(pref)

    await db.commit()
    return {"ok": True}
