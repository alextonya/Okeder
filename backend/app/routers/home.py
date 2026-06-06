"""
okeder.app — Site marketing complet (landing + pages entreprise).
"Clean modern light". Header + footer partagés via _pwa_ui.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.routers._pwa_ui import footer, header, shell

router = APIRouter()

SW = "<script>if('serviceWorker' in navigator){navigator.serviceWorker.register('/sw.js').catch(function(){});}</script>"


def _tile(ic, t, d):
    return f"<div class='tile'><div class='ic'>{ic}</div><h3>{t}</h3><p>{d}</p></div>"


# ─────────────────────────────  LANDING  ─────────────────────────────────────

LANDING = (
    header()
    + """
<header class="hero-xl">
  <span class="pill">✨ No app needed</span>
  <h1>Stop planning.<br><span style="color:var(--accent)">Start going.</span></h1>
  <p class="lead">Collect everyone's preferences in 30 seconds and get a real venue,
     date and time — picked automatically. Works on WhatsApp, Telegram, any device.</p>
  <div class="cta-center">
    <a class="btn btn-primary" href="/create">Plan my outing&nbsp;→</a>
    <a class="btn btn-ghost" href="/about">Our mission</a>
  </div>
  <p class="muted" style="margin-top:14px;font-size:13px">Free · No account · Works everywhere</p>
</header>

<section class="sec" id="how" style="border-top:none">
  <span class="kicker">How it works</span>
  <h2 style="margin-top:10px">Three steps, that's it.</h2>
  <div class="grid3">
    """ + _tile("1️⃣", "Create your outing", "Name it, say how many people you're inviting. Ten seconds.")
    + _tile("2️⃣", "Share the link", "One tap → WhatsApp, Telegram, SMS. Everyone answers in 30 seconds.")
    + _tile("3️⃣", "Get a real proposal", "Okeder finds the venue, date and time that works for everyone — and shows why.")
    + """
  </div>
</section>

<section class="sec" id="why">
  <span class="kicker">Why Okeder</span>
  <h2 style="margin-top:10px">Coordination is the problem.</h2>
  <div class="grid2">
    """ + _tile("📍", "Real venue", "A named place near everyone, with a Google Maps link.")
    + _tile("📅", "Best date", "The date that fits the most people, with each one's flexibility.")
    + _tile("⚖️", "Transparent", "Shows why — budget, vibe and travel time for everyone.")
    + _tile("🔒", "Private", "Each person's answers stay private. No one sees the others'.")
    + """
  </div>
</section>

<section class="sec">
  <span class="kicker">Works everywhere</span>
  <h2 style="margin-top:10px">No app to install.</h2>
  <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:22px">
    <span class="tag">📱 WhatsApp</span><span class="tag">✈️ Telegram</span>
    <span class="tag">💬 SMS</span><span class="tag">📧 Email</span><span class="tag">🔗 Any link</span>
  </div>
</section>

<section class="ctaband-full">
  <h2>Ready to skip the group-chat spiral?</h2>
  <p>Create your outing in ten seconds.</p>
  <div class="cta-center"><a class="btn btn-primary" href="/create">Plan an outing&nbsp;→</a></div>
</section>
"""
    + footer() + SW
)


# ─────────────────────────────  ABOUT  ──────────────────────────────────────

ABOUT = (
    header()
    + """
<div class="hero-xl">
  <span class="kicker">Our mission</span>
  <h1 style="margin-top:12px">Time with people,<br><span style="color:var(--accent)">not logistics.</span></h1>
  <p class="lead">We started Okeder because the hardest part of seeing friends isn't wanting to —
     it's the endless back-and-forth about where, when and how much.</p>
</div>

<section class="sec" style="border-top:none">
  <div class="grid3" style="margin-top:0">
    <div class="stat"><div class="n">5.4 hrs</div><div class="l">average time a group spends deciding on one outing</div></div>
    <div class="stat"><div class="n">30 sec</div><div class="l">what it takes with Okeder, per person</div></div>
    <div class="stat"><div class="n">0</div><div class="l">apps anyone needs to install</div></div>
  </div>
</section>

<section class="sec">
  <span class="kicker">What we believe</span>
  <h2 style="margin-top:10px">Our principles</h2>
  <div class="grid2">
    """ + _tile("🤝", "Togetherness is the product", "Every decision we make is judged by one question: does it get people in the same room faster?")
    + _tile("🪟", "Decisions should be transparent", "No black box. We always show why a place, date and price were chosen.")
    + _tile("🔐", "Privacy by default", "Individual preferences are never shared with the group. Ever.")
    + _tile("🌍", "Meet people where they are", "WhatsApp, Telegram, a browser — no install, no friction, no gatekeeping.")
    + """
  </div>
</section>

<section class="sec">
  <span class="kicker">The team</span>
  <h2 style="margin-top:10px">A small team with a big obsession.</h2>
  <p class="lead" style="max-width:640px">We're builders, designers and data people who got tired of dead group chats.
     We're backed by people who believe real-life connection is the next frontier — and we're hiring.</p>
  <div class="cta-center" style="justify-content:flex-start">
    <a class="btn btn-primary" href="/careers">See open roles&nbsp;→</a>
    <a class="btn btn-ghost" href="/contact">Get in touch</a>
  </div>
</section>
"""
    + footer() + SW
)


# ─────────────────────────────  CAREERS  ────────────────────────────────────

def _role(title, team, loc):
    return (
        f'<a class="role" href="/contact"><div><div style="font-weight:700">{title}</div>'
        f'<div class="meta">{team} · {loc}</div></div>'
        '<span class="muted" style="font-weight:700">→</span></a>'
    )


CAREERS = (
    header()
    + """
<div class="hero-xl">
  <span class="kicker">Careers</span>
  <h1 style="margin-top:12px">Help the world<br>spend more time together.</h1>
  <p class="lead">We're a remote-first team building the easiest way for groups to actually meet up.
     If that sounds like your kind of problem, we'd love to talk.</p>
</div>

<section class="sec" style="border-top:none">
  <span class="kicker">Why join</span>
  <h2 style="margin-top:10px">The good stuff</h2>
  <div class="grid3">
    """ + _tile("🌎", "Remote-first", "Work from anywhere. We sync a few hours a day and trust you with the rest.")
    + _tile("📈", "Real ownership", "Early team, meaningful equity, and your fingerprints on the whole product.")
    + _tile("🍝", "We practice what we build", "Team dinners, off-sites and a culture that actually likes hanging out.")
    + """
  </div>
</section>

<section class="sec">
  <span class="kicker">Open roles</span>
  <h2 style="margin-top:10px">We're hiring</h2>
  <div style="margin-top:8px">
    """ + _role("Senior Full-Stack Engineer", "Engineering", "Remote (EU)")
    + _role("Product Designer", "Design", "Remote (EU)")
    + _role("Growth Marketer", "Marketing", "Remote")
    + _role("Data / ML Engineer", "Engineering", "Remote (EU)")
    + """
  </div>
  <p class="muted" style="margin-top:20px">Don't see your role? We always make room for exceptional people —
     <a class="accent" style="text-decoration:none;font-weight:700" href="/contact">tell us what you'd build</a>.</p>
</section>
"""
    + footer() + SW
)


# ─────────────────────────────  AFFILIATES  ─────────────────────────────────

AFFILIATES = (
    header()
    + """
<div class="hero-xl">
  <span class="kicker">Affiliates &amp; partners</span>
  <h1 style="margin-top:12px">Earn by bringing<br>people together.</h1>
  <p class="lead">Venues, creators and communities: share Okeder, fill more tables,
     and earn on every plan that turns into a real outing.</p>
  <div class="cta-center"><a class="btn btn-primary" href="/contact">Become a partner&nbsp;→</a></div>
</div>

<section class="sec" style="border-top:none">
  <span class="kicker">How it works</span>
  <h2 style="margin-top:10px">Three steps to earn</h2>
  <div class="grid3">
    """ + _tile("🔗", "Get your link", "Sign up and receive a unique referral link and dashboard.")
    + _tile("📣", "Share it", "Drop it in your community, bio or to your guests. No code needed.")
    + _tile("💸", "Get paid", "Earn a commission whenever a referred group books an outing.")
    + """
  </div>
</section>

<section class="sec">
  <div class="grid3" style="margin-top:0">
    <div class="stat"><div class="n">20%</div><div class="l">revenue share on referred outings</div></div>
    <div class="stat"><div class="n">90 days</div><div class="l">cookie window on every referral</div></div>
    <div class="stat"><div class="n">Monthly</div><div class="l">payouts, no minimum threshold</div></div>
  </div>
  <div class="cta-center" style="justify-content:flex-start;margin-top:34px">
    <a class="btn btn-primary" href="/contact">Apply to the program&nbsp;→</a>
  </div>
</section>
"""
    + footer() + SW
)


# ─────────────────────────────  CONTACT  ────────────────────────────────────

CONTACT = (
    header()
    + """
<div class="prose">
  <span class="kicker">Contact</span>
  <h1 style="margin-top:12px">Let's talk.</h1>
  <p class="lead">Press, partnerships, support or just saying hi — we read everything.</p>

  <form id="cform" style="margin-top:30px" onsubmit="return sendMsg(event)">
    <div class="section"><label class="fld">Your name</label>
      <input id="c-name" type="text" placeholder="Your name" required></div>
    <div class="section"><label class="fld">Email</label>
      <input id="c-email" type="email" placeholder="you@email.com" required></div>
    <div class="section"><label class="fld">Message</label>
      <textarea id="c-msg" rows="5" placeholder="What's on your mind?" required></textarea></div>
    <button class="btn btn-primary" type="submit">Send message</button>
  </form>
  <div id="c-done" style="display:none;margin-top:18px" class="card accent center">
    <strong>Thanks!</strong> Your email app just opened — hit send and we'll get back to you shortly.
  </div>

  <h2>Other ways to reach us</h2>
  <p>General: <a class="accent" style="font-weight:700;text-decoration:none" href="mailto:hello@okeder.app">hello@okeder.app</a><br>
     Careers: <a class="accent" style="font-weight:700;text-decoration:none" href="mailto:jobs@okeder.app">jobs@okeder.app</a><br>
     Partners: <a class="accent" style="font-weight:700;text-decoration:none" href="mailto:partners@okeder.app">partners@okeder.app</a></p>
</div>

<script>
function sendMsg(e){
  e.preventDefault();
  var n=document.getElementById('c-name').value, em=document.getElementById('c-email').value, m=document.getElementById('c-msg').value;
  var body=encodeURIComponent(m + '\\n\\n— ' + n + ' (' + em + ')');
  window.location.href='mailto:hello@okeder.app?subject='+encodeURIComponent('Okeder — message from '+n)+'&body='+body;
  document.getElementById('cform').style.display='none';
  document.getElementById('c-done').style.display='block';
  return false;
}
</script>
"""
    + footer() + SW
)


# ─────────────────────────────  LEGAL  ──────────────────────────────────────

PRIVACY = (
    header()
    + """
<div class="prose">
  <span class="kicker">Legal</span>
  <h1 style="margin-top:12px">Privacy Policy</h1>
  <p class="lead">Last updated: June 2026. Plain-language summary below — the short version is: we collect as little as possible.</p>
  <h2>What we collect</h2>
  <p>To plan an outing we use the preferences you submit (vibe, budget, area, availability) and, optionally,
     an email or phone number so we can send you the proposal. That's it.</p>
  <h2>What we never do</h2>
  <ul>
    <li>We never show your individual answers to other members of your group.</li>
    <li>We never sell personal data.</li>
    <li>We never require an account to participate.</li>
  </ul>
  <h2>Your rights</h2>
  <p>You can ask us to access or delete your data at any time by emailing
     <a class="accent" style="font-weight:700;text-decoration:none" href="mailto:hello@okeder.app">hello@okeder.app</a>.</p>
  <p class="muted" style="margin-top:24px;font-size:14px">This page is a placeholder summary for demonstration and is not legal advice.</p>
</div>
"""
    + footer() + SW
)

TERMS = (
    header()
    + """
<div class="prose">
  <span class="kicker">Legal</span>
  <h1 style="margin-top:12px">Terms of Service</h1>
  <p class="lead">Last updated: June 2026. By using Okeder you agree to the following, in plain language.</p>
  <h2>Using Okeder</h2>
  <p>Okeder helps groups decide on outings. You agree to use it for lawful, good-faith coordination
     and not to abuse the service or other users.</p>
  <h2>No guarantees</h2>
  <p>Venue suggestions are recommendations based on the preferences submitted. Availability, pricing and
     bookings are subject to the venues themselves.</p>
  <h2>Contact</h2>
  <p>Questions about these terms? Email
     <a class="accent" style="font-weight:700;text-decoration:none" href="mailto:hello@okeder.app">hello@okeder.app</a>.</p>
  <p class="muted" style="margin-top:24px;font-size:14px">This page is a placeholder summary for demonstration and is not legal advice.</p>
</div>
"""
    + footer() + SW
)


# ─────────────────────────────  ROUTES  ─────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(content=shell("Okeder — Ok, Ordered!", LANDING))


@router.get("/about", response_class=HTMLResponse)
async def about():
    return HTMLResponse(content=shell("Okeder — Our mission", ABOUT))


@router.get("/careers", response_class=HTMLResponse)
async def careers():
    return HTMLResponse(content=shell("Okeder — Careers", CAREERS))


@router.get("/affiliates", response_class=HTMLResponse)
async def affiliates():
    return HTMLResponse(content=shell("Okeder — Affiliates", AFFILIATES))


@router.get("/contact", response_class=HTMLResponse)
async def contact():
    return HTMLResponse(content=shell("Okeder — Contact", CONTACT))


@router.get("/privacy", response_class=HTMLResponse)
async def privacy():
    return HTMLResponse(content=shell("Okeder — Privacy", PRIVACY))


@router.get("/terms", response_class=HTMLResponse)
async def terms():
    return HTMLResponse(content=shell("Okeder — Terms", TERMS))
