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
  created_at: string;
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
  is_correct: boolean;
  error_class: string;
  updated_difficulty_vector: DifficultyVector;
  baseline_ms: number | null;
  movement: string;
  repeat_tier: boolean;
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
  test_report: Record<string, unknown> | null;
};

export type AuditEntry = {
  id: string;
  actor: string;
  action: string;
  payload: Record<string, unknown> | null;
  created_at: string;
};
