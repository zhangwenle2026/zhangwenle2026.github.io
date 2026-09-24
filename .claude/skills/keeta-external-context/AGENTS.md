# AGENTS.md

## Scope

These instructions apply to this repository root.

## Repository Layout

- This is a single-skill repository for `keeta-external-context`.
- Keep the publishable `SKILL.md` at the repository root.
- Keep runtime scripts in `scripts/`.
- Do not commit installed-package signatures, manifests, local caches, or editor state.

## Validation

Run before considering repository-structure changes complete:

```bash
python3 scripts/validate_skills.py
python3 -m compileall -q scripts
python3 -m unittest tests/test_skill_tracker.py
```
