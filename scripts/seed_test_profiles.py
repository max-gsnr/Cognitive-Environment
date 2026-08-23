"""Testing-only helper: create a demo child profile without the LLM intake."""

import uuid

from app import difficulty
from app.db import SessionLocal, init_db
from app.models import ChildProfile, SubjectMastery


def main() -> None:
    init_db()
    pid = str(uuid.uuid4())
    with SessionLocal() as session:
        session.add(
            ChildProfile(
                id=pid,
                name="Ava Demo",
                age=8,
                interests=["space"],
                leniency_band="medium",
                restlessness_interpretation="self_regulation",
                session_length=10,
                difficulty_floor={
                    "addition": "single_digit",
                    "subtraction": "single_digit",
                },
            )
        )
        for skill in ("addition", "subtraction"):
            session.add(
                SubjectMastery(
                    profile_id=pid,
                    skill_id=skill,
                    difficulty_vector=difficulty.base_vector(1),
                )
            )
        session.commit()
    print(pid)


if __name__ == "__main__":
    main()
