import pytest
from fastapi.testclient import TestClient

from app import difficulty
from app.db import SessionLocal, init_db
from app.main import app
from app.models import (
    Attempt,
    ChildProfile,
    Game,
    IntakeSession,
    SubjectMastery,
)
from app.routers import games, intake
from app.routers.games import gates_passed
from app.routers.intake import _restlessness


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def profile():
    init_db()
    with SessionLocal() as session:
        child = ChildProfile(
            name="Leo",
            age=7,
            interests=["outer space", "trains"],
            leniency_band="low",
            restlessness_interpretation="distraction",
            difficulty_floor={
                "addition": "single_digit",
                "subtraction": "single_digit",
            },
            session_length=10,
            constraints={},
        )
        session.add(child)
        session.flush()
        for skill_id in ("addition", "subtraction"):
            session.add(
                SubjectMastery(
                    profile_id=child.id,
                    skill_id=skill_id,
                    difficulty_vector={
                        **difficulty.base_vector(2),
                        "magnitude": "mid_double",
                    },
                )
            )
        session.commit()
        return child.id


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"


def test_skills_are_seeded(client):
    ids = {skill["id"] for skill in client.get("/skills").json()}
    assert ids == {"addition", "subtraction"}


def test_next_question_matches_the_current_vector(client, profile):
    body = client.get(
        f"/profiles/{profile}/skills/addition/next-question"
    ).json()
    a, b = body["operands"]
    assert body["operator"] == "+"
    assert body["correct_answer"] == a + b
    assert body["difficulty_vector_snapshot"]["magnitude"] == "mid_double"


def seed_tier_history(profile_id, skill_id, latency_ms=3000, count=5):
    """A tier only has a pace once five correct attempts sit in it."""
    with SessionLocal() as session:
        mastery = session.get(SubjectMastery, (profile_id, skill_id))
        tier = difficulty.tier_key(mastery.difficulty_vector)
        operator = "+" if skill_id == "addition" else "-"
        for _ in range(count):
            session.add(
                Attempt(
                    profile_id=profile_id,
                    skill_id=skill_id,
                    operands=[40, 30],
                    operator=operator,
                    answer_given=70 if operator == "+" else 10,
                    correct_answer=70 if operator == "+" else 10,
                    is_correct=True,
                    error_class="correct",
                    difficulty_vector_snapshot=mastery.difficulty_vector,
                    tier_key=tier,
                    latency_to_submit_ms=latency_ms,
                )
            )
        session.commit()


def test_the_two_skills_move_independently(client, profile):
    """The demo's central beat: fast addition hardens while slow subtraction softens."""
    seed_tier_history(profile, "subtraction")

    for _ in range(6):
        question = client.get(
            f"/profiles/{profile}/skills/addition/next-question"
        ).json()
        client.post(
            "/attempts",
            json={
                "profile_id": profile,
                "skill_id": "addition",
                "operands": question["operands"],
                "operator": "+",
                "answer_given": question["correct_answer"],
                "latency_to_submit_ms": 1200,
            },
        )

    for _ in range(6):
        question = client.get(
            f"/profiles/{profile}/skills/subtraction/next-question"
        ).json()
        client.post(
            "/attempts",
            json={
                "profile_id": profile,
                "skill_id": "subtraction",
                "operands": question["operands"],
                "operator": "-",
                "answer_given": question["correct_answer"],
                "latency_to_submit_ms": 30000,
            },
        )

    detail = client.get(f"/profiles/{profile}").json()
    vectors = {row["skill_id"]: row["difficulty_vector"] for row in detail["mastery"]}
    addition_rank = difficulty.rank(vectors["addition"], "addition")
    subtraction_rank = difficulty.rank(vectors["subtraction"], "subtraction")
    start = difficulty.rank(
        {**difficulty.base_vector(2), "magnitude": "mid_double"}, "addition"
    )
    assert addition_rank > start
    assert subtraction_rank <= start


def test_attempt_reports_the_error_class(client, profile):
    response = client.post(
        "/attempts",
        json={
            "profile_id": profile,
            "skill_id": "subtraction",
            "operands": [52, 27],
            "operator": "-",
            "answer_given": 35,
            "latency_to_submit_ms": 4000,
        },
    )
    body = response.json()
    assert body["is_correct"] is False
    assert body["error_class"] == "borrow_omitted"


def test_notes_and_audit_log(client, profile):
    client.post(
        f"/profiles/{profile}/notes",
        json={"author": "teacher", "note": "rough week at home"},
    )
    actions = {entry["action"] for entry in client.get("/audit-log").json()}
    assert "note_added" in actions


def test_profile_patch_records_a_diff(client, profile):
    client.patch(f"/profiles/{profile}", json={"session_length": 6})
    entry = next(
        item
        for item in client.get("/audit-log").json()
        if item["action"] == "profile_updated"
    )
    assert entry["payload"]["diff"]["session_length"]["after"] == 6


def test_seeded_history_gives_the_tier_a_real_baseline(client, profile):
    """Without the demo seed, 'correct but slow' cannot fire at all."""
    before = client.post(
        "/attempts",
        json={
            "profile_id": profile,
            "skill_id": "addition",
            "operands": [40, 30],
            "operator": "+",
            "answer_given": 70,
            "latency_to_submit_ms": 15000,
        },
    ).json()
    assert before["baseline_ms"] is None

    seeded = client.post(
        "/demo/seed-history", json={"profile_id": profile, "skill_id": "addition"}
    ).json()
    assert seeded["seeded"] == 30

    after = client.post(
        "/attempts",
        json={
            "profile_id": profile,
            "skill_id": "addition",
            "operands": [40, 30],
            "operator": "+",
            "answer_given": 70,
            "latency_to_submit_ms": 15000,
        },
    ).json()
    assert after["baseline_ms"] is not None
    # Correct but laboured holds the tier. It never used to: it took difficulty
    # away, which punished a child for the slowness itself.
    assert after["movement"] == "hold"


def test_finalize_seeds_mastery_for_both_skills(client, monkeypatch):
    async def resolved(_prompt):
        return {
            "interests": ["outer space"],
            "leniency_band": "high",
            "restlessness_interpretation": "focus",
            "difficulty_floor": {"addition": "double_digit"},
            "session_length": 8,
        }

    monkeypatch.setattr(intake.openai_client, "complete_json", resolved)

    with SessionLocal() as session:
        interview = IntakeSession(
            transcript=[{"question": f"q{n}", "answer": "a"} for n in range(10)],
            status="in_progress",
        )
        session.add(interview)
        session.commit()
        intake_id = interview.id

    profile_id = client.post(
        f"/intake/{intake_id}/finalize", json={"name": "Leo", "age": 7}
    ).json()["profile_id"]

    with SessionLocal() as session:
        child = session.get(ChildProfile, profile_id)
        assert child.restlessness_interpretation == "self_regulation"
        assert child.session_length == 8
        rows = session.query(SubjectMastery).filter_by(profile_id=profile_id).all()
        assert {row.skill_id for row in rows} == {"addition", "subtraction"}
        addition = next(row for row in rows if row.skill_id == "addition")
        assert addition.difficulty_vector["digits"] == 2


def test_rollback_promotes_the_version_the_teacher_picked(client, profile):
    with SessionLocal() as session:
        first = Game(
            profile_id=profile,
            skill_id="addition",
            version=1,
            status="ready",
            is_live=False,
        )
        second = Game(
            profile_id=profile,
            skill_id="addition",
            version=2,
            status="ready",
            is_live=True,
        )
        session.add_all([first, second])
        session.commit()
        first_id = first.id
        second_id = second.id

    body = client.post(f"/games/{first_id}/rollback").json()
    assert body["version"] == 1

    with SessionLocal() as session:
        assert session.get(Game, first_id).is_live is True
        assert session.get(Game, second_id).is_live is False


def test_iterating_an_old_version_does_not_reuse_a_version_number(
    client, profile, monkeypatch
):
    async def created(**_kwargs):
        return {"session_id": "devin-test", "url": "https://app.devin.ai/sessions/test"}

    monkeypatch.setattr(games.devin_client, "create_session", created)

    with SessionLocal() as session:
        old = Game(
            profile_id=profile, skill_id="addition", version=1, status="ready"
        )
        newest = Game(
            profile_id=profile,
            skill_id="addition",
            version=2,
            status="ready",
            is_live=True,
        )
        session.add_all([old, newest])
        session.commit()
        old_id = old.id

    successor_id = client.post(f"/games/{old_id}/iterate", json={}).json()["game_id"]

    with SessionLocal() as session:
        assert session.get(Game, successor_id).version == 3


def test_only_a_gated_version_can_go_live(client, profile):
    with SessionLocal() as session:
        broken = Game(
            profile_id=profile, skill_id="subtraction", version=1, status="gates_failed"
        )
        session.add(broken)
        session.commit()
        broken_id = broken.id

    assert client.post(f"/games/{broken_id}/rollback").status_code == 409


def test_a_gate_verdict_may_carry_its_evidence():
    """Devin reports "PASS - <what it checked>", not a bare token."""
    evidenced = {
        "schema": "PASS - all 10 question objects matched the shape exactly",
        "assertions": "PASS - no negative operands, no operand over 3 digits",
        "playthrough": "PASS - 10 questions, question 2 deliberately wrong",
        "render_accessibility": "PASS - no @keyframes, contrast 7.5:1 to 10.6:1",
    }
    assert gates_passed(evidenced) is True

    evidenced["playthrough"] = "FAIL - the session stalled after question 3"
    assert gates_passed(evidenced) is False

    evidenced["playthrough"] = "the earlier attempt did not pass, this one is fine"
    assert gates_passed(evidenced) is False


def test_the_interviews_focus_answer_is_stored_as_self_regulation():
    assert _restlessness("focus") == "self_regulation"
    assert _restlessness("self_regulation") == "self_regulation"
    assert _restlessness("unknown") == "distraction"
    assert _restlessness(None) == "distraction"


def test_a_missing_gate_is_a_failure():
    assert gates_passed({"schema": "pass"}) is False
    assert (
        gates_passed(
            {
                "schema": "pass",
                "assertions": "passed",
                "playthrough": "pass",
                "render_accessibility": "failed",
            }
        )
        is False
    )
    assert (
        gates_passed(
            {
                "schema": "pass",
                "assertions": "pass",
                "playthrough": "pass",
                "render_accessibility": "pass",
            }
        )
        is True
    )
