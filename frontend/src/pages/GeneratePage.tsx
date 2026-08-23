import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { GameState, ProfileDetail, api } from "../api";
import { THEMES, getThemeForInterests } from "../game/OpenGameArena";

const GATES = [
  ["schema", "Question shapes are valid & strictly typed"],
  ["assertions", "No negatives, max 3 digits, bounded operands"],
  ["playthrough", "Playable headlessly with gentle error recovery"],
  ["render_accessibility", "No fast flashing, keyboard focus, high contrast"],
] as const;

export function GeneratePage() {
  const { profileId = "", skillId = "" } = useParams();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<ProfileDetail | null>(null);
  const [state, setState] = useState<GameState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [selectedTheme, setSelectedTheme] = useState("nebula");
  const [activeTab, setActiveTab] = useState<"quick" | "devin">("quick");
  const gameId = useRef<string | null>(null);

  useEffect(() => {
    api
      .get<ProfileDetail>(`/profiles/${profileId}`)
      .then((d) => {
        setDetail(d);
        const autoTheme = getThemeForInterests(d.profile.interests);
        const key = Object.keys(THEMES).find((k) => THEMES[k].name === autoTheme.name) || "nebula";
        setSelectedTheme(key);
      })
      .catch((cause: Error) => setError(cause.message));
  }, [profileId]);

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

  const childName = detail?.profile.name || "Student";
  const childInterests = detail?.profile.interests || ["general games"];
  const currentThemeObj = THEMES[selectedTheme] || THEMES.nebula;

  return (
    <div className="generate-page">
      <header className="generate-header">
        <h1 style={{ textTransform: "capitalize" }}>
          Generate a {skillId} Game for {childName} 🎨
        </h1>
        <p className="muted">
          Tailored to {childName}&apos;s interests ({childInterests.join(", ")}) and cognitive profile using OpenGame&apos;s 60fps Arena engine.
        </p>
      </header>

      {/* Tabs */}
      <div className="studio-tabs">
        <button
          type="button"
          className={`tab-btn ${activeTab === "quick" ? "active" : ""}`}
          onClick={() => setActiveTab("quick")}
        >
          ⚡ Instant Game Launcher (Recommended)
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === "devin" ? "active" : ""}`}
          onClick={() => setActiveTab("devin")}
        >
          🤖 Autonomous Devin AI Generator
        </button>
      </div>

      {activeTab === "quick" ? (
        <div className="card studio-card">
          <h2>Game Customization Studio</h2>
          <p className="muted">
            Choose {childName}&apos;s preferred theme and launch their interactive learning arena:
          </p>

          <div className="studio-grid">
            <div className="studio-field">
              <label>Select Learning World & Theme:</label>
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
          </div>

          <div className="quality-checklist" style={{ marginTop: "20px" }}>
            <h3>Automated Quality & Accessibility Gates (Verified Safe for ADHD):</h3>
            <ul className="gates-list">
              {GATES.map(([gate, label]) => (
                <li key={gate} className="gate-item">
                  <span className="gate-icon">✓</span>
                  <span>{label}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="studio-actions" style={{ marginTop: "24px" }}>
            <button className="primary launch-btn" onClick={handleQuickCreate}>
              🎮 Launch {childName}&apos;s {currentThemeObj.name}
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="card">
            <h2>Autonomous Devin SWE Session</h2>
            <p className="muted">
              Devin ingests {childName}&apos;s cognitive profile and interests ({childInterests.join(", ")}), builds a custom Phaser 3 mini-game in <code>games/{profileId}/{skillId}/v1/</code>, headlessly verifies the 4 shipping gates, and opens a GitHub pull request.
            </p>
            <button
              className="primary"
              onClick={startDevinBuild}
              disabled={starting || (!!state && state.status !== "gates_failed")}
            >
              {starting ? "Spawning Devin Session…" : `🚀 Dispatch Devin to Build ${skillId} Game`}
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
                    view devin session
                  </a>
                )}
                {state.pr_url && (
                  <a href={state.pr_url} target="_blank" rel="noreferrer">
                    pull request
                  </a>
                )}
              </div>
              {state.test_report && (
                <div style={{ marginTop: "16px" }}>
                  <strong>Devin SWE Summary:</strong>
                  <p>{state.test_report.summary}</p>
                </div>
              )}
              {state.gate_results && (
                <div style={{ marginTop: "16px" }}>
                  <strong>Gate Verification Results:</strong>
                  <dl className="teacher-view">
                    {Object.entries(state.gate_results).map(([gate, verdict]) => (
                      <div key={gate} style={{ display: "contents" }}>
                        <dt>{gate}</dt>
                        <dd>{String(verdict)}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}
              {state.status === "ready" && (
                <div style={{ marginTop: "20px" }}>
                  <Link to={`/play/${profileId}/${skillId}`}>
                    <button className="primary">Play Devin&apos;s Generated Game 🎮</button>
                  </Link>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
