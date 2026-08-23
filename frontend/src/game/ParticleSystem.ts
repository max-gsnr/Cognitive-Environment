/**
 * Particle and Visual FX Engine
 * Based on OpenGame's ScreenEffectHelper and visual particle presets.
 */

export interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  size: number;
  color: string;
  alpha: number;
  life: number;
  maxLife: number;
}

export interface FloatingText {
  x: number;
  y: number;
  text: string;
  color: string;
  alpha: number;
  life: number;
  maxLife: number;
  scale: number;
}

export class ParticleSystem {
  public particles: Particle[] = [];
  public floatingTexts: FloatingText[] = [];
  public shakeDuration: number = 0;
  public shakeIntensity: number = 0;

  /**
   * Trigger screen shake
   */
  shake(durationMs: number = 200, intensity: number = 5): void {
    this.shakeDuration = durationMs;
    this.shakeIntensity = intensity;
  }

  /**
   * Emit thruster particles behind player ship
   */
  emitThruster(x: number, y: number, angle: number, color: string = "#38bdf8"): void {
    const spread = (Math.random() - 0.5) * 0.4;
    const speed = 2 + Math.random() * 3;
    const pAngle = angle + Math.PI + spread;

    this.particles.push({
      x: x + Math.cos(pAngle) * 15,
      y: y + Math.sin(pAngle) * 15,
      vx: Math.cos(pAngle) * speed,
      vy: Math.sin(pAngle) * speed,
      size: 3 + Math.random() * 4,
      color,
      alpha: 0.9,
      life: 0,
      maxLife: 20 + Math.random() * 15,
    });
  }

  /**
   * Emit explosion / laser hit particles
   */
  emitExplosion(x: number, y: number, color: string = "#f59e0b", count: number = 24): void {
    for (let i = 0; i < count; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = 1.5 + Math.random() * 5;
      this.particles.push({
        x,
        y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        size: 3 + Math.random() * 5,
        color,
        alpha: 1,
        life: 0,
        maxLife: 30 + Math.random() * 25,
      });
    }
  }

  /**
   * Docking celebration burst with sparkles
   */
  emitDockCelebration(x: number, y: number): void {
    const colors = ["#4ade80", "#38bdf8", "#fbbf24", "#a855f7"];
    for (let i = 0; i < 40; i++) {
      const angle = (i / 40) * Math.PI * 2 + Math.random() * 0.2;
      const speed = 2 + Math.random() * 4;
      this.particles.push({
        x,
        y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        size: 4 + Math.random() * 4,
        color: colors[i % colors.length],
        alpha: 1,
        life: 0,
        maxLife: 45 + Math.random() * 20,
      });
    }
  }

  /**
   * Add floating popup text (e.g. "+100", "Docked!", "24 + 38 = 62")
   */
  addFloatingText(x: number, y: number, text: string, color: string = "#4ade80"): void {
    this.floatingTexts.push({
      x,
      y,
      text,
      color,
      alpha: 1,
      life: 0,
      maxLife: 60,
      scale: 1.2,
    });
  }

  /**
   * Update particle lifecycle
   */
  update(deltaMs: number): void {
    if (this.shakeDuration > 0) {
      this.shakeDuration -= deltaMs;
      if (this.shakeDuration < 0) this.shakeDuration = 0;
    }

    for (let i = this.particles.length - 1; i >= 0; i--) {
      const p = this.particles[i];
      p.x += p.vx;
      p.y += p.vy;
      p.life++;
      p.alpha = Math.max(0, 1 - p.life / p.maxLife);
      p.size = Math.max(0.5, p.size * 0.96);

      if (p.life >= p.maxLife) {
        this.particles.splice(i, 1);
      }
    }

    for (let i = this.floatingTexts.length - 1; i >= 0; i--) {
      const ft = this.floatingTexts[i];
      ft.y -= 0.8;
      ft.life++;
      ft.alpha = Math.max(0, 1 - ft.life / ft.maxLife);
      ft.scale = Math.max(1.0, ft.scale * 0.98);

      if (ft.life >= ft.maxLife) {
        this.floatingTexts.splice(i, 1);
      }
    }
  }

  /**
   * Render all particles and floating text to canvas
   */
  render(ctx: CanvasRenderingContext2D): void {
    // Render particles
    ctx.save();
    for (const p of this.particles) {
      ctx.globalAlpha = p.alpha;
      ctx.fillStyle = p.color;
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();

    // Render floating texts
    ctx.save();
    ctx.textAlign = "center";
    ctx.font = "bold 18px 'Inter', system-ui, sans-serif";
    for (const ft of this.floatingTexts) {
      ctx.globalAlpha = ft.alpha;
      ctx.fillStyle = ft.color;
      ctx.shadowColor = "#000000";
      ctx.shadowBlur = 8;
      ctx.fillText(ft.text, ft.x, ft.y);
    }
    ctx.restore();
  }
}
