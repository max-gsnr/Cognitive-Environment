import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

type Turn = {
  intake_id: string;
  question: string;
  input_type: "choice" | "text";
  choices: string[] | null;
  complete: boolean;
};

const SUGGESTED_INTERESTS = [
  "Outer Space 🚀",
  "Horses 🐴",
  "Tennis 🎾",
  "Dinosaurs 🦕",
  "Trains 🚂",
  "Ocean Life 🌊",
  "Baking 🍕",
  "Robots 🤖",
  "Legos & Building 🧱",
  "Art & Drawing 🎨",
];

export function IntakePage() {
  const navigate = useNavigate();

  // Wizard Stage: "setup" (Name/Age/Neurodivergence/Interests) | "akinator" (Dynamic AI Questions) | "complete"
  const [stage, setStage] = useState<"setup" | "akinator" | "complete">("setup");

  // Initial General Info
  const [name, setName] = useState("");
  const [age, setAge] = useState("8");
  const [neurodivergence, setNeurodivergence] = useState("ADHD - Combined Type");
  const [interests, setInterests] = useState("");

  // Dynamic Akinator State
  const [turn, setTurn] = useState<Turn | null>(null);
  const [selectedChoice, setSelectedChoice] = useState("");
  const [customAnswer, setCustomAnswer] = useState("");
  const [questionCount, setQuestionCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Quick tag adder for interests
  const addInterestTag = (tag: string) => {
    const cleanTag = tag.replace(/[^a-zA-Z\s]/g, "").trim();
    if (!interests) {
      setInterests(cleanTag);
    } else if (!interests.toLowerCase().includes(cleanTag.toLowerCase())) {
      setInterests(`${interests}, ${cleanTag}`);
    }
  };

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

  // Start the Akinator after collecting general info
  const handleStartAkinator = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Please enter the child's name.");
      return;
    }

    void guard(async () => {
      const firstTurn = await api.post<Turn>("/intake/start", {
        name: name.trim(),
        age: Number(age) || 8,
        neurodivergence,
        interests: interests.trim(),
      });

      setTurn(firstTurn);
      setQuestionCount(1);
      setStage("akinator");
    });
  };

  // Submit answer to the current Akinator question
  const handleAnswerSubmit = (e?: FormEvent) => {
    if (e) e.preventDefault();
    if (!turn) return;

    const answerText = customAnswer.trim() || selectedChoice.trim();
    if (!answerText) return;

    const currentCount = questionCount;
    void guard(async () => {
      const next = await api.post<Turn>(`/intake/${turn.intake_id}/answer`, {
        answer: answerText,
      });

      setSelectedChoice("");
      setCustomAnswer("");

      if (next.complete || currentCount >= 4) {
        setStage("complete");
      } else {
        setTurn(next);
        setQuestionCount(currentCount + 1);
      }
    });
  };

  // Finalize and save the synthesized ChildProfile to the database
  const handleFinalizeProfile = () => {
    if (!turn) return;
    void guard(async () => {
      const interestsArray = interests.split(",").map((s) => s.trim()).filter(Boolean);
      const created = await api.post<{ profile_id: string }>(
        `/intake/${turn.intake_id}/finalize`,
        {
          name: name.trim(),
          age: Number(age) || 8,
          neurodivergence,
          interests: interestsArray.length ? interestsArray : ["general games"],
        }
      );
      if (created && created.profile_id) {
        navigate(`/profiles/${created.profile_id}`);
      } else {
        navigate("/");
      }
    });
  };

  return (
    <div className="intake-wizard-container">
      <header className="intake-header">
        <h1>🧠 AI Student Intake Wizard</h1>
        <p className="muted">
          Akinator-style adaptive profiling. Start with general background, then our AI will ask targeted behavioral questions to generate a tailored neurodivergent learning profile.
        </p>
      </header>

      {error && <div className="card error-banner">{error}</div>}

      {/* STAGE 1: GENERAL INFO SETUP */}
      {stage === "setup" && (
        <form onSubmit={handleStartAkinator} className="card wizard-card">
          <h2>1. General Information & Neurodivergence Profile</h2>
          <p className="muted">
            Provide the foundational details so the AI knows where to focus its interview.
          </p>

          <div className="form-grid">
            <div className="form-group">
              <label htmlFor="child-name">
                <strong>Child's First Name:</strong>
              </label>
              <input
                id="child-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Maya, Alex, Leo, Lena"
                required
                autoFocus
              />
            </div>

            <div className="form-group">
              <label htmlFor="child-age">
                <strong>Age:</strong>
              </label>
              <input
                id="child-age"
                type="number"
                min="4"
                max="16"
                value={age}
                onChange={(e) => setAge(e.target.value)}
                required
              />
            </div>

            <div className="form-group full-width">
              <label htmlFor="neurodivergence-select">
                <strong>Learning Profile / Neurodivergence (Dropdown):</strong>
              </label>
              <select
                id="neurodivergence-select"
                value={neurodivergence}
                onChange={(e) => setNeurodivergence(e.target.value)}
                className="select-input"
              >
                <option value="ADHD - Combined Type">ADHD - Combined Type (Hyperactivity & Inattention)</option>
                <option value="ADHD - Inattentive Type">ADHD - Inattentive Type (Easily Distracted / Dreamer)</option>
                <option value="ADHD - Hyperactive/Impulsive">ADHD - Hyperactive / Impulsive Type</option>
                <option value="Autism Spectrum (ASD)">Autism Spectrum (ASD) / Monotropic Focus</option>
                <option value="Dyscalculia">Dyscalculia / Math Processing Difficulty</option>
                <option value="Sensory Processing Sensitivity">Sensory Processing & Auditory Sensitivity</option>
                <option value="Anxiety / Time Pressure Sensitivity">Anxiety / High Time Pressure Sensitivity</option>
                <option value="General / Diverse Learner">General / Diverse Learner</option>
              </select>
            </div>

            <div className="form-group full-width">
              <label htmlFor="child-interests">
                <strong>Child's Top Passions & Interests (Text Input):</strong>
              </label>
              <input
                id="child-interests"
                type="text"
                value={interests}
                onChange={(e) => setInterests(e.target.value)}
                placeholder="e.g. Dinosaurs, Outer Space, Tennis, Horses, Trains, Baking"
              />
              <div className="tag-chips">
                <span className="chips-label">Quick Suggestions:</span>
                {SUGGESTED_INTERESTS.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    className="chip-btn"
                    onClick={() => addInterestTag(tag)}
                  >
                    {tag}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="wizard-actions">
            <button type="submit" className="primary launch-wizard-btn" disabled={busy || !name.trim()}>
              {busy ? "Initializing AI Akinator..." : "Begin AI Intake Interview →"}
            </button>
          </div>
        </form>
      )}

      {/* STAGE 2: DYNAMIC AKINATOR QUESTIONING */}
      {stage === "akinator" && turn && (
        <div className="card wizard-card">
          <div className="wizard-progress-header">
            <span className="pill">Question {questionCount} of 4</span>
            <span className="muted">Student: {name} (Age {age}) • {neurodivergence}</span>
          </div>

          <h2 className="akinator-question">✦ {turn.question}</h2>

          {/* Multiple choice cards if provided by AI */}
          {turn.choices && turn.choices.length > 0 && (
            <div className="choice-grid">
              {turn.choices.map((choice, idx) => (
                <button
                  key={idx}
                  type="button"
                  className={`choice-card ${selectedChoice === choice ? "selected" : ""}`}
                  onClick={() => {
                    setSelectedChoice(choice);
                    setCustomAnswer("");
                  }}
                >
                  <span className="choice-dot">{selectedChoice === choice ? "●" : "○"}</span>
                  <span className="choice-text">{choice}</span>
                </button>
              ))}
            </div>
          )}

          {/* Custom write-in input */}
          <div className="custom-input-box">
            <label htmlFor="custom-answer">
              <strong>Or write a custom answer / nuance:</strong>
            </label>
            <input
              id="custom-answer"
              type="text"
              value={customAnswer}
              onChange={(e) => {
                setCustomAnswer(e.target.value);
                if (e.target.value) setSelectedChoice("");
              }}
              placeholder="e.g. She loves fast games but gets overwhelmed if colors flash too quickly..."
            />
          </div>

          <div className="wizard-actions">
            <button
              type="button"
              className="primary"
              onClick={() => handleAnswerSubmit()}
              disabled={busy || (!selectedChoice && !customAnswer.trim())}
            >
              {busy ? "AI Reasoning..." : "Next Question →"}
            </button>
          </div>
        </div>
      )}

      {/* STAGE 3: COMPLETE & SYNTHESIZE */}
      {stage === "complete" && (
        <div className="card wizard-card complete-card">
          <h2>🎉 AI Intake Complete!</h2>
          <p className="muted">
            The AI has synthesized a complete, personalized learning profile for <strong>{name}</strong> based on the interview transcript.
          </p>

          <div className="summary-preview-box">
            <h3>Synthesized Profile Summary:</h3>
            <ul className="plain">
              <li><strong>Student Name:</strong> {name} (Age {age})</li>
              <li><strong>Profile Category:</strong> {neurodivergence}</li>
              <li><strong>Top Interests:</strong> {interests || "General Science & Games"}</li>
              <li><strong>Cognitive Guardrails:</strong> Timer Disabled • Single Focal Point • Instant Action Rewards</li>
              <li><strong>Emotional Safety:</strong> Impossible to Lose • Gentle Non-Punitive Recovery</li>
            </ul>
          </div>

          <div className="wizard-actions">
            <button
              type="button"
              className="primary launch-profile-btn"
              onClick={handleFinalizeProfile}
              disabled={busy}
            >
              {busy ? "Saving to Roster..." : "Save Profile & Launch Game Studio 🚀"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
