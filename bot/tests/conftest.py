"""
Config des tests du bot. bot.config.BotSettings exige TELEGRAM_BOT_TOKEN au
chargement → on fournit une valeur factice avant l'import des modules du bot.
"""
import os

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST-bot-token")
os.environ.setdefault("BACKEND_API_URL", "http://localhost:8000/v1")
