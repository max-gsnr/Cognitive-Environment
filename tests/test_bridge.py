"""Tests for the Devin -> Entire hook bridge."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from entire_agent_devin import bridge  # noqa: E402

SESSION_ID = "devin-abc123"

API_PAYLOAD: dict[str, Any] = {
    "session_id": SESSION_ID,
    "status_enum": "working",
    "title": "Add a cooldown to Leo's game",
    "messages": [
        {
            "type": "user_message",
            "message": "Add a non-punitive cooldown after a wrong answer.",
            "timestamp": "2026-01-13T12:00:01Z",
        },
        {
            "type": "devin_message",
            "message": "Patched games/leo/v1/index.html.",
            "timestamp": "2026-01-13T12:00:30Z",
        },
    ],
}


@pytest.fixture(autouse=True)
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setenv("ENTIRE_REPO_ROOT", str(root))
    monkeypatch.setenv("ENTIRE_DEVIN_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.delenv("DEVIN_API_KEY", raising=False)
    return root


@pytest.fixture
def fired(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    """Capture hook invocations instead of shelling out to the Entire CLI."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def record(hook: str, payload: dict[str, Any], *, dry_run: bool = False) -> int:
        calls.append((hook, payload))
        return 0

    monkeypatch.setattr(bridge, "fire_hook", record)
    return calls


def test_normalize_maps_messages_and_summary() -> None:
    records = bridge.normalize(API_PAYLOAD, SESSION_ID)
    assert [record["type"] for record in records] == ["user_message", "devin_message"]
    assert records[0]["message"].startswith("Add a non-punitive")
    assert records[-1]["summary"] == "Add a cooldown to Leo's game"


def test_normalize_is_deterministic() -> None:
    """Re-syncing must not produce new records, so no wall-clock timestamps."""
    assert bridge.normalize(API_PAYLOAD, SESSION_ID) == bridge.normalize(
        API_PAYLOAD, SESSION_ID
    )


def test_normalize_reads_file_changes_from_structured_output() -> None:
    payload = dict(
        API_PAYLOAD,
        structured_output={
            "modified_files": ["games/leo/v1/index.html"],
            "new_files": ["games/leo/v2/index.html"],
        },
    )
    records = bridge.normalize(payload, SESSION_ID)
    changes = [r for r in records if r["type"] == "file_change"]
    assert changes[0]["files"]["modified"] == ["games/leo/v1/index.html"]
    assert changes[0]["files"]["new"] == ["games/leo/v2/index.html"]


def test_normalize_carries_per_message_token_usage() -> None:
    """Usage must survive into the transcript or `calculate-tokens` reads zero."""
    payload = {
        "messages": [
            {
                "type": "devin_message",
                "message": "Done.",
                "usage": {"input_tokens": 120, "output_tokens": 34},
            },
            {"type": "user_message", "message": "Thanks.", "usage": "not-a-dict"},
        ]
    }
    records = bridge.normalize(payload, SESSION_ID)
    assert records[0]["usage"] == {"input_tokens": 120, "output_tokens": 34}
    assert "usage" not in records[1]


def test_normalize_ignores_empty_and_malformed_messages() -> None:
    payload = {"messages": [{"type": "user_message", "message": "  "}, "junk", 42]}
    assert bridge.normalize(payload, SESSION_ID) == []


def test_sync_writes_transcript_and_fires_lifecycle_hooks(
    fired: list[tuple[str, dict[str, Any]]],
) -> None:
    result = bridge.sync_once(SESSION_ID, API_PAYLOAD)

    assert [hook for hook, _ in fired] == [
        "session-start",
        "user-prompt-submit",
        "stop",
    ]
    assert fired[1][1]["user_prompt"].startswith("Add a non-punitive")
    assert all(payload["session_id"] == SESSION_ID for _, payload in fired)

    transcript = Path(result["session_ref"])
    assert transcript.exists()
    assert result["new_records"] == 2
    assert len(transcript.read_text().strip().splitlines()) == 2


def test_sync_is_idempotent(fired: list[tuple[str, dict[str, Any]]]) -> None:
    first = bridge.sync_once(SESSION_ID, API_PAYLOAD)
    fired.clear()
    second = bridge.sync_once(SESSION_ID, API_PAYLOAD)

    assert second["new_records"] == 0
    assert fired == [], "an unchanged session should not re-fire hooks"
    assert len(Path(first["session_ref"]).read_text().strip().splitlines()) == 2


def test_sync_appends_only_new_activity(
    fired: list[tuple[str, dict[str, Any]]],
) -> None:
    bridge.sync_once(SESSION_ID, API_PAYLOAD)
    fired.clear()

    grown = dict(API_PAYLOAD)
    grown["messages"] = [
        *API_PAYLOAD["messages"],
        {
            "type": "user_message",
            "message": "Also compress the reward cadence.",
            "timestamp": "2026-01-13T12:05:00Z",
        },
    ]
    result = bridge.sync_once(SESSION_ID, grown)

    assert result["new_records"] == 1
    assert [hook for hook, _ in fired] == ["user-prompt-submit"]


def test_terminal_status_fires_session_end(
    fired: list[tuple[str, dict[str, Any]]],
) -> None:
    payload = dict(API_PAYLOAD, status_enum="finished")
    result = bridge.sync_once(SESSION_ID, payload)
    assert result["status"] == "finished"
    assert fired[-1][0] == "session-end"


def test_fetch_session_without_api_key_explains_the_alternative() -> None:
    with pytest.raises(bridge.BridgeError, match="capture"):
        bridge.fetch_session(SESSION_ID)


def test_capture_command_reads_a_saved_payload(
    tmp_path: Path,
    fired: list[tuple[str, dict[str, Any]]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload_file = tmp_path / "session.json"
    payload_file.write_text(json.dumps(dict(API_PAYLOAD, status_enum="finished")))

    assert bridge.main(["capture", "--payload", str(payload_file)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["session_id"] == SESSION_ID
    assert result["hooks_fired"][-1] == "session-end"


def test_capture_rejects_a_missing_payload(capsys: pytest.CaptureFixture[str]) -> None:
    assert bridge.main(["capture", "--payload", "/nonexistent.json"]) == 1
    assert "cannot read payload" in capsys.readouterr().err
