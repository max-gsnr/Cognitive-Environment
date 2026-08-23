import { useEffect, useState } from "react";

import { AuditEntry, api } from "../api";

const LABELS: Record<string, string> = {
  profile_created: "Profile built from the interview",
  profile_updated: "A teacher changed the profile",
  note_added: "Development note added",
  problem_reported: "The child reported a problem",
  generation_started: "Devin started building a game",
  generation_completed: "Devin finished building a game",
  iteration_started: "Devin started reworking a game",
  iteration_completed: "Devin finished reworking a game",
  rollback: "Rolled back to an earlier version",
  posthog_seeded: "Demo telemetry seeded",
};

export function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<AuditEntry[]>("/audit-log")
      .then(setEntries)
      .catch((cause: Error) => setError(cause.message));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!entries) return <p className="muted">Loading…</p>;

  return (
    <>
      <h1>What happened, and why</h1>
      <ul className="plain">
        {entries.map((entry) => (
          <li key={entry.id} className="card">
            <div className="row">
              <span className="pill">{entry.actor}</span>
              <strong>{LABELS[entry.action] ?? entry.action}</strong>
              <span className="muted">{new Date(entry.created_at).toLocaleString()}</span>
            </div>
            {entry.payload && (
              <pre className="muted" style={{ whiteSpace: "pre-wrap", margin: 0 }}>
                {JSON.stringify(entry.payload, null, 2)}
              </pre>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}
