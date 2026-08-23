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
Preferred: a small HTTP dashboard rather than a terminal — a green-on-black xterm reads badly
in recordings. Serve an HTML page that polls the DB read-only every second and renders count
cards, `subject_mastery` as difficulty chips (highlight the axis that changed), the newest ~12
`attempts` as a table, `development_notes` / `reported_problems`, and `audit_log` payloads, and
flash brand-new rows for one refresh. Then show it in a SECOND browser window tiled next to
the app:
```
# a second Chrome instance needs its OWN profile dir, otherwise it aborts with
# "Failed to create a ProcessSingleton for your profile directory"
chrome --user-data-dir=/tmp/dbview_profile --window-position=800,0 --window-size=800,1130 URL &
wmctrl -i -r <app-window-id> -e 0,0,0,796,1130   # app on the left half
```
Keep the CDP-controlled Chrome (the one computer-use drives) for the app, and run the read-only
dashboard in the second instance. Note the app window can get resized when a page reflows —
re-apply the wmctrl geometry if halves stop lining up. Before recording, clear `attempts`,
`development_notes`, `reported_problems`, `audit_log` and reset the mastery vectors so the
flashes read clearly, and set the game row back to `is_live=0` so "Make this the live version"
can be shown on camera.

Fallback: no terminal emulator is preinstalled on the Devin desktop: `sudo apt-get install -y xterm`
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

## Demonstrating the biometric / behavioural columns
`attempts` has `cursor_velocity_px_s`, `jitter_ratio`, `idle_time_ms`, `distraction_events`,
`focus_score`, `is_synthetic`. Only the **canvas arcade** (`frontend/src/game/OpenGameArena.ts`,
the default play mode) fills them; the static iframe game and the plain question form write
NULL (the dashboard shows "—"). How to make each value move on camera:
- answer in the canvas by typing into the "Math Coordinates" input and pressing Enter
  ("Dock (Enter)"); clicking the canvas alone never submits.
- `cursor_velocity_px_s` / `jitter_ratio`: sweep the mouse back and forth **over the canvas**
  before answering (jitter = total path / straight-line distance, so zig-zagging gives 20-90x;
  not touching the mouse gives exactly `0.00`, not NULL).
- `idle_time_ms`: only accumulates when a pointermove arrives after a >1200 ms gap — move,
  pause 3-4 s, then nudge the mouse again, otherwise idle stays 0.
- `distraction_events`: comes from `window.blur`, e.g. clicking the other tiled window. It is a
  per-question counter reset on each new question, but a blur that happens while the *next*
  question is already loaded shows up on that later row.
- `focus_score` = 100 − idle share − 25/blur − 15 if jitter > 2.8, so a jitter+idle+blur answer
  lands in the red band (~27%) — good final frame for the gauge cards.
- `hesitation_ms` and `cursor_peak_velocity_px_s` are accepted by `POST /attempts` but have no
  columns; the play page's "Cognitive Latency Breakdown" card is response-only. Say so explicitly
  when demoing, and don't expect them in the DB pane.
- Teacher cards live behind the "Teacher Telemetry Inspector" button at the bottom of the play
  page; they mirror the newest attempt's values, so screenshot them next to the DB row.
- Known flakiness: the canvas can write phantom `attempts` rows (an answer never typed, and/or
  operands from an already-answered question) — count rows before/after each submit and treat
  extra `unclassified` rows as a bug, not as your own mis-click.

## Reaching each feature in the UI
- Roster `/` → "Inspect Profile & Games" → `/profiles/:id`; "Play Game 🎮" → `/play/:profileId/:skillId`.
- Play page defaults to the canvas arcade even when a game is live; "Switch to Static Iframe" /
  "Switch to OpenGame Arcade" toggles the two.
- Play page plain/static flow: question, answer box, "Send"/"Check",
  "Teacher view" toggle (shows the true answer, plain-English difficulty and
  `error_class → movement`).
- Loop A (app/adaptation.py, app/ability.py) is rating-based with a 0.75-rung deadband, so
  a single correct answer usually **holds** the tier; expect 3-4 answers before
  `subject_mastery.difficulty_vector` visibly changes. To make the Difficulty Path chart actually
  step, the seeded `difficulty_vector` must be a **real ladder rung above the floor** (e.g.
  `{digits: 2, magnitude: "low_double"}` for subtraction); an invented vector such as
  `{digits: 1, magnitude: "mid_double"}` silently resolves to rating 0 and the chart stays flat at
  "moved 0 times". Reliable, quick demonstrations:
  two wrong answers in a row → "rest item" (much easier question, vector drops); a fast
  off-by-one → `counting_slip` and the *same* question is redrawn; `a - b` typed for
  `a + b` → `operator_confusion` and the vector is unchanged.
- To show `carry_omitted` you first need a tier with `carries: true`; answer correctly
  until the teacher view says "with carrying", then submit the digit-wise sum mod 10
  (e.g. 25+18 → 33).
- "Tell a grown-up" posts to `/games/<liveGame.id>/report-problem`, falling back to the literal
  id `orbit-game-client` when nothing is live — and `_require_game` 404s on that, so you still
  need a real live `Game` row before demoing report-a-problem.
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

## Testing the analytics dashboards (Session Monitor / Release Impact / Game Build Log)
- `.env` is **optional**: `app/config.py` already defaults `DATABASE_URL` to `sqlite:///./orbit.db`,
  so the backend starts without one. (The `cp .env.example .env` step above only matters if you
  actually create the file.)
- Analytics endpoints 404 ("no mastery row for this profile and skill") without a
  `SubjectMastery` row — seed one per skill you intend to view, and note the profile fields are
  `leniency_band`, `restlessness_interpretation`, `difficulty_floor`, `session_length`.
- After `rm -f orbit.db` you must **restart uvicorn as well as vite** — the running server holds
  the deleted file's inode and every freshly seeded profile 404s until it restarts. After any
  branch switch, kill the existing vite too or it silently serves the old bundle.
- Dashboard CSS may live in `frontend/src/analytics/dashboard.css`, imported from
  `frontend/src/main.tsx`, separate from `frontend/src/styles.css` (main's theme PRs keep
  rewriting `styles.css` wholesale). If analytics cards look unstyled after a merge, check that
  import first.
- Seed demo data from the profile page buttons rather than curl: "Seed practice history (demo)",
  "Seed two versions of play (demo)" (release impact) and "Seed a version history (demo)"
  (Game Build Log). Equivalent endpoints: `POST /demo/seed-release-impact`,
  `POST /demo/seed-evolution` with `{profile_id, skill_id}`.
- The profile page is long and mouse-wheel scrolling is sometimes swallowed by the scroll
  container; if a wheel scroll does nothing, drag the window scrollbar (right edge) instead, and
  Ctrl+Minus (80%) will fit an over-long dashboard section into one screenshot. Whether a section
  fits at 100% zoom changes between revisions — measure it rather than assuming, e.g.
  `document.querySelector('.console-detail')?.getBoundingClientRect().height` vs `innerHeight`,
  and report the two numbers.
- The Game Build Log hides secondary detail behind native `<details>` elements (rule ladder +
  recorded figures, the agent-vs-ours check matrix, provenance, and the rule-set/policy table
  under the run list). They are keyboard reachable: Tab to the `<summary>` and press Enter. Note
  the checks disclosure label is generated from `version.checks.length` while the matrix renders
  one row per **unique** check name, so the label can overcount (e.g. "All 10 checks" over a
  9-row table) — verify the count against the rendered rows, not the label.
- Selecting a different run resets every disclosure to closed; re-open the one you need before
  screenshotting.
- A version whose payload has no `trigger.ladder` / `trigger.measured` (the first build, "no
  telemetry") is the guard path: select it on a **fresh load** and check the console for
  `Cannot read properties of undefined (reading 'length')` from `EvolutionLog.tsx`.
- Build Log responsive behaviour: at ~1240px it keeps the two-column run-list/detail layout (it
  does not stack) and only collapses to one column near ~900px. Check
  `documentElement.scrollWidth === clientWidth` for horizontal overflow at each width.
- To prove the Session Monitor refreshes on WRONG answers, watch the "N of the last M" note and
  the band-chart dot count — those can only change via a re-fetch. Session progress
  ("n / 10 Completed") intentionally advances only on correct answers.
- For a clean v1-vs-v2 Release Impact read, be aware unversioned live play forms a "Before"
  card; the comparison itself should still be labelled `v1 → v2`. Focus is stored 0-100 and the
  dashboards divide by 100 — a four-digit percentage means that scaling regressed.
- Live Devin generation / iteration cannot be exercised without `DEVIN_API_KEY`; use the seeders.

## Blocked without secrets
- `OPENAI_API_KEY`: intake interview (`/intake`), profile creation.
- `DEVIN_API_KEY`: "Generate a game", "Run iteration (demo)".
- `POSTHOG_PROJECT_API_KEY`: `/demo/seed-posthog` (503 without it).

### Devin Secrets Needed
`OPENAI_API_KEY`, `DEVIN_API_KEY`, `POSTHOG_PROJECT_API_KEY` (all optional; everything
else above works without them).
