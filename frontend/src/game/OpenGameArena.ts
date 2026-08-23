/**
 * OpenGame Dynamic Multi-Theme Engine
 * 
 * Generates custom 60fps canvas gameplay tailored to each child's interest:
 * - 🍝 Max (Cooking / Spaghetti): First-person plate of steaming pasta with meatballs.
 *   Each correct answer twirls up a bite with the fork; after 10 questions the plate is empty!
 * - 🦕 Maya (Dinosaurs / Fossils): Jurassic archaeological dig where each question unearths
 *   a piece of a glowing T-Rex fossil skeleton using a field brush.
 * - 🎾 Lena (Tennis / Horses): Grand slam championship court with racket serve mechanics.
 * - 🚀 Leo (Space / Trains): Cosmic star-docking and steam locomotive navigation.
 */

import { AttemptResult, Question, api } from "../api";
import { capture } from "../telemetry";
import { ParticleSystem } from "./ParticleSystem";
import { soundFx } from "./SoundFx";

export interface GameTheme {
  id: string;
  name: string;
  targetLabel: string;
  playerLabel: string;
  successLabel: string;
  bgColor: string;
  gridColor: string;
  accentColor: string;
  playerColor: string;
  starColors: string[];
  laserColor: string;
}

export const THEMES: Record<string, GameTheme> = {
  cooking: {
    id: "cooking",
    name: "🍝 Spaghetti Feast",
    targetLabel: "🍝 PASTA PLATE",
    playerLabel: "Fork",
    successLabel: "✦ Delicious Bite Tasted!",
    bgColor: "#1a0d0d",
    gridColor: "rgba(239, 68, 68, 0.08)",
    accentColor: "#ef4444",
    playerColor: "#cbd5e1",
    starColors: ["#fff1f2", "#fecdd3", "#fb7185", "#fde047"],
    laserColor: "#f59e0b",
  },
  dinosaurs: {
    id: "dinosaurs",
    name: "🦕 Jurassic Fossil Dig",
    targetLabel: "🦴 FOSSIL SITE",
    playerLabel: "Dig Brush",
    successLabel: "✦ Fossil Segment Unearthed!",
    bgColor: "#140e06",
    gridColor: "rgba(245, 158, 11, 0.08)",
    accentColor: "#f59e0b",
    playerColor: "#d97706",
    starColors: ["#fef3c7", "#fde68a", "#d97706", "#6ee7b7"],
    laserColor: "#f59e0b",
  },
  tennis: {
    id: "tennis",
    name: "🎾 Grand Slam Tennis",
    targetLabel: "🏆 COURT NET",
    playerLabel: "Tennis Racket",
    successLabel: "✦ Ace Serve Past Opponent!",
    bgColor: "#051a10",
    gridColor: "rgba(74, 222, 128, 0.08)",
    accentColor: "#4ade80",
    playerColor: "#a3e635",
    starColors: ["#f0fdf4", "#bbf7d0", "#86efac", "#facc15"],
    laserColor: "#4ade80",
  },
  horses: {
    id: "horses",
    name: "🐴 Equestrian Meadow",
    targetLabel: "🏇 STABLE GATE",
    playerLabel: "Horseshoe Rider",
    successLabel: "✦ Meadow Gate Cleared!",
    bgColor: "#0b170e",
    gridColor: "rgba(132, 204, 22, 0.08)",
    accentColor: "#84cc16",
    playerColor: "#eab308",
    starColors: ["#f7fee7", "#ecfccb", "#bef264", "#fef08a"],
    laserColor: "#84cc16",
  },
  trains: {
    id: "trains",
    name: "🚂 Steam Locomotive",
    targetLabel: "🚉 TRAIN DEPOT",
    playerLabel: "Steam Engine",
    successLabel: "✦ Train Station Reached!",
    bgColor: "#09121d",
    gridColor: "rgba(148, 163, 184, 0.08)",
    accentColor: "#38bdf8",
    playerColor: "#f59e0b",
    starColors: ["#f8fafc", "#e2e8f0", "#94a3b8", "#38bdf8"],
    laserColor: "#38bdf8",
  },
  nebula: {
    id: "nebula",
    name: "🌌 Deep Space Nebula",
    targetLabel: "✦ DOCK HUB",
    playerLabel: "Starship",
    successLabel: "✦ Star Pod Docked!",
    bgColor: "#070b14",
    gridColor: "rgba(56, 189, 248, 0.06)",
    accentColor: "#38bdf8",
    playerColor: "#60a5fa",
    starColors: ["#ffffff", "#93c5fd", "#c084fc", "#38bdf8"],
    laserColor: "#38bdf8",
  },
};

export function getThemeForInterests(interests: string[] = []): GameTheme {
  const combined = interests.join(" ").toLowerCase();
  if (combined.includes("spaghetti") || combined.includes("pasta") || combined.includes("cook") || combined.includes("food") || combined.includes("baking") || combined.includes("pizza")) {
    return THEMES.cooking;
  }
  if (combined.includes("dinosaur") || combined.includes("fossil") || combined.includes("paleontol")) {
    return THEMES.dinosaurs;
  }
  if (combined.includes("tennis")) {
    return THEMES.tennis;
  }
  if (combined.includes("horse") || combined.includes("equestrian") || combined.includes("riding")) {
    return THEMES.horses;
  }
  if (combined.includes("train") || combined.includes("railway") || combined.includes("locomotive")) {
    return THEMES.trains;
  }
  return THEMES.nebula;
}

export interface Station {
  id: string;
  x: number;
  y: number;
  radius: number;
  pulsePhase: number;
  docked: boolean;
}

export interface LaserBeam {
  startX: number;
  startY: number;
  endX: number;
  endY: number;
  alpha: number;
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
  public particleIntensity: "low" | "standard" | "high" = "standard";

  // State Machine: Title -> Playing -> Submitting -> Victory
  public state: "TITLE" | "PLAYING" | "SUBMITTING" | "VICTORY" = "TITLE";
  public currentQuestion: Question | null = null;
  public score: number = 0;
  public answeredCount: number = 0;
  public feedbackMessage: string = "";
  public feedbackIsGentle: boolean = false;
  private shownAt: number = 0;

  // Visuals & Particles
  private particles: ParticleSystem;
  private steamVapors: Array<{ x: number; y: number; vx: number; vy: number; alpha: number; size: number }> = [];

  // Player Utensil / Vehicle
  private player = {
    x: 400,
    y: 380,
    vx: 0,
    vy: 0,
    angle: -Math.PI / 2,
    targetAngle: -Math.PI / 2,
    speed: 6.0,
    size: 26,
    idlePhase: 0,
    twirlAngle: 0,
  };

  // Centerpiece Hub (Plate, Fossil Pit, Net, or Space Station)
  private centerpiece: Station = {
    id: "main-target",
    x: 400,
    y: 175,
    radius: 70,
    pulsePhase: 0,
    docked: false,
  };
  private laserBeams: LaserBeam[] = [];

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

    this.initVapors();
    this.bindEvents();
    this.resizeCanvas();
  }

  public setTheme(themeKey: string): void {
    this.theme = THEMES[themeKey] || THEMES.nebula;
    this.initVapors();
  }

  public setAudio(enabled: boolean): void {
    this.soundEnabled = enabled;
    soundFx.enabled = enabled;
  }

  private initVapors(): void {
    this.steamVapors = [];
    for (let i = 0; i < 25; i++) {
      this.steamVapors.push({
        x: this.centerpiece.x + (Math.random() - 0.5) * 60,
        y: this.centerpiece.y + (Math.random() - 0.5) * 40,
        vx: (Math.random() - 0.5) * 0.4,
        vy: -Math.random() * 0.8 - 0.4,
        alpha: Math.random() * 0.6 + 0.2,
        size: Math.random() * 8 + 4,
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
      this.centerpiece.docked = false;

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

    // Action Beam / Fork Motion toward Centerpiece
    this.laserBeams.push({
      startX: this.player.x,
      startY: this.player.y,
      endX: this.centerpiece.x,
      endY: this.centerpiece.y,
      alpha: 1.0,
    });

    if (this.soundEnabled) soundFx.laser();

    try {
      const result = await api.post<AttemptResult>("/attempts", {
        profile_id: this.profileId,
        skill_id: this.skillId,
        operands: this.currentQuestion.operands,
        operator: this.currentQuestion.operator,
        answer_given: answerVal,
        latency_to_submit_ms: latency,
      });

      capture("answer_submitted", {
        game_id: `orbit-${this.theme.id}`,
        profile_id: this.profileId,
        skill_id: this.skillId,
        correct: result.is_correct,
        time_to_solve_ms: latency,
        error_class: result.error_class || "unknown",
      });

      this.callbacks.onAttemptResult?.(result);

      if (result.is_correct) {
        this.centerpiece.docked = true;
        this.answeredCount += 1;
        this.score += 100;
        this.callbacks.onScoreUpdate?.(this.score, this.answeredCount);

        if (this.soundEnabled) soundFx.dockSuccess();

        // Thematic particle explosion
        if (this.theme.id === "cooking") {
          this.particles.emitExplosion(this.centerpiece.x, this.centerpiece.y, "#ef4444", 28);
          this.particles.emitExplosion(this.centerpiece.x, this.centerpiece.y, "#fde047", 16);
          this.particles.addFloatingText(this.centerpiece.x, this.centerpiece.y - 30, "+1 DELICIOUS BITE!", "#ef4444");
        } else if (this.theme.id === "dinosaurs") {
          this.particles.emitExplosion(this.centerpiece.x, this.centerpiece.y, "#f59e0b", 26);
          this.particles.addFloatingText(this.centerpiece.x, this.centerpiece.y - 30, "+1 FOSSIL UNEARTHED!", "#f59e0b");
        } else if (this.theme.id === "tennis") {
          this.particles.emitExplosion(this.centerpiece.x, this.centerpiece.y, "#4ade80", 26);
          this.particles.addFloatingText(this.centerpiece.x, this.centerpiece.y - 30, "🎾 ACE SERVE!", "#4ade80");
        } else {
          this.particles.emitExplosion(this.centerpiece.x, this.centerpiece.y, this.theme.accentColor, 24);
          this.particles.addFloatingText(this.centerpiece.x, this.centerpiece.y - 30, "✦ DOCKED!", this.theme.accentColor);
        }

        this.particles.shake(200, 4);
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
        this.particles.emitExplosion(this.centerpiece.x, this.centerpiece.y, "#fbbf24", 12);
        this.feedbackMessage = `Almost — it was ${this.currentQuestion.correct_answer}. Next one incoming!`;
        this.feedbackIsGentle = true;

        setTimeout(() => this.loadNextQuestion(), 1300);
      }
    } catch (err) {
      this.callbacks.onError?.((err as Error).message);
      this.state = "PLAYING";
    }
  }

  private update(deltaMs: number): void {
    // 1. Steam Vapors (Cooking theme)
    for (const v of this.steamVapors) {
      v.x += v.vx;
      v.y += v.vy;
      v.alpha -= 0.008;
      if (v.alpha <= 0 || v.y < this.centerpiece.y - 80) {
        v.x = this.centerpiece.x + (Math.random() - 0.5) * 50;
        v.y = this.centerpiece.y + 10;
        v.alpha = Math.random() * 0.5 + 0.2;
      }
    }

    // 2. Action Beams
    for (let i = this.laserBeams.length - 1; i >= 0; i--) {
      this.laserBeams[i].alpha -= 0.08;
      if (this.laserBeams[i].alpha <= 0) this.laserBeams.splice(i, 1);
    }

    // 3. Player Steering & Inertia
    this.player.idlePhase += 0.04;
    if (this.state === "SUBMITTING") {
      this.player.twirlAngle += 0.25;
    }

    if (this.targetX !== null && this.targetY !== null) {
      const dx = this.targetX - this.player.x;
      const dy = this.targetY - this.player.y;
      const dist = Math.hypot(dx, dy);
      if (dist > 15) {
        this.player.vx += (dx / dist) * 0.5;
        this.player.vy += (dy / dist) * 0.5;
        this.player.targetAngle = Math.atan2(dy, dx);
      } else {
        this.targetX = null;
        this.targetY = null;
      }
    }

    this.player.vx *= 0.92;
    this.player.vy *= 0.92;
    this.player.x += this.player.vx * this.player.speed;
    this.player.y += this.player.vy * this.player.speed;

    // Bounds clamping
    const pad = 40;
    this.player.x = Math.max(pad, Math.min(this.canvas.width - pad, this.player.x));
    this.player.y = Math.max(this.canvas.height / 2 + 10, Math.min(this.canvas.height - pad, this.player.y));

    this.centerpiece.pulsePhase += 0.05;
    this.particles.update(deltaMs);
  }

  private render(): void {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;

    ctx.save();

    // Screen Shake
    if (this.particles.shakeDuration > 0) {
      const intensity = this.particles.shakeIntensity;
      ctx.translate((Math.random() - 0.5) * intensity * 2, (Math.random() - 0.5) * intensity * 2);
    }

    // 1. Render Thematic Environment
    this.renderEnvironment(ctx, w, h);

    // 2. Render Thematic Target Centerpiece
    this.renderCenterpiece(ctx);

    // 3. Render Laser Beams / Action Trails
    ctx.save();
    for (const b of this.laserBeams) {
      ctx.strokeStyle = this.theme.laserColor;
      ctx.globalAlpha = b.alpha;
      ctx.lineWidth = 4;
      ctx.shadowColor = this.theme.laserColor;
      ctx.shadowBlur = 12;
      ctx.beginPath();
      ctx.moveTo(b.startX, b.startY);
      ctx.lineTo(b.endX, b.endY);
      ctx.stroke();
    }
    ctx.restore();

    // 4. Render Thematic Player Actor (Fork, Brush, Racket, or Starship)
    this.renderPlayerActor(ctx);

    // 5. Render HUD Banner
    this.renderHUD();

    // 6. Particles & Popups
    this.particles.render(ctx);

    ctx.restore();
  }

  private renderEnvironment(ctx: CanvasRenderingContext2D, w: number, h: number): void {
    ctx.fillStyle = this.theme.bgColor;
    ctx.fillRect(0, 0, w, h);

    if (this.theme.id === "cooking") {
      // Warm Italian checkered dining tablecloth
      const cellSize = 40;
      for (let x = 0; x < w; x += cellSize) {
        for (let y = 0; y < h; y += cellSize) {
          if ((Math.floor(x / cellSize) + Math.floor(y / cellSize)) % 2 === 0) {
            ctx.fillStyle = "rgba(239, 68, 68, 0.04)";
            ctx.fillRect(x, y, cellSize, cellSize);
          }
        }
      }
      // Wooden table edge
      ctx.strokeStyle = "rgba(245, 158, 11, 0.15)";
      ctx.lineWidth = 2;
      ctx.strokeRect(16, 16, w - 32, h - 32);
    } else if (this.theme.id === "dinosaurs") {
      // Archaeological Sandstone Grid
      ctx.strokeStyle = "rgba(245, 158, 11, 0.1)";
      ctx.lineWidth = 1;
      for (let x = 0; x < w; x += 50) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let y = 0; y < h; y += 50) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }
    } else if (this.theme.id === "tennis") {
      // Grass Court with Regulation White Lines & Net
      ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
      ctx.lineWidth = 2;
      ctx.strokeRect(60, 40, w - 120, h - 80);
      // Net Line
      ctx.strokeStyle = "rgba(255, 255, 255, 0.6)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(40, h / 2);
      ctx.lineTo(w - 40, h / 2);
      ctx.stroke();
    } else {
      // Cosmic Orbit Coordinate Grid
      ctx.strokeStyle = this.theme.gridColor;
      ctx.lineWidth = 1;
      for (let x = 0; x < w; x += 60) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
    }
  }

  private renderCenterpiece(ctx: CanvasRenderingContext2D): void {
    const cx = this.centerpiece.x;
    const cy = this.centerpiece.y;
    const remainingPct = Math.max(0, 1 - this.answeredCount / this.sessionLength);

    if (this.theme.id === "cooking") {
      // ==========================================
      // MAX'S STEAMING SPAGHETTI PLATE (BITE-BY-BITE)
      // ==========================================
      ctx.save();
      // Plate Shadow
      ctx.fillStyle = "rgba(0, 0, 0, 0.4)";
      ctx.beginPath();
      ctx.arc(cx, cy + 8, 90, 0, Math.PI * 2);
      ctx.fill();

      // Porcelain Plate Outer Rim
      ctx.fillStyle = "#f8fafc";
      ctx.strokeStyle = "#e2e8f0";
      ctx.lineWidth = 4;
      ctx.beginPath();
      ctx.arc(cx, cy, 88, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Plate Inner Well
      ctx.fillStyle = "#f1f5f9";
      ctx.beginPath();
      ctx.arc(cx, cy, 68, 0, Math.PI * 2);
      ctx.fill();

      if (remainingPct > 0) {
        // Steaming Vapor Particles
        for (const v of this.steamVapors) {
          ctx.fillStyle = "rgba(255, 255, 255, " + v.alpha + ")";
          ctx.beginPath();
          ctx.arc(v.x, v.y, v.size, 0, Math.PI * 2);
          ctx.fill();
        }

        // Golden Spaghetti Noodles Mound (Shrinks proportionally with each question!)
        const pastaRadius = 55 * Math.sqrt(remainingPct);
        ctx.fillStyle = "#facc15";
        ctx.strokeStyle = "#eab308";
        ctx.lineWidth = 2.5;

        ctx.beginPath();
        ctx.arc(cx, cy, pastaRadius, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        // Tangled Swirling Noodle Strands
        ctx.strokeStyle = "#ca8a04";
        ctx.lineWidth = 2;
        for (let i = 0; i < 8 * remainingPct; i++) {
          const ang = (i * Math.PI) / 4;
          ctx.beginPath();
          ctx.ellipse(cx + Math.cos(ang) * 15, cy + Math.sin(ang) * 10, pastaRadius * 0.6, pastaRadius * 0.35, ang, 0, Math.PI * 2);
          ctx.stroke();
        }

        // Rich Marinara Sauce Splash
        ctx.fillStyle = "rgba(220, 38, 38, 0.9)";
        ctx.beginPath();
        ctx.arc(cx, cy - 4, pastaRadius * 0.65, 0, Math.PI * 2);
        ctx.fill();

        // Savory Meatballs (3 meatballs disappear as questions are solved)
        const meatballCount = Math.ceil(3 * remainingPct);
        const mbOffsets = [
          { x: -14, y: -10 },
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

        // Fresh Basil Garnish Leaf
        if (remainingPct > 0.3) {
          ctx.fillStyle = "#16a34a";
          ctx.beginPath();
          ctx.ellipse(cx + 2, cy - 14, 8, 4, Math.PI / 4, 0, Math.PI * 2);
          ctx.fill();
        }
      } else {
        // Clean Empty Plate with leftover sauce streaks!
        ctx.strokeStyle = "rgba(220, 38, 38, 0.35)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(cx - 20, cy - 10);
        ctx.bezierCurveTo(cx - 5, cy + 15, cx + 15, cy - 5, cx + 25, cy + 10);
        ctx.stroke();

        ctx.fillStyle = "#16a34a";
        ctx.font = "bold 16px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("⭐ Clean Plate! Molto Bene! ⭐", cx, cy);
      }

      ctx.restore();
    } else if (this.theme.id === "dinosaurs") {
      // ==========================================
      // MAYA'S JURASSIC FOSSIL DIG SITE
      // ==========================================
      ctx.save();
      ctx.fillStyle = "#291807";
      ctx.strokeStyle = "#f59e0b";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(cx, cy, 75, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Unearthed T-Rex Skeleton Segments
      const unearthedBones = Math.min(10, this.answeredCount);
      ctx.fillStyle = "#fef08a";
      ctx.shadowColor = "#f59e0b";
      ctx.shadowBlur = 10;

      // 1. Skull
      if (unearthedBones >= 1) {
        ctx.beginPath();
        ctx.ellipse(cx, cy - 25, 22, 14, 0, 0, Math.PI * 2);
        ctx.fill();
      }
      // 2. Spine & Ribs
      if (unearthedBones >= 3) {
        ctx.fillRect(cx - 4, cy - 10, 8, 35);
        for (let r = 0; r < 4; r++) {
          ctx.fillRect(cx - 16, cy - 5 + r * 8, 32, 3);
        }
      }
      // 3. Tail & Claws
      if (unearthedBones >= 6) {
        ctx.beginPath();
        ctx.moveTo(cx, cy + 25);
        ctx.lineTo(cx + 25, cy + 45);
        ctx.lineTo(cx + 35, cy + 42);
        ctx.stroke();
      }

      ctx.shadowBlur = 0;
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.font = "bold 15px monospace";
      ctx.fillText(`${unearthedBones}/10 BONES`, cx, cy + 60);
      ctx.restore();
    } else {
      // Cosmic Orbit Docking Hub
      ctx.save();
      const glow = Math.sin(this.centerpiece.pulsePhase) * 4 + 8;
      ctx.shadowColor = this.theme.accentColor;
      ctx.shadowBlur = glow;
      ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
      ctx.strokeStyle = this.centerpiece.docked ? "#4ade80" : this.theme.accentColor;
      ctx.lineWidth = 3;

      ctx.beginPath();
      ctx.arc(cx, cy, this.centerpiece.radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      ctx.shadowBlur = 0;
      ctx.fillStyle = "#ffffff";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = "bold 18px monospace";
      ctx.fillText(this.centerpiece.docked ? "✦ DOCKED" : this.theme.targetLabel, cx, cy);
      ctx.restore();
    }
  }

  private renderPlayerActor(ctx: CanvasRenderingContext2D): void {
    ctx.save();
    ctx.translate(this.player.x, this.player.y + Math.sin(this.player.idlePhase) * 2);
    ctx.rotate(this.player.angle + Math.PI / 2 + this.player.twirlAngle);

    if (this.theme.id === "cooking") {
      // ==========================================
      // STAINLESS STEEL FORK WITH TWIRLING NOODLES
      // ==========================================
      // Fork Handle
      ctx.fillStyle = "#94a3b8";
      ctx.strokeStyle = "#475569";
      ctx.lineWidth = 1.5;
      ctx.fillRect(-3, 8, 6, 36);

      // Fork Neck & Base
      ctx.fillStyle = "#cbd5e1";
      ctx.beginPath();
      ctx.moveTo(-10, 8);
      ctx.lineTo(10, 8);
      ctx.lineTo(6, -6);
      ctx.lineTo(-6, -6);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      // 4 Fork Tines
      ctx.fillStyle = "#f8fafc";
      for (let i = 0; i < 4; i++) {
        const xOffset = -8 + i * 5;
        ctx.fillRect(xOffset, -24, 2.5, 18);
      }

      // Twirled Spaghetti on Fork if Submitting
      if (this.state === "SUBMITTING") {
        ctx.fillStyle = "#facc15";
        ctx.beginPath();
        ctx.arc(0, -16, 12, 0, Math.PI * 2);
        ctx.fill();
      }
    } else if (this.theme.id === "dinosaurs") {
      // Archeological Field Brush
      ctx.fillStyle = "#78350f";
      ctx.fillRect(-4, 0, 8, 30);
      ctx.fillStyle = "#d97706";
      ctx.fillRect(-8, -12, 16, 12);
      ctx.fillStyle = "#fef3c7";
      ctx.fillRect(-10, -26, 20, 14);
    } else if (this.theme.id === "tennis") {
      // Tennis Racket
      ctx.strokeStyle = "#4ade80";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.ellipse(0, -12, 14, 18, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fillStyle = "#78350f";
      ctx.fillRect(-3, 6, 6, 24);
    } else {
      // Vector Starship
      ctx.fillStyle = this.theme.playerColor;
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 2;
      ctx.shadowColor = this.theme.accentColor;
      ctx.shadowBlur = 10;

      ctx.beginPath();
      ctx.moveTo(0, -this.player.size);
      ctx.lineTo(this.player.size * 0.75, this.player.size);
      ctx.lineTo(0, this.player.size * 0.5);
      ctx.lineTo(-this.player.size * 0.75, this.player.size);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = "#ffffff";
      ctx.beginPath();
      ctx.arc(0, -this.player.size * 0.25, 4, 0, Math.PI * 2);
      ctx.fill();
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

    // Feedback Overlay
    if (this.feedbackMessage) {
      ctx.fillStyle = this.feedbackIsGentle ? "#fbbf24" : "#4ade80";
      ctx.font = "bold 16px 'Inter', system-ui, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(this.feedbackMessage, w / 2, bannerY + bannerH + 28);
    }

    ctx.restore();
  }

  private bindEvents(): void {
    this.canvas.addEventListener("pointerdown", (e) => {
      const rect = this.canvas.getBoundingClientRect();
      const scaleX = this.canvas.width / rect.width;
      const scaleY = this.canvas.height / rect.height;
      this.targetX = (e.clientX - rect.left) * scaleX;
      this.targetY = (e.clientY - rect.top) * scaleY;
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
