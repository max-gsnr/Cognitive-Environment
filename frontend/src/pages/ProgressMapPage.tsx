import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Profile, ProgressMap, api } from "../api";
import "./progressmap.css";

const STATUS_LABEL: Record<string, string> = {
  mastered: "Mastered",
  active: "Exploring",
  unlocked: "Ready to start",
  locked: "Locked",
};

export function ProgressMapPage() {
  const [profiles, setProfiles] = useState<Profile[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [map, setMap] = useState<ProgressMap | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Profile[]>("/profiles")
      .then((rows) => {
        setProfiles(rows);
        if (rows.length > 0) setSelected((current) => current ?? rows[0].id);
      })
      .catch((cause: Error) => setError(cause.message));
  }, []);

  useEffect(() => {
    if (!selected) return;
    setMap(null);
    api
      .get<ProgressMap>(`/profiles/${selected}/progress-map`)
      .then(setMap)
      .catch((cause: Error) => setError(cause.message));
  }, [selected]);

  if (error) return <p className="error">{error}</p>;
  if (!profiles) return <p className="muted">Loading the map…</p>;
  if (profiles.length === 0) {
    return (
      <div className="card">
        <p>No students yet — onboard one to start the journey.</p>
        <Link to="/intake">
          <button className="primary">Start an AI Intake Interview</button>
        </Link>
      </div>
    );
  }

  return (
    <div className="progress-map-container">
      <div className="roster-header-row">
        <div>
          <h1>🗺️ Progress Map</h1>
          <p className="muted">
            Each topic is an island. Crossing an island is climbing its difficulty
            ladder; getting far enough builds the bridge to the next topic.
          </p>
        </div>
        <select
          value={selected ?? ""}
          onChange={(event) => setSelected(event.target.value)}
          className="progress-map-student-select"
        >
          {profiles.map((profile) => (
            <option key={profile.id} value={profile.id}>
              {profile.name} (age {profile.age})
            </option>
          ))}
        </select>
      </div>

      {!map ? (
        <p className="muted">Charting {profiles.find((p) => p.id === selected)?.name}’s journey…</p>
      ) : (
        <>
          <p className="muted">
            {map.journey.mastered} of {map.journey.total} islands mastered
            {map.journey.current ? ` — currently exploring ${map.journey.current}` : ""}
          </p>
          <div className="island-path">
            {map.islands.map((island, index) => (
              <div key={island.skill_id} className="island-step">
                <div className={`island-card card island-${island.status}`}>
                  <div className="island-emoji" aria-hidden="true">
                    {island.status === "locked" ? "🔒" : island.emoji}
                  </div>
                  <h2>{island.label}</h2>
                  <span className={`pill island-pill-${island.status}`}>
                    {STATUS_LABEL[island.status] ?? island.status}
                  </span>
                  <div className="island-progress-track" title={`${Math.round(island.progress * 100)}% across`}>
                    <div
                      className="island-progress-fill"
                      style={{ width: `${Math.round(island.progress * 100)}%` }}
                    />
                  </div>
                  <p className="muted island-tier">
                    {island.status === "locked"
                      ? "Cross the previous island to unlock"
                      : island.tier_label ??
                        (island.playable ? "Not started yet" : "Coming soon")}
                  </p>
                  {island.status !== "locked" && (
                    <p className="muted island-stats">
                      Camp {island.tier_index + 1} of {island.tier_count}
                      {island.recent_accuracy != null &&
                        ` · ${Math.round(island.recent_accuracy * 100)}% recent`}
                      {island.streak > 1 && ` · 🔥 ${island.streak} streak`}
                    </p>
                  )}
                  {island.playable && selected && island.status !== "locked" && (
                    <Link to={`/play/${selected}/${island.skill_id}`}>
                      <button className="secondary">Play →</button>
                    </Link>
                  )}
                </div>
                {index < map.islands.length - 1 && (
                  <div
                    className="island-bridge"
                    title={`Bridge ${Math.round(island.bridge_to_next * 100)}% built`}
                  >
                    <div
                      className="island-bridge-fill"
                      style={{ width: `${Math.round(island.bridge_to_next * 100)}%` }}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
