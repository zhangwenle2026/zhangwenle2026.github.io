# keeta-external-context

Single-Skill source repository initialized from SkillHub skill `18928`.

This Skill queries external context for Keeta overseas business analysis:
weather, holidays, major events, competition, policy/regulation, infrastructure,
and security context across SA / QA / BH / AE / KW / HK / BR.

## Repository Layout

```text
keeta-external-context/
├── SKILL.md
├── scripts/
│   ├── weather.py
│   ├── holidays.py
│   ├── events_search.py
│   ├── skill_tracker.py
│   └── validate_skills.py
├── tests/
│   └── test_skill_tracker.py
└── .skill-dev/
    └── tracking-plan.json
```

## Validation

```bash
python3 scripts/validate_skills.py
python3 -m compileall -q scripts
python3 -m unittest tests/test_skill_tracker.py
```

## Tracking

`SKILL.md` defines start/end/feedback reporting. Business nodes report through
`scripts/skill_tracker.py` with `skill-script` events around weather, holiday,
and realtime event lookup calls.
