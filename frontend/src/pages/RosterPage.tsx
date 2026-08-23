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
  if (!profiles) return <p className="muted">Loading…</p>;

  return (
    <>
      <h1>Children</h1>
      {profiles.length === 0 && (
        <div className="card">
          <p>No children yet.</p>
          <Link to="/intake">
            <button>Start an intake interview</button>
          </Link>
        </div>
      )}
      <ul className="plain">
        {profiles.map((profile) => (
          <li key={profile.id} className="card">
            <div className="row">
              <strong>{profile.name}</strong>
              <span className="muted">age {profile.age}</span>
              <span className="pill">{profile.leniency_band} leniency</span>
              <span className="pill">{profile.session_length} questions a session</span>
            </div>
            <p className="muted">{profile.interests.join(", ")}</p>
            <Link to={`/profiles/${profile.id}`}>Open profile</Link>
          </li>
        ))}
      </ul>
    </>
  );
}
