import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { AttemptResult, ProfileDetail, Question, api } from "../api";
import { OrbitCanvas } from "../game/OrbitCanvas";
import { getThemeForInterests } from "../game/OpenGameArena";
import { EvolutionLog } from "../analytics/EvolutionLog";

export function PlayPage() {
  const { profileId = "", skillId = "" } = useParams();
  const [detail, setDetail] = useState<ProfileDetail | null>(null);
  const [, setQuestion] = useState<Question | null>(null);
  const [answered, setAnswered] = useState(0);
  const [, setScore] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [problem, setProblem] = useState("");
  const [showReport, setShowReport] = useState(false);
  const [activeVersion, setActiveVersion] = useState<number>(2);
  const [lastResult, setLastResult] = useState<AttemptResult | null>(null);
  const [showEvolutionModal, setShowEvolutionModal] = useState<boolean>(false);

  const availableGames = detail?.games.filter((g) => g.skill_id === skillId) ?? [];
  const selectedGame = availableGames.find((g) => g.version === activeVersion) ?? availableGames[0] ?? null;
  const sessionLength = detail?.profile.session_length ?? 5;
  const activeTheme = getThemeForInterests(detail?.profile.interests);

  useEffect(() => {
    api
      .get<ProfileDetail>(`/profiles/${profileId}`)
      .then((data) => {
        setDetail(data);
        const live = data.games.find((g) => g.skill_id === skillId && g.is_live);
        if (live) {
          setActiveVersion(live.version);
        }
      })
      .catch((cause: Error) => setError(cause.message));
  }, [profileId, skillId]);

  const report = () => {
    const gameId = selectedGame?.id || "orbit-game-client";
    api
      .post(`/games/${gameId}/report-problem`, { description: problem })
      .then(() => {
        setProblem("");
        setShowReport(false);
      })
      .catch((cause: Error) => setError(cause.message));
  };

  if (error) return <p className="error">{error}</p>;

  return (
    <div className="play-page-layout">
      <div className="play-header">
        <div className="play-header-left">
          <Link to={`/profiles/${profileId}`} className="back-to-profile-link" title="Back to profile">
            ← {detail?.profile.name || "Student"}&apos;s Profile
          </Link>
          <h1 style={{ textTransform: "capitalize", margin: "4px 0 0" }}>
            {detail?.profile.name || "Student"}&apos;s {skillId} Mission — {activeTheme.name}
          </h1>
        </div>

        <div className="play-header-controls">
          {/* Version Switcher for Demo */}
          <div className="version-switcher-group" role="group" aria-label="Game Version">
            <button
              type="button"
              className={`version-tab-btn ${activeVersion === 1 ? "is-active" : ""}`}
              onClick={() => setActiveVersion(1)}
              title="Play baseline version 1"
            >
              v1 (Baseline)
            </button>
            <button
              type="button"
              className={`version-tab-btn ${activeVersion === 2 ? "is-active" : ""}`}
              onClick={() => setActiveVersion(2)}
              title="Play Devin post-iteration version 2"
            >
              v2 (Devin Iterated 🚀)
            </button>
            <button
              type="button"
              className={`version-tab-btn ${activeVersion === 3 ? "is-active" : ""}`}
              onClick={() => setActiveVersion(3)}
              title="Play Devin candidate version 3"
            >
              v3 (Candidate ⚡)
            </button>
          </div>

          <button
            type="button"
            className="evolution-badge-btn"
            onClick={() => setShowEvolutionModal(true)}
            title="Inspect Loop B Devin autonomous evolution build log"
          >
            ⚡ Loop B Build Log
          </button>

          <div className="hud-badge">
            ✦ {answered} / {sessionLength} Completed
          </div>
        </div>
      </div>

      {/* Main Centered Arcade Game View */}
      <div className="play-center-wrapper">
        <OrbitCanvas
          key={`${profileId}-${skillId}-v${activeVersion}`}
          profileId={profileId}
          skillId={skillId}
          interests={detail?.profile.interests}
          sessionLength={sessionLength}
          gameId={selectedGame?.id ?? null}
          gameVersion={activeVersion}
          onQuestionLoaded={(q) => setQuestion(q)}
          onAttemptResult={(res) => setLastResult(res)}
          onScoreUpdate={(s, a) => {
            setScore(s);
            setAnswered(a);
          }}
          onLevelComplete={() => {
            setTimeout(() => setShowEvolutionModal(true), 1000);
          }}
        />

        {/* Live Loop A Telemetry Strip */}
        <div className="loop-a-telemetry-strip">
          <div className="loop-a-title">
            <span className="live-pulse"></span>
            <strong>LOOP A (Adaptive Arithmetic &amp; Biometrics):</strong>
          </div>
          {lastResult ? (
            <div className="loop-a-stats">
              <span className={`telemetry-chip ${lastResult.is_correct ? "is-correct" : "is-wrong"}`}>
                {lastResult.is_correct ? "✓ Correct" : "✗ Incorrect"} ({lastResult.error_class || "clean"})
              </span>
              <span className="telemetry-chip">
                <strong>Rating:</strong> {lastResult.ability_rating ? Math.round(lastResult.ability_rating) : "1400"}
              </span>
              <span className="telemetry-chip">
                <strong>Adapted Tier:</strong> {lastResult.updated_difficulty_vector.digits}D {lastResult.updated_difficulty_vector.magnitude}
                {lastResult.updated_difficulty_vector.carries ? " (carries)" : ""}
              </span>
              <span className="telemetry-chip">
                <strong>Movement:</strong> {lastResult.movement || "hold"}
              </span>
              {lastResult.jitter_ratio !== null && lastResult.jitter_ratio !== undefined && (
                <span className="telemetry-chip">
                  <strong>Jitter:</strong> {lastResult.jitter_ratio}×
                </span>
              )}
            </div>
          ) : (
            <div className="loop-a-stats muted">
              <span>Answer a problem above to see real-time ability adaptation &amp; biometrics update live.</span>
            </div>
          )}
        </div>

        {/* Clean Problem Reporting Toggle */}
        <div className="play-footer-actions">
          {!showReport ? (
            <button
              type="button"
              className="text-btn report-toggle-btn"
              onClick={() => setShowReport(true)}
            >
              💬 Report an issue with this question
            </button>
          ) : (
            <div className="card report-card-inline">
              <label>
                <strong>Something unexpected happened?</strong>
                <input
                  value={problem}
                  onChange={(event) => setProblem(event.target.value)}
                  placeholder="Tell us what happened with the star pod or question..."
                />
              </label>
              <div className="row" style={{ marginTop: "8px", gap: "8px" }}>
                <button className="primary" onClick={report} disabled={!problem.trim()}>
                  Submit Report
                </button>
                <button className="secondary" onClick={() => setShowReport(false)}>
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Loop B Autonomous Evolution Modal (Game Build Log Console) */}
      {showEvolutionModal && (
        <div className="evolution-modal-overlay" onClick={() => setShowEvolutionModal(false)}>
          <div
            className="evolution-modal-card"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: "1160px", width: "95vw", maxHeight: "90vh", overflowY: "auto" }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span className="live-pill" style={{ background: "#2563eb", color: "#fff" }}>
                  ★ LOOP B: AUTONOMOUS GAME EVOLUTION
                </span>
                <span style={{ fontSize: "14px", color: "#64748b" }}>
                  {detail?.profile.name}&apos;s {skillId} build history
                </span>
              </div>
              <button
                type="button"
                className="modal-close-btn"
                onClick={() => setShowEvolutionModal(false)}
              >
                ✕
              </button>
            </div>

            <EvolutionLog profileId={profileId} skillId={skillId} />

            <div className="evolution-modal-footer">
              {activeVersion !== 2 && (
                <button
                  type="button"
                  className="primary launch-v2-action-btn"
                  onClick={() => {
                    setActiveVersion(2);
                    setShowEvolutionModal(false);
                    setAnswered(0);
                  }}
                >
                  🚀 Switch &amp; Play Iterated Game v2 ➔
                </button>
              )}
              <button
                type="button"
                className="secondary"
                onClick={() => setShowEvolutionModal(false)}
              >
                Close Log
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
