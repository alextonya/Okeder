"""
Okeder booking-agent — Browser Use + GPT-4o (remplace l'heuristique Playwright).

Même interface HTTP qu'avant :
  POST /book  →  {attempted, success, stopped_reason, confirmation, screenshot_b64, steps}
  GET  /health → {ok: true}

Garde-fous conservés (non négociables) :
  • Disclosé : nom = "<name> (via Okeder)" + message mentionnant l'assistant.
  • Arrêt si carte bancaire / captcha / login détectés.
  • Arrêt si auto_submit=False (rempli mais non soumis).

Nouveauté vs l'heuristique :
  • Le LLM (GPT-4o) lit le DOM + screenshot à chaque étape → gère n'importe quel
    widget sans sélecteur CSS codé en dur (TheFork popup, Zenchef, OpenTable, etc.)
"""
import base64
import json
import logging
import os
import re

from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("booking-agent")
app = FastAPI(title="Okeder booking-agent")


class BookReq(BaseModel):
    url: str
    party: int = 2
    date: str | None = None       # YYYY-MM-DD
    time: str | None = None       # HH:MM
    name: str = ""
    email: str = ""
    phone: str = ""
    message: str = ""
    auto_submit: bool = True


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/book")
async def book(req: BookReq):
    res = {
        "attempted": True,
        "success": False,
        "stopped_reason": None,
        "confirmation": "",
        "screenshot_b64": "",
        "steps": [],
    }

    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_api_key:
        res["stopped_reason"] = "error: OPENAI_API_KEY manquante"
        return res

    # Si auto_submit=False, on informe mais on ne réserve pas
    if not req.auto_submit:
        res["stopped_reason"] = "filled_not_submitted"
        res["steps"].append("auto_submit:disabled")
        return res

    try:
        from browser_use import Agent, Browser, BrowserConfig
        from langchain_openai import ChatOpenAI
        from playwright.async_api import async_playwright
    except ImportError as e:
        res["stopped_reason"] = f"error: dépendance manquante — {e}"
        return res

    # Disclosure : le nom et le message sont toujours marqués "via Okeder"
    disclosed_name = (req.name + " (via Okeder)").strip()
    disclosed_msg = (
        (req.message + "\n\n" if req.message else "")
        + "(Réservation préparée par l'assistant Okeder.)"
    ).strip()

    task = f"""
Tu es l'assistant de réservation d'Okeder. Réponds en français.

Va sur : {req.url}

Remplis le formulaire de réservation avec ces informations :
- Couverts / guests : {req.party}
- Date : {req.date or "non spécifiée"}
- Heure : {req.time or "non spécifiée"}
- Nom : {disclosed_name}
- Email : {req.email}
- Téléphone : {req.phone}
- Message / notes : {disclosed_msg}

RÈGLES ABSOLUES — respecte-les dans cet ordre de priorité :
1. Si un champ demande un numéro de carte bancaire, CVV, ou empreinte bancaire → ARRÊTE-TOI immédiatement. Retourne {{"status":"payment_required","steps":[],"confirmation":""}}.
2. Si un CAPTCHA interactif (puzzle, sélection d'images) apparaît → ARRÊTE-TOI. Retourne {{"status":"login_or_captcha","steps":[],"confirmation":""}}.
3. Si une connexion obligatoire / création de compte est exigée → ARRÊTE-TOI. Retourne {{"status":"login_or_captcha","steps":[],"confirmation":""}}.
4. Si aucun formulaire de réservation n'est trouvé après avoir navigué sur la page → Retourne {{"status":"no_form_found","steps":[],"confirmation":""}}.
5. Soumets le formulaire UNIQUEMENT si les règles 1-4 sont toutes respectées.
6. N'accepte aucune newsletter ni offre marketing.
7. Accepte les cookies si une bannière bloque l'accès au formulaire.

À la fin, retourne UN SEUL objet JSON sur une ligne :
{{"status":"success"|"payment_required"|"login_or_captcha"|"no_form_found"|"error","steps":["liste des actions effectuées"],"confirmation":"texte de confirmation affiché par le site si succès"}}
"""

    screenshot_b64 = ""
    try:
        llm = ChatOpenAI(
            model="gpt-4o",
            api_key=openai_api_key,
            temperature=0,
            max_tokens=1024,
        )

        browser_config = BrowserConfig(
            headless=os.getenv("AGENT_HEADLESS", "true").lower() == "true",
        )
        browser = Browser(config=browser_config)

        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
            max_actions_per_step=5,
        )

        try:
            history = await agent.run(max_steps=25)
            raw_result = history.final_result() or ""
        finally:
            await browser.close()

        # Screenshot final indépendant via Playwright
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    args=["--no-sandbox", "--disable-dev-shm-usage"]
                )
                page = await browser.new_page()
                await page.goto(req.url, wait_until="domcontentloaded", timeout=15000)
                screenshot_b64 = base64.b64encode(
                    await page.screenshot(full_page=False)
                ).decode()
                await browser.close()
        except Exception:
            pass

        res["screenshot_b64"] = screenshot_b64
        return _parse_result(raw_result, res)

    except Exception as exc:
        log.exception("book() failed")
        res["stopped_reason"] = f"error: {str(exc)[:300]}"
        res["screenshot_b64"] = screenshot_b64
        return res


def _parse_result(raw: str, res: dict) -> dict:
    """Parse la réponse JSON de l'agent et hydrate `res`."""
    match = re.search(r'\{[^{}]+\}', raw or "")
    if match:
        try:
            data = json.loads(match.group())
            status = data.get("status", "error")
            steps  = data.get("steps", [])
            conf   = data.get("confirmation", "")

            res["steps"] = steps if isinstance(steps, list) else [str(steps)]
            res["confirmation"] = conf

            if status == "success":
                res["success"] = True
            else:
                res["stopped_reason"] = status
            return res
        except json.JSONDecodeError:
            pass

    # Fallback mots-clés si JSON malformé
    raw_l = (raw or "").lower()
    for kw, reason in [
        ("payment_required", "payment_required"),
        ("login_or_captcha", "login_or_captcha"),
        ("no_form_found",    "no_form_found"),
        ("success",          None),
    ]:
        if kw in raw_l:
            if reason is None:
                res["success"] = True
            else:
                res["stopped_reason"] = reason
            return res

    res["stopped_reason"] = f"parse_error: {raw[:200]}"
    return res
