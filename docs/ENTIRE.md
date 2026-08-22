# Devin as an Entire agent

## Why a plugin is needed

Entire's built-in integrations (Claude Code, Codex, Cursor, …) work by installing hooks
into a *local* agent process: the agent runs on your machine, fires `session-start` /
`stop` / `session-end`, and Entire snapshots the working tree around each turn to build a
checkpoint.

Devin runs in Cognition's cloud. There is no local process to hook and no local transcript
file, so Devin cannot be integrated the same way. This repository closes the gap with two
executables:

- **`entire-agent-devin`** — an Entire *external agent plugin*. Entire resolves external
  agents by looking for an executable named `entire-agent-<name>` on `$PATH` and talking to
  it in JSON over stdin/stdout at protocol version 1.
- **`entire-devin-bridge`** — the hook transport. It reads a Devin session from the Devin
  API (or a saved API response), appends new activity to a local JSONL transcript, and
  invokes `entire hooks devin <hook>` so the CLI sees the same lifecycle a local agent
  would produce.

## Lifecycle

```
Devin API session          bridge                     Entire CLI
─────────────────          ──────                     ──────────
first poll            →    session-start         →    open session
user message          →    user-prompt-submit    →    TurnStart, snapshot worktree
Devin message/edits   →    stop                  →    TurnEnd, diff worktree → checkpoint
terminal status       →    session-end           →    close session
```

Hook name → Entire event type, as reported by the plugin's `parse-hook`:

| Bridge hook | Entire event |
| --- | --- |
| `session-start` | `1` SessionStart |
| `user-prompt-submit` | `2` TurnStart |
| `stop` | `3` TurnEnd |
| `compaction` | `4` Compaction |
| `session-end` | `5` SessionEnd |

A checkpoint is only created if files actually changed between `user-prompt-submit` and
`stop` — Entire diffs the working tree itself rather than trusting the transcript. When
following a live session this happens naturally; when replaying a finished session, sync
the prompt first, apply the changes, then sync the completed session.

The checkpoint is attached to the commit that contains those changes, so
`entire blame` reports `Devin` as the agent for each line and `entire why` traces a line
back to the prompt that caused it.

## Protocol surface

`entire-agent-devin` implements the required commands — `info`, `detect`,
`get-session-id`, `get-session-dir`, `resolve-session-file`, `read-session`,
`write-session`, `read-transcript`, `chunk-transcript`, `reassemble-transcript`,
`format-resume-command` — plus `parse-hook`, `install-hooks`, `uninstall-hooks`,
`are-hooks-installed`, and the transcript-analysis commands `get-transcript-position`,
`extract-modified-files`, `extract-prompts`, `extract-summary`, `calculate-tokens`.

Declared capabilities: `hooks`, `transcript_analyzer`, `token_calculator`.
Not declared: `transcript_preparer`, `text_generator`, `hook_response_writer`,
`subagent_aware_extractor`.

`install-hooks` cannot edit a cloud agent's config, so it writes the hook contract to
`.devin/entire/hooks.json` instead; the bridge reads that table to decide which
`entire hooks devin <hook>` command to run for each API event.

## Where session data lives

Raw Devin transcripts are written **outside** the repository, under
`$XDG_DATA_HOME/entire-agent-devin/sessions/<repo-slug>/` (default
`~/.local/share/...`). Devin session payloads can contain environment details and
credentials from the agent's own machine, so nothing raw is committed; only Entire's own
checkpoint metadata (prompt, files, session ID) enters the repository.

## Verified end to end

Against Entire CLI 0.10.2:

```
$ entire enable -y --agent devin
  Agent: Devin
  Installed 5 hooks for Devin - Cognition's cloud software engineer (Preview)

$ entire-devin-bridge capture --payload session.json
{"hooks_fired": ["stop", "session-end"], ...}

$ entire checkpoint list
● 01M0NY5QX9AMQFPD8WD5VG88FY  "The README references scripts/setup-entire.sh but it does..."
  08-22 23:51 (04b4009) Register Devin as an Entire external agent

$ entire blame scripts/setup-entire.sh
  Line  Tag   Agent   Author  Checkpoint      Content
     1  [MX]  Devin   Anshu   01M0NY5QX9AM    #!/usr/bin/...
```

## Known gaps

- `entire agent list` in CLI 0.10.2 lists built-in agents only; it does not scan `$PATH`.
  External agents are resolved when named explicitly (`entire enable --agent devin`), which
  also sets `external_agents: true` in `.entire/settings.json`. So `devin` works but does
  not show up in the list.
- `entire checkpoint explain` reports `tokens 0`: the CLI does not call the plugin's
  `calculate-tokens` for external agents in this version, although the transcript carries
  per-message usage.
- Live polling (`follow`) needs `DEVIN_API_KEY` and hits
  `GET $DEVIN_API_BASE/session/<id>` (`DEVIN_API_BASE` defaults to
  `https://api.devin.ai/v1`). It is **untested against the live API** — only the offline
  `capture` path has been exercised end to end. Verify the endpoint shape against current
  Devin API docs before relying on it.
- `entire login` was never performed, so nothing was pushed to Entire's hosted side;
  checkpoints live in git refs in this repository.
