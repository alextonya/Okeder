"""Simulation du flow complet via l'API interne (header x-bot-token).
Crée un groupe + 3 membres parisiens, soumet leurs préférences -> quorum 60% -> moteur."""
import json
import urllib.request

BASE = "http://localhost:8000/v1/internal/telegram"
TOKEN = "8966795257:AAE5xs58cHAqPnCl9u-jvHFfGOSx9UPYWh4"
CHAT_ID = -1009000000001  # groupe de test


def call(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path, data=data, method="POST",
        headers={"Content-Type": "application/json", "x-bot-token": TOKEN},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        out = json.loads(r.read().decode())
    print(f"  POST {path} -> {out}")
    return out


print("1) register-group")
call("/register-group", {
    "telegram_chat_id": CHAT_ID,
    "chat_title": "Soirée test Paris",
    "initiator_telegram_id": 900001,
    "initiator_name": "Alice",
})

members = [
    {"tg": 900001, "name": "Alice", "vibe": ["casual"],  "activity": ["dinner"],
     "lat": 48.8532, "lng": 2.3692, "area": "Bastille, Paris",
     "budget": "25-45", "travel": 35, "prefs": "lively, cosy"},
    {"tg": 900002, "name": "Bob",   "vibe": ["cosy"],    "activity": ["dinner"],
     "lat": 48.8675, "lng": 2.3635, "area": "République, Paris",
     "budget": "30-55", "travel": 40, "prefs": "no seafood, quiet"},
    {"tg": 900003, "name": "Carol", "vibe": ["casual"],  "activity": ["drinks"],
     "lat": 48.8484, "lng": 2.3958, "area": "Nation, Paris",
     "budget": "20-40", "travel": 30, "prefs": "vegan, fun"},
]

print("2) register-member x3")
for m in members:
    call("/register-member", {
        "telegram_user_id": m["tg"],
        "display_name": m["name"],
        "telegram_chat_id": CHAT_ID,
    })

print("3) create-event (wizard_mode=False -> auto-publish)")
ev = call("/create-event", {
    "telegram_chat_id": CHAT_ID,
    "title": "Dîner entre potes",
    "location": "Paris",
    "wizard_mode": False,
})
event_id = ev["event_id"]
print("   event_id =", event_id)

print("4) submit-preferences (chaque soumission verifie le quorum)")
for i, m in enumerate(members, 1):
    body = {
        "event_id": event_id,
        "telegram_user_id": m["tg"],
        "display_name": m["name"],
        # champs bruts -> parsés en colonnes
        "budget_raw": m["budget"],
        "availability_raw": "friday evening",
        "preferences_raw": m["prefs"],
        # champs riches lus directement par le moteur (raw_answers = body)
        "vibe": m["vibe"],
        "activity": m["activity"],
        "departure_lat": m["lat"],
        "departure_lng": m["lng"],
        "departure_text": m["area"],
        "travel_time_max": m["travel"],
        "times": ["evening"],
        "preferred_date": "2026-06-05",
        "date_margin_days": 5,
    }
    print(f"   -- membre {i}/3 ({m['name']}) --")
    call("/submit-preferences", body)

print("\nDONE. event_id =", event_id)
