# Cognitive-Environment

Making [Devin](https://devin.ai) a first-class agent in [Entire](https://entire.io), so
cloud agent sessions become checkpoints in the repository they changed.

Git records *what* changed. Entire records *why*: the prompts, the session, the files, and
the checkpoint linked to the commit. Entire ships integrations for local agents that can
fire their own lifecycle hooks — Devin runs in Cognition's cloud and cannot, so it was not
a supported agent. This repository adds it:

| Piece | What it is |
| --- | --- |
| `bin/entire-agent-devin` | Entire [external agent plugin](https://docs.entire.io/agents/external-agent-plugins/architecture) (protocol v1) that teaches the Entire CLI how to read Devin sessions |
| `bin/entire-devin-bridge` | Hook transport: tails the Devin API and delivers lifecycle events to `entire hooks devin <hook>` |
| `tools/entire_agent_devin/` | Implementation: protocol commands, transcript parsing, bridge |

## Setup

```bash
scripts/setup-entire.sh      # installs the Entire CLI if needed, registers the agent
entire agent list            # devin should appear
```

The plugin is discovered by name: any executable called `entire-agent-<name>` on `$PATH`
is registered as an agent, and the setup script symlinks `bin/` accordingly.

## Use

```bash
# Live: follow a running Devin session and stream its activity into Entire.
export DEVIN_API_KEY=...
entire-devin-bridge follow --session devin-abc123

# Offline / CI: ingest a saved Devin API response.
entire-devin-bridge capture --payload session.json

# Link a session that ran before the bridge was watching to your last commit.
entire-devin-bridge attach --session devin-abc123
```

Then read the history back:

```bash
entire checkpoint list                    # sessions on this branch
entire checkpoint explain <commit>        # prompts and files behind a commit
entire blame path/to/file --long          # per-line attribution: AI / mixed / human
entire why path/to/file                   # why this code exists
```

`docs/ENTIRE.md` covers the architecture, the hook lifecycle, and what the integration
does and does not capture.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/pytest        # protocol compliance + bridge behaviour
.venv/bin/ruff check .
```

## Why this repository exists

It is the provenance layer for **Orbit**, a system that evolves a child's educational game
from that child's own telemetry by fanning out parallel Devin sessions. Agent-written code
in a learning tool has to be auditable — a teacher must be able to ask "why does Leo's game
pause for 2.5 seconds after a wrong answer?" and get back the session, the prompt, and the
telemetry that motivated it. Entire is that answer, and this integration is what makes it
reach Devin. Orbit itself is not in this repository yet.
