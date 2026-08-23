"""``entire-agent-devin`` — an Entire external agent plugin for Devin.

Entire discovers external agents by scanning ``$PATH`` for executables named
``entire-agent-<name>`` and speaking protocol version 1 to them over
stdin/stdout. This module implements that protocol for Devin, so Devin's cloud
sessions become Entire checkpoints in the repository they modified.

Devin runs remotely and has no local lifecycle hooks, so hook delivery is done
by :mod:`tools.entire_agent_devin.bridge`, which tails the Devin API and pipes
payloads into ``entire hooks devin <hook>``. ``install-hooks`` records the hook
table the bridge dispatches against.

Reference: https://docs.entire.io/agents/external-agent-plugins/architecture
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import transcript as tx

PROTOCOL_VERSION = 1
AGENT_NAME = "devin"
BRIDGE_BIN = "entire-devin-bridge"

HOOK_DIR = Path(".devin") / "entire"
HOOK_TABLE_FILE = HOOK_DIR / "hooks.json"

# Entire event types (see the protocol data model).
EVENT_SESSION_START = 1
EVENT_TURN_START = 2
EVENT_TURN_END = 3
EVENT_COMPACTION = 4
EVENT_SESSION_END = 5

HOOK_EVENTS: dict[str, int] = {
    "session-start": EVENT_SESSION_START,
    "user-prompt-submit": EVENT_TURN_START,
    "stop": EVENT_TURN_END,
    "compaction": EVENT_COMPACTION,
    "session-end": EVENT_SESSION_END,
}


class PluginError(Exception):
    """Reported to the CLI as a non-zero exit with a message on stderr."""


# --------------------------------------------------------------------------- #
# session storage
# --------------------------------------------------------------------------- #


def repo_root() -> Path:
    """The repository Entire is operating on.

    The CLI sets ``ENTIRE_REPO_ROOT`` and runs the plugin from that directory.
    """
    return Path(os.environ.get("ENTIRE_REPO_ROOT") or Path.cwd()).resolve()


def data_home() -> Path:
    override = os.environ.get("ENTIRE_DEVIN_DATA_HOME")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return base / "entire-agent-devin"


def repo_slug(repo_path: str | os.PathLike[str]) -> str:
    """A filesystem-safe, collision-resistant name for a repository path."""
    resolved = str(Path(repo_path).expanduser().resolve())
    digest = hashlib.sha256(resolved.encode()).hexdigest()[:10]
    name = re.sub(r"[^A-Za-z0-9_.-]+", "-", Path(resolved).name).strip("-")
    return f"{name or 'repo'}-{digest}"


def session_dir(repo_path: str | os.PathLike[str]) -> Path:
    """Where transcripts for ``repo_path`` live.

    Transcripts stay outside the repository: Entire stores what it needs on the
    checkpoint branch, and raw agent logs should not become working-tree noise.
    """
    return data_home() / "sessions" / repo_slug(repo_path)


def sanitize_session_id(session_id: str) -> str:
    if not session_id:
        raise PluginError("session id is required")
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "-", session_id).strip("-")
    if not cleaned or set(cleaned) <= {"."}:
        raise PluginError(f"unusable session id: {session_id!r}")
    return cleaned


def transcript_path(directory: str | os.PathLike[str], session_id: str) -> Path:
    return Path(directory) / f"{sanitize_session_id(session_id)}.jsonl"


def metadata_path(session_ref: str | os.PathLike[str]) -> Path:
    """Sidecar holding the AgentSession fields Entire hands back to us."""
    ref = Path(session_ref)
    return ref.with_name(ref.name + ".session.json")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def read_stdin_bytes() -> bytes:
    return sys.stdin.buffer.read()


def read_stdin_json() -> dict[str, Any]:
    raw = read_stdin_bytes().strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PluginError(f"invalid JSON on stdin: {exc}") from exc
    if not isinstance(payload, dict):
        raise PluginError("expected a JSON object on stdin")
    return payload


def emit(payload: Any) -> None:
    sys.stdout.write(json.dumps(payload))
    sys.stdout.write("\n")


def emit_bytes(payload: bytes) -> None:
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def hook_input_session_id(payload: dict[str, Any]) -> str:
    for key in ("session_id", "sessionId"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    raw = payload.get("raw_data")
    if isinstance(raw, dict):
        return hook_input_session_id(raw)
    raise PluginError("hook input contains no session_id")


def resolve_session_ref(payload: dict[str, Any]) -> Path:
    """The transcript path for a hook input, derived if not supplied."""
    ref = payload.get("session_ref")
    if isinstance(ref, str) and ref:
        return Path(ref)
    return transcript_path(session_dir(repo_root()), hook_input_session_id(payload))


# --------------------------------------------------------------------------- #
# required commands
# --------------------------------------------------------------------------- #


def cmd_info(_: argparse.Namespace) -> None:
    emit(
        {
            "protocol_version": PROTOCOL_VERSION,
            "name": AGENT_NAME,
            "type": "Devin",
            "description": "Devin - Cognition's cloud software engineer",
            "is_preview": True,
            "protected_dirs": [".devin"],
            "hook_names": list(HOOK_EVENTS),
            "capabilities": {
                "hooks": True,
                "transcript_analyzer": True,
                "transcript_preparer": False,
                "token_calculator": True,
                "text_generator": False,
                "hook_response_writer": False,
                "subagent_aware_extractor": False,
            },
        }
    )


def cmd_detect(_: argparse.Namespace) -> None:
    """Devin is a cloud agent, so there is no local agent binary to look for.

    The real dependency is the hook transport: without ``entire-devin-bridge``
    on ``$PATH`` nothing can deliver Devin's activity to Entire. An API key is
    needed only for live polling, not for ``capture`` or ``session attach``, so
    it is not required here.
    """
    present = bool(
        shutil.which(BRIDGE_BIN)
        or os.environ.get("DEVIN_API_KEY")
        or session_dir(repo_root()).exists()
    )
    emit({"present": present})


def cmd_get_session_id(_: argparse.Namespace) -> None:
    emit({"session_id": hook_input_session_id(read_stdin_json())})


def cmd_get_session_dir(args: argparse.Namespace) -> None:
    directory = session_dir(args.repo_path or repo_root())
    directory.mkdir(parents=True, exist_ok=True)
    emit({"session_dir": str(directory)})


def cmd_resolve_session_file(args: argparse.Namespace) -> None:
    emit({"session_file": str(transcript_path(args.session_dir, args.session_id))})


def cmd_read_session(_: argparse.Namespace) -> None:
    payload = read_stdin_json()
    session_id = hook_input_session_id(payload)
    ref = resolve_session_ref(payload)

    session: dict[str, Any] = {
        "session_id": session_id,
        "agent_name": AGENT_NAME,
        "repo_path": str(repo_root()),
        "session_ref": str(ref),
        "start_time": payload.get("timestamp") or "",
        "native_data": None,
        "modified_files": [],
        "new_files": [],
        "deleted_files": [],
    }

    stored = metadata_path(ref)
    if stored.exists():
        try:
            saved = json.loads(stored.read_text())
        except json.JSONDecodeError:
            saved = {}
        if isinstance(saved, dict):
            session.update({k: v for k, v in saved.items() if k in session})

    changes = tx.extract_file_changes(tx.read_slice(str(ref)))
    session["modified_files"] = changes.modified
    session["new_files"] = changes.new
    session["deleted_files"] = changes.deleted
    if not session["start_time"]:
        session["start_time"] = _first_timestamp(str(ref))
    emit(session)


def _first_timestamp(path: str) -> str:
    for record in tx.iter_records(tx.read_slice(path)):
        stamp = record.get("timestamp")
        if isinstance(stamp, str) and stamp:
            return stamp
    return ""


def cmd_write_session(_: argparse.Namespace) -> None:
    session = read_stdin_json()
    session_id = hook_input_session_id(session)
    ref = session.get("session_ref")
    ref_path = (
        Path(ref)
        if isinstance(ref, str) and ref
        else transcript_path(session_dir(repo_root()), session_id)
    )
    ref_path.parent.mkdir(parents=True, exist_ok=True)
    ref_path.touch(exist_ok=True)

    session.setdefault("agent_name", AGENT_NAME)
    session["session_ref"] = str(ref_path)
    metadata_path(ref_path).write_text(json.dumps(session, indent=2, sort_keys=True))


def cmd_read_transcript(args: argparse.Namespace) -> None:
    emit_bytes(tx.read_slice(args.session_ref))


def cmd_chunk_transcript(args: argparse.Namespace) -> None:
    if args.max_size <= 0:
        raise PluginError("--max-size must be positive")
    raw = read_stdin_bytes()
    chunks = [
        base64.b64encode(raw[start : start + args.max_size]).decode()
        for start in range(0, len(raw), args.max_size)
    ]
    emit({"chunks": chunks})


def cmd_reassemble_transcript(_: argparse.Namespace) -> None:
    payload = read_stdin_json()
    chunks = payload.get("chunks")
    if chunks is None:
        chunks = []
    if not isinstance(chunks, list):
        raise PluginError("chunks must be a list")
    out = bytearray()
    for chunk in chunks:
        if not isinstance(chunk, str):
            raise PluginError("each chunk must be a base64 string")
        try:
            out += base64.b64decode(chunk, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise PluginError(f"chunk is not valid base64: {exc}") from exc
    emit_bytes(bytes(out))


def cmd_format_resume_command(args: argparse.Namespace) -> None:
    session = sanitize_session_id(args.session_id)
    emit({"command": f"{BRIDGE_BIN} follow --session {session}"})


# --------------------------------------------------------------------------- #
# hooks capability
# --------------------------------------------------------------------------- #


def cmd_parse_hook(args: argparse.Namespace) -> None:
    """Normalize a bridge payload into an Entire event.

    Hooks with no lifecycle significance return ``null``, which tells the CLI
    to do nothing.
    """
    payload = read_stdin_json()
    hook = args.hook or payload.get("hook_type") or ""
    event_type = HOOK_EVENTS.get(hook.replace("_", "-"))
    if event_type is None:
        emit(None)
        return

    try:
        session_id = hook_input_session_id(payload)
    except PluginError:
        emit(None)
        return

    event: dict[str, Any] = {"type": event_type, "session_id": session_id}
    ref = payload.get("session_ref")
    if isinstance(ref, str) and ref:
        event["session_ref"] = ref
    else:
        event["session_ref"] = str(resolve_session_ref(payload))
    for source, target in (("user_prompt", "prompt"), ("timestamp", "timestamp")):
        value = payload.get(source)
        if isinstance(value, str) and value:
            event[target] = value
    model = payload.get("model") or tx.latest_model(tx.read_slice(event["session_ref"]))
    if isinstance(model, str) and model:
        event["model"] = model
    emit(event)


def hook_table() -> dict[str, str]:
    return {hook: f"entire hooks {AGENT_NAME} {hook}" for hook in HOOK_EVENTS}


def cmd_install_hooks(args: argparse.Namespace) -> None:
    """Record the hook table the bridge dispatches against.

    Devin has no local process to hook, so this writes the contract instead of
    editing an agent config: the bridge reads it to decide which
    ``entire hooks devin <hook>`` command to invoke for each API event.
    """
    target = repo_root() / HOOK_TABLE_FILE
    if target.exists() and not args.force:
        emit({"hooks_installed": len(hook_table())})
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    table = hook_table()
    if args.local_dev:
        table = {
            hook: command.replace("entire ", "./entire ", 1)
            for hook, command in table.items()
        }
    target.write_text(
        json.dumps(
            {
                "agent": AGENT_NAME,
                "protocol_version": PROTOCOL_VERSION,
                "transport": "entire-devin-bridge",
                "hooks": table,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    emit({"hooks_installed": len(table)})


def cmd_uninstall_hooks(_: argparse.Namespace) -> None:
    target = repo_root() / HOOK_TABLE_FILE
    if target.exists():
        target.unlink()
    parent = target.parent
    if parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()


def cmd_are_hooks_installed(_: argparse.Namespace) -> None:
    emit({"installed": (repo_root() / HOOK_TABLE_FILE).exists()})


# --------------------------------------------------------------------------- #
# transcript_analyzer capability
# --------------------------------------------------------------------------- #


def cmd_get_transcript_position(args: argparse.Namespace) -> None:
    path = Path(args.path)
    emit({"position": path.stat().st_size if path.exists() else 0})


def cmd_extract_modified_files(args: argparse.Namespace) -> None:
    path = Path(args.path)
    changes = tx.extract_file_changes(tx.read_slice(args.path, args.offset))
    emit(
        {
            "files": changes.touched,
            "current_position": path.stat().st_size if path.exists() else 0,
        }
    )


def cmd_extract_prompts(args: argparse.Namespace) -> None:
    emit({"prompts": tx.extract_prompts(tx.read_slice(args.session_ref, args.offset))})


def cmd_extract_summary(args: argparse.Namespace) -> None:
    summary = tx.extract_summary(tx.read_slice(args.session_ref))
    emit({"summary": summary or "", "has_summary": bool(summary)})


# --------------------------------------------------------------------------- #
# token_calculator capability
# --------------------------------------------------------------------------- #


def cmd_calculate_tokens(args: argparse.Namespace) -> None:
    raw = read_stdin_bytes()
    if args.offset > 0:
        raw = raw[args.offset :]
    emit(tx.sum_tokens(raw))


# --------------------------------------------------------------------------- #
# CLI wiring
# --------------------------------------------------------------------------- #

Handler = Callable[[argparse.Namespace], None]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"entire-agent-{AGENT_NAME}",
        description="Entire external agent plugin for Devin (protocol v1).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add(name: str, handler: Handler) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(name)
        sub.set_defaults(handler=handler)
        return sub

    add("info", cmd_info)
    add("detect", cmd_detect)
    add("get-session-id", cmd_get_session_id)
    add("get-session-dir", cmd_get_session_dir).add_argument("--repo-path", default="")
    resolve = add("resolve-session-file", cmd_resolve_session_file)
    resolve.add_argument("--session-dir", required=True)
    resolve.add_argument("--session-id", required=True)
    add("read-session", cmd_read_session)
    add("write-session", cmd_write_session)
    add("read-transcript", cmd_read_transcript).add_argument(
        "--session-ref", required=True
    )
    add("chunk-transcript", cmd_chunk_transcript).add_argument(
        "--max-size", type=int, required=True
    )
    add("reassemble-transcript", cmd_reassemble_transcript)
    add("format-resume-command", cmd_format_resume_command).add_argument(
        "--session-id", required=True
    )

    add("parse-hook", cmd_parse_hook).add_argument("--hook", default="")
    install = add("install-hooks", cmd_install_hooks)
    install.add_argument("--local-dev", action="store_true")
    install.add_argument("--force", action="store_true")
    add("uninstall-hooks", cmd_uninstall_hooks)
    add("are-hooks-installed", cmd_are_hooks_installed)

    position = add("get-transcript-position", cmd_get_transcript_position)
    position.add_argument("--path", required=True)
    modified = add("extract-modified-files", cmd_extract_modified_files)
    modified.add_argument("--path", required=True)
    modified.add_argument("--offset", type=int, default=0)
    prompts = add("extract-prompts", cmd_extract_prompts)
    prompts.add_argument("--session-ref", required=True)
    prompts.add_argument("--offset", type=int, default=0)
    add("extract-summary", cmd_extract_summary).add_argument(
        "--session-ref", required=True
    )

    add("calculate-tokens", cmd_calculate_tokens).add_argument(
        "--offset", type=int, default=0
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except PluginError as exc:
        print(f"entire-agent-{AGENT_NAME}: {exc}", file=sys.stderr)
        return 1
    return 0
