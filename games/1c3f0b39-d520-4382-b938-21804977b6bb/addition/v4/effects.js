(function () {
  function create(constraints, tuning) {
    const visual = constraints.visual || {};
    const audio = constraints.audio || {};
    const palette = window.ORBIT.PALETTE;
    const shakeAllowed = visual.animations !== "minimal_no_screen_shake";
    const particlesAllowed = visual.particle_effects === true;
    const soundAllowed = audio.sfx !== "none";
    const activeFloats = new Set();
    const activeTrails = [];
    const activeBursts = [];
    const timers = new Set();
    let audioContext = null;

    function getAudioContext() {
      if (!soundAllowed) return null;
      if (audioContext === null) {
        const AudioCtor = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtor) return null;
        audioContext = new AudioCtor();
      }
      if (audioContext.state === "suspended") audioContext.resume();
      return audioContext;
    }

    function tone(frequency, durationMs, startMs) {
      const context = getAudioContext();
      if (!context) return;
      const oscillator = context.createOscillator();
      const gain = context.createGain();
      const start = context.currentTime + startMs / 1000;
      const duration = durationMs / 1000;
      oscillator.type = "sine";
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0, start);
      gain.gain.linearRampToValueAtTime(tuning.audio.gain, start + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
      oscillator.connect(gain).connect(context.destination);
      oscillator.start(start);
      oscillator.stop(start + duration + 0.02);
    }

    function tap() {
      tone(tuning.audio.tapHz, tuning.audio.tapMs, 0);
    }

    function dock() {
      tuning.audio.chordHz.forEach(function (frequency, index) {
        tone(frequency, tuning.audio.chordMs, index * 50);
      });
    }

    function settle() {
      tone(tuning.audio.settleHz, tuning.audio.settleMs, 0);
    }

    function floatText(text, toneName, position) {
      const element = document.createElement("div");
      element.className = "effect-float " + (toneName || "good");
      element.textContent = text;
      const point =
        position || { x: window.innerWidth / 2, y: window.innerHeight / 2 };
      element.style.left = point.x + "px";
      element.style.top = point.y + "px";
      document.getElementById("hint-root").appendChild(element);
      const started = performance.now();
      const duration = tuning.feedback.floatMs;
      activeFloats.add(element);

      function animate(now) {
        if (!activeFloats.has(element)) return;
        const progress = Math.min(1, (now - started) / duration);
        const ease = 1 - Math.pow(1 - progress, 3);
        element.style.transform =
          "translate(-50%, " + -tuning.feedback.floatRisePx * ease + "px)";
        element.style.opacity = String(1 - progress);
        if (progress < 1) {
          requestAnimationFrame(animate);
        } else {
          activeFloats.delete(element);
          element.remove();
        }
      }

      requestAnimationFrame(animate);
    }

    function schedule(callback, delayMs) {
      const timer = window.setTimeout(function () {
        timers.delete(timer);
        callback();
      }, delayMs);
      timers.add(timer);
    }

    function snapshotActor(actor) {
      return { x: actor.x, y: actor.y, heading: actor.heading };
    }

    function drawHull(context, trail) {
      context.save();
      context.translate(trail.x, trail.y);
      context.rotate(trail.heading + Math.PI / 2);
      context.fillStyle = palette.warm;
      context.strokeStyle = palette.accent;
      context.lineWidth = 2;
      context.beginPath();
      context.moveTo(0, -25);
      context.lineTo(16, 15);
      context.lineTo(0, 9);
      context.lineTo(-16, 15);
      context.closePath();
      context.fill();
      context.stroke();
      context.restore();
    }

    function drawEffects(context, now) {
      const trailLife = tuning.effects.trailFadeMs;
      for (let index = activeTrails.length - 1; index >= 0; index -= 1) {
        const trail = activeTrails[index];
        const progress = (now - trail.started) / trailLife;
        if (progress >= 1) {
          activeTrails.splice(index, 1);
          continue;
        }
        context.globalAlpha = tuning.effects.trailAlpha * (1 - progress);
        drawHull(context, trail);
      }

      for (let index = activeBursts.length - 1; index >= 0; index -= 1) {
        const burst = activeBursts[index];
        const progress = (now - burst.started) / tuning.effects.burstMs;
        if (progress >= 1) {
          activeBursts.splice(index, 1);
          continue;
        }
        const ease = 1 - Math.pow(1 - progress, 3);
        burst.dots.forEach(function (dot) {
          context.globalAlpha = 1 - progress;
          context.fillStyle = dot.color;
          context.beginPath();
          context.arc(
            burst.x + Math.cos(dot.angle) * dot.distance * ease,
            burst.y + Math.sin(dot.angle) * dot.distance * ease,
            3,
            0,
            Math.PI * 2
          );
          context.fill();
        });
      }
      context.globalAlpha = 1;
    }

    function trail(actor) {
      if (!particlesAllowed || !actor) return;
      activeTrails.push(
        Object.assign(snapshotActor(actor), { started: performance.now() })
      );
      for (let index = 1; index < tuning.effects.trailCount; index += 1) {
        schedule(function () {
          activeTrails.push(
            Object.assign(snapshotActor(actor), { started: performance.now() })
          );
        }, index * tuning.effects.trailDelayMs);
      }
    }

    function burst(x, y) {
      if (!particlesAllowed) return;
      const colors = [palette.accent, palette.good, palette.warm];
      const dots = [];
      for (let index = 0; index < tuning.effects.burstCount; index += 1) {
        dots.push({
          angle: Math.random() * Math.PI * 2,
          distance: tuning.effects.burstSpreadPx * (0.4 + Math.random() * 0.6),
          color: colors[index % colors.length],
        });
      }
      activeBursts.push({ x: x, y: y, dots: dots, started: performance.now() });
    }

    function shakeLight() {
      if (!shakeAllowed) return;
      const runtime = window.ORBIT_RUNTIME;
      if (runtime && runtime.runner) {
        runtime.runner.startShake(
          tuning.effects.shakeLightPx,
          tuning.effects.shakeLightMs
        );
      }
    }

    function shakeMedium() {
      if (!shakeAllowed) return;
      const runtime = window.ORBIT_RUNTIME;
      if (runtime && runtime.runner) {
        runtime.runner.startShake(
          tuning.effects.shakeMediumPx,
          tuning.effects.shakeMediumMs
        );
      }
    }

    function clear() {
      activeFloats.forEach(function (element) {
        element.remove();
      });
      activeFloats.clear();
      timers.forEach(function (timer) {
        window.clearTimeout(timer);
      });
      timers.clear();
      activeTrails.length = 0;
      activeBursts.length = 0;
      const runtime = window.ORBIT_RUNTIME;
      if (runtime && runtime.runner) runtime.runner.clearShake();
    }

    const noop = function () {};
    return {
      shakeLight: shakeAllowed ? shakeLight : noop,
      shakeMedium: shakeAllowed ? shakeMedium : noop,
      trail: particlesAllowed ? trail : noop,
      burst: particlesAllowed ? burst : noop,
      draw: particlesAllowed ? drawEffects : noop,
      floatText: floatText,
      tap: soundAllowed ? tap : noop,
      dock: soundAllowed ? dock : noop,
      settle: soundAllowed ? settle : noop,
      clear: clear,
    };
  }

  window.Effects = { create: create };
})();
