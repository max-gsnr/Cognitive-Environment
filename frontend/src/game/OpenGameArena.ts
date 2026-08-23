/**
 * OpenGame Space Arena Engine (Engineered for Leo - Age 7, Space & Trains)
 *
 * Implements OpenGame 5-Phase Architecture:
 * - Phase 1: Dual-Knowledge GDD (Top-Down Cosmic Arena)
 * - Phase 2: Configuration & 4-Scene Lifecycle Stack (Preloader, Title, Game+UI, Victory)
 * - Phase 3: Game Juice Engine (ScreenEffectHelper, ParticleSystem, Web Audio Synth)
 * - Phase 4: Frictionless Click/Tap Navigation & Freeform Math Production
 * - Phase 5: Verification & Orbit Backend Loop A Integration
 */

import { AttemptResult, Question, api } from "../api";
import { capture } from "../telemetry";
import { ParticleSystem } from "./ParticleSystem";
import { soundFx } from "./SoundFx";

export interface GameTheme {
  name: string;
  targetLabel: string;
  playerLabel: string;
  bgColor: string;
  gridColor: string;
  accentColor: string;
  playerColor: string;
  starColors: string[];
  laserColor: string;
}

export const THEMES: Record<string, GameTheme> = {
  nebula: {
    name: "🌌 Deep Space Nebula",
    targetLabel: "✦ DOCK HUB",
    playerLabel: "Starship",
    bgColor: "#070b14",
    gridColor: "rgba(56, 189, 248, 0.06)",
    accentColor: "#38bdf8",
    playerColor: "#60a5fa",
    starColors: ["#ffffff", "#93c5fd", "#c084fc", "#38bdf8"],
    laserColor: "#38bdf8",
  },
  dinosaurs: {
    name: "🦕 Jurassic Fossil Quest",
    targetLabel: "🦴 FOSSIL DOME",
    playerLabel: "Dig Rover",
    bgColor: "#141009",
    gridColor: "rgba(251, 191, 36, 0.08)",
    accentColor: "#f59e0b",
    playerColor: "#10b981",
    starColors: ["#fef3c7", "#fde68a", "#d97706", "#6ee7b7"],
    laserColor: "#f59e0b",
  },
  cooking: {
    name: "🍝 Chef Kitchen Quest",
    targetLabel: "🍕 OVEN STATION",
    playerLabel: "Chef Cart",
    bgColor: "#1a0e0e",
    gridColor: "rgba(239, 68, 68, 0.08)",
    accentColor: "#ef4444",
    playerColor: "#f97316",
    starColors: ["#fff1f2", "#fecdd3", "#fb7185", "#fde047"],
    laserColor: "#ef4444",
  },
  tennis: {
    name: "🎾 Grand Slam Tennis",
    targetLabel: "🏆 COURT NET",
    playerLabel: "Tennis Racket",
    bgColor: "#061a12",
    gridColor: "rgba(74, 222, 128, 0.08)",
    accentColor: "#4ade80",
    playerColor: "#a3e635",
    starColors: ["#f0fdf4", "#bbf7d0", "#86efac", "#facc15"],
    laserColor: "#4ade80",
  },
  horses: {
    name: "🐴 Equestrian Meadow",
    targetLabel: "🏇 STABLE GATE",
    playerLabel: "Horseshoe Rider",
    bgColor: "#0c170f",
    gridColor: "rgba(132, 204, 22, 0.08)",
    accentColor: "#84cc16",
    playerColor: "#eab308",
    starColors: ["#f7fee7", "#ecfccb", "#bef264", "#fef08a"],
    laserColor: "#84cc16",
  },
  trains: {
    name: "🚂 Steam Locomotive",
    targetLabel: "🚉 TRAIN DEPOT",
    playerLabel: "Steam Engine",
    bgColor: "#0b1320",
    gridColor: "rgba(148, 163, 184, 0.08)",
    accentColor: "#38bdf8",
    playerColor: "#f59e0b",
    starColors: ["#f8fafc", "#e2e8f0", "#94a3b8", "#38bdf8"],
    laserColor: "#38bdf8",
  },
  aurora: {
    name: "✨ Solar Flare Aurora",
    targetLabel: "✦ SOLAR DOCK",
    playerLabel: "Solar Glider",
    bgColor: "#09121d",
    gridColor: "rgba(251, 191, 36, 0.06)",
    accentColor: "#fbbf24",
    playerColor: "#38bdf8",
    starColors: ["#ffffff", "#fde047", "#67e8f9", "#fbbf24"],
    laserColor: "#fbbf24",
  },
};

export function getThemeForInterests(interests: string[] = []): GameTheme {
  const combined = interests.join(" ").toLowerCase();
  if (combined.includes("dinosaur") || combined.includes("fossil") || combined.includes("paleontol")) {
    return THEMES.dinosaurs;
  }
  if (combined.includes("spaghetti") || combined.includes("cook") || combined.includes("food") || combined.includes("baking") || combined.includes("pizza")) {
    return THEMES.cooking;
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

  // Parallax Starfield & Visuals
  private particles: ParticleSystem;
  private stars: Array<{ x: number; y: number; size: number; speed: number; color: string; alpha: number }> = [];

  // Player Spacecraft (Leo's Starship)
  private player = {
    x: 400,
    y: 380,
    vx: 0,
    vy: 0,
    angle: -Math.PI / 2,
    targetAngle: -Math.PI / 2,
    speed: 6.0,
    size: 24,
    idlePhase: 0,
  };

  // Orbital Docking Hub & Laser Beams
  private dockingHub: Station = {
    id: "central-dock",
    x: 400,
    y: 180,
    radius: 46,
    pulsePhase: 0,
    docked: false,
  };
  private laserBeams: LaserBeam[] = [];

  // Controls & Interaction
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

    this.initStars();
    this.bindEvents();
    this.resizeCanvas();
  }

  public setTheme(themeKey: string): void {
    this.theme = THEMES[themeKey] || THEMES.nebula;
    this.initStars();
  }

  public setAudio(enabled: boolean): void {
    this.soundEnabled = enabled;
    soundFx.enabled = enabled;
  }

  private initStars(): void {
    this.stars = [];
    const width = this.canvas.width || 800;
    const height = this.canvas.height || 600;
    const count = 140;
    for (let i = 0; i < count; i++) {
      this.stars.push({
        x: Math.random() * width,
        y: Math.random() * height,
        size: Math.random() * 2.4 + 0.6,
        speed: Math.random() * 0.9 + 0.3,
        color: this.theme.starColors[Math.floor(Math.random() * this.theme.starColors.length)],
        alpha: Math.random() * 0.85 + 0.15,
      });
    }
  }

  private resizeCanvas(): void {
    const rect = this.canvas.parentElement?.getBoundingClientRect();
    if (rect && rect.width > 0) {
      this.canvas.width = Math.floor(rect.width);
      this.canvas.height = Math.min(620, Math.floor(window.innerHeight * 0.7));
      this.player.x = this.canvas.width / 2;
      this.player.y = this.canvas.height - 110;
      this.dockingHub.x = this.canvas.width / 2;
      this.dockingHub.y = 175;
      this.initStars();
    }
  }

  private bindEvents(): void {
    this.canvas.addEventListener("pointerdown", this.handlePointerDown);
    this.canvas.addEventListener("pointermove", this.handlePointerMove);
    window.addEventListener("resize", () => this.resizeCanvas());
  }

  public destroy(): void {
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
    }
    this.canvas.removeEventListener("pointerdown", this.handlePointerDown);
    this.canvas.removeEventListener("pointermove", this.handlePointerMove);
  }

  private handlePointerDown = (e: PointerEvent): void => {
    const rect = this.canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (this.state === "TITLE" || this.state === "VICTORY") {
      soundFx.blip(600);
      this.startGame();
      return;
    }

    if (this.state === "PLAYING") {
      this.targetX = x;
      this.targetY = y;
      // Pulse emission toward destination
      this.particles.emitThruster(this.player.x, this.player.y, this.player.angle, this.theme.accentColor);
    }
  };

  private handlePointerMove = (e: PointerEvent): void => {
    if (this.state === "PLAYING" && (e.buttons === 1 || e.pointerType === "touch")) {
      const rect = this.canvas.getBoundingClientRect();
      this.targetX = e.clientX - rect.left;
      this.targetY = e.clientY - rect.top;
    }
  };

  public async startGame(): Promise<void> {
    this.state = "PLAYING";
    this.score = 0;
    this.answeredCount = 0;
    this.feedbackMessage = "";
    this.laserBeams = [];
    this.player.x = this.canvas.width / 2;
    this.player.y = this.canvas.height - 110;
    this.player.vx = 0;
    this.player.vy = 0;

    capture("level_started", { profile_id: this.profileId, skill_id: this.skillId });
    await this.loadNextQuestion();
  }

  public async loadNextQuestion(): Promise<void> {
    try {
      this.feedbackMessage = "";
      this.dockingHub.docked = false;
      const q = await api.get<Question>(
        `/profiles/${this.profileId}/skills/${this.skillId}/next-question`
      );
      this.currentQuestion = q;
      this.shownAt = performance.now();

      if (this.callbacks.onQuestionLoaded) {
        this.callbacks.onQuestionLoaded(q);
      }

      capture("problem_shown", {
        profile_id: this.profileId,
        skill_id: this.skillId,
        operands: q.operands,
        operator: q.operator,
        difficulty_vector: q.difficulty_vector_snapshot,
      });
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to load docking coordinates";
      this.feedbackMessage = msg;
      if (this.callbacks.onError) this.callbacks.onError(msg);
    }
  }

  /**
   * Submit an answer freely produced by the child
   */
  public async submitAnswer(value: number): Promise<void> {
    if (this.state !== "PLAYING" || !this.currentQuestion) return;

    this.state = "SUBMITTING";
    const latency = Math.max(100, Math.round(performance.now() - this.shownAt));
    const targetX = this.dockingHub.x;
    const targetY = this.dockingHub.y;

    // Fire Ion Quantum Docking Beam toward target hub
    this.laserBeams.push({
      startX: this.player.x,
      startY: this.player.y,
      endX: targetX,
      endY: targetY,
      alpha: 1.0,
    });
    soundFx.laser();

    try {
      const result = await api.post<AttemptResult>("/attempts", {
        profile_id: this.profileId,
        skill_id: this.skillId,
        operands: this.currentQuestion.operands,
        operator: this.currentQuestion.operator,
        answer_given: value,
        latency_to_submit_ms: latency,
      });

      capture("answer_submitted", {
        profile_id: this.profileId,
        skill_id: this.skillId,
        is_correct: result.is_correct,
        error_class: result.error_class,
        latency_to_submit_ms: latency,
      });

      if (this.callbacks.onAttemptResult) {
        this.callbacks.onAttemptResult(result);
      }

      if (result.is_correct) {
        const pts = 100;
        this.score += pts;
        this.answeredCount += 1;
        this.dockingHub.docked = true;

        soundFx.dockSuccess();
        this.particles.emitDockCelebration(targetX, targetY);
        this.particles.shake(200, 3);
        this.particles.addFloatingText(targetX, targetY - 25, `✦ DOCKED! +${pts} PTS!`, "#38bdf8");
        this.feedbackMessage = "✦ Star Pod Docked Successfully!";
        this.feedbackIsGentle = false;

        if (this.callbacks.onScoreUpdate) {
          this.callbacks.onScoreUpdate(this.score, this.answeredCount);
        }

        if (this.answeredCount >= this.sessionLength) {
          setTimeout(() => this.finishLevel(), 1000);
          return;
        }

        setTimeout(() => {
          this.state = "PLAYING";
          this.loadNextQuestion();
        }, 900);
      } else {
        soundFx.gentleRetry();
        this.particles.emitExplosion(targetX, targetY, "#fbbf24", 14);
        this.particles.addFloatingText(
          targetX,
          targetY - 25,
          `Coordinates were ${this.currentQuestion.correct_answer}`,
          "#fbbf24"
        );
        this.feedbackMessage = `Almost, Leo — the answer was ${this.currentQuestion.correct_answer}. Next star pod incoming!`;
        this.feedbackIsGentle = true;

        if (this.callbacks.onScoreUpdate) {
          this.callbacks.onScoreUpdate(this.score, this.answeredCount);
        }

        setTimeout(() => {
          this.state = "PLAYING";
          this.loadNextQuestion();
        }, 1200);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Error submitting coordinates";
      this.feedbackMessage = msg;
      this.state = "PLAYING";
      if (this.callbacks.onError) this.callbacks.onError(msg);
    }
  }

  private finishLevel(): void {
    this.state = "VICTORY";
    soundFx.levelComplete();
    this.particles.emitDockCelebration(this.canvas.width / 2, this.canvas.height / 2);
    capture("level_completed", {
      profile_id: this.profileId,
      skill_id: this.skillId,
      final_score: this.score,
      answered: this.answeredCount,
    });
    if (this.callbacks.onLevelComplete) {
      this.callbacks.onLevelComplete();
    }
  }

  public startLoop(): void {
    this.lastTime = performance.now();
    const loop = (timestamp: number) => {
      const deltaMs = Math.min(100, timestamp - this.lastTime);
      this.lastTime = timestamp;

      this.update(deltaMs);
      this.render();

      this.animFrameId = requestAnimationFrame(loop);
    };
    this.animFrameId = requestAnimationFrame(loop);
  }

  private update(deltaMs: number): void {
    // 1. Parallax Starfield update
    for (const star of this.stars) {
      star.y += star.speed;
      if (star.y > this.canvas.height) {
        star.y = 0;
        star.x = Math.random() * this.canvas.width;
      }
    }

    // 2. Laser beams decay
    for (let i = this.laserBeams.length - 1; i >= 0; i--) {
      this.laserBeams[i].alpha -= 0.06;
      if (this.laserBeams[i].alpha <= 0) {
        this.laserBeams.splice(i, 1);
      }
    }

    if (this.state === "PLAYING" || this.state === "SUBMITTING") {
      this.player.idlePhase += 0.04;

      // Mouse / Touch Steering (Click to Glide)
      let moveX = 0;
      let moveY = 0;

      if (this.targetX !== null && this.targetY !== null) {
        const dx = this.targetX - this.player.x;
        const dy = this.targetY - this.player.y;
        const dist = Math.hypot(dx, dy);
        if (dist > 15) {
          moveX = dx / dist;
          moveY = dy / dist;
        } else {
          this.targetX = null;
          this.targetY = null;
        }
      }

      if (moveX !== 0 || moveY !== 0) {
        const len = Math.hypot(moveX, moveY);
        const normX = moveX / len;
        const normY = moveY / len;

        this.player.vx += normX * 0.48;
        this.player.vy += normY * 0.48;
        this.player.targetAngle = Math.atan2(normY, normX);

        if (this.particleIntensity !== "low" && Math.random() > 0.3) {
          this.particles.emitThruster(this.player.x, this.player.y, this.player.angle, this.theme.accentColor);
        }
      }

      // Smooth inertia damping
      this.player.vx *= 0.92;
      this.player.vy *= 0.92;
      this.player.x += this.player.vx * this.player.speed;
      this.player.y += this.player.vy * this.player.speed;

      // Angle interpolation
      let angleDiff = this.player.targetAngle - this.player.angle;
      while (angleDiff < -Math.PI) angleDiff += Math.PI * 2;
      while (angleDiff > Math.PI) angleDiff -= Math.PI * 2;
      this.player.angle += angleDiff * 0.2;

      // Boundary clamp
      const pad = 36;
      this.player.x = Math.max(pad, Math.min(this.canvas.width - pad, this.player.x));
      this.player.y = Math.max(this.canvas.height / 2 + 10, Math.min(this.canvas.height - pad, this.player.y));

      // Docking hub pulse
      this.dockingHub.pulsePhase += 0.05;
    }

    // 3. Update Particles
    this.particles.update(deltaMs);
  }

  private render(): void {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;

    ctx.save();

    // Screen Shake Offset
    if (this.particles.shakeDuration > 0) {
      const intensity = this.particles.shakeIntensity;
      const offsetX = (Math.random() - 0.5) * intensity * 2;
      const offsetY = (Math.random() - 0.5) * intensity * 2;
      ctx.translate(offsetX, offsetY);
    }

    // 1. Deep Space Environment
    this.renderSpaceEnvironment(ctx, w, h);

    if (this.state === "TITLE") {
      this.renderTitleScreen();
    } else if (this.state === "PLAYING" || this.state === "SUBMITTING") {
      this.renderGameplay();
    } else if (this.state === "VICTORY") {
      this.renderVictoryScreen();
    }

    // Render Particle Systems & Floating Popups
    this.particles.render(ctx);

    ctx.restore();
  }

  private renderSpaceEnvironment(ctx: CanvasRenderingContext2D, w: number, h: number): void {
    // Deep Void
    ctx.fillStyle = this.theme.bgColor;
    ctx.fillRect(0, 0, w, h);

    // Orbital Coordinates Grid Lines
    ctx.strokeStyle = this.theme.gridColor;
    ctx.lineWidth = 1;
    const gridSize = 60;
    for (let x = 0; x < w; x += gridSize) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    for (let y = 0; y < h; y += gridSize) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Parallax Stars
    for (const star of this.stars) {
      ctx.fillStyle = star.color;
      ctx.globalAlpha = star.alpha;
      ctx.beginPath();
      ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1.0;

    // Leo's Space Station Badge in Corner
    ctx.save();
    ctx.font = "14px 'Inter', system-ui, sans-serif";
    ctx.fillStyle = "rgba(255, 255, 255, 0.35)";
    ctx.textAlign = "left";
    ctx.fillText("🚀 Leo's Star Docking Station", 24, h - 20);
    ctx.restore();
  }

  private renderGameplay(): void {
    const ctx = this.ctx;

    // 1. Orbital Ring Guide
    ctx.save();
    ctx.strokeStyle = "rgba(56, 189, 248, 0.12)";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([8, 8]);
    ctx.beginPath();
    ctx.arc(this.dockingHub.x, this.dockingHub.y, 110, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();

    // 2. Central Orbital Docking Station
    ctx.save();
    const glow = Math.sin(this.dockingHub.pulsePhase) * 4 + 8;
    ctx.shadowColor = this.theme.accentColor;
    ctx.shadowBlur = glow;
    ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
    ctx.strokeStyle = this.dockingHub.docked ? "#4ade80" : this.theme.accentColor;
    ctx.lineWidth = 3;

    ctx.beginPath();
    ctx.arc(this.dockingHub.x, this.dockingHub.y, this.dockingHub.radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();

    // Docking Portal Rings
    ctx.strokeStyle = "rgba(255, 255, 255, 0.25)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.arc(this.dockingHub.x, this.dockingHub.y, this.dockingHub.radius + 8, 0, Math.PI * 2);
    ctx.stroke();

    // Hub Icon / Status
    ctx.shadowBlur = 0;
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = "bold 20px 'Inter', system-ui, sans-serif";
    ctx.fillText(this.dockingHub.docked ? "✦ DOCKED" : "✦ DOCK", this.dockingHub.x, this.dockingHub.y);
    ctx.restore();

    // 3. Ion Laser Beams
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

    // 4. Leo's Starship (Player Vector Sprite)
    ctx.save();
    ctx.translate(this.player.x, this.player.y + Math.sin(this.player.idlePhase) * 2);
    ctx.rotate(this.player.angle + Math.PI / 2);

    // Ship Hull
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

    // Cockpit Glow
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(0, -this.player.size * 0.25, 4, 0, Math.PI * 2);
    ctx.fill();

    // Wing Cannons
    ctx.fillStyle = this.theme.accentColor;
    ctx.fillRect(-this.player.size * 0.8, 0, 3, 10);
    ctx.fillRect(this.player.size * 0.8 - 3, 0, 3, 10);

    ctx.restore();

    // 5. Single Focal Point HUD
    this.renderHUD();
  }

  private renderHUD(): void {
    const ctx = this.ctx;
    const w = this.canvas.width;

    // Top Math Problem Banner (Single Focal Point)
    ctx.save();
    ctx.fillStyle = "rgba(15, 23, 42, 0.9)";
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
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.font = "bold 26px 'Inter', system-ui, monospace";
      ctx.fillStyle = "#38bdf8";
      ctx.fillText(`✦  ${a} ${op} ${b} = ?`, w / 2, bannerY + bannerH / 2);
    }

    // Score & Missions Indicators
    ctx.font = "bold 14px 'Inter', system-ui, sans-serif";
    ctx.textAlign = "left";
    ctx.fillStyle = "#cbd5e1";
    ctx.fillText(`Orbit Score: ${this.score}`, 20, 36);

    ctx.textAlign = "right";
    ctx.fillStyle = "#cbd5e1";
    ctx.fillText(`Missions: ${this.answeredCount} / ${this.sessionLength}`, w - 20, 36);

    // Feedback Banner
    if (this.feedbackMessage) {
      ctx.textAlign = "center";
      ctx.font = "15px 'Inter', system-ui, sans-serif";
      ctx.fillStyle = this.feedbackIsGentle ? "#fde047" : "#4ade80";
      ctx.fillText(this.feedbackMessage, w / 2, bannerY + bannerH + 24);
    }

    ctx.restore();
  }

  private renderTitleScreen(): void {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;

    ctx.save();
    ctx.textAlign = "center";

    // Title
    ctx.font = "bold 38px 'Inter', system-ui, sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.shadowColor = this.theme.accentColor;
    ctx.shadowBlur = 18;
    ctx.fillText("✦ LEO'S COSMIC DOCKING ODYSSEY ✦", w / 2, h / 2 - 70);

    // Subtitle
    ctx.shadowBlur = 0;
    ctx.font = "16px 'Inter', system-ui, sans-serif";
    ctx.fillStyle = "#cbd5e1";
    ctx.fillText(`Skill: ${this.skillId.toUpperCase()} • Type answer & click to steer starship!`, w / 2, h / 2 - 25);

    // Start Button
    const btnW = 240;
    const btnH = 52;
    const btnX = (w - btnW) / 2;
    const btnY = h / 2 + 30;

    ctx.fillStyle = this.theme.accentColor;
    ctx.beginPath();
    ctx.roundRect(btnX, btnY, btnW, btnH, 10);
    ctx.fill();

    ctx.fillStyle = "#070b14";
    ctx.font = "bold 18px 'Inter', system-ui, sans-serif";
    ctx.textBaseline = "middle";
    ctx.fillText("LAUNCH MISSION (CLICK)", w / 2, btnY + btnH / 2);

    // Controls hint
    ctx.font = "13px 'Inter', system-ui, sans-serif";
    ctx.fillStyle = "#94a3b8";
    ctx.fillText("Controls: Click / Tap to Glide Starship • Type Math Coordinates to Dock", w / 2, h / 2 + 120);

    ctx.restore();
  }

  private renderVictoryScreen(): void {
    const ctx = this.ctx;
    const w = this.canvas.width;
    const h = this.canvas.height;

    ctx.save();
    ctx.textAlign = "center";

    // Crown / Badge
    ctx.font = "bold 36px 'Inter', system-ui, sans-serif";
    ctx.fillStyle = "#fbbf24";
    ctx.shadowColor = "#f59e0b";
    ctx.shadowBlur = 20;
    ctx.fillText("🏆 ALL STAR PODS DOCKED! 🏆", w / 2, h / 2 - 80);

    ctx.shadowBlur = 0;
    ctx.font = "18px 'Inter', system-ui, sans-serif";
    ctx.fillStyle = "#ffffff";
    ctx.fillText(`Final Orbit Score: ${this.score} pts • Missions Mastered: ${this.answeredCount}`, w / 2, h / 2 - 30);

    // Play Again Button
    const btnW = 220;
    const btnH = 50;
    const btnX = (w - btnW) / 2;
    const btnY = h / 2 + 30;

    ctx.fillStyle = "#4ade80";
    ctx.beginPath();
    ctx.roundRect(btnX, btnY, btnW, btnH, 10);
    ctx.fill();

    ctx.fillStyle = "#064e3b";
    ctx.font = "bold 17px 'Inter', system-ui, sans-serif";
    ctx.textBaseline = "middle";
    ctx.fillText("NEXT STAR SYSTEM", w / 2, btnY + btnH / 2);

    ctx.restore();
  }
}
