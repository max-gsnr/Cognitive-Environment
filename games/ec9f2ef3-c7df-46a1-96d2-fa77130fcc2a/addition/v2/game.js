// Leo's Space Docking Odyssey — 60fps Canvas Game Engine & API Harness
(function () {
  const C = window.ORBIT;
  const T = window.Telemetry;

  // DOM Elements
  const titleScreen = document.getElementById("title-screen");
  const playScreen = document.getElementById("play-screen");
  const victoryScreen = document.getElementById("victory-screen");
  const startBtn = document.getElementById("start-btn");
  const replayBtn = document.getElementById("replay-btn");
  const problemEl = document.getElementById("problem");
  const formEl = document.getElementById("answer-form");
  const inputEl = document.getElementById("answer-input");
  const submitBtn = document.getElementById("submit-btn");
  const feedbackEl = document.getElementById("feedback");
  const progressEl = document.getElementById("progress");
  const reportBtn = document.getElementById("report-btn");
  const reportDialog = document.getElementById("report-dialog");
  const reportText = document.getElementById("report-text");
  const reportCancel = document.getElementById("report-cancel");
  const reportSend = document.getElementById("report-send");
  const canvas = document.getElementById("game-canvas");
  const ctx = canvas.getContext("2d");

  // Game State
  let currentQuestion = null;
  let shownAt = 0;
  let answeredCount = 0;
  let totalSession = C.SESSION_LENGTH || 10;
  let isSubmitting = false;

  // Visual Effects & Starfield
  let stars = [];
  let particles = [];
  let laserBeams = [];
  let shakeTime = 0;
  let animId = null;

  // Player Starship Physics
  const player = {
    x: 400,
    y: 280,
    vx: 0,
    vy: 0,
    angle: -Math.PI / 2,
    targetAngle: -Math.PI / 2,
    speed: 5.5,
    size: 22,
    idlePhase: 0,
  };

  // Central Docking Station
  const dockHub = {
    x: 400,
    y: 110,
    radius: 40,
    pulse: 0,
    docked: false,
  };

  let targetX = null;
  let targetY = null;

  // -------------------------------------------------------------
  // Web Audio API Synthesizer (0ms Latency Procedural Sound)
  // -------------------------------------------------------------
  let audioCtx = null;
  function getAudioContext() {
    if (C.CONSTRAINTS.audio.sfx === "none") return null;
    try {
      if (!audioCtx) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        audioCtx = new AudioCtx();
      }
      if (audioCtx.state === "suspended") audioCtx.resume();
      return audioCtx;
    } catch {
      return null;
    }
  }

  function playLaserSound() {
    const ctx = getAudioContext();
    if (!ctx) return;
    try {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(880, now);
      osc.frequency.exponentialRampToValueAtTime(110, now + 0.12);
      gain.gain.setValueAtTime(0.2, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.12);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.13);
    } catch {}
  }

  function playDockChime() {
    const ctx = getAudioContext();
    if (!ctx) return;
    try {
      const now = ctx.currentTime;
      [440, 554.37, 659.25, 880].forEach((freq, idx) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        const t = now + idx * 0.06;
        osc.type = "sine";
        osc.frequency.setValueAtTime(freq, t);
        gain.gain.setValueAtTime(0.2, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.25);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(t);
        osc.stop(t + 0.28);
      });
    } catch {}
  }

  function playGentleRetry() {
    const ctx = getAudioContext();
    if (!ctx) return;
    try {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.setValueAtTime(330, now);
      osc.frequency.linearRampToValueAtTime(260, now + 0.22);
      gain.gain.setValueAtTime(0.18, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.22);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now);
      osc.stop(now + 0.24);
    } catch {}
  }

  // -------------------------------------------------------------
  // Visuals & Parallax Setup
  // -------------------------------------------------------------
  function initStars() {
    stars = [];
    const colors = ["#ffffff", "#93c5fd", "#38bdf8", "#fbbf24"];
    for (let i = 0; i < 110; i++) {
      stars.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        size: Math.random() * 2.2 + 0.6,
        speed: Math.random() * 0.8 + 0.3,
        color: colors[Math.floor(Math.random() * colors.length)],
        alpha: Math.random() * 0.8 + 0.2,
      });
    }
  }

  function emitExplosion(x, y, color, count = 18) {
    if (!C.CONSTRAINTS.visual.particle_effects) return;
    for (let i = 0; i < count; i++) {
      const ang = Math.random() * Math.PI * 2;
      const spd = Math.random() * 4.5 + 1.0;
      particles.push({
        x,
        y,
        vx: Math.cos(ang) * spd,
        vy: Math.sin(ang) * spd,
        color,
        size: Math.random() * 3.5 + 1.5,
        alpha: 1.0,
        decay: Math.random() * 0.03 + 0.02,
      });
    }
  }

  function emitThruster(x, y, angle) {
    if (!C.CONSTRAINTS.visual.particle_effects) return;
    const opp = angle + Math.PI + (Math.random() - 0.5) * 0.4;
    const spd = Math.random() * 2.5 + 1.5;
    particles.push({
      x: x + Math.cos(opp) * 12,
      y: y + Math.sin(opp) * 12,
      vx: Math.cos(opp) * spd,
      vy: Math.sin(opp) * spd,
      color: "#38bdf8",
      size: Math.random() * 2.5 + 1.0,
      alpha: 0.9,
      decay: 0.05,
    });
  }

  // -------------------------------------------------------------
  // API Integration (Loop A Harness)
  // -------------------------------------------------------------
  async function api(path, opts = {}) {
    const base = C.API_BASE;
    const url = `${base}${path}`;
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(`API ${res.status}: ${txt}`);
    }
    return res.json();
  }

  async function loadNextQuestion() {
    isSubmitting = false;
    feedbackEl.textContent = "";
    feedbackEl.className = "feedback";
    dockHub.docked = false;
    inputEl.value = "";
    inputEl.disabled = false;
    submitBtn.disabled = false;
    inputEl.focus();

    try {
      const q = await api(`/profiles/${C.PROFILE_ID}/skills/${C.SKILL_ID}/next-question`);
      currentQuestion = q;
      shownAt = performance.now();

      T.setDifficultyVector(q.difficulty_vector_snapshot);
      T.capture("problem_shown", {
        operands: q.operands,
        operator: q.operator,
      });

      const [a, b] = q.operands;
      problemEl.textContent = `✦  ${a} ${q.operator} ${b} = ?`;
      renderProgress();
    } catch (err) {
      feedbackEl.textContent = `Could not reach Orbit: ${err.message}`;
      feedbackEl.className = "feedback gentle";
    }
  }

  async function handleAnswerSubmit(e) {
    if (e) e.preventDefault();
    if (isSubmitting || !currentQuestion) return;

    const val = parseInt(inputEl.value.trim(), 10);
    if (isNaN(val)) return;

    isSubmitting = true;
    inputEl.disabled = true;
    submitBtn.disabled = true;

    const latency = Math.max(100, Math.round(performance.now() - shownAt));

    // Fire laser beam toward docking station
    laserBeams.push({
      startX: player.x,
      startY: player.y,
      endX: dockHub.x,
      endY: dockHub.y,
      alpha: 1.0,
    });
    playLaserSound();

    try {
      const result = await api("/attempts", {
        method: "POST",
        body: JSON.stringify({
          profile_id: C.PROFILE_ID,
          skill_id: C.SKILL_ID,
          operands: currentQuestion.operands,
          operator: currentQuestion.operator,
          answer_given: val,
          latency_to_submit_ms: latency,
        }),
      });

      T.capture("answer_submitted", {
        correct: result.is_correct,
        time_to_solve_ms: latency,
        error_class: result.error_class || "unknown",
      });

      if (result.updated_difficulty_vector) {
        T.setDifficultyVector(result.updated_difficulty_vector);
      }

      if (result.is_correct) {
        dockHub.docked = true;
        answeredCount += 1;
        playDockChime();
        emitExplosion(dockHub.x, dockHub.y, "#38bdf8", 24);

        if (C.CONSTRAINTS.visual.animations !== "minimal_no_screen_shake") {
          shakeTime = 12;
        }

        feedbackEl.textContent = "✦ Star Pod Docked Successfully!";
        feedbackEl.className = "feedback";

        if (answeredCount >= totalSession) {
          setTimeout(finishLevel, 1000);
          return;
        }

        setTimeout(loadNextQuestion, 900);
      } else {
        playGentleRetry();
        emitExplosion(dockHub.x, dockHub.y, "#fbbf24", 12);
        feedbackEl.textContent = `Almost, Leo — it was ${currentQuestion.correct_answer}. Next star pod incoming!`;
        feedbackEl.className = "feedback gentle";

        setTimeout(loadNextQuestion, 1300);
      }
    } catch (err) {
      feedbackEl.textContent = `Error: ${err.message}`;
      feedbackEl.className = "feedback gentle";
      inputEl.disabled = false;
      submitBtn.disabled = false;
      isSubmitting = false;
    }
  }

  function finishLevel() {
    playScreen.hidden = true;
    victoryScreen.hidden = false;
    T.stopIdleWatch();
    T.capture("level_completed", { total_answered: answeredCount });
  }

  function renderProgress() {
    progressEl.innerHTML = "";
    for (let i = 0; i < totalSession; i++) {
      const dot = document.createElement("div");
      dot.className = `dot ${i < answeredCount ? "filled" : ""}`;
      progressEl.appendChild(dot);
    }
  }

  // -------------------------------------------------------------
  // 60fps Game Loop & Rendering
  // -------------------------------------------------------------
  function gameLoop() {
    update();
    render();
    animId = requestAnimationFrame(gameLoop);
  }

  function update() {
    // 1. Starfield parallax
    stars.forEach((s) => {
      s.y += s.speed;
      if (s.y > canvas.height) {
        s.y = 0;
        s.x = Math.random() * canvas.width;
      }
    });

    // 2. Laser beam decay
    for (let i = laserBeams.length - 1; i >= 0; i--) {
      laserBeams[i].alpha -= 0.08;
      if (laserBeams[i].alpha <= 0) laserBeams.splice(i, 1);
    }

    // 3. Particles
    for (let i = particles.length - 1; i >= 0; i--) {
      const p = particles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.alpha -= p.decay;
      if (p.alpha <= 0) particles.splice(i, 1);
    }

    // 4. Starship steering & physics
    player.idlePhase += 0.04;
    if (targetX !== null && targetY !== null) {
      const dx = targetX - player.x;
      const dy = targetY - player.y;
      const dist = Math.hypot(dx, dy);
      if (dist > 15) {
        const nx = dx / dist;
        const ny = dy / dist;
        player.vx += nx * 0.48;
        player.vy += ny * 0.48;
        player.targetAngle = Math.atan2(ny, nx);
        if (Math.random() > 0.3) emitThruster(player.x, player.y, player.angle);
      } else {
        targetX = null;
        targetY = null;
      }
    }

    player.vx *= 0.92;
    player.vy *= 0.92;
    player.x += player.vx * player.speed;
    player.y += player.vy * player.speed;

    // Angle interpolation
    let diff = player.targetAngle - player.angle;
    while (diff < -Math.PI) diff += Math.PI * 2;
    while (diff > Math.PI) diff -= Math.PI * 2;
    player.angle += diff * 0.2;

    // Bounds clamping
    player.x = Math.max(30, Math.min(canvas.width - 30, player.x));
    player.y = Math.max(canvas.height / 2, Math.min(canvas.height - 30, player.y));

    dockHub.pulse += 0.05;
    if (shakeTime > 0) shakeTime--;
  }

  function render() {
    ctx.save();

    // Screen Shake
    if (shakeTime > 0) {
      ctx.translate((Math.random() - 0.5) * 5, (Math.random() - 0.5) * 5);
    }

    // Parallax Void Background
    ctx.fillStyle = "#070b14";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Subtle Coordinate Grid
    ctx.strokeStyle = "rgba(56, 189, 248, 0.05)";
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 50) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
    }
    for (let y = 0; y < canvas.height; y += 50) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }

    // Stars
    stars.forEach((s) => {
      ctx.fillStyle = s.color;
      ctx.globalAlpha = s.alpha;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.size, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1.0;

    // Docking Orbital Guide
    ctx.strokeStyle = "rgba(56, 189, 248, 0.15)";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([6, 6]);
    ctx.beginPath();
    ctx.arc(dockHub.x, dockHub.y, 90, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Central Docking Station
    ctx.shadowColor = "#38bdf8";
    ctx.shadowBlur = Math.sin(dockHub.pulse) * 4 + 8;
    ctx.fillStyle = "rgba(15, 23, 42, 0.95)";
    ctx.strokeStyle = dockHub.docked ? "#4ade80" : "#38bdf8";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(dockHub.x, dockHub.y, dockHub.radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    ctx.shadowBlur = 0;
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = "bold 16px monospace";
    ctx.fillText(dockHub.docked ? "✦ DOCKED" : "✦ DOCK HUB", dockHub.x, dockHub.y);

    // Laser Beams
    laserBeams.forEach((b) => {
      ctx.strokeStyle = "#38bdf8";
      ctx.globalAlpha = b.alpha;
      ctx.lineWidth = 3.5;
      ctx.shadowColor = "#38bdf8";
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.moveTo(b.startX, b.startY);
      ctx.lineTo(b.endX, b.endY);
      ctx.stroke();
    });
    ctx.globalAlpha = 1.0;
    ctx.shadowBlur = 0;

    // Particles
    particles.forEach((p) => {
      ctx.fillStyle = p.color;
      ctx.globalAlpha = Math.max(0, p.alpha);
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1.0;

    // Leo's Starship (Procedural Vector Sprite)
    ctx.save();
    ctx.translate(player.x, player.y + Math.sin(player.idlePhase) * 2);
    ctx.rotate(player.angle + Math.PI / 2);

    ctx.fillStyle = "#38bdf8";
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.shadowColor = "#38bdf8";
    ctx.shadowBlur = 8;

    ctx.beginPath();
    ctx.moveTo(0, -player.size);
    ctx.lineTo(player.size * 0.75, player.size);
    ctx.lineTo(0, player.size * 0.5);
    ctx.lineTo(-player.size * 0.75, player.size);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    // Cockpit
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(0, -player.size * 0.2, 3.5, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
    ctx.restore();
  }

  // -------------------------------------------------------------
  // Event Bindings
  // -------------------------------------------------------------
  function startGame() {
    titleScreen.hidden = true;
    victoryScreen.hidden = true;
    playScreen.hidden = false;
    answeredCount = 0;
    initStars();

    T.startIdleWatch();
    T.capture("level_started", { session_length: totalSession });

    if (!animId) gameLoop();
    loadNextQuestion();
  }

  startBtn.addEventListener("click", startGame);
  replayBtn.addEventListener("click", startGame);
  formEl.addEventListener("submit", handleAnswerSubmit);

  inputEl.addEventListener("keydown", (e) => {
    T.recordKeystroke(e.key === "Backspace");
  });

  canvas.addEventListener("pointerdown", (e) => {
    const rect = canvas.getBoundingClientRect();
    targetX = (e.clientX - rect.left) * (canvas.width / rect.width);
    targetY = (e.clientY - rect.top) * (canvas.height / rect.height);
    T.markActive();
  });

  canvas.addEventListener("pointermove", (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) * (canvas.width / rect.width);
    const y = (e.clientY - rect.top) * (canvas.height / rect.height);
    T.recordPointerMove(x, y);
  });

  // Problem Reporting
  reportBtn.addEventListener("click", () => {
    reportDialog.hidden = false;
    reportText.focus();
  });

  reportCancel.addEventListener("click", () => {
    reportDialog.hidden = true;
    reportText.value = "";
  });

  reportSend.addEventListener("click", async () => {
    const desc = reportText.value.trim();
    if (!desc) return;
    try {
      await api(`/games/${C.GAME_ID}/report-problem`, {
        method: "POST",
        body: JSON.stringify({ description: desc }),
      });
      reportDialog.hidden = true;
      reportText.value = "";
      feedbackEl.textContent = "Thank you! Feedback reported.";
      feedbackEl.className = "feedback";
    } catch (e) {
      reportDialog.hidden = true;
    }
  });

  // Window unload telemetry
  window.addEventListener("beforeunload", () => {
    if (answeredCount < totalSession && !victoryScreen.hidden) {
      T.capture("level_abandoned", { progress_pct: Math.round((answeredCount / totalSession) * 100) });
    }
  });
})();
