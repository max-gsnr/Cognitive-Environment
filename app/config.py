"""Environment configuration. Everything optional except the database."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass
class Settings:
    database_url: str = field(
        default_factory=lambda: _env("DATABASE_URL", "sqlite:///./orbit.db")
    )
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: _env("OPENAI_MODEL", "gpt-4o"))
    devin_api_key: str = field(default_factory=lambda: _env("DEVIN_API_KEY"))
    devin_api_base: str = field(
        default_factory=lambda: _env("DEVIN_API_BASE", "https://api.devin.ai/v1")
    )
    posthog_project_api_key: str = field(
        default_factory=lambda: _env("POSTHOG_PROJECT_API_KEY")
    )
    posthog_personal_api_key: str = field(
        default_factory=lambda: _env("POSTHOG_PERSONAL_API_KEY")
    )
    posthog_host: str = field(
        default_factory=lambda: _env("POSTHOG_HOST", "https://us.i.posthog.com")
    )
    posthog_project_id: str = field(default_factory=lambda: _env("POSTHOG_PROJECT_ID"))
    games_root: str = field(default_factory=lambda: _env("GAMES_ROOT", "games"))
    repo_url: str = field(default_factory=lambda: _env("REPO_URL", ""))
    cors_origins: str = field(
        default_factory=lambda: _env(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,*"
        )
    )

    @property
    def allowed_origins(self) -> list[str]:
        origins = (origin.strip() for origin in self.cors_origins.split(","))
        return [origin for origin in origins if origin]

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def devin_configured(self) -> bool:
        return bool(self.devin_api_key)


settings = Settings()
