// Rendering shell only. Questions come from the backend, and whether an answer
// was right (and why it was wrong) comes back from POST /attempts. Nothing in
// this file generates a question, judges an answer, or moves difficulty.
(function () {
  const C = window.ORBIT;
  const T = window.Telemetry;

  const el = {
    pods: document.getElementById("pods"),
    intro: document.getElementById("intro"),
    play: document.getElementById("play"),
    done: document.getElementById("done"),
    start: document.getElementById("start"),
    again: document.getElementById("again"),
    progress: document.getElementById("progress"),
    podLeft: document.getElementById("pod-left"),
    podRight: document.getElementById("pod-right"),
    podOp: document.getElementById("pod-op"),
    problem: document.getElementById("problem"),
    form: document.getElementById("answer-form"),
    answer: document.getElementById("answer"),
    submit: document.getElementById("submit"),
    feedback: document.getElementById("feedback"),
    reportOpen: document.getElementById("report-open"),
    reportDialog: document.getElementById("report-dialog"),
    reportText: document.getElementById("report-text"),
    reportSend: document.getElementById("report-send"),
    reportCancel: document.getElementById("report-cancel"),
    reportStatus: document.getElementById("report-status"),
  };

  const state = {
    question: null,
    shownAt: 0,
    answered: 0,
    running: false,
    busy: false,
  };

  const api = (path) => C.API_BASE + path;

  async function getJSON(path) {
    const res = await fetch(api(path), { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error(path + " -> " + res.status);
    return res.json();
  }

  async function postJSON(path, body) {
    const res = await fetch(api(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(path + " -> " + res.status);
    return res.json();
  }

  function renderProgress() {
    if (el.progress.children.length !== C.SESSION_LENGTH) {
      el.progress.textContent = "";
      for (let i = 0; i < C.SESSION_LENGTH; i++) {
        const dot = document.createElement("span");
        dot.className = "dot";
        el.progress.appendChild(dot);
      }
    }
    Array.prototype.forEach.call(el.progress.children, (dot, i) => {
      dot.classList.toggle("filled", i < state.answered);
    });
  }

  function renderPod(node, count) {
    node.textContent = "";
    const shown = Math.min(count, 9);
    for (let i = 0; i < shown; i++) {
      const star = document.createElement("span");
      star.className = "star";
      node.appendChild(star);
    }
  }

  function showFeedback(text, gentle) {
    el.feedback.textContent = text;
    el.feedback.classList.toggle("gentle", !!gentle);
    el.feedback.classList.add("show");
  }

  function clearFeedback() {
    el.feedback.classList.remove("show");
    el.feedback.textContent = "";
  }

  // A single soft blip. Audio constraints: no music, UI sounds only.
  let audioCtx = null;
  function blip(freq) {
    try {
      audioCtx =
        audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.value = 0.05;
      osc.connect(gain).connect(audioCtx.destination);
      osc.start();
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.16);
      osc.stop(audioCtx.currentTime + 0.18);
    } catch (err) {
      /* sound is optional */
    }
  }

  async function loadQuestion() {
    const question = await getJSON(
      "/profiles/" +
        C.PROFILE_ID +
        "/skills/" +
        C.SKILL_ID +
        "/next-question"
    );
    state.question = question;
    T.setDifficultyVector(question.difficulty_vector_snapshot);

    const [a, b] = question.operands;
    // Stars only stand in for a number they can actually show. Past single
    // digits the numerals are the focal point on their own.
    const countable = a <= 9 && b <= 9;
    el.pods.hidden = !countable;
    if (countable) {
      renderPod(el.podLeft, a);
      renderPod(el.podRight, b);
      el.podOp.textContent = question.operator;
    }
    el.problem.textContent = a + " " + question.operator + " " + b;
    el.answer.value = "";
    el.answer.focus();
    state.shownAt = performance.now();
    T.markActive();
    T.capture("problem_shown", {});
  }

  async function submitAnswer(value) {
    const question = state.question;
    const elapsed = Math.max(0, Math.round(performance.now() - state.shownAt));
    const result = await postJSON("/attempts", {
      profile_id: C.PROFILE_ID,
      skill_id: C.SKILL_ID,
      operands: question.operands,
      operator: question.operator,
      answer_given: value,
      latency_to_submit_ms: elapsed,
    });

    T.capture("answer_submitted", {
      correct: result.is_correct,
      time_to_solve_ms: elapsed,
      error_class: result.error_class,
    });
    T.setDifficultyVector(result.updated_difficulty_vector);

    if (result.is_correct) {
      blip(660);
      showFeedback("Docked!", false);
    } else {
      // Impossible to lose: no failure state, no red X. Show the answer the
      // backend already sent with the question, then move on.
      blip(392);
      showFeedback(
        "Almost — it was " + question.correct_answer + ". Next one.",
        true
      );
    }

    state.answered += 1;
    renderProgress();
    return result;
  }

  async function advance() {
    if (state.answered >= C.SESSION_LENGTH) {
      finish();
      return;
    }
    clearFeedback();
    try {
      await loadQuestion();
    } catch (err) {
      showFeedback("Taking a moment…", true);
    }
  }

  function finish() {
    state.running = false;
    T.stopIdleWatch();
    T.capture("level_completed", {});
    el.play.hidden = true;
    el.done.hidden = false;
    el.again.focus();
  }

  async function startLevel() {
    state.answered = 0;
    state.running = true;
    abandonReported = false;
    renderProgress();
    clearFeedback();
    el.intro.hidden = true;
    el.done.hidden = true;
    el.play.hidden = false;
    T.startIdleWatch();
    T.capture("level_started", {});
    await advance();
  }

  el.start.addEventListener("click", () => {
    blip(523);
    startLevel();
  });
  el.again.addEventListener("click", () => {
    blip(523);
    startLevel();
  });

  el.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.busy || !state.running) return;
    const raw = el.answer.value.trim();
    if (!/^\d{1,4}$/.test(raw)) {
      el.answer.focus();
      return;
    }
    state.busy = true;
    el.submit.disabled = true;
    try {
      await submitAnswer(Number(raw));
      await new Promise((resolve) => setTimeout(resolve, 1100));
      await advance();
    } catch (err) {
      showFeedback("Taking a moment…", true);
    } finally {
      state.busy = false;
      el.submit.disabled = false;
      if (state.running) el.answer.focus();
    }
  });

  el.answer.addEventListener("keydown", (event) => {
    const allowed = [
      "Backspace",
      "Delete",
      "Tab",
      "Enter",
      "ArrowLeft",
      "ArrowRight",
      "Home",
      "End",
    ];
    if (allowed.indexOf(event.key) !== -1 || event.ctrlKey || event.metaKey) return;
    if (!/^\d$/.test(event.key)) event.preventDefault();
  });

  // --- Report a problem ---
  el.reportOpen.addEventListener("click", () => {
    const opening = el.reportDialog.hidden;
    el.reportDialog.hidden = !opening;
    el.reportStatus.textContent = "";
    if (opening) el.reportText.focus();
  });
  el.reportCancel.addEventListener("click", () => {
    el.reportDialog.hidden = true;
    el.reportOpen.focus();
  });
  el.reportSend.addEventListener("click", async () => {
    const description = el.reportText.value.trim() || "No description given.";
    el.reportSend.disabled = true;
    try {
      await postJSON("/games/" + C.GAME_ID + "/report-problem", {
        description: description,
      });
      el.reportStatus.textContent = "Thanks — sent.";
      el.reportText.value = "";
    } catch (err) {
      el.reportStatus.textContent = "Could not send that yet.";
    } finally {
      el.reportSend.disabled = false;
    }
  });

  // --- level_abandoned ---
  let abandonReported = false;
  function reportAbandon() {
    if (!state.running || abandonReported) return;
    abandonReported = true;
    T.capture("level_abandoned", {
      progress_pct: Math.round((state.answered / C.SESSION_LENGTH) * 100),
    });
  }
  window.addEventListener("pagehide", reportAbandon);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") reportAbandon();
  });

  renderProgress();
})();
