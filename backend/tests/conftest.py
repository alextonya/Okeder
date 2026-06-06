"""
Configuration partagée des tests backend.

Certains modules (ex. app.utils.crypto) importent app.config.settings au
chargement, ce qui instancie Settings() — or `database_url` est un champ requis
sans valeur par défaut. On fournit donc des variables d'environnement factices
AVANT que pytest n'importe les modules de test, pour que l'import réussisse sans
base de données réelle. Les tests qui en ont besoin surchargent ensuite les
valeurs précises via monkeypatch.
"""
import os

# setdefault : ne jamais écraser une vraie valeur si l'environnement en fournit une.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/okeder_test"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_placeholder")
os.environ.setdefault("CLERK_WEBHOOK_SECRET", "whsec_placeholder")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST-token")


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures d'intégration (nécessitent une vraie base Postgres de test).
#
# Si la base n'est pas joignable (machine sans Docker/Postgres), les fixtures
# appellent pytest.skip() → les tests d'intégration sont SAUTÉS, mais la suite
# de tests "logique pure" reste verte. On ne casse jamais la CI faute d'infra.
# ─────────────────────────────────────────────────────────────────────────────
import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def sessionmaker_test():
    """Crée le schéma sur la base de test, fournit un sessionmaker, nettoie après."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import app.models  # noqa: F401 — enregistre tous les modèles sur Base.metadata
    from app.database import Base

    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:  # connexion impossible → pas d'infra
        await engine.dispose()
        pytest.skip(f"Base Postgres de test indisponible: {e}")

    sm = async_sessionmaker(engine, expire_on_commit=False)
    yield sm

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_member(sessionmaker_test):
    """Insère un Member de test et le retourne (détaché)."""
    from app.models.member import Member

    async with sessionmaker_test() as s:
        m = Member(display_name="Test User", clerk_user_id="clerk_test_user")
        s.add(m)
        await s.commit()
        await s.refresh(m)
        return m


@pytest_asyncio.fixture
async def client(sessionmaker_test, seeded_member):
    """
    AsyncClient ASGI sur l'app FastAPI, avec :
      - get_db surchargé → session de la base de test
      - get_current_member surchargé → le Member de test (auth contournée)
    """
    from httpx import ASGITransport, AsyncClient

    from app.database import get_db
    from app.deps import get_current_member
    from app.main import app

    async def _override_db():
        async with sessionmaker_test() as session:
            yield session

    async def _override_member():
        return seeded_member

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_member] = _override_member

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
