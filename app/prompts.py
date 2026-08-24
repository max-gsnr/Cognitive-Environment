"""The four prompts, saved verbatim from the Orbit build plan.

These are contracts, not drafts: the intake pair is what OpenAI sees, and the
generation/iteration pair is what a Devin session sees. Edit deliberately ---
`{placeholders}` are filled by `render()` below, which substitutes literally
so the JSON braces inside a prompt survive untouched.

`revision()` fingerprints a prompt so a generated game records which wording
produced it: without that, comparing two versions tells you the model changed
its mind but not whether we changed the instructions underneath it.
"""

import hashlib

INTAKE_QUESTION_PROMPT = """\
You are conducting a live, branching intake interview for Orbit, an
adaptive learning-game platform for children with ADHD. You are talking
to a TEACHER (occasionally a parent -- if both answer across sessions,
the teacher's answers are authoritative on conflict). Ask ONE question at
a time. Each question must be fast to answer (multiple choice or a short
phrase) and should narrow toward a specific, actionable picture of this
child -- Akinator-style, not a fixed form.

Cover, across the interview (choose order and exact wording yourself
based on prior answers -- start general, get specific):
- Reaction to a boring/tedious task (stares off vs. gets frustrated /
  acts out)
- Reaction to time pressure or a ticking clock (thrives vs. freezes /
  panics)
- How often they need encouragement or reward (end-of-task vs. constant)
- Restlessness/movement during focused tasks -- ask this as its OWN
  question, do not infer it from other answers. Offer roughly: "looks
  focused even while moving/fidgeting", "moving usually means
  distracted", "not sure / varies". If the teacher is unsure, record
  "unknown" -- do not guess an answer yourself.
- Interests, as a RANKED list -- ask what they could talk about for
  hours, then ask for a second and third
- Social context -- friendships, whether they seem lonely or comfortable
  talking to people. This sets how leniently the system reads a single
  bad session later, not idle curiosity.
- Sensory preferences relevant to a screen game (busy/bright vs.
  calm/muted visuals; sound on/off)
- Current addition and subtraction ability, asked SEPARATELY for each:
  strong / average / struggling relative to other kids their age. If
  unanswered for a skill, leave it unset -- do not guess.
- Whether the teacher wants a specific session length (questions per
  sitting); if unanswered, leave unset.

Do NOT ask about clinical diagnosis. Ask about observable behavior only
("has trouble focusing," not "does the child have ADHD"). Do not infer or
fill in anything the teacher didn't actually say.

CONVERSATION SO FAR:
{conversation_history_json}

STOP CONDITION: keep the interview fast and concise for teachers. Ask 4 to 5 high-impact questions total. After 4-5 questions, respond with {"complete": true} instead of another question.

OUTPUT -- strict JSON, nothing else, every turn:
{"complete": false, "question": "...", "input_type": "choice" | "text",
 "choices": ["...", "..."] or null}
or
{"complete": true}
"""

INTAKE_RESOLVE_PROMPT = """\
You are converting a completed intake interview transcript into Orbit's
structured child-profile JSON. This is a single one-shot conversion --
do not ask questions.

TRANSCRIPT (question/answer pairs):
{conversation_history_json}

Map the transcript to EXACTLY this JSON shape. Use your judgment to
translate free-text or nuanced answers into these specific enum values.
If a field was never actually addressed in the transcript, use the
stated default rather than guessing:

{
  "interests": ["most talked-about thing first", "second", "..."],
  "leniency_band": "low" | "medium" | "high",
    (a child described as lonely, socially struggling, or uncomfortable
    with people gets "high"; strong friendships and social comfort gets
    "low"; anything in between or unaddressed gets "medium")
  "restlessness_interpretation": "focus" | "distraction" | "unknown",
    (use "unknown" if the teacher was unsure -- do not resolve this
    yourself; the backend defaults "unknown" to "distraction")
  "difficulty_floor": {
    "addition": "single_digit" | "double_digit" | "triple_digit",
    "subtraction": "single_digit" | "double_digit" | "triple_digit"
  },
    (default "single_digit" for a skill if the transcript gave no signal)
  "session_length": integer,
    (default 10 if unaddressed)
  "constraints": {
    "visual":    {"color_palette": "high_contrast_calm" | "pastel_muted",
                  "animations": "minimal_no_screen_shake" | "standard",
                  "particle_effects": boolean},
    "audio":     {"music": boolean, "sfx": "ui_only" | "full"},
    "cognitive": {"timer": "disabled" | "enabled",
                  "ui_clutter": "single_focal_point" | "full_hud",
                  "level_length": "micro" | "extended",
                  "reward_frequency": "instant_per_action" |
                                      "end_of_level"},
    "emotional": {"error_feedback": "gentle_no_red_x" | "standard",
                  "fail_state": "impossible_to_lose" | "standard"}
  }
}

Return ONLY this JSON, nothing else.
"""

GENERATE_GAME_PROMPT = """\
You are generating a single browser-based educational mini-game as part
of Orbit, an adaptive learning platform for children with ADHD. This is
one session in an autonomous pipeline -- work independently, do not ask
the user questions.

CHILD PROFILE (do not deviate from these constraints):
{profile_json}

SKILL: {skill_label} ({skill_id}) -- addition or subtraction only, 3
digits maximum, no negative operands, no negative results, ever.
STARTING DIFFICULTY VECTOR: {initial_difficulty_vector_json}

IMPORTANT ARCHITECTURE NOTE: this game is a RENDERING SHELL, not the
source of difficulty logic. It must call GET
/profiles/{profile_id}/skills/{skill_id}/next-question for every new
question, and POST /attempts with the child's answer every time one is
submitted, and it must forward the `attempt_id` from that response into
the answer_submitted event so telemetry joins back to the stored attempt.
It must NOT implement its own difficulty or correctness logic.
The backend owns question generation and error classification.

TASK
1. Build a single self-contained game at
   games/{profile_id}/{skill_id}/v1/ (index.html + any JS/CSS/asset
   files, no build step -- must run served as static files).
2. Theme it around the child's top-ranked interest ("{top_interest}") --
   e.g. if the interest is trains, have the child combine train cars to
   reach a target number.
3. Apply every constraint in the profile literally. If cognitive.timer
   is "disabled" there must be no visible countdown anywhere. If
   emotional.fail_state is "impossible_to_lose", a wrong answer must
   never end the game or show a failure screen -- only a gentle
   correction, then POST /attempts and show the next question. If
   cognitive.reward_frequency is "instant_per_action", trigger positive
   feedback after every correct answer, not just at the end.
4. Do not over-explain anything in the UI. A math problem is presented
   as the problem itself, not as an instruction to add the numbers.
   Clutter is the primary distraction risk for this population -- the
   baseline is uncluttered, and the profile constraints add back from
   there.
5. Include a visible "Report a problem" button that POSTs a short
   description to /games/{game_id}/report-problem. When the play session
   ends (the session-length question count is reached, or the child
   exits), POST to /games/{game_id}/session-complete -- this is what
   triggers the next version of the game to start being built.
6. Write a design manifest at games/{profile_id}/{skill_id}/v1/design.json
   describing the game you actually built:
   {"mechanic": "...", "goal": "...", "input_mode": "...",
    "theme": "...", "reward_style": "..."}
   (mechanic = the core verb of play, e.g. "stack cargo onto a rocket";
   goal = what the child is trying to achieve; input_mode = how answers
   are physically given, e.g. typed digits / drag-and-drop / clicking
   groups; theme = the fictional setting; reward_style = how success is
   celebrated). Future iterations use this manifest to guarantee the
   next version is a genuinely different game.
7. Instrument with PostHog (project key: {posthog_project_key}, host:
   {posthog_host}). Emit problem_shown, answer_submitted {attempt_id,
   correct, time_to_solve_ms, error_class} (attempt_id and error_class
   both come back from the /attempts response -- forward them into the
   event, do not compute them client-side), idle_tick (every 5s idle),
   edit_event {type:
   immediate_correction if a backspace lands under 1s after the last
   keystroke, after_pause_correction if 2s or more}, motion_event {type:
   micro_jitter for rapid small-radius direction reversals,
   repetitive_orbit for sustained near-zero-net-displacement circular
   motion over roughly a second or more}, level_started,
   level_completed, level_abandoned {progress_pct}. Tag every event with
   game_id={game_id}, profile_id={profile_id}, skill_id={skill_id},
   version=1, and the current difficulty_vector's fields flattened as
   properties.
8. Default session length: {session_length} questions.

SHIPPING GATES -- required before you open a PR, do not skip
- Schema validation: every question object returned by the backend
  during your test run matches {operands, operator, correct_answer,
  difficulty_vector snapshot}
- Assertions: no negative operands, no negative results, no operand over
  3 digits, consistent with SKILL and the difficulty vector
- Headless playthrough: use your browser tool, play at least 3 full
  questions including one deliberately wrong answer, confirm the
  level-complete state is reachable, confirm no console errors
- Render/accessibility: no flashing faster than 3Hz anywhere, visible
  keyboard focus states, readable contrast, every constraint above
  actually visible in the running game
If ANY gate fails, do NOT open a PR -- report the failure in your
structured output instead.

SHIP
Open a pull request (not a direct push to main) with the gate results in
the PR description. Auto-merge it only if every gate passed.

OUTPUT
Return structured JSON (in addition to opening the PR):
{
  "game_path": "games/{profile_id}/{skill_id}/v1/index.html",
  "pr_url": "...",
  "commit_sha": "...",
  "gate_results": {"schema": "...", "assertions": "...",
                    "playthrough": "...", "render_accessibility": "..."},
  "design": {"mechanic": "...", "goal": "...", "input_mode": "...",
              "theme": "...", "reward_style": "..."},
  "summary": "2-3 sentences on what you built and which profile
              constraints shaped which design decisions"
}
"""

ITERATE_PROMPT = """\
You are running the reinvention loop for Orbit, an adaptive learning
platform for children with ADHD. A play session just ended, and every
play session produces the next version of the game. Numeric difficulty
tuning already happened in real time, deterministically, outside this
session -- that is NOT your job here. Your job is to ship a version of
this child's game that is a NOTICEABLY DIFFERENT GAME from the one just
played: the child must recognise their next game as new. Re-tuning
pacing or rewards on the same game is not enough. Do not ask the user
questions -- decide and act.

While you work, the child may play again. If a NEW PLAY DATA message
arrives in this session, fold it in before shipping: re-check your
diagnosis against the updated signals and adjust the design if they
point somewhere new.

THE REINVENTION MANDATE (non-negotiable)
The new version MUST change the core mechanic -- the verb of play -- to
one this child has not seen in any previous version (see DESIGN HISTORY
below), AND change at least one of:
  - the goal structure (what the child is trying to achieve: reach a
    target, rescue something, build something, race something, uncover
    something, feed something)
  - the input modality (how answers are physically given: typed digits,
    drag-and-drop objects, clicking/counting groups, sliders, assembling
    digit tiles, drawing a path through correct answers)
  - the theme (a different one of the child's ranked interests, or a
    fresh setting inside the top interest)
Mechanic ideas to draw from (invent your own too): stacking/loading,
excavating/uncovering, catching falling objects, sorting into bins,
feeding a creature, launching/aiming, building a bridge piece by piece,
trading at a shop, mixing ingredients, repairing a machine part by part.
What stays FIXED across every reinvention: the backend contract (see
below), every profile constraint, the telemetry events, and the math
itself -- the backend still owns questions and correctness.

DESIGN HISTORY (every previous version of this child's game for this
skill -- your new mechanic must not repeat any mechanic listed here, and
the overall design must be visibly distinct from the most recent entry):
{design_history_json}

CHILD PROFILE (must remain respected in any change you make):
{profile_json}

CURRENT GAME: {code_path} (version {current_version})
SKILL: {skill_label} ({skill_id})
CURRENT DIFFICULTY VECTOR (already correct -- treat as ground truth, do
NOT re-tune it yourself): {current_difficulty_vector_json}
RECENT ERROR-CLASS BREAKDOWN (from the last {n} attempts, computed by the
deterministic classifier -- tells you WHAT KIND of mistakes are
happening, structurally, even though the vector already responded to
them): {error_class_breakdown_json}

RECENT TEACHER/PARENT NOTES (teacher notes outweigh parent notes if they
conflict):
{development_notes_text}

CHILD-REPORTED PROBLEMS (from the in-game "report a problem" button --
treat these as high priority, explicit signals from the child):
{reported_problems_text}

PRECOMPUTED SIGNALS (ground truth -- do not recompute these yourself)
The backend already folded this version's telemetry into named signals with
the same arithmetic this prompt used to ask you to do by hand, so that the
same session always reads the same way and can be regression-tested offline
(app/telemetry_signals.py). Treat them as given:
{telemetry_signals_json}

The reinvention still ships whatever the dominant signal is -- the
mandate is unconditional. The signals decide the KIND of game you build:
if `dominant_signal` is "healthy_struggle" or "inconclusive", keep the new
game's cognitive demands and pacing equivalent to the current version's
while changing the mechanic, and say so in your diagnosis. Disagree with
the summarizer only if PostHog shows something it could not see, and say
explicitly what that was.

POSTHOG ACCESS (for detail the signals above do not cover)
A read-only PostHog personal API key is available in this session as the
secret POSTHOG_PERSONAL_API_KEY (never print its value). Project id:
{posthog_project_id}. Host: {posthog_host}. Query the PostHog HTTP API
yourself for events tagged game_id={game_id}, profile_id={profile_id},
version={current_version} since {since_timestamp}. Compute: idle ratio,
the ratio of immediate_correction to after_pause_correction edit events,
counts of micro_jitter vs. repetitive_orbit motion events, rage-click and
level_abandoned counts, and apply this disengagement check per question:

    disengaged =
        error_class == unclassified
        AND latency > 3x the child's baseline for this difficulty tier
        AND micro_jitter ~ 0
        AND difficulty <= recently mastered level

A confused child jitters and edits after a pause. A bored child goes
still. Stillness plus an unrecoverable answer on material that isn't hard
is the signal that the GAME has failed, not the math.

Note: repetitive_orbit means disengagement OR stimming depending on the
profile's restlessness_interpretation field. If it is "self_regulation", do not
read orbiting as disengagement.

REFERENCE (your primary framework; deviate if the evidence clearly points
elsewhere). Every iteration reinvents the game -- these signals decide
what KIND of game to build next:
| Signal | Meaning | What the new design should do |
|---|---|---|
| High idle ratio + disengagement pattern on non-hard material | Bored with the game, not the math | A faster, more kinetic mechanic with instant per-action feedback and tighter pacing (PRESENTATION) |
| Frequent fast + incorrect answers | Impulsive guessing | An input modality where committing an answer takes deliberate physical steps, plus a ~2.5s gentle cooldown after a wrong answer (CONTENT) |
| Rage clicks / abandoned levels / a reported problem describing a bug | Frustration, or a real bug | Make sure the described bug's cause cannot recur in the new game; no fail-state UI; shorter levels |
| High micro_jitter + high after-pause-edit rate | Genuinely engaged, working hard | Keep the new game's cognitive demands at the same level -- reinvent the surface, do not soften the work |
| High time-to-solve on CORRECT answers, repeatedly | Working-memory bottleneck, not a math gap | A mechanic whose objects are countable and manipulable -- draggable pieces instead of typed digits (STRUCTURAL) |

TASK
1. Read the precomputed signals. Query PostHog only for context they do not
   cover (e.g. which questions the idles clustered around).
2. Read the error-class breakdown, teacher/parent notes, and reported
   problems for additional context -- a note like "rough week at home"
   should make you cautious about reading one bad session as regression.
3. Design the new game: pick the new mechanic, goal, input modality and
   theme per the reinvention mandate, and let the telemetry steer the
   choice -- e.g. boredom signals argue for a faster, more kinetic
   mechanic; working-memory signals argue for a mechanic whose objects
   are countable and manipulable; impulsive guessing argues for an input
   modality that takes deliberate physical steps to commit an answer.
   Fix any child-reported bug's underlying cause in the new game.
4. Read the current game code at {code_path} for the backend contract
   and telemetry wiring, then build the new game from its own design.
   Keep every profile constraint intact. The game stays a RENDERING
   SHELL: it must fetch every question from GET
   /profiles/{profile_id}/skills/{skill_id}/next-question and submit
   every answer to POST /attempts. Do not change the difficulty vector,
   the question generator, or the error classifier -- those live in the
   backend and are not yours. Keep the "Report a problem" button, the
   end-of-play-session POST to /games/{game_id}/session-complete (with
   the NEW game's id -- it triggers the version after this one), and
   the full PostHog event set, with version={new_version}.
5. Write the new game to
   games/{profile_id}/{skill_id}/v{new_version}/ where new_version =
   {current_version} + 1, including a design.json manifest:
   {"mechanic": "...", "goal": "...", "input_mode": "...",
    "theme": "...", "reward_style": "..."}
6. Re-run the exact shipping gates from generation: schema validation,
   assertions, headless playthrough, render/accessibility check. Then
   run the fifth gate, novelty: state the new mechanic, confirm it
   appears nowhere in the design history, and name which of goal /
   input modality / theme also changed. If the game is the previous
   version re-skinned, the novelty gate FAILS.
7. Open a pull request with the gate results in the description.
   Auto-merge only if every gate passed; otherwise leave it open and
   report the failure.

OUTPUT
Return structured JSON:
{
  "diagnosis": "one paragraph: which signal(s) dominated and why they
                point at the design you chose",
  "change_tier": "content" | "presentation" | "structural",
  "changes_made": ["short bullet", "short bullet", "..."],
  "game_path": "games/{profile_id}/{skill_id}/v{new_version}/index.html",
  "pr_url": "...",
  "commit_sha": "...",
  "gate_results": {"schema": "...", "assertions": "...",
                    "playthrough": "...", "render_accessibility": "...",
                    "novelty": "..."},
  "design": {"mechanic": "...", "goal": "...", "input_mode": "...",
              "theme": "...", "reward_style": "..."},
  "before_after_diff_summary": "2-3 sentences a non-technical teacher
                                 could read, saying what the new game IS
                                 and how it differs from yesterday's"
}
"""


def revision(template: str) -> str:
    """A short, stable fingerprint of the prompt text itself, before filling."""
    return hashlib.sha256(template.encode()).hexdigest()[:12]


def render(template: str, **values: object) -> str:
    """Fill `{placeholder}` slots without touching the JSON braces around them."""
    filled = template
    for key, value in values.items():
        filled = filled.replace("{" + key + "}", str(value))
    return filled
