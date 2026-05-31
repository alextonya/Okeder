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

    <!-- DISPONIBILITÉS -->
    <div class="section">
      <span class="section-label">Date idéale <span style="font-weight:400;text-transform:none">(optionnel)</span></span>
      <input type="date" id="preferred-date" style="color-scheme:dark">
      <div style="margin-top:10px">
        <span style="font-size:12px;color:var(--tg-theme-hint-color,#64748b);display:block;margin-bottom:8px">FLEXIBILITÉ</span>
        <div class="chips" id="margin-chips">
          <span class="chip single" data-group="margin" data-val="1">± 1 jour</span>
          <span class="chip single" data-group="margin" data-val="3">± 3 jours</span>
          <span class="chip single selected" data-group="margin" data-val="5">± 5 jours</span>
          <span class="chip single" data-group="margin" data-val="14">± 2 sem</span>
        </div>
      </div>
    </div>

    <div class="section">
      <span class="section-label">Quel moment ? <span style="font-weight:400;text-transform:none">(optionnel)</span></span>
      <div class="chips" id="times-chips">
        <span class="chip" data-group="times" data-val="lunch">🌅 Déjeuner</span>
        <span class="chip" data-group="times" data-val="after_work">🌆 Après le boulot</span>
        <span class="chip" data-group="times" data-val="evening">🌙 Soirée</span>
        <span class="chip" data-group="times" data-val="weekend">🎉 Week-end</span>
      </div>
    </div>

    <div class="divider"></div>

    <!-- ZONE GÉOGRAPHIQUE — autocomplete Nominatim -->
    <div class="section">
      <span class="section-label">Votre point de départ<span class="required">*</span></span>
      <div style="position:relative">
        <input type="text" id="departure-text" autocomplete="off"
          placeholder="Commence à taper une adresse, quartier ou ville…"
          oninput="onDepartureInput(this.value)">
        <div id="departure-suggestions" style="
          display:none; position:absolute; top:100%; left:0; right:0; z-index:100;
          background:var(--tg-theme-secondary-bg-color,#1e293b);
          border:1.5px solid rgba(255,255,255,0.15); border-top:none; border-radius:0 0 12px 12px;
          max-height:200px; overflow-y:auto;
        "></div>
      </div>
      <input type="hidden" id="departure-lat" value="">
      <input type="hidden" id="departure-lng" value="">
      <p class="hint" style="margin-top:6px" id="departure-selected-hint"></p>
    </div>

    <!-- CONTEXTE DE DÉPART -->
    <div class="section">
      <span class="section-label">Tu pars d'où ? <span style="font-weight:400;text-transform:none">(optionnel)</span></span>
      <div class="chips" id="departure-chips">
        <span class="chip single" data-group="departure" data-val="home">🏠 De chez moi</span>
        <span class="chip single" data-group="departure" data-val="work">🏢 Du bureau</span>
        <span class="chip single" data-group="departure" data-val="center">🎯 Centre-ville</span>
      </div>
      <div id="departure-extra" style="display:none"></div>
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

    <!-- NOM + EMAIL -->
    <div class="section">
      <span class="section-label">Ton prénom</span>
      <input type="text" id="display-name" placeholder="Prénom ou surnom">
    </div>
    <div class="section">
      <span class="section-label">Email <span style="font-weight:400;text-transform:none">(pour recevoir la proposal)</span></span>
      <input type="email" id="notify-email" placeholder="ton@email.com" autocomplete="email">
      <p class="hint" style="margin-top:6px">Uniquement pour t'envoyer la proposition.</p>
    </div>

    <button class="submit-btn" id="submit-btn" onclick="submitPrefs()">
      Envoyer mes préférences
    </button>
  </div>

  <div class="success" id="success-view">
    <div class="icon">✅</div>
    <h2>Done!</h2>
    <p style="margin-bottom:16px">Your preferences have been saved.</p>
    <div id="result-link-box" style="display:none;
      background:rgba(99,102,241,0.15);border:1px solid #6366f1;
      border-radius:12px;padding:14px;margin-bottom:12px;text-align:left">
      <p style="font-size:13px;color:#a5b4fc;margin-bottom:8px">
        📌 Bookmark this link to see the proposal when it's ready:
      </p>
      <a id="result-link-url" href="#" target="_blank"
         style="font-size:12px;color:#6366f1;word-break:break-all"></a>
    </div>
    <p style="font-size:13px;color:var(--tg-theme-hint-color,#64748b)">
      You'll be notified when the proposal is ready.
    </p>
  </div>

  <script>
    const tg = window.Telegram.WebApp;
    tg.ready();
    tg.expand();

    const EVENT_ID = "{event_id}";
    const BACKEND_URL = "{backend_url}";
    // next_url : page vers laquelle rediriger après soumission (optionnel)
    const NEXT_URL = new URLSearchParams(window.location.search).get('next') || "";

    // Sélections courantes
    const selected = {{ vibe: new Set(), activity: new Set(), times: new Set() }};
    const singleSelected = {{ departure: null, travel: null, margin: '5' }};

    // ─── Préremplissage au chargement ────────────────────────────────────────
    window.addEventListener('load', async () => {{
      // 1. Prénom depuis Telegram
      const user = tg.initDataUnsafe?.user;
      if (user?.first_name) {{
        const f = document.getElementById('display-name');
        f.value = user.first_name;
        f.placeholder = user.first_name;
      }}

      // 2. Préférences existantes (si initData disponible = WebApp depuis DM)
      if (tg.initData) {{
        try {{
          const res = await fetch(BACKEND_URL + '/mini-app/' + EVENT_ID + '/prefill', {{
            method: 'POST',
            headers: {{
              'Content-Type': 'application/json',
              'ngrok-skip-browser-warning': 'true',
            }},
            body: JSON.stringify({{ init_data: tg.initData }}),
          }});

          if (res.ok) {{
            const data = await res.json();
            if (data.found) _prefillForm(data);
          }}
        }} catch (e) {{
          // Silencieux — formulaire vide si pas de données
        }}
      }}
    }});

    function _prefillForm(data) {{
      // Vibe
      (data.vibe || []).forEach(v => {{
        const chip = document.querySelector(`.chip[data-group="vibe"][data-val="${{v}}"]`);
        if (chip) {{ chip.classList.add('selected'); selected.vibe.add(v); }}
      }});

      // Activité
      (data.activity || []).forEach(v => {{
        const chip = document.querySelector(`.chip[data-group="activity"][data-val="${{v}}"]`);
        if (chip) {{ chip.classList.add('selected'); selected.activity.add(v); }}
      }});

      // Départ (single)
      if (data.departure_type) {{
        const chip = document.querySelector(`.chip.single[data-group="departure"][data-val="${{data.departure_type}}"]`);
        if (chip) {{
          chip.classList.add('selected');
          singleSelected.departure = data.departure_type;
          if (data.departure_type === 'other') {{
            document.getElementById('departure-extra').style.display = 'block';
          }}
        }}
      }}
      // Date idéale
      if (data.preferred_date) {{
        document.getElementById('preferred-date').value = data.preferred_date;
      }}
      // Marge
      if (data.date_margin_days) {{
        const mchip = document.querySelector(`.chip.single[data-group="margin"][data-val="${{data.date_margin_days}}"]`);
        if (mchip) {{
          document.querySelectorAll('.chip.single[data-group="margin"]').forEach(c => c.classList.remove('selected'));
          mchip.classList.add('selected');
          singleSelected.margin = String(data.date_margin_days);
        }}
      }}
      // Moments
      (data.times || []).forEach(v => {{
        const chip = document.querySelector(`.chip[data-group="times"][data-val="${{v}}"]`);
        if (chip) {{ chip.classList.add('selected'); selected.times.add(v); }}
      }});

      // Zone géographique (toujours visible maintenant)
      if (data.departure_text) {{
        document.getElementById('departure-text').value = data.departure_text;
      }}

      // Temps de trajet (single)
      if (data.travel_time_max) {{
        const val = String(data.travel_time_max);
        const chip = document.querySelector(`.chip.single[data-group="travel"][data-val="${{val}}"]`);
        if (chip) {{
          chip.classList.add('selected');
          singleSelected.travel = val;
        }}
      }}

      // Budget
      if (data.budget_min) document.getElementById('budget-min').value = Math.round(data.budget_min / 100);
      if (data.budget_max) document.getElementById('budget-max').value = Math.round(data.budget_max / 100);

      // Hard nos
      if (data.hard_constraints?.length) {{
        document.getElementById('hard-nos').value = data.hard_constraints.join(', ');
      }}

      // Nom
      if (data.display_name) {{
        const f = document.getElementById('display-name');
        if (!f.value) f.value = data.display_name;
      }}

      // Indicateur visuel
      const subtitle = document.querySelector('.subtitle');
      if (subtitle) subtitle.textContent = '✏️ Modifie tes préférences si besoin.';
    }}

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

    // ─── Autocomplete adresse (Photon by Komoot — meilleur que Nominatim) ────
    // Photon utilise OSM mais avec fuzzy search bien supérieur pour les adresses précises
    let _searchTimer = null;

    async function onDepartureInput(val) {{
      document.getElementById('departure-lat').value = '';
      document.getElementById('departure-lng').value = '';
      document.getElementById('departure-selected-hint').textContent = '';

      clearTimeout(_searchTimer);
      const box = document.getElementById('departure-suggestions');

      if (val.length < 2) {{ box.style.display = 'none'; return; }}

      _searchTimer = setTimeout(async () => {{
        box.innerHTML = '<div style="padding:10px 14px;font-size:12px;color:#64748b">Searching...</div>';
        box.style.display = 'block';

        try {{
          // Photon : bien meilleur pour adresses précises (maison, rue, quartier)
          const url = `https://photon.komoot.io/api/?q=${{encodeURIComponent(val)}}&limit=7&lang=en`;
          const resp = await fetch(url);
          const data = await resp.json();
          const features = data.features || [];

          box.innerHTML = '';
          if (!features.length) {{
            box.innerHTML = '<div style="padding:10px 14px;font-size:12px;color:#64748b">No results — try a different spelling</div>';
            return;
          }}

          features.forEach(f => {{
            const p = f.properties;
            const coords = f.geometry.coordinates; // [lng, lat]

            // Construire un label lisible
            const parts = [];
            if (p.housenumber) parts.push(p.housenumber);
            if (p.street || p.name) parts.push(p.street || p.name);
            if (p.city || p.town || p.village) parts.push(p.city || p.town || p.village);
            if (p.postcode) parts.push(p.postcode);
            if (p.country) parts.push(p.country);
            const label = parts.filter(Boolean).join(', ');
            if (!label) return;

            const item = document.createElement('div');
            item.textContent = label;
            item.style.cssText = 'padding:10px 14px;cursor:pointer;font-size:13px;border-bottom:1px solid rgba(255,255,255,0.07);line-height:1.4;';
            item.addEventListener('mouseover', () => item.style.background = 'rgba(99,102,241,0.15)');
            item.addEventListener('mouseout', () => item.style.background = '');
            item.addEventListener('mousedown', () => {{
              document.getElementById('departure-text').value = label;
              document.getElementById('departure-lat').value = coords[1];
              document.getElementById('departure-lng').value = coords[0];
              document.getElementById('departure-selected-hint').textContent = '✅ ' + label;
              box.style.display = 'none';
            }});
            box.appendChild(item);
          }});
        }} catch(e) {{
          box.innerHTML = '<div style="padding:10px 14px;font-size:12px;color:#ef4444">Search error — check your connection</div>';
        }}
      }}, 300);
    }}

    document.getElementById('departure-text').addEventListener('blur', () => {{
      setTimeout(() => {{ document.getElementById('departure-suggestions').style.display = 'none'; }}, 250);
    }});

    async function submitPrefs() {{
      // Validation
      if (selected.vibe.size === 0) {{
        alert('Choisis au moins une ambiance (Vibe)');
        return;
      }}
      const depText = document.getElementById('departure-text').value.trim();
      const depLat  = document.getElementById('departure-lat').value;
      const depLng  = document.getElementById('departure-lng').value;
      if (!depText) {{
        alert('Please enter your starting point');
        document.getElementById('departure-text').focus();
        return;
      }}
      // Forcer la sélection dans la liste pour avoir des coordonnées précises
      if (!depLat || !depLng) {{
        const box = document.getElementById('departure-suggestions');
        if (box.children.length > 0) {{
          alert('Please select an address from the suggestions list (tap on a result).');
          document.getElementById('departure-text').focus();
          return;
        }}
        // Pas de suggestions disponibles — on soumet quand même avec texte seul
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
      // depText déjà lu dans la validation ci-dessus

      const body = {{
        init_data:        tg.initData || "",
        display_name:     name,
        notify_email:     document.getElementById('notify-email').value.trim() || null,
        next_url:         NEXT_URL || null,
        event_id:         EVENT_ID,
        // Ambiance + activité
        vibe:             [...selected.vibe],
        activity:         [...selected.activity],
        // Disponibilités
        preferred_date:   document.getElementById('preferred-date').value || null,
        date_margin_days: parseInt(singleSelected.margin || '5'),
        times:            [...selected.times],
        // Localisation avec coordonnées
        departure_type:   singleSelected.departure,
        departure_text:   depText || null,
        departure_lat:    depLat ? parseFloat(depLat) : null,
        departure_lng:    depLng ? parseFloat(depLng) : null,
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
          const data = await res.json().catch(() => ({{}}));
          document.getElementById('form-view').style.display = 'none';
          const sv = document.getElementById('success-view');
          sv.style.display = 'flex';

          // Afficher le lien /result/ pour que les invités puissent revenir
          const resultUrl = BACKEND_URL + '/result/' + EVENT_ID;
          const linkBox = document.getElementById('result-link-box');
          const linkEl  = document.getElementById('result-link-url');
          if (linkBox && linkEl) {{
            linkEl.href = resultUrl;
            linkEl.textContent = resultUrl;
            linkBox.style.display = 'block';
          }}

          // Redirection : next_url (organisateur) ou fermeture Telegram
          const redirectTo = data.next_url || NEXT_URL;
          if (redirectTo) {{
            setTimeout(() => window.location.href = redirectTo, 2000);
          }} else if (tg.initData) {{
            setTimeout(() => tg.close(), 3000);
          }}
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
    notify_email = body.get("notify_email", "").strip() or None

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
            if notify_email:
                member.email = notify_email
    else:
        member = Member(display_name=display_name, email=notify_email)
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
        "preferred_date":  body.get("preferred_date"),
        "date_margin_days": body.get("date_margin_days", 5),
        "times":           body.get("times", []),
        "departure_type":  body.get("departure_type"),
        "departure_text":  body.get("departure_text"),
        "departure_lat":   body.get("departure_lat"),
        "departure_lng":   body.get("departure_lng"),
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

    # Vérifier si le quorum est atteint → déclencher l'engine si wizard_mode=False
    # Wrapped dans try/except pour ne jamais bloquer la réponse au membre
    try:
        from app.workers.jobs.collect_constraints import check_and_trigger_engine
        await check_and_trigger_engine(event_id_str, db)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"check_and_trigger_engine: {e}")

    # Si next_url fourni dans le body → renvoyer l'URL de redirection
    next_url = body.get("next_url")
    return {"ok": True, "next_url": next_url}


@router.post("/mini-app/{event_id}/prefill")
async def get_existing_preferences(
    event_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Retourne les préférences existantes d'un membre pour préremplir le formulaire.
    Identité validée via Telegram initData.
    Retourne {"found": False} si aucune donnée existante.
    """
    from app.models.member import Member
    from app.models.preference import Preference

    body = await request.json()
    init_data = body.get("init_data", "")

    user_data = _validate_telegram_init_data(init_data, settings.telegram_bot_token) if init_data else None
    if not user_data:
        return {"found": False}

    tg_user_id = user_data.get("id")
    member_result = await db.execute(
        select(Member).where(Member.telegram_user_id == tg_user_id)
    )
    member = member_result.scalar_one_or_none()
    if not member:
        return {"found": False}

    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        return {"found": False}

    pref_result = await db.execute(
        select(Preference).where(
            Preference.event_id == event_uuid,
            Preference.member_id == member.id,
            Preference.declined == False,  # noqa: E712
            Preference.submitted_at != None,  # noqa: E711
        )
    )
    pref = pref_result.scalar_one_or_none()
    if not pref:
        return {"found": False}

    # Extraire depuis raw_answers (source de vérité pour les nouveaux champs)
    raw = pref.raw_answers or {}

    return {
        "found": True,
        "vibe":            raw.get("vibe", []),
        "activity":        raw.get("activity", []),
        "preferred_date":  raw.get("preferred_date"),
        "date_margin_days": raw.get("date_margin_days", 5),
        "times":           raw.get("times", []),
        "departure_type":  raw.get("departure_type"),
        "departure_text":  raw.get("departure_text"),
        "travel_time_max": raw.get("travel_time_max"),
        "budget_min":      pref.budget_min,
        "budget_max":      pref.budget_max,
        "hard_constraints": pref.hard_constraints or [],
        "display_name":    member.display_name,
    }
