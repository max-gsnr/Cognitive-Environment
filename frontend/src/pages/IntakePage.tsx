import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api";

type Turn = { intake_id: string; question: string; input_type: "choice" | "text"; choices: string[] | null; complete: boolean };

export function IntakePage() {
  const navigate = useNavigate();
  const [turn, setTurn] = useState<Turn | null>(null);
  const [answer, setAnswer] = useState("");
  const [asked, setAsked] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [age, setAge] = useState("7");

  async function guard<T>(work: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setError(null);
    try {
      return await work();
    } catch (cause) {
      setError((cause as Error).message);
      return undefined;
    } finally {
      setBusy(false);
    }
  }

  const start = () =>
    guard(async () => {
      const first = await api.post<Turn>("/intake/start");
      setTurn(first);
      setAsked(1);
    });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!turn || !answer.trim()) return;
    void guard(async () => {
      const next = await api.post<Turn>(`/intake/${turn.intake_id}/answer`, { answer });
      setTurn(next);
      setAnswer("");
      if (!next.complete) setAsked((count) => count + 1);
    });
  };

  const finalize = () =>
    guard(async () => {
      if (!turn) return;
      const created = await api.post<{ profile_id: string }>(
        `/intake/${turn.intake_id}/finalize`,
        { name, age: Number(age) },
      );
      navigate(`/profiles/${created.profile_id}`);
    });

  if (!turn) {
    return (
      <>
        <h1>Intake interview</h1>
        <div className="card">
          <p>
            One question at a time, branching on what you say. It runs for at least ten
            questions — there is no profile until the interview is finished.
          </p>
          <button onClick={start} disabled={busy}>
            {busy ? "Starting…" : "Start"}
          </button>
          {error && <p className="error">{error}</p>}
        </div>
      </>
    );
  }

  if (turn.complete) {
    return (
      <>
        <h1>Almost there</h1>
        <div className="card">
          <label>
            Child&apos;s name
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            Age
            <input
              type="number"
              min={4}
              max={12}
              value={age}
              onChange={(event) => setAge(event.target.value)}
            />
          </label>
          <button onClick={finalize} disabled={busy || !name.trim()}>
            {busy ? "Building the profile…" : "Build the profile"}
          </button>
          {error && <p className="error">{error}</p>}
        </div>
      </>
    );
  }

  return (
    <>
      <h1>Intake interview</h1>
      <p className="muted">Question {asked}</p>
      <form className="card" onSubmit={submit}>
        <p style={{ fontSize: 20 }}>{turn.question}</p>
        {turn.input_type === "choice" && turn.choices ? (
          <div className="row">
            {turn.choices.map((choice) => (
              <button
                key={choice}
                type="button"
                className={choice === answer ? "" : "secondary"}
                onClick={() => setAnswer(choice)}
              >
                {choice}
              </button>
            ))}
          </div>
        ) : (
          <textarea
            rows={3}
            value={answer}
            onChange={(event) => setAnswer(event.target.value)}
          />
        )}
        <p>
          <button type="submit" disabled={busy || !answer.trim()}>
            {busy ? "Thinking…" : "Next"}
          </button>
        </p>
        {error && <p className="error">{error}</p>}
      </form>
    </>
  );
}
