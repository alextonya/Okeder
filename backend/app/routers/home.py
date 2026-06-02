"""
okeder.app — Landing page principale.
Mobile-first, claire, CTA vers /create.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="Okeder — Stop planning, start going. Group outings without the back-and-forth.">
  <title>Okeder — Ok, Ordered!</title>
  <link rel="manifest" href="/manifest.json">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg:       #0a0f1e;
      --surface:  #111827;
      --border:   rgba(255,255,255,0.07);
      --text:     #f1f5f9;
      --muted:    #64748b;
      --accent:   #6366f1;
      --accent2:  #818cf8;
      --green:    #10b981;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      overflow-x: hidden;
    }

    /* ── Nav ── */
    nav {
      display: flex; align-items: center; justify-content: space-between;
      padding: 20px 24px;
      border-bottom: 1px solid var(--border);
    }
    .logo { font-size: 20px; font-weight: 800; letter-spacing: -.5px; }
    .logo span { color: var(--accent2); }
    .nav-cta {
      background: var(--accent); color: white; border: none;
      padding: 10px 20px; border-radius: 10px; font-weight: 600;
      font-size: 14px; cursor: pointer; text-decoration: none;
      transition: opacity .15s;
    }
    .nav-cta:active { opacity: .8; }

    /* ── Hero ── */
    .hero {
      text-align: center;
      padding: 64px 24px 48px;
    }
    .badge {
      display: inline-flex; align-items: center; gap: 6px;
      background: rgba(99,102,241,.15); border: 1px solid rgba(99,102,241,.3);
      color: var(--accent2); padding: 6px 14px; border-radius: 20px;
      font-size: 13px; font-weight: 600; margin-bottom: 28px;
    }
    h1 {
      font-size: clamp(32px, 8vw, 56px);
      font-weight: 900;
      line-height: 1.1;
      letter-spacing: -1.5px;
      margin-bottom: 20px;
    }
    h1 em { color: var(--accent2); font-style: normal; }
    .hero-sub {
      font-size: clamp(16px, 4vw, 20px);
      color: var(--muted);
      line-height: 1.6;
      max-width: 480px;
      margin: 0 auto 36px;
    }
    .hero-cta {
      display: inline-flex; align-items: center; gap: 10px;
      background: var(--accent); color: white; text-decoration: none;
      padding: 18px 32px; border-radius: 16px;
      font-size: 18px; font-weight: 700;
      box-shadow: 0 8px 32px rgba(99,102,241,.4);
      transition: transform .15s, box-shadow .15s;
    }
    .hero-cta:active { transform: scale(.97); }
    .hero-note { margin-top: 14px; font-size: 13px; color: var(--muted); }

    /* ── How it works ── */
    .section { padding: 48px 24px; }
    .section-label {
      text-align: center; font-size: 12px; font-weight: 700;
      letter-spacing: .1em; text-transform: uppercase;
      color: var(--accent2); margin-bottom: 16px;
    }
    .section h2 {
      text-align: center; font-size: clamp(24px, 5vw, 36px);
      font-weight: 800; letter-spacing: -.5px; margin-bottom: 40px;
    }

    .steps { display: flex; flex-direction: column; gap: 16px; max-width: 480px; margin: 0 auto; }
    .step {
      display: flex; align-items: flex-start; gap: 16px;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 16px; padding: 20px;
    }
    .step-num {
      width: 40px; height: 40px; border-radius: 12px; flex-shrink: 0;
      background: rgba(99,102,241,.2); color: var(--accent2);
      display: flex; align-items: center; justify-content: center;
      font-size: 18px; font-weight: 800;
    }
    .step-title { font-size: 16px; font-weight: 700; margin-bottom: 4px; }
    .step-desc { font-size: 14px; color: var(--muted); line-height: 1.5; }

    /* ── Why ── */
    .why-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; max-width: 480px; margin: 0 auto; }
    .why-card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 14px; padding: 20px;
    }
    .why-icon { font-size: 28px; margin-bottom: 10px; }
    .why-title { font-size: 14px; font-weight: 700; margin-bottom: 6px; }
    .why-desc { font-size: 13px; color: var(--muted); line-height: 1.5; }

    /* ── Channels ── */
    .channels {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 20px; padding: 28px; max-width: 480px; margin: 0 auto;
      text-align: center;
    }
    .channels h3 { font-size: 18px; font-weight: 700; margin-bottom: 8px; }
    .channels p { font-size: 14px; color: var(--muted); margin-bottom: 20px; }
    .channel-icons { display: flex; justify-content: center; gap: 16px; flex-wrap: wrap; }
    .channel-pill {
      display: flex; align-items: center; gap: 8px;
      background: rgba(255,255,255,.05); border: 1px solid var(--border);
      border-radius: 20px; padding: 8px 14px; font-size: 14px; font-weight: 600;
    }

    /* ── CTA bottom ── */
    .cta-bottom {
      text-align: center; padding: 48px 24px 64px;
      background: linear-gradient(to bottom, transparent, rgba(99,102,241,.08));
    }
    .cta-bottom h2 { font-size: clamp(24px,5vw,36px); font-weight: 800; margin-bottom: 12px; }
    .cta-bottom p { color: var(--muted); margin-bottom: 28px; }
    .cta-bottom a {
      display: inline-flex; align-items: center; gap: 10px;
      background: var(--accent); color: white; text-decoration: none;
      padding: 18px 36px; border-radius: 16px;
      font-size: 18px; font-weight: 700;
    }

    /* ── Footer ── */
    footer {
      text-align: center; padding: 24px;
      border-top: 1px solid var(--border);
      font-size: 13px; color: var(--muted);
    }
    footer a { color: var(--accent2); text-decoration: none; }
  </style>
</head>
<body>

<!-- Nav -->
<nav>
  <div class="logo">ok<span>eder</span></div>
  <a class="nav-cta" href="/create">Plan an outing →</a>
</nav>

<!-- Hero -->
<section class="hero">
  <div class="badge">✨ No app needed</div>
  <h1>Stop planning.<br><em>Start going.</em></h1>
  <p class="hero-sub">
    Collect everyone's preferences in 30 seconds,
    get a real venue proposal — automatically.
    Works on WhatsApp, Telegram, or any device.
  </p>
  <a class="hero-cta" href="/create">
    🎯 Plan my outing
  </a>
  <p class="hero-note">Free · No account needed · Works everywhere</p>
</section>

<!-- How it works -->
<section class="section">
  <p class="section-label">How it works</p>
  <h2>3 steps, that's it.</h2>
  <div class="steps">
    <div class="step">
      <div class="step-num">1</div>
      <div>
        <div class="step-title">Create your outing</div>
        <div class="step-desc">Give it a name, say how many people you're inviting. Takes 10 seconds.</div>
      </div>
    </div>
    <div class="step">
      <div class="step-num">2</div>
      <div>
        <div class="step-title">Share the link</div>
        <div class="step-desc">One tap → native share sheet → WhatsApp, Telegram, SMS, email. Everyone fills their preferences in 30s.</div>
      </div>
    </div>
    <div class="step">
      <div class="step-num">3</div>
      <div>
        <div class="step-title">Get a real proposal</div>
        <div class="step-desc">Okeder finds the best venue, date and time that works for everyone — and shows why.</div>
      </div>
    </div>
  </div>
</section>

<!-- Why Okeder -->
<section class="section" style="padding-top:0">
  <p class="section-label">Why Okeder</p>
  <h2>Because coordination is the problem.</h2>
  <div class="why-grid">
    <div class="why-card">
      <div class="why-icon">📍</div>
      <div class="why-title">Real venue</div>
      <div class="why-desc">A named bar or restaurant near everyone, with a direct Google Maps link.</div>
    </div>
    <div class="why-card">
      <div class="why-icon">📅</div>
      <div class="why-title">Best date</div>
      <div class="why-desc">Finds the date that works for the most people, with your flexibility margin.</div>
    </div>
    <div class="why-card">
      <div class="why-icon">⚖️</div>
      <div class="why-title">Transparent</div>
      <div class="why-desc">Shows why that venue was chosen — budget, vibe, travel time for everyone.</div>
    </div>
    <div class="why-card">
      <div class="why-icon">🔒</div>
      <div class="why-title">Private</div>
      <div class="why-desc">Each person's preferences are private. No one sees what others chose.</div>
    </div>
  </div>
</section>

<!-- Works everywhere -->
<section class="section" style="padding-top:0">
  <div class="channels">
    <h3>Works on every channel</h3>
    <p>No app to install. Share the link however you want.</p>
    <div class="channel-icons">
      <div class="channel-pill">📱 WhatsApp</div>
      <div class="channel-pill">✈️ Telegram</div>
      <div class="channel-pill">💬 SMS</div>
      <div class="channel-pill">📧 Email</div>
      <div class="channel-pill">🔗 Any link</div>
    </div>
  </div>
</section>

<!-- Bottom CTA -->
<section class="cta-bottom">
  <h2>Ready to stop the group chat spiral?</h2>
  <p>Create your outing in 10 seconds.</p>
  <a href="/create">🎯 Plan an outing →</a>
</section>

<!-- Footer -->
<footer>
  <p>© 2026 Okeder · <a href="/create">Plan an outing</a></p>
</footer>

<script>
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
</script>

</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(content=HTML)
