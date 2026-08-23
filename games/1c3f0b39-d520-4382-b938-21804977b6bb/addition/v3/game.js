// Orbit Tug --- a rendering shell. Every question comes from the backend and
// every answer goes back to it; nothing here decides difficulty or correctness.
//
// The scene is drawn procedurally at 60fps on one canvas: a tug that follows
// the pointer with inertia, a station ring it delivers pods to, and the
// equation itself as the scene's focal point. Which effects exist at all is
// decided by ORBIT.CONSTRAINTS, not by taste.
(function () {
  const C = window.ORBIT;
  const V = C.CONSTRAINTS.visual;
  const A = C.CONSTRAINTS.audio;
  const E = C.CONSTRAINTS.emotional;

  const SHAKE_ALLOWED = V.animations !== "minimal_no_screen_shake";
  const BURSTS_ALLOWED = V.particle_effects === true;
  const SFX_ALLOWED = A.sfx !== "none";
  const GENTLE = E.fail_state === "impossible_to_lose";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // --- pastel_muted palette -------------------------------------------------
  const PALETTE = {
    deep: "#161a2e",
    high: "#232a4a",
    ring: "#5d6796",
    marks: "#3c4570",
    star: "#cfd6f5",
    hull: "#e5e9fb",
    hullEdge: "#9aa4d2",
    pod: "#f2d9b0",
    podDocked: "#bfe3c8",
    text: "#f4f6ff",
  };

  // --- Web Audio: three synthesised UI sounds, no music --------------------
  const Sound = (function () {
    let ctx = null;

    function resume() {
      if (!SFX_ALLOWED) return;
      if (ctx === null) {
        const Ctor = window.AudioContext || window.webkitAudioContext;
        if (!Ctor) return;
        ctx = new Ctor();
      }
      if (ctx.state === "suspended") ctx.resume();
    }

    function tone(freq, start, duration, peak, type) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = type || "sine";
      osc.frequency.value = freq;
      const t0 = ctx.currentTime + start;
      gain.gain.setValueAtTime(0, t0);
      gain.gain.linearRampToValueAtTime(peak, t0 + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
      osc.connect(gain).connect(ctx.destination);
      osc.start(t0);
      osc.stop(t0 + duration + 0.02);
    }

    return {
      resume: resume,
      // The thematic action: a short soft pop as the pod leaves the tug.
      launch: function () {
        if (!SFX_ALLOWED || ctx === null) return;
        tone(320, 0, 0.12, 0.12, "triangle");
      },
      // Correct: a major chord, arriving rather than announcing.
      docked: function () {
        if (!SFX_ALLOWED || ctx === null) return;
        [523.25, 659.25, 783.99].forEach(function (f, i) {
          tone(f, i * 0.05, 0.5, 0.08, "sine");
        });
      },
      // Wrong: one warm low tone. Not a buzzer, not a failure.
      gentle: function () {
        if (!SFX_ALLOWED || ctx === null) return;
        tone(196, 0, 0.4, 0.09, "sine");
      },
    };
  })();

  // --- scene ---------------------------------------------------------------
  const canvas = document.getElementById("scene");
  const ctx = canvas.getContext("2d");

  const scene = {
    w: 0,
    h: 0,
    // The tug chases the pointer; inertia is what makes it feel piloted.
    tug: { x: 0, y: 0, vx: 0, vy: 0, heading: -Math.PI / 2 },
    target: { x: 0, y: 0 },
    dock: { x: 0, y: 0, r: 0 },
    stars: [],
    pod: null,
    docked: 0,
    glow: 0,
    equation: "",
    bob: 0,
  };

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    scene.w = window.innerWidth;
    scene.h = window.innerHeight;
    canvas.width = Math.floor(scene.w * dpr);
    canvas.height = Math.floor(scene.h * dpr);
    canvas.style.width = scene.w + "px";
    canvas.style.height = scene.h + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    scene.dock.x = scene.w / 2;
    scene.dock.y = scene.h * 0.3;
    scene.dock.r = Math.max(64, Math.min(scene.w, scene.h) * 0.13);

    if (scene.tug.x === 0 && scene.tug.y === 0) {
      scene.tug.x = scene.w / 2;
      scene.tug.y = scene.h * 0.74;
      scene.target.x = scene.tug.x;
      scene.target.y = scene.tug.y;
    }

    const count = Math.round((scene.w * scene.h) / 26000);
    scene.stars = [];
    for (let i = 0; i < count; i++) {
      scene.stars.push({
        x: Math.random() * scene.w,
        y: Math.random() * scene.h,
        r: 0.6 + Math.random() * 1.4,
        drift: 2 + Math.random() * 8,
        alpha: 0.12 + Math.random() * 0.22,
      });
    }
  }

  window.addEventListener("resize", resize);

  window.addEventListener(
    "pointermove",
    function (event) {
      scene.target.x = event.clientX;
      scene.target.y = event.clientY;
    },
    { passive: true }
  );

  function drawBackground() {
    const grad = ctx.createLinearGradient(0, 0, 0, scene.h);
    grad.addColorStop(0, PALETTE.high);
    grad.addColorStop(1, PALETTE.deep);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, scene.w, scene.h);
  }

  function drawStars(dt) {
    // Ambient drift: the only motion that is never gated, because it carries
    // no information and never asks for attention.
    ctx.save();
    for (let i = 0; i < scene.stars.length; i++) {
      const s = scene.stars[i];
      if (!reduceMotion) {
        s.x += s.drift * dt;
        if (s.x > scene.w + 2) s.x = -2;
      }
      ctx.globalAlpha = s.alpha;
      ctx.fillStyle = PALETTE.star;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawStation() {
    const d = scene.dock;

    ctx.save();
    ctx.strokeStyle = PALETTE.marks;
    ctx.lineWidth = 1.5;
    ctx.globalAlpha = 0.7;
    ctx.beginPath();
    ctx.ellipse(d.x, d.y, d.r * 2.1, d.r * 0.62, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = PALETTE.ring;
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2);
    ctx.stroke();

    // Docked pods accumulate around the ring: the progress you can see.
    for (let i = 0; i < scene.docked; i++) {
      const angle = -Math.PI / 2 + (i * Math.PI * 2) / C.SESSION_LENGTH;
      ctx.fillStyle = PALETTE.podDocked;
      ctx.beginPath();
      ctx.arc(d.x + Math.cos(angle) * d.r, d.y + Math.sin(angle) * d.r, 7, 0, Math.PI * 2);
      ctx.fill();
    }

    if (scene.glow > 0) {
      ctx.globalAlpha = scene.glow * 0.5;
      ctx.strokeStyle = PALETTE.podDocked;
      ctx.lineWidth = 10;
      ctx.beginPath();
      ctx.arc(d.x, d.y, d.r + 6, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawEquation() {
    if (!scene.equation) return;
    const size = Math.max(34, Math.min(scene.w * 0.09, 76));
    ctx.save();
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = PALETTE.text;
    ctx.font = "600 " + size + "px ui-rounded, 'Segoe UI', system-ui, sans-serif";
    ctx.fillText(scene.equation, scene.dock.x, scene.dock.y);
    ctx.restore();
  }

  function drawTug(dt) {
    const t = scene.tug;

    // Spring toward the pointer, damped: inertia without overshoot drama.
    const ax = (scene.target.x - t.x) * 9;
    const ay = (scene.target.y - t.y) * 9;
    t.vx = (t.vx + ax * dt) * 0.86;
    t.vy = (t.vy + ay * dt) * 0.86;
    t.x += t.vx * dt;
    t.y += t.vy * dt;

    const speed = Math.hypot(t.vx, t.vy);
    if (speed > 12) {
      const want = Math.atan2(t.vy, t.vx);
      let delta = want - t.heading;
      while (delta > Math.PI) delta -= Math.PI * 2;
      while (delta < -Math.PI) delta += Math.PI * 2;
      t.heading += delta * Math.min(1, dt * 6);
    }

    scene.bob += dt;
    const bob = reduceMotion ? 0 : Math.sin(scene.bob * 1.8) * 3;

    ctx.save();
    ctx.translate(t.x, t.y + bob);
    ctx.rotate(t.heading + Math.PI / 2);

    ctx.fillStyle = PALETTE.hull;
    ctx.strokeStyle = PALETTE.hullEdge;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, -22);
    ctx.lineTo(13, 12);
    ctx.lineTo(0, 6);
    ctx.lineTo(-13, 12);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = PALETTE.ring;
    ctx.beginPath();
    ctx.arc(0, -6, 4.5, 0, Math.PI * 2);
    ctx.fill();

    if (scene.pod === null) {
      ctx.fillStyle = PALETTE.pod;
      ctx.beginPath();
      ctx.arc(0, 14, 6, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawPod(dt) {
    const pod = scene.pod;
    if (pod === null) return;

    pod.t = Math.min(1, pod.t + dt / pod.duration);
    const ease = pod.t * pod.t * (3 - 2 * pod.t);
    const from = pod.returning ? pod.to : pod.from;
    const to = pod.returning ? pod.from : pod.to;
    const x = from.x + (to.x - from.x) * ease;
    // One arc, so the pod travels rather than slides.
    const lift = Math.sin(ease * Math.PI) * 46;
    const y = from.y + (to.y - from.y) * ease - lift;

    ctx.save();
    ctx.fillStyle = pod.returning ? PALETTE.pod : PALETTE.podDocked;
    ctx.beginPath();
    ctx.arc(x, y, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    if (pod.t >= 1) {
      if (pod.arrived) pod.arrived();
      scene.pod = null;
    }
  }

  let last = 0;
  function frame(now) {
    const dt = last === 0 ? 0.016 : Math.min(0.05, (now - last) / 1000);
    last = now;

    drawBackground();
    drawStars(dt);
    drawStation();
    drawEquation();
    drawPod(dt);
    drawTug(dt);

    if (scene.glow > 0) scene.glow = Math.max(0, scene.glow - dt * 1.6);
    requestAnimationFrame(frame);
  }

  // Screen shake would live here. The profile disables it, so the hook exists
  // and does nothing --- 0ms, no offset ever applied.
  function shake() {
    if (!SHAKE_ALLOWED) return;
    /* intentionally unreachable for this profile */
  }

  function burst() {
    if (!BURSTS_ALLOWED) return;
    /* intentionally unreachable for this profile */
  }

  function launchPod(correct, onArrive) {
    Sound.launch();
    scene.pod = {
      from: { x: scene.tug.x, y: scene.tug.y },
      to: { x: scene.dock.x, y: scene.dock.y + scene.dock.r },
      t: 0,
      duration: 0.55,
      returning: !correct,
      arrived: onArrive,
    };
  }

  // --- the loop ------------------------------------------------------------
  const els = {
    intro: document.getElementById("intro"),
    play: document.getElementById("play"),
    done: document.getElementById("done"),
    start: document.getElementById("start"),
    again: document.getElementById("again"),
    progress: document.getElementById("progress"),
    problem: document.getElementById("problem"),
    form: document.getElementById("answer-form"),
    answer: document.getElementById("answer"),
    submit: document.getElementById("submit"),
    feedback: document.getElementById("feedback"),
  };

  const PRAISE = ["Docked.", "Clean approach.", "Locked on.", "Steady hands.", "In she goes."];

  let question = null;
  let shownAt = 0;
  let answered = 0;
  let busy = false;

  function api(path, options) {
    return fetch(C.API_BASE + path, options).then(function (res) {
      if (!res.ok) throw new Error(path + " -> " + res.status);
      return res.json();
    });
  }

  function renderProgress() {
    els.progress.innerHTML = "";
    for (let i = 0; i < C.SESSION_LENGTH; i++) {
      const dot = document.createElement("span");
      dot.className = "dot" + (i < answered ? " filled" : "");
      els.progress.appendChild(dot);
    }
  }

  function nextQuestion() {
    return api(
      "/profiles/" + C.PROFILE_ID + "/skills/" + C.SKILL_ID + "/next-question"
    ).then(function (q) {
      question = q;
      Telemetry.setDifficultyVector(q.difficulty_vector_snapshot);
      scene.equation = q.operands[0] + " " + q.operator + " " + q.operands[1];
      els.problem.textContent = scene.equation;
      els.answer.value = "";
      els.answer.focus();
      shownAt = performance.now();
      Telemetry.capture("problem_shown", {
        operands: q.operands,
        operator: q.operator,
      });
    });
  }

  function finish() {
    els.play.hidden = true;
    els.done.hidden = false;
    scene.equation = "";
    Telemetry.stopIdleWatch();
    Telemetry.capture("level_completed", { questions: answered });
  }

  // Fetching the next question can fail. When it does there is no question on
  // screen to answer, so Send becomes a retry instead of a submit --- never a
  // second submission of the question that was already answered.
  function retry() {
    busy = true;
    els.submit.disabled = true;
    nextQuestion()
      .then(
        function () {
          els.feedback.textContent = "";
        },
        function () {
          lostSignal();
        }
      )
      .then(function () {
        busy = false;
        els.submit.disabled = false;
      });
  }

  function lostSignal() {
    question = null;
    els.feedback.textContent = "Lost the signal. Press Send to try again.";
    els.feedback.className = "feedback gentle";
  }

  function submit(event) {
    event.preventDefault();
    if (busy) return;
    if (question === null) {
      retry();
      return;
    }
    const raw = els.answer.value.trim();
    if (!/^\d+$/.test(raw)) {
      els.answer.focus();
      return;
    }
    busy = true;
    els.submit.disabled = true;
    Sound.resume();

    const latency = Math.round(performance.now() - shownAt);
    api("/attempts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_id: C.PROFILE_ID,
        skill_id: C.SKILL_ID,
        operands: question.operands,
        operator: question.operator,
        answer_given: Number(raw),
        latency_to_submit_ms: latency,
      }),
    })
      .then(function (result) {
        Telemetry.capture("answer_submitted", {
          attempt_id: result.attempt_id,
          correct: result.is_correct,
          time_to_solve_ms: latency,
          error_class: result.error_class,
        });
        Telemetry.setDifficultyVector(result.updated_difficulty_vector);
        answered += 1;
        return settle(result);
      })
      .catch(function () {
        els.feedback.textContent = "Lost the signal. Try that again.";
        els.feedback.className = "feedback gentle";
      })
      .then(function () {
        busy = false;
        els.submit.disabled = false;
      });
  }

  function settle(result) {
    return new Promise(function (resolve) {
      const correct = result.is_correct;
      launchPod(correct, function () {
        if (correct) {
          scene.docked += 1;
          scene.glow = 1;
          Sound.docked();
          burst();
          els.feedback.textContent = PRAISE[answered % PRAISE.length];
          els.feedback.className = "feedback good";
        } else if (GENTLE) {
          // No red X, no failure state: the answer is simply shown.
          Sound.gentle();
          shake();
          els.feedback.textContent =
            "Almost — it was " + question.correct_answer + ". Next one.";
          els.feedback.className = "feedback gentle";
        }
        renderProgress();

        const pause = correct ? 650 : 1600;
        window.setTimeout(function () {
          els.feedback.textContent = "";
          if (answered >= C.SESSION_LENGTH) {
            finish();
            resolve();
            return;
          }
          nextQuestion().then(resolve, function () {
            lostSignal();
            resolve();
          });
        }, pause);
      });
    });
  }

  function startLevel() {
    // Nothing from the finished session may still be answerable while the
    // first question of the new one is in flight.
    question = null;
    els.answer.value = "";
    answered = 0;
    scene.docked = 0;
    els.intro.hidden = true;
    els.done.hidden = true;
    els.play.hidden = false;
    renderProgress();
    Sound.resume();
    Telemetry.startIdleWatch();
    Telemetry.capture("level_started", {});
    nextQuestion().catch(lostSignal);
  }

  els.start.addEventListener("click", startLevel);
  els.again.addEventListener("click", startLevel);
  els.form.addEventListener("submit", submit);

  // Tapping the scene is the same thematic action as sending the answer.
  canvas.addEventListener("pointerdown", function () {
    if (!els.play.hidden) els.form.requestSubmit();
  });

  window.addEventListener("beforeunload", function () {
    if (els.play.hidden || answered >= C.SESSION_LENGTH) return;
    Telemetry.capture("level_abandoned", {
      progress_pct: Math.round((answered / C.SESSION_LENGTH) * 100),
    });
  });

  // --- report a problem ----------------------------------------------------
  const report = {
    open: document.getElementById("report-open"),
    dialog: document.getElementById("report-dialog"),
    text: document.getElementById("report-text"),
    send: document.getElementById("report-send"),
    cancel: document.getElementById("report-cancel"),
    status: document.getElementById("report-status"),
  };

  report.open.addEventListener("click", function () {
    report.dialog.hidden = false;
    report.text.focus();
  });
  report.cancel.addEventListener("click", function () {
    report.dialog.hidden = true;
  });
  report.send.addEventListener("click", function () {
    const description = report.text.value.trim();
    if (!description) return;
    api("/games/" + C.GAME_ID + "/report-problem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description: description }),
    })
      .then(function () {
        report.status.textContent = "Sent.";
        report.text.value = "";
        window.setTimeout(function () {
          report.dialog.hidden = true;
          report.status.textContent = "";
        }, 900);
      })
      .catch(function () {
        report.status.textContent = "Could not send.";
      });
  });

  resize();
  requestAnimationFrame(frame);
})();
