import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { AttemptResult, DifficultyVector, ProfileDetail, Question, api } from "../api";
import { SessionMonitor } from "../analytics/SessionMonitor";
import { OrbitCanvas } from "../game/OrbitCanvas";
import { getThemeForInterests } from "../game/OpenGameArena";

export function PlayPage() {
  const { profileId = "", skillId = "" } = useParams();
  const [detail, setDetail] = useState<ProfileDetail | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [lastResult, setLastResult] = useState<AttemptResult | null>(null);
  const [answered, setAnswered] = useState(0);
  const [score, setScore] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [problem, setProblem] = useState("");
  const [teacherView, setTeacherView] = useState(false);
  const [playMode, setPlayMode] = useState<"arcade" | "iframe">("arcade");

  const liveGame = detail?.games.find((game) => game.skill_id === skillId && game.is_live) ?? null;
  const sessionLength = detail?.profile.session_length ?? 10;
  const activeTheme = getThemeForInterests(detail?.profile.interests);

  useEffect(() => {
    api
      .get<ProfileDetail>(`/profiles/${profileId}`)
      .then(setDetail)
      .catch((cause: Error) => setError(cause.message));
  }, [profileId]);

  const report = () => {
    const gameId = liveGame?.id || "orbit-game-client";
    api
      .post(`/games/${gameId}/report-problem`, { description: problem })
      .then(() => setProblem(""))
      .catch((cause: Error) => setError(cause.message));
  };

  const rawStream = teacherView && (
    <div className="card teacher-card">
      <h2>Raw Signal Stream</h2>
      <p className="muted">Live diagnostic stream tracking cognitive pace, cursor kinematics, and attention nuance.</p>
      
      {/* Biometric Gauges Grid (2 Decimal Precision) */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "16px", margin: "16px 0" }}>
        <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "14px", borderRadius: "10px", border: "1px solid rgba(255, 255, 255, 0.1)" }}>
          <span style={{ fontSize: "12px", textTransform: "uppercase", color: "#94a3b8", fontWeight: 600 }}>⚡ Focus & Engagement Index</span>
          <div style={{ fontSize: "24px", fontWeight: 700, color: (lastResult?.focus_score ?? 100) >= 80 ? "#4ade80" : (lastResult?.focus_score ?? 100) >= 60 ? "#fbbf24" : "#f87171", marginTop: "4px" }}>
            {lastResult?.focus_score !== undefined ? `${lastResult.focus_score.toFixed(2)}%` : "100.00% (High Focus)"}
          </div>
          <small style={{ color: "#cbd5e1" }}>
            {(lastResult?.distraction_events ?? 0) > 0 ? `⚠️ ${lastResult?.distraction_events} distraction blurs` : "✓ Direct on-screen attention"}
          </small>
        </div>

        <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "14px", borderRadius: "10px", border: "1px solid rgba(255, 255, 255, 0.1)" }}>
          <span style={{ fontSize: "12px", textTransform: "uppercase", color: "#94a3b8", fontWeight: 600 }}>🖱️ Cursor Kinematics & Jitter</span>
          <div style={{ fontSize: "24px", fontWeight: 700, color: "#38bdf8", marginTop: "4px" }}>
            {lastResult?.cursor_velocity_px_s !== undefined ? `${lastResult.cursor_velocity_px_s.toFixed(2)} px/s` : "Tracking movement..."}
          </div>
          <small style={{ color: "#cbd5e1" }}>
            Jitter: {lastResult?.jitter_ratio !== undefined ? `${lastResult.jitter_ratio.toFixed(2)}x` : "1.00x"} • {(lastResult?.jitter_ratio ?? 1) > 2.5 ? "Restless / Tremor" : "Smooth Intentional"}
          </small>
        </div>

        <div style={{ background: "rgba(15, 23, 42, 0.6)", padding: "14px", borderRadius: "10px", border: "1px solid rgba(255, 255, 255, 0.1)" }}>
          <span style={{ fontSize: "12px", textTransform: "uppercase", color: "#94a3b8", fontWeight: 600 }}>⏱️ Cognitive Latency Breakdown</span>
          <div style={{ fontSize: "24px", fontWeight: 700, color: "#c084fc", marginTop: "4px" }}>
            {lastResult?.hesitation_ms !== undefined ? `${(lastResult.hesitation_ms / 1000).toFixed(2)}s` : "0.00s"} Hesitation
          </div>
          <small style={{ color: "#cbd5e1" }}>
            Idle: {lastResult?.idle_time_ms !== undefined ? `${(lastResult.idle_time_ms / 1000).toFixed(2)}s` : "0.00s"} • Baseline: {lastResult?.baseline_ms ? `${(lastResult.baseline_ms / 1000).toFixed(2)}s` : "Accumulating"}
          </small>
        </div>
      </div>

      <dl className="teacher-view">
        <dt>Current Problem</dt>
        <dd>
          {question
            ? `${question.operands[0]} ${question.operator} ${question.operands[1]} = ${question.correct_answer}`
            : "Waiting for question..."}
        </dd>
        <dt>Difficulty Vector</dt>
        <dd>
          {describeVector(
            lastResult?.updated_difficulty_vector ?? question?.difficulty_vector_snapshot
          )}
        </dd>
        <dt>Last Error Classification</dt>
        <dd>
          {lastResult
            ? `${lastResult.error_class} (${lastResult.movement || "steady"})`
            : "No attempts yet"}
        </dd>
        <dt>Session Progress</dt>
        <dd>
          {answered} of {sessionLength} completed • Score: {score}
        </dd>
      </dl>
    </div>
  );

  const teacherToggle = (
    <div className="teacher-toggle-bar">
      <button className="secondary" onClick={() => setTeacherView((on) => !on)}>
        {teacherView ? "Hide raw signal stream" : "Show raw signal stream"}
      </button>
      {liveGame?.code_path && (
        <button
          className="secondary"
          onClick={() => setPlayMode((m) => (m === "arcade" ? "iframe" : "arcade"))}
        >
          {playMode === "arcade" ? "Switch to Static Iframe" : "Switch to OpenGame Arcade"}
        </button>
      )}
    </div>
  );

  if (error) return <p className="error">{error}</p>;

  return (
    <div className="play-page-layout">
      <div className="play-header">
        <h1 style={{ textTransform: "capitalize" }}>
          {detail?.profile.name || "Student"}&apos;s {skillId} Mission — {activeTheme.name}
        </h1>
        <div className="hud-badge">
          ✦ {answered} / {sessionLength} Completed
        </div>
      </div>

      {/* The game and the dashboard sit side by side: a judge should be able to
          watch a dot land in the target band as the child answers. */}
      <div className="play-grid">
        <div className="play-main">
          {playMode === "iframe" && liveGame?.code_path ? (
            <iframe
              title="Orbit game"
              src={`/${liveGame.code_path}`}
              style={{ width: "100%", height: 640, border: "1px solid #e3e6ef", borderRadius: 12 }}
            />
          ) : (
            <OrbitCanvas
              profileId={profileId}
              skillId={skillId}
              interests={detail?.profile.interests}
              sessionLength={sessionLength}
              gameId={liveGame?.id ?? null}
              gameVersion={liveGame?.version ?? null}
              onQuestionLoaded={(q) => setQuestion(q)}
              onAttemptResult={(res) => setLastResult(res)}
              onScoreUpdate={(s, a) => {
                setScore(s);
                setAnswered(a);
              }}
            />
          )}

          {/* Problem reporting */}
          <div className="card report-card">
            <label>
              Something wrong with the star pod or coordinates?
              <input
                value={problem}
                onChange={(event) => setProblem(event.target.value)}
                placeholder="Tell us what happened..."
              />
            </label>
            <button className="secondary" onClick={report} disabled={!problem.trim()}>
              Tell a grown-up
            </button>
          </div>

          {teacherToggle}
          {rawStream}
        </div>

        <aside className="play-side">
          <SessionMonitor
            profileId={profileId}
            skillId={skillId}
            childName={detail?.profile.name ?? ""}
            refreshKey={answered}
          />
        </aside>
      </div>
    </div>
  );
}

function describeVector(vector: DifficultyVector | undefined): string {
  if (!vector) return "unknown";
  const flags = [
    vector.carries && "carrying",
    vector.borrows && "borrowing",
    vector.zero_in_minuend && "zeros to borrow across",
  ].filter(Boolean);
  const magnitude = vector.magnitude ? vector.magnitude.replace(/_/g, " ") : "single";
  return flags.length
    ? `${vector.digits || 1}-digit, ${magnitude}, with ${flags.join(" and ")}`
    : `${vector.digits || 1}-digit, ${magnitude}`;
}
