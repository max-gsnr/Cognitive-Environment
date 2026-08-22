"""Protocol-compliance tests for the ``entire-agent-devin`` plugin.

Every subcommand is exercised through the executable itself, the way the Entire
CLI calls it: JSON in on stdin, JSON out on stdout, non-zero exit on failure.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PLUGIN = REPO / "bin" / "entire-agent-devin"

REQUIRED_COMMANDS = {
    "info",
    "detect",
    "get-session-id",
    "get-session-dir",
    "resolve-session-file",
    "read-session",
    "write-session",
    "read-transcript",
    "chunk-transcript",
    "reassemble-transcript",
    "format-resume-command",
}

TRANSCRIPT = [
    {
        "type": "session_start",
        "session_id": "devin-abc123",
        "timestamp": "2026-01-13T12:00:00Z",
    },
    {
        "type": "user_message",
        "session_id": "devin-abc123",
        "timestamp": "2026-01-13T12:00:01Z",
        "message": "Add a non-punitive cooldown after a wrong answer.",
    },
    {
        "type": "tool_use",
        "session_id": "devin-abc123",
        "timestamp": "2026-01-13T12:00:02Z",
        "tool": {"name": "edit_file", "input": {"path": "games/leo/v1/index.html"}},
        "usage": {"input_tokens": 1200, "output_tokens": 340},
    },
    {
        "type": "tool_use",
        "session_id": "devin-abc123",
        "timestamp": "2026-01-13T12:00:03Z",
        "tool": {"name": "shell", "input": {"command": "pytest -q"}},
    },
    {
        "type": "file_change",
        "session_id": "devin-abc123",
        "timestamp": "2026-01-13T12:00:04Z",
        "files": {
            "new": ["games/leo/v2/index.html"],
            "deleted": ["games/leo/tmp.html"],
        },
    },
    {
        "type": "devin_message",
        "session_id": "devin-abc123",
        "timestamp": "2026-01-13T12:00:05Z",
        "message": "Cooldown added and tests pass.",
        "summary": "Added a 2.5s non-punitive cooldown",
        "model": "devin",
        "usage": {"input_tokens": 800, "output_tokens": 120},
    },
]


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    """Plugin environment as the CLI provides it, with storage redirected."""
    repo = tmp_path / "repo"
    repo.mkdir()
    environ = dict(os.environ)
    environ.update(
        ENTIRE_REPO_ROOT=str(repo),
        ENTIRE_PROTOCOL_VERSION="1",
        ENTIRE_DEVIN_DATA_HOME=str(tmp_path / "data"),
    )
    environ.pop("DEVIN_API_KEY", None)
    return environ


@pytest.fixture
def transcript(tmp_path: Path) -> Path:
    path = tmp_path / "devin-abc123.jsonl"
    path.write_text("".join(json.dumps(record) + "\n" for record in TRANSCRIPT))
    return path


def run(
    args: list[str], env: dict[str, str], stdin: bytes = b""
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [sys.executable, str(PLUGIN), *args],
        input=stdin,
        capture_output=True,
        cwd=env["ENTIRE_REPO_ROOT"],
        env=env,
        check=False,
    )


def run_json(args: list[str], env: dict[str, str], stdin: bytes = b"") -> object:
    result = run(args, env, stdin)
    assert result.returncode == 0, result.stderr.decode()
    return json.loads(result.stdout.decode())


def test_info_declares_protocol_and_capabilities(env: dict[str, str]) -> None:
    info = run_json(["info"], env)
    assert info["protocol_version"] == 1
    assert info["name"] == "devin"
    assert PLUGIN.name == f"entire-agent-{info['name']}"
    assert set(info["capabilities"]) == {
        "hooks",
        "transcript_analyzer",
        "transcript_preparer",
        "token_calculator",
        "text_generator",
        "hook_response_writer",
        "subagent_aware_extractor",
    }
    assert info["capabilities"]["hooks"] is True
    assert info["hook_names"]


def test_every_declared_command_is_implemented(env: dict[str, str]) -> None:
    """`--help` lists the subparsers, so it doubles as a protocol inventory."""
    result = run(["--help"], env)
    assert result.returncode == 0
    text = result.stdout.decode()
    for command in REQUIRED_COMMANDS:
        assert command in text


def test_detect_reports_presence(env: dict[str, str], tmp_path: Path) -> None:
    """Devin is present once something can deliver its sessions to Entire."""
    env["PATH"] = str(tmp_path / "empty-path")
    assert run_json(["detect"], env)["present"] is False
    env["DEVIN_API_KEY"] = "test-key"
    assert run_json(["detect"], env)["present"] is True


def test_detect_finds_the_bridge_on_path(env: dict[str, str]) -> None:
    env["PATH"] = str(PLUGIN.parent) + os.pathsep + env["PATH"]
    assert run_json(["detect"], env)["present"] is True


def test_get_session_id_reads_hook_input(env: dict[str, str]) -> None:
    payload = json.dumps({"hook_type": "stop", "session_id": "devin-abc123"}).encode()
    assert run_json(["get-session-id"], env, payload) == {"session_id": "devin-abc123"}


def test_get_session_id_fails_without_a_session(env: dict[str, str]) -> None:
    result = run(["get-session-id"], env, b"{}")
    assert result.returncode == 1
    assert b"session_id" in result.stderr


def test_session_dir_is_per_repository(env: dict[str, str]) -> None:
    first = run_json(["get-session-dir", "--repo-path", env["ENTIRE_REPO_ROOT"]], env)
    other = str(Path(env["ENTIRE_REPO_ROOT"]).parent)
    second = run_json(["get-session-dir", "--repo-path", other], env)
    assert first["session_dir"] != second["session_dir"]
    assert Path(first["session_dir"]).is_dir()


def test_resolve_session_file(env: dict[str, str]) -> None:
    resolved = run_json(
        [
            "resolve-session-file",
            "--session-dir",
            "/tmp/sessions",
            "--session-id",
            "devin-abc123",
        ],
        env,
    )
    assert resolved["session_file"] == "/tmp/sessions/devin-abc123.jsonl"


def test_resolve_session_file_rejects_path_traversal(env: dict[str, str]) -> None:
    resolved = run_json(
        [
            "resolve-session-file",
            "--session-dir",
            "/tmp/sessions",
            "--session-id",
            "../../etc/passwd",
        ],
        env,
    )
    assert resolved["session_file"] == "/tmp/sessions/..-..-etc-passwd.jsonl"
    assert Path(resolved["session_file"]).parent == Path("/tmp/sessions")


def test_read_session_reports_file_changes(
    env: dict[str, str], transcript: Path
) -> None:
    hook_input = json.dumps(
        {
            "hook_type": "stop",
            "session_id": "devin-abc123",
            "session_ref": str(transcript),
            "timestamp": "2026-01-13T12:00:06Z",
        }
    ).encode()
    session = run_json(["read-session"], env, hook_input)
    assert session["agent_name"] == "devin"
    assert session["repo_path"] == env["ENTIRE_REPO_ROOT"]
    assert session["modified_files"] == ["games/leo/v1/index.html"]
    assert session["new_files"] == ["games/leo/v2/index.html"]
    assert session["deleted_files"] == ["games/leo/tmp.html"]


def test_write_session_then_read_session_round_trips(
    env: dict[str, str], tmp_path: Path
) -> None:
    ref = tmp_path / "sessions" / "devin-xyz.jsonl"
    session = {
        "session_id": "devin-xyz",
        "agent_name": "devin",
        "repo_path": env["ENTIRE_REPO_ROOT"],
        "session_ref": str(ref),
        "start_time": "2026-01-13T09:00:00Z",
        "modified_files": [],
        "new_files": [],
        "deleted_files": [],
    }
    result = run(["write-session"], env, json.dumps(session).encode())
    assert result.returncode == 0, result.stderr.decode()
    assert ref.exists(), "transcript file should be created for the session"

    hook_input = json.dumps(
        {"hook_type": "stop", "session_id": "devin-xyz", "session_ref": str(ref)}
    ).encode()
    assert run_json(["read-session"], env, hook_input)["start_time"] == (
        "2026-01-13T09:00:00Z"
    )


def test_read_transcript_returns_raw_bytes(
    env: dict[str, str], transcript: Path
) -> None:
    result = run(["read-transcript", "--session-ref", str(transcript)], env)
    assert result.returncode == 0
    assert result.stdout == transcript.read_bytes()


def test_read_transcript_of_missing_file_is_empty(env: dict[str, str]) -> None:
    result = run(["read-transcript", "--session-ref", "/nonexistent.jsonl"], env)
    assert result.returncode == 0
    assert result.stdout == b""


def test_chunk_and_reassemble_are_lossless(
    env: dict[str, str], transcript: Path
) -> None:
    raw = transcript.read_bytes()
    chunked = run_json(["chunk-transcript", "--max-size", "64"], env, raw)
    assert len(chunked["chunks"]) > 1
    assert all(base64.b64decode(chunk) for chunk in chunked["chunks"])

    result = run(["reassemble-transcript"], env, json.dumps(chunked).encode())
    assert result.returncode == 0
    assert result.stdout == raw


def test_reassemble_rejects_non_base64(env: dict[str, str]) -> None:
    result = run(["reassemble-transcript"], env, b'{"chunks": ["not base64!"]}')
    assert result.returncode == 1


def test_format_resume_command(env: dict[str, str]) -> None:
    command = run_json(["format-resume-command", "--session-id", "devin-abc123"], env)
    assert command["command"] == "entire-devin-bridge follow --session devin-abc123"


@pytest.mark.parametrize(
    ("hook", "expected_type"),
    [
        ("session-start", 1),
        ("user-prompt-submit", 2),
        ("stop", 3),
        ("compaction", 4),
        ("session-end", 5),
    ],
)
def test_parse_hook_maps_lifecycle_events(
    env: dict[str, str], transcript: Path, hook: str, expected_type: int
) -> None:
    payload = json.dumps(
        {
            "hook_type": hook,
            "session_id": "devin-abc123",
            "session_ref": str(transcript),
            "timestamp": "2026-01-13T12:00:07Z",
            "user_prompt": "Add a cooldown",
        }
    ).encode()
    event = run_json(["parse-hook", "--hook", hook], env, payload)
    assert event["type"] == expected_type
    assert event["session_id"] == "devin-abc123"
    assert event["session_ref"] == str(transcript)


def test_parse_hook_ignores_irrelevant_hooks(env: dict[str, str]) -> None:
    payload = json.dumps({"session_id": "devin-abc123"}).encode()
    assert run_json(["parse-hook", "--hook", "notification"], env, payload) is None


def test_parse_hook_without_session_returns_null(env: dict[str, str]) -> None:
    assert run_json(["parse-hook", "--hook", "stop"], env, b"{}") is None


def test_hook_install_lifecycle(env: dict[str, str]) -> None:
    table = Path(env["ENTIRE_REPO_ROOT"]) / ".devin" / "entire" / "hooks.json"
    assert run_json(["are-hooks-installed"], env)["installed"] is False

    installed = run_json(["install-hooks"], env)
    assert installed["hooks_installed"] > 0
    assert run_json(["are-hooks-installed"], env)["installed"] is True
    hooks = json.loads(table.read_text())["hooks"]
    assert hooks["stop"] == "entire hooks devin stop"

    assert run(["uninstall-hooks"], env).returncode == 0
    assert run_json(["are-hooks-installed"], env)["installed"] is False


def test_install_hooks_local_dev_points_at_local_build(env: dict[str, str]) -> None:
    run_json(["install-hooks", "--local-dev"], env)
    table = Path(env["ENTIRE_REPO_ROOT"]) / ".devin" / "entire" / "hooks.json"
    assert json.loads(table.read_text())["hooks"]["stop"].startswith("./entire ")


def test_transcript_position_and_incremental_extraction(
    env: dict[str, str], transcript: Path
) -> None:
    position = run_json(["get-transcript-position", "--path", str(transcript)], env)
    assert position["position"] == transcript.stat().st_size

    extracted = run_json(
        ["extract-modified-files", "--path", str(transcript), "--offset", "0"], env
    )
    assert "games/leo/v1/index.html" in extracted["files"]
    assert extracted["current_position"] == position["position"]

    # Nothing new since the last checkpoint.
    assert (
        run_json(
            [
                "extract-modified-files",
                "--path",
                str(transcript),
                "--offset",
                str(position["position"]),
            ],
            env,
        )["files"]
        == []
    )


def test_extract_modified_files_ignores_read_only_tools(
    env: dict[str, str], tmp_path: Path
) -> None:
    path = tmp_path / "read-only.jsonl"
    path.write_text(
        json.dumps(
            {
                "type": "tool_use",
                "session_id": "devin-abc123",
                "tool": {"name": "read_file", "input": {"path": "secrets.env"}},
            }
        )
        + "\n"
    )
    assert run_json(["extract-modified-files", "--path", str(path)], env)["files"] == []


def test_extract_prompts_and_summary(env: dict[str, str], transcript: Path) -> None:
    prompts = run_json(["extract-prompts", "--session-ref", str(transcript)], env)
    assert prompts["prompts"] == [
        "Add a non-punitive cooldown after a wrong answer.",
    ]
    summary = run_json(["extract-summary", "--session-ref", str(transcript)], env)
    assert summary == {
        "summary": "Added a 2.5s non-punitive cooldown",
        "has_summary": True,
    }


def test_extract_summary_without_one(env: dict[str, str], tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text("")
    assert run_json(["extract-summary", "--session-ref", str(path)], env) == {
        "summary": "",
        "has_summary": False,
    }


def test_calculate_tokens(env: dict[str, str], transcript: Path) -> None:
    raw = transcript.read_bytes()
    usage = run_json(["calculate-tokens", "--offset", "0"], env, raw)
    assert usage["input_tokens"] == 2000
    assert usage["output_tokens"] == 460
    assert usage["api_call_count"] == 2


def test_malformed_transcript_lines_are_skipped(
    env: dict[str, str], tmp_path: Path
) -> None:
    path = tmp_path / "partial.jsonl"
    path.write_text(
        json.dumps({"type": "user_message", "message": "first"})
        + "\n{ this is not json\n"
        + json.dumps({"type": "user_message", "message": "second"})
        + "\n"
    )
    prompts = run_json(["extract-prompts", "--session-ref", str(path)], env)
    assert prompts["prompts"] == ["first", "second"]
