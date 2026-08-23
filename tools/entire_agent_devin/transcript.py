"""Reading and interpreting Devin session transcripts.

A Devin transcript is a JSONL file. Each line is one record produced by the
bridge from the Devin API. Record shape:

    {
      "type": "session_start" | "user_message" | "devin_message"
              | "tool_use" | "file_change" | "session_end",
      "session_id": "devin-abc123",
      "timestamp": "2026-01-13T12:00:00Z",
      "message": "free text, for message records",
      "model": "devin",
      "tool": {"name": "shell", "input": {...}},
      "files": {"modified": [...], "new": [...], "deleted": [...]},
      "usage": {"input_tokens": 0, "output_tokens": 0, ...},
      "summary": "structured output / final summary"
    }

Unknown record types and unknown fields are ignored, so the format can grow
with the Devin API without breaking the plugin.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

PATH_KEYS = ("path", "file_path", "filename", "file", "target_file")

USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_tokens",
    "cache_read_tokens",
)


def iter_records(raw: bytes) -> Iterator[dict[str, Any]]:
    """Yield the JSON objects in a transcript, skipping unparsable lines."""
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            yield record


def read_slice(path: str, offset: int = 0) -> bytes:
    """Read a transcript from ``offset`` bytes onward.

    A short file (rewritten or truncated since the offset was taken) is read
    from the start rather than treated as empty.
    """
    try:
        with open(path, "rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(offset if 0 <= offset <= size else 0)
            return handle.read()
    except FileNotFoundError:
        return b""


@dataclass
class FileChanges:
    modified: list[str] = field(default_factory=list)
    new: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    @property
    def touched(self) -> list[str]:
        return _dedupe(self.modified + self.new + self.deleted)


def _dedupe(paths: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for path in paths:
        if isinstance(path, str) and path:
            seen.setdefault(path, None)
    return list(seen)


def extract_file_changes(raw: bytes) -> FileChanges:
    """Collect the files a session touched.

    Two sources are used: explicit ``file_change`` records, and path-bearing
    inputs of file-editing tool calls.
    """
    changes = FileChanges()
    for record in iter_records(raw):
        files = record.get("files")
        if isinstance(files, dict):
            for key, bucket in (
                ("modified", changes.modified),
                ("new", changes.new),
                ("deleted", changes.deleted),
            ):
                value = files.get(key)
                if isinstance(value, list):
                    bucket.extend(item for item in value if isinstance(item, str))
        changes.modified.extend(_tool_paths(record))

    changes.modified = [
        path
        for path in _dedupe(changes.modified)
        if path not in set(changes.new) | set(changes.deleted)
    ]
    changes.new = _dedupe(changes.new)
    changes.deleted = _dedupe(changes.deleted)
    return changes


def _tool_paths(record: dict[str, Any]) -> list[str]:
    if record.get("type") != "tool_use":
        return []
    tool = record.get("tool")
    if not isinstance(tool, dict):
        return []
    if not _is_write_tool(str(tool.get("name", ""))):
        return []
    tool_input = tool.get("input")
    if not isinstance(tool_input, dict):
        return []
    return [
        tool_input[key]
        for key in PATH_KEYS
        if isinstance(tool_input.get(key), str) and tool_input[key]
    ]


def _is_write_tool(name: str) -> bool:
    lowered = name.lower()
    return any(
        verb in lowered
        for verb in ("write", "edit", "create", "patch", "apply", "delete", "remove")
    )


def extract_prompts(raw: bytes) -> list[str]:
    """Return the human prompts sent to Devin, oldest first."""
    prompts: list[str] = []
    for record in iter_records(raw):
        if record.get("type") != "user_message":
            continue
        message = record.get("message")
        if isinstance(message, str) and message.strip():
            prompts.append(message)
    return prompts


def extract_summary(raw: bytes) -> str | None:
    """Return the session's own summary, preferring the most recent one."""
    summary: str | None = None
    for record in iter_records(raw):
        candidate = record.get("summary")
        if isinstance(candidate, str) and candidate.strip():
            summary = candidate
    return summary


def sum_tokens(raw: bytes) -> dict[str, int]:
    """Aggregate token usage. ``api_call_count`` counts records reporting usage."""
    totals = {name: 0 for name in USAGE_FIELDS}
    calls = 0
    for record in iter_records(raw):
        usage = record.get("usage")
        if not isinstance(usage, dict):
            continue
        counted = False
        for name in USAGE_FIELDS:
            value = usage.get(name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            totals[name] += int(value)
            counted = True
        if counted:
            calls += 1
    totals["api_call_count"] = calls
    return totals


def latest_model(raw: bytes) -> str | None:
    model: str | None = None
    for record in iter_records(raw):
        candidate = record.get("model")
        if isinstance(candidate, str) and candidate:
            model = candidate
    return model
