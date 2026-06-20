# Okeder — Handoff / Reprise de travail

> Document de reprise pour continuer le projet sur une autre session ou un autre PC.
> Dernière mise à jour : 2026-06-20.

## 1. C'est quoi Okeder
App de décision pour sorties de groupe. Flux : créer un événement → collecter les
préférences des membres → à **60 % de quorum** le moteur de décision tourne → choix
d'un lieu via **OpenStreetMap Overpass** → proposition → engagements → **réservation
(Okeder Concierge)**.

Monorepo (`okeder/`) :
- `backend/` — FastAPI. **Sert aussi la vraie PWA en HTML** (ce n'est PAS le Next.js).
- `bot/` — bot Telegram (python-telegram-bot, polling).
- `web/` — console admin Next.js (secondaire, Clerk).
- `booking-agent/` — **service agent navigateur Playwright** (réservation zéro-clic).
- `infra/` — docker-compose + `infra/env/*.env` (secrets, **gitignorés**).

La **vraie PWA produit** = pages servies par le backend : `home.py` (landing), `pwa.py`
(`/create /share /join /result /dashboard` + Concierge), `miniapp.py` (formulaire prefs,
partagé avec Telegram). Design system : `backend/app/routers/_pwa_ui.py`.

## 2. État actuel (2026-06-20)
**Tourne en local via Docker + tunnel cloudflared, branché sur Supabase + Upstash (cloud).**
PAS encore déployé sur Render (blueprint `render.yaml` prêt, voir `GUIDE_MISE_EN_LIGNE.md`).

Fait récemment :
- **Quick-wins correctness** : validation du niveau d'engagement (422), persistance des
  **ratings** (modèle `app/models/rating.py`), webhook Telegram durci, secrets retirés du code.
- **Okeder Concierge — réservation par cascade pilotée par la réservabilité** :
  - **Bookability dans le scoring** (`overpass_service.py`) : extraction des contacts OSM
    (tél/site/email/whatsapp/réservation) + terme 0.18 dans `_score_venue` → le moteur
    préfère les lieux faciles à réserver.
  - **Reservation Resolver** (`services/reservation_resolver.py` + `services/google_places.py`,
    **Google Places API New**) : résout l'identité exacte du resto (`place_id`, `reservable`,
    site) → **lien profond "fiche exacte"** (chemin 1-clic). Résultat caché dans
    `proposal.legitimacy_json["reservation"]`.
  - **Cascade** (`services/booking.py`) : canal primaire `reserve` (lien profond) puis
    tél / WhatsApp / email / TheFork ; message rédigé (OpenAI si clé, sinon template FR/EN) ;
    machine à états dans `confirmation_data["state"]`.
  - **Agent navigateur zéro-clic** (`booking-agent/`) : Playwright, iframe-aware, remplit
    couverts/date/heure/nom/email/tél/message, **auto-submit SAUF carte/captcha/login**,
    screenshot, disclosé. Appelé par `services/ai_booking_agent.py` (httpx) ; flag
    `ENABLE_AI_BOOKING_AGENT`.
  - **UI** `/result` : carte "Lock the table" → "Prepare reservation" → bouton "Reserve at X"
    + bouton "🤖 Let Okeder book it (beta)". Endpoints membre : `POST /pwa/result/{id}/book`,
    `/book/sent`, `/book/confirm`, `/autobook`.
  - **Cron** `booking_reminder` (arq, toutes les 30 min) — relance idempotente.
- **78 tests verts** (logique pure + intégration DB).

État réel de l'agent : fonctionnel + garde-fous OK. Le succès réel dépend du widget du
resto (formulaire inline → remplit ; widget externe type TheFork popup → `no_form_found`
→ repli propre sur le lien 1-clic). **Prochain levier : mode LLM** (voir §7).

## 3. Lancer en local (procédure complète)
Prérequis : Docker Desktop, et les fichiers `infra/env/*.env` présents (voir §5).

1. **Réveiller Supabase si en pause** (free tier) : app.supabase.com → projet
   `srkolgzpamdauvolzndb` → Restore (~1-3 min). Erreur typique si en pause :
   `tenant/user ... not found`.
2. **Démarrer la stack** (DB/Redis sont externes → `--no-deps`) :
   ```
   docker compose -f infra/docker-compose.yml up -d --no-deps backend worker bot booking-agent
   ```
3. **Tunnel public** (URL éphémère, change à chaque run) :
   ```
   cd backend && ./cloudflared.exe tunnel --url http://localhost:8000
   ```
   Copier l'URL `https://*.trycloudflare.com`.
4. **Mettre l'URL** dans `PUBLIC_URL=` de **`infra/env/backend.env` ET `infra/env/bot.env`**,
   puis **recréer backend + bot + worker** (⚠️ le worker construit les liens des
   notifications — ne pas l'oublier) :
   ```
   docker compose -f infra/docker-compose.yml up -d --no-deps --force-recreate backend bot worker
   ```
5. Ouvrir `<url>/create`, ou mentionner `@OkederBot` dans un groupe Telegram.

**Créer les tables** (1re fois sur une base neuve, idempotent) :
`docker exec infra-backend-1 python create_tables.py`

**Build de l'agent** (réseau mcr parfois flaky → builder classique qui réutilise l'image
de base locale) :
```
DOCKER_BUILDKIT=0 docker build -t infra-booking-agent ./booking-agent
docker compose -f infra/docker-compose.yml up -d --no-deps --force-recreate booking-agent
```

## 4. Tests
Suite complète dans l'image backend (Python 3.12) contre une Postgres jetable
(NE PAS lancer contre Supabase — les tests font create/drop) :
```
docker network create okeder-test 2>$null
docker run -d --name okeder-pg --network okeder-test -e POSTGRES_PASSWORD=test -e POSTGRES_USER=test -e POSTGRES_DB=okeder_test postgres:15-alpine
docker build -t okeder-backend-test ./backend
docker run --rm --network okeder-test -v "<abs>/backend:/app" -e DATABASE_URL=postgresql+asyncpg://test:test@okeder-pg:5432/okeder_test -e REDIS_URL=redis://localhost:6379/0 -e TELEGRAM_BOT_TOKEN=x:y -e STRIPE_WEBHOOK_SECRET=x -e CLERK_WEBHOOK_SECRET=x -e SESSION_SECRET=x okeder-backend-test python -m pytest tests/ -q
```
Les tests DB se SKIPPENT proprement si aucune Postgres n'est joignable (logique pure reste verte).

## 5. Secrets / variables (NON versionnés — à transférer à part)
Fichiers `infra/env/backend.env`, `infra/env/bot.env`, `infra/env/web.env` (gitignorés).
Clés attendues dans `backend.env` :
`DATABASE_URL` (Supabase Session Pooler IPv4), `REDIS_URL` (Upstash rediss://),
`PUBLIC_URL`, `APP_ENV`, `TELEGRAM_BOT_TOKEN`, `GOOGLE_MAPS_API_KEY` (Places API New activée +
restrictions clé OK), `ENABLE_AI_BOOKING_AGENT`, `BOOKING_AGENT_URL`, `OPENAI_API_KEY` (vide
pour l'instant), `SMTP_*` (Gmail), `VAPID_*`, `STRIPE_*` (vide), `FOURSQUARE_API_KEY` (mort).
`bot.env` : `BACKEND_API_URL=http://backend:8000/v1`, `TELEGRAM_USE_POLLING=true`, `PUBLIC_URL`.

⚠️ **Gotchas** :
- DB Supabase = **Session Pooler IPv4** (le host `db.<ref>.supabase.co` est IPv6-only → injoignable depuis Docker).
- Google : **Places API (New)** doit être activée + clé sans restriction bloquante (App restrictions=None).
- `playwright==1.47.0` pinné pour matcher l'image de base `mcr...:v1.47.0-jammy`.
- Piège Python : pas de `await` DANS une generator-expression (`any(x in await f() for ...)`).

## 6. Déploiement (à faire) — voir `GUIDE_MISE_EN_LIGNE.md`
Render via `render.yaml` (backend web + worker + bot). À durcir avant : URL bot/worker
pointant sur okeder.com avant DNS (amorçage), variables manquantes (Eventbrite/WhatsApp/Clerk),
ajouter le service `booking-agent`, VAPID email `.app` vs `.com`.

## 7. Next steps / idées
1. **Agent en mode LLM** (gros gain) : avec `OPENAI_API_KEY`, faire piloter `booking-agent`
   par un LLM qui lit le DOM/la capture → gère bien plus de widgets que l'heuristique actuelle.
2. Déployer sur Render (+ ajouter le service booking-agent au blueprint).
3. Agent **vocal** pour les restos sans widget web (téléphone seul, fréquent en FR).
4. Jalons restants : Stripe payment-failed (M4), webhook Eventbrite (M5), profil
   comportemental depuis les ratings (M6).

## 8. Reprise sur un AUTRE PC — voir la section dédiée que l'assistant t'a donnée
En résumé : récupérer le code (Git/remote), transférer les `infra/env/*.env` à part
(jamais dans Git), réinstaller Docker, suivre §3. Le fichier de mémoire de l'assistant
(`~/.claude/.../memory/`) est local à la machine — ce HANDOFF.md est la source de vérité
portable.
