import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { GameState, api } from "../api";

const GATES = [
  ["schema", "Question shapes are valid"],
  ["assertions", "No negatives, nothing over three digits"],
  ["playthrough", "Played three questions headlessly, one wrong on purpose"],
  ["render_accessibility", "No fast flashing, focus visible, contrast readable"],
] as const;

export function GeneratePage() {
  const { profileId = "", skillId = "" } = useParams();
  const [state, setState] = useState<GameState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
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

  const start = async () => {
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
    <>
      <h1>Build a {skillId} game</h1>
      <div className="card">
        <p>
          Devin writes the game against this child&apos;s profile, runs the gates, and opens
          a pull request. Nothing goes live until every gate passes.
        </p>
        <button onClick={start} disabled={starting || (!!state && state.status !== "gates_failed")}>
          {starting ? "Handing it to Devin…" : "Build it"}
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
                href={`https://app.devin.ai/sessions/${state.devin_session_id.replace("devin-", "")}`}
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
              <button>Play it</button>
            </Link>
          )}
        </div>
      )}
    </>
  );
}
