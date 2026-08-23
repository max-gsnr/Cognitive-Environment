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
    # Lightweight auto-migration for SQLite local development
    if settings.database_url.startswith("sqlite"):
        from sqlalchemy import text
        with engine.connect() as conn:
            # Check attempts table
            result = conn.execute(text("PRAGMA table_info(attempts)")).fetchall()
            existing_cols = {row[1] for row in result}
            new_cols = [
                ("is_synthetic", "BOOLEAN DEFAULT 0"),
                ("cursor_velocity_px_s", "FLOAT"),
                ("jitter_ratio", "FLOAT"),
                ("idle_time_ms", "INTEGER"),
                ("distraction_events", "INTEGER"),
                ("focus_score", "FLOAT"),
            ]
            for col_name, col_type in new_cols:
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE attempts ADD COLUMN {col_name} {col_type}"))
            
            # Check subject_mastery table
            res_mastery = conn.execute(text("PRAGMA table_info(subject_mastery)")).fetchall()
            mastery_cols = {row[1] for row in res_mastery}
            if "decrement_credit" not in mastery_cols:
                conn.execute(text("ALTER TABLE subject_mastery ADD COLUMN decrement_credit FLOAT DEFAULT 0.0"))
            conn.commit()

    with SessionLocal() as session:
        for skill_id, label in SEEDED_SKILLS:
            if session.get(Skill, skill_id) is None:
                session.add(Skill(id=skill_id, label=label))
        session.commit()


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
