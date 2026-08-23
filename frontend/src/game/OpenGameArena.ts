/**
 * OpenGame Dynamic Multi-Theme Engine
 * 
 * Generates custom 60fps canvas gameplay tailored to each child's interest:
 * - 🍝 Max (Spaghetti / Cooking): Real plate of steaming pasta with meatballs.
 *   Each correct answer lifts a twirling forkful of noodles; after 10 questions the plate is empty!
 * - 🎾 Lena (Tennis): A real tennis match where each correct answer serves a high-velocity
 *   ace past the opposing player across the net for a match point!
 * - 🦕 Maya (Dinosaurs): An archaeological dig where a brush sweeps away dirt to reveal a T-Rex fossil.
 * - 🚀 Leo (Space): Starship quantum docking into an orbital station.
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
    successLabel: "✦ Delicious Bite Tasted!",
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
    name: "🦕 Jurassic Fossil Dig",
    playerLabel: "Dig Brush",
    successLabel: "✦ Fossil Segment Unearthed!",
    bgColor: "#160e05",
    accentColor: "#f59e0b",
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
  nebula: {
    id: "nebula",
    name: "🌌 Deep Space Nebula",
    playerLabel: "Starship",
    successLabel: "✦ Star Pod Docked!",
    bgColor: "#070b14",
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
  if (combined.includes("dinosaur") || combined.includes("fossil") || combined.includes("paleontol")) {
    return THEMES.dinosaurs;
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

  // Profile & Skill
  public profileId: string;
  public skillId: string;
  public sessionLength: number = 10;
  public theme: GameTheme = THEMES.nebula;
  public soundEnabled: boolean = true;

  // State Machine
  public state: "TITLE" | "PLAYING" | "SUBMITTING" | "VICTORY" = "TITLE";
  public currentQuestion: Question | null = null;
  public score: number = 0;
  public answeredCount: number = 0;
  public feedbackMessage: string = "";
  public feedbackIsGentle: boolean = false;
  private shownAt: number = 0;

  // Particles
  private particles: ParticleSystem;
  private steamVapors: Array<{ x: number; y: number; vx: number; vy: number; alpha: number; size: number }> = [];

  // Player Actor (Fork, Tennis Racket, Dig Brush, Starship)
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
  };

  // Opponent Tennis Player (for Tennis Match)
  private opponent = {
    x: 400,
    y: 115,
    vx: 1.8,
    targetX: 400,
    diveOffset: 0,
    swinging: false,
  };

  // Tennis Ball Physics
  private tennisBall = {
    x: 400,
    y: 380,
    vx: 0,
    vy: 0,
    altitude: 0,
    active: false,
    trail: [] as Array<{ x: number; y: number; alpha: number }>,
  };

  // Dropped Spaghetti Physics
  private droppedSpaghetti = {
    x: 400,
    y: 220,
    vy: 0,
    alpha: 0,
    active: false,
  };

  // Biometric & Behavioral Nuance Tracking
  private startCursorPos: { x: number; y: number } | null = null;
  private lastCursorPos: { x: number; y: number } | null = null;
  private lastCursorMoveTime: number = 0;
  private totalCursorDistancePx: number = 0;
  private peakCursorVelocityPxS: number = 0;
  private idleDurationMs: number = 0;
  private firstInteractionTime: number = 0;
  private distractionEvents: number = 0;

  // Controls
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

  public destroy(): void {
    if (this.animFrameId !== null) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
  }

  private async loadNextQuestion(): Promise<void> {
    try {
      const q = await api.get<Question>(
        `/profiles/${this.profileId}/skills/${this.skillId}/next-question`
      );
      this.currentQuestion = q;
      this.shownAt = performance.now();
      this.state = "PLAYING";
      this.feedbackMessage = "";
      this.feedbackIsGentle = false;
      this.player.twirlAngle = 0;
      this.player.swingPhase = 0;
      this.tennisBall.active = false;
      this.opponent.diveOffset = 0;

      // Reset biometric & behavioral accumulation for this question
      this.startCursorPos = null;
      this.lastCursorPos = null;
      this.lastCursorMoveTime = performance.now();
      this.totalCursorDistancePx = 0;
      this.peakCursorVelocityPxS = 0;
      this.idleDurationMs = 0;
      this.firstInteractionTime = 0;
      this.distractionEvents = 0;

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

    // Calculate Nuanced Biometrics (2 decimal places)
    const hesitation = this.firstInteractionTime > 0 ? Math.round(this.firstInteractionTime - this.shownAt) : latency;
    const dtSec = Math.max(0.1, latency / 1000);
    const avgVelocity = Math.round((this.totalCursorDistancePx / dtSec) * 100) / 100;
    const peakVelocity = Math.round(this.peakCursorVelocityPxS * 100) / 100;
    const directDist = (this.startCursorPos && this.lastCursorPos)
      ? Math.hypot(this.lastCursorPos.x - this.startCursorPos.x, this.lastCursorPos.y - this.startCursorPos.y)
      : 25;
    const jitterRatio = Math.round((this.totalCursorDistancePx / Math.max(15, directDist)) * 100) / 100;
    const rawFocus = 100 - (this.idleDurationMs / latency) * 45 - this.distractionEvents * 25 - (jitterRatio > 2.8 ? 15 : 0);
    const focusScore = Math.round(Math.max(0, Math.min(100, rawFocus)) * 100) / 100;

    // Tennis Serve Launch
    if (this.theme.id === "tennis") {
      this.player.swingPhase = 1.0;
      this.tennisBall.active = true;
      this.tennisBall.x = this.player.x + 10;
      this.tennisBall.y = this.player.y - 15;
      const targetX = this.opponent.x > 400 ? 260 : 540;
      this.tennisBall.vx = (targetX - this.tennisBall.x) / 22;
      this.tennisBall.vy = (110 - this.tennisBall.y) / 22;
      this.tennisBall.altitude = 20;
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
        idle_time_ms: Math.round(this.idleDurationMs),
        hesitation_ms: hesitation,
        distraction_events: this.distractionEvents,
        focus_score: focusScore,
      });

      // Augment result with local biometric nuance for real-time dashboard
      result.focus_score = focusScore;
      result.jitter_ratio = jitterRatio;
      result.idle_time_ms = Math.round(this.idleDurationMs);
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
        idle_time_ms: this.idleDurationMs,
        distraction_events: this.distractionEvents,
      });

      this.callbacks.onAttemptResult?.(result);

      if (result.is_correct) {
        this.answeredCount += 1;
        this.score += 100;
        this.callbacks.onScoreUpdate?.(this.score, this.answeredCount);

        if (this.soundEnabled) soundFx.dockSuccess();

        // Thematic Celebrations
        if (this.theme.id === "cooking") {
          this.particles.emitExplosion(400, 180, "#ef4444", 26);
          this.particles.emitExplosion(400, 180, "#fde047", 18);
          this.particles.addFloatingText(400, 140, "+1 DELICIOUS BITE!", "#ef4444");
        } else if (this.theme.id === "tennis") {
          this.opponent.diveOffset = this.tennisBall.vx > 0 ? -40 : 40;
          this.particles.emitExplosion(this.tennisBall.x, 110, "#ffffff", 24);
          this.particles.addFloatingText(this.opponent.x, 75, "🎾 ACE! PAST OPPONENT!", "#4ade80");
        } else if (this.theme.id === "dinosaurs") {
          this.particles.emitExplosion(400, 180, "#f59e0b", 26);
          this.particles.addFloatingText(400, 140, "+1 FOSSIL UNEARTHED!", "#f59e0b");
        } else {
          this.particles.emitExplosion(400, 180, this.theme.accentColor, 24);
          this.particles.addFloatingText(400, 140, "✦ DOCKED!", this.theme.accentColor);
        }

        this.particles.shake(200, 3.5);
        this.feedbackMessage = this.theme.successLabel;
        this.feedbackIsGentle = false;

        if (this.answeredCount >= this.sessionLength) {
          setTimeout(() => {
            this.state = "VICTORY";
            capture("level_completed", { total_answered: this.answeredCount });
            this.callbacks.onLevelComplete?.();
          }, 1100);
        } else {
          setTimeout(() => this.loadNextQuestion(), 950);
        }
      } else {
        if (this.soundEnabled) soundFx.gentleRetry();

        // Thematic Physical Miss Mechanics
        if (this.theme.id === "cooking") {
          // Spaghetti slips off the fork and drops onto the table
          this.droppedSpaghetti = { x: 400, y: 220, vy: 3.5, alpha: 1.0, active: true };
          this.particles.emitExplosion(400, 240, "#facc15", 14);
          this.particles.emitExplosion(400, 310, "#ef4444", 10);
          this.particles.addFloatingText(400, 260, "🍝 Slipped off the fork!", "#f59e0b");
        } else if (this.theme.id === "tennis") {
          // Opponent hits the ball right back past our baseline!
          this.opponent.x = Math.max(120, Math.min(680, this.tennisBall.x));
          this.opponent.diveOffset = 0;
          this.tennisBall.vy = 9.5;
          this.tennisBall.vx = (Math.random() - 0.5) * 5;
          this.particles.emitExplosion(this.opponent.x, 115, "#ffffff", 16);
          this.particles.addFloatingText(this.opponent.x, 80, "🎾 Opponent Returned Ball!", "#38bdf8");
        } else if (this.theme.id === "dinosaurs") {
          this.particles.emitExplosion(400, 185, "#78350f", 16);
          this.particles.addFloatingText(400, 140, "🪨 Hard stone layer! Next dig...", "#f59e0b");
        } else {
          this.particles.emitExplosion(400, 185, "#38bdf8", 14);
          this.particles.addFloatingText(400, 140, "🚀 Deflected / Missed! Re-aligning...", "#fbbf24");
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
    // 1. Steam Vapors
    for (const v of this.steamVapors) {
      v.x += v.vx;
      v.y += v.vy;
      v.alpha -= 0.007;
      if (v.alpha <= 0 || v.y < 110) {
        v.x = 400 + (Math.random() - 0.5) * 60;
        v.y = 180 + (Math.random() - 0.5) * 30;
        v.alpha = Math.random() * 0.5 + 0.2;
      }
    }

    // 2. Dropped Spaghetti Physics
    if (this.droppedSpaghetti.active) {
      this.droppedSpaghetti.y += this.droppedSpaghetti.vy;
      this.droppedSpaghetti.vy += 0.25;
      if (this.droppedSpaghetti.y > 330) {
        this.droppedSpaghetti.active = false;
      }
    }

    // 3. Tennis Ball Physics
    if (this.tennisBall.active) {
      this.tennisBall.x += this.tennisBall.vx;
      this.tennisBall.y += this.tennisBall.vy;
      this.tennisBall.altitude = Math.max(0, this.tennisBall.altitude - 0.8);
      this.tennisBall.trail.push({ x: this.tennisBall.x, y: this.tennisBall.y, alpha: 0.9 });
      if (this.tennisBall.trail.length > 12) this.tennisBall.trail.shift();
    }

    // 4. Opponent Pacing (Tennis)
    if (this.theme.id === "tennis") {
      this.opponent.x += this.opponent.vx;
      if (this.opponent.x > 520 || this.opponent.x < 280) {
        this.opponent.vx = -this.opponent.vx;
      }
    }

    // 4. Player Steering
    this.player.idlePhase += 0.04;
    if (this.state === "SUBMITTING") {
      this.player.twirlAngle += 0.22;
    }

    if (this.targetX !== null && this.targetY !== null) {
      const dx = this.targetX - this.player.x;
      const dy = this.targetY - this.player.y;
      const dist = Math.hypot(dx, dy);
      if (dist > 12) {
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

    // Bounds
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

    // 1. World Environment
    this.renderEnvironment(ctx, w, h);

    // 2. Center Target / Match Item
    if (this.theme.id === "cooking") {
      this.renderSpaghettiPlate(ctx, 400, 185);
    } else if (this.theme.id === "tennis") {
      this.renderTennisMatch(ctx, w, h);
    } else if (this.theme.id === "dinosaurs") {
      this.renderDinosaurDigSite(ctx, 400, 185);
    } else {
      this.renderSpaceStation(ctx, 400, 185);
    }

    // 3. Player Actor (Fork, Racket, Brush, Starship)
    this.renderPlayerActor(ctx);

    // 4. Single Focal Point HUD
    this.renderHUD();

    // 5. Particles & Text
    this.particles.render(ctx);

    ctx.restore();
  }

  private renderEnvironment(ctx: CanvasRenderingContext2D, w: number, h: number): void {
    ctx.fillStyle = this.theme.bgColor;
    ctx.fillRect(0, 0, w, h);

    if (this.theme.id === "cooking") {
      // Warm Italian Gingham Checkered Dining Table
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
      // Grass Court with Regulation White Chalk Lines
      ctx.fillStyle = "#0c3b1e";
      ctx.fillRect(40, 20, w - 80, h - 40);

      ctx.strokeStyle = "rgba(255, 255, 255, 0.7)";
      ctx.lineWidth = 2.5;
      // Baseline & Sidelines
      ctx.strokeRect(60, 40, w - 120, h - 80);
      // Service Line (Top)
      ctx.strokeRect(120, 90, w - 240, 90);
      // Service Line (Bottom)
      ctx.strokeRect(120, h / 2 + 10, w - 240, 90);
      // Center Line
      ctx.beginPath();
      ctx.moveTo(w / 2, 90);
      ctx.lineTo(w / 2, h - 130);
      ctx.stroke();
    } else {
      // Cosmic Grid
      ctx.strokeStyle = "rgba(56, 189, 248, 0.08)";
      ctx.lineWidth = 1;
      for (let x = 0; x < w; x += 60) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
    }
  }

  // ==========================================
  // 1. MAX'S REAL SPAGHETTI PLATE (BITE-BY-BITE)
  // ==========================================
  private renderSpaghettiPlate(ctx: CanvasRenderingContext2D, cx: number, cy: number): void {
    const remainingPct = Math.max(0, 1 - this.answeredCount / this.sessionLength);

    ctx.save();
    // Plate Outer Ceramic Shadow
    ctx.fillStyle = "rgba(0, 0, 0, 0.45)";
    ctx.beginPath();
    ctx.arc(cx, cy + 8, 92, 0, Math.PI * 2);
    ctx.fill();

    // White Porcelain Plate Rim with Red Tuscan Band
    ctx.fillStyle = "#f8fafc";
    ctx.strokeStyle = "#dc2626";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(cx, cy, 90, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Plate Inner Well
    ctx.fillStyle = "#f1f5f9";
    ctx.beginPath();
    ctx.arc(cx, cy, 70, 0, Math.PI * 2);
    ctx.fill();

    if (remainingPct > 0) {
      // Steaming Hot Vapor Particles
      for (const v of this.steamVapors) {
        ctx.fillStyle = "rgba(255, 255, 255, " + v.alpha + ")";
        ctx.beginPath();
        ctx.arc(v.x, v.y, v.size, 0, Math.PI * 2);
        ctx.fill();
      }

      // Golden Spaghetti Mound (Proportionally Shrinks as Max Eats!)
      const pastaRadius = 56 * Math.sqrt(remainingPct);
      ctx.fillStyle = "#facc15";
      ctx.strokeStyle = "#ca8a04";
      ctx.lineWidth = 2.5;

      ctx.beginPath();
      ctx.arc(cx, cy, pastaRadius, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Swirling Noodle Strands
      ctx.strokeStyle = "#eab308";
      ctx.lineWidth = 2;
      for (let i = 0; i < Math.ceil(8 * remainingPct); i++) {
        const ang = (i * Math.PI) / 4;
        ctx.beginPath();
        ctx.ellipse(cx + Math.cos(ang) * 12, cy + Math.sin(ang) * 10, pastaRadius * 0.6, pastaRadius * 0.35, ang, 0, Math.PI * 2);
        ctx.stroke();
      }

      // Rich Red Marinara Sauce Layer
      ctx.fillStyle = "rgba(220, 38, 38, 0.92)";
      ctx.beginPath();
      ctx.arc(cx, cy - 4, pastaRadius * 0.65, 0, Math.PI * 2);
      ctx.fill();

      // Savory Meatballs (3 Meatballs that vanish bite-by-bite)
      const meatballCount = Math.ceil(3 * remainingPct);
      const mbOffsets = [
        { x: -15, y: -10 },
        { x: 16, y: -8 },
        { x: 0, y: 14 },
      ];
      ctx.fillStyle = "#78350f";
      ctx.strokeStyle = "#451a03";
      ctx.lineWidth = 1.5;
      for (let i = 0; i < meatballCount; i++) {
        ctx.beginPath();
        ctx.arc(cx + mbOffsets[i].x, cy + mbOffsets[i].y, 11, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      }

      // Fresh Green Basil Leaf Garnish
      if (remainingPct > 0.25) {
        ctx.fillStyle = "#16a34a";
        ctx.beginPath();
        ctx.ellipse(cx + 2, cy - 14, 8, 4, Math.PI / 4, 0, Math.PI * 2);
        ctx.fill();
      }
    } else {
      // Completely Clean Plate with leftover sauce streaks!
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

    // Dropped Spaghetti Noodles Splatter on Table
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

  // ==========================================
  // 2. LENA'S REAL GRAND SLAM TENNIS MATCH
  // ==========================================
  private renderTennisMatch(ctx: CanvasRenderingContext2D, w: number, h: number): void {
    const netY = h / 2 - 5;

    // 1. Tennis Net across the court
    ctx.save();
    ctx.fillStyle = "rgba(255, 255, 255, 0.4)";
    ctx.fillRect(40, netY, w - 80, 14);
    // White top tape
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(40, netY, w - 80, 3);
    // Net posts
    ctx.fillStyle = "#334155";
    ctx.fillRect(36, netY - 8, 6, 26);
    ctx.fillRect(w - 42, netY - 8, 6, 26);
    ctx.restore();

    // 2. Opponent Player across the net (Pacing Baseline)
    ctx.save();
    const opX = this.opponent.x + this.opponent.diveOffset;
    const opY = this.opponent.y;

    // Opponent Shadow
    ctx.fillStyle = "rgba(0, 0, 0, 0.35)";
    ctx.beginPath();
    ctx.ellipse(opX, opY + 22, 14, 6, 0, 0, Math.PI * 2);
    ctx.fill();

    // Opponent Body (Tennis Whites)
    ctx.fillStyle = "#38bdf8";
    ctx.beginPath();
    ctx.arc(opX, opY, 10, 0, Math.PI * 2); // Head
    ctx.fill();

    ctx.fillStyle = "#ffffff";
    ctx.fillRect(opX - 7, opY + 8, 14, 16); // Jersey

    // Opponent Racket
    ctx.strokeStyle = "#f87171";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.arc(opX + 16, opY + 8, 9, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();

    // 3. High-Velocity Tennis Ball Serve with Trail
    if (this.tennisBall.active) {
      ctx.save();
      // Ball Trail
      for (const t of this.tennisBall.trail) {
        ctx.fillStyle = `rgba(204, 255, 0, ${t.alpha * 0.5})`;
        ctx.beginPath();
        ctx.arc(t.x, t.y, 4, 0, Math.PI * 2);
        ctx.fill();
      }

      // Fuzzy Optic Yellow Tennis Ball with white seam
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

  // ==========================================
  // 3. MAYA'S REAL JURASSIC FOSSIL DIG SITE
  // ==========================================
  private renderDinosaurDigSite(ctx: CanvasRenderingContext2D, cx: number, cy: number): void {
    const unearthedBones = Math.min(10, this.answeredCount);

    ctx.save();
    // Excavation Trench Border
    ctx.fillStyle = "#1e1408";
    ctx.strokeStyle = "#f59e0b";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.arc(cx, cy, 78, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Unearthed T-Rex Skeleton Segments
    ctx.fillStyle = "#fef08a";
    ctx.shadowColor = "#f59e0b";
    ctx.shadowBlur = 12;

    // Skull
    if (unearthedBones >= 1) {
      ctx.beginPath();
      ctx.ellipse(cx, cy - 26, 22, 14, 0, 0, Math.PI * 2);
      ctx.fill();
    }
    // Spine & Ribs
    if (unearthedBones >= 3) {
      ctx.fillRect(cx - 4, cy - 10, 8, 35);
      for (let r = 0; r < 4; r++) {
        ctx.fillRect(cx - 16, cy - 5 + r * 8, 32, 3);
      }
    }
    // Tail
    if (unearthedBones >= 6) {
      ctx.beginPath();
      ctx.moveTo(cx, cy + 25);
      ctx.lineTo(cx + 25, cy + 45);
      ctx.lineTo(cx + 36, cy + 42);
      ctx.stroke();
    }

    ctx.shadowBlur = 0;
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.font = "bold 15px monospace";
    ctx.fillText(`${unearthedBones}/10 BONES UNEARTHED`, cx, cy + 62);
    ctx.restore();
  }

  // ==========================================
  // 4. LEO'S COSMIC ORBITAL DOCKING
  // ==========================================
  private renderSpaceStation(ctx: CanvasRenderingContext2D, cx: number, cy: number): void {
    ctx.save();
    ctx.fillStyle = "rgba(15, 23, 42, 0.92)";
    ctx.strokeStyle = this.theme.accentColor;
    ctx.lineWidth = 3;
    ctx.shadowColor = this.theme.accentColor;
    ctx.shadowBlur = 10;

    ctx.beginPath();
    ctx.arc(cx, cy, 48, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Solar Wings
    ctx.fillStyle = "#38bdf8";
    ctx.fillRect(cx - 85, cy - 6, 32, 12);
    ctx.fillRect(cx + 53, cy - 6, 32, 12);

    ctx.shadowBlur = 0;
    ctx.restore();
  }

  // ==========================================
  // PLAYER ACTOR RENDERING
  // ==========================================
  private renderPlayerActor(ctx: CanvasRenderingContext2D): void {
    ctx.save();
    ctx.translate(this.player.x, this.player.y + Math.sin(this.player.idlePhase) * 2);
    ctx.rotate(this.player.angle + Math.PI / 2 + this.player.twirlAngle);

    if (this.theme.id === "cooking") {
      // 🍴 Polished Stainless Steel Fork
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

      // 4 Fork Tines
      ctx.fillStyle = "#f8fafc";
      for (let i = 0; i < 4; i++) {
        ctx.fillRect(-9 + i * 5.5, -26, 2.5, 20);
      }

      // Twirled Spaghetti on Fork if Submitting
      if (this.state === "SUBMITTING") {
        ctx.fillStyle = "#facc15";
        ctx.beginPath();
        ctx.arc(0, -16, 13, 0, Math.PI * 2);
        ctx.fill();
      }
    } else if (this.theme.id === "tennis") {
      // 🎾 Lena's Tennis Racket with String Mesh
      ctx.fillStyle = "#1e293b";
      ctx.fillRect(-3, 12, 6, 28); // Grip

      ctx.strokeStyle = "#4ade80";
      ctx.lineWidth = 3.5;
      ctx.beginPath();
      ctx.ellipse(0, -12, 16, 22, 0, 0, Math.PI * 2);
      ctx.stroke();

      // Racket Strings
      ctx.strokeStyle = "rgba(255, 255, 255, 0.4)";
      ctx.lineWidth = 1;
      for (let x = -10; x <= 10; x += 5) {
        ctx.beginPath();
        ctx.moveTo(x, -28);
        ctx.lineTo(x, 4);
        ctx.stroke();
      }
    } else if (this.theme.id === "dinosaurs") {
      // 🦕 Archeology Field Brush
      ctx.fillStyle = "#78350f";
      ctx.fillRect(-4, 0, 8, 30);
      ctx.fillStyle = "#d97706";
      ctx.fillRect(-8, -12, 16, 12);
      ctx.fillStyle = "#fef3c7";
      ctx.fillRect(-10, -26, 20, 14);
    } else {
      // 🚀 Vector Starship
      ctx.fillStyle = "#38bdf8";
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, -this.player.size);
      ctx.lineTo(this.player.size * 0.75, this.player.size);
      ctx.lineTo(0, this.player.size * 0.5);
      ctx.lineTo(-this.player.size * 0.75, this.player.size);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
    }

    ctx.restore();
  }

  private renderHUD(): void {
    const ctx = this.ctx;
    const w = this.canvas.width;

    ctx.save();
    ctx.fillStyle = "rgba(15, 23, 42, 0.92)";
    ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
    ctx.lineWidth = 1.5;

    const bannerW = Math.min(w * 0.85, 420);
    const bannerH = 56;
    const bannerX = (w - bannerW) / 2;
    const bannerY = 12;

    ctx.beginPath();
    ctx.roundRect(bannerX, bannerY, bannerW, bannerH, 12);
    ctx.fill();
    ctx.stroke();

    if (this.currentQuestion) {
      const [a, b] = this.currentQuestion.operands;
      const op = this.currentQuestion.operator;
      ctx.fillStyle = this.theme.accentColor;
      ctx.font = "bold 26px monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(`✦  ${a} ${op} ${b} = ?`, w / 2, bannerY + bannerH / 2);
    }

    if (this.feedbackMessage) {
      ctx.fillStyle = this.feedbackIsGentle ? "#fbbf24" : "#4ade80";
      ctx.font = "bold 16px 'Inter', system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(this.feedbackMessage, w / 2, bannerY + bannerH + 28);
    }

    ctx.restore();
  }

  private bindEvents(): void {
    window.addEventListener("blur", () => {
      this.distractionEvents += 1;
      capture("window_blurred", { profile_id: this.profileId, skill_id: this.skillId });
    });

    window.addEventListener("keydown", () => {
      if (!this.firstInteractionTime) {
        this.firstInteractionTime = performance.now();
      }
    });

    this.canvas.addEventListener("pointermove", (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const scaleX = this.canvas.width / rect.width;
      const scaleY = this.canvas.height / rect.height;
      const x = (e.clientX - rect.left) * scaleX;
      const y = (e.clientY - rect.top) * scaleY;
      const now = performance.now();

      if (!this.firstInteractionTime) {
        this.firstInteractionTime = now;
      }

      if (!this.startCursorPos) {
        this.startCursorPos = { x, y };
      }

      if (this.lastCursorPos && this.lastCursorMoveTime > 0) {
        const dt = Math.max(1, now - this.lastCursorMoveTime);
        const dist = Math.hypot(x - this.lastCursorPos.x, y - this.lastCursorPos.y);

        if (dt > 1200) {
          this.idleDurationMs += dt;
        }

        this.totalCursorDistancePx += dist;
        const instVelocity = (dist / dt) * 1000;
        if (instVelocity > this.peakCursorVelocityPxS) {
          this.peakCursorVelocityPxS = instVelocity;
        }
      }

      this.lastCursorPos = { x, y };
      this.lastCursorMoveTime = now;
    });

    this.canvas.addEventListener("pointerdown", (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const scaleX = this.canvas.width / rect.width;
      const scaleY = this.canvas.height / rect.height;
      this.targetX = (e.clientX - rect.left) * scaleX;
      this.targetY = (e.clientY - rect.top) * scaleY;

      if (!this.firstInteractionTime) {
        this.firstInteractionTime = performance.now();
      }
    });

    window.addEventListener("resize", () => this.resizeCanvas());
  }

  private resizeCanvas(): void {
    const parent = this.canvas.parentElement;
    if (parent) {
      this.canvas.width = 800;
      this.canvas.height = 480;
    }
  }
}
