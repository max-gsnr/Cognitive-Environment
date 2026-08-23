"""Devin client: endpoint shapes, structured output, and refusal to fake a run.

The transport is injected, so these tests assert on the requests the client would
make rather than hitting the API. The endpoints under test are the current v3
organization-scoped ones.
"""

from __future__ import annotations

import pytest

from orbit.devin import DevinClient, DevinError, MissingCredentials, Session


class Recorder:
    """Stand-in transport: records calls, replays queued responses."""

    def __init__(self, *responses: dict) -> None:
        self.calls: list[tuple[str, str, dict | None]] = []
        self.responses = list(responses)

    def __call__(self, method: str, url: str, body: dict | None) -> dict:
        self.calls.append((method, url, body))
        return self.responses.pop(0) if self.responses else {}


def session_payload(**kwargs: object) -> dict:
    payload = {
        "session_id": "devin-abc",
        "url": "https://app.devin.ai/sessions/abc",
        "status": "running",
        "acus_consumed": 1.5,
        "pull_requests": [],
    }
    payload.update(kwargs)
    return payload


def client(*responses: dict) -> tuple[DevinClient, Recorder]:
    transport = Recorder(*responses)
    return (
        DevinClient(api_key="k", org_id="org-1", transport=transport),
        transport,
    )


def test_create_session_targets_the_v3_org_endpoint() -> None:
    devin, transport = client(session_payload())
    devin.create_session("mutate the game", repos=["owner/repo"], tags=["orbit"])
    method, url, body = transport.calls[0]
    assert method == "POST"
    assert url.endswith("/v3/organizations/org-1/sessions")
    assert body["repos"] == ["owner/repo"]


def test_create_session_requires_structured_output() -> None:
    devin, transport = client(session_payload())
    devin.create_session("mutate")
    _, _, body = transport.calls[0]
    assert body["structured_output_required"] is True
    assert body["structured_output_schema"]["required"] == [
        "summary",
        "branch",
        "mechanism",
        "gates_passed",
    ]


def test_sessions_are_acu_capped() -> None:
    devin, transport = client(session_payload())
    devin.create_session("mutate", max_acu_limit=7)
    assert transport.calls[0][2]["max_acu_limit"] == 7


def test_get_session_parses_structured_output_and_cost() -> None:
    devin, _ = client(
        session_payload(
            status="exit",
            acus_consumed=9.25,
            structured_output={"summary": "interleaved the tiers", "branch": "orbit/gen1"},
        )
    )
    session = devin.get_session("devin-abc")
    assert session.finished
    assert session.acus_consumed == 9.25
    assert session.structured_output["branch"] == "orbit/gen1"


def test_wait_polls_until_structured_output_appears() -> None:
    devin, transport = client(
        session_payload(status="running"),
        session_payload(status="running"),
        session_payload(status="running", structured_output={"summary": "done"}),
    )
    ticks: list[float] = []
    session = devin.wait("devin-abc", poll_s=1.0, sleep=ticks.append, now=lambda: 0.0)
    assert session.structured_output == {"summary": "done"}
    assert len(ticks) == 2
    assert all(call[0] == "GET" for call in transport.calls)


def test_wait_stops_on_a_terminal_status_without_output() -> None:
    devin, _ = client(session_payload(status="error"))
    assert devin.wait("devin-abc", sleep=lambda _: None).status == "error"


def test_wait_times_out_rather_than_hanging_a_generation() -> None:
    devin, _ = client(*[session_payload(status="running")] * 5)
    clock = iter([0.0, 10.0, 20.0, 30.0, 40.0])
    with pytest.raises(DevinError, match="did not finish"):
        devin.wait(
            "devin-abc",
            timeout_s=5.0,
            poll_s=1.0,
            sleep=lambda _: None,
            now=lambda: next(clock),
        )


def test_missing_credentials_is_an_error_not_a_mock() -> None:
    devin = DevinClient(api_key="", org_id="")
    assert not devin.configured
    with pytest.raises(MissingCredentials, match="DEVIN_API_KEY"):
        devin.create_session("mutate")


def test_http_errors_surface_the_api_message() -> None:
    import urllib.error

    def failing(method: str, url: str, body: dict | None) -> dict:
        raise urllib.error.HTTPError(url, 422, "Unprocessable", None, None)  # type: ignore[arg-type]  # noqa: E501

    devin = DevinClient(api_key="k", org_id="org-1", transport=failing)
    with pytest.raises(urllib.error.HTTPError):
        devin.create_session("mutate")


def test_session_payload_defaults_are_safe() -> None:
    session = Session.from_payload({})
    assert session.acus_consumed == 0.0
    assert session.pull_requests == []
    assert not session.finished
