#!/usr/bin/env bash
# Register Devin as an Entire agent in this repository.
#
# Entire discovers external agents as `entire-agent-<name>` executables on
# $PATH, so this links the two entry points into ~/.local/bin before enabling.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bin_dir="${BIN_DIR:-$HOME/.local/bin}"

if ! command -v entire >/dev/null 2>&1; then
  echo "==> installing the Entire CLI"
  curl -fsSL https://entire.io/install.sh | bash
fi
export PATH="$bin_dir:$PATH"

echo "==> linking the Devin plugin into $bin_dir"
mkdir -p "$bin_dir"
for entry in entire-agent-devin entire-devin-bridge; do
  chmod +x "$repo_root/bin/$entry"
  ln -sf "$repo_root/bin/$entry" "$bin_dir/$entry"
done

echo "==> enabling Entire with the devin agent"
# --agent resolves external plugins by name and turns on external agent
# discovery for the rest of Entire.
entire enable -y --agent devin

echo
echo "Done. Devin's hook contract is in .devin/entire/hooks.json."
echo "Feed it a session:  entire-devin-bridge follow --session <devin-session-id>"
echo "                    entire-devin-bridge capture --payload <saved-api-response.json>"
