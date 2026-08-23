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

                # Seed v1 (Baseline), v2 (Devin Iterated - Live), and v3 (Blocked Candidate)
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
                                "independent": {
                                    "files": "PASS - index.html and game.js present",
                                    "shell_contract": "PASS - calls next-question and attempts",
                                    "instrumentation": "PASS - all 7 events emitted",
                                    "no_fast_flashing": "PASS - slowest cycle 0.9s",
                                    "focus_visible": "PASS - :focus-visible styled",
                                    "playthrough": "PASS - answered 3 questions headless",
                                    "passed": True,
                                },
                            },
                            provenance={
                                "prompt": "generate",
                                "prompt_revision": "v1.0",
                                "agent": "devin",
                                "seeded": True,
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
                                "independent": {
                                    "files": "PASS - index.html and game.js present",
                                    "shell_contract": "PASS - calls next-question and attempts",
                                    "instrumentation": "PASS - all 7 events emitted",
                                    "no_fast_flashing": "PASS - slowest cycle 0.6s",
                                    "focus_visible": "PASS - :focus-visible styled",
                                    "playthrough": "PASS - answered 3 questions headless",
                                    "passed": True,
                                },
                            },
                            provenance={
                                "prompt": "iterate",
                                "prompt_revision": "v2.1",
                                "agent": "devin",
                                "seeded": True,
                                "from_version": 1,
                                "telemetry_signals": {
                                    "dominant_signal": "healthy_struggle",
                                    "change_tier": "structural",
                                    "suggested_fix": "Upgrade arithmetic difficulty floor to double-digit carrying",
                                    "event_count": 148,
                                    "signals": {
                                        "questions": 12,
                                        "answers": 11,
                                        "idle_seconds": 35,
                                        "solve_seconds": 64.2,
                                        "idle_ratio": 0.35,
                                        "immediate_corrections": 1,
                                        "after_pause_corrections": 2,
                                        "after_pause_ratio": 0.67,
                                        "micro_jitter": 3,
                                        "repetitive_orbit": 0,
                                        "rage_clicks": 0,
                                        "abandons": 0,
                                        "disengaged_answers": 0,
                                        "fast_wrong_ratio": 0.08,
                                        "slow_correct_ratio": 0.15,
                                    },
                                },
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

                g3_id = f"game-{student['name'].lower()}-{skill}-v3"
                if session.get(Game, g3_id) is None:
                    session.add(
                        Game(
                            id=g3_id,
                            profile_id=student["id"],
                            skill_id=skill,
                            version=3,
                            status="gates_failed",
                            is_live=False,
                            gate_results={
                                "schema": "PASS - all questions matched schema",
                                "assertions": "PASS - 18 assertions passed",
                                "playthrough": "PASS - completed simulated level",
                                "render_accessibility": "PASS - no contrast regressions",
                                "independent": {
                                    "files": "PASS - index.html and game.js present",
                                    "shell_contract": "PASS - calls next-question and attempts",
                                    "instrumentation": "FAIL - idle_tick is no longer emitted during cooldown",
                                    "no_fast_flashing": "PASS - slowest cycle 0.6s",
                                    "focus_visible": "FAIL - disabled answer button loses focus ring",
                                    "playthrough": "FAIL - stalled after question 1 of 3: answer field stayed disabled",
                                    "passed": False,
                                },
                            },
                            provenance={
                                "prompt": "iterate",
                                "prompt_revision": "v2.2",
                                "agent": "devin",
                                "seeded": True,
                                "from_version": 2,
                                "telemetry_signals": {
                                    "dominant_signal": "impulsive_guessing",
                                    "change_tier": "content",
                                    "suggested_fix": "Add a ~2.5s gentle cooldown before the next guess is accepted",
                                    "event_count": 96,
                                    "signals": {
                                        "questions": 9,
                                        "answers": 9,
                                        "idle_seconds": 25,
                                        "solve_seconds": 41.2,
                                        "idle_ratio": 0.378,
                                        "immediate_corrections": 4,
                                        "after_pause_corrections": 0,
                                        "after_pause_ratio": 0.0,
                                        "micro_jitter": 1,
                                        "repetitive_orbit": 0,
                                        "rage_clicks": 0,
                                        "abandons": 0,
                                        "disengaged_answers": 0,
                                        "fast_wrong_ratio": 0.44,
                                        "slow_correct_ratio": 0.11,
                                    },
                                },
                            },
                            test_report={
                                "summary": "Experimental cooldown candidate to throttle impulsive guessing.",
                                "diagnosis": "Frequent fast incorrect guesses detected.",
                                "change_tier": "content",
                                "changes_made": [
                                    "Added 2.5s input cooldown timer",
                                    "Temporarily disabled answer button during transition",
                                ],
                                "before_after_diff_summary": "Throttled input submission.",
                            },
                        )
                    )
        session.commit()


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
