// PostHog instrumentation plus the input/motion detectors that feed it.
// Every event carries the game identity and the current difficulty vector,
// flattened. Nothing here decides anything about the game itself.
(function () {
  const C = window.ORBIT;

  // Minimal PostHog loader (official snippet, trimmed to capture + init).
  !(function (t, e) {
    var o, n, p, r;
    e.__SV ||
      ((window.posthog = e),
      (e._i = []),
      (e.init = function (i, s, a) {
        function g(t, e) {
          var o = e.split(".");
          2 == o.length && ((t = t[o[0]]), (e = o[1]));
          t[e] = function () {
            t.push([e].concat(Array.prototype.slice.call(arguments, 0)));
          };
        }
        ((p = t.createElement("script")).type = "text/javascript"),
          (p.crossOrigin = "anonymous"),
          (p.async = !0),
          (p.src = (s.api_host || "https://us.i.posthog.com") + "/static/array.js"),
          (r = t.getElementsByTagName("script")[0]).parentNode.insertBefore(p, r);
        var u = e;
        for (
          void 0 !== a ? (u = e[a] = []) : (a = "posthog"),
            u.people = u.people || [],
            u.toString = function (t) {
              var e = "posthog";
              return "posthog" !== a && (e += "." + a), t || (e += " (stub)"), e;
            },
            u.people.toString = function () {
              return u.toString(1) + ".people (stub)";
            },
            o =
              "init capture register register_once unregister opt_out_capturing has_opted_out_capturing opt_in_capturing reset group identify".split(
                " "
              ),
            n = 0;
          n < o.length;
          n++
        )
          g(u, o[n]);
        e._i.push([i, s, a]);
      }),
      (e.__SV = 1));
  })(document, window.posthog || []);

  // Capture only. Feature flags, surveys, session recording and remote config
  // are all off: this game has one screen and no experiments, and every extra
  // request is one more thing that can fail in front of a child.
  posthog.init(C.POSTHOG_KEY, {
    api_host: C.POSTHOG_HOST,
    person_profiles: "identified_only",
    autocapture: false,
    capture_pageview: false,
    capture_pageleave: false,
    disable_session_recording: true,
    disable_surveys: true,
    disable_web_experiments: true,
    disable_external_dependency_loading: true,
    advanced_disable_decide: true,
    advanced_disable_feature_flags: true,
    advanced_disable_feature_flags_on_first_load: true,
  });

  let vector = {};

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
      try {
        posthog.capture(name, payload);
      } catch (err) {
        /* telemetry must never break play */
      }
      if (window.ORBIT_DEBUG_EVENTS) {
        window.ORBIT_DEBUG_EVENTS.push({ event: name, properties: payload });
      }
    },
  };

  window.Telemetry = Telemetry;

  // --- idle_tick: one event per 5s with no keyboard/pointer activity ---
  let lastActivity = Date.now();
  let idleEnabled = false;

  Telemetry.markActive = function () {
    lastActivity = Date.now();
  };
  Telemetry.startIdleWatch = function () {
    idleEnabled = true;
    lastActivity = Date.now();
  };
  Telemetry.stopIdleWatch = function () {
    idleEnabled = false;
  };

  setInterval(() => {
    if (!idleEnabled) return;
    if (Date.now() - lastActivity >= 5000) {
      lastActivity = Date.now();
      Telemetry.capture("idle_tick", {});
    }
  }, 1000);

  ["pointerdown", "pointermove", "keydown", "touchstart"].forEach((type) => {
    window.addEventListener(type, Telemetry.markActive, { passive: true });
  });

  // --- edit_event: a backspace classified by how long the child paused ---
  // Scoped to the answer box: a backspace in the report textarea is typing,
  // not a correction, and would otherwise inflate the correction signal.
  let lastKeystroke = 0;
  window.addEventListener("keydown", (event) => {
    if (!event.target || event.target.id !== "answer") return;
    if (event.key === "Backspace" || event.key === "Delete") {
      const gap = lastKeystroke ? Date.now() - lastKeystroke : Infinity;
      if (gap < 1000) {
        Telemetry.capture("edit_event", { type: "immediate_correction" });
      } else if (gap >= 2000) {
        Telemetry.capture("edit_event", { type: "after_pause_correction" });
      }
      lastKeystroke = Date.now();
      return;
    }
    if (event.key.length === 1) {
      lastKeystroke = Date.now();
    }
  });

  // --- motion_event: pointer-path shape, sampled from pointermove ---
  // micro_jitter: several direction reversals inside a small radius, fast.
  // repetitive_orbit: circular travel that comes back to where it started,
  // sustained for about a second or more.
  const samples = [];
  const MAX_SAMPLES = 90;
  let lastMotionEvent = 0;

  function emitMotion(type) {
    const now = Date.now();
    if (now - lastMotionEvent < 1500) return;
    lastMotionEvent = now;
    Telemetry.capture("motion_event", { type: type });
  }

  window.addEventListener(
    "pointermove",
    (event) => {
      const now = Date.now();
      samples.push({ x: event.clientX, y: event.clientY, t: now });
      if (samples.length > MAX_SAMPLES) samples.shift();

      const recent = samples.filter((s) => now - s.t <= 600);
      if (recent.length >= 8) {
        let reversals = 0;
        let travel = 0;
        let radius = 0;
        const first = recent[0];
        for (let i = 2; i < recent.length; i++) {
          const dx1 = recent[i - 1].x - recent[i - 2].x;
          const dy1 = recent[i - 1].y - recent[i - 2].y;
          const dx2 = recent[i].x - recent[i - 1].x;
          const dy2 = recent[i].y - recent[i - 1].y;
          if (dx1 * dx2 + dy1 * dy2 < 0) reversals++;
        }
        for (let i = 1; i < recent.length; i++) {
          travel += Math.hypot(
            recent[i].x - recent[i - 1].x,
            recent[i].y - recent[i - 1].y
          );
          radius = Math.max(
            radius,
            Math.hypot(recent[i].x - first.x, recent[i].y - first.y)
          );
        }
        if (reversals >= 4 && radius <= 40 && travel > 30) {
          emitMotion("micro_jitter");
        }
      }

      const window1s = samples.filter((s) => now - s.t <= 1400);
      if (window1s.length >= 14 && now - window1s[0].t >= 900) {
        let travel = 0;
        for (let i = 1; i < window1s.length; i++) {
          travel += Math.hypot(
            window1s[i].x - window1s[i - 1].x,
            window1s[i].y - window1s[i - 1].y
          );
        }
        const net = Math.hypot(
          window1s[window1s.length - 1].x - window1s[0].x,
          window1s[window1s.length - 1].y - window1s[0].y
        );
        if (travel > 220 && net < travel * 0.2) {
          emitMotion("repetitive_orbit");
        }
      }
    },
    { passive: true }
  );
})();
