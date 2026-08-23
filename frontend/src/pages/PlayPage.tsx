import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { AttemptResult, DifficultyVector, ProfileDetail, Question, api } from "../api";
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

  const teacherPanel = teacherView && (
    <div className="card teacher-card">
      <h2>Teacher Telemetry & Adaptive Inspector</h2>
      <p className="muted">Live diagnostic stream from Orbit's deterministic adaptation engine.</p>
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
        <dt>Usual Pace (Baseline)</dt>
        <dd>
          {lastResult?.baseline_ms
            ? `${Math.round(lastResult.baseline_ms / 100) / 10}s at this tier`
            : "Accumulating baseline samples"}
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
        {teacherView ? "Hide teacher telemetry" : "Teacher Telemetry Inspector"}
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
      {teacherPanel}
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
