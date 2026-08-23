---
name: orbit-frontend-design
description: Design standard for Orbit's generated child-facing games and any new Orbit frontend — layout shell, focal hierarchy, feedback and telemetry rules, and the pre-ship checks that rendered testing keeps catching. Use when building or reviewing a game bundle under games/{profile_id}/{skill_id}/v{n}/ or any new Orbit UI.
---

# Orbit frontend design standard

Defaults to reason from, not a template to copy. Every child profile can justify a deviation;
nothing here outranks a profile constraint. When a rule and a constraint disagree, the
constraint wins and the deviation gets written down in the bundle's GAME_DESIGN.md.

## 1. Layout shell

- One bounded, chrome-framed stage (rounded card, own border and shadow) centred in the page,
  rather than a full-bleed canvas. The frame is what makes it read as a made thing rather than
  a raw canvas, and it gives the HUD somewhere to live that is not on top of the play area.
- Screens are sibling panels toggled with the `hidden` attribute, one visible at a time
  (title / intro / play / complete). Any CSS `display` on the panel class must be defeated by
  an explicit `[hidden] { display: none !important }` rule — a `display: grid` on the base
  class silently overrides native hiding, which has already shipped as a bug once.
- Three horizontal bands inside the stage: HUD banner on top, canvas in the middle, controls
  below. The child never has to look in two places to know what to do.
- Fixed logical canvas size, scaled responsively, with device-pixel-ratio handling.

## 2. Focal hierarchy

- The equation is the single focal point and gets real chrome: a bordered, high-contrast banner
  chip with generous padding, monospace or tabular digits, and letter spacing. Floating text on
  the canvas is not enough — the chip is what makes the maths, not the spaceship, the thing the
  child looks at.
- The goal is a labelled target, not a bare shape: draw the destination with its own ring, an
  orbit/approach guide, and a short word on it, and change that word on success. A 7-year-old
  should be able to tell where the pod is going without being told.
- Everything else is subordinate: one input, one submit, one feedback line, one report affordance.
- No score. No high score, no combo, no streak meter, no "Missions 3/10" alongside a progress
  track that already says it. Progress is one neutral track of dots and nothing else. A score is
  a fail-adjacent pressure signal even when it only goes up.
- Controls that are not the task (theme switchers, sound toggles, fullscreen buttons) do not
  belong on a single-focal-point screen.

## 3. Feedback and failure

- Wrong answers continue the session, name the correct answer gently, and never use red, an X,
  a buzzer, or a failure sound.
- Screen shake and particle bursts are bound to positive impact only, and only when the profile
  permits them. Never shake on a mistake, for any profile: jolting the screen on a wrong answer
  is punitive feedback whatever the constraint block says.
- Effect helpers must be genuinely implemented and then gated by constraint. A gate around an
  empty function is not an implementation — the next profile that permits juice gets nothing.
- Progress advances on every answered question, right or wrong. Tying progress to correctness
  means a struggling child can never reach the end of a session.
- Completion copy must not assert something the play state contradicted ("All ten docked" after
  nine docked). Say the neutral true thing.

## 4. Input

- Free numeric production: `<input type="text" inputmode="numeric" pattern="[0-9]*" maxlength="4">`.
  No multiple choice, no client-side distractors — the backend error classifier needs the digits
  the child actually produced.
- Set `noValidate` on the form and do the validation yourself. `pattern` plus `required` hands the
  child Chrome's "Please match the requested format" bubble, which is both harsh and untranslated
  into the game's voice. Keep `pattern` for the mobile keypad; never let it gate submission.
- Invalid input gets a visible, gentle, in-voice hint. Silent rejection reads as "broken".
- The answer field is cleared as each new question appears and keeps focus.
- Give the input an opaque background. A translucent field over a live canvas puts moving art
  behind the digits the child is trying to read.

## 5. Backend ownership

- The game is a rendering shell. Every question comes from
  `GET /profiles/{profile_id}/skills/{skill_id}/next-question`; every answer goes to
  `POST /attempts`; `error_class` is forwarded verbatim from the response.
- No correctness logic, no difficulty logic, no distractor generation in the client, ever.
- Every request is abortable and time-bounded, and a scene teardown aborts in flight and latches
  a stopped flag: a late response must not touch a HUD that no longer exists.
- Network failures speak to the child, not about the API. No status codes, no exception text.
  Keep the question active and re-enable Send so the action is retryable.

## 6. Telemetry

- Emit the full suite: `problem_shown`, `answer_submitted`, `idle_tick`, `edit_event`,
  `motion_event`, `level_started`, `level_completed`, `level_abandoned`.
- Tag every event with game/profile/skill/version and the flattened difficulty vector.
- `level_abandoned` fires from `visibilitychange` and `pagehide`, at most once per session, with
  `progress_pct` from questions answered. `beforeunload` alone does not fire reliably on mobile.
- Scope input instrumentation to the answer field. Typing in a report box is not an answer edit.
- Telemetry never throws into gameplay.

## 7. Pre-ship checks

Structural, from OpenGame's debug protocol:

- Every scene key referenced exists in the scene order; no placeholder ids or TODO tokens.
- Every tuning path resolves against the config object; no magic numbers in gameplay code.
- Re-enter the play scene three times: listener adds equal removes, DOM node counts stable.
- State mutation stays out of the draw path.

Rendered, in a real browser against the real backend — these are the ones reading the code does
not catch, and each has caught a shipped defect:

- Play several questions including a deliberate wrong answer, and reach completion.
- Invalid input, and confirm it is *your* hint on screen rather than a native browser bubble.
- Fail `POST /attempts` deliberately and observe the retry banner.
- Escape closes the report dialog, Tab cannot leave it, focus returns to the opener.
- Screenshot the play screen and look at it: nothing overlapping the equation or the input,
  no panel visible that should be hidden, no colour that contradicts the profile palette.
- Console empty.
