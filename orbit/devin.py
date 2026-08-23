"""Devin API client — the mutation operator is an agent session, not a template.

Two API generations are supported, because which one a key can use depends on
the key. The organization-scoped v3 endpoints

    POST /v3/organizations/{org_id}/sessions
    GET  /v3/organizations/{org_id}/sessions/{devin_id}
    POST /v3/organizations/{org_id}/sessions/{devin_id}/messages

are tried first; a user-scoped key (``apk_user_…``) gets 403 Forbidden on them
while working fine on v1, so the client then falls back to

    POST /v1/sessions
    GET  /v1/session/{devin_id}
    POST /v1/session/{devin_id}/message

This is a real fallback, not a mock: both paths create actual sessions. Set
``DEVIN_API_VERSION=v1`` or ``v3`` to pin one.

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
SESSION_URL = "https://app.devin.ai/sessions"
#: v3 statuses plus v1's ``status_enum`` values that mean "not going to progress".
TERMINAL = {"exit", "error", "suspended", "finished", "expired", "blocked"}

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
        session_id = payload.get("session_id", "")
        # v1 reports `status_enum` and a single `pull_request`; v3 reports
        # `status` and a list. Normalise both into one shape.
        single_pr = payload.get("pull_request")
        return cls(
            session_id=session_id,
            url=payload.get("url") or f"{SESSION_URL}/{session_id.removeprefix('devin-')}",
            status=payload.get("status_enum") or payload.get("status") or "new",
            acus_consumed=float(payload.get("acus_consumed") or 0.0),
            structured_output=payload.get("structured_output"),
            pull_requests=list(
                payload.get("pull_requests") or ([single_pr] if single_pr else [])
            ),
        )


class DevinClient:
    """Thin, typed wrapper. `transport` is injectable so tests never hit the API."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        org_id: str | None = None,
        base_url: str | None = None,
        api_version: str | None = None,
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
        self.api_version = (
            api_version or os.environ.get("DEVIN_API_VERSION") or "auto"
        ).lower()
        # v3 paths are org-scoped, so without an org id there is nothing to try:
        # start on v1 rather than making a request that cannot succeed.
        self._version = (
            "v1" if self.api_version == "v1" or (self.api_version == "auto" and not self.org_id)
            else "v3"
        )

    @property
    def configured(self) -> bool:
        # v1 is keyed on the API key alone; only v3's paths need the org id.
        return bool(self.api_key) and (self._version == "v1" or bool(self.org_id))

    def _require(self) -> None:
        if self._transport is not None:
            return
        needed = [("DEVIN_API_KEY", self.api_key)]
        if self._version == "v3":
            needed.append(("DEVIN_ORG_ID", self.org_id))
        missing = [name for name, value in needed if not value]
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

    def _path(self, endpoint: str, session_id: str = "") -> str:
        if self._version == "v1":
            return {
                "create": "/v1/sessions",
                "get": f"/v1/session/{session_id}",
                "message": f"/v1/session/{session_id}/message",
            }[endpoint]
        root = f"/v3/organizations/{self.org_id}/sessions"
        return {
            "create": root,
            "get": f"{root}/{session_id}",
            "message": f"{root}/{session_id}/messages",
        }[endpoint]

    def _call(
        self,
        endpoint: str,
        method: str,
        *,
        session_id: str = "",
        body: dict[str, Any] | None = None,
    ) -> Any:
        try:
            return self._request(method, self._path(endpoint, session_id), body)
        except DevinError as error:
            downgradable = (
                self.api_version == "auto"
                and self._version == "v3"
                and (" -> 403:" in str(error) or " -> 404:" in str(error))
            )
            if not downgradable:
                raise
            # A user-scoped key cannot reach the org endpoints; v1 is not a
            # lesser mode here, it creates the same sessions.
            self._version = "v1"
            body = self._v1_body(body) if endpoint == "create" and body else body
            return self._request(method, self._path(endpoint, session_id), body)

    @staticmethod
    def _v1_body(body: dict[str, Any]) -> dict[str, Any]:
        """v1 create rejects unknown fields, and has no `repos`."""
        allowed = {
            "prompt",
            "title",
            "tags",
            "max_acu_limit",
            "idempotent",
            "structured_output_schema",
        }
        return {key: value for key, value in body.items() if key in allowed}

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
        if self._version == "v1":
            body = self._v1_body(body)
        payload = self._call("create", "POST", body=body)
        return Session.from_payload(payload)

    def get_session(self, session_id: str) -> Session:
        return Session.from_payload(self._call("get", "GET", session_id=session_id))

    def send_message(self, session_id: str, message: str) -> None:
        self._call("message", "POST", session_id=session_id, body={"message": message})

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
