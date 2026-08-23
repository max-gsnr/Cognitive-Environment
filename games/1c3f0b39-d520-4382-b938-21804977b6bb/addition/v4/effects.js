(function () {
  function create(constraints, tuning) {
    const visual = constraints.visual || {};
    const audio = constraints.audio || {};
    const shakeAllowed = visual.animations !== "minimal_no_screen_shake";
    const particlesAllowed = visual.particle_effects === true;
    const soundAllowed = audio.sfx !== "none";
    const activeFloats = new Set();
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
      const point = position || { x: window.innerWidth / 2, y: window.innerHeight / 2 };
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

    function clear() {
      activeFloats.forEach(function (element) {
        element.remove();
      });
      activeFloats.clear();
    }

    const noop = function () {};
    const shakeLight = shakeAllowed
      ? function () {
          return undefined;
        }
      : noop;
    const shakeMedium = shakeAllowed
      ? function () {
          return undefined;
        }
      : noop;
    const trail = particlesAllowed
      ? function () {
          return undefined;
        }
      : noop;
    const burst = particlesAllowed
      ? function () {
          return undefined;
        }
      : noop;
    return {
      shakeLight: shakeLight,
      shakeMedium: shakeMedium,
      trail: trail,
      burst: burst,
      floatText: floatText,
      tap: soundAllowed ? tap : noop,
      dock: soundAllowed ? dock : noop,
      settle: soundAllowed ? settle : noop,
      clear: clear,
    };
  }

  window.Effects = { create: create };
})();
