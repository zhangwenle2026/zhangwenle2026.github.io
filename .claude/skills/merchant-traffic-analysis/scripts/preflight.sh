#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV_SPEC_VALIDATE_PLAN="/Users/tiantian/.keetai/profiles/codex/Default/.codex/skills/keeta-data-skill-dev-spec/scripts/validate_tracking_plan.py"

cd "$ROOT"

python3 "$DEV_SPEC_VALIDATE_PLAN" .skill-dev/tracking-plan.json >/dev/null
python3 -m py_compile \
  scripts/skill_tracker.py \
  assets/scripts/keeta_bi_skill.py \
  tests/test_tracking_compliance.py
python3 scripts/skill_tracker.py --help >/dev/null
node --check assets/bi-proxy-server.js
bash -n assets/start-dashboard.sh

echo "READY"
