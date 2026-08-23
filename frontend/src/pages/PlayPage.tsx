import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { AttemptResult, DifficultyVector, ProfileDetail, Question, api } from "../api";
import { capture } from "../telemetry";

const ENCOURAGEMENT = ["Close — try that one again.", "Have another go.", "Nearly. One more try."];

export function PlayPage() {
  const { profileId = "", skillId = "" } = useParams();
  const [detail, setDetail] = useState<ProfileDetail | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<{ text: string; retry: boolean } | null>(null);
  const [answered, setAnswered] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [problem, setProblem] = useState("");
  const [teacherView, setTeacherView] = useState(false);
  const [lastResult, setLastResult] = useState<AttemptResult | null>(null);
  const shownAt = useRef<number>(Date.now());

  const liveGame = detail?.games.find((game) => game.skill_id === skillId && game.is_live) ?? null;
  const sessionLength = detail?.profile.session_length ?? 10;

  const draw = useCallback(async () => {
    const next = await api.get<Question>(`/profiles/${profileId}/skills/${skillId}/next-question`);
    setQuestion(next);
    setAnswer("");
    shownAt.current = Date.now();
    capture("problem_shown", {
      profile_id: profileId,
      skill_id: skillId,
      operands: next.operands,
      difficulty_vector: next.difficulty_vector_snapshot,
    });
  }, [profileId, skillId]);

  useEffect(() => {
    api
      .get<ProfileDetail>(`/profiles/${profileId}`)
      .then(setDetail)
      .catch((cause: Error) => setError(cause.message));
    draw().catch((cause: Error) => setError(cause.message));
    capture("level_started", { profile_id: profileId, skill_id: skillId });
  }, [draw, profileId, skillId]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!question || answer.trim() === "") return;
    const latency = Date.now() - shownAt.current;
    try {
      // Correctness and difficulty both belong to the backend; the shell only asks.
      const result = await api.post<AttemptResult>("/attempts", {
        profile_id: profileId,
        skill_id: skillId,
        operands: question.operands,
        operator: question.operator,
        answer_given: Number(answer),
        latency_to_submit_ms: latency,
      });
      capture("answer_submitted", {
        profile_id: profileId,
        skill_id: skillId,
        attempt_id: result.attempt_id,
        is_correct: result.is_correct,
        error_class: result.error_class,
        latency_to_submit_ms: latency,
      });
      setLastResult(result);
      setAnswered((count) => count + 1);
      if (result.is_correct) {
        setFeedback({ text: "Yes!", retry: false });
        await draw();
      } else {
        setFeedback({
          text: ENCOURAGEMENT[answered % ENCOURAGEMENT.length],
          retry: true,
        });
        setAnswer("");
        if (!result.repeat_tier) await draw();
        shownAt.current = Date.now();
      }
    } catch (cause) {
      setError((cause as Error).message);
    }
  };

  const report = () => {
    if (!liveGame) return;
    api
      .post(`/games/${liveGame.id}/report-problem`, { description: problem })
      .then(() => setProblem(""))
      .catch((cause: Error) => setError(cause.message));
  };

  const teacherPanel = teacherView && (
    <div className="card">
      <h2>Teacher view</h2>
      <p className="muted">Only a grown-up sees this. The child's screen is unchanged.</p>
      <dl className="teacher-view">
        <dt>This question</dt>
        <dd>
          {question
            ? `${question.operands[0]} ${question.operator} ${question.operands[1]} = ${question.correct_answer}`
            : "nothing drawn yet"}
        </dd>
        <dt>Difficulty now</dt>
        <dd>
          {describeVector(
            lastResult?.updated_difficulty_vector ?? question?.difficulty_vector_snapshot,
          )}
        </dd>
        <dt>Last answer</dt>
        <dd>{lastResult ? `${lastResult.error_class} \u2192 ${lastResult.movement}` : "nothing yet"}</dd>
        <dt>Usual pace</dt>
        <dd>
          {lastResult?.baseline_ms
            ? `${Math.round(lastResult.baseline_ms / 100) / 10}s at this tier`
            : "not enough attempts yet"}
        </dd>
        <dt>Live game</dt>
        <dd>{liveGame ? `v${liveGame.version}` : "none generated yet"}</dd>
      </dl>
    </div>
  );

  const teacherToggle = (
    <p>
      <button className="secondary" onClick={() => setTeacherView((on) => !on)}>
        {teacherView ? "Hide teacher view" : "Teacher view"}
      </button>
    </p>
  );

  if (error) return <p className="error">{error}</p>;

  if (liveGame?.code_path) {
    return (
      <>
        <h1 style={{ textTransform: "capitalize" }}>{skillId}</h1>
        <iframe
          title="Orbit game"
          src={`/${liveGame.code_path}`}
          style={{ width: "100%", height: 640, border: "1px solid #e3e6ef", borderRadius: 12 }}
        />
        <div className="card">
          <label>
            Something wrong with the game?
            <input value={problem} onChange={(event) => setProblem(event.target.value)} />
          </label>
          <button className="secondary" onClick={report} disabled={!problem.trim()}>
            Tell a grown-up
          </button>
        </div>
        {teacherToggle}
        {teacherPanel}
      </>
    );
  }

  return (
    <>
      <div className="play card">
        <p className="muted">
          {Math.min(answered + 1, sessionLength)} of {sessionLength}
        </p>
        {question && (
          <form onSubmit={submit}>
            <div className="sum">
              {question.operands[0]} {question.operator} {question.operands[1]}
            </div>
            <input
              inputMode="numeric"
              autoFocus
              aria-label="Your answer"
              value={answer}
              onChange={(event) => setAnswer(event.target.value.replace(/[^0-9]/g, ""))}
            />
            <p>
              <button type="submit" disabled={answer.trim() === ""}>
                Check
              </button>
            </p>
          </form>
        )}
        <div className={feedback?.retry ? "feedback retry" : "feedback"}>{feedback?.text}</div>
      </div>
      <p className="muted">
        There is no way to lose here. Wrong answers just come back around.
      </p>
      {teacherToggle}
      {teacherPanel}
    </>
  );
}

function describeVector(vector: DifficultyVector | undefined): string {
  if (!vector) return "unknown";
  const flags = [
    vector.carries && "carrying",
    vector.borrows && "borrowing",
    vector.zero_in_minuend && "zeros to borrow across",
  ].filter(Boolean);
  const magnitude = vector.magnitude.replace(/_/g, " ");
  return flags.length
    ? `${vector.digits}-digit, ${magnitude}, with ${flags.join(" and ")}`
    : `${vector.digits}-digit, ${magnitude}`;
}
