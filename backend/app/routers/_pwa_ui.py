"""Design system partagé des pages PWA (Okeder) — "Clean modern light".
Blanc / encre / corail vif, Plus Jakarta Sans, minimal premium.
THEME et shell() sont des strings simples (pas de f-string) -> les accolades
CSS/JS sont littérales et ne cassent pas les .format()/f-string des pages.
"""

FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
)

THEME = """
:root{
  --bg:#FFFFFF; --ink:#0B0B0C; --muted:#6B7280; --line:#ECECEC; --soft:#F7F7F8;
  --accent:#FF4D2E; --accent-press:#E63E1F; --accent-soft:#FFF1ED;
  --ok:#0E9F6E; --warn:#C2410C; --radius:20px; --maxw:460px;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html{-webkit-text-size-adjust:100%}
body{
  background:var(--bg);color:var(--ink);min-height:100vh;line-height:1.5;
  font-family:'Plus Jakarta Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
}
.wrap{max-width:var(--maxw);margin:0 auto;padding:22px 20px 40px}
a{color:inherit}
/* Brand */
.brand{display:inline-flex;align-items:center;gap:9px;font-weight:800;font-size:19px;letter-spacing:-.03em}
.brand .dot{width:10px;height:10px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 4px var(--accent-soft)}
/* Type */
h1{font-size:clamp(32px,8.5vw,46px);line-height:1.04;font-weight:800;letter-spacing:-.035em}
h2{font-size:24px;font-weight:800;letter-spacing:-.025em}
h3{font-size:17px;font-weight:700;letter-spacing:-.01em}
.lead{color:var(--muted);font-size:17px;line-height:1.55;margin-top:14px}
.muted{color:var(--muted)}
.accent{color:var(--accent)}
.eyebrow{font-size:12px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
.divider{height:1px;background:var(--line);margin:22px 0}
/* Buttons */
.btn{display:flex;align-items:center;justify-content:center;gap:9px;width:100%;
  padding:17px 22px;border:none;border-radius:999px;font-family:inherit;font-size:16.5px;
  font-weight:700;cursor:pointer;text-decoration:none;letter-spacing:-.01em;
  transition:transform .08s ease,background .15s,opacity .15s,box-shadow .15s}
.btn:active{transform:scale(.98)}
.btn-primary{background:var(--accent);color:#fff;box-shadow:0 10px 26px -10px rgba(255,77,46,.6)}
.btn-primary:active{background:var(--accent-press)}
.btn-ghost{background:#fff;color:var(--ink);border:1.5px solid var(--line)}
.btn-dark{background:var(--ink);color:#fff}
.btn[disabled]{opacity:.45;cursor:default;box-shadow:none}
.btn.sm{padding:12px 18px;font-size:14.5px;width:auto}
/* Cards */
.card{border:1.5px solid var(--line);border-radius:var(--radius);padding:22px;background:#fff}
.card.soft{background:var(--soft);border-color:transparent}
.card.accent{background:var(--accent-soft);border-color:rgba(255,77,46,.18)}
/* Forms */
label.fld{display:block;font-size:13px;font-weight:700;margin:0 0 9px;letter-spacing:-.01em}
label.fld .opt{font-weight:500;color:var(--muted);text-transform:none;letter-spacing:0}
input,textarea,select{width:100%;padding:15px 16px;border:1.5px solid var(--line);border-radius:14px;
  background:#fff;color:var(--ink);font-size:16px;font-family:inherit;outline:none;
  transition:border-color .15s,box-shadow .15s}
input::placeholder,textarea::placeholder{color:#9CA3AF}
input:focus,textarea:focus,select:focus{border-color:var(--accent);box-shadow:0 0 0 4px rgba(255,77,46,.12)}
.row{display:flex;gap:10px}
.row>*{flex:1}
.hint{font-size:12.5px;color:var(--muted);margin-top:7px}
.req{color:var(--accent)}
.section{margin-bottom:24px}
.label{display:block;font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:11px}
/* Chips */
.chips{display:flex;flex-wrap:wrap;gap:9px}
.chip{padding:11px 16px;border-radius:999px;border:1.5px solid var(--line);background:#fff;
  color:var(--ink);font-size:14.5px;font-weight:600;cursor:pointer;user-select:none;
  transition:all .13s ease}
.chip:active{transform:scale(.96)}
.chip.on{background:var(--ink);border-color:var(--ink);color:#fff}
.chip.on.accent-sel{background:var(--accent);border-color:var(--accent)}
/* Misc */
.center{text-align:center}
.stack>*+*{margin-top:12px}
.pill{display:inline-flex;align-items:center;gap:7px;background:var(--accent-soft);
  color:var(--accent);border:1px solid rgba(255,77,46,.2);padding:7px 14px;border-radius:999px;
  font-size:13px;font-weight:700}
.tag{display:inline-flex;align-items:center;gap:6px;background:var(--soft);border:1px solid var(--line);
  border-radius:999px;padding:6px 12px;font-size:13px;font-weight:600;color:var(--muted)}
.linkbox{background:var(--soft);border:1px solid var(--line);border-radius:12px;
  padding:13px 14px;font-size:13px;color:var(--muted);word-break:break-all}
.progress{height:8px;background:var(--soft);border-radius:99px;overflow:hidden}
.progress>i{display:block;height:100%;background:var(--accent);border-radius:99px;transition:width .5s ease}
.metric{display:flex;align-items:center;gap:10px;padding:11px 0;font-size:14.5px;border-bottom:1px solid var(--line)}
.metric:last-child{border-bottom:none}
.dot-ok{color:var(--ok)} .dot-warn{color:var(--warn)}

/* ===== Marketing site (nav, footer, sections) ===== */
.nav{position:sticky;top:0;z-index:60;background:rgba(255,255,255,.82);backdrop-filter:saturate(180%) blur(12px);border-bottom:1px solid var(--line)}
.nav-in{max-width:1080px;margin:0 auto;display:flex;align-items:center;gap:16px;padding:13px 20px}
.nav .brand{text-decoration:none}
.nav-links{display:flex;flex:1;justify-content:center;gap:28px}
.nav-links a{color:var(--ink);text-decoration:none;font-weight:600;font-size:14.5px;opacity:.82}
.nav-links a:hover{opacity:1;color:var(--accent)}
.nav-right{display:flex;align-items:center;gap:12px;margin-left:auto}
.nav-toggle{display:none}
.nav-burger{display:none;flex-direction:column;gap:5px;cursor:pointer;padding:8px;margin-left:auto}
.nav-burger span{width:22px;height:2px;background:var(--ink);border-radius:2px;transition:.2s}
.site{max-width:1080px;margin:0 auto;padding:0 20px}
.hero-xl{text-align:center;padding:62px 20px 30px;max-width:780px;margin:0 auto}
.hero-xl h1{font-size:clamp(38px,9vw,66px)}
.hero-xl .lead{font-size:clamp(17px,4.4vw,21px);max-width:580px;margin:18px auto 0}
.cta-center{display:flex;gap:12px;justify-content:center;flex-wrap:wrap;margin-top:30px}
.cta-center .btn{width:auto;padding:16px 26px}
.kicker{font-size:13px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}
.sec{max-width:1080px;margin:0 auto;padding:56px 20px;border-top:1px solid var(--line)}
.sec h2{font-size:clamp(26px,5.4vw,40px);letter-spacing:-.03em}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:26px}
.grid2{display:grid;grid-template-columns:repeat(2,1fr);gap:16px;margin-top:26px}
.tile{border:1.5px solid var(--line);border-radius:18px;padding:22px}
.tile .ic{font-size:24px}
.tile h3{margin-top:12px}
.tile p{color:var(--muted);font-size:14px;margin-top:6px;line-height:1.55}
.stat .n{font-size:clamp(34px,7vw,46px);font-weight:800;letter-spacing:-.03em;color:var(--accent)}
.stat .l{color:var(--muted);font-size:14px;margin-top:4px}
.prose{max-width:680px;margin:0 auto;padding:46px 20px}
.prose h1{font-size:clamp(34px,8vw,52px)}
.prose .lead{margin-top:16px}
.prose h2{margin-top:34px;font-size:24px}
.prose p{color:#374151;font-size:16.5px;line-height:1.75;margin-top:14px}
.prose ul{margin:14px 0 0 2px;list-style:none}
.prose li{position:relative;padding-left:26px;color:#374151;font-size:16px;line-height:1.7;margin-top:10px}
.prose li::before{content:"";position:absolute;left:4px;top:11px;width:7px;height:7px;border-radius:50%;background:var(--accent)}
.role{display:flex;align-items:center;justify-content:space-between;gap:16px;border:1.5px solid var(--line);
  border-radius:16px;padding:18px 20px;margin-top:12px;text-decoration:none;color:inherit;transition:border-color .15s}
.role:hover{border-color:var(--ink)}
.role .meta{color:var(--muted);font-size:13.5px;margin-top:3px}
.ctaband-full{background:var(--ink);color:#fff;text-align:center;padding:60px 24px}
.ctaband-full h2{color:#fff}.ctaband-full p{color:#cbd5e1;margin-top:10px}
.footer{border-top:1px solid var(--line);background:var(--soft)}
.footer-in{max-width:1080px;margin:0 auto;padding:48px 20px 30px;display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr;gap:28px}
.footer .tag{background:transparent;border:none;padding:0;color:var(--muted);font-weight:500;display:block;margin-top:12px;max-width:240px;line-height:1.5}
.footer h4{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin-bottom:14px}
.footer-col a{display:block;color:var(--ink);text-decoration:none;font-size:14.5px;font-weight:500;opacity:.85;margin-bottom:11px}
.footer-col a:hover{color:var(--accent);opacity:1}
.footer-bottom{max-width:1080px;margin:0 auto;padding:18px 20px 40px;display:flex;align-items:center;
  justify-content:space-between;gap:12px;border-top:1px solid var(--line);color:var(--muted);font-size:13px;flex-wrap:wrap}
@media(max-width:760px){
  .nav-links{position:absolute;left:0;right:0;top:55px;flex-direction:column;justify-content:flex-start;
    gap:0;background:#fff;border-bottom:1px solid var(--line);padding:6px 20px 14px;display:none}
  .nav-links a{padding:15px 0;width:100%;border-bottom:1px solid var(--line);font-size:16px;opacity:1}
  .nav-toggle:checked~.nav-links{display:flex}
  .nav-burger{display:flex}
  .nav-right{display:none}
  .grid3,.grid2{grid-template-columns:1fr}
  .footer-in{grid-template-columns:1fr 1fr}
}
"""


def header(active: str = "") -> str:
    """Barre de navigation marketing partagée (responsive, burger mobile CSS-only)."""
    links = [("/#how", "How it works"), ("/about", "About"), ("/careers", "Careers"), ("/contact", "Contact")]
    items = "".join(f'<a href="{href}">{label}</a>' for href, label in links)
    return (
        '<div class="nav"><div class="nav-in">'
        '<a class="brand" href="/"><span class="dot"></span>Okeder</a>'
        '<input type="checkbox" id="nav-toggle" class="nav-toggle">'
        '<label class="nav-burger" for="nav-toggle"><span></span><span></span><span></span></label>'
        f'<div class="nav-links">{items}</div>'
        '<div class="nav-right"><a class="btn btn-primary sm" href="/create">Plan an outing</a></div>'
        '</div></div>'
    )


def footer() -> str:
    """Pied de page complet (sitemap entreprise)."""
    return (
        '<footer class="footer"><div class="footer-in">'
        '<div><div class="brand"><span class="dot"></span>Okeder</div>'
        '<span class="tag">Stop planning, start going. Group outings decided in 30 seconds — on any device.</span></div>'
        '<div class="footer-col"><h4>Product</h4>'
        '<a href="/create">Plan an outing</a><a href="/#how">How it works</a><a href="/#why">Why Okeder</a></div>'
        '<div class="footer-col"><h4>Company</h4>'
        '<a href="/about">About &amp; mission</a><a href="/careers">Careers</a>'
        '<a href="/affiliates">Affiliates</a><a href="/contact">Contact</a></div>'
        '<div class="footer-col"><h4>Legal</h4>'
        '<a href="/privacy">Privacy</a><a href="/terms">Terms</a></div>'
        '</div>'
        '<div class="footer-bottom"><span>© 2026 Okeder. All rights reserved.</span>'
        '<span>Made for people who&rsquo;d rather be together.</span></div>'
        '</footer>'
    )


def shell(title: str, body: str, head_extra: str = "", body_attrs: str = "") -> str:
    """Document HTML complet avec le thème partagé."""
    return (
        "<!DOCTYPE html><html lang=\"en\"><head>"
        "<meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,maximum-scale=1,viewport-fit=cover\">"
        "<meta name=\"theme-color\" content=\"#FFFFFF\">"
        f"<title>{title}</title>"
        "<link rel=\"manifest\" href=\"/manifest.json\">"
        + FONT_LINK
        + "<style>" + THEME + "</style>"
        + head_extra
        + "</head><body" + (" " + body_attrs if body_attrs else "") + ">"
        + body
        + "</body></html>"
    )
