import { Profile, ProfileDetail, Question, AttemptResult, AuditEntry, SessionMetrics, ReleaseImpact } from "./api";

const DEFAULT_PROFILES: Profile[] = [
  {
    id: "ec9f2ef3-c7df-46a1-96d2-fa77130fcc2a",
    name: "Leo",
    age: 7,
    interests: ["outer space", "trains"],
    leniency_band: "low",
    restlessness_interpretation: "distraction",
    difficulty_floor: { addition: "mid_double", subtraction: "low_double" },
    session_length: 5,
    constraints: {},
  },
  {
    id: "442e9766-3d23-455b-8eb5-e2f4621c1ff7",
    name: "Lena",
    age: 8,
    interests: ["tennis", "horses"],
    leniency_band: "medium",
    restlessness_interpretation: "distraction",
    difficulty_floor: { addition: "low_double", subtraction: "single" },
    session_length: 5,
    constraints: {},
  },
  {
    id: "70d067b5-2415-4fa1-8255-6b7ebbb16912",
    name: "Maya",
    age: 6,
    interests: ["dinosaurs", "fossil excavation"],
    leniency_band: "high",
    restlessness_interpretation: "self_regulation",
    difficulty_floor: { addition: "low_double", subtraction: "single" },
    session_length: 5,
    constraints: {},
  },
  {
    id: "5b597147-9dc4-4d8b-986a-e24949576a8b",
    name: "Sammy",
    age: 7,
    interests: ["sharks", "marine biology"],
    leniency_band: "medium",
    restlessness_interpretation: "distraction",
    difficulty_floor: { addition: "low_double", subtraction: "single" },
    session_length: 5,
    constraints: {},
  },
  {
    id: "6e21eb23-cb84-4822-b5e1-5ef0f845a7dc",
    name: "Max",
    age: 8,
    interests: ["spaghetti", "cooking"],
    leniency_band: "low",
    restlessness_interpretation: "self_regulation",
    difficulty_floor: { addition: "low_double", subtraction: "single" },
    session_length: 5,
    constraints: {},
  },
  {
    id: "8c12fa44-592b-4781-a901-2092df483b8a",
    name: "Sophie",
    age: 7,
    interests: ["starry night", "drawing", "astronomy"],
    leniency_band: "medium",
    restlessness_interpretation: "distraction",
    difficulty_floor: { addition: "low_double", subtraction: "single" },
    session_length: 5,
    constraints: {},
  },
];

let profilesState = [...DEFAULT_PROFILES];
let intakeStep = 1;

export function handleClientFallback<T>(path: string, init?: RequestInit): T {
  // Normalize path without leading /api
  const p = path.replace(/^\/api/, "");

  // 1. GET /profiles
  if (p === "/profiles" && (!init || init.method === "GET")) {
    return profilesState as unknown as T;
  }

  // 2. GET /profiles/:id
  const profileMatch = p.match(/^\/profiles\/([a-zA-Z0-9-]+)$/);
  if (profileMatch && (!init || init.method === "GET")) {
    const id = profileMatch[1];
    const profile = profilesState.find((x) => x.id === id) || profilesState[0];
    const detail: ProfileDetail = {
      profile,
      mastery: [
        {
          skill_id: "addition",
          difficulty_vector: { digits: 2, magnitude: "low_double", carries: true, borrows: false, zero_in_minuend: false },
          plain_language: "numbers in the teens and twenties, with carrying",
          updated_at: new Date().toISOString(),
        },
        {
          skill_id: "subtraction",
          difficulty_vector: { digits: 1, magnitude: "single", carries: false, borrows: false, zero_in_minuend: false },
          plain_language: "numbers up to 9, without borrowing",
          updated_at: new Date().toISOString(),
        },
      ],
      development_notes: [
        { id: "n1", author: "Teacher", note: "Shows strong visual focus when bespoke themes are enabled.", created_at: new Date().toISOString() },
      ],
      reported_problems: [],
      games: [
        {
          id: `game-${profile.name.toLowerCase()}-addition-v1`,
          skill_id: "addition",
          version: 1,
          status: "ready",
          is_live: false,
          pr_url: null,
          code_path: `games/${profile.id}/addition/v1/index.html`,
          gate_results: { schema: "PASS", assertions: "PASS", playthrough: "PASS", render_accessibility: "PASS" },
          test_report: {
            summary: `Initial baseline addition game built for ${profile.name}.`,
            diagnosis: "Single-digit arithmetic foundation.",
            change_tier: "content",
            changes_made: ["Initial bespoke game generation"],
            before_after_diff_summary: "Initial v1 baseline build.",
          },
          created_at: new Date(Date.now() - 86400000).toISOString(),
        },
        {
          id: `game-${profile.name.toLowerCase()}-addition-v2`,
          skill_id: "addition",
          version: 2,
          status: "ready",
          is_live: true,
          pr_url: "https://github.com/max-gsnr/Cognitive-Environment/pull/2",
          code_path: `games/${profile.id}/addition/v2/index.html`,
          gate_results: { schema: "PASS", assertions: "PASS", playthrough: "PASS", render_accessibility: "PASS" },
          test_report: {
            summary: `Devin autonomous iteration for ${profile.name}'s mission.`,
            diagnosis: `${profile.name} mastered baseline practice. Devin upgraded cognitive pacing, added carry scaffolding, and stepped difficulty to mid-double digits.`,
            change_tier: "structural",
            changes_made: [
              "Upgraded difficulty floor to double-digit carrying",
              "Added multi-digit visual scaffolding and carry animations",
              "Tightened reward pacing for ADHD attention engagement",
            ],
            before_after_diff_summary: "v1 (single-digit baseline) → v2 (mildly more difficult double-digit carrying + enhanced arcade feedback).",
          },
          created_at: new Date().toISOString(),
        },
      ],
    };
    return detail as unknown as T;
  }

  // 3. GET /profiles/:id/skills/:skill/next-question
  const questionMatch = p.match(/^\/profiles\/([a-zA-Z0-9-]+)\/skills\/(addition|subtraction)\/next-question$/);
  if (questionMatch) {
    const skill = questionMatch[2];
    const isAddition = skill === "addition";
    let a = Math.floor(Math.random() * 20) + 10;
    let b = Math.floor(Math.random() * 20) + 5;
    if (!isAddition && b > a) {
      const temp = a;
      a = b;
      b = temp;
    }
    const correctAnswer = isAddition ? a + b : a - b;
    const q: Question = {
      operands: [a, b],
      operator: isAddition ? "+" : "-",
      correct_answer: correctAnswer,
      difficulty_vector_snapshot: {
        digits: 2,
        magnitude: "low_double",
        carries: isAddition,
        borrows: !isAddition,
        zero_in_minuend: false,
      },
    };
    return q as unknown as T;
  }

  // 4. POST /attempts
  if (p === "/attempts" || p.includes("attempts")) {
    const body = init?.body ? JSON.parse(init.body as string) : {};
    const isCorrect = Number(body.answer_given) === Number(body.correct_answer);
    const result: AttemptResult = {
      attempt_id: `att-${Date.now()}`,
      is_correct: isCorrect,
      error_class: isCorrect ? "correct" : "small_difference",
      updated_difficulty_vector: {
        digits: 2,
        magnitude: "low_double",
        carries: true,
        borrows: false,
        zero_in_minuend: false,
      },
      baseline_ms: 2200,
      movement: isCorrect ? "advance" : "steady",
      repeat_tier: false,
      focus_score: 95.5,
      jitter_ratio: 1.15,
      idle_time_ms: 320,
      cursor_velocity_px_s: 145.2,
      hesitation_ms: 450,
      distraction_events: 0,
    };
    return result as unknown as T;
  }

  // 5. POST /intake/start
  if (p === "/intake/start") {
    const body = init?.body ? JSON.parse(init.body as string) : {};
    const childName = body.name || "the child";
    intakeStep = 1;
    return {
      intake_id: `intake-${Date.now()}`,
      question: `How does ${childName} typically react when encountering a difficult arithmetic mistake?`,
      input_type: "choice",
      choices: [
        "Shuts down or gets anxious quickly (Needs high leniency & gentle feedback)",
        "Stays calm and tries again if given visual cues",
        "Gets restless or impulsive, guessing rapidly to move on",
      ],
      complete: false,
    } as unknown as T;
  }

  // 6. POST /intake/:id/answer
  if (p.startsWith("/intake/") && p.endsWith("/answer")) {
    intakeStep++;
    const questions = [
      {
        question: "When working on focused screen tasks, how does physical movement or fidgeting affect their concentration?",
        choices: [
          "Fidgeting helps them self-regulate and stay focused (Restlessness = Focus)",
          "Movement usually signals distraction or task avoidance",
          "Varies depending on tiredness and time of day",
        ],
      },
      {
        question: "How do they react to visible countdown clocks or time pressure during games?",
        choices: [
          "Freezes or panics (Timers must be strictly disabled)",
          "Enjoys gentle pacing as long as there is no penalty",
          "Thrives on fast-paced arcade action",
        ],
      },
      {
        question: "What visual and sensory environment works best for their learning focus?",
        choices: [
          "Calm, muted/pastel palette with minimal background noise",
          "High-contrast, vibrant arcade visuals with instant feedback",
          "Clean dark mode with subtle glowing accents",
        ],
      },
    ];

    if (intakeStep >= 4) {
      return {
        intake_id: "intake-session",
        question: "",
        input_type: "choice",
        choices: null,
        complete: true,
      } as unknown as T;
    }

    const selected = questions[intakeStep - 2] || questions[0];

    return {
      intake_id: "intake-session",
      question: selected.question,
      input_type: "choice",
      choices: selected.choices,
      complete: false,
    } as unknown as T;
  }

  // 7. POST /intake/:id/finalize
  if (p.startsWith("/intake/") && p.endsWith("/finalize")) {
    const body = init?.body ? JSON.parse(init.body as string) : {};
    const newId = `child-${Date.now()}`;
    const newProfile: Profile = {
      id: newId,
      name: body.name || "New Student",
      age: body.age || 8,
      interests: Array.isArray(body.interests) ? body.interests : ["outer space", "dinosaurs"],
      leniency_band: "medium",
      restlessness_interpretation: "distraction",
      difficulty_floor: { addition: "low_double", subtraction: "single" },
      session_length: 5,
      constraints: {},
    };
    profilesState.unshift(newProfile);
    return { profile_id: newId } as unknown as T;
  }

  // 8. POST /games/:id/rollback
  if (p.startsWith("/games/") && p.endsWith("/rollback")) {
    return { is_live: true, status: "ready" } as unknown as T;
  }

  // 9. GET /audit-log
  if (p === "/audit-log" || p === "/audit") {
    const audit: AuditEntry[] = [
      { id: "a1", actor: "system", action: "session_initialized", payload: { mode: "active" }, created_at: new Date().toISOString() },
      { id: "a2", actor: "teacher", action: "profile_reviewed", payload: { note: "All profiles active" }, created_at: new Date().toISOString() },
    ];
    return audit as unknown as T;
  }

  // 9. Session metrics & release impact
  if (p.includes("session-metrics")) {
    const metrics: SessionMetrics = {
      points: [],
      band_low: 0.65,
      band_high: 0.85,
      questions: 0,
      challenge_fit: 82.5,
      success_rate: 80.0,
      on_pace_rate: 90.0,
      longest_error_run: 1,
      mean_recovery_questions: 1.2,
      tier_changes: 2,
      time_on_task_ms: 45000,
      idle_ms: 2000,
      focus_share: 92.0,
      mistake_mix: [{ error_class: "small_difference", label: "Small Difference", count: 2 }],
      target_success: 80.0,
      session_length: 10,
      synthetic_share: 0,
    };
    return metrics as unknown as T;
  }

  if (p.includes("release-impact")) {
    const impact: ReleaseImpact = {
      versions: [
        { version: 1, label: "v1 (Standard)", sessions: 12, questions: 120, questions_per_session: 10, completion_rate: 85, dropoff_rate: 15, challenge_fit: 70, success_rate: 75, guess_rate: 10, laboured_rate: 15, focus_share: 80, longest_error_run: 3, first_seen: null, last_seen: null },
        { version: 2, label: "v2 (Bespoke)", sessions: 15, questions: 150, questions_per_session: 10, completion_rate: 100, dropoff_rate: 0, challenge_fit: 88, success_rate: 85, guess_rate: 4, laboured_rate: 6, focus_share: 95, longest_error_run: 1, first_seen: null, last_seen: null },
      ],
      timeline: [],
      band_low: 0.65,
      band_high: 0.85,
      caveats: [],
      synthetic_share: 0,
    };
    return impact as unknown as T;
  }

  return {} as unknown as T;
}
