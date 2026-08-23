(function () {
  const C = window.ORBIT;
  const T = C.TUNING;
  const SCENE_ORDER = ["title", "intro", "play", "complete"];

  function apiRequest(path, options, onController) {
    const controller = new AbortController();
    if (onController) onController(controller);
    const timeout = window.setTimeout(
      function () {
        controller.abort();
      },
      T.net.requestTimeoutMs
    );
    const request = Object.assign({}, options || {}, { signal: controller.signal });
    return fetch(C.API_BASE + path, request).then(function (response) {
      window.clearTimeout(timeout);
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    }, function (error) {
      window.clearTimeout(timeout);
      throw error;
    });
  }

  class BaseScene {
    constructor(runner) {
      this.runner = runner;
    }

    onPreCreate() {}
    onCreate() {}
    onPostCreate() {}
    onUpdate() {}
    onDraw() {}
    onExit() {}
  }

  class Runner {
    constructor(canvas) {
      this.canvas = canvas;
      this.context = canvas.getContext("2d");
      this.logicalWidth = T.loop.logicalWidth;
      this.logicalHeight = T.loop.logicalHeight;
      this.scale = 1;
      this.offsetX = 0;
      this.offsetY = 0;
      this.dpr = 1;
      this.scene = null;
      this.sceneKey = null;
      this.accumulator = 0;
      this.shakeAmplitude = 0;
      this.shakeStarted = 0;
      this.shakeUntil = 0;
      this.lastFrame = performance.now();
      this.resize = this.resize.bind(this);
      this.frame = this.frame.bind(this);
      window.addEventListener("resize", this.resize);
      this.resize();
      requestAnimationFrame(this.frame);
    }

    resize() {
      this.dpr = Math.min(window.devicePixelRatio || 1, 2);
      const bounds = this.canvas.getBoundingClientRect();
      const width = bounds.width;
      const height = bounds.height;
      this.scale = Math.min(
        width / this.logicalWidth,
        height / this.logicalHeight
      );
      this.offsetX = (width - this.logicalWidth * this.scale) / 2;
      this.offsetY = (height - this.logicalHeight * this.scale) / 2;
      this.canvas.width = Math.floor(width * this.dpr);
      this.canvas.height = Math.floor(height * this.dpr);
      this.canvas.style.width = width + "px";
      this.canvas.style.height = height + "px";
    }

    toLogical(clientX, clientY) {
      const bounds = this.canvas.getBoundingClientRect();
      return {
        x: (clientX - bounds.left - this.offsetX) / this.scale,
        y: (clientY - bounds.top - this.offsetY) / this.scale,
      };
    }

    toScreen(point) {
      return {
        x: this.offsetX + point.x * this.scale,
        y: this.offsetY + point.y * this.scale,
      };
    }

    startShake(amplitude, durationMs) {
      this.shakeAmplitude = amplitude;
      this.shakeStarted = performance.now();
      this.shakeUntil = this.shakeStarted + durationMs;
    }

    clearShake() {
      this.shakeAmplitude = 0;
      this.shakeStarted = 0;
      this.shakeUntil = 0;
    }

    shakeOffset(now) {
      if (this.shakeAmplitude === 0 || now >= this.shakeUntil) {
        this.clearShake();
        return { x: 0, y: 0 };
      }
      const progress =
        (now - this.shakeStarted) / (this.shakeUntil - this.shakeStarted);
      const fade = 1 - progress;
      return {
        x: Math.sin(progress * Math.PI * 8) * this.shakeAmplitude * fade,
        y: Math.cos(progress * Math.PI * 6) * this.shakeAmplitude * fade,
      };
    }

    start(key) {
      if (SCENE_ORDER.indexOf(key) < 0) {
        throw new Error("Unknown scene: " + key);
      }
      if (this.scene) this.scene.onExit();
      const SceneType = {
        title: TitleScene,
        intro: IntroScene,
        play: PlayScene,
        complete: CompleteScene,
      }[key];
      this.sceneKey = key;
      this.scene = new SceneType(this);
      this.scene.onPreCreate();
      this.scene.onCreate();
      this.scene.onPostCreate();
    }

    frame(now) {
      const elapsed = Math.min(now - this.lastFrame, T.loop.stepMs * T.loop.maxCatchUpSteps);
      this.lastFrame = now;
      this.accumulator += elapsed;
      let steps = 0;
      while (this.accumulator >= T.loop.stepMs && steps < T.loop.maxCatchUpSteps) {
        if (this.scene) this.scene.onUpdate(T.loop.stepMs / 1000);
        this.accumulator -= T.loop.stepMs;
        steps += 1;
      }
      this.context.setTransform(1, 0, 0, 1, 0, 0);
      this.context.clearRect(0, 0, this.canvas.width, this.canvas.height);
      const shake = this.shakeOffset(now);
      this.context.setTransform(
        this.dpr * this.scale,
        0,
        0,
        this.dpr * this.scale,
        this.dpr * (this.offsetX + shake.x),
        this.dpr * (this.offsetY + shake.y)
      );
      if (this.scene) this.scene.onDraw(this.context);
      requestAnimationFrame(this.frame);
    }
  }

  class TitleScene extends BaseScene {
    onCreate() {
      this.panel = document.createElement("section");
      this.panel.className = "scene-copy";
      const heading = document.createElement("h1");
      heading.textContent = "Orbit Tug";
      this.startButton = document.createElement("button");
      this.startButton.className = "primary";
      this.startButton.type = "button";
      this.startButton.textContent = "Start";
      this.panel.append(heading, this.startButton);
      document.getElementById("hud-root").appendChild(this.panel);
    }

    onDraw(context) {
      window.OrbitWorld.draw(context, "title");
    }

    onPostCreate() {
      this.onStart = () => this.runner.start("intro");
      this.onKeyDown = (event) => {
        if (event.key === "Enter") this.onStart();
      };
      this.startButton.addEventListener("click", this.onStart);
      document.addEventListener("keydown", this.onKeyDown);
    }

    onExit() {
      this.startButton.removeEventListener("click", this.onStart);
      document.removeEventListener("keydown", this.onKeyDown);
      this.panel.remove();
    }
  }

  class IntroScene extends BaseScene {
    onPreCreate() {
      this.lineIndex = 0;
      this.visibleChars = 0;
      this.elapsed = 0;
      this.finished = false;
    }

    onCreate() {
      this.panel = document.createElement("section");
      this.panel.className = "scene-copy";
      this.dialogue = document.createElement("p");
      this.dialogue.className = "dialogue";
      this.continueButton = document.createElement("button");
      this.continueButton.className = "primary";
      this.continueButton.type = "button";
      this.continueButton.textContent = "Continue";
      this.panel.append(this.dialogue, this.continueButton);
      document.getElementById("hud-root").appendChild(this.panel);
      this.lines = ["Ten pods to dock.", "Type the number, press Send."];
      this.renderLine();
    }

    onPostCreate() {
      this.onAdvance = () => {
        if (!this.finished) {
          this.visibleChars = this.lines[this.lineIndex].length;
          this.finished = true;
          this.renderLine();
          return;
        }
        if (this.lineIndex < this.lines.length - 1) {
          this.lineIndex += 1;
          this.visibleChars = 0;
          this.elapsed = 0;
          this.finished = false;
          this.renderLine();
          return;
        }
        this.runner.start("play");
      };
      this.onKeyDown = (event) => {
        if (event.key === "Enter" || event.key === " ") this.onAdvance();
      };
      this.continueButton.addEventListener("click", this.onAdvance);
      document.addEventListener("keydown", this.onKeyDown);
    }

    onUpdate(dt) {
      if (this.finished) return;
      this.elapsed += dt * 1000;
      const nextChars = Math.floor(this.elapsed / T.intro.typewriterMsPerChar);
      if (nextChars >= this.lines[this.lineIndex].length) {
        this.visibleChars = this.lines[this.lineIndex].length;
        this.finished = true;
      } else {
        this.visibleChars = nextChars;
      }
      this.renderLine();
    }

    onDraw(context) {
      window.OrbitWorld.draw(context, "intro");
    }

    onExit() {
      this.continueButton.removeEventListener("click", this.onAdvance);
      document.removeEventListener("keydown", this.onKeyDown);
      this.panel.remove();
      Telemetry.capture("level_started", {});
    }

    renderLine() {
      if (!this.dialogue) return;
      this.dialogue.textContent = this.lines[this.lineIndex].slice(
        0,
        this.visibleChars
      );
    }
  }

  class Session {
    constructor(callbacks) {
      this.callbacks = callbacks;
      this.question = null;
      this.inFlight = false;
      this.answered = 0;
      this.questionStartedAt = 0;
      this.nextTimer = null;
      this.controller = null;
      this.stopped = false;
    }

    start() {
      this.stopped = false;
      this.answered = 0;
      this.question = null;
      this.callbacks.onProgress(this.answered);
      this.fetchNext();
    }

    current() {
      return this.question;
    }

    progress() {
      return this.answered;
    }

    isComplete() {
      return this.answered >= C.SESSION_LENGTH;
    }

    fetchNext() {
      if (this.inFlight || this.stopped) return;
      this.inFlight = true;
      this.callbacks.onSendEnabled(false);
      apiRequest(
        "/profiles/" +
          C.PROFILE_ID +
          "/skills/" +
          C.SKILL_ID +
          "/next-question",
        null,
        (controller) => {
          this.controller = controller;
        }
      ).then((question) => {
        if (this.stopped) return;
        this.controller = null;
        this.question = question;
        this.questionStartedAt = performance.now();
        this.inFlight = false;
        Telemetry.setDifficultyVector(question.difficulty_vector_snapshot);
        Telemetry.capture("problem_shown", {
          operands: question.operands,
          operator: question.operator,
          correct_answer: question.correct_answer,
        });
        this.callbacks.onQuestion(question);
        this.callbacks.onSendEnabled(true);
      }).catch(() => {
        if (this.stopped) return;
        this.controller = null;
        this.question = null;
        this.inFlight = false;
        this.callbacks.onQuestion(null);
        this.callbacks.onMessage(
          "Lost the signal. Press Send to try again.",
          "gentle"
        );
        this.callbacks.onSendEnabled(true);
      });
    }

    submit(rawText) {
      if (this.inFlight || this.stopped) return;
      if (!this.question) {
        this.callbacks.onMessage(
          "Lost the signal. Press Send to try again.",
          "gentle"
        );
        this.fetchNext();
        return;
      }
      const raw = String(rawText).trim();
      if (!/^\d+$/.test(raw)) {
        this.callbacks.onMessage("Numbers only — try 0 to 9.", "hint");
        this.callbacks.onFocusAnswer();
        return;
      }
      this.inFlight = true;
      this.callbacks.onSendEnabled(false);
      const question = this.question;
      const started = this.questionStartedAt;
      apiRequest("/attempts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_id: C.PROFILE_ID,
          skill_id: C.SKILL_ID,
          operands: question.operands,
          operator: question.operator,
          answer_given: Number(raw),
          latency_to_submit_ms: Math.max(
            0,
            Math.round(performance.now() - started)
          ),
        }),
      }, (controller) => {
        this.controller = controller;
      }).then((result) => {
        if (this.stopped) return;
        this.controller = null;
        this.question = null;
        this.inFlight = false;
        this.answered += 1;
        this.callbacks.onProgress(this.answered);
        Telemetry.setDifficultyVector(result.updated_difficulty_vector);
        Telemetry.capture("answer_submitted", {
          correct: result.is_correct,
          time_to_solve_ms: Math.round(performance.now() - started),
          error_class: result.error_class,
        });
        if (result.is_correct) {
          this.callbacks.onDock();
          this.callbacks.onMessage("Docked.", "good");
        } else {
          this.callbacks.onMessage(
            "Almost — it was " + question.correct_answer + ". Next one.",
            "gentle"
          );
        }
        if (this.isComplete()) {
          this.nextTimer = window.setTimeout(
            () => this.callbacks.onComplete(),
            T.feedback.holdMs
          );
        } else {
          this.nextTimer = window.setTimeout(
            () => this.fetchNext(),
            T.feedback.holdMs
          );
        }
      }).catch(() => {
        if (this.stopped) return;
        this.controller = null;
        this.inFlight = false;
        this.callbacks.onMessage(
          "That didn't send. Press Send to try again.",
          "gentle"
        );
        this.callbacks.onSendEnabled(true);
      });
    }

    retry() {
      if (!this.question && !this.stopped) this.fetchNext();
    }

    stop() {
      this.stopped = true;
      if (this.nextTimer !== null) window.clearTimeout(this.nextTimer);
      this.nextTimer = null;
      this.question = null;
      this.inFlight = false;
      if (this.controller) this.controller.abort();
      this.controller = null;
    }
  }

  class PlayScene extends BaseScene {
    onPreCreate() {
      window.OrbitWorld.reset();
      window.ORBIT_RUNTIME.resetAbandonment();
      this.hud = null;
      this.effects = null;
      this.session = null;
    }

    onCreate() {
      this.effects = window.Effects.create(C.CONSTRAINTS, T);
      this.hud = new window.Hud(T, {
        onAnswer: (value) => {
          this.effects.tap();
          this.session.submit(value);
        },
        onActivity: () => Telemetry.markActive(),
        onReport: (description) => this.reportProblem(description),
      });
      this.hud.mount();
      this.session = new Session({
        onQuestion: (question) => this.hud.setQuestion(question),
        onProgress: (answered) => this.hud.setProgress(answered),
        onMessage: (text, tone) => this.showFeedback(text, tone),
        onSendEnabled: (enabled) => this.hud.setSendEnabled(enabled),
        onFocusAnswer: () => this.hud.focusAnswer(),
        onDock: () => {
          this.effects.trail(window.OrbitWorld.actor);
          this.effects.burst(
            window.OrbitWorld.dock.x,
            window.OrbitWorld.dock.y
          );
          window.OrbitWorld.dockPod();
          this.effects.shakeLight();
          this.effects.dock();
          this.effects.floatText(
            "Docked.",
            "good",
            this.runner.toScreen(window.OrbitWorld.actorPosition())
          );
        },
        onComplete: () => this.runner.start("complete"),
      });
      window.ORBIT_RUNTIME.session = this.session;
    }

    onPostCreate() {
      this.session.start();
      Telemetry.startIdleWatch();
      this.hud.focusAnswer();
    }

    onUpdate(dt) {
      window.OrbitWorld.update(dt);
    }

    onDraw(context) {
      window.OrbitWorld.draw(context, "play");
      this.effects.draw(context, performance.now());
    }

    onExit() {
      Telemetry.stopIdleWatch();
      this.session.stop();
      window.ORBIT_RUNTIME.session = null;
      this.hud.unmount();
      this.effects.clear();
    }

    showFeedback(text, tone) {
      this.hud.setFeedback(text, tone);
      if (tone === "gentle" && text.indexOf("Almost") === 0) {
        this.effects.settle();
      }
    }

    reportProblem(description) {
      return apiRequest("/games/" + C.GAME_ID + "/report-problem", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description: description }),
      }).then(
        function () {
          return true;
        },
        function () {
          return false;
        }
      );
    }
  }

  class CompleteScene extends BaseScene {
    onCreate() {
      this.panel = document.createElement("section");
      this.panel.className = "scene-copy";
      const heading = document.createElement("h2");
      heading.textContent = "That's all ten.";
      this.panel.appendChild(heading);
      document.getElementById("hud-root").appendChild(this.panel);
      window.OrbitWorld.setComplete();
    }

    onDraw(context) {
      window.OrbitWorld.draw(context, "complete");
    }

    onPostCreate() {
      Telemetry.capture("level_completed", {});
    }

    onExit() {
      this.panel.remove();
    }
  }

  window.SCENE_ORDER = SCENE_ORDER;
  window.Runner = Runner;
  window.Session = Session;
  window.PlayScene = PlayScene;
})();
