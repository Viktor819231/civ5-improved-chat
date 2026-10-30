Improved Chat translation backend

Public API: https://civ5-improved-chat-api.pages.dev
Maintainer deployment, quotas, billing and retention: ../docs/HOSTING.md
Security boundary and reporting guidance: ../SECURITY.md

LAYOUT
src/worker.js: translation service and transactional Durable Object quota store.
wrangler.jsonc: disabled default, private_test and public_beta environments.
edge/: Pages advanced-mode API front door and internal TRANSLATION binding.
test/: mock-only backend and edge tests.

All client traffic uses the neutral Pages endpoint. The backend has no direct
workers.dev or preview route. The edge forwards supported routes only, preserves
Cloudflare's ingress IP over the trusted binding, and rejects admin routes,
redirects and internal metadata. There is no public-backend HTTP fallback.

INSTALLATION ENROLLMENT
POST /v1/installations/register
Content-Type: application/json
{"version":1,"installationId":"<UUID>","registrationSecret":"<64 lowercase hex>"}

Reply:
{"token":"<64 lowercase hex>","subject":"install:<UUID>",
 "expiresAt":"<ISO UTC timestamp>"}

The client generates one random installation UUID and 256-bit secret and stores
its proof/token protected with Windows DPAPI, bound to the service URL. Repeating
registration with the same identity and secret recovers access without resetting
usage or consuming another new-registration slot. Wrong secrets cannot claim an
existing UUID. Do not generate a fresh identity after a 403/429/503 response.

POST /v1/installations/renew accepts the same body, or {version,installationId}
with an existing bearer token. Renew cannot create an identity. Tokens expire in
30 days in public_beta; only the latest three unexpired token hashes are kept.
Revocation blocks both token access and registration-secret recovery. No email,
account or mandatory Steam sign-in is required. Legacy /v1/auth/* is unavailable.

TRANSLATION
Authorization: Bearer <token>
POST /v1/translate
Content-Type: application/json
{"text":"Hello","source":"en","target":"ru"}

Reply:
{"text":"...","source":"en","target":"ru","usage":{...}}

GET /v1/usage returns day, requests, inputBytes, requestsRemaining,
inputBytesRemaining and resetAt (UTC ISO timestamp).

Supported explicit source/target codes:
en ru uk ko fr de es pl pt tr it nl sv zh ja ar
Source detection and Civ colour/icon preservation are companion responsibilities.
Only text/source/target are accepted in translation requests. Clients cannot
specify identity, server clock, model, quota, reservations or billed-token counts.
Individual inference input is limited to 500 UTF-8 bytes in public_beta.

Public response statuses:
400 invalid body/unsupported fields; 401 invalid/expired/revoked token;
403 enrollment proof rejected; 413 input too large; 429 quota/rate/concurrency
ceiling; 503 unavailable service/configuration or backend/provider failure.
The internal service's 502 failures are sanitized by the public edge. Internal
errors, redirect locations and non-contract response fields are not exposed.

OPERATOR ACCESS
Internal /admin/installations/token and /admin/installations/revoke accept
installationId. /admin/accounts/token and /admin/accounts/revoke accept a
SteamID64 independently verified by the operator; they are not public sign-in.
All require ADMIN_PROVISIONING_ENABLED=true and an ADMIN_SECRET bearer. They are
off in public_beta and never forwarded by the Pages API. A privately issued
UUID requires its valid bearer before adoption into public secret recovery.

VALIDATION
Run npm test from this directory. Tests mock inference and transactional storage.
Wrangler dry-run builds validate configuration without deployment:
  npx wrangler deploy --dry-run --env public_beta
  npx wrangler pages functions build --project-directory edge --build-output-directory edge/public --outdir .wrangler/edge-dry-run

Real deployment and inference are separate operator actions. Local Wrangler
Workers AI development can use remote inference when enabled. Mock tests and
successful builds do not establish production readiness or exact spending caps.
See ../docs/HOSTING.md for complete abuse/privacy controls and the unresolved
output-token/dollar-budget limitation; request/input-byte quotas are not a
one-cent per-user or five-dollar global guarantee.
