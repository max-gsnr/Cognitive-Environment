"""Orbit's FastAPI app. Generated games are served as static files from /games."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import init_db
from app.routers import attempts, audit_log, demo, games, intake, profiles


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="Orbit", version="0.1.0", lifespan=lifespan)

# There is no auth here, so the browser origin check is the only thing standing
# between a stranger's page and a child's roster. Keep it to known origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)

app.include_router(intake.router)
app.include_router(profiles.router)
app.include_router(attempts.router)
app.include_router(games.router)
app.include_router(demo.router)
app.include_router(audit_log.router)


os.makedirs(settings.games_root, exist_ok=True)
app.mount(
    "/games", StaticFiles(directory=settings.games_root, html=True), name="games"
)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "openai_configured": settings.openai_configured,
        "devin_configured": settings.devin_configured,
        "posthog_configured": bool(settings.posthog_project_api_key),
        "database": settings.database_url.split("://", 1)[0],
    }
