# Harden Hotpass Web Authentication and Proxies

This guide explains how to configure the Hotpass web UI with the new Okta/OIDC provider, rate-limited API proxy, and encrypted human-in-the-loop (HIL) storage. Follow these steps whenever you deploy or troubleshoot the secure UI surface.

## 1. Configure OIDC / Okta

1. Create an OIDC client in your identity provider (Okta, Auth0, Azure AD, etc.).
2. Set the following environment variables for the web UI build and runtime:
   - `VITE_OIDC_AUTHORITY` – the issuer URL (e.g. `https://example.okta.com/oauth2/default`).
   - `VITE_OIDC_CLIENT_ID` – the public client ID.
   - `VITE_OIDC_REDIRECT_URI` – typically `https://<host>/auth/callback`.
   - `VITE_OIDC_POST_LOGOUT_REDIRECT` – where the IdP should send users after sign-out.
   - Optional: `VITE_OIDC_SCOPES` if additional scopes are required.
3. For local development without an IdP, set `VITE_AUTH_DISABLED=true`. The UI will fall back to a mock user. Override mock roles by storing a comma-separated list in `localStorage.setItem('hotpass_mock_roles', 'admin,operator')` before the app loads (Playwright tests already do this).

## 2. Deploy the secure proxy server

The web UI now ships with an Express edge server (`apps/web-ui/server/index.mjs`) that enforces rate limits and CSRF protection.

1. Build the UI using the updated Dockerfile or run `pnpm run build && pnpm run start` locally.
2. Provide target URLs for the proxy:
   - `PREFECT_API_URL` (defaults to `http://localhost:4200/api`).
   - `MARQUEZ_API_URL` or `OPENLINEAGE_URL` (defaults to `http://localhost:5000/api/v1`).
3. Tune rate limits if necessary:
   - `PREFECT_RATE_LIMIT` (requests per minute, default 120).
   - `MARQUEZ_RATE_LIMIT` (requests per minute, default 60).
4. The proxy exposes the following routes:
   - `/api/prefect/**` → Prefect API (rate-limited).
   - `/api/marquez/**` → Marquez/OpenLineage API (rate-limited).
   - `GET /telemetry/operator-feedback/csrf` → issues a CSRF token cookie.
   - `POST /telemetry/operator-feedback` → accepts feedback only with a valid `X-CSRF-Token` header.

## 3. Harden HIL audit storage

The human-in-the-loop audit trail now lives in encrypted IndexedDB storage:

- Encryption keys are derived from the signed-in user’s ID token. In mock mode a per-user seed is used.
- Approvals and audit entries are only written when the key is available; otherwise UI controls are disabled.
- Admins can configure retention in **Admin → Human-in-the-loop retention**:
  - Toggle the policy on/off.
  - Set the retention window (days). Older entries are securely purged when the window is updated.

## 4. Operational checklist

1. **Before deployment**
   - Set the OIDC environment variables and restart the Node server.
   - Confirm rate limits reflect platform SLAs (`PREFECT_RATE_LIMIT`, `MARQUEZ_RATE_LIMIT`).
   - Verify `pnpm run start` serves the UI on port 3000 (Docker exposes port 3000).
2. **After deployment**
   - Navigate to `/admin` and check the Prefect/Marquez badges. Use the “Test connection” buttons if available.
   - Confirm the retention card reflects policy defaults and adjust as needed.
   - Run the Playwright smoke suite (`pnpm run test:e2e`) to validate auth guardrails.
3. **Troubleshooting**
   - If `/admin` renders “Access restricted”, ensure the signed-in identity carries the `admin` role.
   - If approvals are disabled, confirm the browser has a CSRF token (`GET /telemetry/operator-feedback/csrf`) and that IndexedDB is accessible.
   - For mock mode testing, remove the `hotpass_mock_roles` entry from localStorage to restore default roles.

## 5. Security notes

- All fetches to Prefect/Marquez now send `credentials: 'include'` so cookies or future session data flow through the proxy.
- CSRF tokens are short-lived and bound to the HTTP-only cookie issued by the server. Ensure downstream telemetry collectors verify payload origin if forwarding the data.
- Keep the Node server behind TLS terminators; it relies on the platform to provide HTTPS.
