/**
 * Hand-rolled SVG chart primitives, shared by the Session Monitor and Release
 * Impact views. No charting dependency: the shapes needed here are few, and
 * owning them is what makes the accessibility rules below enforceable.
 *
 * Three rules run through all of them, because the audience is a teacher
 * watching a child with ADHD rather than an analyst:
 *
 *   1. Never colour alone. Every state also has a shape or a label, so the
 *      charts survive colour blindness and a projector's washed-out gamut.
 *   2. Familiar forms only --- band, line, bar, funnel. Novel visualisations
 *      test worse than plain ones, and a chart that needs a lesson is a chart
 *      that will be misread on stage.
 *   3. Motion is opt-out and never load-bearing; nothing animates that a reader
 *      has to watch to understand, and prefers-reduced-motion removes it.
 */
import { ReactNode, useState } from "react";

type FigureProps = {
  title: string;
  /** The plain-English reason this chart is on the page at all. */
  why: string;
  /** What a screen reader (or a sceptical judge) gets instead of the picture. */
  summary: string;
  children: ReactNode;
  legend?: ReactNode;
};

export function Figure({ title, why, summary, children, legend }: FigureProps) {
  const [showData, setShowData] = useState(false);
  return (
    <figure className="chart">
      <div className="chart-head">
        <h3>{title}</h3>
        <button
          type="button"
          className="chart-alt"
          aria-expanded={showData}
          onClick={() => setShowData((on) => !on)}
        >
          {showData ? "Hide numbers" : "Read as text"}
        </button>
      </div>
      <p className="chart-why">{why}</p>
      {children}
      {legend && <div className="chart-legend">{legend}</div>}
      {showData && <p className="chart-summary">{summary}</p>}
      <figcaption className="visually-hidden">{summary}</figcaption>
    </figure>
  );
}

export function Legend({ items }: { items: { mark: ReactNode; label: string }[] }) {
  return (
    <>
      {items.map((item) => (
        <span key={item.label} className="legend-item">
          {item.mark}
          {item.label}
        </span>
      ))}
    </>
  );
}

type StatProps = {
  label: string;
  value: string;
  /** What the number means, in words, so the tile is readable without training. */
  note?: string;
  tone?: "good" | "watch" | "neutral";
};

export function Stat({ label, value, note, tone = "neutral" }: StatProps) {
  return (
    <div className={`stat stat-${tone}`}>
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      {note && <span className="stat-note">{note}</span>}
    </div>
  );
}

export type BandPoint = {
  index: number;
  value: number;
  inBand: boolean;
  correct: boolean;
  label: string;
  marker?: "rest" | "fluency";
};

type BandChartProps = {
  points: BandPoint[];
  low: number;
  high: number;
  onSelect?: (index: number) => void;
  selected?: number | null;
};

/**
 * The chart the whole system is judged by: one dot per question, a shaded
 * target band, and the question of whether the dots sit inside it.
 *
 * The y-axis is Loop A's own expected success rate, not the score --- so this is
 * a claim about whether the difficulty was right, which a score cannot make.
 */
export function BandChart({ points, low, high, onSelect, selected }: BandChartProps) {
  const W = 640;
  const H = 220;
  const pad = { top: 16, right: 16, bottom: 28, left: 40 };
  const plot = { w: W - pad.left - pad.right, h: H - pad.top - pad.bottom };
  const yFor = (value: number) => pad.top + plot.h * (1 - clamp(value));
  const xFor = (i: number) =>
    pad.left + (points.length < 2 ? plot.w / 2 : (plot.w * i) / (points.length - 1));

  const path = points
    .map((point, i) => `${i ? "L" : "M"}${xFor(i)},${yFor(point.value)}`)
    .join(" ");

  return (
    <svg
      className="chart-svg"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Challenge fit: expected success rate per question against the target band"
    >
      <rect
        x={pad.left}
        y={yFor(high)}
        width={plot.w}
        height={yFor(low) - yFor(high)}
        className="band"
      />
      <text x={pad.left + 6} y={yFor(high) - 5} className="band-label">
        target zone {pct(low)}–{pct(high)}
      </text>
      {[0.25, 0.5, 0.75, 1].map((tick) => (
        <g key={tick}>
          <line
            x1={pad.left}
            x2={W - pad.right}
            y1={yFor(tick)}
            y2={yFor(tick)}
            className="gridline"
          />
          <text x={pad.left - 8} y={yFor(tick) + 4} className="axis-label" textAnchor="end">
            {pct(tick)}
          </text>
        </g>
      ))}
      <path d={path} className="series" />
      {points.map((point, i) => (
        <g
          key={point.index}
          className={`dot-group${selected === point.index ? " is-selected" : ""}`}
          tabIndex={0}
          role="button"
          aria-label={point.label}
          onFocus={() => onSelect?.(point.index)}
          onMouseEnter={() => onSelect?.(point.index)}
        >
          <title>{point.label}</title>
          {/* Generous invisible hit area: the dots are small on purpose. */}
          <circle cx={xFor(i)} cy={yFor(point.value)} r={14} className="dot-hit" />
          {point.correct ? (
            <circle
              cx={xFor(i)}
              cy={yFor(point.value)}
              r={5}
              className={`dot${point.inBand ? " in-band" : ""}`}
            />
          ) : (
            /* Wrong answers are a different shape, not a different colour. */
            <rect
              x={xFor(i) - 4.5}
              y={yFor(point.value) - 4.5}
              width={9}
              height={9}
              className={`dot wrong${point.inBand ? " in-band" : ""}`}
            />
          )}
          {point.marker && (
            <text x={xFor(i)} y={H - 10} className="dot-marker" textAnchor="middle">
              {point.marker === "rest" ? "rest" : "check"}
            </text>
          )}
        </g>
      ))}
    </svg>
  );
}

export type StepPoint = { index: number; rung: number; label: string };

/** Difficulty over time as a step line: the chart that shows there is no cliff. */
export function StepChart({ points }: { points: StepPoint[] }) {
  const W = 640;
  const H = 130;
  const pad = { top: 14, right: 16, bottom: 20, left: 40 };
  const plot = { w: W - pad.left - pad.right, h: H - pad.top - pad.bottom };
  const rungs = points.map((p) => p.rung);
  const lo = Math.min(...rungs, 0);
  const hi = Math.max(...rungs, lo + 3);
  const yFor = (rung: number) => pad.top + plot.h * (1 - (rung - lo) / (hi - lo));
  const xFor = (i: number) =>
    pad.left + (points.length < 2 ? plot.w / 2 : (plot.w * i) / (points.length - 1));

  const path = points
    .map((point, i) => {
      const x = xFor(i);
      const y = yFor(point.rung);
      if (!i) return `M${x},${y}`;
      return `L${x},${yFor(points[i - 1].rung)} L${x},${y}`;
    })
    .join(" ");

  return (
    <svg
      className="chart-svg"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Difficulty path: the difficulty step of each question in order"
    >
      {range(lo, hi).map((rung) => (
        <line
          key={rung}
          x1={pad.left}
          x2={W - pad.right}
          y1={yFor(rung)}
          y2={yFor(rung)}
          className="gridline"
        />
      ))}
      <text x={pad.left - 8} y={yFor(hi) + 4} className="axis-label" textAnchor="end">
        harder
      </text>
      <text x={pad.left - 8} y={yFor(lo) + 4} className="axis-label" textAnchor="end">
        easier
      </text>
      <path d={path} className="series step" />
      {points.map((point, i) => (
        <g key={point.index} tabIndex={0} role="button" aria-label={point.label}>
          <title>{point.label}</title>
          <circle cx={xFor(i)} cy={yFor(point.rung)} r={3.5} className="dot in-band" />
        </g>
      ))}
    </svg>
  );
}

export type Bar = { label: string; count: number; hint?: string };

/** Where the mistakes actually are. Ranked bars, because ranking is the point. */
export function BarList({ bars, total }: { bars: Bar[]; total: number }) {
  if (!bars.length) return <p className="muted">No mistakes in this window.</p>;
  const max = Math.max(...bars.map((bar) => bar.count));
  return (
    <ul className="bar-list">
      {bars.map((bar) => (
        <li key={bar.label} title={bar.hint}>
          <span className="bar-label">{bar.label}</span>
          <span className="bar-track">
            <span className="bar-fill" style={{ width: `${(bar.count / max) * 100}%` }} />
          </span>
          <span className="bar-value">
            {bar.count}
            <span className="muted"> of {total}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

export type DeltaRow = {
  label: string;
  before: number;
  after: number;
  /** Formats both values; keeps percentages and counts honest in one table. */
  format: (value: number) => string;
  /** Which direction is an improvement. Stated, never assumed by the reader. */
  better: "up" | "down";
  why: string;
};

/**
 * Before/after pairs with the direction of "better" declared per row.
 *
 * Deliberately paired bars rather than a single delta number: a 20-point move
 * off a base of 5 questions and off a base of 300 look identical as a delta and
 * nothing like each other as bars.
 */
export function DeltaBars({
  rows,
  beforeLabel,
  afterLabel,
}: {
  rows: DeltaRow[];
  beforeLabel: string;
  afterLabel: string;
}) {
  return (
    <table className="delta-table">
      <thead>
        <tr>
          <th scope="col">Measure</th>
          <th scope="col">{beforeLabel}</th>
          <th scope="col">{afterLabel}</th>
          <th scope="col">Change</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const scale = Math.max(row.before, row.after) || 1;
          const delta = row.after - row.before;
          const improved = row.better === "up" ? delta > 0 : delta < 0;
          const flat = Math.abs(delta) < 1e-9;
          return (
            <tr key={row.label}>
              <th scope="row">
                {row.label}
                <span className="row-why">{row.why}</span>
              </th>
              {[row.before, row.after].map((value, i) => (
                <td key={i}>
                  <span className="mini-track">
                    <span
                      className={`mini-fill${i ? " after" : ""}`}
                      style={{ width: `${(value / scale) * 100}%` }}
                    />
                  </span>
                  <span className="mini-value">{row.format(value)}</span>
                </td>
              ))}
              <td>
                <span
                  className={`chip ${flat ? "chip-flat" : improved ? "chip-up" : "chip-down"}`}
                >
                  {flat ? "no change" : `${improved ? "better" : "worse"} ${arrow(delta)}`}
                  {!flat && ` ${row.format(Math.abs(delta))}`}
                </span>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export type FunnelStep = { label: string; value: number; hint: string };

/** Started → kept going → finished. The standard shape for "where do we lose them". */
export function Funnel({ steps }: { steps: FunnelStep[] }) {
  const top = steps[0]?.value || 1;
  return (
    <ol className="funnel">
      {steps.map((step, i) => (
        <li key={step.label}>
          <span className="funnel-label">{step.label}</span>
          <span className="funnel-bar" style={{ width: `${(step.value / top) * 100}%` }}>
            {step.value}
          </span>
          <span className="funnel-hint">
            {i ? `${pct(step.value / top)} of starters — ` : ""}
            {step.hint}
          </span>
        </li>
      ))}
    </ol>
  );
}

export type TrendPoint = { at: string; value: number; group: string; label: string };

/**
 * A metric per sitting with a dashed marker where the version changed --- the
 * deployment-annotation convention every product analytics tool uses, and the
 * only honest way to show a before/after for one child: the trend stays visible
 * instead of collapsing into two averages that hide it.
 */
export function TrendChart({
  points,
  band,
}: {
  points: TrendPoint[];
  band?: { low: number; high: number };
}) {
  const W = 640;
  const H = 190;
  const pad = { top: 16, right: 16, bottom: 34, left: 40 };
  const plot = { w: W - pad.left - pad.right, h: H - pad.top - pad.bottom };
  const yFor = (value: number) => pad.top + plot.h * (1 - clamp(value));
  const xFor = (i: number) =>
    pad.left + (points.length < 2 ? plot.w / 2 : (plot.w * i) / (points.length - 1));
  // Only a version boundary is a release. Unversioned sittings can appear
  // anywhere in the log, and marking them read as "baseline shipped" after v2.
  const breaks = points
    .map((point, i) => ({ i, point }))
    .filter(
      ({ i, point }) =>
        i > 0 && points[i - 1].group !== point.group && point.group !== "baseline"
    );

  return (
    <svg
      className="chart-svg"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Trend per sitting, with a marker where the game version changed"
    >
      {band && (
        <rect
          x={pad.left}
          y={yFor(band.high)}
          width={plot.w}
          height={yFor(band.low) - yFor(band.high)}
          className="band"
        />
      )}
      {[0, 0.5, 1].map((tick) => (
        <g key={tick}>
          <line
            x1={pad.left}
            x2={W - pad.right}
            y1={yFor(tick)}
            y2={yFor(tick)}
            className="gridline"
          />
          <text x={pad.left - 8} y={yFor(tick) + 4} className="axis-label" textAnchor="end">
            {pct(tick)}
          </text>
        </g>
      ))}
      <path
        d={points.map((p, i) => `${i ? "L" : "M"}${xFor(i)},${yFor(p.value)}`).join(" ")}
        className="series"
      />
      {points.map((point, i) => (
        <g key={point.at} tabIndex={0} role="button" aria-label={point.label}>
          <title>{point.label}</title>
          <circle cx={xFor(i)} cy={yFor(point.value)} r={4.5} className="dot in-band" />
        </g>
      ))}
      {breaks.map(({ i, point }) => {
        const x = (xFor(i) + xFor(i - 1)) / 2;
        return (
          <g key={point.group}>
            <line x1={x} x2={x} y1={pad.top} y2={pad.top + plot.h} className="release-line" />
            <text x={x + 5} y={pad.top + 10} className="release-label">
              {point.group} shipped
            </text>
          </g>
        );
      })}
    </svg>
  );
}

export function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function seconds(ms: number): string {
  return ms >= 60000 ? `${Math.round(ms / 60000)} min` : `${(ms / 1000).toFixed(1)}s`;
}

function arrow(delta: number): string {
  return delta > 0 ? "▲" : "▼";
}

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function range(from: number, to: number): number[] {
  return Array.from({ length: to - from + 1 }, (_, i) => from + i);
}
