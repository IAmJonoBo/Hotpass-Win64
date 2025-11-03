# Toolchain Setup

## Local dev

- Prereqs: language runtime(s), package manager(s).
- One‑command bootstrap: `make setup` (or `npm run setup`).

## Quality hooks

- Pre‑commit: format, lint, typecheck, secrets scan.
- Pre‑push: unit tests.
- Front-end testing: install Playwright browsers once with `npx playwright install --with-deps chromium` so accessibility/e2e suites run locally before committing.

## IDE

- Recommended extensions and settings.
