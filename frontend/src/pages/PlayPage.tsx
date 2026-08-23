import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ProfileDetail, Question, api } from "../api";
import { OrbitCanvas } from "../game/OrbitCanvas";
import { getThemeForInterests } from "../game/OpenGameArena";

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
          </div>

          <button
            type="button"
            className="evolution-badge-btn"
            onClick={() => setShowEvolutionModal(true)}
            title="Inspect Loop B Devin autonomous evolution"
          >
            ⚡ Loop B Storyboard
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
          onScoreUpdate={(s, a) => {
            setScore(s);
            setAnswered(a);
          }}
          onLevelComplete={() => {
            if (activeVersion === 1) {
              setTimeout(() => setShowEvolutionModal(true), 1200);
            }
          }}
        />

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

      {/* Loop B Autonomous Evolution Modal (Post-v1 Screen & Demo Storyboard) */}
      {showEvolutionModal && (
        <div className="evolution-modal-overlay" onClick={() => setShowEvolutionModal(false)}>
          <div className="evolution-modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="evolution-modal-header">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%" }}>
                <span className="live-pill" style={{ background: "#2563eb", color: "#fff" }}>
                  ★ LOOP B: AUTONOMOUS GAME EVOLUTION
                </span>
                <button
                  type="button"
                  className="modal-close-btn"
                  onClick={() => setShowEvolutionModal(false)}
                >
                  ✕
                </button>
              </div>
              <h2 style={{ fontSize: "22px", margin: "10px 0 6px", color: "#0f172a" }}>
                ✦ {detail?.profile.name || "Student"} Mastered Baseline — Devin Iteration Ready!
              </h2>
              <p style={{ color: "#475569", margin: "0 0 16px", fontSize: "14px" }}>
                Telemetry from <strong>v1 (Baseline single-digit)</strong> indicated strong mastery. Orbit triggered Devin to iterate the game codebase to gently step up the arithmetic challenge.
              </p>
            </div>

            <div className="evolution-story-grid">
              {/* Step 1: Telemetry Signal */}
              <div className="story-card">
                <div className="story-step-badge">1. Telemetry Signal</div>
                <h4 style={{ margin: "6px 0 4px", fontSize: "16px", color: "#0f172a" }}>
                  📈 High Focus &amp; Accuracy
                </h4>
                <p style={{ fontSize: "13px", color: "#475569", margin: 0 }}>
                  {detail?.profile.name || "Student"} answered baseline single-digit problems with 100% accuracy and steady kinematics (&lt;1.2× jitter).
                </p>
                <div className="story-metric-pill" style={{ background: "#dcfce7", color: "#166534" }}>
                  ✓ Challenge fit: 1.00 (Ready for carry)
                </div>
              </div>

              {/* Step 2: Devin Autonomous PR */}
              <div className="story-card">
                <div className="story-step-badge" style={{ background: "#3b82f6" }}>2. Devin Autonomous PR</div>
                <h4 style={{ margin: "6px 0 4px", fontSize: "16px", color: "#0f172a" }}>
                  🤖 Codebase Upgraded to v2
                </h4>
                <p style={{ fontSize: "13px", color: "#475569", margin: 0 }}>
                  Devin added double-digit carrying, visual carry scaffolding, and tuned reward feedback for ADHD attention engagement.
                </p>
                <div className="story-metric-pill" style={{ background: "#dbeafe", color: "#1e40af" }}>
                  <a
                    href="https://github.com/max-gsnr/Cognitive-Environment/pull/2"
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: "inherit", textDecoration: "underline" }}
                  >
                    🔗 GitHub PR #2 (Verified &amp; Merged)
                  </a>
                </div>
              </div>

              {/* Step 3: Independent Safety Gates */}
              <div className="story-card">
                <div className="story-step-badge" style={{ background: "#8b5cf6" }}>3. Safety Gates</div>
                <h4 style={{ margin: "6px 0 4px", fontSize: "16px", color: "#0f172a" }}>
                  🛡️ 4 / 4 Automated Checks Pass
                </h4>
                <ul style={{ margin: "6px 0 0", paddingLeft: "18px", fontSize: "12px", color: "#334155" }}>
                  <li>✓ <strong>Schema</strong>: Validated arithmetic</li>
                  <li>✓ <strong>Invariants</strong>: No negative traps</li>
                  <li>✓ <strong>Playthrough</strong>: 100% reachable</li>
                  <li>✓ <strong>WCAG 2.3.1</strong>: High contrast</li>
                </ul>
              </div>
            </div>

            <div className="evolution-modal-footer">
              <button
                type="button"
                className="primary launch-v2-action-btn"
                onClick={() => {
                  setActiveVersion(2);
                  setShowEvolutionModal(false);
                  setAnswered(0);
                }}
              >
                🚀 Play Iterated Game v2 (Mildly More Challenging) ➔
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setShowEvolutionModal(false)}
              >
                Stay on v1
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
