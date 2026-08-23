// PostHog telemetry plus the input and motion detectors. Telemetry never
// affects gameplay: every capture is wrapped so a failure cannot break a turn.
(function () {
  const C = window.ORBIT;
  window.ORBIT_DEBUG_EVENTS = window.ORBIT_DEBUG_EVENTS || [];

  let vector = {};
  let idleTimer = null;
  let lastActivity = Date.now();
  let lastKeystrokeAt = 0;
  let idleTicksSent = 0;
  let points = [];
  let lastMotionEventAt = 0;

  function loadPostHog() {
    if (!C.POSTHOG_KEY) return;
    const script = document.createElement("script");
    script.async = true;
    script.src = C.POSTHOG_HOST + "/static/array.js";
    script.onload = function () {
      if (window.posthog && typeof window.posthog.init === "function") {
        window.posthog.init(C.POSTHOG_KEY, {
          api_host: C.POSTHOG_HOST,
          autocapture: false,
          capture_pageview: false,
        });
      }
    };
    document.head.appendChild(script);
  }

  const Telemetry = {
    setDifficultyVector(next) {
      vector = next || {};
    },

    capture(event, properties) {
      const payload = Object.assign(
        {
          game_id: C.GAME_ID,
          profile_id: C.PROFILE_ID,
          skill_id: C.SKILL_ID,
          version: C.VERSION,
        },
        vector,
        properties || {}
      );
      window.ORBIT_DEBUG_EVENTS.push({ event: event, properties: payload });
      try {
        if (window.posthog && typeof window.posthog.capture === "function") {
          window.posthog.capture(event, payload);
        }
      } catch (err) {
        /* never let telemetry break play */
      }
    },

    markActive() {
      lastActivity = Date.now();
      idleTicksSent = 0;
    },

    startIdleWatch() {
      if (idleTimer) return;
      this.markActive();
      // One tick per 5s of continuous idleness, counted from the last activity.
      idleTimer = window.setInterval(() => {
        const idleMs = Date.now() - lastActivity;
        const due = Math.floor(idleMs / 5000);
        if (due > idleTicksSent) {
          idleTicksSent = due;
          Telemetry.capture("idle_tick", { idle_ms: idleMs });
        }
      }, 1000);
    },

    stopIdleWatch() {
      if (idleTimer) {
        window.clearInterval(idleTimer);
        idleTimer = null;
      }
    },

    // A backspace under 1s after the previous keystroke is an immediate
    // correction; 2s or more means the child paused first.
    recordKeystroke(isBackspace) {
      this.markActive();
      const now = Date.now();
      if (isBackspace && lastKeystrokeAt) {
        const gap = now - lastKeystrokeAt;
        if (gap < 1000) {
          this.capture("edit_event", { type: "immediate_correction", gap_ms: gap });
        } else if (gap >= 2000) {
          this.capture("edit_event", { type: "after_pause_correction", gap_ms: gap });
        }
      }
      lastKeystrokeAt = now;
    },

    recordPointer(x, y) {
      this.markActive();
      const now = Date.now();
      points.push({ x: x, y: y, t: now });
      while (points.length && now - points[0].t > 1600) points.shift();
      if (points.length < 8) return;
      if (now - lastMotionEventAt < 1500) return;

      const first = points[0];
      const last = points[points.length - 1];
      const span = last.t - first.t;
      const net = Math.hypot(last.x - first.x, last.y - first.y);
      let path = 0;
      let reversals = 0;
      let maxRadius = 0;
      const cx = points.reduce((s, p) => s + p.x, 0) / points.length;
      const cy = points.reduce((s, p) => s + p.y, 0) / points.length;
      for (let i = 1; i < points.length; i++) {
        path += Math.hypot(points[i].x - points[i - 1].x, points[i].y - points[i - 1].y);
        maxRadius = Math.max(maxRadius, Math.hypot(points[i].x - cx, points[i].y - cy));
        if (i > 1) {
          const ax = points[i - 1].x - points[i - 2].x;
          const ay = points[i - 1].y - points[i - 2].y;
          const bx = points[i].x - points[i - 1].x;
          const by = points[i].y - points[i - 1].y;
          if (ax * bx + ay * by < 0) reversals++;
        }
      }

      // Micro jitter: rapid direction reversals inside a small radius.
      if (reversals >= 4 && maxRadius <= 30 && span <= 900) {
        lastMotionEventAt = now;
        this.capture("motion_event", {
          type: "micro_jitter",
          reversals: reversals,
          radius_px: Math.round(maxRadius),
          span_ms: span,
        });
        points = [];
        return;
      }

      // Repetitive orbit: a long path that goes nowhere, sustained ~1s or more.
      if (span >= 1000 && path >= 180 && net <= 40) {
        lastMotionEventAt = now;
        this.capture("motion_event", {
          type: "repetitive_orbit",
          path_px: Math.round(path),
          net_px: Math.round(net),
          span_ms: span,
        });
        points = [];
      }
    },
  };

  loadPostHog();
  window.Telemetry = Telemetry;
})();
