"""The telemetry read path: scoped, quiet about secrets, and never fatal."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app import posthog_client
from app.config import settings

SINCE = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "posthog_personal_api_key", "phx_secret", False)
    monkeypatch.setattr(settings, "posthog_project_id", "4242", False)
    monkeypatch.setattr(settings, "posthog_host", "https://eu.i.posthog.com", False)


def capture_request(monkeypatch: pytest.MonkeyPatch, results: Any) -> dict[str, Any]:
    """Record the outgoing call and answer it with `results`."""
    seen: dict[str, Any] = {}

    def post(url: str, **kwargs: Any) -> httpx.Response:
        seen["url"] = url
        seen.update(kwargs)
        return httpx.Response(
            200,
            json={"results": results},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(posthog_client.httpx, "post", post)
    return seen


def test_unconfigured_returns_nothing_instead_of_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing key must not be the reason an iteration cannot start."""
    monkeypatch.setattr(settings, "posthog_personal_api_key", "", False)
    assert posthog_client.configured() is False
    assert posthog_client.fetch_events("g1", "p1", SINCE) == []


def test_rows_come_back_as_events(
    monkeypatch: pytest.MonkeyPatch, configured: None
) -> None:
    seen = capture_request(
        monkeypatch,
        [
            ["answer_submitted", {"correct": True}, "2026-01-02T00:00:00Z"],
            ["idle_tick", '{"game_id": "g1"}', "2026-01-02T00:00:05Z"],
        ],
    )
    events = posthog_client.fetch_events("g1", "p1", SINCE)

    assert [event["event"] for event in events] == ["answer_submitted", "idle_tick"]
    assert events[0]["properties"] == {"correct": True}
    # Properties arrive as a JSON string on some projects.
    assert events[1]["properties"] == {"game_id": "g1"}
    assert seen["url"] == "https://eu.i.posthog.com/api/projects/4242/query/"


def test_the_query_is_scoped_to_one_child_and_one_game(
    monkeypatch: pytest.MonkeyPatch, configured: None
) -> None:
    seen = capture_request(monkeypatch, [])
    posthog_client.fetch_events("game-1", "profile-1", SINCE)

    query = seen["json"]["query"]["query"]
    assert "'game-1'" in query
    assert "'profile-1'" in query
    assert f"'{SINCE}'" in query


def test_a_quote_in_an_id_cannot_break_out_of_the_query(
    monkeypatch: pytest.MonkeyPatch, configured: None
) -> None:
    seen = capture_request(monkeypatch, [])
    posthog_client.fetch_events("g' or 1=1 --", "p1", SINCE)
    assert "'g'' or 1=1 --'" in seen["json"]["query"]["query"]


def test_the_key_travels_in_a_header_and_not_the_body(
    monkeypatch: pytest.MonkeyPatch, configured: None
) -> None:
    seen = capture_request(monkeypatch, [])
    posthog_client.fetch_events("g1", "p1", SINCE)

    assert seen["headers"]["Authorization"] == "Bearer phx_secret"
    assert "phx_secret" not in str(seen["json"])


def test_a_posthog_outage_reads_as_no_events(
    monkeypatch: pytest.MonkeyPatch, configured: None
) -> None:
    def post(url: str, **kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError("posthog is down")

    monkeypatch.setattr(posthog_client.httpx, "post", post)
    assert posthog_client.fetch_events("g1", "p1", SINCE) == []
