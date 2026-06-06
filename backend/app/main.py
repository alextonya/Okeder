from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.models import *  # noqa: F401, F403 — imports all models for Alembic
from app.routers import (
    auth,
    auth_pwa,
    commitments,
    events,
    groups,
    home,
    internal,
    miniapp,
    preferences,
    proposals,
    pwa,
    sw_route,
    webhooks,
    wizard,
    ws,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title="Okeder API",
    version="0.1.0",
    docs_url="/docs" if settings.is_dev else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev — restreindre en prod
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
app.include_router(groups.router, prefix="/v1/groups", tags=["groups"])
app.include_router(events.router, prefix="/v1/events", tags=["events"])
app.include_router(proposals.router, prefix="/v1", tags=["proposals"])
app.include_router(commitments.router, prefix="/v1", tags=["commitments"])
app.include_router(preferences.router, prefix="/v1", tags=["preferences"])
app.include_router(webhooks.router, prefix="/v1/webhooks", tags=["webhooks"])
app.include_router(wizard.router, prefix="/v1/wizard", tags=["wizard"])
app.include_router(ws.router, prefix="/ws", tags=["websocket"])
app.include_router(internal.router, prefix="/v1/internal/telegram", tags=["internal"])
app.include_router(miniapp.router, tags=["miniapp"])
app.include_router(pwa.router, tags=["pwa"])
app.include_router(sw_route.router, tags=["sw"])
app.include_router(home.router, tags=["home"])
app.include_router(auth_pwa.router, tags=["auth_pwa"])


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
