"""Script de création des tables — remplace Alembic pour le dev initial."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.ext.asyncio import create_async_engine
from app.database import Base
import app.models  # noqa — importe tous les modèles


async def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("❌ DATABASE_URL non définie")
        return

    print(f"📡 Connexion à la base de données...")
    engine = create_async_engine(url, echo=False)

    print("🔨 Création des tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    print("✅ Toutes les tables créées avec succès !")
    print("\nTables créées :")
    for table in Base.metadata.sorted_tables:
        print(f"  - {table.name}")


asyncio.run(main())
