#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV_SPEC_DIR="${DEV_SPEC_DIR:-/Users/tiantian/.keetai/profiles/codex/Default/.codex/skills/keeta-data-skill-dev-spec}"

cd "$ROOT"

python3 -m py_compile scripts/*.py
python3 scripts/skill_tracker.py --help >/dev/null
SKILL_TRACKER_DRY_RUN=1 python3 scripts/skill_tracker.py self-test >/dev/null
python3 scripts/brand_anomaly_evidence.py --help >/dev/null
SKILL_TRACKER_DRY_RUN=1 python3 scripts/brand_anomaly_evidence.py --self-test --format json >/tmp/brand_anomaly_evidence_self_test.json
python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("/tmp/brand_anomaly_evidence_self_test.json").read_text(encoding="utf-8"))
required = {"status", "query_records", "sections", "summary", "errors", "data_gaps"}
missing = required - set(data)
if missing:
    raise SystemExit(f"evidence packet missing fields: {sorted(missing)}")
if data["status"] not in {"ok", "partial", "fail"}:
    raise SystemExit(f"unexpected evidence status: {data['status']}")
if not data["query_records"]:
    raise SystemExit("query_records is empty")
if not all("--task-id" in item["command"] and "--task-name" in item["command"] for item in data["query_records"]):
    raise SystemExit("not all query commands include task id and task name")
PY
python3 "$DEV_SPEC_DIR/scripts/validate_tracking_plan.py" .skill-dev/tracking-plan.json >/dev/null
python3 - <<'PY'
from pathlib import Path

manifest = Path("skill.manifest").read_text(encoding="utf-8")
required = [
    "scripts/skill_tracker.py",
    "scripts/brand_anomaly_evidence.py",
    "scripts/preflight.sh",
    "references/data-query-protocol.md",
    "requirements.txt",
]
missing = [item for item in required if item not in manifest]
if missing:
    raise SystemExit(f"manifest missing files: {missing}")
PY

echo "READY"
