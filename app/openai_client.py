"""OpenAI is used for the intake interview and nothing else."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings

CHAT_COMPLETIONS = "https://api.openai.com/v1/chat/completions"


class OpenAINotConfigured(RuntimeError):
    pass


async def complete_json(prompt: str) -> dict[str, Any]:
    """Send one prompt, expect strict JSON back."""
    if not settings.openai_configured:
        raise OpenAINotConfigured(
            "OPENAI_API_KEY is not set; the branching intake cannot run."
        )

    payload = {
        "model": settings.openai_model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
    }
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(CHAT_COMPLETIONS, json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()

    return json.loads(body["choices"][0]["message"]["content"])
