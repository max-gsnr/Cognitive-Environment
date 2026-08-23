"""Session and engine wiring. Postgres when DATABASE_URL says so, SQLite otherwise."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base, Skill

connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

SEEDED_SKILLS = [("addition", "Addition"), ("subtraction", "Subtraction")]


def init_db() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        for skill_id, label in SEEDED_SKILLS:
            if session.get(Skill, skill_id) is None:
                session.add(Skill(id=skill_id, label=label))
        session.commit()


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
