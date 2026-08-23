# Build notes

What this system does, why it is split the way it is, and what is deliberately
missing.

## The split

Two loops, and the line between them is the whole design.

**Loop A — every answer, no model call.** The game asks the backend for a
question, the child answers, the backend classifies the error, compares the
latency to that child's own recent pace at that exact difficulty tier, updates a
rating for the child, and aims the next question at the tier they should get
roughly 80% right. It is arithmetic and a lookup table. It runs in
milliseconds, it is testable, and it never surprises a teacher. Tuning numbers
does not need an agent and we do not pretend otherwise.

**Loop B — after a session settles, with a model.** Devin gets the profile, the
error breakdown, the teacher's notes, the child's reported problems, and a
scoped PostHog key. It queries the telemetry itself, decides whether the *game*
has stopped working (bored, confused by the interface, ignoring a mechanic), and
edits the generated game's code. That judgment is what needs an agent.

Loop A moves the numbers. Loop B decides whether the game itself is broken.

## Decisions worth knowing

- **The baseline is the child's own pace, never a benchmark.** Five correct
  attempts at the same tier inside three days, or latency is not read at all.
  Below that, correctness alone decides. A child having a bad week does not get
  compared to last month's good week, and a new child is never rushed.
  `app/baseline.py`.
- **Difficulty is a vector, not a level.** Digits, magnitude band, carries,
  borrows, zero-in-minuend. Movement changes one axis at a time, so a child who
  can do 3-digit sums but not borrowing across a zero gets exactly that
  question, not "level 4". `app/difficulty.py`.
- **Error class decides which axis moves.** A borrow omitted softens borrowing,
  not magnitude. Operator confusion repeats the tier instead of easing it —
  misreading the sign is not evidence the arithmetic is too hard.
  `app/error_taxonomy.py`, `app/adaptation.py`.
- **Difficulty is aimed, not stepped.** The state is "how strong is this child"
  (a rating), not "which rung are we on", and each question is drawn from the
  tier whose expected success rate is the one we want. Stepping one rung per
  correct answer — what this used to do — crossed the whole ladder in nine
  answers, so a ten-question session ended in 3-digit carrying regardless of the
  child. `app/ability.py`, and `scripts/loop_a_sim.py` for the numbers: simulated
  quit rate falls from ~99% to ~16%, accuracy lands at 76-87%.
- **The target success rate is what leniency now means.** Low 75%, medium 80%,
  high 85%. Adaptive *testing* aims at 50% because that is where an answer is
  most informative; practice for a child cannot, and 75-85% is where both Math
  Garden's item sampling and the "85% rule" put fastest learning.
- **Latency never drives difficulty, in either direction.** A correct-but-slow
  answer holds the tier; it used to take difficulty away, which punished the
  child for the slowness itself. Response-time-adaptive scheduling buys no
  measurable post-test gain, and children with raised inattention report more
  trouble concentrating under it. Latency stays diagnostic. `app/baseline.py`.
- **Errors are answered, not just absorbed.** Every fifth question is aimed a
  rung low, and two wrong answers in a row buy a deliberately easy one — a rest
  item outranks every other rule, including "repeat this tier". Long error runs
  are the thing that ends an ADHD session.
- **The rating is replayed, never stored.** It is a fold over the child's own
  attempt log, seeded from the tier intake first placed them at, so the
  difficulty a child saw is always reproducible from the audit trail and a
  restart cannot lose it. `app/adaptation.py`.
- **Restlessness is a teacher setting, not an inference.** The intake asks
  whether the child's movement means they have lost the thread or that they are
  moving in order to think, and Loop B reads that before treating orbiting as
  disengagement. Guessing this wrong is worse than not knowing.
- **Nothing goes live without passing gates.** Schema, arithmetic assertions (no
  negative operands, no negative results, no fourth digit), a headless
  playthrough including a deliberate wrong answer, and a render/accessibility
  check. A missing gate result counts as a failure; there are no silent retries,
  and a failed version stays visible in the teacher's version list.
  `app/routers/games.py`.
- **Rollback is a database flag, never a git operation.** `games.is_live` picks
  which generated version is served. History is never rewritten and every
  version stays playable. A teacher can undo Devin in one click.
- **Devin opens a PR; it never pushes to main.** Every generated or iterated
  game is reviewable code with a session URL attached, which is what makes the
  agent auditable rather than magic.
- **Secrets travel as Devin session secrets.** The PostHog personal key is
  passed through the session-secret mechanism so Devin can query telemetry
  itself; it never appears in prompt text. Prompt text ends up in transcripts.
- **`POSTHOG_HOST` has to name the project's region.** PostHog ingestion on the
  wrong region returns 200 and drops the batch, so telemetry looks captured and
  Devin's query returns nothing. An EU project needs `eu.i.posthog.com` in both
  the backend env and the frontend's `VITE_POSTHOG_HOST`.

## The intake is real

The interview is live, one question at a time, and the next question depends on
the previous answer. There is no fallback profile: if the interview does not
finish, no child is created. It asks about observable behaviour ("what happens
when a task gets boring"), never for a diagnosis, ranks interests, asks about
addition and subtraction separately, and keeps "unknown" as an answer rather
than guessing. Teacher answers outrank parent answers when they conflict.

Only two calls to a model: generating each next question, and resolving the
transcript into a profile. `app/prompts.py` holds both verbatim.

## What is demo scaffolding

Marked as such in the UI, and it exists because a demo cannot wait three days
for real data:

- `POST /demo/seed-history` writes 30 correct, at-pace attempts at the current
  tier so the latency baseline has samples and the "correct but slow" beat can
  actually fire.
- `POST /demo/seed-posthog` pushes a canned *bored* session (long idles, an
  abandoned level, no error-class signal) so Devin has real events to query.
- "Run iteration (demo)" on the profile page seeds those events and starts the
  iteration session in one click.

## Known limits

- SQLite by default. `DATABASE_URL` switches it to Postgres; nothing depends on
  SQLite behaviour.
- No auth, no multi-tenancy. One teacher, one classroom, by design.
- Addition and subtraction only, three digits maximum, no negative results.
- The backend serves generated games from the working tree, so a generated
  game's PR has to be merged and pulled before it is playable locally.
- Idle and motion telemetry is emitted by the generated games, not by the React
  shell; the shell only mirrors problem/answer events.
