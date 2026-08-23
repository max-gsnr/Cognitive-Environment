#!/usr/bin/env bash
# One command to put a laptop into the exact state the live demo expects.
#
#   scripts/demo_up.sh            # fresh database, backend + frontend, seeded demo child
#   KEEP_DB=1 scripts/demo_up.sh  # keep whatever is already in orbit.db
#
# A demo that starts from an unknown database is a demo that reads a different
# number every time it is rehearsed, so the default is to throw the file away
# and let init_db re-seed the roster.
set -euo pipefail

cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
DEMO_PROFILE=${DEMO_PROFILE:-ec9f2ef3-c7df-46a1-96d2-fa77130fcc2a} # Leo
DEMO_SKILL=${DEMO_SKILL:-addition}

if [ ! -x "$PY" ]; then
  echo "no interpreter at $PY -- run: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
  exit 1
fi
[ -f .env ] || cp .env.example .env

pkill -f "uvicorn app.main" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
sleep 1

if [ -z "${KEEP_DB:-}" ]; then
  rm -f orbit.db
  echo "reset orbit.db"
fi

mkdir -p .demo
"$PY" -m uvicorn app.main:app --port 8000 >.demo/backend.log 2>&1 &
(cd frontend && npm run dev >../.demo/frontend.log 2>&1 &)

for _ in $(seq 1 40); do
  curl -sf localhost:8000/health >/dev/null && break
  sleep 0.5
done
curl -sf localhost:8000/health >/dev/null || { echo "backend did not come up; see .demo/backend.log" >&2; exit 1; }

# The baseline latency and the release-impact chart both need a past. Seeding it
# up front means the first thing shown on stage is not an empty panel.
for endpoint in seed-history seed-release-impact; do
  curl -sf -X POST "localhost:8000/demo/$endpoint" \
    -H 'content-type: application/json' \
    -d "{\"profile_id\":\"$DEMO_PROFILE\",\"skill_id\":\"$DEMO_SKILL\"}" >/dev/null \
    && echo "$endpoint ok"
done

cat <<EOF

ready
  roster    http://localhost:5173/roster
  child     http://localhost:5173/profiles/$DEMO_PROFILE
  play      http://localhost:5173/play/$DEMO_PROFILE/$DEMO_SKILL
  audit     http://localhost:5173/audit
  logs      .demo/backend.log  .demo/frontend.log
EOF
