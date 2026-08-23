/**
 * The panel beside the game. One question: is this child in the right place
 * right now?
 *
 * Everything drawn here is computed server-side in app/analytics.py by replaying
 * the attempt log through Loop A, so the panel cannot flatter the game: if the
 * chart says the difficulty was wrong, that is the same arithmetic the teaching
 * decision used.
 */
import { useCallback, useEffect, useState } from "react";

import { SessionMetrics, api } from "../api";
import {
  BandChart,
  BandPoint,
  BarList,
  Figure,
  Legend,
  Stat,
  StepChart,
  pct,
  seconds,
} from "./charts";

type Props = {
  profileId: string;
  skillId: string;
  childName: string;
  /** Bumped by the caller after each answer, which is what re-fetches. */
  refreshKey: number;
};

// The rail is narrow, so it plots a sitting rather than a history: twelve dots
// stay individually readable at 320-380px, twenty do not.
const WINDOW = 12;

export function SessionMonitor({ profileId, skillId, childName, refreshKey }: Props) {
  const [metrics, setMetrics] = useState<SessionMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [showMore, setShowMore] = useState(false);

  const load = useCallback(() => {
    api
      .get<SessionMetrics>(
        `/profiles/${profileId}/skills/${skillId}/session-metrics?window=${WINDOW}`
      )
      .then((body) => {
        setMetrics(body);
        setError(null);
      })
      .catch((cause: Error) => setError(cause.message));
  }, [profileId, skillId]);

  useEffect(load, [load, refreshKey]);

  if (error) return <p className="error">Session monitor unavailable: {error}</p>;
  if (!metrics) return <p className="muted">Loading session metrics…</p>;
  if (!metrics.questions) {
    return (
      <div className="card">
        <h2>Session Monitor</h2>
        <p className="muted">
          No answers yet. The charts fill in from the first question — nothing here is
          pre-computed.
        </p>
      </div>
    );
  }

  const points: BandPoint[] = metrics.points.map((point) => ({
    index: point.index,
    value: point.expected_success,
    inBand: point.in_band,
    correct: point.correct,
    marker: point.rest_item ? "rest" : point.fluency_check ? "fluency" : undefined,
    label:
      `Q${point.index}: ${point.problem} — ${point.correct ? "correct" : "wrong"}, ` +
      `${pct(point.expected_success)} expected success (${point.tier_label})`,
  }));
  const focus = metrics.points.find((point) => point.index === selected) ?? null;
  const inBand = metrics.points.filter((point) => point.in_band).length;

  return (
    <div className="card monitor">
      <div className="monitor-head">
        <h2>Session Monitor</h2>
        <p className="monitor-verdict">
          {verdict(childName, metrics)}
        </p>
        {metrics.synthetic_share > 0 && (
          <p className="chart-caveat">
            {pct(metrics.synthetic_share)} of the attempts behind these charts are seeded
            demo history, not real play.
          </p>
        )}
      </div>

      {/* Four tiles, chosen because each one can change a decision: is the
          difficulty right, is the child succeeding as often as intended, does a
          mistake end quickly, and is a quit-risk run building. Pace, idle time
          and focus are diagnostics, not decisions, so they wait behind the
          toggle. */}
      <div className="stat-grid">
        <Stat
          label="Challenge Fit"
          value={pct(metrics.challenge_fit)}
          note={`${inBand} of the last ${metrics.questions} in the target zone`}
          tone={metrics.challenge_fit >= 0.6 ? "good" : "watch"}
        />
        <Stat
          label="Success Rate"
          value={pct(metrics.success_rate)}
          note={`aiming at ${pct(metrics.target_success)}`}
          tone={Math.abs(metrics.success_rate - metrics.target_success) <= 0.15 ? "good" : "watch"}
        />
        <Stat
          label="Time to Recovery"
          value={
            metrics.mean_recovery_questions === null
              ? "—"
              : `${metrics.mean_recovery_questions} Qs`
          }
          note="mistake to right answer"
          tone={
            metrics.mean_recovery_questions !== null && metrics.mean_recovery_questions <= 2
              ? "good"
              : "watch"
          }
        />
        <Stat
          label="Longest Error Run"
          value={`${metrics.longest_error_run}`}
          note="3+ is where children quit"
          tone={metrics.longest_error_run <= 2 ? "good" : "watch"}
        />
      </div>

      <Figure
        title="Challenge Fit"
        why={
          "Each dot is one question, placed at the chance this child had of getting it " +
          "right. The shaded band is the zone we aim for — hard enough to learn, easy " +
          "enough to stay. Dots inside the band mean the difficulty was right, whatever " +
          "the score did."
        }
        summary={summarise(metrics)}
        legend={
          <Legend
            items={[
              { mark: <span className="key-dot" />, label: "correct" },
              { mark: <span className="key-square" />, label: "wrong" },
              { mark: <span className="key-hollow" />, label: "outside the band" },
              { mark: <span className="key-text">rest</span>, label: "easier item after 2 mistakes" },
              { mark: <span className="key-text">check</span>, label: "fluency check-in" },
            ]}
          />
        }
      >
        <BandChart
          points={points}
          low={metrics.band_low}
          high={metrics.band_high}
          selected={selected}
          onSelect={setSelected}
        />
        <p className="chart-readout" aria-live="polite">
          {focus
            ? `Q${focus.index}: ${focus.problem} • ${focus.correct ? "correct" : "wrong"} • ` +
              `${pct(focus.expected_success)} expected • ${focus.tier_label} • ` +
              `${(focus.latency_ms / 1000).toFixed(1)}s` +
              (focus.pace_index === null
                ? " (no pace yet)"
                : ` (${focus.pace_index}× usual pace)`)
            : "Hover or tab through the dots to inspect any single question."}
        </p>
      </Figure>

      <button
        type="button"
        className="secondary monitor-more"
        aria-expanded={showMore}
        onClick={() => setShowMore((on) => !on)}
      >
        {showMore ? "Hide difficulty path and mistakes" : "Difficulty path and mistakes"}
      </button>

      {showMore && (
        <>
      <div className="stat-grid">
        <Stat
          label="On-Pace Rate"
          value={pct(metrics.on_pace_rate)}
          note="within this child's usual speed"
        />
        <Stat
          label="Time on Task"
          value={seconds(metrics.time_on_task_ms)}
          note={`${seconds(metrics.idle_ms)} idle${
            metrics.focus_share === null ? "" : ` • focus ${pct(metrics.focus_share)}`
          }`}
        />
      </div>

      <Figure
        title="Difficulty Path"
        why={
          "The difficulty of each question in order. A staircase with small steps and the " +
          "occasional dip is the goal; a cliff is the failure mode we fixed."
        }
        summary={
          `Difficulty moved ${metrics.tier_changes} time(s) across ${metrics.questions} ` +
          `questions, currently at ${metrics.points[metrics.points.length - 1].tier_label}.`
        }
      >
        <StepChart
          points={metrics.points.map((point) => ({
            index: point.index,
            rung: point.rung,
            label: `Q${point.index}: ${point.tier_label} (${point.movement})`,
          }))}
        />
      </Figure>

      <Figure
        title="Mistake Patterns"
        why={
          "Mistakes grouped by what went wrong in the working, not just how many. This is " +
          "what turns a wrong answer into something teachable — and it is what decides " +
          "which part of the difficulty gets eased."
        }
        summary={
          metrics.mistake_mix.length
            ? metrics.mistake_mix.map((m) => `${m.label}: ${m.count}`).join(", ")
            : "No mistakes in this window."
        }
      >
        <BarList
          bars={metrics.mistake_mix.map((mistake) => ({
            label: mistake.label,
            count: mistake.count,
            hint: mistake.error_class,
          }))}
          total={metrics.questions}
        />
      </Figure>
        </>
      )}
    </div>
  );
}

/** One sentence a teacher can act on, before any chart is read. */
function verdict(childName: string, metrics: SessionMetrics): string {
  const name = childName || "This child";
  if (metrics.longest_error_run >= 3) {
    return `${name} hit ${metrics.longest_error_run} wrong answers in a row — the next items are easier by design, but this is the moment to sit with them.`;
  }
  if (metrics.challenge_fit >= 0.6) {
    const recovery =
      metrics.mean_recovery_questions === null
        ? "no mistakes to recover from yet"
        : `recovering from mistakes in ${metrics.mean_recovery_questions} questions`;
    return `${name} is in the target zone on ${pct(metrics.challenge_fit)} of recent questions, ${recovery}. Leave it alone.`;
  }
  if (metrics.success_rate > metrics.target_success + 0.15) {
    return `${name} is getting nearly everything right — the work is drifting too easy, and the next questions will step up.`;
  }
  return `${name} is outside the target zone more often than in it. Watch the difficulty path below before changing anything.`;
}

function summarise(metrics: SessionMetrics): string {
  return (
    `${metrics.questions} questions. Challenge fit ${pct(metrics.challenge_fit)} ` +
    `(target zone ${pct(metrics.band_low)}–${pct(metrics.band_high)} expected success). ` +
    `Success rate ${pct(metrics.success_rate)} against a ${pct(metrics.target_success)} ` +
    `target. Longest run of wrong answers ${metrics.longest_error_run}. ` +
    `Mean recovery ${metrics.mean_recovery_questions ?? "n/a"} questions.`
  );
}
