---
name: testing-orbit-ui
description: How to set up, seed, and exercise the Orbit adaptive-math UI (FastAPI backend in app/, React+Vite frontend in frontend/) end-to-end without API keys.
---

# Testing the Orbit UI

## Running the stack

```bash
# backend (SQLite ./orbit.db by default, no keys required)
nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/backend.log 2>&1 &
# frontend (proxies /api -> 127.0.0.1:8000)
cd frontend && npm install && npm run dev     # http://localhost:5173
```

Beware: `pkill -f "uvicorn app.main"` can kill the shell running it, because the shell's own
command line matches the pattern. Use a narrower pattern or `pkill -f "bin/uvicorn"`.

The backend log (`/tmp/backend.log`) is the cheapest proof that the UI is really backend-driven:
each question is a `GET /profiles/{id}/skills/{skill}/next-question` and each answer a
`POST /attempts`.

## Devin Secrets Needed

- `OPENAI_API_KEY` — only for the intake interview (`/intake`). Without it there is **no UI path
  to create a child profile**.
- `DEVIN_API_KEY` — only for game generation/iteration (`/profiles/:id/generate/:skill`).
- PostHog key — telemetry only.

Everything else (roster, profile, play, teacher settings, notes, audit log) works keyless.

## Seeding a profile without the intake interview

Mirror the `profile` fixture in `tests/test_api.py`: one `ChildProfile` plus one `SubjectMastery`
row per skill (`addition`, `subtraction`). Example:

```python
from app import difficulty
from app.db import SessionLocal, init_db
from app.models import ChildProfile, SubjectMastery
init_db()
with SessionLocal() as s:
    child = ChildProfile(name="Leo", age=7, interests=["outer space"],
        leniency_band="low", restlessness_interpretation="distraction",
        difficulty_floor={"addition": "single_digit", "subtraction": "single_digit"},
        session_length=10, constraints={})
    s.add(child); s.flush()
    for skill in ("addition", "subtraction"):
        s.add(SubjectMastery(profile_id=child.id, skill_id=skill,
              difficulty_vector={**difficulty.base_vector(1), "magnitude": "single"}))
    s.commit(); print(child.id)
```

## How the adaptation actually moves (needed to design real tests)

Read `app/adaptation.py`, `app/difficulty.py`, `app/error_taxonomy.py`, `app/baseline.py` first.
Key non-obvious behaviours that make naive tests vacuous:

- **Correct + fast → increment.** The ladder is: current band → next band in the same digit count
  → skill flags (`carries`; `borrows`, `zero_in_minuend`) → +1 digit. From single digits, ~7 fast
  correct answers reach triple digits, so "difficulty hardens" is easy to demonstrate live.
- **Most wrong answers do NOT decrement.** `unclassified` and `operator_confusion` HOLD, and a
  *fast* `counting_slip` HOLDs and repeats the tier. So "answer wrong repeatedly" typically leaves
  the difficulty untouched — a floor test built only on wrong answers passes even if the clamp is
  broken. Design for a decrement explicitly.
- **To force a decrement through the UI:** a *slow* `counting_slip` (answer off by exactly 1).
  "Slow" needs a baseline, which needs ≥5 correct attempts in the *same* `tier_key` within 3 days
  (`app/baseline.py`). Correct answers change the tier, so seed the baseline rows directly:

  ```python
  tier = difficulty.tier_key(vec)   # e.g. digits=2|magnitude=low_double|carries=False|...
  Attempt(..., tier_key=tier, is_correct=True, error_class="correct", latency_to_submit_ms=1000)
  ```

  Then wait ~5 s in the UI before submitting an off-by-one answer.
- **Leniency banks decrements:** low = 1 step per rough answer, medium = 0.5, high = 0.34. Set
  leniency to Low when you want one rough answer to move the ladder once.
- **Proving the difficulty floor:** run the *same* slow off-by-one scenario twice — once with the
  floor at "Never below single digits" (difficulty visibly drops to single-digit questions) and
  once at "Never below double digits" (it stays double-digit). The contrast is the proof; a single
  run proves nothing.

## Useful UI facts

- Routes: `/` roster, `/profiles/:id`, `/play/:id/:skill`, `/audit`, `/intake`,
  `/profiles/:id/generate/:skill`.
- The answer input strips non-digits client-side, and Check is disabled while empty.
- Teacher settings save on `change` (selects) / `blur` (questions-per-session number input) and
  each change writes an audit entry with a before/after diff.
- Errors render as the raw API JSON string (e.g. `{"detail":"profile not found"}`) in the main
  area — expect that, not a styled error page.
