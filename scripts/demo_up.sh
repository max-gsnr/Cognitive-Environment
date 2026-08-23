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
DEMO_PROFILE=${DEMO_PROFILE:-442e9766-3d23-455b-8eb5-e2f4621c1ff7} # Lena, the seeded roster child
DEMO_SKILL=${DEMO_SKILL:-addition}
# Release Impact is seeded on the *other* skill on purpose. Its rows are recent
# and its v2 is deliberately far too easy, so seeding it into the skill about to
# be played drags that skill's live challenge fit to zero.
IMPACT_SKILL=${IMPACT_SKILL:-subtraction}

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

# The live beat is a carry-omitted mistake switching carrying off, so the demo
# child has to start on a tier where carrying is on. The seeded roster starts
# below that, and seed-history draws its questions from whatever tier the child
# is on, so this has to happen before the seeding does.
"$PY" - "$DEMO_PROFILE" "$DEMO_SKILL" <<'PYEOF'
import sys

from app.db import SessionLocal
from app.models import SubjectMastery

profile_id, skill_id = sys.argv[1], sys.argv[2]
carry_tier = {
    "digits": 2,
    "magnitude": "mid_double",
    "carries": skill_id == "addition",
    "borrows": skill_id == "subtraction",
    "zero_in_minuend": False,
}
with SessionLocal() as session:
    mastery = session.get(SubjectMastery, (profile_id, skill_id))
    if mastery is None:
        raise SystemExit(f"no mastery row for {profile_id}/{skill_id}")
    mastery.difficulty_vector = carry_tier
    session.commit()
print(f"tier set ({skill_id}: 2-digit mid double, carrying on)")
PYEOF

# The baseline latency and the release-impact chart both need a past. Seeding it
# up front means the first thing shown on stage is not an empty panel.
seed() {
  curl -sf -X POST "localhost:8000/demo/$1" \
    -H 'content-type: application/json' \
    -d "{\"profile_id\":\"$DEMO_PROFILE\",\"skill_id\":\"$2\"}" >/dev/null \
    && echo "$1 ok ($2)"
}
seed seed-history "$DEMO_SKILL"
seed seed-release-impact "$IMPACT_SKILL"

cat <<EOF

ready
  roster    http://localhost:5173/roster
  child     http://localhost:5173/profiles/$DEMO_PROFILE
  play      http://localhost:5173/play/$DEMO_PROFILE/$DEMO_SKILL
  impact    on the child page, under $IMPACT_SKILL
  audit     http://localhost:5173/audit
  logs      .demo/backend.log  .demo/frontend.log
EOF
