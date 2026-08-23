"""Devin API: create a session from a prompt, poll it, read its structured output.

Secrets travel through Devin's own secrets mechanism, never inside prompt text.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.config import settings


class DevinNotConfigured(RuntimeError):
    pass


def _headers() -> dict[str, str]:
    if not settings.devin_configured:
        raise DevinNotConfigured("DEVIN_API_KEY is not set; cannot start a session.")
    return {"Authorization": f"Bearer {settings.devin_api_key}"}


async def create_session(
    prompt: str,
    tags: list[str] | None = None,
    session_secrets: dict[str, str] | None = None,
    structured_output_schema: dict[str, Any] | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"prompt": prompt, "idempotent": False}
    if tags:
        payload["tags"] = tags
    if session_secrets:
        payload["session_secrets"] = [
            {"key": key, "value": value, "sensitive": True}
            for key, value in session_secrets.items()
        ]
    if structured_output_schema:
        payload["structured_output_schema"] = structured_output_schema
    if title:
        payload["title"] = title

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{settings.devin_api_base}/sessions", json=payload, headers=_headers()
        )
        response.raise_for_status()
        return response.json()


async def get_session(session_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(
            f"{settings.devin_api_base}/sessions/{session_id}", headers=_headers()
        )
        response.raise_for_status()
        return response.json()


def extract_structured_output(session: dict[str, Any]) -> dict[str, Any] | None:
    """Pull the session's structured JSON out, wherever the API surfaced it.

    The field name has moved between Devin API versions, so accept the
    documented `structured_output` and fall back to parsing the final message.
    """
    for key in ("structured_output", "output"):
        value = session.get(key)
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            parsed = _first_json_object(value)
            if parsed is not None:
                return parsed

    messages = session.get("messages") or []
    for message in reversed(messages):
        text = message.get("message") or message.get("content") or ""
        parsed = _first_json_object(text)
        if parsed is not None:
            return parsed
    return None


def _first_json_object(text: str) -> dict[str, Any] | None:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            return None
        candidate = text[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def is_finished(session: dict[str, Any]) -> bool:
    status = (session.get("status_enum") or session.get("status") or "").lower()
    return status in {"blocked", "stopped", "finished", "completed", "expired"}


def pull_request_url(session: dict[str, Any]) -> str | None:
    pull_request = session.get("pull_request") or {}
    return pull_request.get("url") if isinstance(pull_request, dict) else None
