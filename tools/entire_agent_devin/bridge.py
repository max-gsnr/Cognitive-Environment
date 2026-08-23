"""``entire-devin-bridge`` — hook transport for Devin sessions.

Local agents fire Entire's hooks themselves. Devin runs in Cognition's cloud
and cannot, so the bridge stands in for that: it polls the Devin API for a
session, appends new activity to the session transcript, and invokes
``entire hooks devin <hook>`` with a payload for each lifecycle event. From the
CLI's point of view this is indistinguishable from a local agent's hooks.

    entire-devin-bridge follow  --session devin-abc123
    entire-devin-bridge capture --session devin-abc123 --payload session.json
    entire-devin-bridge attach  --session devin-abc123

``capture`` ingests an already-saved API payload, which is what CI and the
offline demo use; ``follow`` is the live path and needs ``DEVIN_API_KEY``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .plugin import AGENT_NAME, HOOK_EVENTS, repo_root, session_dir, transcript_path

DEFAULT_API_BASE = "https://api.devin.ai/v1"
# Record types that mean Devin produced work in this batch, so the turn ended.
TURN_OUTPUT_TYPES = {"devin_message", "tool_use", "file_change"}
TERMINAL_STATUSES = {"blocked", "finished", "expired", "stopped", "suspended"}
POLL_INTERVAL_SECONDS = 5.0

MODIFIED_KEYS = ("modified_files", "files_modified", "changed_files")
NEW_KEYS = ("new_files", "created_files", "files_created")
DELETED_KEYS = ("deleted_files", "removed_files", "files_deleted")


class BridgeError(Exception):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- #
# Devin API
# --------------------------------------------------------------------------- #


def api_base() -> str:
    return os.environ.get("DEVIN_API_BASE", DEFAULT_API_BASE).rstrip("/")


def fetch_session(session_id: str) -> dict[str, Any]:
    """Fetch a session from the Devin API.

    Reference: ``GET /v1/sessions/{session_id}`` (docs.devin.ai v1 OpenAPI).
    For the v3 API, point ``DEVIN_API_BASE`` at
    ``https://api.devin.ai/v3/organizations/<org_id>``: the path suffix matches
    and the response carries the same ``messages`` / ``status_enum`` fields.
    """
    api_key = os.environ.get("DEVIN_API_KEY")
    if not api_key:
        raise BridgeError(
            "DEVIN_API_KEY is not set. Use 'capture --payload <file>' to ingest a "
            "saved API response instead of polling."
        )
    request = urllib.request.Request(
        f"{api_base()}/sessions/{session_id}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise BridgeError(
            f"Devin API returned {exc.code} for session {session_id}: {exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise BridgeError(f"cannot reach the Devin API: {exc.reason}") from exc
    if not isinstance(payload, dict):
        raise BridgeError("unexpected Devin API response: expected a JSON object")
    return payload


# --------------------------------------------------------------------------- #
# API payload -> transcript records
# --------------------------------------------------------------------------- #


def _string_list(source: dict[str, Any], keys: Iterable[str]) -> list[str]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str) and item]
    return []


def normalize(payload: dict[str, Any], session_id: str) -> list[dict[str, Any]]:
    """Convert an API session payload into ordered transcript records.

    Only fields the API is documented to return are read, and anything missing
    is omitted rather than invented. Records are derived deterministically from
    the payload — no wall-clock values — so re-syncing an unchanged session
    produces byte-identical records and appends nothing.
    """
    records: list[dict[str, Any]] = []
    messages = payload.get("messages")
    if isinstance(messages, list):
        for index, message in enumerate(messages):
            if not isinstance(message, dict):
                continue
            text = message.get("message")
            if not isinstance(text, str) or not text.strip():
                continue
            kind = str(message.get("type", ""))
            record: dict[str, Any] = {
                "type": ("user_message" if "user" in kind.lower() else "devin_message"),
                "session_id": session_id,
                "timestamp": message.get("timestamp") or f"message-{index}",
                "message": text,
                "model": AGENT_NAME,
            }
            usage = message.get("usage")
            if isinstance(usage, dict):
                record["usage"] = usage
            records.append(record)

    anchor = records[-1]["timestamp"] if records else ""
    structured = payload.get("structured_output")
    if isinstance(structured, dict):
        files = {
            "modified": _string_list(structured, MODIFIED_KEYS),
            "new": _string_list(structured, NEW_KEYS),
            "deleted": _string_list(structured, DELETED_KEYS),
        }
        if any(files.values()):
            records.append(
                {
                    "type": "file_change",
                    "session_id": session_id,
                    "timestamp": anchor,
                    "files": files,
                }
            )

    summary = None
    if isinstance(structured, dict):
        summary = structured.get("summary")
    summary = summary or payload.get("title")
    if isinstance(summary, str) and summary.strip():
        _attach_summary(records, summary)
    return records


def _attach_summary(records: list[dict[str, Any]], summary: str) -> None:
    """Carry the session summary on its latest agent message.

    Attaching rather than appending keeps the summary from accumulating as a
    duplicate record every time the session is re-synced, and a session that
    has not produced an agent message yet stays free of synthetic turns.
    """
    for record in reversed(records):
        if record["type"] == "devin_message":
            record["summary"] = summary
            return


def transcript_for(session_id: str) -> Path:
    directory = session_dir(repo_root())
    directory.mkdir(parents=True, exist_ok=True)
    return transcript_path(directory, session_id)


def existing_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def append_records(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _fingerprint(record: dict[str, Any]) -> str:
    return json.dumps(
        {key: record.get(key) for key in ("type", "message", "files", "timestamp")},
        sort_keys=True,
    )


def new_records(
    path: Path, candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Records not already in the transcript, preserving order."""
    seen = {_fingerprint(record) for record in existing_records(path)}
    fresh = []
    for record in candidates:
        key = _fingerprint(record)
        if key in seen:
            continue
        seen.add(key)
        fresh.append(record)
    return fresh


# --------------------------------------------------------------------------- #
# hook dispatch
# --------------------------------------------------------------------------- #


def hook_command(hook: str) -> list[str]:
    entire = os.environ.get("ENTIRE_BIN", "entire")
    return [entire, "hooks", AGENT_NAME, hook]


def fire_hook(hook: str, payload: dict[str, Any], *, dry_run: bool = False) -> int:
    if hook not in HOOK_EVENTS:
        raise BridgeError(f"unknown hook: {hook}")
    command = hook_command(hook)
    body = json.dumps(payload)
    if dry_run:
        print(f"$ {' '.join(command)} <<< {body}")
        return 0
    result = subprocess.run(
        command, input=body.encode(), capture_output=True, check=False
    )
    if result.returncode != 0:
        sys.stderr.write(
            f"hook {hook} failed ({result.returncode}): "
            f"{result.stderr.decode(errors='replace').strip()}\n"
        )
    elif result.stdout:
        sys.stdout.write(result.stdout.decode(errors="replace"))
    return result.returncode


def hook_payload(
    hook: str, session_id: str, ref: Path, prompt: str | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "hook_type": hook,
        "session_id": session_id,
        "session_ref": str(ref),
        "timestamp": now(),
        "model": AGENT_NAME,
    }
    if prompt:
        payload["user_prompt"] = prompt
    return payload


def dispatch(
    session_id: str,
    ref: Path,
    records: list[dict[str, Any]],
    *,
    first_sync: bool,
    terminal: bool,
    dry_run: bool = False,
) -> list[str]:
    """Fire the hooks implied by a batch of new transcript records."""
    fired: list[str] = []

    def send(hook: str, prompt: str | None = None) -> None:
        fire_hook(hook, hook_payload(hook, session_id, ref, prompt), dry_run=dry_run)
        fired.append(hook)

    if first_sync:
        send("session-start")
    for record in records:
        if record.get("type") == "user_message":
            send("user-prompt-submit", record.get("message"))
    if any(record.get("type") in TURN_OUTPUT_TYPES for record in records):
        send("stop")
    if terminal:
        send("session-end")
    return fired


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #


def sync_once(
    session_id: str, payload: dict[str, Any], *, dry_run: bool = False
) -> dict[str, Any]:
    ref = transcript_for(session_id)
    first_sync = not ref.exists() or not existing_records(ref)
    records = new_records(ref, normalize(payload, session_id))
    append_records(ref, records)
    status = str(payload.get("status_enum") or payload.get("status") or "").lower()
    fired = dispatch(
        session_id,
        ref,
        records,
        first_sync=first_sync,
        terminal=status in TERMINAL_STATUSES,
        dry_run=dry_run,
    )
    return {
        "session_id": session_id,
        "session_ref": str(ref),
        "status": status,
        "new_records": len(records),
        "hooks_fired": fired,
    }


def cmd_capture(args: argparse.Namespace) -> int:
    try:
        payload = json.loads(Path(args.payload).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise BridgeError(f"cannot read payload {args.payload}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BridgeError("payload must be a JSON object")
    session_id = args.session or payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        raise BridgeError("--session is required when the payload has no session_id")
    print(json.dumps(sync_once(session_id, payload, dry_run=args.dry_run), indent=2))
    return 0


def cmd_follow(args: argparse.Namespace) -> int:
    deadline = time.monotonic() + args.timeout if args.timeout else None
    while True:
        result = sync_once(
            args.session, fetch_session(args.session), dry_run=args.dry_run
        )
        print(json.dumps(result))
        if result["status"] in TERMINAL_STATUSES:
            return 0
        if args.once:
            return 0
        if deadline and time.monotonic() >= deadline:
            sys.stderr.write(f"timed out waiting for session {args.session}\n")
            return 2
        time.sleep(args.interval)


def cmd_attach(args: argparse.Namespace) -> int:
    """Hand a session to ``entire session attach``.

    Used when a Devin session ran before the bridge was watching, or when its
    checkpoint should be linked to a commit made afterwards.
    """
    entire = os.environ.get("ENTIRE_BIN", "entire")
    command = [entire, "session", "attach", args.session, "-a", AGENT_NAME]
    if args.force:
        command.append("-f")
    return subprocess.run(command, check=False).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="entire-devin-bridge",
        description="Deliver Devin cloud session activity to Entire's hooks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser(
        "capture", help="ingest a saved Devin API session payload"
    )
    capture.add_argument("--payload", required=True)
    capture.add_argument("--session", default="")
    capture.add_argument("--dry-run", action="store_true")
    capture.set_defaults(handler=cmd_capture)

    follow = subparsers.add_parser("follow", help="poll a live Devin session")
    follow.add_argument("--session", required=True)
    follow.add_argument("--interval", type=float, default=POLL_INTERVAL_SECONDS)
    follow.add_argument(
        "--timeout", type=float, default=0.0, help="seconds; 0 waits forever"
    )
    follow.add_argument("--once", action="store_true", help="sync once and exit")
    follow.add_argument("--dry-run", action="store_true")
    follow.set_defaults(handler=cmd_follow)

    attach = subparsers.add_parser(
        "attach", help="attach a session to the last commit as a checkpoint"
    )
    attach.add_argument("--session", required=True)
    attach.add_argument("-f", "--force", action="store_true")
    attach.set_defaults(handler=cmd_attach)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except BridgeError as exc:
        print(f"entire-devin-bridge: {exc}", file=sys.stderr)
        return 1
