import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { GameState, GameSummary, Profile, ProfileDetail, api } from "../api";

const SKILLS = ["addition", "subtraction"] as const;

export function ProfilePage() {
  const { profileId = "" } = useParams();
  const [detail, setDetail] = useState<ProfileDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [iterating, setIterating] = useState<{ from: GameSummary; state: GameState } | null>(
    null,
  );

  const load = useCallback(() => {
    api
      .get<ProfileDetail>(`/profiles/${profileId}`)
      .then(setDetail)
      .catch((cause: Error) => setError(cause.message));
  }, [profileId]);

  useEffect(load, [load]);

  const patch = (change: Partial<Profile>) =>
    api.patch<Profile>(`/profiles/${profileId}`, change).then(load).catch((cause: Error) => setError(cause.message));

  const addNote = () =>
    api
      .post(`/profiles/${profileId}/notes`, { author: "teacher", note })
      .then(() => {
        setNote("");
        load();
      })
      .catch((cause: Error) => setError(cause.message));

  // Demo-only: seed the telemetry Devin will read, start the iteration session,
  // then poll it so the before/after lands on this page without a refresh.
  const runIteration = async (from: GameSummary) => {
    try {
      const started = await api.post<{ game_id: string }>(`/games/${from.id}/iterate`, {
        demo_mode: true,
      });
      let state = await api.get<GameState>(`/games/${started.game_id}/iterate/status`);
      setIterating({ from, state });
      while (state.status === "iterating") {
        await new Promise((resolve) => setTimeout(resolve, 10000));
        state = await api.get<GameState>(`/games/${state.game_id}/iterate/status`);
        setIterating({ from, state });
      }
      load();
    } catch (cause) {
      setError((cause as Error).message);
    }
  };

  const seedHistory = (skillId: string) =>
    api
      .post("/demo/seed-history", { profile_id: profileId, skill_id: skillId })
      .then(load)
      .catch((cause: Error) => setError(cause.message));

  const rollback = (gameId: string) =>
    api.post(`/games/${gameId}/rollback`).then(load).catch((cause: Error) => setError(cause.message));

  if (error) return <p className="error">{error}</p>;
  if (!detail) return <p className="muted">Loading…</p>;
  const { profile } = detail;

  const interestsString = Array.isArray(profile.interests)
    ? profile.interests.join(", ")
    : (profile.interests || "various games");

  return (
    <>
      <h1>{profile.name}</h1>
      <p className="muted">
        Age {profile.age} · likes {interestsString}
      </p>

      <div className="card">
        <h2>Where they are now</h2>
        <div className="mastery-list">
          {detail.mastery.map((row) => (
            <div key={row.skill_id} className="mastery-item-card">
              <div className="mastery-info">
                <div className="mastery-header-row">
                  <strong style={{ textTransform: "capitalize", fontSize: "18px" }}>{row.skill_id}</strong>
                  <span className="pill">Current Tier</span>
                </div>
                <div className="muted" style={{ marginTop: "4px", fontSize: "14px" }}>
                  {row.plain_language}
                </div>
              </div>
              <div className="mastery-actions">
                <Link to={`/play/${profile.id}/${row.skill_id}`}>
                  <button className="secondary">Play Game 🎮</button>
                </Link>
                <Link to={`/profiles/${profile.id}/generate/${row.skill_id}`}>
                  <button>Generate a game 🛠️</button>
                </Link>
                <button className="secondary" onClick={() => seedHistory(row.skill_id)}>
                  Seed practice history (demo)
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>Teacher settings</h2>
        <label>
          Leniency
          <span>How many rough answers before the game eases off.</span>
          <select
            value={profile.leniency_band}
            onChange={(event) => patch({ leniency_band: event.target.value as Profile["leniency_band"] })}
          >
            <option value="low">Low — ease off immediately</option>
            <option value="medium">Medium — after two</option>
            <option value="high">High — after three</option>
          </select>
        </label>
        <label>
          Restlessness means
          <select
            value={profile.restlessness_interpretation}
            onChange={(event) =>
              patch({
                restlessness_interpretation: event.target
                  .value as Profile["restlessness_interpretation"],
              })
            }
          >
            <option value="distraction">They have lost the thread</option>
            <option value="self_regulation">They are moving in order to think</option>
          </select>
        </label>
        <label>
          Questions per session
          <input
            type="number"
            min={4}
            max={20}
            defaultValue={profile.session_length}
            onBlur={(event) => patch({ session_length: Number(event.target.value) })}
          />
        </label>
        {SKILLS.map((skill) => (
          <label key={skill}>
            <span style={{ textTransform: "capitalize" }}>{skill} floor</span>
            <select
              value={profile.difficulty_floor[skill] ?? "single_digit"}
              onChange={(event) =>
                patch({
                  difficulty_floor: { ...profile.difficulty_floor, [skill]: event.target.value },
                })
              }
            >
              <option value="single_digit">Never below single digits</option>
              <option value="double_digit">Never below double digits</option>
              <option value="triple_digit">Never below triple digits</option>
            </select>
          </label>
        ))}
      </div>

      <div className="card">
        <h2>Development notes</h2>
        <textarea
          rows={2}
          value={note}
          placeholder="Rough week at home; keep sessions short."
          onChange={(event) => setNote(event.target.value)}
        />
        <p>
          <button onClick={addNote} disabled={!note.trim()}>
            Add note
          </button>
        </p>
        <ul className="plain">
          {detail.development_notes.map((entry) => (
            <li key={entry.id}>
              <span className="pill">{entry.author}</span> {entry.note}
              <div className="muted">{new Date(entry.created_at).toLocaleString()}</div>
            </li>
          ))}
        </ul>
      </div>

      <div className="card">
        <h2>Game versions</h2>
        {detail.games.length === 0 && <p className="muted">Nothing generated yet.</p>}
        <ul className="plain">
          {detail.games.map((game) => (
            <li key={game.id} className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <strong>
                  {game.skill_id} v{game.version}
                </strong>{" "}
                <span className="pill">{game.status}</span>{" "}
                {game.is_live && <span className="pill">live</span>}
                {game.pr_url && (
                  <div>
                    <a href={game.pr_url} target="_blank" rel="noreferrer">
                      pull request
                    </a>
                  </div>
                )}
              </div>
              <div className="row">
                {game.status === "ready" && (
                  <button className="secondary" onClick={() => runIteration(game)}>
                    Run iteration (demo)
                  </button>
                )}
                {!game.is_live && game.status === "ready" && (
                  <button className="secondary" onClick={() => rollback(game.id)}>
                    Make this the live version
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
        {iterating && <IterationPanel from={iterating.from} state={iterating.state} />}
      </div>

      <div className="card">
        <h2>Reported problems</h2>
        {detail.reported_problems.length === 0 && <p className="muted">None.</p>}
        <ul className="plain">
          {detail.reported_problems.map((problem) => (
            <li key={problem.id}>{problem.description}</li>
          ))}
        </ul>
      </div>
    </>
  );
}

function IterationPanel({ from, state }: { from: GameSummary; state: GameState }) {
  const report = state.test_report;
  return (
    <div className="card">
      <h3>
        Iteration to v{state.version} — {state.status}
        {state.devin_status ? ` (${state.devin_status})` : ""}
      </h3>
      {state.status === "iterating" && (
        <p className="muted">Devin is reading the telemetry itself. This takes a few minutes.</p>
      )}
      {report?.diagnosis && (
        <p>
          <strong>Diagnosis:</strong> {report.diagnosis}
        </p>
      )}
      <div className="diff">
        <div>
          <h3>Before (v{from.version})</h3>
          <p className="muted">{from.test_report?.summary ?? "The version the child played."}</p>
        </div>
        <div>
          <h3>After (v{state.version})</h3>
          <p className="muted">{report?.before_after_diff_summary ?? report?.summary ?? "Pending."}</p>
          <ul className="plain">
            {(report?.changes_made ?? []).map((change) => (
              <li key={change}>{change}</li>
            ))}
          </ul>
        </div>
      </div>
      {state.gate_results && (
        <p className="muted">
          Gates:{" "}
          {Object.entries(state.gate_results)
            .map(([gate, result]) => `${gate}: ${result}`)
            .join(" · ")}
        </p>
      )}
      {state.pr_url && (
        <a href={state.pr_url} target="_blank" rel="noreferrer">
          pull request
        </a>
      )}
    </div>
  );
}
