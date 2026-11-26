# Changelog

## Unreleased

### Added
- Replaced the generic web template with a hand-authored Minecraft Bedrock visual identity using CSS block textures and pixel-style controls.
- Reworked the player portal around the server name, description, custom cover image and browser pairing flow.
- Added optional server-cover uploads with browser preview/optimization, owner authorization, format/dimension/size validation and persistent Docker storage.
- Added public API endpoints for safe server metadata and its optimized cover.
- Added Alembic migration 0005 for optional cover metadata.
- Added optional Sentry and OpenTelemetry tracing with OTLP export; documented Datadog and New Relic collector compatibility.
- Added frontend unit tests, Playwright portal/upload tests, Biome linting, dependency-cruiser architecture checks, Knip analysis, Commitlint and Codecov upload.

### Changed
- Added loading skeletons, lazy-loaded dashboard thumbnails, concise transition feedback and reduced-motion support.
- Extended CI to run lint, architecture checks, unit tests, build and Playwright before a merge can be considered for release.
