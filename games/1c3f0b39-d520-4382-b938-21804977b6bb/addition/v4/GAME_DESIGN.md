# Game Design Document — Orbit Tug v4

Archetype: `ui_heavy` content (equation production) running inside a `top_down`-style
arena loop. Philosophy: config-first, hook-driven, no framework, no build step.

Design vocabulary is borrowed from OpenGame (`agent-test/docs/modules/top_down/template_api.md`,
`BaseArenaScene.ts`, `ScreenEffectHelper.ts`, `UIScene.ts`, `docs/debug_protocol.md`) and
re-expressed in vanilla ES2015, because Orbit's generation contract requires a static bundle
that runs with no build step and no external image or audio assets.

---

## 0. Technical Architecture

- Resolution: logical 960x600, scaled to the canvas element and `devicePixelRatio`; the scene
  letterboxes rather than reflows inside one bounded, chrome-framed stage centred in the
  viewport. The stage has a HUD band above the canvas and a controls band below it.
- Runtime: one `requestAnimationFrame` loop, fixed 1/60 s simulation step with an accumulator,
  max 4 catch-up steps per frame (borrowed from `BaseArenaScene.updateSpawner`'s
  delta-accumulator discipline).
- No Phaser, no Vite, no Tailwind, no raster assets, no audio files. All graphics are canvas 2D
  vector primitives; all sound is Web Audio oscillators.
- Served by FastAPI from `games/1c3f0b39-d520-4382-b938-21804977b6bb/addition/v4/`.

Scene flow (OpenGame Pattern B, "Story + Battle", recommended for educational):

```
TitleScene -> IntroScene -> PlayScene -> CompleteScene
```

`SCENE_ORDER = ["title", "intro", "play", "complete"]`. Every key used in `Runner.start(key)`
is in that array; `SCENE_ORDER[0]` is `"title"`.

Files:

| File           | Role                                                                     |
| -------------- | ------------------------------------------------------------------------ |
| `index.html`   | Canvas element, HUD layer, dialog markup, script order                   |
| `styles.css`   | Palette tokens, stage shell, HUD bands, depth scale, focus states      |
| `config.js`    | `window.ORBIT`: identity, constraints, and the whole `TUNING` block       |
| `effects.js`   | `Effects` — constraint-gated juice (shake / trail / burst / floating text) |
| `hud.js`       | `Hud` — parallel HUD layer, never drawn on canvas                        |
| `scenes.js`    | `Runner` + the four scenes + `Session` (question flow)                   |
| `game.js`      | Actor, environment layers, input, bootstrap                              |
| `telemetry.js` | PostHog wiring and behavioural classification (carried over from v3)      |

Ownership boundary is unchanged: the backend owns question generation, correctness and error
classification. `PlayScene` calls `GET /profiles/{profile_id}/skills/{skill_id}/next-question`
for every question and `POST /attempts` for every answer, and forwards `error_class` verbatim.

---

## 1. Procedural Draw Registry

Style anchor: a quiet vacuum-blue depth field where one pastel tug drifts toward a docking
ring, everything drawn from soft-edged vector primitives, nothing brighter than the equation.

| Layer | Depth | Drawable      | Primitive                                                        | Palette token           | Motion                                  |
| ----- | ----- | ------------- | ---------------------------------------------------------------- | ----------------------- | --------------------------------------- |
| base  | 0     | `deepField`   | vertical linear gradient + one very soft radial bloom            | `--space-far`/`--space-near` | none                                |
| mid   | 1     | `orbitRing`   | dashed ellipse approach guide, 1.5px, 22% alpha                  | `--edge`                | none                                    |
| mid   | 2     | `dockPad`     | labelled ring with two guide ticks and `Dock`/`Docked` hub text   | `--accent`              | 0.9 s alpha breathe, 0.18–0.30          |
| mid   | 3     | `starsFar`    | 60 dots r=0.8, alpha 0.25                                        | `--ink`                 | drift 6 px/s                            |
| mid   | 4     | `starsMid`    | 28 dots r=1.2, alpha 0.35                                        | `--ink`                 | drift 14 px/s                           |
| actor | 5     | `tug`         | hull polygon + cabin arc + two thruster trapezoids + nose accent | `--warm`/`--accent`     | pointer inertia, idle bob, heading lerp |
| actor | 6     | `starsNear`   | 12 dots r=1.8, alpha 0.4                                         | `--ink`                 | drift 26 px/s                           |
| actor | 7     | `pod`         | small hexagon carried under the hull                             | `--good`                | slides to `dockPad` on a correct answer |

Palette tokens keep v3's values (`--ink #f4f6ff`, `--dim #aab3dd`, `--panel rgba(22,26,46,.82)`,
`--panel-solid #161a2e`, `--edge #3c4570`, `--accent #9fb6f0`, `--good #bfe3c8`,
`--warm #f2d9b0`), which satisfy `visual.color_palette: pastel_muted` and pass contrast against
the field gradient. The stage, equation banner, answer field, and report dialog use muted
surfaces; the answer field and report dialog use opaque `--panel-solid` so moving canvas art
never passes behind readable text.

Presentation hierarchy is deliberate: one rounded stage frames three horizontal bands (equation
and neutral progress dots above, play canvas in the middle, answer controls and feedback below).
The equation is a bordered, padded chip using letter-spaced tabular/monospace digits and remains
the single focal point. The dock target keeps its ring, adds the dashed approach guide and a
short hub label, and changes `Dock` to `Docked` after a pod lands. No score, extra counters,
theme/sound/fullscreen controls, or other competing focal elements are present.

Audio registry (Web Audio, no files), only when `audio.sfx !== "none"`:

| Sound   | Shape                                     | When                       |
| ------- | ----------------------------------------- | -------------------------- |
| `tap`   | sine 660 Hz, 60 ms, gain 0.05             | submit / thematic action   |
| `dock`  | triad 523/659/784 Hz, 220 ms, gain 0.05   | correct answer             |
| `settle`| sine 196 Hz, 260 ms, gain 0.04            | gentle correction          |

No continuous music, ever, because `audio.music === false`.

---

## 2. Configuration (config-first — no numbers in scene code)

`config.js` gains a `TUNING` object. Every value below is a literal to write; scene and actor
code reads `T.<path>` and never inlines a number.

```
TUNING = {
  loop:   { logicalWidth: 960, logicalHeight: 600, stepMs: 16.6667, maxCatchUpSteps: 4 },
  actor:  { followLerp: 0.08, maxSpeedPxPerSec: 420, headingLerp: 0.12,
            bobAmplitudePx: 4, bobPeriodMs: 3200, edgePaddingPx: 48,
            idleAfterMs: 1200 },
  effects:{ shakeLightMs: 200, shakeLightPx: 3, shakeMediumMs: 400, shakeMediumPx: 7,
            trailCount: 5, trailDelayMs: 60, trailAlpha: 0.35, trailFadeMs: 300,
            burstCount: 12, burstSpreadPx: 46, burstMs: 420 },
  stars:  { far: { count: 60, radius: 0.8, alpha: 0.25, driftPxPerSec: 6 },
            mid: { count: 28, radius: 1.2, alpha: 0.35, driftPxPerSec: 14 },
            near:{ count: 12, radius: 1.8, alpha: 0.40, driftPxPerSec: 26 } },
  dock:   { podTravelMs: 520, padBreatheMs: 900, padAlphaMin: 0.18, padAlphaMax: 0.30,
            approachRadiusX: 174, approachRadiusY: 56, guideDash: [8, 12],
            guideAlpha: 0.22, ringRadius: 78, guideTickInner: 78, guideTickOuter: 96,
            labelFontPx: 16, guideLineWidth: 1.5, ringLineWidth: 7, tickLineWidth: 2 },
  feedback: { floatRisePx: 42, floatMs: 900, holdMs: 1200 },
  intro:  { typewriterMsPerChar: 28 },
  audio:  { tapHz: 660, tapMs: 60, chordHz: [523, 659, 784], chordMs: 220,
            settleHz: 196, settleMs: 260, gain: 0.05 },
  hud:    { dotRadiusPx: 7, dotGapPx: 18 },
  net:    { requestTimeoutMs: 8000 },
  idle:   { tickMs: 5000 }
}
```

Depth scale (single source of truth, mirrored in `styles.css`):
canvas `0` < HUD `150` < dialog overlay `300` < help/hint `500`.

The stage is centred and chrome-framed with a rounded border and subtle shadow. Its three bands
are horizontal: the equation/progress HUD above, the fixed logical canvas in the middle, and the
answer field/Send/feedback controls below. CSS explicitly applies `[hidden] { display: none
!important }` to prevent hidden scene panels from resurfacing.

---

## 3. Scene, Actor and Component Architecture

### 3.1 The only hooks that exist

Hook-integrity rule (from OpenGame's template API): a scene may override **only** these. Any
other name does not exist.

| Hook              | Signature            | Purpose                                                             |
| ----------------- | -------------------- | ------------------------------------------------------------------- |
| `onPreCreate()`   | `(): void`           | Reset per-entry mutable state before anything is built              |
| `onCreate()`      | `(): void`           | Build scene-owned DOM/canvas state (required)                       |
| `onPostCreate()`  | `(): void`           | Attach listeners, fire entry telemetry, focus management            |
| `onUpdate(dt)`    | `(dt: number): void` | Fixed-step simulation                                               |
| `onDraw(ctx)`     | `(ctx): void`        | Draw this scene's layers in registry order                          |
| `onExit()`        | `(): void`           | Remove every listener and destroy every element `onCreate` produced |

`Runner` owns the loop, the canvas resize/DPR handling, and scene switching; it calls
`onExit()` on the outgoing scene before `onPreCreate()` on the incoming one, and it re-enters
scenes cleanly (no state may survive an exit — this is the Phaser "scene instances are reused"
trap from the debug protocol, and it is why `onPreCreate` exists at all).

### 3.2 Scenes

| Scene           | Overrides                                                | Behaviour                                                                                                             |
| --------------- | -------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `TitleScene`    | `onCreate`, `onDraw`, `onPostCreate`, `onExit`            | Field + ring drawn behind one line of copy and a Start button; Enter or click advances. No animation faster than 3 Hz. |
| `IntroScene`    | all six                                                  | Two typewriter lines (`DialogueBox` component), Enter/click advances, skippable; emits `level_started` on leaving.     |
| `PlayScene`     | all six                                                  | Owns `Session`; drives actor, pod, HUD banner and feedback; the only scene that talks to the API.                      |
| `CompleteScene` | `onCreate`, `onDraw`, `onPostCreate`, `onExit`            | "That's all ten." plus the tug parked in the ring; emits `level_completed`. No score, no rating, no retry pressure.    |

### 3.3 `Session` (logic only, no rendering)

Mirrors OpenGame's `systems/` split (managers hold state, scenes render). API:
`start()`, `current()`, `submit(rawText)`, `retry()`, `progress()`, `isComplete()`.
Rules:

- `stop()` aborts any in-flight request and latches a stopped flag; a response that lands after
  the scene exited must touch neither the HUD nor telemetry.
- The answer field is cleared as each new question is shown, and focus stays in it.
- `submit` is a no-op while a request is in flight (single-flight guard) and while there is no
  active question — in that state it retries the fetch instead, so a dropped question can
  never be re-submitted (the v3 review fix, preserved).
- A failed `next-question` clears the active question and surfaces the lost-signal banner.
- A failed `POST /attempts` keeps the question active, re-enables Send, and surfaces the same
  banner with retry copy — this branch must be reachable and is a required gate this time.
- Non-digit input never reaches the API; it produces the gentle hint in §4.

### 3.4 Actor behaviours (composed, one concern each)

| Behaviour      | Config                                          | Purpose                                              |
| -------------- | ----------------------------------------------- | ---------------------------------------------------- |
| `PointerFollow`| `followLerp`, `maxSpeedPxPerSec`, `edgePaddingPx`| Velocity toward pointer with inertia; clamped inside the logical bounds (screen-bounds clamping from `BaseArenaScene.setupScreenBounds`) |
| `IdleBob`      | `bobAmplitudePx`, `bobPeriodMs`, `idleAfterMs`   | Slow sine bob, faded in only once the pointer has been still for `idleAfterMs` |
| `HeadingAlign` | `headingLerp`                                   | Hull rotates toward the velocity vector              |
| `DockAction`   | `podTravelMs`                                   | On a correct answer, releases the pod toward the pad |

### 3.5 `Effects` — constraint-gated juice

Structural port of `ScreenEffectHelper`: same preset shape, but each preset resolves to a no-op
at construction when the child's constraints forbid it. This is the part that makes the module
reusable across profiles rather than hard-coded for one child.

| Preset                      | Gate                                                | Leo's profile |
| --------------------------- | --------------------------------------------------- | ------------- |
| `shakeLight/Medium`         | `visual.animations !== "minimal_no_screen_shake"`    | disabled      |
| `trail(actor)`              | `visual.particle_effects === true`                   | disabled      |
| `burst(x, y)`               | `visual.particle_effects === true`                   | disabled      |

Each preset must be fully implemented, not a stub that happens never to run for this child:
`shake*` offsets the scene transform by `shake*Px` for `shake*Ms` and restores it exactly;
`trail` drops `trailCount` fading hull silhouettes at `trailDelayMs` spacing (`trailAlpha`,
`trailFadeMs`); `burst` throws `burstCount` pastel dots across `burstSpreadPx` over `burstMs`.
The gate decides whether they run for a given profile — it is not a substitute for the effect.
Shake is bound to positive impact (a pod docking) only. It must never fire on a wrong answer:
for any profile that permits shake, jolting the screen on a mistake is exactly the punitive
feedback `gentle_no_red_x` / `impossible_to_lose` rules out.

| `floatText(text, tone)`     | always available (text feedback, not a particle)     | enabled       |
| `tap` / `dock` / `settle`   | `audio.sfx !== "none"`                               | enabled       |

`floatText` uses a rise-and-fade (`floatRisePx`, `floatMs`, cubic ease-out) — never a damage
number, never red, never a streak label.

### 3.6 `Hud` — parallel layer, not canvas

Port of `UIScene`'s idea: the HUD is a sibling DOM layer with `pointer-events: none` (its
controls re-enable pointer events individually) that reads game state each frame instead of
being drawn into the scene. Components:

| Component        | Content                                                            |
| ---------------- | ------------------------------------------------------------------ |
| `EquationBanner` | The single focal point: `837 + 821`, plus an SR-only text mirror    |
| `AnswerField`    | `<input type="text" inputmode="numeric" pattern="[0-9]*" maxlength="4">` and Send |
| `ProgressTrack`  | Ten dots, filled in neutral accent as questions are answered — no colour-coded right/wrong, no counter, no score |
| `FeedbackSlot`   | One line, one tone class (`good` / `gentle` / `hint`)               |
| `ReportButton`   | Opens `ReportDialog`                                               |
| `ReportDialog`   | Textarea + Send + Close, `role="dialog"`, `aria-modal`, **Escape closes, focus is trapped, focus returns to the button** |

The answer form sets `noValidate` so the browser never replaces the game's voice with a native
pattern-validation bubble. The client keeps `pattern="[0-9]*"` for mobile numeric keyboards,
validates production input itself, and shows the visible gentle "Numbers only" hint. The answer
field is cleared and refocused for every new question. Its fill is opaque `--panel-solid`, as is
the report-dialog surface, so live canvas art cannot show through readable controls.

Absent by design: clock, countdown, timer bar, HP bar, score, streak meter, pause. `cognitive.timer`
is `disabled` and `fail_state` is `impossible_to_lose`, so none of them may exist.

---

## 4. Content Design

Intro lines (typewriter, `intro.typewriterMsPerChar`):

1. "Ten pods to dock."
2. "Type the number, press Send."

Feedback copy:

| Case               | Copy                                            | Tone     | Sound    |
| ------------------ | ----------------------------------------------- | -------- | -------- |
| Correct            | "Docked."                                       | `good`   | `dock`   |
| Wrong              | "Almost — it was {correct_answer}. Next one."    | `gentle` | `settle` |
| Non-digit input    | "Numbers only — try 0 to 9."                    | `hint`   | none     |
| Next question lost | "Lost the signal. Press Send to try again."     | `gentle` | none     |
| Attempt POST lost  | "That didn't send. Press Send to try again."    | `gentle` | none     |
| Report sent        | "Sent. Thanks."                                 | `good`   | none     |
| Report failed      | "Could not send."                               | `gentle` | none     |

Completion copy: "That's all ten." — nothing else. It must not claim ten pods docked, because a
wrong answer docks no pod and the copy would then contradict the ring. No stars, no percentage, no "try to beat it".

Telemetry is unchanged from v3 and must keep firing: `problem_shown`, `answer_submitted`
(`correct`, `time_to_solve_ms`, `error_class` verbatim from the response), `idle_tick` every
5 s idle, `edit_event` (`immediate_correction` < 1 s, `after_pause_correction` >= 2 s, scoped to
the answer field only), `motion_event` (`micro_jitter`, `repetitive_orbit`), `level_started`,
`level_completed`, `level_abandoned` with `progress_pct` (share of questions *answered*, not
pods docked, and emitted at most once per session). Every event carries `game_id`,
`profile_id`, `skill_id`, `version: 4` and the flattened difficulty vector.

---

## 5. Implementation Roadmap

1. `cp` v3's `telemetry.js` into `v4/`, change `VERSION` handling to read from config only.
2. NEW `config.js`: identity block (v3 values, `VERSION: 4`, `GAME_ID` from the new row),
   Leo's constraints verbatim, and the full `TUNING` block from §2.
3. NEW `effects.js`: `Effects.create(constraints, tuning)` returning the gated preset object (§3.5).
4. NEW `hud.js`: the components in §3.6, including the Escape/focus-trap dialog.
5. NEW `scenes.js`: `Runner`, the six-hook base scene, `SCENE_ORDER`, the four scenes, `Session`.
6. NEW `game.js`: actor + behaviours (§3.4), the three star layers, environment draw functions
   from the registry (§1), pointer/keyboard input, bootstrap that starts `SCENE_ORDER[0]`.
7. NEW `index.html` / `styles.css`: canvas + HUD layer + dialog, palette tokens, depth scale,
   `[hidden] { display: none !important }`, visible 3px focus rings.
8. Create the v4 game row (`version 4`, `status ready`, `is_live false`) and paste its id into
   `config.js`. No promotion.

---

## 6. Pre-Ship Checklist (adapted debug protocol) + Orbit Gates

Structural (from `docs/debug_protocol.md`, translated to this bundle):

- [ ] Every key passed to `Runner.start()` exists in `SCENE_ORDER`; `SCENE_ORDER[0] === "title"`.
- [ ] Every `T.` path read by code exists in `TUNING` (grep the paths).
- [ ] No numeric literal in scene/actor code that belongs in `TUNING`.
- [ ] Every listener added in `onPostCreate` is removed in `onExit`; re-entering a scene twice
      leaks no listeners and duplicates no DOM.
- [ ] Every element created in `onCreate` is destroyed in `onExit` before recreation.
- [ ] Depth order holds: canvas < HUD < dialog < hint.
- [ ] No leftover placeholder (`GAME_ID_PLACEHOLDER`, `TODO`).
- [ ] `Effects` presets are no-ops under Leo's constraints, verified by call, not by reading.

Orbit shipping gates (unchanged, all four required, no PR if any fails):

- [ ] Schema: every question object matches `{operands, operator, correct_answer, difficulty_vector_snapshot}`.
- [ ] Assertions: no negative operand or result, no operand over three digits, consistent with skill and vector.
- [ ] Playthrough: at least three questions in a real browser including one deliberate wrong
      answer, gentle correction shown, completion reachable, no console errors.
- [ ] Render/accessibility: nothing flashing above 3 Hz, visible focus states, readable contrast,
      every profile constraint visibly respected.

Additionally required this time, because v3 shipped with them open:

- [ ] The failed-`POST /attempts` banner is triggered and observed (fail the endpoint deliberately).
- [ ] Escape closes the report dialog, Tab cannot leave it, focus returns to the report button.
- [ ] Invalid input produces the visible "Numbers only" hint instead of silence.
