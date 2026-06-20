"""
Okeder booking-agent — service navigateur (Playwright) qui REMPLIT le formulaire
de réservation d'un resto à partir du proposal, et le valide (sauf paiement).

Garde-fous (non négociables) :
  • Disclosé : nom = "<name> (via Okeder)" + message mentionnant l'assistant.
  • S'arrête si saisie de CARTE / captcha / login → stopped_reason → l'app retombe
    sur le lien pré-rempli (jamais de réservation en aveugle).
  • Best-effort heuristique, iframe-aware (TheFork/Zenchef sont souvent en iframe).
    Marche sur les widgets standards, échoue proprement ailleurs.

POST /book → {attempted, success, stopped_reason, confirmation, screenshot_b64, steps}
"""
import base64
import logging

from fastapi import FastAPI
from playwright.async_api import async_playwright
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("booking-agent")
app = FastAPI(title="Okeder booking-agent")

# Marqueurs de SAISIE DE CARTE uniquement (resserrés pour éviter les faux positifs
# sur un simple mot "paiement" en pied de page).
CARD = ["card number", "numéro de carte", "credit card", "carte de crédit",
        "carte bancaire", "cvv", "cvc", "expiry", "date d'expiration",
        "empreinte bancaire", "card holder", "titulaire de la carte"]
BLOCK = ["captcha", "recaptcha", "hcaptcha", "not a robot", "sign in", "log in",
         "connectez-vous", "créer un compte", "connexion requise"]
RESERVE_WORDS = ["réserver une table", "réserver", "reserve a table", "book a table",
                 "reservation", "réservation", "prendre une table", "booking"]
COOKIE_WORDS = ["tout accepter", "accepter", "j'accepte", "accept all", "accept", "got it"]
SUBMIT_WORDS = ["confirmer la réservation", "valider la réservation", "réserver maintenant",
                "confirmer", "valider", "réserver", "book now", "confirm", "finaliser"]
CONFIRM_WORDS = ["confirmée", "confirmed", "réservation enregistrée", "merci de votre réservation",
                 "votre réservation", "your reservation", "booking confirmed", "à bientôt"]


class BookReq(BaseModel):
    url: str
    party: int = 2
    date: str | None = None      # YYYY-MM-DD
    time: str | None = None      # HH:MM
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
    res = {"attempted": True, "success": False, "stopped_reason": None,
           "confirmation": "", "screenshot_b64": "", "steps": []}
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
        ctx = await browser.new_context(
            locale="fr-FR",
            user_agent="Mozilla/5.0 (compatible; OkederBookingAssistant/1.0)",
        )
        page = await ctx.new_page()
        try:
            await page.goto(req.url, wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(2500)
            await _click_text(page, COOKIE_WORDS, res, "cookies")
            await _click_text(page, RESERVE_WORDS, res, "open")
            await page.wait_for_timeout(2000)

            txt = await _all_text(page)
            if any(b in txt for b in BLOCK):
                return _stop(res, "login_or_captcha", await _shot(page))

            # Remplit dans la 1ère "scope" (page ou iframe) qui a un formulaire
            scope, filled = await _fill_best_scope(page, req, res)
            if not filled:
                return _stop(res, "no_form_found", await _shot(page))
            txt2 = await _all_text(page)
            if any(c in txt2 for c in CARD):
                return _stop(res, "payment_required", await _shot(page))

            if req.auto_submit:
                clicked = await _click_text(scope, SUBMIT_WORDS, res, "submit")
                await page.wait_for_timeout(3000)
                after = await _all_text(page)
                if any(c in after for c in CARD):
                    return _stop(res, "payment_required", await _shot(page))
                conf = next((w for w in CONFIRM_WORDS if w in after), "")
                res["success"] = bool(conf) or clicked
                res["confirmation"] = conf
            else:
                res["stopped_reason"] = "filled_not_submitted"

            res["screenshot_b64"] = await _shot(page)
            return res
        except Exception as e:
            log.exception("book() failed")
            return _stop(res, "error: " + str(e)[:200], await _shot(page))
        finally:
            await browser.close()


def _stop(res, reason, shot):
    res["stopped_reason"] = reason
    res["screenshot_b64"] = shot
    return res


async def _all_text(page) -> str:
    """Texte de la page + de toutes les iframes (minuscule)."""
    parts = []
    for fr in page.frames:
        try:
            parts.append(await fr.inner_text("body", timeout=2000))
        except Exception:
            continue
    return " ".join(parts).lower()


async def _shot(page) -> str:
    try:
        return base64.b64encode(await page.screenshot(full_page=False)).decode()
    except Exception:
        return ""


async def _click_text(scope, words, res, label) -> bool:
    for w in words:
        for sel in (f"button:has-text(\"{w}\")", f"a:has-text(\"{w}\")",
                    f"[role=button]:has-text(\"{w}\")"):
            try:
                el = scope.locator(sel).first
                if await el.count() and await el.is_visible():
                    await el.click(timeout=3000)
                    res["steps"].append(f"{label}:{w}")
                    return True
            except Exception:
                continue
    return False


async def _fill_field(scope, selectors, value, res, label) -> bool:
    if not value:
        return False
    for sel in selectors:
        try:
            el = scope.locator(sel).first
            if await el.count() and await el.is_visible():
                await el.fill(str(value), timeout=2500)
                res["steps"].append(f"fill:{label}")
                return True
        except Exception:
            continue
    return False


async def _select_party(scope, party, res) -> bool:
    try:
        selects = scope.locator("select")
        n = await selects.count()
        for i in range(min(n, 8)):
            s = selects.nth(i)
            try:
                opts = await s.locator("option").all_inner_texts()
            except Exception:
                opts = []
            for needle in (f"{party} personne", f"{party} pers", f"{party} guest",
                           f"{party} people", f"{party} couvert", str(party)):
                for o in opts:
                    if needle.lower() in o.lower():
                        try:
                            await s.select_option(label=o, timeout=2000)
                            res["steps"].append("fill:party(select)")
                            return True
                        except Exception:
                            pass
    except Exception:
        pass
    return await _fill_field(
        scope,
        ["input[name*=party i]", "input[name*=cover i]", "input[name*=guest i]",
         "input[aria-label*=personne i]", "input[aria-label*=couvert i]", "input[type=number]"],
        party, res, "party(input)",
    )


async def _fill_scope(scope, req, res) -> bool:
    filled = False
    filled |= await _select_party(scope, req.party, res)
    if req.date:
        filled |= await _fill_field(scope, ["input[type=date]", "input[name*=date i]",
                                            "input[placeholder*=date i]"], req.date, res, "date")
    if req.time:
        filled |= await _fill_field(scope, ["input[type=time]", "input[name*=time i]",
                                            "input[name*=heure i]"], req.time, res, "time")
    name = (req.name + " (via Okeder)").strip()
    await _fill_field(scope, ["input[name*=name i]", "input[autocomplete=name]", "input[name*=nom i]",
                              "input[placeholder*=nom i]", "input[placeholder*=name i]"], name, res, "name")
    await _fill_field(scope, ["input[type=email]", "input[name*=email i]",
                              "input[autocomplete=email]"], req.email, res, "email")
    await _fill_field(scope, ["input[type=tel]", "input[name*=phone i]", "input[name*=tel i]",
                              "input[autocomplete=tel]"], req.phone, res, "phone")
    msg = (req.message + "\n\n(Réservation préparée par l'assistant Okeder.)").strip()
    await _fill_field(scope, ["textarea[name*=message i]", "textarea[name*=note i]",
                              "textarea[name*=comment i]", "textarea"], msg, res, "message")
    return filled


async def _fill_best_scope(page, req, res):
    """Essaie la page puis chaque iframe ; renvoie (scope, filled) au 1er succès."""
    scopes = [page] + [fr for fr in page.frames if fr != page.main_frame]
    for scope in scopes:
        try:
            if await _fill_scope(scope, req, res):
                return scope, True
        except Exception:
            continue
    return page, False
