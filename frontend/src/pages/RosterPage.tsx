import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Profile, api } from "../api";

export function RosterPage() {
  const [profiles, setProfiles] = useState<Profile[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Profile[]>("/profiles")
      .then(setProfiles)
      .catch((cause: Error) => setError(cause.message));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!profiles) return <p className="muted">Loading student roster…</p>;

  return (
    <div className="roster-container">
      <div className="roster-header-row">
        <div>
          <h1>Student Profiles</h1>
          <p className="muted">
            Manage neurodivergent learning profiles, cognitive constraints, and generated games.
          </p>
        </div>
        <Link to="/intake">
          <button className="primary">➕ Onboard Student (AI Akinator)</button>
        </Link>
      </div>

      {profiles.length === 0 ? (
        <div className="card">
          <p>No student profiles yet.</p>
          <Link to="/intake">
            <button className="primary">Start an AI Intake Interview</button>
          </Link>
        </div>
      ) : (
        <ul className="plain roster-grid">
          {profiles.map((profile) => (
            <li key={profile.id} className="card roster-card">
              <div className="row">
                <strong style={{ fontSize: "19px" }}>{profile.name}</strong>
                <span className="muted">age {profile.age}</span>
                <span className="pill">{profile.leniency_band} leniency</span>
                <span className="pill">{profile.session_length} questions/session</span>
              </div>
              <p className="muted" style={{ margin: "10px 0 14px" }}>
                <strong>Interests:</strong>{" "}
                {Array.isArray(profile.interests)
                  ? profile.interests.join(", ")
                  : (profile.interests || "general games")}
              </p>
              <div className="roster-card-actions">
                <Link to={`/profiles/${profile.id}`}>
                  <button className="secondary">Inspect Profile & Games →</button>
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
