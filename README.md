# Cognitive-Environment

Making [Devin](https://devin.ai) a first-class agent in [Entire](https://entire.io), so
cloud agent sessions become checkpoints in the repository they changed.

Git records *what* changed. Entire records *why*: the prompts, the session, the files, and
the checkpoint linked to the commit. Entire ships integrations for local agents that can
fire their own lifecycle hooks — Devin runs in Cognition's cloud and cannot, so it was not
a supported agent. This repository adds it:

| Piece | What it is |
| --- | --- |
| `bin/entire-agent-devin` | Entire [external agent plugin](https://docs.entire.io/agents/external-agent-plugins/architecture) (protocol v1) that teaches the Entire CLI how to read Devin sessions |
| `bin/entire-devin-bridge` | Hook transport: tails the Devin API and delivers lifecycle events to `entire hooks devin <hook>` |
| `tools/entire_agent_devin/` | Implementation: protocol commands, transcript parsing, bridge |

## Setup

```bash
scripts/setup-entire.sh      # installs the Entire CLI if needed, registers the agent
entire agent list            # devin should appear
```

The plugin is discovered by name: any executable called `entire-agent-<name>` on `$PATH`
is registered as an agent, and the setup script symlinks `bin/` accordingly.

## Use

```bash
# Live: follow a running Devin session and stream its activity into Entire.
export DEVIN_API_KEY=...
entire-devin-bridge follow --session devin-abc123

# Offline / CI: ingest a saved Devin API response.
entire-devin-bridge capture --payload session.json

# Link a session that ran before the bridge was watching to your last commit.
entire-devin-bridge attach --session devin-abc123
```

Then read the history back:

```bash
entire checkpoint list                    # sessions on this branch
entire checkpoint explain <commit>        # prompts and files behind a commit
entire blame path/to/file --long          # per-line attribution: AI / mixed / human
entire why path/to/file                   # why this code exists
```

`docs/ENTIRE.md` covers the architecture, the hook lifecycle, and what the integration
does and does not capture.

## Orbit

**Orbit** is the system this provenance layer exists for: an ADHD-focused adaptive math
game where the numbers are tuned by a plain script and the *game itself* is written and
rewritten by Devin. A teacher must be able to ask "why does Leo's game pause for 2.5
seconds after a wrong answer?" and get back the session, the prompt, and the telemetry
that motivated it.

Two loops, deliberately separated:

| | Loop A — difficulty | Loop B — the game |
| --- | --- | --- |
| Runs | after every single answer | after a play session |
| Decided by | pure Python over the database | a Devin session |
| Changes | which numbers come next | pacing, rewards, scaffolding, bugs |
| Ships as | a row in `subject_mastery` | a gated pull request |

Loop A never calls a model. `POST /attempts` classifies the answer (`borrow_omitted`,
`carry_omitted`, `place_value_misalignment`, …), compares latency against a three-day
per-tier baseline, and moves one axis of the difficulty vector. Loop B hands Devin the
profile, the error breakdown, the teacher's notes and a scoped PostHog key, and only
marks a generated game live once all four gates — schema, assertions, headless
playthrough, render/accessibility — report a pass.

| Piece | Where |
| --- | --- |
| Deterministic core | `app/difficulty.py`, `app/error_taxonomy.py`, `app/baseline.py`, `app/adaptation.py` |
| API | `app/routers/` (intake, profiles, attempts, games, audit, demo) |
| Prompts, verbatim | `app/prompts.py` |
| Teacher + child UI | `frontend/` (React, Vite) |
| Generated games | `games/{profile_id}/{skill_id}/v{n}/` |

```bash
cp .env.example .env             # OpenAI, Devin and PostHog keys; SQLite otherwise
.venv/bin/uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
```

The intake interview needs `OPENAI_API_KEY`; game generation and iteration need
`DEVIN_API_KEY`. Everything else — the roster, the adaptive question loop, the audit
log — runs without any external key.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest        # deterministic core + API behaviour
.venv/bin/ruff check .
cd frontend && npm run build
```
