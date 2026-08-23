import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Profile, ProfileDetail, api } from "../api";

const SKILLS = ["addition", "subtraction"] as const;

export function ProfilePage() {
  const { profileId = "" } = useParams();
  const [detail, setDetail] = useState<ProfileDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");

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

  const rollback = (gameId: string) =>
    api.post(`/games/${gameId}/rollback`).then(load).catch((cause: Error) => setError(cause.message));

  if (error) return <p className="error">{error}</p>;
  if (!detail) return <p className="muted">Loading…</p>;
  const { profile } = detail;

  return (
    <>
      <h1>{profile.name}</h1>
      <p className="muted">
        Age {profile.age} · likes {profile.interests.join(", ")}
      </p>

      <div className="card">
        <h2>Where they are now</h2>
        {detail.mastery.map((row) => (
          <div key={row.skill_id} className="row" style={{ justifyContent: "space-between" }}>
            <div>
              <strong style={{ textTransform: "capitalize" }}>{row.skill_id}</strong>
              <div className="muted">{row.plain_language}</div>
            </div>
            <div className="row">
              <Link to={`/play/${profile.id}/${row.skill_id}`}>
                <button className="secondary">Play</button>
              </Link>
              <Link to={`/profiles/${profile.id}/generate/${row.skill_id}`}>
                <button>Generate a game</button>
              </Link>
            </div>
          </div>
        ))}
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
              {!game.is_live && game.status === "ready" && (
                <button className="secondary" onClick={() => rollback(game.id)}>
                  Make this the live version
                </button>
              )}
            </li>
          ))}
        </ul>
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
