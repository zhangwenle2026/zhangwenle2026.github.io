from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRACKER_PATH = ROOT / "scripts" / "skill_tracker.py"


def load_tracker():
    spec = importlib.util.spec_from_file_location("skill_tracker_under_test", TRACKER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class SkillTrackerTest(unittest.TestCase):
    def test_clip_content_keeps_head_and_tail_when_too_long(self) -> None:
        tracker = load_tracker()
        content = "A" * 7000 + "B" * 7000

        clipped = tracker._clip_content(content, 10000)

        self.assertLessEqual(len(clipped), 10000)
        self.assertIn("[TRUNCATED]", clipped)
        self.assertTrue(clipped.startswith("A" * 100))
        self.assertTrue(clipped.endswith("B" * 100))

    def test_task_end_marks_visible_failure_as_fail(self) -> None:
        tracker = load_tracker()
        reports: list[dict[str, str]] = []

        def fake_report(**kwargs):
            reports.append(kwargs)

        with tempfile.TemporaryDirectory() as tmpdir:
            tracker._TASK_STATE_FILE = Path(tmpdir) / "task_state.json"
            tracker._report = fake_report
            tracker._get_mis = lambda: "tester"

            tracker.task_start("查节假日")
            tracker.task_end("权限不足，部分数据没查到，但已返回申请链接")

        self.assertEqual(reports[-1]["cli_command"], "skill-output")
        self.assertEqual(reports[-1]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
