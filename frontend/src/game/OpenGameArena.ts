/**
 * OpenGame Dynamic Multi-Theme Engine
 * 
 * Bespoke 60fps canvas gameplay tailored to each child's interest:
 * - 🍝 Max (Spaghetti / Cooking): Real plate of steaming pasta with meatballs.
 *   Each correct answer lifts a twirling forkful of noodles; after 10 questions the plate is empty!
 * - 🎾 Lena (Tennis): A real tennis match where each correct answer serves a high-velocity
 *   ace past the opposing player across the net for a match point!
 * - 🦕 Maya (Dinosaurs): Archaeological excavation where an archaeology brush sweeps away
 *   mounds of sand to unearth a glowing, cartoonish T-Rex skeleton with teeth, ribs, claws, and tail!
 * - 🎨 Sophie (Astronomy / Drawing): Vincent van Gogh's Starry Night studio with an easel and canvas.
 *   Each question paints another rich stroke-by-stroke oil layer with radiant halo stars and golden crescent moon!
 * - 🚀 Leo (Space / Asteroids): Cartoon spaceship blaster shooting floating cratered asteroids with twin plasma lasers!
 */

import { AttemptResult, Question, api } from "../api";
import { capture } from "../telemetry";
import { ParticleSystem } from "./ParticleSystem";
import { soundFx } from "./SoundFx";

export interface GameTheme {
  id: string;
  name: string;
  playerLabel: string;
  successLabel: string;
  bgColor: string;
  accentColor: string;
}

export const THEMES: Record<string, GameTheme> = {
  cooking: {
    id: "cooking",
    name: "🍝 Spaghetti Feast",
    playerLabel: "Fork",
    successLabel: "✦ Delicious Bite Eaten!",
    bgColor: "#1c100d",
    accentColor: "#ef4444",
  },
  tennis: {
    id: "tennis",
    name: "🎾 Grand Slam Match",
    playerLabel: "Lena (Server)",
    successLabel: "✦ ACE! Served Past Opponent!",
    bgColor: "#072413",
    accentColor: "#4ade80",
  },
  dinosaurs: {
    id: "dinosaurs",
    name: "🦕 Dinosaur Fossil Dig",
    playerLabel: "Archaeology Brush",
    successLabel: "✦ Sand Brushed Away! Fossil Revealed!",
    bgColor: "#1c140a",
    accentColor: "#f59e0b",
  },
  art: {
    id: "art",
    name: "🎨 Starry Night Studio",
    playerLabel: "Artist Paintbrush",
    successLabel: "✦ Starry Night Stroke Painted!",
    bgColor: "#090d16",
    accentColor: "#facc15",
  },
  nebula: {
    id: "nebula",
    name: "🚀 Asteroid Blaster",
    playerLabel: "Starship Blaster",
    successLabel: "✦ Asteroid Blasted!",
    bgColor: "#070b14",
    accentColor: "#38bdf8",
  },
  horses: {
    id: "horses",
    name: "🐴 Equestrian Meadow",
    playerLabel: "Horseshoe Rider",
    successLabel: "✦ Meadow Gate Cleared!",
    bgColor: "#0b170e",
    accentColor: "#84cc16",
  },
  trains: {
    id: "trains",
    name: "🚂 Steam Locomotive",
    playerLabel: "Steam Engine",
    successLabel: "✦ Depot Reached!",
    bgColor: "#09121d",
    accentColor: "#38bdf8",
  },
};

export function getThemeForInterests(interests: string[] = []): GameTheme {
  const combined = interests.join(" ").toLowerCase();
  if (combined.includes("spaghetti") || combined.includes("pasta") || combined.includes("cook") || combined.includes("food") || combined.includes("baking") || combined.includes("pizza")) {
    return THEMES.cooking;
  }
  if (combined.includes("tennis")) {
    return THEMES.tennis;
  }
  if (combined.includes("dinosaur") || combined.includes("fossil") || combined.includes("paleontol") || combined.includes("excavat") || combined.includes("dig")) {
    return THEMES.dinosaurs;
  }
  if (combined.includes("draw") || combined.includes("art") || combined.includes("paint") || combined.includes("starry") || combined.includes("sketch") || combined.includes("astronomy")) {
    return THEMES.art;
  }
  if (combined.includes("horse") || combined.includes("equestrian") || combined.includes("riding")) {
    return THEMES.horses;
  }
  if (combined.includes("train") || combined.includes("railway") || combined.includes("locomotive")) {
    return THEMES.trains;
  }
  return THEMES.nebula;
}

export interface GameCallbacks {
  onQuestionLoaded?: (q: Question) => void;
  onAttemptResult?: (result: AttemptResult) => void;
  onScoreUpdate?: (score: number, answered: number) => void;
  onLevelComplete?: () => void;
  onError?: (err: string) => void;
}

export class OpenGameArena {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private animFrameId: number | null = null;
  private lastTime: number = 0;

  public profileId: string;
  public skillId: string;
  public sessionLength: number = 10;
  // The build of the game this session is running, stamped onto every attempt so
  // a release can be measured afterwards rather than argued about.
  public gameId: string | null = null;
  public gameVersion: number | null = null;
  public theme: GameTheme = THEMES.nebula;
  public soundEnabled: boolean = true;

  public state: "TITLE" | "PLAYING" | "SUBMITTING" | "VICTORY" = "TITLE";
  public currentQuestion: Question | null = null;
  public score: number = 0;
  public answeredCount: number = 0;
  public feedbackMessage: string = "";
  public feedbackIsGentle: boolean = false;
  private shownAt: number = 0;

  private particles: ParticleSystem;
  private steamVapors: Array<{ x: number; y: number; vx: number; vy: number; alpha: number; size: number }> = [];

  private player = {
    x: 400,
    y: 390,
    vx: 0,
    vy: 0,
    angle: -Math.PI / 2,
    targetAngle: -Math.PI / 2,
    speed: 6.5,
    size: 26,
    idlePhase: 0,
    twirlAngle: 0,
    swingPhase: 0,
    brushSweep: 0,
  };

  private asteroid = {
    x: 400,
    y: 175,
    radius: 46,
    angle: 0,
    rotSpeed: 0.008,
    scale: 1.0,
    craters: [
      { x: -16, y: -14, r: 9 },
      { x: 18, y: -8, r: 12 },
      { x: -8, y: 16, r: 11 },
      { x: 16, y: 15, r: 7 },
      { x: 0, y: -2, r: 6 },
    ],
  };
  private lasers: Array<{ x: number; y: number; vx: number; vy: number; active: boolean; color: string; deflected?: boolean }> = [];

  private opponent = {
    x: 400,
    y: 115,
    vx: 1.8,
    targetX: 400,
    diveOffset: 0,
    swinging: false,
  };

  private tennisBall = {
    x: 400,
    y: 380,
    vx: 0,
    vy: 0,
    altitude: 0,
    active: false,
    trail: [] as Array<{ x: number; y: number; alpha: number }>,
  };

  private droppedSpaghetti = {
    x: 400,
    y: 220,
    vy: 0,
    alpha: 0,
    active: false,
  };

  private sandParticles: Array<{ x: number; y: number; vx: number; vy: number; size: number; alpha: number }> = [];
  private sandPuff = { active: false, x: 400, y: 180, alpha: 0 };

  private paintDrips: Array<{ x: number; y: number; length: number; color: string; alpha: number }> = [];
  private starGlowPhase: number = 0;

  private startCursorPos: { x: number; y: number } | null = null;
  private lastCursorPos: { x: number; y: number } | null = null;
  private lastCursorMoveTime: number = 0;
  private totalCursorDistancePx: number = 0;
  private peakCursorVelocityPxS: number = 0;
  private idleDurationMs: number = 0;
  private firstInteractionTime: number = 0;
  private distractionEvents: number = 0;

  private targetX: number | null = null;
  private targetY: number | null = null;
  private callbacks: GameCallbacks;

  constructor(
    canvas: HTMLCanvasElement,
    profileId: string,
    skillId: string,
    callbacks: GameCallbacks = {},
    themeKey: string = "nebula"
  ) {
    this.canvas = canvas;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("Could not get 2D context");
    this.ctx = ctx;
    this.profileId = profileId;
    this.skillId = skillId;
    this.callbacks = callbacks;
    this.theme = THEMES[themeKey] || THEMES.nebula;
    this.particles = new ParticleSystem();

    this.initSteam();
    this.bindEvents();
    this.resizeCanvas();
  }

  public setTheme(themeKey: string): void {
    this.theme = THEMES[themeKey] || THEMES.nebula;
    this.initSteam();
  }

  public setAudio(enabled: boolean): void {
    this.soundEnabled = enabled;
    soundFx.enabled = enabled;
  }

  private initSteam(): void {
    this.steamVapors = [];
    for (let i = 0; i < 20; i++) {
      this.steamVapors.push({
        x: 400 + (Math.random() - 0.5) * 60,
        y: 180 + (Math.random() - 0.5) * 40,
        vx: (Math.random() - 0.5) * 0.3,
        vy: -Math.random() * 0.7 - 0.3,
        alpha: Math.random() * 0.5 + 0.2,
        size: Math.random() * 7 + 4,
      });
    }
  }

  public startLoop(): void {
    this.lastTime = performance.now();
    this.state = "PLAYING";
    this.loadNextQuestion();

    const loop = (currentTime: number) => {
      const deltaMs = Math.min(currentTime - this.lastTime, 50);
      this.lastTime = currentTime;

      this.update(deltaMs);
      this.render();

      this.animFrameId = requestAnimationFrame(loop);
    };
    this.animFrameId = requestAnimationFrame(loop);
  }

  public stopLoop(): void {
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
  }

  public destroy(): void {
    this.stopLoop();
  }

  private bindEvents(): void {
    const getPos = (e: MouseEvent | TouchEvent) => {
      const rect = this.canvas.getBoundingClientRect();
      const scaleX = this.canvas.width / rect.width;
      const scaleY = this.canvas.height / rect.height;
      if ("touches" in e) {
        if (!e.touches.length) return null;
        return {
          x: (e.touches[0].clientX - rect.left) * scaleX,
          y: (e.touches[0].clientY - rect.top) * scaleY,
        };
      }
      return {
        x: (e.clientX - rect.left) * scaleX,
        y: (e.clientY - rect.top) * scaleY,
      };
    };

    const onPointerMove = (e: MouseEvent | TouchEvent) => {
      const pos = getPos(e);
      if (!pos) return;

      const now = performance.now();
      if (!this.startCursorPos) {
        this.startCursorPos = { ...pos };
        this.firstInteractionTime = now;
      }

      if (this.lastCursorPos && this.lastCursorMoveTime > 0) {
        const dt = Math.max(1, now - this.lastCursorMoveTime) / 1000;
        const dx = pos.x - this.lastCursorPos.x;
        const dy = pos.y - this.lastCursorPos.y;
        const dist = Math.hypot(dx, dy);

        this.totalCursorDistancePx += dist;
        const instVelocity = dist / dt;
        if (instVelocity > this.peakCursorVelocityPxS) {
          this.peakCursorVelocityPxS = instVelocity;
        }

        if (dt > 1.2) {
          this.idleDurationMs += dt * 1000;
        }
      }

      this.lastCursorPos = { ...pos };
      this.lastCursorMoveTime = now;

      this.targetX = pos.x;
      this.targetY = pos.y;
    };

    const onVisibilityChange = () => {
      if (document.hidden) {
        this.distractionEvents += 1;
      }
    };

    const onBlur = () => {
      this.distractionEvents += 1;
    };

    window.addEventListener("blur", onBlur);
    document.addEventListener("visibilitychange", onVisibilityChange);

    this.canvas.addEventListener("mousemove", onPointerMove);
    this.canvas.addEventListener("touchmove", onPointerMove, { passive: true });
    this.canvas.addEventListener("touchstart", onPointerMove, { passive: true });
  }

  private resizeCanvas(): void {
    const parent = this.canvas.parentElement;
    if (parent) {
      this.canvas.width = 800;
      this.canvas.height = 480;
    }
  }

  public async loadNextQuestion(): Promise<void> {
    try {
      const q = await api.get<Question>(
        `/profiles/${this.profileId}/skills/${this.skillId}/next-question`
      );
      this.currentQuestion = q;
      this.state = "PLAYING";
      this.shownAt = performance.now();
      this.feedbackMessage = "";

      this.startCursorPos = null;
      this.lastCursorPos = null;
      this.lastCursorMoveTime = performance.now();
      this.totalCursorDistancePx = 0;
      this.peakCursorVelocityPxS = 0;
      this.idleDurationMs = 0;
      this.firstInteractionTime = 0;
      this.distractionEvents = 0;

      this.asteroid.scale = 1.0;
      this.lasers = [];

      capture("problem_shown", {
        game_id: `orbit-${this.theme.id}`,
        profile_id: this.profileId,
        skill_id: this.skillId,
        operands: q.operands,
        operator: q.operator,
      });

      this.callbacks.onQuestionLoaded?.(q);
    } catch (err) {
      this.callbacks.onError?.((err as Error).message);
    }
  }

  public async submitAnswer(answerVal: number): Promise<void> {
    if (this.state === "SUBMITTING" || !this.currentQuestion) return;

    this.state = "SUBMITTING";
    const latency = Math.max(100, Math.round(performance.now() - this.shownAt));
    const hesitation = this.firstInteractionTime > 0 ? Math.round(this.firstInteractionTime - this.shownAt) : latency;
    const dtSec = Math.max(0.1, latency / 1000);
    const avgVelocity = Math.round((this.totalCursorDistancePx / dtSec) * 100) / 100;
    const peakVelocity = Math.round(this.peakCursorVelocityPxS * 100) / 100;
    const directDist = (this.startCursorPos && this.lastCursorPos)
      ? Math.hypot(this.lastCursorPos.x - this.startCursorPos.x, this.lastCursorPos.y - this.startCursorPos.y)
      : 25;
    const jitterRatio = Math.round((this.totalCursorDistancePx / Math.max(15, directDist)) * 100) / 100;
    // Idle only counts while this question was on screen: the timer keeps running
    // between questions and over the teacher panel, and unclamped it reports more
    // idle time than the question lasted.
    const idleMs = Math.round(Math.min(this.idleDurationMs, latency));
    const rawFocus = 100 - (idleMs / latency) * 45 - this.distractionEvents * 25 - (jitterRatio > 2.8 ? 15 : 0);
    const focusScore = Math.round(Math.max(0, Math.min(100, rawFocus)) * 100) / 100;

    if (this.theme.id === "tennis") {
      this.player.swingPhase = 1.0;
      this.tennisBall.active = true;
      this.tennisBall.x = this.player.x + 10;
      this.tennisBall.y = this.player.y - 15;
      const targetX = this.opponent.x > 400 ? 260 : 540;
      this.tennisBall.vx = (targetX - this.tennisBall.x) / 22;
      this.tennisBall.vy = (110 - this.tennisBall.y) / 22;
      this.tennisBall.altitude = 20;
    } else if (this.theme.id === "nebula") {
      this.lasers.push(
        { x: this.player.x - 14, y: this.player.y - 18, vx: (400 - (this.player.x - 14)) / 14, vy: (175 - this.player.y) / 14, active: true, color: "#38bdf8" },
        { x: this.player.x + 14, y: this.player.y - 18, vx: (400 - (this.player.x + 14)) / 14, vy: (175 - this.player.y) / 14, active: true, color: "#ef4444" }
      );
    } else if (this.theme.id === "dinosaurs") {
      this.player.brushSweep = 1.0;
      for (let i = 0; i < 18; i++) {
        this.sandParticles.push({
          x: 400 + (Math.random() - 0.5) * 80,
          y: 180 + (Math.random() - 0.5) * 40,
          vx: (Math.random() - 0.5) * 4.5,
          vy: -Math.random() * 3.5 - 1.0,
          size: Math.random() * 4 + 2,
          alpha: 1.0,
        });
      }
    }

    if (this.soundEnabled) soundFx.laser();

    try {
      const result = await api.post<AttemptResult>("/attempts", {
        profile_id: this.profileId,
        skill_id: this.skillId,
        operands: this.currentQuestion.operands,
        operator: this.currentQuestion.operator,
        answer_given: answerVal,
        latency_to_submit_ms: latency,
        cursor_velocity_px_s: avgVelocity,
        cursor_peak_velocity_px_s: peakVelocity,
        jitter_ratio: jitterRatio,
        idle_time_ms: idleMs,
        hesitation_ms: hesitation,
        distraction_events: this.distractionEvents,
        focus_score: focusScore,
        game_id: this.gameId,
        game_version: this.gameVersion,
      });

      // Augment result with local biometric nuance for real-time dashboard
      result.focus_score = focusScore;
      result.jitter_ratio = jitterRatio;
      result.idle_time_ms = idleMs;
      result.cursor_velocity_px_s = avgVelocity;
      result.hesitation_ms = hesitation;
      result.distraction_events = this.distractionEvents;

      capture("answer_submitted", {
        game_id: `orbit-${this.theme.id}`,
        profile_id: this.profileId,
        skill_id: this.skillId,
        attempt_id: result.attempt_id,
        correct: result.is_correct,
        time_to_solve_ms: latency,
        error_class: result.error_class || "unknown",
        cursor_velocity_px_s: avgVelocity,
        jitter_ratio: jitterRatio,
        focus_score: focusScore,
        idle_time_ms: idleMs,
        distraction_events: this.distractionEvents,
      });

      this.callbacks.onAttemptResult?.(result);

      if (result.is_correct) {
        this.answeredCount += 1;
        this.score += 100;
        this.callbacks.onScoreUpdate?.(this.score, this.answeredCount);

        if (this.soundEnabled) soundFx.dockSuccess();

        if (this.theme.id === "cooking") {
          this.particles.emitExplosion(400, 180, "#ef4444", 26);
          this.particles.emitExplosion(400, 180, "#fde047", 18);
          this.particles.addFloatingText(400, 140, "+1 DELICIOUS BITE!", "#ef4444");
        } else if (this.theme.id === "tennis") {
          this.opponent.diveOffset = this.tennisBall.vx > 0 ? -40 : 40;
          this.particles.emitExplosion(this.tennisBall.x, 110, "#ffffff", 24);
          this.particles.addFloatingText(this.opponent.x, 75, "🎾 ACE! PAST OPPONENT!", "#4ade80");
        } else if (this.theme.id === "dinosaurs") {
          this.particles.emitExplosion(400, 180, "#f59e0b", 28);
          this.particles.emitExplosion(400, 180, "#fef08a", 20);
          this.particles.addFloatingText(400, 140, "🦕 FOSSIL BRUSHED CLEAN!", "#f59e0b");
        } else if (this.theme.id === "art") {
          this.particles.emitExplosion(400, 175, "#facc15", 30);
          this.particles.emitExplosion(400, 175, "#38bdf8", 22);
          this.particles.addFloatingText(400, 130, "🎨 STARRY NIGHT LAYER PAINTED!", "#facc15");
        } else {
          this.asteroid.scale = 0;
          this.particles.emitExplosion(400, 175, "#94a3b8", 32);
          this.particles.emitExplosion(400, 175, "#f97316", 24);
          this.particles.emitExplosion(400, 175, "#38bdf8", 18);
          this.particles.addFloatingText(400, 130, "💥 ASTEROID BLASTED! +100", "#38bdf8");
        }

        this.particles.shake(220, 3.5);
        this.feedbackMessage = this.theme.successLabel;
        this.feedbackIsGentle = false;

        if (this.answeredCount >= this.sessionLength) {
          setTimeout(() => {
            this.state = "VICTORY";
            this.callbacks.onLevelComplete?.();
          }, 1100);
        } else {
          setTimeout(() => this.loadNextQuestion(), 950);
        }
      } else {
        if (this.soundEnabled) soundFx.gentleRetry();

        if (this.theme.id === "cooking") {
          this.droppedSpaghetti = { x: 400, y: 220, vy: 3.5, alpha: 1.0, active: true };
          this.particles.emitExplosion(400, 240, "#facc15", 14);
          this.particles.emitExplosion(400, 310, "#ef4444", 10);
          this.particles.addFloatingText(400, 260, "🍝 Slipped off the fork!", "#f59e0b");
        } else if (this.theme.id === "tennis") {
          this.opponent.x = Math.max(120, Math.min(680, this.tennisBall.x));
          this.opponent.diveOffset = 0;
          this.tennisBall.vy = 9.5;
          this.tennisBall.vx = (Math.random() - 0.5) * 5;
          this.particles.emitExplosion(this.opponent.x, 115, "#ffffff", 16);
          this.particles.addFloatingText(this.opponent.x, 80, "🎾 Opponent Returned Ball!", "#38bdf8");
        } else if (this.theme.id === "dinosaurs") {
          this.sandPuff = { active: true, x: 400, y: 180, alpha: 1.0 };
          this.particles.emitExplosion(400, 185, "#d97706", 18);
          this.particles.addFloatingText(400, 140, "💨 Sand blew over the dig!", "#f59e0b");
        } else if (this.theme.id === "art") {
          this.paintDrips.push({ x: 400 + (Math.random() - 0.5) * 60, y: 130, length: 0, color: "#38bdf8", alpha: 1.0 });
          this.particles.emitExplosion(400, 175, "#60a5fa", 16);
          this.particles.addFloatingText(400, 130, "🎨 Paint smudge on canvas!", "#60a5fa");
        } else {
          for (const l of this.lasers) {
            l.deflected = true;
            l.vx = (Math.random() - 0.5) * 16;
            l.vy = Math.random() * 8 + 4;
          }
          this.particles.emitExplosion(400, 175, "#38bdf8", 16);
          this.particles.addFloatingText(400, 130, "🛡️ Asteroid Deflected Laser!", "#fbbf24");
        }

        this.feedbackMessage = `Almost — it was ${this.currentQuestion.correct_answer}. Next one incoming!`;
        this.feedbackIsGentle = true;

        setTimeout(() => this.loadNextQuestion(), 1400);
      }
    } catch (err) {
      this.callbacks.onError?.((err as Error).message);
      this.state = "PLAYING";
    }
  }

  private update(deltaMs: number): void {
    for (const v of this.steamVapors) {
      v.x += v.vx;
      v.y += v.vy;
      v.alpha -= 0.007;
      if (v.alpha <= 0 || v.y < 110) {
        v.x = 400 + (Math.random() - 0.5) * 60;
        v.y = 180 + (Math.random() - 0.5) * 40;
        v.alpha = Math.random() * 0.5 + 0.2;
      }
    }

    this.asteroid.angle += this.asteroid.rotSpeed;
    for (const l of this.lasers) {
      if (l.active) {
        l.x += l.vx;
        l.y += l.vy;
        if (l.y < 50 || l.y > 480 || l.x < 0 || l.x > 800) l.active = false;
      }
    }

    for (let i = this.sandParticles.length - 1; i >= 0; i--) {
      const sp = this.sandParticles[i];
      sp.x += sp.vx;
      sp.y += sp.vy;
      sp.vy += 0.15;
      sp.alpha -= 0.02;
      if (sp.alpha <= 0) this.sandParticles.splice(i, 1);
    }
    if (this.sandPuff.active) {
      this.sandPuff.alpha -= 0.02;
      if (this.sandPuff.alpha <= 0) this.sandPuff.active = false;
    }

    this.starGlowPhase += 0.05;
    for (const pd of this.paintDrips) {
      if (pd.length < 35) pd.length += 1.2;
      pd.alpha -= 0.01;
    }

    if (this.droppedSpaghetti.active) {
      this.droppedSpaghetti.y += this.droppedSpaghetti.vy;
      this.droppedSpaghetti.vy += 0.25;
      if (this.droppedSpaghetti.y > 330) {
        this.droppedSpaghetti.active = false;
      }
    }

    if (this.tennisBall.active) {
      this.tennisBall.x += this.tennisBall.vx;
      this.tennisBall.y += this.tennisBall.vy;
      this.tennisBall.altitude = Math.max(0, this.tennisBall.altitude - 0.8);
      this.tennisBall.trail.push({ x: this.tennisBall.x, y: this.tennisBall.y, alpha: 0.9 });
      if (this.tennisBall.trail.length > 12) this.tennisBall.trail.shift();
    }

    if (this.theme.id === "tennis") {
      this.opponent.x += this.opponent.vx;
      if (this.opponent.x > 520 || this.opponent.x < 280) {
        this.opponent.vx = -this.opponent.vx;
      }
    }

    this.player.idlePhase += 0.04;
    if (this.state === "SUBMITTING") {
      this.player.twirlAngle += 0.22;
      if (this.player.brushSweep > 0) this.player.brushSweep = Math.sin(this.player.twirlAngle * 2) * 18;
    } else {
      this.player.twirlAngle = 0;
      this.player.brushSweep = 0;
    }

    if (this.targetX !== null && this.targetY !== null) {
      const dx = this.targetX - this.player.x;
      const dy = this.targetY - this.player.y;
      const dist = Math.hypot(dx, dy);

      if (dist > 3) {
        this.player.vx += (dx / dist) * 0.55;
        this.player.vy += (dy / dist) * 0.55;
        this.player.targetAngle = Math.atan2(dy, dx);
      } else {
        this.targetX = null;
        this.targetY = null;
      }
    }

    this.player.vx *= 0.91;
    this.player.vy *= 0.91;
    this.player.x += this.player.vx * this.player.speed;
    this.player.y += this.player.vy * this.player.speed;

    const pad = 40;
    this.player.x = Math.max(pad, Math.min(this.canvas.width - pad, this.player.x));
    this.player.y = Math.max(this.canvas.height / 2 + 20, Math.min(this.canvas.height - pad, this.player.y));

    this.particles.update(deltaMs);
  }

  private render(): void {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;

    ctx.save();
    if (this.particles.shakeDuration > 0) {
      const intensity = this.particles.shakeIntensity;
      ctx.translate((Math.random() - 0.5) * intensity * 2, (Math.random() - 0.5) * intensity * 2);
    }

    this.renderEnvironment(ctx, w, h);

    if (this.theme.id === "cooking") {
      this.renderSpaghettiPlate(ctx, 400, 185);
    } else if (this.theme.id === "tennis") {
      this.renderTennisMatch(ctx, w, h);
    } else if (this.theme.id === "dinosaurs") {
      this.renderDinosaurDigSite(ctx, 400, 185);
    } else if (this.theme.id === "art") {
      this.renderStarryNightStudio(ctx, 400, 180);
    } else {
      this.renderAsteroidField(ctx, 400, 175);
    }

    this.renderPlayerActor(ctx);
    this.renderHUD();
    this.particles.render(ctx);

    ctx.restore();
  }

  private renderEnvironment(ctx: CanvasRenderingContext2D, w: number, h: number): void {
    ctx.fillStyle = this.theme.bgColor;
    ctx.fillRect(0, 0, w, h);

    if (this.theme.id === "cooking") {
      const cellSize = 36;
      for (let x = 0; x < w; x += cellSize) {
        for (let y = 0; y < h; y += cellSize) {
          if ((Math.floor(x / cellSize) + Math.floor(y / cellSize)) % 2 === 0) {
            ctx.fillStyle = "rgba(239, 68, 68, 0.05)";
            ctx.fillRect(x, y, cellSize, cellSize);
          }
        }
      }
      ctx.strokeStyle = "rgba(245, 158, 11, 0.15)";
      ctx.lineWidth = 2;
      ctx.strokeRect(16, 16, w - 32, h - 32);
    } else if (this.theme.id === "tennis") {
      ctx.fillStyle = "#0c3b1e";
      ctx.fillRect(40, 20, w - 80, h - 40);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.7)";
      ctx.lineWidth = 2.5;
      ctx.strokeRect(60, 40, w - 120, h - 80);
      ctx.strokeRect(120, 90, w - 240, 90);
      ctx.strokeRect(120, h / 2 + 10, w - 240, 90);
      ctx.beginPath();
      ctx.moveTo(w / 2, 90);
      ctx.lineTo(w / 2, h - 130);
      ctx.stroke();
    } else if (this.theme.id === "dinosaurs") {
      ctx.fillStyle = "#1e1307";
      ctx.fillRect(30, 20, w - 60, h - 40);
      ctx.strokeStyle = "rgba(245, 158, 11, 0.15)";
      ctx.lineWidth = 1.5;
      for (let x = 60; x < w - 60; x += 70) {
        ctx.beginPath();
        ctx.moveTo(x, 30);
        ctx.lineTo(x, h - 30);
        ctx.stroke();
      }
      for (let y = 40; y < h - 30; y += 60) {
        ctx.beginPath();
        ctx.moveTo(40, y);
        ctx.lineTo(w - 40, y);
        ctx.stroke();
      }
    } else if (this.theme.id === "art") {
      ctx.fillStyle = "#0c1322";
      ctx.fillRect(0, 0, w, h);
      ctx.strokeStyle = "rgba(56, 189, 248, 0.06)";
      ctx.lineWidth = 2;
      for (let y = 0; y < h; y += 32) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }
    } else {
      ctx.strokeStyle = "rgba(56, 189, 248, 0.08)";
      ctx.lineWidth = 1;
      for (let x = 0; x < w; x += 60) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      ctx.fillStyle = "rgba(255, 255, 255, 0.6)";
      for (let i = 0; i < 30; i++) {
        const sx = (i * 137.5) % w;
        const sy = (i * 93.7) % (h / 2);
        ctx.fillRect(sx, sy, 2, 2);
      }
    }
  }

  private renderSpaghettiPlate(ctx: CanvasRenderingContext2D, cx: number, cy: number): void {
    const remainingPct = Math.max(0, 1 - this.answeredCount / this.sessionLength);
    ctx.save();
    ctx.fillStyle = "rgba(0, 0, 0, 0.45)";
    ctx.beginPath();
    ctx.arc(cx, cy + 8, 92, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#f8fafc";
    ctx.strokeStyle = "#dc2626";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(cx, cy, 90, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#f1f5f9";
    ctx.beginPath();
    ctx.arc(cx, cy, 70, 0, Math.PI * 2);
    ctx.fill();
    if (remainingPct > 0) {
      for (const v of this.steamVapors) {
        ctx.fillStyle = "rgba(255, 255, 255, " + v.alpha + ")";
        ctx.beginPath();
        ctx.arc(v.x, v.y, v.size, 0, Math.PI * 2);
        ctx.fill();
      }
      const pastaRadius = 56 * Math.sqrt(remainingPct);
      ctx.fillStyle = "#facc15";
      ctx.strokeStyle = "#ca8a04";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(cx, cy, pastaRadius, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.strokeStyle = "#eab308";
      ctx.lineWidth = 2;
      for (let i = 0; i < Math.ceil(8 * remainingPct); i++) {
        const ang = (i * Math.PI) / 4;
        ctx.beginPath();
        ctx.ellipse(cx + Math.cos(ang) * 12, cy + Math.sin(ang) * 10, pastaRadius * 0.6, pastaRadius * 0.35, ang, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.fillStyle = "rgba(220, 38, 38, 0.92)";
      ctx.beginPath();
      ctx.arc(cx, cy - 4, pastaRadius * 0.65, 0, Math.PI * 2);
      ctx.fill();
      const meatballCount = Math.ceil(3 * remainingPct);
      const mbOffsets = [{ x: -15, y: -10 }, { x: 16, y: -8 }, { x: 0, y: 14 }];
      ctx.fillStyle = "#78350f";
      ctx.strokeStyle = "#451a03";
      ctx.lineWidth = 1.5;
      for (let i = 0; i < meatballCount; i++) {
        ctx.beginPath();
        ctx.arc(cx + mbOffsets[i].x, cy + mbOffsets[i].y, 11, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      }
      if (remainingPct > 0.25) {
        ctx.fillStyle = "#16a34a";
        ctx.beginPath();
        ctx.ellipse(cx + 2, cy - 14, 8, 4, Math.PI / 4, 0, Math.PI * 2);
        ctx.fill();
      }
    } else {
      ctx.strokeStyle = "rgba(220, 38, 38, 0.4)";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(cx - 25, cy - 10);
      ctx.bezierCurveTo(cx - 5, cy + 18, cx + 15, cy - 8, cx + 28, cy + 12);
      ctx.stroke();
      ctx.fillStyle = "#16a34a";
      ctx.font = "bold 16px system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("⭐ Clean Plate! Molto Bene! ⭐", cx, cy);
    }
    if (this.droppedSpaghetti.active) {
      ctx.save();
      ctx.fillStyle = "#facc15";
      ctx.strokeStyle = "#ca8a04";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(this.droppedSpaghetti.x, this.droppedSpaghetti.y, 11, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = "rgba(220, 38, 38, 0.85)";
      ctx.beginPath();
      ctx.arc(this.droppedSpaghetti.x + 3, this.droppedSpaghetti.y - 2, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
    ctx.restore();
  }

  private renderTennisMatch(ctx: CanvasRenderingContext2D, w: number, h: number): void {
    const netY = h / 2 - 5;
    ctx.save();
    ctx.fillStyle = "rgba(255, 255, 255, 0.4)";
    ctx.fillRect(40, netY, w - 80, 14);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(40, netY, w - 80, 3);
    ctx.fillStyle = "#334155";
    ctx.fillRect(36, netY - 8, 6, 26);
    ctx.fillRect(w - 42, netY - 8, 6, 26);
    ctx.restore();
    ctx.save();
    const opX = this.opponent.x + this.opponent.diveOffset;
    const opY = this.opponent.y;
    ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
    ctx.beginPath();
    ctx.ellipse(opX, opY + 22, 14, 6, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#38bdf8";
    ctx.beginPath();
    ctx.arc(opX, opY, 10, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(opX - 7, opY + 8, 14, 16);
    ctx.strokeStyle = "#f87171";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(opX + 16, opY + 8, 9, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
    if (this.tennisBall.active) {
      ctx.save();
      for (const t of this.tennisBall.trail) {
        ctx.fillStyle = `rgba(204, 255, 0, ${t.alpha * 0.5})`;
        ctx.beginPath();
        ctx.arc(t.x, t.y, 4, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.fillStyle = "#ccff00";
      ctx.shadowColor = "#ccff00";
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(this.tennisBall.x, this.tennisBall.y, 6.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.2;
      ctx.shadowBlur = 0;
      ctx.beginPath();
      ctx.arc(this.tennisBall.x, this.tennisBall.y, 4, 0, Math.PI);
      ctx.stroke();
      ctx.restore();
    }
  }

  private renderDinosaurDigSite(ctx: CanvasRenderingContext2D, cx: number, cy: number): void {
    const progress = Math.min(1.0, this.answeredCount / this.sessionLength);
    const dirtRemaining = Math.max(0, 1.0 - progress);
    ctx.save();
    ctx.fillStyle = "#291807";
    ctx.strokeStyle = "#f59e0b";
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.roundRect(cx - 145, cy - 95, 290, 190, 16);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
    ctx.fillRect(cx - 140, cy - 90, 280, 20);
    ctx.fillStyle = "#fef08a";
    ctx.strokeStyle = "#fef08a";
    ctx.lineWidth = 3;
    ctx.shadowColor = "#f59e0b";
    ctx.shadowBlur = 8;
    if (progress >= 0.1) {
      ctx.beginPath();
      ctx.ellipse(cx - 65, cy - 35, 26, 18, -0.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#1e1408";
      ctx.beginPath();
      ctx.arc(cx - 56, cy - 37, 5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillRect(cx - 86, cy - 36, 3, 3);
      ctx.fillStyle = "#ffffff";
      for (let t = 0; t < 5; t++) {
        ctx.fillRect(cx - 84 + t * 6, cy - 20, 2.5, 5);
      }
      ctx.fillStyle = "#fef08a";
      ctx.fillRect(cx - 86, cy - 18, 30, 6);
    }
    if (progress >= 0.25) {
      ctx.fillStyle = "#fef08a";
      for (let i = 0; i < 3; i++) {
        ctx.fillRect(cx - 40 + i * 10, cy - 28 + i * 4, 7, 10);
      }
      ctx.fillRect(cx - 15, cy - 18, 65, 8);
    }
    if (progress >= 0.4) {
      ctx.strokeStyle = "#fef08a";
      ctx.lineWidth = 3.5;
      for (let r = 0; r < 4; r++) {
        ctx.beginPath();
        ctx.moveTo(cx - 10 + r * 14, cy - 14);
        ctx.bezierCurveTo(cx - 16 + r * 14, cy + 12, cx + r * 14, cy + 14, cx + 6 + r * 14, cy + 8);
        ctx.stroke();
      }
    }
    if (progress >= 0.55) {
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(cx - 12, cy - 4);
      ctx.lineTo(cx - 24, cy + 4);
      ctx.lineTo(cx - 28, cy - 2);
      ctx.stroke();
    }
    if (progress >= 0.7) {
      ctx.fillRect(cx + 42, cy - 22, 18, 14);
      ctx.lineWidth = 4.5;
      ctx.beginPath();
      ctx.moveTo(cx + 48, cy - 12);
      ctx.lineTo(cx + 62, cy + 18);
      ctx.lineTo(cx + 52, cy + 48);
      ctx.lineTo(cx + 38, cy + 50);
      ctx.stroke();
    }
    if (progress >= 0.85) {
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.moveTo(cx + 56, cy - 18);
      ctx.quadraticCurveTo(cx + 95, cy - 12, cx + 115, cy + 22);
      ctx.quadraticCurveTo(cx + 125, cy + 42, cx + 130, cy + 48);
      ctx.stroke();
    }
    ctx.shadowBlur = 0;
    if (dirtRemaining > 0.05) {
      const moundW = 135 * Math.sqrt(dirtRemaining);
      const moundH = 85 * Math.sqrt(dirtRemaining);
      const grad = ctx.createRadialGradient(cx, cy, 10, cx, cy, moundW);
      grad.addColorStop(0, "#d97706");
      grad.addColorStop(0.7, "#b45309");
      grad.addColorStop(1, "rgba(180, 83, 9, 0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.ellipse(cx, cy, moundW, moundH, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#78350f";
      for (let i = 0; i < Math.ceil(18 * dirtRemaining); i++) {
        const ang = (i * 137.5 * Math.PI) / 180;
        const dist = (i * 4) % moundW;
        ctx.fillRect(cx + Math.cos(ang) * dist, cy + Math.sin(ang) * (dist * 0.6), 3, 3);
      }
    }
    for (const sp of this.sandParticles) {
      ctx.fillStyle = `rgba(245, 158, 11, ${sp.alpha})`;
      ctx.beginPath();
      ctx.arc(sp.x, sp.y, sp.size, 0, Math.PI * 2);
      ctx.fill();
    }
    if (this.sandPuff.active) {
      ctx.fillStyle = `rgba(217, 119, 6, ${this.sandPuff.alpha * 0.65})`;
      ctx.beginPath();
      ctx.arc(this.sandPuff.x, this.sandPuff.y, 65, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = "#fef3c7";
    ctx.textAlign = "center";
    ctx.font = "bold 13px system-ui, sans-serif";
    if (progress >= 1.0) {
      ctx.fillStyle = "#4ade80";
      ctx.fillText("🏆 TYRANNOSAURUS REX FULLY UNEARTHED! 🦖", cx, cy + 80);
    } else {
      ctx.fillText(`🧹 ${Math.round(progress * 100)}% EXCAVATED (${this.answeredCount}/10 BONES BRUSHED)`, cx, cy + 80);
    }
    ctx.restore();
  }

  private renderStarryNightStudio(ctx: CanvasRenderingContext2D, cx: number, cy: number): void {
    const progress = Math.min(1.0, this.answeredCount / this.sessionLength);
    const canvasW = 280;
    const canvasH = 175;
    const left = cx - canvasW / 2;
    const top = cy - canvasH / 2 - 10;
    ctx.save();
    ctx.fillStyle = "#78350f";
    ctx.strokeStyle = "#451a03";
    ctx.lineWidth = 3;
    ctx.fillRect(cx - 7, top - 32, 14, canvasH + 64);
    ctx.strokeRect(cx - 7, top - 32, 14, canvasH + 64);
    ctx.beginPath();
    ctx.moveTo(cx - 20, top - 25);
    ctx.lineTo(left - 30, top + canvasH + 35);
    ctx.moveTo(cx + 20, top - 25);
    ctx.lineTo(left + canvasW + 30, top + canvasH + 35);
    ctx.stroke();
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(left, top, canvasW, canvasH);
    ctx.strokeStyle = "#ca8a04";
    ctx.lineWidth = 4;
    ctx.strokeRect(left, top, canvasW, canvasH);
    if (progress >= 0.1) {
      const skyGrad = ctx.createLinearGradient(left, top, left, top + canvasH * 0.7);
      skyGrad.addColorStop(0, "#090d16");
      skyGrad.addColorStop(0.5, "#172554");
      skyGrad.addColorStop(1, "#1e3a8a");
      ctx.fillStyle = skyGrad;
      ctx.fillRect(left + 2, top + 2, canvasW - 4, canvasH * 0.7);
      ctx.fillStyle = "#1e1b4b";
      ctx.beginPath();
      ctx.moveTo(left, top + canvasH * 0.68);
      ctx.bezierCurveTo(left + 70, top + canvasH * 0.52, left + 180, top + canvasH * 0.72, left + canvasW, top + canvasH * 0.58);
      ctx.lineTo(left + canvasW, top + canvasH);
      ctx.lineTo(left, top + canvasH);
      ctx.closePath();
      ctx.fill();
    }
    if (progress >= 0.2) {
      ctx.strokeStyle = "rgba(56, 189, 248, 0.45)";
      ctx.lineWidth = 2.5;
      for (let i = 0; i < 6; i++) {
        ctx.beginPath();
        ctx.moveTo(left + 20, top + 30 + i * 16);
        ctx.bezierCurveTo(left + 100, top + 15 + i * 14, left + 180, top + 45 + i * 14, left + canvasW - 20, top + 25 + i * 14);
        ctx.stroke();
      }
    }
    if (progress >= 0.35) {
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 3.5;
      ctx.shadowColor = "#38bdf8";
      ctx.shadowBlur = 10;
      ctx.beginPath();
      ctx.arc(cx + 10, top + 48, 22, 0, Math.PI * 1.5, false);
      ctx.bezierCurveTo(cx - 35, top + 75, cx + 55, top + 75, cx + 75, top + 35);
      ctx.stroke();
      ctx.shadowBlur = 0;
    }
    if (progress >= 0.5) {
      ctx.fillStyle = "#0f172a";
      ctx.fillRect(left + 65, top + canvasH * 0.7, 160, canvasH * 0.3);
      ctx.fillStyle = "#1e293b";
      for (let h = 0; h < 7; h++) {
        const hx = left + 80 + h * 20;
        const hy = top + canvasH * 0.76;
        ctx.beginPath();
        ctx.moveTo(hx, hy);
        ctx.lineTo(hx + 10, hy - 12);
        ctx.lineTo(hx + 20, hy);
        ctx.closePath();
        ctx.fill();
      }
      ctx.fillStyle = "#020617";
      ctx.beginPath();
      ctx.moveTo(cx + 25, top + canvasH * 0.85);
      ctx.lineTo(cx + 31, top + canvasH * 0.48);
      ctx.lineTo(cx + 37, top + canvasH * 0.85);
      ctx.closePath();
      ctx.fill();
    }
    if (progress >= 0.65) {
      ctx.fillStyle = "#facc15";
      ctx.shadowColor = "#facc15";
      ctx.shadowBlur = 6;
      for (let w = 0; w < 8; w++) {
        ctx.fillRect(left + 85 + (w * 18) % 120, top + canvasH * 0.8 + (w % 2) * 8, 4, 5);
      }
      ctx.shadowBlur = 0;
    }
    if (progress >= 0.8) {
      ctx.fillStyle = "#064e3b";
      ctx.strokeStyle = "#022c22";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(left + 35, top + canvasH);
      ctx.quadraticCurveTo(left + 22, top + canvasH * 0.5, left + 45, top + 15);
      ctx.quadraticCurveTo(left + 65, top + canvasH * 0.45, left + 75, top + canvasH);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.strokeStyle = "#047857";
      ctx.lineWidth = 2;
      for (let b = 0; b < 6; b++) {
        ctx.beginPath();
        ctx.moveTo(left + 45, top + 40 + b * 18);
        ctx.quadraticCurveTo(left + 30 + (b % 2) * 30, top + 25 + b * 18, left + 45, top + 10 + b * 18);
        ctx.stroke();
      }
    }
    if (progress >= 0.9) {
      const pulse = Math.sin(this.starGlowPhase) * 2;
      const starCoords = [
        { x: left + 35, y: top + 25 },
        { x: left + 90, y: top + 45 },
        { x: left + 140, y: top + 25 },
        { x: left + 185, y: top + 55 },
        { x: left + 225, y: top + 35 },
      ];
      for (const s of starCoords) {
        ctx.strokeStyle = "rgba(250, 204, 21, 0.45)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(s.x, s.y, 10 + pulse, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = "#fef08a";
        ctx.beginPath();
        ctx.arc(s.x, s.y, 4, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.shadowColor = "#facc15";
      ctx.shadowBlur = 14;
      ctx.fillStyle = "#facc15";
      ctx.beginPath();
      ctx.arc(left + canvasW - 40, top + 35, 18, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#1e3a8a";
      ctx.beginPath();
      ctx.arc(left + canvasW - 46, top + 31, 14, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    }
    if (progress >= 1.0) {
      ctx.fillStyle = "#facc15";
      ctx.font = "italic bold 12px serif";
      ctx.textAlign = "right";
      ctx.fillText("Vincent", left + canvasW - 14, top + canvasH - 8);
    }
    for (const pd of this.paintDrips) {
      ctx.strokeStyle = pd.color;
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(pd.x, pd.y);
      ctx.lineTo(pd.x, pd.y + pd.length);
      ctx.stroke();
    }
    ctx.fillStyle = "#92400e";
    ctx.fillRect(left - 15, top + canvasH, canvasW + 30, 12);
    ctx.fillStyle = "#fef3c7";
    ctx.textAlign = "center";
    ctx.font = "bold 13px system-ui, sans-serif";
    if (progress >= 1.0) {
      ctx.fillStyle = "#4ade80";
      ctx.fillText("✨ STARRY NIGHT MASTERPIECE COMPLETE! 🎨", cx, top + canvasH + 34);
    } else {
      ctx.fillText(`🎨 PAINTING STARRY NIGHT (${this.answeredCount}/10 OIL LAYERS)`, cx, top + canvasH + 34);
    }
    ctx.restore();
  }

  private renderAsteroidField(ctx: CanvasRenderingContext2D, cx: number, cy: number): void {
    ctx.save();
    if (this.asteroid.scale > 0.05) {
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(this.asteroid.angle);
      ctx.scale(this.asteroid.scale, this.asteroid.scale);
      const r = this.asteroid.radius;
      ctx.fillStyle = "#1e293b";
      ctx.beginPath();
      ctx.arc(0, 4, r + 2, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#64748b";
      ctx.strokeStyle = "#94a3b8";
      ctx.lineWidth = 3.5;
      ctx.beginPath();
      for (let i = 0; i < 12; i++) {
        const ang = (i * Math.PI * 2) / 12;
        const rad = r + (i % 2 === 0 ? 4 : -5);
        const px = Math.cos(ang) * rad;
        const py = Math.sin(ang) * rad;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      for (const c of this.asteroid.craters) {
        ctx.fillStyle = "#334155";
        ctx.strokeStyle = "#475569";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(c.x, c.y, c.r, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = "#1e293b";
        ctx.beginPath();
        ctx.arc(c.x - 1, c.y - 1, c.r * 0.55, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.strokeStyle = "rgba(56, 189, 248, 0.4)";
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 6]);
      ctx.beginPath();
      ctx.arc(0, 0, r + 18, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.restore();
    }
    for (const l of this.lasers) {
      if (l.active) {
        ctx.save();
        ctx.fillStyle = l.color;
        ctx.shadowColor = l.color;
        ctx.shadowBlur = 12;
        ctx.beginPath();
        ctx.ellipse(l.x, l.y, 4, 12, Math.atan2(l.vy, l.vx) + Math.PI / 2, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
    }
    ctx.fillStyle = "#38bdf8";
    ctx.textAlign = "center";
    ctx.font = "bold 13px monospace";
    ctx.fillText(`TARGET: ASTEROID SECTOR [${this.answeredCount}/10 CLEARED]`, cx, cy + 78);
    ctx.restore();
  }

  private renderPlayerActor(ctx: CanvasRenderingContext2D): void {
    ctx.save();
    ctx.translate(this.player.x, this.player.y + Math.sin(this.player.idlePhase) * 2);
    ctx.rotate(this.player.angle + Math.PI / 2 + this.player.twirlAngle);

    if (this.theme.id === "cooking") {
      ctx.fillStyle = "#94a3b8";
      ctx.fillRect(-3.5, 10, 7, 36);
      ctx.fillStyle = "#cbd5e1";
      ctx.beginPath();
      ctx.moveTo(-11, 10);
      ctx.lineTo(11, 10);
      ctx.lineTo(7, -8);
      ctx.lineTo(-7, -8);
      ctx.closePath();
      ctx.fill();
      ctx.fillStyle = "#f8fafc";
      for (let i = 0; i < 4; i++) {
        ctx.fillRect(-9 + i * 5.5, -26, 2.5, 20);
      }
      if (this.state === "SUBMITTING") {
        ctx.fillStyle = "#facc15";
        ctx.beginPath();
        ctx.arc(0, -16, 13, 0, Math.PI * 2);
        ctx.fill();
      }
    } else if (this.theme.id === "tennis") {
      ctx.fillStyle = "#1e293b";
      ctx.fillRect(-3, 12, 6, 28);
      ctx.strokeStyle = "#4ade80";
      ctx.lineWidth = 3.5;
      ctx.beginPath();
      ctx.ellipse(0, -12, 16, 22, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.strokeStyle = "rgba(255, 255, 255, 0.4)";
      ctx.lineWidth = 1;
      for (let x = -10; x <= 10; x += 5) {
        ctx.beginPath();
        ctx.moveTo(x, -28);
        ctx.lineTo(x, 4);
        ctx.stroke();
      }
    } else if (this.theme.id === "dinosaurs") {
      ctx.save();
      ctx.rotate((this.player.brushSweep * Math.PI) / 180);
      ctx.fillStyle = "#78350f";
      ctx.strokeStyle = "#451a03";
      ctx.lineWidth = 1.5;
      ctx.fillRect(-4, 0, 8, 36);
      ctx.strokeRect(-4, 0, 8, 36);
      ctx.fillStyle = "#d97706";
      ctx.fillRect(-8, -12, 16, 12);
      ctx.fillStyle = "#fef08a";
      ctx.beginPath();
      ctx.moveTo(-11, -12);
      ctx.lineTo(11, -12);
      ctx.lineTo(14, -28);
      ctx.lineTo(-14, -28);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = "#ca8a04";
      ctx.lineWidth = 1;
      for (let b = -8; b <= 8; b += 4) {
        ctx.beginPath();
        ctx.moveTo(b, -12);
        ctx.lineTo(b * 1.2, -28);
        ctx.stroke();
      }
      ctx.restore();
    } else if (this.theme.id === "art") {
      ctx.fillStyle = "#b45309";
      ctx.strokeStyle = "#78350f";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.ellipse(-14, 12, 16, 22, 0.3, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
      const dabs = ["#facc15", "#38bdf8", "#ef4444", "#16a34a", "#ffffff"];
      for (let p = 0; p < dabs.length; p++) {
        ctx.fillStyle = dabs[p];
        ctx.beginPath();
        ctx.arc(-20 + (p % 2) * 10, 4 + p * 5, 3.5, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.fillStyle = "#1e293b";
      ctx.fillRect(-2, -4, 4, 34);
      ctx.fillStyle = "#94a3b8";
      ctx.fillRect(-3, -12, 6, 8);
      ctx.fillStyle = "#facc15";
      ctx.shadowColor = "#facc15";
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(-3, -12);
      ctx.lineTo(3, -12);
      ctx.lineTo(0, -26);
      ctx.closePath();
      ctx.fill();
      ctx.shadowBlur = 0;
    } else {
      ctx.fillStyle = "#38bdf8";
      ctx.shadowColor = "#38bdf8";
      ctx.shadowBlur = 12;
      ctx.beginPath();
      ctx.moveTo(-8, 18);
      ctx.lineTo(0, 32 + (Math.random() - 0.5) * 6);
      ctx.lineTo(8, 18);
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.fillStyle = "#0f172a";
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(0, -26);
      ctx.lineTo(24, 18);
      ctx.lineTo(10, 12);
      ctx.lineTo(0, 18);
      ctx.lineTo(-10, 12);
      ctx.lineTo(-24, 18);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = "#ef4444";
      ctx.fillRect(-22, 6, 4, 12);
      ctx.fillRect(18, 6, 4, 12);
      ctx.fillStyle = "#38bdf8";
      ctx.beginPath();
      ctx.ellipse(0, -2, 5, 9, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  private renderHUD(): void {
    const ctx = this.ctx;
    const w = this.canvas.width;
    ctx.save();

    // 16-Bit Arcade Question Header Plaque (Top Center)
    const plaqueW = 460;
    const plaqueH = 68;
    const plaqueX = w / 2 - plaqueW / 2;
    const plaqueY = 12;

    // Drop shadow
    ctx.fillStyle = "rgba(0, 0, 0, 0.65)";
    ctx.beginPath();
    ctx.roundRect(plaqueX + 4, plaqueY + 4, plaqueW, plaqueH, 10);
    ctx.fill();

    // Plaque background & gold border
    ctx.fillStyle = "#0f172a";
    ctx.strokeStyle = "#facc15";
    ctx.lineWidth = 3.5;
    ctx.beginPath();
    ctx.roundRect(plaqueX, plaqueY, plaqueW, plaqueH, 10);
    ctx.fill();
    ctx.stroke();

    // Inner highlight border
    ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(plaqueX + 3, plaqueY + 3, plaqueW - 6, plaqueH - 6, 8);
    ctx.stroke();

    // Top row: Theme name & question progress
    ctx.fillStyle = "#38bdf8";
    ctx.font = "bold 11px 'Press Start 2P', monospace, sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(
      `${this.theme.name.toUpperCase()} • Q${Math.min(this.sessionLength, this.answeredCount + 1)}/${this.sessionLength}`,
      w / 2,
      plaqueY + 22
    );

    // Main Math Equation (High Contrast Gold & White)
    if (this.currentQuestion) {
      const a = this.currentQuestion.operands[0];
      const b = this.currentQuestion.operands[1];
      const op = this.currentQuestion.operator;
      ctx.fillStyle = "#facc15";
      ctx.font = "bold 22px 'Press Start 2P', monospace, sans-serif";
      ctx.shadowColor = "rgba(250, 204, 21, 0.75)";
      ctx.shadowBlur = 8;
      ctx.fillText(`${a} ${op} ${b} = ?`, w / 2, plaqueY + 54);
      ctx.shadowBlur = 0;
    } else {
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 13px 'Press Start 2P', monospace, sans-serif";
      ctx.fillText("LOADING QUESTION...", w / 2, plaqueY + 52);
    }

    // Feedback message toast (Rendered directly beneath plaque)
    if (this.feedbackMessage) {
      ctx.font = "bold 13px 'Press Start 2P', monospace, sans-serif";
      const msgW = Math.min(520, ctx.measureText(this.feedbackMessage).width + 48);
      ctx.fillStyle = "rgba(15, 23, 42, 0.95)";
      ctx.strokeStyle = this.feedbackIsGentle ? "#f59e0b" : "#22c55e";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.roundRect(w / 2 - msgW / 2, plaqueY + plaqueH + 8, msgW, 36, 8);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = this.feedbackIsGentle ? "#fde047" : "#4ade80";
      ctx.textAlign = "center";
      ctx.fillText(this.feedbackMessage, w / 2, plaqueY + plaqueH + 30);
    }

    if (this.state === "VICTORY") {
      ctx.fillStyle = "rgba(15, 23, 42, 0.95)";
      ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

      ctx.fillStyle = "#facc15";
      ctx.font = "bold 26px 'Press Start 2P', monospace, sans-serif";
      ctx.textAlign = "center";
      ctx.shadowColor = "rgba(250, 204, 21, 0.8)";
      ctx.shadowBlur = 12;
      ctx.fillText("🎉 LEVEL CLEAR! 🎉", w / 2, 200);
      ctx.shadowBlur = 0;

      ctx.fillStyle = "#ffffff";
      ctx.font = "16px system-ui, sans-serif";
      ctx.fillText(`You completed all ${this.sessionLength} questions with high mastery!`, w / 2, 255);
    }

    ctx.restore();
  }
}
