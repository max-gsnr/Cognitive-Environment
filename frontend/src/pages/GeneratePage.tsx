import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { GameState, api } from "../api";
import { THEMES } from "../game/OpenGameArena";

const GATES = [
  ["schema", "Question shapes are valid & strictly typed"],
  ["assertions", "No negatives, max 3 digits, bounded operands"],
  ["playthrough", "Playable headlessly with gentle error recovery"],
  ["render_accessibility", "No fast flashing, keyboard focus, high contrast"],
] as const;

export function GeneratePage() {
  const { profileId = "", skillId = "" } = useParams();
  const navigate = useNavigate();
  const [state, setState] = useState<GameState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [selectedTheme, setSelectedTheme] = useState("nebula");
  const [selectedVibe, setSelectedVibe] = useState("space");
  const [activeTab, setActiveTab] = useState<"quick" | "devin">("quick");
  const gameId = useRef<string | null>(null);

  useEffect(() => {
    if (!state || state.status === "ready" || state.status === "gates_failed") return;
    const timer = setInterval(() => {
      if (!gameId.current) return;
      api
        .get<GameState>(`/games/${gameId.current}/status`)
        .then(setState)
        .catch((cause: Error) => setError(cause.message));
    }, 5000);
    return () => clearInterval(timer);
  }, [state]);

  const handleQuickCreate = () => {
    navigate(`/play/${profileId}/${skillId}`);
  };

  const startDevinBuild = async () => {
    setStarting(true);
    setError(null);
    try {
      const created = await api.post<{ game_id: string; status: string }>("/games/generate", {
        profile_id: profileId,
        skill_id: skillId,
      });
      gameId.current = created.game_id;
      setState(await api.get<GameState>(`/games/${created.game_id}/status`));
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="generate-page">
      <h1>Create a {skillId} Space Odyssey for Leo 🚀</h1>
      <p className="muted">
        Launch a cosmic star-docking math game powered by OpenGame&apos;s Top-Down Arena skeleton.
      </p>

      {/* Tabs */}
      <div className="studio-tabs">
        <button
          type="button"
          className={`tab-btn ${activeTab === "quick" ? "active" : ""}`}
          onClick={() => setActiveTab("quick")}
        >
          ⚡ Instant Space Creator (Recommended)
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === "devin" ? "active" : ""}`}
          onClick={() => setActiveTab("devin")}
        >
          🤖 Cloud AI / Devin PR Generator
        </button>
      </div>

      {activeTab === "quick" ? (
        <div className="card studio-card">
          <h2>Space Customization Studio</h2>
          <p className="muted">
            Choose Leo&apos;s star system theme and sensory preferences, then launch the mission!
          </p>

          <div className="studio-grid">
            <div className="studio-field">
              <label>Select Star System / Theme:</label>
              <div className="theme-options">
                {Object.entries(THEMES).map(([key, t]) => (
                  <button
                    key={key}
                    type="button"
                    className={`theme-card ${selectedTheme === key ? "selected" : ""}`}
                    onClick={() => setSelectedTheme(key)}
                    style={{ borderColor: t.accentColor }}
                  >
                    <div className="theme-preview" style={{ backgroundColor: t.bgColor }}>
                      <span style={{ color: t.accentColor }}>✦</span>
                    </div>
                    <strong>{t.name}</strong>
                  </button>
                ))}
              </div>
            </div>

            <div className="studio-field">
              <label>Game Archetype / Skeleton:</label>
              <div className="radio-group">
                <label className="radio-label">
                  <input
                    type="radio"
                    name="vibe"
                    value="space"
                    checked={selectedVibe === "space"}
                    onChange={() => setSelectedVibe("space")}
                  />
                  <span>
                    <strong>Top-Down Cosmic Arena (OpenGame Arena)</strong>
                    <br />
                    <small className="muted">
                      Parallax starfield, ion thrusters, quantum docking hub, laser beams, and space station flair.
                    </small>
                  </span>
                </label>
              </div>
            </div>
          </div>

          <div className="quality-checklist">
            <h3>Automated Quality & Accessibility Gates:</h3>
            <ul className="gates-list">
              {GATES.map(([gate, label]) => (
                <li key={gate} className="gate-item">
                  <span className="gate-icon">✓</span>
                  <span>{label}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="studio-actions">
            <button className="primary launch-btn" onClick={handleQuickCreate}>
              🚀 Launch Space Mission
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="card">
            <p>
              Devin writes the game against Leo&apos;s profile, runs the gates, and opens a
              pull request. Nothing goes live until every gate passes.
            </p>
            <button
              onClick={startDevinBuild}
              disabled={starting || (!!state && state.status !== "gates_failed")}
            >
              {starting ? "Handing it to Devin…" : "Build via Devin"}
            </button>
            {error && <p className="error">{error}</p>}
          </div>

          {state && (
            <div className="card">
              <div className="row">
                <span className="pill">{state.status}</span>
                {state.devin_status && <span className="pill">devin: {state.devin_status}</span>}
                {state.devin_session_id && (
                  <a
                    href={`https://app.devin.ai/sessions/${state.devin_session_id.replace(
                      "devin-",
                      ""
                    )}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    watch the session
                  </a>
                )}
              </div>
              <ul className="plain">
                {GATES.map(([gate, label]) => {
                  const result = state.gate_results?.[gate];
                  return (
                    <li key={gate}>
                      <span className="pill">{result ?? "waiting"}</span> {label}
                    </li>
                  );
                })}
              </ul>
              {state.pr_url && (
                <p>
                  <a href={state.pr_url} target="_blank" rel="noreferrer">
                    Review the pull request
                  </a>
                </p>
              )}
              {state.status === "gates_failed" && (
                <p className="error">A gate failed, so this version was not shipped.</p>
              )}
              {state.status === "ready" && (
                <Link to={`/play/${profileId}/${skillId}`}>
                  <button className="primary">Play it</button>
                </Link>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
