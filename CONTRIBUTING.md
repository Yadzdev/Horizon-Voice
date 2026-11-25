# Contributing

1. Open an issue describing the behavior, compatibility target and reproduction steps.
2. Create a branch named `feat/<short-name>` or `fix/<short-name>`.
3. Keep BDS APIs tied to documented versions. Do not add invented Script API calls or undocumented HUD events.
4. Add backend tests for every tenant boundary and authorization change.
5. Do not add real credentials, tokens, private player data or screenshots containing secrets.
6. Run `pytest` in `backend/`, `npm run build` in `frontend/`, and `python scripts/package_addon.py`.
7. Open a pull request with `Fixes #<issue-number>` or `Refs #<issue-number>`, describe tests performed and list anything requiring real BDS verification.
8. Update the relevant docs and `CHANGELOG.md` in the same pull request.

Do not mark audio, HUD interaction, production readiness or cross-version compatibility complete unless the relevant integration tests ran successfully on the named BDS and browser versions.
