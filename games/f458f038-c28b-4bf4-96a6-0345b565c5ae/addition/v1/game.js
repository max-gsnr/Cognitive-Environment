// Token Machine: a rendering shell. Every question comes from the backend and
// every answer is judged by the backend. There is no difficulty or correctness
// logic here, and no way to lose.
(function () {
  const C = window.ORBIT;
  const T = window.Telemetry;

  const el = {
    play: document.getElementById("play-screen"),
    done: document.getElementById("done-screen"),
    againBtn: document.getElementById("again-btn"),
    dots: document.getElementById("dots"),
    problem: document.getElementById("problem"),
    form: document.getElementById("answer-form"),
    input: document.getElementById("answer"),
    submit: document.getElementById("submit-btn"),
    feedback: document.getElementById("feedback"),
    doneTitle: document.getElementById("done-title"),
    canvas: document.getElementById("tokens"),
    reportBtn: document.getElementById("report-btn"),
    reportPanel: document.getElementById("report-panel"),
    reportText: document.getElementById("report-text"),
    reportSend: document.getElementById("report-send"),
    reportCancel: document.getElementById("report-cancel"),
  };

  const ctx = el.canvas.getContext("2d");
  const PALETTE = { hundred: "#8fa9c9", ten: "#a8c6ae", one: "#d8b98c" };

  const state = {
    question: null,
    vector: {},
    index: 0,
    solved: 0,
    shownAt: 0,
    busy: false,
    needsQuestion: false,
    live: false,
    abandonReported: false,
  };

  let particles = [];
  let particleFrame = null;
  let questionRetryTimer = null;
  const QUESTION_RETRY_DELAY_MS = 1800;

  /* ---------- audio: ui blips only, no music ---------- */
  let audio = null;
  function blip(freq) {
    if (C.CONSTRAINTS.audio.sfx !== "ui_only") return;
    try {
      const Ctor = window.AudioContext || window.webkitAudioContext;
      if (!Ctor) return;
      audio = audio || new Ctor();
      const osc = audio.createOscillator();
      const gain = audio.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.value = 0.0001;
      gain.gain.exponentialRampToValueAtTime(0.05, audio.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, audio.currentTime + 0.22);
      osc.connect(gain).connect(audio.destination);
      osc.start();
      osc.stop(audio.currentTime + 0.24);
    } catch (err) {
      /* silence is an acceptable outcome */
    }
  }

  /* ---------- api ---------- */
  function url(path) {
    return C.API_BASE + path;
  }

  async function fetchQuestion() {
    const res = await fetch(
      url(
        "/profiles/" +
          C.PROFILE_ID +
          "/skills/" +
          C.SKILL_ID +
          "/next-question"
      ),
      { headers: { Accept: "application/json" } }
    );
    if (!res.ok) throw new Error("next-question " + res.status);
    return res.json();
  }

  async function postAttempt(answer, latencyMs) {
    const res = await fetch(url("/attempts"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile_id: C.PROFILE_ID,
        skill_id: C.SKILL_ID,
        operands: state.question.operands,
        operator: state.question.operator,
        answer_given: answer,
        latency_to_submit_ms: latencyMs,
        game_id: C.GAME_ID,
        game_version: C.VERSION,
      }),
    });
    if (!res.ok) throw new Error("attempts " + res.status);
    return res.json();
  }

  /* ---------- canvas: tokens for each operand ---------- */
  function groups(n) {
    return [
      { count: Math.floor(n / 100), size: 30, color: PALETTE.hundred },
      { count: Math.floor((n % 100) / 10), size: 22, color: PALETTE.ten },
      { count: n % 10, size: 14, color: PALETTE.one },
    ].filter((g) => g.count > 0);
  }

  function drawPile(n, cx, cy) {
    const rows = groups(n);
    const rowHeight = 34;
    let y = cy - ((rows.length - 1) * rowHeight) / 2;
    rows.forEach((row) => {
      const gap = row.size + 8;
      let x = cx - ((row.count - 1) * gap) / 2;
      for (let i = 0; i < row.count; i++) {
        ctx.fillStyle = row.color;
        round(x - row.size / 2, y - row.size / 2, row.size, row.size, 5);
        x += gap;
      }
      y += rowHeight;
    });
  }

  function round(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
    ctx.fill();
  }

  function drawScene() {
    const w = el.canvas.width;
    const h = el.canvas.height;
    ctx.clearRect(0, 0, w, h);
    if (state.question) {
      drawPile(state.question.operands[0], w * 0.27, h * 0.5);
      drawPile(state.question.operands[1], w * 0.73, h * 0.5);
      ctx.fillStyle = "#b9b2a5";
      ctx.font = "600 34px Segoe UI, system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(state.question.operator, w * 0.5, h * 0.5);
    }
    particles.forEach((p) => {
      ctx.globalAlpha = Math.max(0, p.life);
      ctx.fillStyle = p.color;
      round(p.x, p.y, p.size, p.size, 3);
      ctx.globalAlpha = 1;
    });
  }

  function burst() {
    if (!C.CONSTRAINTS.visual.particle_effects) return;
    const colors = [PALETTE.hundred, PALETTE.ten, PALETTE.one, "#e6d4c1"];
    for (let i = 0; i < 26; i++) {
      particles.push({
        x: el.canvas.width / 2 + (Math.random() - 0.5) * 220,
        y: el.canvas.height * 0.6,
        vx: (Math.random() - 0.5) * 1.6,
        vy: -1.2 - Math.random() * 1.4,
        size: 6 + Math.random() * 7,
        life: 1,
        color: colors[i % colors.length],
      });
    }
    if (!particleFrame) particleFrame = requestAnimationFrame(stepParticles);
  }

  function stepParticles() {
    particles.forEach((p) => {
      p.x += p.vx;
      p.y += p.vy;
      p.vy += 0.02;
      p.life -= 0.016;
    });
    particles = particles.filter((p) => p.life > 0);
    drawScene();
    particleFrame = particles.length ? requestAnimationFrame(stepParticles) : null;
  }

  /* ---------- flow ---------- */
  function renderDots() {
    el.dots.innerHTML = "";
    for (let i = 0; i < C.SESSION_LENGTH; i++) {
      const dot = document.createElement("span");
      if (i < state.index) dot.className = "filled";
      el.dots.appendChild(dot);
    }
    el.dots.setAttribute(
      "aria-label",
      state.index + " of " + C.SESSION_LENGTH + " done"
    );
  }

  function show(panel) {
    [el.play, el.done].forEach((p) => {
      p.hidden = p !== panel;
    });
  }

  function progressPct() {
    return Math.round((state.index / C.SESSION_LENGTH) * 100);
  }

  function clearQuestionRetry() {
    if (questionRetryTimer !== null) {
      window.clearTimeout(questionRetryTimer);
      questionRetryTimer = null;
    }
  }

  function scheduleQuestionRetry() {
    if (!state.live || !state.needsQuestion || questionRetryTimer !== null) {
      return;
    }
    questionRetryTimer = window.setTimeout(() => {
      questionRetryTimer = null;
      if (state.live && state.needsQuestion) nextQuestion();
    }, QUESTION_RETRY_DELAY_MS);
  }

  async function nextQuestion() {
    if (!state.live || (state.busy && state.needsQuestion)) return;
    state.busy = true;
    state.needsQuestion = true;
    state.question = null;
    el.input.value = "";
    el.problem.textContent = "";
    drawScene();
    try {
      const question = await fetchQuestion();
      state.question = question;
      state.needsQuestion = false;
      clearQuestionRetry();
      state.vector = question.difficulty_vector_snapshot || {};
      T.setDifficultyVector(state.vector);
      el.feedback.textContent = "";
      el.feedback.className = "feedback";
      el.problem.textContent =
        question.operands[0] +
        " " +
        question.operator +
        " " +
        question.operands[1];
      drawScene();
      state.shownAt = Date.now();
      T.capture("problem_shown", {
        operands: question.operands,
        operator: question.operator,
        question_index: state.index + 1,
      });
      T.markActive();
    } catch (err) {
      el.feedback.className = "feedback is-gentle";
      el.feedback.textContent = "Taking a moment. Press Enter to try again.";
      scheduleQuestionRetry();
    }
    state.busy = false;
    el.input.focus();
  }

  async function submit(answer) {
    state.busy = true;
    const latency = Date.now() - state.shownAt;
    let result;
    try {
      result = await postAttempt(answer, latency);
    } catch (err) {
      el.feedback.className = "feedback is-gentle";
      el.feedback.textContent = "Taking a moment. Press Enter to send again.";
      state.busy = false;
      return;
    }

    T.capture("answer_submitted", {
      attempt_id: result.attempt_id,
      correct: result.is_correct,
      time_to_solve_ms: latency,
      error_class: result.error_class,
      question_index: state.index + 1,
    });

    if (result.is_correct) {
      state.solved++;
      blip(660);
      burst();
      el.feedback.className = "feedback is-good";
      el.feedback.textContent = "In it goes.";
    } else {
      blip(392);
      el.feedback.className = "feedback is-gentle";
      el.feedback.textContent =
        "Close one — it lands on " + state.question.correct_answer + ".";
    }

    state.index++;
    renderDots();
    const pause = result.is_correct ? 900 : 1700;
    window.setTimeout(() => {
      el.feedback.textContent = "";
      el.feedback.className = "feedback";
      if (state.index >= C.SESSION_LENGTH) {
        finish();
      } else {
        nextQuestion();
      }
    }, pause);
  }

  function startLevel() {
    state.index = 0;
    state.solved = 0;
    state.live = true;
    state.abandonReported = false;
    state.question = null;
    state.needsQuestion = false;
    clearQuestionRetry();
    particles = [];
    renderDots();
    show(el.play);
    T.capture("level_started", { session_length: C.SESSION_LENGTH });
    T.startIdleWatch();
    nextQuestion();
  }

  function finish() {
    state.live = false;
    state.needsQuestion = false;
    clearQuestionRetry();
    state.question = null;
    T.stopIdleWatch();
    drawScene();
    el.doneTitle.textContent = "All " + C.SESSION_LENGTH + " tokens in";
    show(el.done);
    blip(784);
    T.capture("level_completed", {
      solved: state.solved,
      session_length: C.SESSION_LENGTH,
    });
  }

  /* ---------- report a problem ---------- */
  async function sendReport() {
    const description = (el.reportText.value || "").trim();
    if (!description) {
      el.reportPanel.hidden = true;
      return;
    }
    try {
      await fetch(url("/games/" + C.GAME_ID + "/report-problem"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: description }),
      });
    } catch (err) {
      /* a failed report must not interrupt play */
    }
    el.reportText.value = "";
    el.reportPanel.hidden = true;
    el.feedback.className = "feedback";
    el.feedback.textContent = "Thanks for telling us.";
    window.setTimeout(() => {
      if (el.feedback.textContent === "Thanks for telling us.") {
        el.feedback.textContent = "";
      }
    }, 2200);
  }

  /* ---------- wiring ---------- */
  el.againBtn.addEventListener("click", startLevel);

  el.form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (state.busy) return;
    if (state.needsQuestion || !state.question) {
      el.input.focus();
      return;
    }
    const raw = (el.input.value || "").replace(/[^0-9]/g, "");
    if (!raw) {
      el.input.focus();
      return;
    }
    submit(parseInt(raw, 10));
  });

  el.input.addEventListener("keydown", (event) => {
    T.recordKeystroke(event.key === "Backspace" || event.key === "Delete");
  });
  el.input.addEventListener("input", () => {
    el.input.value = el.input.value.replace(/[^0-9]/g, "");
    T.markActive();
  });

  document.addEventListener("pointermove", (event) => {
    T.recordPointer(event.clientX, event.clientY);
  });
  document.addEventListener("pointerdown", () => T.markActive());

  el.reportBtn.addEventListener("click", () => {
    el.reportPanel.hidden = !el.reportPanel.hidden;
    if (!el.reportPanel.hidden) el.reportText.focus();
  });
  el.reportCancel.addEventListener("click", () => {
    el.reportPanel.hidden = true;
  });
  el.reportSend.addEventListener("click", sendReport);

  function reportAbandon() {
    if (!state.live || state.abandonReported) return;
    state.abandonReported = true;
    T.capture("level_abandoned", { progress_pct: progressPct() });
  }

  window.addEventListener("pagehide", reportAbandon);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") reportAbandon();
  });

  window.ORBIT_GAME = { state: state, startLevel: startLevel };
  startLevel();
})();
