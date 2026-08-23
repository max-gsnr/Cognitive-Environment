"""OpenAI client for the Akinator teacher intake interview with smart fallback."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)
CHAT_COMPLETIONS = "https://api.openai.com/v1/chat/completions"


class OpenAINotConfigured(RuntimeError):
    pass


async def complete_json(prompt: str) -> dict[str, Any]:
    """Send one prompt, expect strict JSON back. Falls back to deterministic Akinator if unconfigured."""
    if settings.openai_configured:
        try:
            payload = {
                "model": settings.openai_model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.7,
            }
            headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(CHAT_COMPLETIONS, json=payload, headers=headers)
                response.raise_for_status()
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                return json.loads(content)
        except Exception as e:
            logger.warning("OpenAI API call failed or timed out: %s. Using Akinator reasoning engine.", e)

    # Smart fallback synthesizer for when OpenAI is not configured or in offline demo mode
    return _fallback_akinator_reasoning(prompt)


def _fallback_akinator_reasoning(prompt: str) -> dict[str, Any]:
    """Intelligent fallback for Akinator questionnaire when API key is missing."""
    prompt_lower = prompt.lower()

    # If this is the resolve / profile synthesis prompt
    if "converting a completed intake interview transcript" in prompt_lower or "structured child-profile json" in prompt_lower:
        # Extract interests, restlessness, and sensory signals from transcript
        interests = ["outer space", "dinosaurs", "tennis"]
        for keyword in ["horse", "tennis", "space", "train", "dinosaur", "robot", "ocean", "baking", "lego", "music", "art", "math", "soccer"]:
            if keyword in prompt_lower and keyword not in interests:
                interests.insert(0, keyword)

        return {
            "interests": interests[:3],
            "leniency_band": "high" if ("struggle" in prompt_lower or "shut down" in prompt_lower or "anxious" in prompt_lower or "panic" in prompt_lower) else "medium",
            "restlessness_interpretation": "focus" if ("moving" in prompt_lower or "fidget" in prompt_lower or "self-regulate" in prompt_lower) else "distraction",
            "difficulty_floor": {
                "addition": "double_digit" if ("strong" in prompt_lower or "older" in prompt_lower or "carries" in prompt_lower) else "single_digit",
                "subtraction": "single_digit"
            },
            "session_length": 10,
            "constraints": {
                "visual": {
                    "color_palette": "pastel_muted" if ("calm" in prompt_lower or "sensitive" in prompt_lower) else "high_contrast_calm",
                    "animations": "minimal_no_screen_shake" if ("overwhelm" in prompt_lower or "seizure" in prompt_lower) else "standard",
                    "particle_effects": True
                },
                "audio": {
                    "music": False,
                    "sfx": "ui_only"
                },
                "cognitive": {
                    "timer": "disabled",
                    "ui_clutter": "single_focal_point",
                    "level_length": "micro",
                    "reward_frequency": "instant_per_action"
                },
                "emotional": {
                    "error_feedback": "gentle_no_red_x",
                    "fail_state": "impossible_to_lose"
                }
            }
        }

    # Dynamic question tree
    questions = [
        {
            "complete": False,
            "question": "How does the child typically react when they encounter a difficult problem or make an arithmetic mistake?",
            "input_type": "choice",
            "choices": [
                "Shuts down or gets anxious quickly (Needs high leniency & no fail states)",
                "Stays calm and tries again if given a gentle visual hint",
                "Gets restless or impulsive, guessing rapidly to move on"
            ]
        },
        {
            "complete": False,
            "question": "When working on focused screen tasks, how does physical movement/fidgeting affect their concentration?",
            "input_type": "choice",
            "choices": [
                "Fidgeting helps them self-regulate and stay focused (Restlessness = Focus)",
                "Movement usually signals that they are getting distracted / losing focus",
                "Varies / not entirely sure"
            ]
        },
        {
            "complete": False,
            "question": "What is their reaction to time pressure or visible countdown clocks?",
            "input_type": "choice",
            "choices": [
                "Freezes or panics (Timers must be strictly disabled)",
                "Enjoys gentle pacing as long as there is no penalty",
                "Thrives on fast arcade action"
            ]
        },
        {
            "complete": False,
            "question": "What visual and sensory environment works best for them during learning?",
            "input_type": "choice",
            "choices": [
                "Calm, muted/pastel palette with minimal distractions",
                "High-contrast, vibrant, and energetic theme",
                "Clean dark mode with subtle glowing accents"
            ]
        },
        {
            "complete": False,
            "question": "How would you rate their current comfort with multi-digit addition and subtraction?",
            "input_type": "choice",
            "choices": [
                "Comfortable with single digits, learning double-digit carrying/borrowing",
                "Needs single-digit baseline practice without time pressure",
                "Ready for multi-digit challenges with carries and borrows"
            ]
        }
    ]

    for q in questions:
        if q["question"] not in prompt:
            return q

    return {"complete": True}
