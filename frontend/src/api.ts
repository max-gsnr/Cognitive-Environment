import { handleClientFallback } from "./fallbackData";

const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  try {
    const response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });

    const contentType = response.headers.get("content-type") ?? "";

    if (response.ok && contentType.includes("application/json")) {
      return (await response.json()) as T;
    }

    const text = await response.text();
    // If backend returns HTML (e.g. Vercel SPA rewrite fallback or 404), use client fallback
    if (text.trim().startsWith("<!doctype") || text.trim().startsWith("<html") || !response.ok) {
      return handleClientFallback<T>(path, init);
    }

    return JSON.parse(text) as T;
  } catch (_err) {
    // Network or parse error: gracefully fall back to client state
    return handleClientFallback<T>(path, init);
  }
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

/** One version of the game, as Loop B produced it. Computed by app/evolution.py. */
export type EvolutionVersion = {
  game_id: string;
  version: number;
  label: string;
  created_at: string;
  from_version: number | null;
  state: "live" | "shipped" | "blocked" | "in_progress" | "failed";
  state_label: string;
  status: string;
  is_live: boolean;
  trigger: {
    available: boolean;
    reason: string | null;
    signal: string | null;
    signal_label: string | null;
    event_count?: number | null;
    evidence: { key: string; label: string; unit: string; value: number }[];
    /** Every rule in priority order, with the threshold each one compared against. */
    ladder: {
      signal: string;
      label: string;
      tier: string | null;
      outcome: "fired" | "no" | "not_reached";
      terms: {
        key: string;
        label: string;
        comparison: string;
        threshold: number;
        value: number | null;
        joiner: string;
        met: boolean | null;
      }[];
    }[];
    measured: { key: string; label: string; value: number }[];
  };
  permitted_change: {
    allowed: string | null;
    allowed_label: string | null;
    claimed: string | null;
    claimed_label: string | null;
    within_scope: boolean | null;
    rule: string | null;
  };
  summary: string | null;
  changes_made: string[];
  diff_summary: string | null;
  checks: {
    name: string;
    label: string;
    source: "agent" | "ours";
    verdict: "pass" | "fail" | "skipped" | "not_run";
    detail: string | null;
  }[];
  checks_passed: boolean;
  blocked_by: string[];
  provenance: {
    agent: string | null;
    prompt: string | null;
    prompt_revision: string | null;
    devin_session_id: string | null;
    pr_url: string | null;
    requested_at: string | null;
  };
};

export type EvolutionLog = {
  versions: EvolutionVersion[];
  summary: {
    proposed: number;
    shipped: number;
    blocked: number;
    in_progress: number;
    live_version: number | null;
    no_change_needed: number;
    checked: number;
    disagreements: number;
  };
};

export type AuditEntry = {
  id: string;
  actor: string;
  action: string;
  payload: Record<string, unknown> | null;
  created_at: string;
};
