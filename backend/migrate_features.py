"""Migration: colonnes comptes/synthese + table otp_codes (idempotent)."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import Base
import app.models  # noqa — importe tous les modeles (dont OtpCode)

ALTERS = [
    "ALTER TABLE members ADD COLUMN IF NOT EXISTS email_verified_at timestamptz",
    "ALTER TABLE events  ADD COLUMN IF NOT EXISTS initiator_summary_chat_id bigint",
    "ALTER TABLE events  ADD COLUMN IF NOT EXISTS initiator_summary_msg_id  bigint",
]


async def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL non definie")
        return
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        for stmt in ALTERS:
            await conn.execute(text(stmt))
            print("OK:", stmt)
        # cree les tables manquantes (otp_codes), n'altere pas l'existant
        await conn.run_sync(Base.metadata.create_all)
        print("OK: create_all (otp_codes)")
    await engine.dispose()
    print("Migration terminee.")


asyncio.run(main())
