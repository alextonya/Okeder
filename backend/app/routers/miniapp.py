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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    *{{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}}
    body{{
      font-family:'Plus Jakarta Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
      background:#FFFFFF;color:#0B0B0C;padding:24px 18px 40px;min-height:100vh;
      max-width:460px;margin:0 auto;-webkit-font-smoothing:antialiased;
    }}
    h1{{font-size:25px;font-weight:800;letter-spacing:-.03em;}}
    .subtitle{{font-size:14px;color:#6B7280;margin-top:6px;margin-bottom:26px;}}
    .section{{margin-bottom:22px;}}
    .section-label{{
      display:block;font-size:12px;font-weight:700;letter-spacing:.1em;
      color:#6B7280;text-transform:uppercase;margin-bottom:11px;
    }}
    .required{{color:#FF4D2E;margin-left:2px;}}
    /* Chips */
    .chips{{display:flex;flex-wrap:wrap;gap:9px;}}
    .chip{{
      padding:11px 16px;border-radius:999px;font-size:14.5px;font-weight:600;cursor:pointer;
      border:1.5px solid #ECECEC;background:#fff;color:#0B0B0C;
      transition:all .13s;user-select:none;
    }}
    .chip:active{{transform:scale(.96);}}
    .chip.selected{{background:#0B0B0C;border-color:#0B0B0C;color:#fff;}}
    .chip.single.selected{{background:#FF4D2E;border-color:#FF4D2E;color:#fff;}}
    /* Input */
    input,textarea{{
      width:100%;padding:14px 16px;border-radius:14px;border:1.5px solid #ECECEC;
      background:#fff;color:#0B0B0C;font-size:16px;font-family:inherit;outline:none;
      transition:border-color .15s,box-shadow .15s;
    }}
    input::placeholder,textarea::placeholder{{color:#9CA3AF;}}
    input:focus,textarea:focus{{border-color:#FF4D2E;box-shadow:0 0 0 4px rgba(255,77,46,.12);}}
    .row{{display:flex;gap:10px;}}
    .row input{{flex:1;}}
    .hint{{font-size:12.5px;color:#6B7280;margin-top:7px;}}
    #departure-extra{{display:none;margin-top:10px;}}
    /* Submit */
    .submit-btn{{
      width:100%;padding:17px;border-radius:999px;border:none;background:#FF4D2E;color:#fff;
      font-size:16.5px;font-weight:700;font-family:inherit;cursor:pointer;margin-top:8px;
      box-shadow:0 10px 26px -10px rgba(255,77,46,.6);
      transition:transform .08s,background .15s,opacity .15s;
    }}
    .submit-btn:active{{transform:scale(.98);background:#E63E1F;}}
    .submit-btn:disabled{{opacity:.45;box-shadow:none;}}
    /* Success */
    .success{{
      display:none;flex-direction:column;align-items:center;
      justify-content:center;min-height:60vh;text-align:center;gap:14px;
    }}
    .success .icon{{font-size:60px;}}
    .success h2{{font-size:26px;font-weight:800;letter-spacing:-.02em;}}
    .success p{{color:#6B7280;font-size:14px;line-height:1.5;}}
    /* Divider */
    .divider{{height:1px;background:#ECECEC;margin:6px 0 22px;}}
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
          background:#fff; box-shadow:0 12px 30px -8px rgba(0,0,0,.18);
          border:1.5px solid #ECECEC; border-top:none; border-radius:0 0 14px 14px;
          max-height:220px; overflow-y:auto;
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
    <div class="section" id="name-section">
      <span class="section-label">Ton prénom</span>
      <input type="text" id="display-name" placeholder="Prénom ou surnom">
    </div>
    <div class="section" id="contact-section">
      <span class="section-label">Email ou WhatsApp <span style="font-weight:400;text-transform:none">(pour recevoir la proposal)</span></span>
      <input type="email" id="notify-email" placeholder="ton@email.com" autocomplete="email" style="margin-bottom:10px">
      <input type="tel" id="notify-phone" placeholder="+44 7xxx xxx xxx (WhatsApp)" autocomplete="tel">
      <p class="hint" style="margin-top:6px">Pour t'envoyer la proposition quand elle est prête. Optionnel.</p>
    </div>

    <button class="submit-btn" id="submit-btn" onclick="submitPrefs()">
      Envoyer mes préférences
    </button>
    <button type="button" id="decline-btn" onclick="declineInvite()"
      style="width:100%;margin-top:14px;background:none;border:none;color:#9CA3AF;
             font-size:14px;font-weight:600;cursor:pointer;font-family:inherit">
      I can't make it — count me out
    </button>
  </div>

  <div class="success" id="declined-view">
    <div class="icon">👋</div>
    <h2>No worries!</h2>
    <p style="margin-bottom:16px">We've let the organiser know you can't make it this time.</p>
  </div>

  <div class="success" id="success-view">
    <div class="icon">✅</div>
    <h2>Done!</h2>
    <p style="margin-bottom:16px">Your preferences have been saved.</p>
    <div id="result-link-box" style="display:none;
      background:#FFF1ED;border:1px solid rgba(255,77,46,0.25);
      border-radius:14px;padding:14px;margin-bottom:12px;text-align:left">
      <p style="font-size:13px;color:#9A3412;font-weight:600;margin-bottom:8px">
        📌 Bookmark this link to see the proposal when it's ready:
      </p>
      <a id="result-link-url" href="#" target="_blank"
         style="font-size:12px;color:#FF4D2E;font-weight:600;word-break:break-all"></a>
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
    const PARAMS = new URLSearchParams(window.location.search);
    const NEXT_URL = PARAMS.get('next') || "";
    // Organisateur web pré-identifié depuis /create (compte connecté)
    const PRESET_MID = PARAMS.get('mid') || "";
    const PRESET_NAME = PARAMS.get('name') || "";

    // Sélections courantes
    const selected = {{ vibe: new Set(), activity: new Set(), times: new Set() }};
    const singleSelected = {{ departure: null, travel: null, margin: '5' }};

    // ─── Préremplissage au chargement ────────────────────────────────────────
    // Contexte : lancé depuis Telegram (initData présent) -> identité connue,
    // donc pas besoin de mail/téléphone. Depuis le web -> on les demande.
    const IS_TELEGRAM = !!tg.initData;

    window.addEventListener('load', async () => {{
      // 0. Masquer les champs de contact dans Telegram (identité déjà connue)
      if (IS_TELEGRAM) {{
        const cs = document.getElementById('contact-section');
        if (cs) cs.style.display = 'none';
      }}

      // 0b. Organisateur web pré-identifié (depuis /create) : nom + contact déjà connus
      if (PRESET_MID) {{
        const cs = document.getElementById('contact-section');
        if (cs) cs.style.display = 'none';
      }}
      if (PRESET_NAME) {{
        const nf = document.getElementById('display-name');
        if (nf) nf.value = PRESET_NAME;
        const ns = document.getElementById('name-section');
        if (ns) ns.style.display = 'none';
      }}

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
            item.style.cssText = 'padding:11px 14px;cursor:pointer;font-size:13.5px;border-bottom:1px solid #F1F1F1;line-height:1.4;';
            item.addEventListener('mouseover', () => item.style.background = '#F7F7F8');
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
        member_id:        PRESET_MID || (localStorage.getItem('okeder_member_' + EVENT_ID) || null),
        display_name:     name,
        notify_email:     document.getElementById('notify-email').value.trim() || null,
        notify_phone:     document.getElementById('notify-phone').value.trim() || null,
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
          // Lier ce navigateur au membre pour les engagements web (/result)
          if (data.member_id) {{
            try {{ localStorage.setItem('okeder_member_' + EVENT_ID, data.member_id); }} catch(e) {{}}
          }}
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

    async function declineInvite() {{
      if (!confirm("Tell the organiser you can't make it this time?")) return;
      const btn = document.getElementById('decline-btn');
      btn.disabled = true;
      btn.textContent = 'Sending…';
      try {{
        const res = await fetch(BACKEND_URL + '/mini-app/decline', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json', 'ngrok-skip-browser-warning': 'true' }},
          body: JSON.stringify({{
            init_data:    tg.initData || "",
            event_id:     EVENT_ID,
            member_id:    PRESET_MID || (localStorage.getItem('okeder_member_' + EVENT_ID) || null),
            display_name: document.getElementById('display-name').value.trim() || null,
          }}),
        }});
        if (res.ok) {{
          document.getElementById('form-view').style.display = 'none';
          document.getElementById('declined-view').style.display = 'flex';
          const redirectTo = NEXT_URL;
          if (redirectTo) setTimeout(() => window.location.href = redirectTo, 2000);
          else if (tg.initData) setTimeout(() => tg.close(), 2500);
        }} else {{
          btn.disabled = false;
          btn.textContent = "I can't make it — count me out";
          alert('Could not record. Please try again.');
        }}
      }} catch(e) {{
        btn.disabled = false;
        btn.textContent = "I can't make it — count me out";
        alert('Network error. Please try again.');
      }}
    }}
  </script>
</body>
</html>"""


@router.get("/mini-app/{event_id}", response_class=HTMLResponse)
async def serve_mini_app(event_id: str):
    public_url = os.environ.get("PUBLIC_URL", "http://localhost:8000")
    html = MINI_APP_HTML.format(event_id=event_id, backend_url=public_url)
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-store, no-cache, must-revalidate", "Pragma": "no-cache"},
    )


async def _ensure_group_membership(db: AsyncSession, event_id_str: str, member_id) -> None:
    """Ajoute le membre au groupe de l'event s'il n'y est pas déjà (best-effort)."""
    from app.models.event import Event
    from app.models.group import GroupMembership
    try:
        event_uuid = uuid.UUID(event_id_str)
    except ValueError:
        return
    ev = await db.execute(select(Event).where(Event.id == event_uuid))
    event = ev.scalar_one_or_none()
    if not event:
        return
    exists = await db.execute(
        select(GroupMembership).where(
            GroupMembership.group_id == event.group_id,
            GroupMembership.member_id == member_id,
        )
    )
    if not exists.scalar_one_or_none():
        db.add(GroupMembership(group_id=event.group_id, member_id=member_id, role="member"))


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
    member_id_in = (body.get("member_id") or "").strip() or None
    # NB : .get(k, "") renvoie None si la clé existe avec la valeur JSON null
    # (champs vides envoyés en null par le formulaire) -> sécuriser avec `or ""`.
    display_name = (body.get("display_name") or "").strip() or "Anonymous"
    notify_email = (body.get("notify_email") or "").strip() or None
    notify_phone = (body.get("notify_phone") or "").strip() or None

    # Identification via Telegram initData ou fallback nom
    user_data = _validate_telegram_init_data(init_data, settings.telegram_bot_token) if init_data else None

    member = None
    if user_data:
        tg_user_id = user_data.get("id")
        tg_name = ((user_data.get("first_name") or "") + " " + (user_data.get("last_name") or "")).strip()
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
            if notify_phone:
                member.phone = notify_phone
                member.whatsapp_notify = True
    else:
        # Web : réutiliser le membre connu (organisateur connecté ou invité déjà créé)
        if member_id_in:
            try:
                m_res = await db.execute(select(Member).where(Member.id == uuid.UUID(member_id_in)))
                member = m_res.scalar_one_or_none()
            except ValueError:
                member = None
            if member:
                if display_name and display_name != "Anonymous":
                    member.display_name = display_name
                if notify_email:
                    member.email = notify_email
                if notify_phone:
                    member.phone = notify_phone
                    member.whatsapp_notify = True
        if not member:
            member = Member(
                display_name=display_name,
                email=notify_email,
                phone=notify_phone,
                whatsapp_notify=bool(notify_phone),
            )
            db.add(member)
            await db.flush()

    # S'assurer que le membre appartient bien au groupe de l'event (web sans Telegram)
    await _ensure_group_membership(db, event_id_str, member.id)

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

    try:
        from app.services.synthesis import update_initiator_synthesis
        await update_initiator_synthesis(event_id_str, db)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"synthesis (submit): {e}")

    # Si next_url fourni dans le body → renvoyer l'URL de redirection
    # member_id : permet au navigateur de lier ses engagements ultérieurs (/result)
    next_url = body.get("next_url")
    return {"ok": True, "next_url": next_url, "member_id": str(member.id)}


@router.post("/mini-app/decline")
async def decline_invite(request: Request, db: AsyncSession = Depends(get_db)):
    """Le membre décline l'invitation (choix explicite, pas de préférences)."""
    from datetime import datetime, timezone

    from app.models.member import Member
    from app.models.preference import Preference

    body = await request.json()
    init_data    = body.get("init_data", "")
    event_id_str = body.get("event_id", "")
    member_id_in = (body.get("member_id") or "").strip() or None
    display_name = (body.get("display_name") or "").strip() or "Guest"

    try:
        event_uuid = uuid.UUID(event_id_str)
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="invalid event")

    user_data = _validate_telegram_init_data(init_data, settings.telegram_bot_token) if init_data else None

    member = None
    if user_data:
        tg_user_id = user_data.get("id")
        tg_name = ((user_data.get("first_name") or "") + " " + (user_data.get("last_name") or "")).strip()
        res = await db.execute(select(Member).where(Member.telegram_user_id == tg_user_id))
        member = res.scalar_one_or_none()
        if not member:
            member = Member(telegram_user_id=tg_user_id, display_name=tg_name or display_name)
            db.add(member)
            await db.flush()
    elif member_id_in:
        try:
            res = await db.execute(select(Member).where(Member.id == uuid.UUID(member_id_in)))
            member = res.scalar_one_or_none()
        except ValueError:
            member = None
    if not member:
        member = Member(display_name=display_name)
        db.add(member)
        await db.flush()

    await _ensure_group_membership(db, event_id_str, member.id)

    now = datetime.now(timezone.utc)
    pref_result = await db.execute(
        select(Preference).where(
            Preference.event_id == event_uuid,
            Preference.member_id == member.id,
        )
    )
    pref = pref_result.scalar_one_or_none()
    if pref:
        pref.declined = True
        pref.submitted_at = now
    else:
        db.add(Preference(event_id=event_uuid, member_id=member.id, declined=True, submitted_at=now))
    await db.commit()

    # Un refus peut faire atteindre le quorum aux autres → on revérifie
    try:
        from app.workers.jobs.collect_constraints import check_and_trigger_engine
        await check_and_trigger_engine(event_id_str, db)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"check_and_trigger_engine (decline): {e}")

    # Mise à jour de la synthèse temps réel de l'initiateur (Telegram)
    try:
        from app.services.synthesis import update_initiator_synthesis
        await update_initiator_synthesis(event_id_str, db)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"synthesis (decline): {e}")

    return {"ok": True, "member_id": str(member.id)}


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
