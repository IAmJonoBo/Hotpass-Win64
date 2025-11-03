# Toolchain Setup

## Local dev

- Prereqs: language runtime(s), package manager(s).
- One‑command bootstrap: `make setup` (or `npm run setup`).

## Quality hooks

- Pre‑commit: format, lint, typecheck, secrets scan.
- Pre‑push: unit tests.
- Front-end testing: install Playwright browsers once with `npx playwright install --with-deps chromium` so accessibility/e2e suites run locally before committing.

## Containers

- Production builds use `Dockerfile` (lean runtime image for end users).
- Local development can use `Dockerfile.dev`, which layers Node.js, Playwright browsers, and shell tooling for interactive work. Example: `docker build -f Dockerfile.dev -t hotpass-dev .` followed by `docker run --rm -it -p 4173:4173 -v "$PWD":/app hotpass-dev`.

## IDE

- Recommended extensions and settings.
