---
title: How-to — set up the Hotpass toolchain
summary: Create a repeatable local environment for the CLI, Prefect flows, and web UI so you can run tests and build docs.
last_updated: 2025-11-03
---

# Set up the Hotpass toolchain

Follow these steps when you clone the repository on a new machine. You install the Python extras with `uv`, fetch JavaScript dependencies for the web UI, and register the shared pre-commit hooks so your local checks match CI.

## 1. Bootstrap the Python environment

1. Install `uv` if it is not already available:

   ```bash
   python -m pip install -U uv
   ```

2. Sync the default extras used by engineering. The helper script wraps `uv sync` and refuses to continue if you forget to declare a profile:

   ```bash
   HOTPASS_UV_EXTRAS="dev orchestration" bash ops/uv_sync_extras.sh
   ```

   - Add `docs` to the extras when you plan to build documentation.
   - Use `make sync EXTRAS="dev orchestration compliance"` as a shortcut; the target exports `HOTPASS_UV_EXTRAS` and calls the same script.

3. Activate the virtual environment created under `.venv`:

   ```bash
   source .venv/bin/activate
   ```

   The repository pins dependencies through `uv.lock`, so repeat the sync whenever that lock file changes.

## 2. Prepare CLI support tooling

Run the shared hook installation once so linting, formatting, and security scans stay aligned with CI:

```bash
uv run pre-commit install
```

You can now run `make qa` for the smoke tier or `make qa-full` for the full regression. Both targets call the scripts in `scripts/testing/` through `uv`, so the commands work on a clean machine as long as you completed the previous step.

## 3. Install front-end dependencies

Hotpass ships a React control panel that you exercise during smoke tests. Install its dependencies from the repo root:

```bash
make web-ui-install
```

Optional, but recommended if you run Playwright locally:

```bash
cd apps/web-ui
npx playwright install --with-deps chromium
```

Return to the repository root after installing browsers.

## 4. Validate your setup

1. Confirm the CLI resolves the bundled profiles:

   ```bash
   uv run hotpass overview
   ```

2. Run the smoke tier to ensure linting, targeted tests, and coverage reporting succeed:

   ```bash
   make qa
   ```

   The command streams output from Ruff, pytest, Vitest, and pre-commit. It finishes by writing coverage artefacts to `htmlcov/` and `apps/web-ui/coverage/unit/`.

3. Build the documentation to verify the Diátaxis site remains healthy:

   ```bash
   uv run sphinx-build -n -W -b html docs docs/_build/html
   ```

Resolve any warnings before you commit; the docs workflow enforces the same command.

## 5. Keep dependencies up to date

- When `uv.lock` changes on `main`, rerun `make sync EXTRAS="dev orchestration"` and restart your shell session.
- Web dependencies change less frequently, but the CI cache invalidates when `package-lock.json` updates. Re-run `make web-ui-install` after you pull those changes.
- Use `pre-commit autoupdate` sparingly; open a pull request if you raise hook versions so the change is tracked.

With this setup in place you can run the CLI, orchestrate Prefect deployments, execute the quality gates, and regenerate the docs with confidence.
