#!/usr/bin/env python3
"""Validate this single SkillHub-compatible repository."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FIELDS = ("name", "description")


def parse_front_matter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(?P<body>.*?)\n---\n", text, re.S)
    if not match:
        return {}

    fields: dict[str, str] = {}
    for line in match.group("body").splitlines():
        if not line.strip() or line.startswith((" ", "\t")):
            continue
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip("\"'")
    return fields


def main() -> int:
    skill_file = ROOT / "SKILL.md"
    if not skill_file.is_file():
        print(f"missing root SKILL.md: {skill_file}", file=sys.stderr)
        return 1

    fields = parse_front_matter(skill_file)
    missing = [field for field in REQUIRED_FIELDS if not fields.get(field)]
    if missing:
        print(f"FAIL SKILL.md: missing {', '.join(missing)}", file=sys.stderr)
        return 1

    print(f"OK   SKILL.md: {fields['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
