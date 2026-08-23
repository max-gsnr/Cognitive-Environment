(function () {
  const C = window.ORBIT;
  const T = C.TUNING;
  const P = C.PALETTE;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  class PointerFollow {
    constructor() {
      this.lerp = T.actor.followLerp;
      this.maxSpeed = T.actor.maxSpeedPxPerSec;
      this.padding = T.actor.edgePaddingPx;
    }

    update(actor, target, dt, width, height) {
      const dx = target.x - actor.x;
      const dy = target.y - actor.y;
      const desiredX = Math.max(-this.maxSpeed, Math.min(this.maxSpeed, dx / dt));
      const desiredY = Math.max(-this.maxSpeed, Math.min(this.maxSpeed, dy / dt));
      actor.vx += (desiredX - actor.vx) * this.lerp;
      actor.vy += (desiredY - actor.vy) * this.lerp;
      actor.x = Math.max(
        this.padding,
        Math.min(width - this.padding, actor.x + actor.vx * dt)
      );
      actor.y = Math.max(
        this.padding,
        Math.min(height - this.padding, actor.y + actor.vy * dt)
      );
    }
  }

  class IdleBob {
    constructor() {
      this.amplitude = T.actor.bobAmplitudePx;
      this.period = T.actor.bobPeriodMs;
      this.idleAfter = T.actor.idleAfterMs;
      this.elapsed = 0;
    }

    update(dt, idleForMs) {
      this.elapsed = (this.elapsed + dt * 1000) % this.period;
      if (reducedMotion || idleForMs < this.idleAfter) return 0;
      const fade = Math.min(1, (idleForMs - this.idleAfter) / this.idleAfter);
      return (
        Math.sin((this.elapsed / this.period) * Math.PI * 2) *
        this.amplitude *
        fade
      );
    }
  }

  class HeadingAlign {
    constructor() {
      this.lerp = T.actor.headingLerp;
    }

    update(actor) {
      const speed = Math.hypot(actor.vx, actor.vy);
      if (speed <= 1) return;
      const target = Math.atan2(actor.vy, actor.vx);
      let delta = target - actor.heading;
      while (delta > Math.PI) delta -= Math.PI * 2;
      while (delta < -Math.PI) delta += Math.PI * 2;
      actor.heading += delta * this.lerp;
    }
  }

  class DockAction {
    constructor() {
      this.travelMs = T.dock.podTravelMs;
    }

    begin(actor, dock) {
      actor.pod = {
        x: actor.x,
        y: actor.y + 22,
        elapsed: 0,
        targetX: dock.x,
        targetY: dock.y,
      };
    }

    update(actor, dt) {
      if (!actor.pod) return null;
      actor.pod.elapsed += dt * 1000;
      const progress = Math.min(1, actor.pod.elapsed / this.travelMs);
      const ease = 1 - Math.pow(1 - progress, 3);
      actor.pod.x += (actor.pod.targetX - actor.pod.x) * ease;
      actor.pod.y += (actor.pod.targetY - actor.pod.y) * ease;
      if (progress >= 1) {
        actor.pod = null;
        return true;
      }
      return false;
    }
  }

  class Tug {
    constructor(x, y) {
      this.x = x;
      this.y = y;
      this.vx = 0;
      this.vy = 0;
      this.heading = -Math.PI / 2;
      this.bob = new IdleBob();
      this.follow = new PointerFollow();
      this.align = new HeadingAlign();
      this.dockAction = new DockAction();
      this.pod = null;
      this.parked = false;
      this.bobOffset = 0;
      this.lastTarget = { x: x, y: y };
      this.idleForMs = 0;
    }

    update(target, dt, width, height, dock) {
      if (target.x !== this.lastTarget.x || target.y !== this.lastTarget.y) {
        this.idleForMs = 0;
        this.lastTarget = { x: target.x, y: target.y };
      } else {
        this.idleForMs += dt * 1000;
      }
      if (this.parked) {
        this.vx = 0;
        this.vy = 0;
        this.x += (dock.x - this.x) * T.actor.followLerp;
        this.y += (dock.y + T.actor.edgePaddingPx - this.y) * T.actor.followLerp;
      } else {
        this.follow.update(this, target, dt, width, height);
        this.align.update(this);
      }
      this.bobOffset = this.bob.update(dt, this.idleForMs);
      this.dockAction.update(this, dt);
    }

    dock(dock) {
      this.dockAction.begin(this, dock);
    }
  }

  function createStars(spec) {
    const stars = [];
    for (let index = 0; index < spec.count; index += 1) {
      stars.push({
        x: Math.random() * T.loop.logicalWidth,
        y: Math.random() * T.loop.logicalHeight,
        radius: spec.radius,
        alpha: spec.alpha,
        drift: spec.driftPxPerSec,
      });
    }
    return stars;
  }

  function updateStars(stars, dt) {
    stars.forEach(function (star) {
      if (reducedMotion) return;
      star.x -= star.drift * dt;
      if (star.x < -star.radius) star.x = T.loop.logicalWidth + star.radius;
    });
  }

  function drawStars(context, stars) {
    stars.forEach(function (star) {
      context.globalAlpha = star.alpha;
      context.fillStyle = P.ink;
      context.beginPath();
      context.arc(star.x, star.y, star.radius, 0, Math.PI * 2);
      context.fill();
    });
    context.globalAlpha = 1;
  }

  function drawBackground(context) {
    const gradient = context.createLinearGradient(
      0,
      0,
      0,
      T.loop.logicalHeight
    );
    gradient.addColorStop(0, P.spaceNear);
    gradient.addColorStop(1, P.spaceFar);
    context.fillStyle = gradient;
    context.fillRect(0, 0, T.loop.logicalWidth, T.loop.logicalHeight);
    const bloom = context.createRadialGradient(
      T.loop.logicalWidth / 2,
      T.loop.logicalHeight * 0.25,
      0,
      T.loop.logicalWidth / 2,
      T.loop.logicalHeight * 0.25,
      T.loop.logicalWidth * 0.6
    );
    bloom.addColorStop(0, "rgba(159, 182, 240, .10)");
    bloom.addColorStop(1, "rgba(159, 182, 240, 0)");
    context.fillStyle = bloom;
    context.fillRect(0, 0, T.loop.logicalWidth, T.loop.logicalHeight);
  }

  function drawDock(context, dock, docked) {
    const breathe = reducedMotion
      ? T.dock.padAlphaMin
      : T.dock.padAlphaMin +
        (T.dock.padAlphaMax - T.dock.padAlphaMin) *
          ((Math.sin((performance.now() / T.dock.padBreatheMs) * Math.PI * 2) + 1) /
            2);
    context.save();
    context.strokeStyle = P.edge;
    context.lineWidth = T.dock.guideLineWidth;
    context.globalAlpha = T.dock.guideAlpha;
    context.setLineDash(T.dock.guideDash);
    context.beginPath();
    context.ellipse(
      dock.x,
      dock.y,
      T.dock.approachRadiusX,
      T.dock.approachRadiusY,
      0,
      0,
      Math.PI * 2
    );
    context.stroke();
    context.setLineDash([]);
    context.globalAlpha = breathe;
    context.strokeStyle = P.accent;
    context.lineWidth = T.dock.ringLineWidth;
    context.beginPath();
    context.arc(dock.x, dock.y, T.dock.ringRadius, 0, Math.PI * 2);
    context.stroke();
    context.lineWidth = T.dock.tickLineWidth;
    context.beginPath();
    context.moveTo(dock.x - T.dock.guideTickOuter, dock.y);
    context.lineTo(dock.x - T.dock.guideTickInner, dock.y);
    context.moveTo(dock.x + T.dock.guideTickInner, dock.y);
    context.lineTo(dock.x + T.dock.guideTickOuter, dock.y);
    context.stroke();
    context.globalAlpha = 1;
    for (let index = 0; index < docked; index += 1) {
      const angle = -Math.PI / 2 + (index * Math.PI * 2) / C.SESSION_LENGTH;
      context.fillStyle = P.good;
      context.beginPath();
      context.arc(
        dock.x + Math.cos(angle) * T.dock.ringRadius,
        dock.y + Math.sin(angle) * T.dock.ringRadius,
        7,
        0,
        Math.PI * 2
      );
      context.fill();
    }
    context.fillStyle = P.ink;
    context.font = "600 " + T.dock.labelFontPx + "px ui-rounded, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(docked > 0 ? "Docked" : "Dock", dock.x, dock.y);
    context.restore();
  }

  function drawPod(context, pod) {
    if (!pod) return;
    context.save();
    context.fillStyle = P.good;
    context.strokeStyle = P.edge;
    context.lineWidth = 2;
    context.beginPath();
    for (let index = 0; index < 6; index += 1) {
      const angle = (index * Math.PI) / 3;
      const x = pod.x + Math.cos(angle) * 10;
      const y = pod.y + Math.sin(angle) * 10;
      if (index === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    }
    context.closePath();
    context.fill();
    context.stroke();
    context.restore();
  }

  function drawTug(context, tug) {
    context.save();
    context.translate(tug.x, tug.y + tug.bobOffset);
    context.rotate(tug.heading + Math.PI / 2);
    context.fillStyle = P.warm;
    context.strokeStyle = P.accent;
    context.lineWidth = 2;
    context.beginPath();
    context.moveTo(0, -25);
    context.lineTo(16, 15);
    context.lineTo(0, 9);
    context.lineTo(-16, 15);
    context.closePath();
    context.fill();
    context.stroke();
    context.fillStyle = P.accent;
    context.beginPath();
    context.arc(0, -5, 8, Math.PI, 0);
    context.lineTo(8, -5);
    context.lineTo(-8, -5);
    context.closePath();
    context.fill();
    context.fillStyle = P.edge;
    context.beginPath();
    context.moveTo(-17, 8);
    context.lineTo(-25, 18);
    context.lineTo(-13, 15);
    context.closePath();
    context.fill();
    context.beginPath();
    context.moveTo(17, 8);
    context.lineTo(25, 18);
    context.lineTo(13, 15);
    context.closePath();
    context.fill();
    context.fillStyle = P.good;
    context.beginPath();
    context.arc(0, -23, 3, 0, Math.PI * 2);
    context.fill();
    context.restore();
  }

  const World = {
    runner: null,
    pointer: { x: T.loop.logicalWidth / 2, y: T.loop.logicalHeight * 0.78 },
    dock: { x: T.loop.logicalWidth / 2, y: T.loop.logicalHeight * 0.28 },
    actor: null,
    starsFar: [],
    starsMid: [],
    starsNear: [],
    docked: 0,
    complete: false,

    reset() {
      this.pointer = {
        x: T.loop.logicalWidth / 2,
        y: T.loop.logicalHeight * 0.78,
      };
      this.actor = new Tug(
        T.loop.logicalWidth / 2,
        T.loop.logicalHeight * 0.75
      );
      this.starsFar = createStars(T.stars.far);
      this.starsMid = createStars(T.stars.mid);
      this.starsNear = createStars(T.stars.near);
      this.docked = 0;
      this.complete = false;
    },

    init(runner) {
      this.runner = runner;
      this.reset();
      this.onPointerMove = (event) => {
        this.pointer = runner.toLogical(event.clientX, event.clientY);
      };
      window.addEventListener("pointermove", this.onPointerMove, { passive: true });
    },

    update(dt) {
      updateStars(this.starsFar, dt);
      updateStars(this.starsMid, dt);
      updateStars(this.starsNear, dt);
      this.actor.update(
        this.pointer,
        dt,
        T.loop.logicalWidth,
        T.loop.logicalHeight,
        this.dock
      );
    },

    draw(context, sceneKey) {
      drawBackground(context);
      drawStars(context, this.starsFar);
      drawDock(context, this.dock, this.docked);
      drawStars(context, this.starsMid);
      drawTug(context, this.actor);
      drawPod(context, this.actor.pod);
      drawStars(context, this.starsNear);
    },

    dockPod() {
      this.actor.dock(this.dock);
      this.docked += 1;
    },

    actorPosition() {
      return { x: this.actor.x, y: this.actor.y };
    },

    setComplete() {
      this.complete = true;
      this.actor.parked = true;
    },
  };

  const runner = new window.Runner(document.getElementById("scene"));
  World.init(runner);
  window.OrbitWorld = World;
  let abandonmentSent = false;
  const resetAbandonment = function () {
    abandonmentSent = false;
  };
  window.ORBIT_RUNTIME = {
    runner: runner,
    world: World,
    session: null,
    resetAbandonment: resetAbandonment,
  };
  const abandon = function () {
    if (
      runner.sceneKey !== "play" ||
      World.complete ||
      abandonmentSent ||
      !window.ORBIT_RUNTIME.session
    ) {
      return;
    }
    abandonmentSent = true;
    Telemetry.capture("level_abandoned", {
      progress_pct: Math.round(
        (window.ORBIT_RUNTIME.session.progress() / C.SESSION_LENGTH) * 100
      ),
    });
  };
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) abandon();
  });
  window.addEventListener("pagehide", abandon);
  runner.start(window.SCENE_ORDER[0]);
})();
