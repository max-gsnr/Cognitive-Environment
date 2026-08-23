// PostHog behavioral telemetry and input/motion detectors for Orbit
(function () {
  const C = window.ORBIT;
  window.ORBIT_DEBUG_EVENTS = window.ORBIT_DEBUG_EVENTS || [];

  let vector = {};
  let idleTimer = null;
  let lastActivity = Date.now();
  let lastKeystroke = 0;
  let pointerHistory = [];

  function flatten(v) {
    const out = {};
    Object.keys(v || {}).forEach((key) => {
      out[key] = v[key];
    });
    return out;
  }

  const Telemetry = {
    setDifficultyVector(next) {
      vector = next || {};
    },

    capture(name, properties) {
      const payload = Object.assign(
        {
          game_id: C.GAME_ID,
          profile_id: C.PROFILE_ID,
          skill_id: C.SKILL_ID,
          version: C.VERSION,
        },
        flatten(vector),
        properties || {}
      );

      window.ORBIT_DEBUG_EVENTS.push({ event: name, properties: payload });

      if (window.posthog && typeof window.posthog.capture === "function") {
        try {
          window.posthog.capture(name, payload);
        } catch (e) {
          // Telemetry must never crash gameplay
        }
      }
    },

    startIdleWatch() {
      if (idleTimer) return;
      lastActivity = Date.now();
      idleTimer = window.setInterval(() => {
        const idleDuration = Date.now() - lastActivity;
        if (idleDuration >= 5000) {
          Telemetry.capture("idle_tick", { idle_duration_ms: idleDuration });
        }
      }, 5000);
    },

    stopIdleWatch() {
      if (idleTimer) {
        clearInterval(idleTimer);
        idleTimer = null;
      }
    },

    markActive() {
      lastActivity = Date.now();
    },

    recordKeystroke(isBackspace) {
      this.markActive();
      const now = Date.now();
      if (isBackspace && lastKeystroke > 0) {
        const delta = now - lastKeystroke;
        if (delta < 1000) {
          this.capture("edit_event", { type: "immediate_correction", delta_ms: delta });
        } else if (delta >= 2000) {
          this.capture("edit_event", { type: "after_pause_correction", delta_ms: delta });
        }
      }
      lastKeystroke = now;
    },

    recordPointerMove(x, y) {
      this.markActive();
      const now = Date.now();
      pointerHistory.push({ x, y, t: now });
      if (pointerHistory.length > 20) pointerHistory.shift();

      if (pointerHistory.length >= 10) {
        const first = pointerHistory[0];
        const last = pointerHistory[pointerHistory.length - 1];
        const netDist = Math.hypot(last.x - first.x, last.y - first.y);
        let totalDist = 0;
        for (let i = 1; i < pointerHistory.length; i++) {
          totalDist += Math.hypot(pointerHistory[i].x - pointerHistory[i - 1].x, pointerHistory[i].y - pointerHistory[i - 1].y);
        }

        // Repetitive orbit: sustained near-zero-net-displacement with large total motion over ~1s
        if (totalDist > 80 && netDist < 25 && (last.t - first.t) >= 800) {
          this.capture("motion_event", { type: "repetitive_orbit", total_dist: totalDist, net_dist: netDist });
          pointerHistory = [];
        }
      }
    }
  };

  window.Telemetry = Telemetry;
})();
