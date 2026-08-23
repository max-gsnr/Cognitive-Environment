const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
  patch: <T,>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
};

export type DifficultyVector = {
  digits: number;
  magnitude: string;
  carries: boolean;
  borrows: boolean;
  zero_in_minuend: boolean;
};

export type Profile = {
  id: string;
  name: string;
  age: number;
  interests: string[];
  leniency_band: "low" | "medium" | "high";
  restlessness_interpretation: "distraction" | "self_regulation";
  difficulty_floor: Record<string, string>;
  session_length: number;
  constraints: Record<string, unknown>;
};

export type Mastery = {
  skill_id: string;
  difficulty_vector: DifficultyVector;
  plain_language: string;
  updated_at: string;
};

export type GameSummary = {
  id: string;
  skill_id: string;
  version: number;
  status: string;
  is_live: boolean;
  pr_url: string | null;
  code_path: string | null;
  gate_results: Record<string, string> | null;
  test_report: TestReport | null;
  created_at: string;
};

export type TestReport = {
  summary?: string;
  diagnosis?: string;
  change_tier?: string;
  changes_made?: string[];
  before_after_diff_summary?: string;
};

export type ProfileDetail = {
  profile: Profile;
  mastery: Mastery[];
  development_notes: { id: string; author: string; note: string; created_at: string }[];
  reported_problems: { id: string; game_id: string; description: string; created_at: string }[];
  games: GameSummary[];
};

export type Question = {
  operands: number[];
  operator: string;
  correct_answer: number;
  difficulty_vector_snapshot: DifficultyVector;
};

export type AttemptResult = {
  /** The stored row, so a telemetry event can be joined to the attempt it describes. */
  attempt_id: string;
  is_correct: boolean;
  error_class: string;
  updated_difficulty_vector: DifficultyVector;
  baseline_ms: number | null;
  movement: string;
  repeat_tier: boolean;
  focus_score?: number;
  jitter_ratio?: number;
  idle_time_ms?: number;
  cursor_velocity_px_s?: number;
  hesitation_ms?: number;
  distraction_events?: number;
};

export type GameState = {
  game_id: string;
  status: string;
  devin_status: string | null;
  devin_session_id: string | null;
  version: number;
  is_live: boolean;
  pr_url: string | null;
  code_path: string | null;
  gate_results: Record<string, string> | null;
  test_report: TestReport | null;
};

/** One question, as the Session Monitor plots it. Computed by app/analytics.py. */
export type SessionPoint = {
  index: number;
  at: string;
  problem: string;
  correct: boolean;
  error_class: string;
  expected_success: number;
  in_band: boolean;
  rung: number;
  tier_label: string;
  latency_ms: number;
  pace_index: number | null;
  movement: string;
  rest_item: boolean;
  fluency_check: boolean;
  focus_score: number | null;
};

export type SessionMetrics = {
  points: SessionPoint[];
  band_low: number;
  band_high: number;
  questions: number;
  challenge_fit: number;
  success_rate: number;
  on_pace_rate: number;
  longest_error_run: number;
  mean_recovery_questions: number | null;
  tier_changes: number;
  time_on_task_ms: number;
  idle_ms: number;
  focus_share: number | null;
  mistake_mix: { error_class: string; label: string; count: number }[];
  target_success: number;
  session_length: number;
  synthetic_share: number;
};

export type VersionMetrics = {
  version: number | null;
  label: string;
  sessions: number;
  questions: number;
  questions_per_session: number;
  completion_rate: number;
  dropoff_rate: number;
  challenge_fit: number;
  success_rate: number;
  guess_rate: number;
  laboured_rate: number;
  focus_share: number | null;
  longest_error_run: number;
  first_seen: string | null;
  last_seen: string | null;
  game_id?: string | null;
  diagnosis?: string | null;
  change_tier?: string | null;
  changes_made?: string[];
  dominant_signal?: string | null;
  pr_url?: string | null;
};

export type ReleaseImpact = {
  versions: VersionMetrics[];
  timeline: {
    at: string;
    version: number | null;
    questions: number;
    challenge_fit: number;
    success_rate: number;
    focus_share: number | null;
    completed: boolean;
  }[];
  band_low: number;
  band_high: number;
  caveats: string[];
  synthetic_share: number;
};

export type AuditEntry = {
  id: string;
  actor: string;
  action: string;
  payload: Record<string, unknown> | null;
  created_at: string;
};
