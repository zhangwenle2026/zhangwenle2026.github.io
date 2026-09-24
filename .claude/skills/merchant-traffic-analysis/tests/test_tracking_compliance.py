#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEV_SPEC_VALIDATE_PLAN = (
    "/Users/tiantian/.keetai/profiles/codex/Default/.codex/skills/"
    "keeta-data-skill-dev-spec/scripts/validate_tracking_plan.py"
)


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load_tracker_module():
    spec = importlib.util.spec_from_file_location(
        "skill_tracker_under_test", ROOT / "scripts" / "skill_tracker.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TrackingComplianceTest(unittest.TestCase):
    def test_skill_protocol_requires_full_output_and_env_limits(self) -> None:
        skill_md = read_text("SKILL.md")

        self.assertIn('end --output "最终回答全文（尽量原文复制）"', skill_md)
        self.assertIn("错误全文或关键错误信息", skill_md)
        self.assertIn("status: partial/fail", skill_md)
        self.assertIn("KDATA_LOG_INPUT_MAX_CHARS", skill_md)
        self.assertIn("KDATA_LOG_OUTPUT_MAX_CHARS", skill_md)
        self.assertNotIn("最终回答摘要（100字以内）", skill_md)

    def test_tracker_clips_by_env_and_infers_visible_failures(self) -> None:
        tracker_source = read_text("scripts/skill_tracker.py")

        self.assertIn("INPUT_CONTENT_MAX_CHARS", tracker_source)
        self.assertIn("OUTPUT_CONTENT_MAX_CHARS", tracker_source)
        self.assertNotIn("input_summary[:500]", tracker_source)
        self.assertNotIn("output_summary[:500]", tracker_source)

        tracker = load_tracker_module()
        clipped = tracker._clip_content("a" * 120, 40)
        self.assertLessEqual(len(clipped), 40)
        self.assertIn("[TRUNCATED]", clipped)
        self.assertEqual(tracker._clip_content("a" * 120, 0), "a" * 120)
        redacted = tracker._prepare_content("Authorization: Bearer secret-token\nsql=select 1", 0)
        self.assertIn("Authorization: <redacted>", redacted)
        self.assertNotIn("secret-token", redacted)
        self.assertTrue(tracker._infer_visible_failure_reason("status: partial，部分数据没查到"))
        self.assertFalse(tracker._infer_visible_failure_reason("查询完成，未发现失败或缺失"))

    def test_business_layers_pass_raw_query_context_to_tracker(self) -> None:
        proxy_js = read_text("assets/bi-proxy-server.js")
        bi_py = read_text("assets/scripts/keeta_bi_skill.py")

        self.assertNotIn("sql_len=", proxy_js)
        self.assertIn("sql=", proxy_js)
        self.assertIn("request_body=", proxy_js)
        self.assertNotIn("String(params || '').slice", proxy_js)
        self.assertNotIn('f"<sql:{len(str(value))} chars>"', bi_py)

    def test_tracking_plan_exists_and_validates(self) -> None:
        plan_path = ROOT / ".skill-dev" / "tracking-plan.json"
        self.assertTrue(plan_path.is_file())
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        self.assertEqual(plan["target_skill"], "merchant-traffic-analysis")
        self.assertGreaterEqual(len(plan["plan_items"]), 3)

        result = subprocess.run(
            ["python3", DEV_SPEC_VALIDATE_PLAN, str(plan_path)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_preflight_runs_tracking_checks(self) -> None:
        preflight = ROOT / "scripts" / "preflight.sh"
        self.assertTrue(preflight.is_file())

        result = subprocess.run(
            ["bash", str(preflight)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("READY", result.stdout)


if __name__ == "__main__":
    unittest.main()
