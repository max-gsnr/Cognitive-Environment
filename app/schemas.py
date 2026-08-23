"""Request and response shapes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class IntakeStartRequest(BaseModel):
    name: str | None = None
    age: int | None = None
    neurodivergence: str | None = None
    interests: str | None = None


class IntakeStartResponse(BaseModel):
    intake_id: str
    question: str
    input_type: Literal["choice", "text"] = "text"
    choices: list[str] | None = None
    complete: bool = False
    category: str | None = None


class IntakeAnswerRequest(BaseModel):
    answer: str


class IntakeFinalizeRequest(BaseModel):
    name: str
    age: int
    neurodivergence: str | None = None
    interests: list[str] | str | None = None


class NoteRequest(BaseModel):
    author: Literal["teacher", "parent"]
    note: str


class ProfilePatch(BaseModel):
    name: str | None = None
    age: int | None = None
    interests: list[str] | None = None
    leniency_band: Literal["low", "medium", "high"] | None = None
    restlessness_interpretation: Literal["distraction", "self_regulation"] | None = None
    difficulty_floor: dict[str, str] | None = None
    session_length: int | None = None
    constraints: dict[str, Any] | None = None


class QuestionResponse(BaseModel):
    operands: list[int]
    operator: str
    correct_answer: int
    difficulty_vector_snapshot: dict[str, Any]


class AttemptRequest(BaseModel):
    profile_id: str
    skill_id: str
    operands: list[int]
    operator: str
    answer_given: int
    latency_to_submit_ms: int = Field(ge=0)
    # Nuanced biometric & behavioral telemetry
    cursor_velocity_px_s: float | None = None
    cursor_peak_velocity_px_s: float | None = None
    jitter_ratio: float | None = None
    idle_time_ms: int | None = None
    hesitation_ms: int | None = None
    distraction_events: int | None = None
    focus_score: float | None = None


class AttemptResponse(BaseModel):
    # The stored row's id. The game forwards it into its answer_submitted event,
    # which is what lets a telemetry event be joined to the attempt it describes.
    attempt_id: str
    is_correct: bool
    error_class: str
    updated_difficulty_vector: dict[str, Any]
    baseline_ms: float | None = None
    movement: str
    repeat_tier: bool = False
    ability_rating: float | None = None
    expected_success: float | None = None
    # Biometric insights
    focus_score: float | None = None
    jitter_ratio: float | None = None
    idle_time_ms: int | None = None


class GenerateGameRequest(BaseModel):
    profile_id: str
    skill_id: str


class IterateRequest(BaseModel):
    demo_mode: bool = False


class ReportProblemRequest(BaseModel):
    description: str


class SeedHistoryRequest(BaseModel):
    profile_id: str
    skill_id: str


class SeedPostHogRequest(BaseModel):
    game_id: str
