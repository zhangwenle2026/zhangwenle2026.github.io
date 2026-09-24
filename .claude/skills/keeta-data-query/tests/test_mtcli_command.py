#!/usr/bin/env python3
"""Tests for mtcli command fallback construction."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from core import mis, mtcli  # noqa: E402


class MtcliCommandTest(unittest.TestCase):
    def test_command_prefix_uses_global_mtcli_when_available(self) -> None:
        with mock.patch.object(mtcli.shutil, "which", return_value="/usr/local/bin/mtcli"):
            self.assertEqual(mtcli._command_prefix(), ["/usr/local/bin/mtcli"])

    def test_command_prefix_fallback_uses_internal_package_and_registry(self) -> None:
        def fake_which(name: str) -> str | None:
            if name == "mtcli":
                return None
            if name == "npx":
                return "/usr/local/bin/npx"
            return None

        with mock.patch.object(mtcli.shutil, "which", side_effect=fake_which):
            self.assertEqual(
                mtcli._command_prefix(),
                [
                    "/usr/local/bin/npx",
                    "--yes",
                    "--package",
                    "@dp/mtcli",
                    "--registry",
                    "http://r.npm.sankuai.com",
                    "mtcli",
                ],
            )

    def test_mis_candidate_fallback_uses_internal_package_and_registry(self) -> None:
        def fake_which(name: str) -> str | None:
            if name == "mtcli":
                return None
            if name == "npx":
                return "/usr/local/bin/npx"
            return None

        with mock.patch.object(mis.shutil, "which", side_effect=fake_which):
            self.assertEqual(
                mis._candidate_commands(),
                [
                    [
                        "/usr/local/bin/npx",
                        "--yes",
                        "--package",
                        "@dp/mtcli",
                        "--registry",
                        "http://r.npm.sankuai.com",
                        "mtcli",
                        "kdata",
                        "log",
                        "get-mis",
                    ]
                ],
            )

    def test_run_does_not_append_output_format_flags(self) -> None:
        calls: list[list[str]] = []

        def fake_run(cmd, **_kwargs):
            calls.append(cmd)
            return SimpleNamespace(
                returncode=0,
                stdout='{"success": true, "code": 0, "data": {"ok": true}}',
                stderr="",
            )

        with (
            mock.patch.object(mtcli, "_command_prefix", return_value=["mtcli"]),
            mock.patch.object(mtcli.subprocess, "run", side_effect=fake_run),
        ):
            result = mtcli.run(["kdata", "user", "whoami"], timeout=1)

        self.assertEqual(result, {"success": True, "code": 0, "data": {"ok": True}})
        self.assertNotIn("--output", calls[0])
        self.assertNotIn("--format", calls[0])

    def test_run_still_unwraps_mtcli_output_json_payload(self) -> None:
        def fake_run(_cmd, **_kwargs):
            return SimpleNamespace(
                returncode=0,
                stdout=(
                    '{"success": true, "status_code": 200, '
                    '"data": {"success": true, "code": 0, "data": {"ok": true}}}'
                ),
                stderr="",
            )

        with (
            mock.patch.object(mtcli, "_command_prefix", return_value=["mtcli"]),
            mock.patch.object(mtcli.subprocess, "run", side_effect=fake_run),
        ):
            result = mtcli.run(["kdata", "user", "whoami"], timeout=1)

        self.assertEqual(result, {"success": True, "code": 0, "data": {"ok": True}})


if __name__ == "__main__":
    unittest.main()
