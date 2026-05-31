"""Ajoute la colonne 'location' à la table events (migration M3)."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text


async def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("❌ DATABASE_URL non définie")
        return

    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        # Vérifier si la colonne existe déjà
        result = await conn.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'events' AND column_name = 'location'
        """))
        if result.fetchone():
            print("✅ Colonne 'location' déjà présente")
        else:
            await conn.execute(text("ALTER TABLE events ADD COLUMN location TEXT"))
            print("✅ Colonne 'location' ajoutée à la table events")

    await engine.dispose()


asyncio.run(main())
