"""Read a session's events back out of PostHog, so the backend can score them.

Capture was one-way until now: the frontend pushed events and nothing in the
backend ever read them, which meant every behavioural signal had to be computed
by a model inside a Devin session. This is the return path -- one HogQL query,
read-only, used before an iteration to hand that session numbers it does not
have to derive (see app/telemetry_signals.py).

Unconfigured is not an error: without a personal API key this returns no events
and Loop B falls back to asking the session to query PostHog itself.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings

TIMEOUT = 20
LIMIT = 2000

EVENTS_QUERY = """
select event, properties, timestamp
from events
where properties.game_id = {game_id}
  and properties.profile_id = {profile_id}
  and timestamp > {since}
order by timestamp
limit {limit}
"""


def configured() -> bool:
    return bool(settings.posthog_personal_api_key and settings.posthog_project_id)


def fetch_events(game_id: str, profile_id: str, since: str) -> list[dict[str, Any]]:
    """Every event for one child on one game version. Empty on any failure.

    A telemetry read must never be the reason an iteration cannot start, so this
    swallows transport and query errors and reports nothing found.
    """
    if not configured():
        return []

    query = (
        EVENTS_QUERY.replace("{game_id}", _literal(game_id))
        .replace("{profile_id}", _literal(profile_id))
        .replace("{since}", _literal(since))
        .replace("{limit}", str(LIMIT))
    )
    url = (
        f"{settings.posthog_host.rstrip('/')}"
        f"/api/projects/{settings.posthog_project_id}/query/"
    )
    try:
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.posthog_personal_api_key}",
                "Content-Type": "application/json",
            },
            json={"query": {"kind": "HogQLQuery", "query": query}},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        rows = response.json().get("results") or []
    except (httpx.HTTPError, ValueError):
        return []

    return [_row(row) for row in rows if row]


def _row(row: list[Any]) -> dict[str, Any]:
    """HogQL returns positional columns in the order the select asked for them."""
    properties = row[1] if len(row) > 1 else {}
    if isinstance(properties, str):
        try:
            properties = json.loads(properties)
        except ValueError:
            properties = {}
    return {
        "event": row[0] if row else "",
        "properties": properties or {},
        "timestamp": row[2] if len(row) > 2 else None,
    }


def _literal(value: str) -> str:
    """HogQL string literal. Single quotes are the only thing to worry about."""
    return "'" + value.replace("'", "''") + "'"
