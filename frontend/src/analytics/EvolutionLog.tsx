/**
 * Loop B, as a build log: every version of the game, why it was asked for, and
 * what stopped the ones that never reached the child.
 *
 * Deliberately shaped like an internal engineering console rather than a product
 * dashboard -- a run list on the left, the selected run on the right, verdicts in
 * monospace -- because that is what this is: continuous delivery where the change
 * being shipped is the game, and the tests are run against a child's telemetry.
 *
 * Every field is read straight off the game row (app/evolution.py). Nothing here
 * scores, predicts or infers. The diagnosis is shown as the rule ladder that
 * produced it -- each rule, its threshold, the recorded value, and whether it was
 * even reached -- so a reader can recompute it instead of trusting it. The two
 * scoreboards stay paired but separate so the agent's claim never stands in for
 * our check, and a check we could not run reads as "not run", not as a pass.
 */
import { useEffect, useMemo, useState } from "react";

import { EvolutionLog as EvolutionLogData, EvolutionVersion, api } from "../api";

type Props = { profileId: string; skillId: string; refreshKey?: number };
type Ladder = EvolutionVersion["trigger"]["ladder"];

export function EvolutionLog({ profileId, skillId, refreshKey = 0 }: Props) {
  const [data, setData] = useState<EvolutionLogData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<EvolutionLogData>(`/profiles/${profileId}/skills/${skillId}/evolution`)
      .then((body) => {
        setData(body);
        setError(null);
      })
      .catch((cause: Error) => setError(cause.message));
  }, [profileId, skillId, refreshKey]);

  const versions = data?.versions ?? [];
  const current = useMemo(
    () => versions.find((version) => version.game_id === selected) ?? versions[0],
    [versions, selected]
  );
  // The rule set is the same for every version, so any version that carries a
  // ladder can supply the policy table beside the run list.
  const policy = useMemo(
    () =>
      versions.find((version) => version.trigger.ladder?.length)?.trigger.ladder ?? [],
    [versions]
  );

  if (error) return <p className="error">Build log unavailable: {error}</p>;
  if (!data) return <p className="muted">Loading build log…</p>;
  if (!versions.length) {
    return (
      <div className="card console">
        <h2>Game Build Log</h2>
        <p className="muted">
          No version of the {skillId} game has been generated yet, so Loop B has nothing
          to show.
        </p>
      </div>
    );
  }

  const { summary } = data;

  return (
    <div className="card console">
      <div className="console-head">
        <div>
          <h2>Game Build Log</h2>
          <p className="console-sub">
            Loop B rewrites the game between sessions. Each run below is one attempt at
            that: the evidence that triggered it, the scope that evidence allowed, and
            the checks it had to pass before a child saw it.
          </p>
        </div>
        <dl className="console-counts">
          <Count label="Runs" value={summary.proposed} />
          <Count
            label="Live"
            value={summary.live_version === null ? "—" : `v${summary.live_version}`}
          />
          <Count
            label="Blocked by us"
            value={summary.blocked}
            tone={summary.blocked ? "bad" : "neutral"}
          />
          <Count
            label="Self-pass, we failed"
            value={summary.disagreements}
            tone={summary.disagreements ? "bad" : "neutral"}
            hint="runs whose own report said pass and whose independent re-check did not"
          />
        </dl>
      </div>

      <div className="console-body">
        <div className="console-side">
          <ol className="console-runs" aria-label="Versions, newest first">
            {versions.map((version) => (
              <li key={version.game_id}>
                <button
                  type="button"
                  className={`console-run${
                    version.game_id === current.game_id ? " is-current" : ""
                  }`}
                  aria-current={version.game_id === current.game_id}
                  onClick={() => setSelected(version.game_id)}
                >
                  <span className="console-run-top">
                    <span className="console-run-id">
                      {version.label}
                      {version.from_version !== null && (
                        <span className="console-from">←v{version.from_version}</span>
                      )}
                    </span>
                    <span className={`verdict verdict-${stateTone(version.state)}`}>
                      {STATE_WORD[version.state]}
                    </span>
                  </span>
                  <span className="console-run-why">
                    {version.trigger.signal ?? "no telemetry"}
                    <span className="console-run-tier">
                      {" → "}
                      {version.permitted_change.allowed ?? "—"}
                    </span>
                  </span>
                  <span className="console-run-at">
                    {when(version.created_at)}
                    <span className="console-run-checks">
                      {passCount(version)} pass / {failCount(version)} fail
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ol>

          {policy.length > 0 && (
            <Disclose summary={`The rule set (${policy.length} readings)`}>
              <Policy ladder={policy} fired={current.trigger.signal} />
            </Disclose>
          )}
        </div>

        <VersionDetail version={current} />
      </div>
    </div>
  );
}

/**
 * The fixed policy: which reading permits which class of change. Static code, not
 * a model output, and worth showing because it is the ceiling on what the agent
 * is allowed to touch.
 */
function Policy({ ladder, fired }: { ladder: Ladder; fired: string | null }) {
  return (
    <div className="console-policy">
      <h4>Signal → permitted change</h4>
      <table>
        <tbody>
          {ladder.map((rule) => (
            <tr key={rule.signal} className={rule.signal === fired ? "is-current" : ""}>
              <th scope="row">{rule.signal}</th>
              <td>{rule.tier ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="console-note">
        Priority order, top to bottom. The first rule that holds wins and fixes the
        scope; nothing below it is evaluated.
      </p>
    </div>
  );
}

/**
 * One screen, four claims: why this run happened, what it was allowed to touch,
 * what it changed, and who let it near a child. Everything that supports those
 * claims -- the losing rules, the raw figures, the checks that agreed, the
 * provenance -- sits behind a disclosure, so the page can be read in a minute and
 * still answer a follow-up question in one click.
 */
function VersionDetail({ version }: { version: EvolutionVersion }) {
  const { trigger, permitted_change: change, provenance } = version;
  // An older payload, or one written before the ladder existed, simply has no
  // rules to show -- it must not take the panel down with it.
  const ladder = trigger.ladder ?? [];
  const measured = trigger.measured ?? [];
  const fired = ladder.find((rule) => rule.outcome === "fired");
  const clashes = version.checks.filter(
    (check) => check.source === "ours" && check.verdict === "fail"
  );
  const agent = version.checks.filter((check) => check.source === "agent");
  const ours = version.checks.filter((check) => check.source === "ours");

  return (
    <div className="console-detail">
      <div className="console-detail-head">
        <h3>
          {version.label}
          {version.from_version !== null && (
            <span className="console-from"> from v{version.from_version}</span>
          )}
        </h3>
        <code className="console-meta">
          status={version.status} · live={String(version.is_live)} ·{" "}
          {trigger.event_count ? `${trigger.event_count} events` : "no events"}
        </code>
        <span className={`verdict verdict-${stateTone(version.state)}`}>
          {version.state_label}
        </span>
      </div>

      <Step
        n={1}
        title="Why this run was requested"
        note="A rule over recorded numbers, not a model call. Read from this child's last session."
      >
        {trigger.available ? (
          <>
            {fired && (
              <p className="console-fired">
                <span className="verdict verdict-good">FIRED</span>
                <code>{fired.signal}</code>
                <span className="console-fired-terms">
                  {fired.terms.map((term, index) => (
                    <code key={term.key}>
                      {index > 0 && ` ${term.joiner} `}
                      {term.key} {term.comparison} {round(term.threshold)}{" "}
                      <span className="term-value">
                        (was {term.value === null ? "n/a" : round(term.value)})
                      </span>
                    </code>
                  ))}
                </span>
              </p>
            )}
            <Disclose
              summary={`How the other rules scored, and the ${measured.length} figures behind them`}
            >
              <RuleTable ladder={ladder} />
              <dl className="console-raw">
                {measured.map((item) => (
                  <div key={item.key}>
                    <dt>{item.key}</dt>
                    <dd>{round(item.value)}</dd>
                  </div>
                ))}
              </dl>
            </Disclose>
          </>
        ) : (
          <p className="muted">
            {trigger.reason} — so no reading was claimed, and this build was the first
            one rather than a response to anything.
          </p>
        )}
      </Step>

      <div className="console-split">
        <Step
          n={2}
          title="Scope it was allowed"
          note="The signal fixes the remit before the agent starts, so it cannot widen its own brief."
        >
          <table className="console-scope">
            <tbody>
              <tr>
                <th scope="row">allowed</th>
                <td>
                  <code>{change.allowed ?? "—"}</code>
                  <span className="muted"> {change.allowed_label ?? ""}</span>
                </td>
              </tr>
              <tr>
                <th scope="row">claimed</th>
                <td>
                  <code>{change.claimed ?? "—"}</code>
                  <span className="muted"> {change.claimed_label ?? ""}</span>
                </td>
              </tr>
              <tr>
                <th scope="row">verdict</th>
                <td>
                  {change.within_scope === false && (
                    <span className="verdict verdict-bad">OUT OF SCOPE</span>
                  )}
                  {change.within_scope === true && (
                    <span className="verdict verdict-good">WITHIN SCOPE</span>
                  )}
                  {change.within_scope === null && <span className="muted">—</span>}
                </td>
              </tr>
            </tbody>
          </table>
          {change.rule && <p className="console-rule">{change.rule}</p>}
        </Step>

        <Step n={3} title="What it changed" note={version.diff_summary ?? undefined}>
          {version.summary && <p className="console-summary">{version.summary}</p>}
          {version.changes_made.length ? (
            <ul className="console-changes">
              {version.changes_made.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p className="muted">Nothing recorded.</p>
          )}
        </Step>
      </div>

      <Step
        n={4}
        title="Whether it was allowed near a child"
        note="Two verdicts: the agent's own report, and a re-check that runs in code the agent never sees. A run has to pass both."
      >
        <p className="console-tally">
          <span className="verdict verdict-neutral">
            agent {count(agent, "pass")}/{agent.length} pass
          </span>
          <span
            className={`verdict verdict-${count(ours, "fail") ? "bad" : "good"}`}
          >
            our re-check {count(ours, "pass")}/{ours.length} pass
          </span>
          {clashes.length > 0 && (
            <span className="console-tally-why">
              It reported itself green; we did not agree.
            </span>
          )}
        </p>
        {clashes.length > 0 && (
          <ul className="console-clashes">
            {clashes.map((check) => (
              <li key={check.name}>
                <span className="verdict verdict-bad">FAIL</span>
                <code>{check.name}</code>
                <span>{check.detail ?? check.label}</span>
              </li>
            ))}
          </ul>
        )}
        {version.blocked_by.length > 0 && (
          <p className="error">Never shipped. Failed: {version.blocked_by.join("; ")}.</p>
        )}
        {/* Counted by name, because the matrix pairs the two sources on one row:
            `playthrough` is checked twice but is one check. */}
        <Disclose
          summary={`All ${
            new Set(version.checks.map((check) => check.name)).size
          } checks, agent beside ours`}
        >
          <GateMatrix checks={version.checks} />
        </Disclose>
      </Step>

      <Disclose summary="Provenance: prompt, agent, session, diff">
        <dl className="console-provenance">
        <div>
          <dt>prompt</dt>
          <dd>
            <code>
              {provenance.prompt ?? "—"}
              {provenance.prompt_revision ? `@${provenance.prompt_revision}` : ""}
            </code>
          </dd>
        </div>
        <div>
          <dt>agent</dt>
          <dd>
            <code>{provenance.agent ?? "—"}</code>
          </dd>
        </div>
        <div>
          <dt>session</dt>
          <dd>
            <code>{provenance.devin_session_id ?? "—"}</code>
          </dd>
        </div>
        <div>
          <dt>diff</dt>
          <dd>
            {provenance.pr_url ? (
              <a href={provenance.pr_url} target="_blank" rel="noreferrer">
                {provenance.pr_url.replace(/^https?:\/\/(www\.)?github\.com\//, "")}
              </a>
            ) : (
              <code>—</code>
            )}
          </dd>
          </div>
        </dl>
      </Disclose>
    </div>
  );
}

/** Detail a judge only needs if they ask. Closed by default, one click away. */
function Disclose({
  summary,
  children,
}: {
  summary: string;
  children: React.ReactNode;
}) {
  return (
    <details className="console-disclose">
      <summary>{summary}</summary>
      <div>{children}</div>
    </details>
  );
}

/** The decision itself: rule, condition with the real values in it, outcome. */
function RuleTable({ ladder }: { ladder: Ladder }) {
  return (
    <table className="console-ladder">
      <thead>
        <tr>
          <th scope="col">rule</th>
          <th scope="col">condition, with this session's values</th>
          <th scope="col">outcome</th>
        </tr>
      </thead>
      <tbody>
        {ladder.map((rule) => (
          <tr key={rule.signal} className={`outcome-${rule.outcome}`}>
            <th scope="row">{rule.signal}</th>
            <td>
              <code>
                {rule.terms.map((term, index) => (
                  <span key={term.key} className={term.met ? "term-met" : "term-unmet"}>
                    {index > 0 && ` ${term.joiner} `}
                    {term.key} {term.comparison} {round(term.threshold)}{" "}
                    <span className="term-value">
                      ({term.value === null ? "n/a" : round(term.value)})
                    </span>
                  </span>
                ))}
              </code>
            </td>
            <td>
              <span className={`verdict verdict-${outcomeTone(rule.outcome)}`}>
                {OUTCOME_WORD[rule.outcome]}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * One row per check, the agent's verdict beside ours, so a disagreement is read as
 * a mismatched pair rather than as two lists of different lengths. A check only
 * one side runs shows a dash on the other -- never a borrowed pass.
 */
function GateMatrix({ checks }: { checks: EvolutionVersion["checks"] }) {
  const names: string[] = [];
  for (const check of checks) if (!names.includes(check.name)) names.push(check.name);
  const find = (name: string, source: "agent" | "ours") =>
    checks.find((check) => check.name === name && check.source === source);

  return (
    <table className="console-matrix">
      <thead>
        <tr>
          <th scope="col">check</th>
          <th scope="col">agent said</th>
          <th scope="col">we found</th>
          <th scope="col">what it means</th>
        </tr>
      </thead>
      <tbody>
        {names.map((name) => {
          const agent = find(name, "agent");
          const ours = find(name, "ours");
          const clash = agent?.verdict === "pass" && ours?.verdict === "fail";
          return (
            <tr key={name} className={clash ? "is-clash" : ""}>
              <th scope="row">{name}</th>
              <Cell check={agent} />
              <Cell check={ours} />
              <td className="console-matrix-why">
                {ours?.detail ?? ours?.label ?? agent?.label ?? ""}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Cell({ check }: { check?: EvolutionVersion["checks"][number] }) {
  if (!check)
    return (
      <td>
        <span className="muted">—</span>
      </td>
    );
  return (
    <td>
      <span className={`verdict verdict-${verdictTone(check.verdict)}`}>
        {VERDICT_WORD[check.verdict]}
      </span>
    </td>
  );
}

function Step({
  n,
  title,
  note,
  children,
}: {
  n: number;
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="console-step">
      <h4>
        <span className="console-step-n">{n}</span>
        {title}
      </h4>
      {note && <p className="console-note">{note}</p>}
      {children}
    </section>
  );
}

function Count({
  label,
  value,
  tone = "neutral",
  hint,
}: {
  label: string;
  value: number | string;
  tone?: "neutral" | "bad";
  hint?: string;
}) {
  return (
    <div className={`console-count tone-${tone}`} title={hint}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

const VERDICT_WORD: Record<EvolutionVersion["checks"][number]["verdict"], string> = {
  pass: "PASS",
  fail: "FAIL",
  skipped: "SKIP",
  not_run: "N/RUN",
};

const OUTCOME_WORD: Record<Ladder[number]["outcome"], string> = {
  fired: "FIRED",
  no: "no",
  not_reached: "not reached",
};

const STATE_WORD: Record<EvolutionVersion["state"], string> = {
  live: "LIVE",
  shipped: "SHIPPED",
  blocked: "BLOCKED",
  in_progress: "BUILDING",
  failed: "FAILED",
};

function outcomeTone(outcome: Ladder[number]["outcome"]): string {
  return outcome === "fired" ? "good" : "neutral";
}

function passCount(version: EvolutionVersion): number {
  return count(version.checks, "pass");
}

function failCount(version: EvolutionVersion): number {
  return count(version.checks, "fail");
}

function count(
  checks: EvolutionVersion["checks"],
  verdict: EvolutionVersion["checks"][number]["verdict"]
): number {
  return checks.filter((check) => check.verdict === verdict).length;
}

function verdictTone(verdict: EvolutionVersion["checks"][number]["verdict"]): string {
  if (verdict === "pass") return "good";
  if (verdict === "fail") return "bad";
  return "neutral";
}

function stateTone(state: EvolutionVersion["state"]): string {
  if (state === "live") return "good";
  if (state === "blocked" || state === "failed") return "bad";
  return "neutral";
}

function round(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function when(at: string): string {
  return new Date(at).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
