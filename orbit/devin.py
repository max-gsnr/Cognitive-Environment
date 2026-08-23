"""Devin API client — the mutation operator is an agent session, not a template.

Endpoints are the current v3 organization-scoped ones (the v1 paths in earlier
drafts of this project were wrong):

    POST /v3/organizations/{org_id}/sessions
    GET  /v3/organizations/{org_id}/sessions/{devin_id}
    POST /v3/organizations/{org_id}/sessions/{devin_id}/messages

Two details do real work here:

* ``structured_output_schema`` — the session returns a validated JSON object, so
  the orchestrator reads the branch name and the candidate's self-reported score
  from a field instead of scraping prose out of a transcript.
* ``max_acu_limit`` — a generation of parallel sessions is the expensive part of
  this system, so every session is capped and the consumed ACUs are recorded per
  candidate.

Only the standard library is used: this has to run inside a Devin session that
may not have extra packages installed.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

DEFAULT_BASE = "https://api.devin.ai"
TERMINAL = {"exit", "error", "suspended"}

#: What each mutation session must hand back. Draft-7, self-contained.
MUTATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "branch", "mechanism", "gates_passed"],
    "properties": {
        "summary": {
            "type": "string",
            "description": "One line: what changed in the game.",
        },
        "branch": {
            "type": "string",
            "description": "Branch the candidate was pushed to.",
        },
        "mechanism": {
            "type": "string",
            "description": "Why this should move the fitness score.",
        },
        "gates_passed": {"type": "boolean"},
        "self_reported_fitness": {"type": ["number", "null"]},
        "notes": {"type": ["string", "null"]},
    },
}


class DevinError(RuntimeError):
    pass


class MissingCredentials(DevinError):
    """No API key/org id. Never silently substituted with a mock."""


@dataclass
class Session:
    session_id: str
    url: str
    status: str = "new"
    acus_consumed: float = 0.0
    structured_output: dict[str, Any] | None = None
    pull_requests: list[dict[str, Any]] = field(default_factory=list)

    @property
    def finished(self) -> bool:
        return self.status in TERMINAL

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Session:
        return cls(
            session_id=payload.get("session_id", ""),
            url=payload.get("url", ""),
            status=payload.get("status", "new"),
            acus_consumed=float(payload.get("acus_consumed") or 0.0),
            structured_output=payload.get("structured_output"),
            pull_requests=list(payload.get("pull_requests") or []),
        )


class DevinClient:
    """Thin, typed wrapper. `transport` is injectable so tests never hit the API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        org_id: str | None = None,
        base_url: str | None = None,
        transport: Any | None = None,
    ) -> None:
        # `is None` rather than falsy: an explicit empty string means "no
        # credential", and must not quietly fall back to the ambient environment.
        self.api_key = os.environ.get("DEVIN_API_KEY", "") if api_key is None else api_key
        self.org_id = os.environ.get("DEVIN_ORG_ID", "") if org_id is None else org_id
        self.base_url = (base_url or os.environ.get("DEVIN_API_BASE", DEFAULT_BASE)).rstrip(
            "/"
        )
        self._transport = transport

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.org_id)

    def _require(self) -> None:
        if self._transport is not None:
            return
        missing = [
            name
            for name, value in (("DEVIN_API_KEY", self.api_key), ("DEVIN_ORG_ID", self.org_id))
            if not value
        ]
        if missing:
            raise MissingCredentials(
                f"set {' and '.join(missing)} to run agent mutations"
            )

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        self._require()
        url = f"{self.base_url}{path}"
        payload = json.dumps(body).encode() if body is not None else None
        if self._transport is not None:
            return self._transport(method, url, body)

        request = urllib.request.Request(url, data=payload, method=method)
        request.add_header("Authorization", f"Bearer {self.api_key}")
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode() or "{}")
        except urllib.error.HTTPError as error:  # surface the API's own message
            detail = error.read().decode()[:400]
            raise DevinError(f"{method} {path} -> {error.code}: {detail}") from error

    # --- sessions -------------------------------------------------------

    def create_session(
        self,
        prompt: str,
        *,
        title: str | None = None,
        repos: list[str] | None = None,
        tags: list[str] | None = None,
        max_acu_limit: int | None = 12,
        idempotent: bool = True,
    ) -> Session:
        body: dict[str, Any] = {
            "prompt": prompt,
            "structured_output_schema": MUTATION_SCHEMA,
            "structured_output_required": True,
        }
        if title:
            body["title"] = title
        if repos:
            body["repos"] = repos
        if tags:
            body["tags"] = tags
        if max_acu_limit:
            body["max_acu_limit"] = max_acu_limit
        if idempotent:
            body["idempotent"] = True
        payload = self._request(
            "POST", f"/v3/organizations/{self.org_id}/sessions", body
        )
        return Session.from_payload(payload)

    def get_session(self, session_id: str) -> Session:
        payload = self._request(
            "GET", f"/v3/organizations/{self.org_id}/sessions/{session_id}"
        )
        return Session.from_payload(payload)

    def send_message(self, session_id: str, message: str) -> None:
        self._request(
            "POST",
            f"/v3/organizations/{self.org_id}/sessions/{session_id}/messages",
            {"message": message},
        )

    def wait(
        self,
        session_id: str,
        *,
        timeout_s: float = 2400.0,
        poll_s: float = 20.0,
        sleep: Any = time.sleep,
        now: Any = time.monotonic,
    ) -> Session:
        """Block until the session reaches a terminal state or produces output.

        A session that has already provided its structured output is done for our
        purposes even if the agent is still idling, which saves waiting on the
        tail of a run that has nothing left to say.
        """
        deadline = now() + timeout_s
        session = self.get_session(session_id)
        while not session.finished and not session.structured_output:
            if now() >= deadline:
                raise DevinError(f"{session_id} did not finish within {timeout_s:.0f}s")
            sleep(poll_s)
            session = self.get_session(session_id)
        return session
