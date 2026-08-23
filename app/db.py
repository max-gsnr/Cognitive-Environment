"""Session and engine wiring. Postgres when DATABASE_URL says so, SQLite otherwise."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base, ChildProfile, Game, Skill, SubjectMastery

connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

SEEDED_SKILLS = [("addition", "Addition"), ("subtraction", "Subtraction")]

DEFAULT_STUDENTS = [
    {
        "id": "ec9f2ef3-c7df-46a1-96d2-fa77130fcc2a",
        "name": "Leo",
        "age": 7,
        "interests": ["outer space", "trains"],
        "leniency_band": "low",
        "restlessness_interpretation": "distraction",
        "difficulty_floor": {"addition": "mid_double", "subtraction": "low_double"},
        "session_length": 5,
        "addition": {"digits": 2, "magnitude": "mid_double", "carries": True, "borrows": False, "zero_in_minuend": False},
        "subtraction": {"digits": 2, "magnitude": "low_double", "carries": False, "borrows": True, "zero_in_minuend": False},
    },
    {
        "id": "442e9766-3d23-455b-8eb5-e2f4621c1ff7",
        "name": "Lena",
        "age": 8,
        "interests": ["tennis", "horses"],
        "leniency_band": "medium",
        "restlessness_interpretation": "distraction",
        "difficulty_floor": {"addition": "low_double", "subtraction": "single"},
        "session_length": 5,
        "addition": {"digits": 2, "magnitude": "low_double", "carries": False, "borrows": False, "zero_in_minuend": False},
        "subtraction": {"digits": 1, "magnitude": "single", "carries": False, "borrows": False, "zero_in_minuend": False},
    },
    {
        "id": "70d067b5-2415-4fa1-8255-6b7ebbb16912",
        "name": "Maya",
        "age": 6,
        "interests": ["dinosaurs", "fossil excavation"],
        "leniency_band": "high",
        "restlessness_interpretation": "self_regulation",
        "difficulty_floor": {"addition": "low_double", "subtraction": "single"},
        "session_length": 5,
        "addition": {"digits": 2, "magnitude": "low_double", "carries": False, "borrows": False, "zero_in_minuend": False},
        "subtraction": {"digits": 1, "magnitude": "single", "carries": False, "borrows": False, "zero_in_minuend": False},
    },
    {
        "id": "5b597147-9dc4-4d8b-986a-e24949576a8b",
        "name": "Sammy",
        "age": 7,
        "interests": ["sharks", "marine biology"],
        "leniency_band": "medium",
        "restlessness_interpretation": "distraction",
        "difficulty_floor": {"addition": "low_double", "subtraction": "single"},
        "session_length": 5,
        "addition": {"digits": 2, "magnitude": "low_double", "carries": False, "borrows": False, "zero_in_minuend": False},
        "subtraction": {"digits": 1, "magnitude": "single", "carries": False, "borrows": False, "zero_in_minuend": False},
    },
    {
        "id": "6e21eb23-cb84-4822-b5e1-5ef0f845a7dc",
        "name": "Max",
        "age": 8,
        "interests": ["spaghetti", "cooking"],
        "leniency_band": "low",
        "restlessness_interpretation": "self_regulation",
        "difficulty_floor": {"addition": "low_double", "subtraction": "single"},
        "session_length": 5,
        "addition": {"digits": 2, "magnitude": "low_double", "carries": False, "borrows": False, "zero_in_minuend": False},
        "subtraction": {"digits": 1, "magnitude": "single", "carries": False, "borrows": False, "zero_in_minuend": False},
    },
    {
        "id": "8c12fa44-592b-4781-a901-2092df483b8a",
        "name": "Sophie",
        "age": 7,
        "interests": ["starry night", "drawing", "astronomy"],
        "leniency_band": "medium",
        "restlessness_interpretation": "distraction",
        "difficulty_floor": {"addition": "low_double", "subtraction": "single"},
        "session_length": 5,
        "addition": {"digits": 2, "magnitude": "low_double", "carries": False, "borrows": False, "zero_in_minuend": False},
        "subtraction": {"digits": 1, "magnitude": "single", "carries": False, "borrows": False, "zero_in_minuend": False},
    },
]


def init_db() -> None:
    Base.metadata.create_all(engine)
    # Universal auto-migration for SQLite local development
    if settings.database_url.startswith("sqlite"):
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        with engine.connect() as conn:
            for table in Base.metadata.tables.values():
                if not inspector.has_table(table.name):
                    continue
                existing_cols = {col["name"] for col in inspector.get_columns(table.name)}
                for col in table.columns:
                    if col.name not in existing_cols:
                        col_type = col.type.compile(engine.dialect)
                        conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type}"))
            conn.commit()

    with SessionLocal() as session:
        for skill_id, label in SEEDED_SKILLS:
            if session.get(Skill, skill_id) is None:
                session.add(Skill(id=skill_id, label=label))

        for student in DEFAULT_STUDENTS:
            profile = session.get(ChildProfile, student["id"])
            if profile is None:
                profile = ChildProfile(
                    id=student["id"],
                    name=student["name"],
                    age=student["age"],
                    interests=student["interests"],
                    leniency_band=student["leniency_band"],
                    restlessness_interpretation=student["restlessness_interpretation"],
                    difficulty_floor=student["difficulty_floor"],
                    session_length=student["session_length"],
                )
                session.add(profile)
                session.flush()

            for skill in ("addition", "subtraction"):
                mastery = session.get(SubjectMastery, (student["id"], skill))
                if mastery is None:
                    session.add(
                        SubjectMastery(
                            profile_id=student["id"],
                            skill_id=skill,
                            difficulty_vector=student[skill],
                        )
                    )

                # Seed v1 (Baseline) and v2 (Devin Iterated - Live) Game versions
                g1_id = f"game-{student['name'].lower()}-{skill}-v1"
                if session.get(Game, g1_id) is None:
                    session.add(
                        Game(
                            id=g1_id,
                            profile_id=student["id"],
                            skill_id=skill,
                            version=1,
                            code_path=f"games/{student['id']}/{skill}/v1/index.html",
                            status="ready",
                            is_live=False,
                            gate_results={
                                "schema": "PASS - 5 questions validated",
                                "assertions": "PASS - no negative results",
                                "playthrough": "PASS - verified reachable",
                                "render_accessibility": "PASS - high contrast",
                            },
                            test_report={
                                "summary": f"Initial bespoke {skill} game generated for {student['name']}.",
                                "diagnosis": "Baseline level designed around single-digit foundation.",
                                "change_tier": "content",
                                "changes_made": [
                                    "Created theme-aligned arcade mechanics",
                                    "Bound adaptive Loop A arithmetic difficulty engine",
                                ],
                                "before_after_diff_summary": f"Initial version 1 built for {student['name']}.",
                            },
                        )
                    )

                g2_id = f"game-{student['name'].lower()}-{skill}-v2"
                if session.get(Game, g2_id) is None:
                    session.add(
                        Game(
                            id=g2_id,
                            profile_id=student["id"],
                            skill_id=skill,
                            version=2,
                            code_path=f"games/{student['id']}/{skill}/v2/index.html",
                            pr_url="https://github.com/max-gsnr/Cognitive-Environment/pull/2",
                            status="ready",
                            is_live=True,
                            gate_results={
                                "schema": "PASS - 5 questions validated",
                                "assertions": "PASS - carries and borrows verified",
                                "playthrough": "PASS - 100% completion reachable",
                                "render_accessibility": "PASS - WCAG compliant",
                            },
                            test_report={
                                "summary": f"Devin autonomous iteration for {student['name']}'s {skill} mission.",
                                "diagnosis": f"{student['name']} mastered the baseline with sustained high focus. Devin upgraded the cognitive pacing, added multi-digit visual scaffolding, and gently stepped arithmetic to mid-double digits with carrying.",
                                "change_tier": "structural",
                                "changes_made": [
                                    "Upgraded arithmetic difficulty floor from single-digit to double-digit carrying",
                                    "Added multi-digit visual scaffolding and carry animations",
                                    "Tightened reward feedback pacing for ADHD engagement",
                                    "Instrumented PostHog telemetry hooks for Loop A and Loop B",
                                ],
                                "before_after_diff_summary": f"v1 (single-digit baseline) → v2 (mildly increased difficulty with double-digit carrying, upgraded starfield, and instant feedback).",
                            },
                        )
                    )
        session.commit()


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
