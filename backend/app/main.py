from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.models import *  # noqa: F401, F403 — imports all models for Alembic
from app.routers import (
    auth,
    commitments,
    events,
    groups,
    preferences,
    proposals,
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
    allow_origins=[settings.pwa_base_url],
    allow_credentials=True,
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


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
