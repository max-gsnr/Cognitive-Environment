/**
 * The v1 → v2 view: did shipping a new build of the game actually help?
 *
 * This is the release-impact dashboard every product team already has, pointed
 * at a child's sessions instead of a checkout funnel: engagement per version, a
 * completion funnel, and the trend per sitting with the release marked on it.
 *
 * The honesty is in three places, and they are the reason this survives a
 * question from the floor: difficulty is reported *alongside* engagement (if the
 * work got easier, that explains an engagement lift and the caveats say so), the
 * per-sitting trend is shown rather than only two averages, and the caveats come
 * from the backend rather than being written here.
 */
import { useEffect, useState } from "react";

import { ReleaseImpact as ReleaseImpactData, api } from "../api";
import {
  DeltaBars,
  DeltaRow,
  Figure,
  Funnel,
  Stat,
  pct,
} from "./charts";

type Props = { profileId: string; skillId: string };

export function ReleaseImpact({ profileId, skillId }: Props) {
  const [data, setData] = useState<ReleaseImpactData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<ReleaseImpactData>(`/profiles/${profileId}/skills/${skillId}/release-impact`)
      .then((body) => {
        setData(body);
        setError(null);
      })
      .catch((cause: Error) => setError(cause.message));
  }, [profileId, skillId]);

  if (error) return <p className="error">Release impact unavailable: {error}</p>;
  if (!data) return <p className="muted">Loading release impact…</p>;
  if (!data.versions.length) {
    return (
      <div className="card">
        <h2>Release Impact</h2>
        <p className="muted">
          No completed sittings on record for {skillId} yet, so there is nothing to compare.
        </p>
      </div>
    );
  }

  const before = data.versions[0];
  const after = data.versions[data.versions.length - 1];
  const single = data.versions.length < 2;

  const rows: DeltaRow[] = [
    {
      label: "Questions per Session",
      before: before.questions_per_session,
      after: after.questions_per_session,
      format: (value) => value.toFixed(1),
      better: "up",
      why: "how much practice a child actually gets before they stop",
    },
    {
      label: "Completion Rate",
      before: before.completion_rate,
      after: after.completion_rate,
      format: pct,
      better: "up",
      why: "sittings that reached the full session length",
    },
    {
      label: "Drop-off Rate",
      before: before.dropoff_rate,
      after: after.dropoff_rate,
      format: pct,
      better: "down",
      why: "sittings abandoned before the end",
    },
    {
      label: "Challenge Fit",
      before: before.challenge_fit,
      after: after.challenge_fit,
      format: pct,
      better: "up",
      why: "the control: if this moved, difficulty changed too, not just the game",
    },
    {
      label: "Success Rate",
      before: before.success_rate,
      after: after.success_rate,
      format: pct,
      better: "up",
      why: "answers correct — read together with challenge fit, never alone",
    },
    {
      label: "Guessing Rate",
      before: before.guess_rate,
      after: after.guess_rate,
      format: pct,
      better: "down",
      why: "wrong answers given faster than the child's own thinking speed",
    },
    {
      label: "Slow-but-Correct Rate",
      before: before.laboured_rate,
      after: after.laboured_rate,
      format: pct,
      better: "down",
      why: "right answers that took twice as long as usual: effort, not confusion",
    },
    ...(before.focus_share !== null && after.focus_share !== null
      ? [
          {
            label: "Focus Share",
            before: before.focus_share,
            after: after.focus_share,
            format: pct,
            better: "up" as const,
            why: "share of session time spent on the game rather than away from it",
          },
        ]
      : []),
  ];

  return (
    <div className="card monitor">
      <div className="monitor-head">
        <h2>Release Impact</h2>
        <p className="monitor-verdict">
          {single
            ? `Only ${after.label} has been played, so this is a baseline, not a comparison.`
            : `${before.label} → ${after.label}: ${headline(before, after)}`}
        </p>
        {data.synthetic_share > 0 && (
          <p className="chart-caveat">
            {pct(data.synthetic_share)} of these attempts are seeded demo history, not real
            play.
          </p>
        )}
      </div>

      <div className="stat-grid">
        {data.versions.map((version) => (
          <Stat
            key={version.label}
            label={`${version.label} — ${version.sessions} sitting${
              version.sessions === 1 ? "" : "s"
            }`}
            value={`${version.questions_per_session} Qs/sitting`}
            note={
              version.diagnosis
                ? `built because: ${version.diagnosis.replace(/_/g, " ")} → ${
                    version.change_tier ?? "no"
                  } change`
                : `${version.questions} questions, challenge fit ${pct(version.challenge_fit)}`
            }
            tone={version === data.versions[data.versions.length - 1] ? "good" : "neutral"}
          />
        ))}
      </div>

      {!single && (
        <Figure
          title="What Changed, Version to Version"
          why={
            "Each measure before and after the new build, with the direction that counts as " +
            "an improvement stated explicitly. Challenge Fit is in the list on purpose: it " +
            "is the check that the game changed and the difficulty did not."
          }
          summary={rows
            .map((row) => `${row.label}: ${row.format(row.before)} → ${row.format(row.after)}`)
            .join(". ")}
        >
          <DeltaBars rows={rows} beforeLabel={before.label} afterLabel={after.label} />
        </Figure>
      )}

      <Figure
        title="Where Sessions End"
        why={
          "Of the sittings a child starts, how many get past the first few questions and how " +
          "many reach the end. Attention, measured as behaviour rather than as a score."
        }
        summary={funnelSummary(data)}
      >
        <Funnel
          steps={[
            {
              label: "Sittings started",
              value: data.timeline.length,
              hint: "a run of questions with no long break",
            },
            {
              label: "Reached 5 questions",
              value: data.timeline.filter((point) => point.questions >= 5).length,
              hint: "past the point where a bored child usually stops",
            },
            {
              label: "Finished the session",
              value: data.timeline.filter((point) => point.completed).length,
              hint: "played the full session length set at intake",
            },
          ]}
        />
      </Figure>



      <div className="caveats">
        <h3>Read this with the caveats</h3>
        <ul>
          {data.caveats.map((caveat) => (
            <li key={caveat}>{caveat}</li>
          ))}
          <li>
            One child, no control group: this is a directional read on whether a build helped,
            not proof that it caused the change.
          </li>
        </ul>
        {after.changes_made?.length ? (
          <>
            <h3>What the new version actually changed</h3>
            <ul>
              {after.changes_made.map((change) => (
                <li key={change}>{change}</li>
              ))}
            </ul>
          </>
        ) : null}
        {after.pr_url && (
          <p>
            <a href={after.pr_url} target="_blank" rel="noreferrer">
              Review the pull request that produced {after.label}
            </a>
          </p>
        )}
      </div>
    </div>
  );
}

function headline(
  before: ReleaseImpactData["versions"][number],
  after: ReleaseImpactData["versions"][number]
): string {
  const practice = after.questions_per_session - before.questions_per_session;
  const fitDrift = Math.abs(after.challenge_fit - before.challenge_fit);
  const direction = practice > 0 ? "more" : "less";
  const clean =
    fitDrift <= 0.15
      ? "at the same difficulty"
      : "but the difficulty moved too, so read the caveats first";
  return `${Math.abs(practice).toFixed(1)} ${direction} questions per sitting, ${clean}.`;
}

function funnelSummary(data: ReleaseImpactData): string {
  const started = data.timeline.length;
  const finished = data.timeline.filter((point) => point.completed).length;
  return `${started} sittings started, ${finished} finished (${pct(
    started ? finished / started : 0
  )}).`;
}
