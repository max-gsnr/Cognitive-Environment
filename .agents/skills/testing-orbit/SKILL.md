---
name: testing-orbit
description: How to run and demo the Orbit app (FastAPI + Vite) locally end to end, including seeding a child profile, showing live SQLite changes beside the UI, and which flows are blocked without API keys.
---

# Testing / demoing Orbit locally

## Bring the stack up
1. `cp .env.example .env` then set `DATABASE_URL=sqlite:///./orbit.db`.
   The example ships an **empty** `DATABASE_URL`, which makes SQLAlchemy raise at
   import time and the backend never starts — always set it.
2. Backend: `.venv/bin/uvicorn app.main:app --port 8000` (log to a file, e.g. /tmp/backend.log).
3. Frontend: `cd frontend && npm run dev` → http://localhost:5173 (proxies `/api` → :8000
   after stripping `/api`, and `/games` → :8000 unchanged).
4. `GET /health` reports which integrations are configured (openai/devin/posthog).

## Getting a child profile without the intake interview
There is no `POST /profiles`; the only creation path is the branching intake interview,
which needs `OPENAI_API_KEY` (without it `POST /intake/start` returns a bare 500 and the
UI just prints "Internal Server Error"). Seed directly instead:

```python
from app.db import SessionLocal, init_db
from app.models import ChildProfile, SubjectMastery
from app import difficulty
# ChildProfile(name=..., age=..., interests=[...], leniency_band="low",
#   restlessness_interpretation="distraction",
#   difficulty_floor={"addition": "single_digit", "subtraction": "single_digit"},
#   session_length=10, constraints={})
# plus one SubjectMastery(profile_id=..., skill_id="addition"/"subtraction",
#   difficulty_vector={**difficulty.base_vector(2), "magnitude": "mid_double"})
```
Mastery rows are required: `POST /attempts` 404s ("no mastery row") without them.

## Showing the DB change live next to the UI (very good demo material)
No terminal emulator is preinstalled on the Devin desktop: `sudo apt-get install -y xterm`
works. Then tile with wmctrl (screen is 1600x1122 behind the 1024x768 tool coordinates):
```
wmctrl -r "Chrome" -b remove,maximized_vert,maximized_horz
wmctrl -r "Chrome" -e 0,0,0,796,1090
xterm -fa Monospace -fs 11 -bg black -fg green -e .venv/bin/python watcher.py &
wmctrl -r "orbit.db live" -e 0,802,0,796,1090
```
A ~40-line polling script that prints `subject_mastery`, the newest `attempts`,
`development_notes`, `reported_problems` and `audit_log` every second is enough; open the
DB read-only (`sqlite3.connect("file:orbit.db?mode=ro", uri=True)`) so it never locks
the app.

## Reaching each feature in the UI
- Roster `/` → "Open profile" → `/profiles/:id`; Play button → `/play/:profileId/:skillId`.
- Play page plain flow (used when no game is live): question, answer box, "Check",
  "Teacher view" toggle (shows the true answer, plain-English difficulty and
  `error_class → movement`).
- Loop A (app/adaptation.py, app/ability.py) is rating-based with a 0.75-rung deadband, so
  a single correct answer usually **holds** the tier; expect 3-4 answers before
  `subject_mastery.difficulty_vector` visibly changes. Reliable, quick demonstrations:
  two wrong answers in a row → "rest item" (much easier question, vector drops); a fast
  off-by-one → `counting_slip` and the *same* question is redrawn; `a - b` typed for
  `a + b` → `operator_confusion` and the vector is unchanged.
- To show `carry_omitted` you first need a tier with `carries: true`; answer correctly
  until the teacher view says "with carrying", then submit the digit-wise sum mod 10
  (e.g. 25+18 → 33).
- The "Something wrong with the game?" / "Tell a grown-up" input only exists when a game
  is **live** for that skill. Without `DEVIN_API_KEY` you cannot generate one, but you can
  copy an existing `games/<other-profile>/<skill>/vN` directory to
  `games/<profile>/<skill>/v1`, patch `config.js` (`PROFILE_ID`, `GAME_ID`, and
  `API_BASE` → `http://localhost:8000`, since the iframe is served from :5173 and only
  `/api` is proxied), and insert a `Game` row with `status="ready"`, `is_live=False`,
  `code_path="games/<profile>/<skill>/v1/index.html"`. Then use the profile page's
  "Make this the live version" button (writes a `rollback` audit row) and the play page
  renders the game in an iframe.
- Audit log page `/audit` renders `audit_log` rows with payloads — a good closing shot.

## Blocked without secrets
- `OPENAI_API_KEY`: intake interview (`/intake`), profile creation.
- `DEVIN_API_KEY`: "Generate a game", "Run iteration (demo)".
- `POSTHOG_PROJECT_API_KEY`: `/demo/seed-posthog` (503 without it).

### Devin Secrets Needed
`OPENAI_API_KEY`, `DEVIN_API_KEY`, `POSTHOG_PROJECT_API_KEY` (all optional; everything
else above works without them).
