"""
Client HTTP partagé pour les appels du bot vers le backend.
Ajoute automatiquement X-Bot-Token pour l'auth interne.
"""
from contextlib import asynccontextmanager

import httpx

from bot.config import settings


@asynccontextmanager
async def backend_client():
    async with httpx.AsyncClient(
        base_url=settings.backend_api_url,
        headers={"X-Bot-Token": settings.telegram_bot_token},
        timeout=10.0,
    ) as client:
        yield client
