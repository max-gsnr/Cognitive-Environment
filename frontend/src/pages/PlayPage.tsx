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
    </div>
  );
}
