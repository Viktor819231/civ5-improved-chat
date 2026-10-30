Improved Chat: Cloudflare translation proxy

ENVIRONMENTS
Default improved-chat-translation: public routing, translation and registration
disabled. private_test is operator-provisioned. public_beta is the internal
improved-chat-translation-beta service, offering anonymous installation enrollment
through the neutral Pages API front door.
It requires IP_HASH_SECRET as a server secret (at least 32 random characters).
Missing secret or missing valid Cloudflare client IP fails closed. Never ship
that secret or an administrative secret to clients. Existing private settings
are not changed by selecting the separate public_beta environment.

DEVELOPMENT
npm test runs mocked AI/transactional-storage tests without network inference.
Wrangler deploy --dry-run --env public_beta validates builds without deployment.
Actual deployment is an operator step. Local Wrangler development can perform
REMOTE Workers AI inference if enabled, so it is not automatically cost-free.
The tests are not live-provider quality, latency or integration verification.

ENROLLMENT CONTRACT
POST /v1/installations/register with Content-Type application/json:
{"version":1,"installationId":"<UUID>","registrationSecret":"<64 lowercase hex>"}
Reply: {"token":"<64 lowercase hex>","subject":"install:<UUID>",
"expiresAt":"<ISO UTC timestamp>"}.
The client generates one random UUID and 256-bit secret; Windows DPAPI should
protect its local secret/token, bound to this service URL. Do not log either.

Same UUID + secret safely recovers credentials for the SAME subject without
resetting usage or consuming another new-registration allowance. Wrong secrets
cannot claim a known UUID. Never create a new UUID after a 403/429/503 error.
POST /v1/installations/renew accepts the same JSON or {version,installationId}
with an existing valid bearer. Renew cannot create a new identity. Anonymous
installation registration requires no email, account or mandatory Steam login.
Legacy /v1/auth/* remains unavailable; claimed Steam IDs cannot sign in.

Tokens expire in 30 days in public_beta. Renewal is throttled and only the
latest three unexpired token hashes are retained per subject; earlier tokens
are invalidated. Admin revocation blocks both tokens AND secret recovery until
operator intervention. Registration secrets are stored only as SHA256 hashes.

TRANSLATION CONTRACT
Authorization: Bearer <token>
POST /v1/translate JSON: {"text":"Hello","source":"en","target":"ru"}
Reply: {"text":"...","source":"en","target":"ru","usage":{...}}.
GET /v1/usage returns day, requests, inputBytes, requestsRemaining,
inputBytesRemaining and resetAt (UTC ISO).
Supported explicit codes: en ru uk ko fr de es pl pt tr it nl sv zh ja ar.
The companion detects source language and preserves Civ colour/icon markup.
Only text/source/target are accepted; clients cannot specify identity, clock,
model, quota, usage, input byte counts or reservations.
401 invalid/expired/revoked token; 403 rejected enrollment proof; 413 input too
large; 429 quota/rate/concurrency ceiling; 502 model failure; 503 service off.

PUBLIC BETA CEILINGS
Per installation: 2,000 requests + 100,000 UTF-8 INPUT BYTES/UTC day,
60 requests/minute, two concurrent inferences. Maximum 500 input bytes/request.
Global: 10,000 requests + 500,000 input bytes/day, four concurrent inferences.
IP: 6,000 translations + 250,000 input bytes/day. Subnet: 12,000 translations
+ 500,000 bytes/day. IPv4 grouping is /24; IPv6 grouping is /64.
IP/subnet front-door request rates: 120/240 requests/minute. Shared homes,
universities and VPN connections share network ceilings; IPs are not people.

New registrations: 3/IP/day, 12/subnet/day, 200 globally/day.
Token issues: 12/installation/day, 30/IP/hour, 100/IP/day, 1,000 globally/day.
Enrollment attempts: 10/IP/minute. General admitted requests: 20,000/IP/day,
40,000 globally/day. Failed/malformed enrollments also face front-door limits.

A coordinating Durable Object transaction reserves account/network/global
allowances BEFORE inference. Multiple keys cannot overshoot a shared quota.
Failed inferences remain charged conservatively. Concurrency leases expire in
two minutes for crash recovery; unusually long inference needs monitoring.
The singleton deliberately trades throughput for strict shared counters.
Eventually-consistent KV counters are not an equivalent replacement.

PRIVACY AND LIMITATIONS
Only Cloudflare's edge-supplied CF-Connecting-IP identifies the network.
X-Forwarded-For and client IP fields are never trusted. IP and subnet values
are HMAC-SHA256 hashed with separate labels before storage. Raw IP addresses
and message text are not intentionally stored by this backend. Cloudflare
still receives network connections/text; review its processing/retention terms.
Observability is disabled here to avoid accidental body logging.

A daily Durable Object alarm deletes expired token records and network/issuance
counters inactive for over two days. Stable registration hashes and subject
usage are retained for recovery and quota-reset prevention. These identify
INSTALLATIONS, not verified people. Attackers can create identities through
multiple networks or steal local credentials: this is not bot-proof security.

Quotas count requests and UTF-8 INPUT BYTES, not model tokens or dollars. The
documented M2M100 endpoint exposes no maximum-output-token parameter. The global
request/byte cap is NOT an exact Cloudflare dollar spending cap. Output tokens,
Worker requests (including rejected traffic), storage and DO operations are
separate charges. Actual model measurements and operator budget controls remain
necessary. TRANSLATION_ENABLED is a kill switch, not an account billing limit.

DEPLOYMENT / DOLLAR BUDGET STATUS (2026-10-30)
The public API front door is
https://civ5-improved-chat-api.pages.dev
with the server IP_HASH_SECRET configured privately. Registration is available;
admin provisioning is off. The 2,000-request/100,000-byte installation allowance
and global 10,000-request/500,000-byte allowance are not guaranteed $0.01/day
and $5/day dollar caps. The current M2M100 binding bypasses AI Gateway.

AI Gateway listing returned HTTP403 with the available Wrangler OAuth rights.
An appropriately authorized account administrator must grant AI Gateway access
or configure a dedicated gateway, fixed daily global BLOCK rule and disabled
prompt/response logging. Then every inference must use its gateway ID and fail
closed if configuration is absent. Do not configure a paid fallback route.
Verify cost reporting for M2M100 before describing it as an active cost guard.
Gateway limits remain eventually consistent and best-effort, with completed-call
accounting; concurrent calls can overshoot. A provable ceiling requires a known
maximum output cost and atomic pre-call reservations, not merely a gateway
threshold. No output-token cap is documented for this M2M100 API. Worker/DO/
storage charges, including rejected traffic, remain outside inference budgets.

OPERATOR ENDPOINTS
/admin/installations/token and /revoke require installationId. Legacy
/admin/accounts/token and /revoke require SteamID64 independently verified by
an operator. All admin endpoints require ADMIN_PROVISIONING_ENABLED=true plus
ADMIN_SECRET bearer and are off in public_beta. They are not public sign-in.
A previously operator-issued UUID cannot be adopted into public secret recovery
without its existing valid bearer. Never embed ADMIN_SECRET in the mod.

REFERENCES
https://developers.cloudflare.com/workers-ai/models/m2m100-1.2b/
https://developers.cloudflare.com/workers-ai/platform/pricing/
https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/

NEUTRAL PAGES FRONT DOOR / PRIVATE SERVICE BINDING
Public clients use https://civ5-improved-chat-api.pages.dev only. The project
name contains no account username and does not require buying a domain or
changing the account-wide Workers subdomain. No other project is changed.

edge/wrangler.jsonc defines a separate Pages project using advanced-mode
edge/public/_worker.js. Its TRANSLATION service binding invokes the existing
internal improved-chat-translation-beta Worker. It never fetches a public
backend hostname or falls back to HTTP. Backend default/private_test/public_beta
configurations have workers_dev=false and preview_urls=false. The operator must
deploy these settings and verify previous direct/preview routes are disabled.

The edge forwards only GET /health and /v1/usage; POST /v1/translate and
/v1/installations/register or /renew. Admin and legacy auth routes are blocked.
It preserves the Cloudflare Pages ingress CF-Connecting-IP for backend HMAC
network limits, plus Authorization and Content-Type. X-Forwarded-For and other
client headers are not forwarded. Missing edge IP or binding fails closed.
The service boundary trusts the configured Pages front door and its internal
binding; do not create an alternative externally spoofable ingress.

Backend redirects are rejected, errors replaced with generic safe responses,
response headers rebuilt, and success JSON restricted to the API contract.
No internal host/account metadata is returned. _worker.js serves the API only;
other paths (including / and static index.html) intentionally return 404.

Local tests: npm test includes edge passthrough/security checks with mocked
service bindings and no inference. Pages deployment is an operator step; do
not claim a configuration edit alone disables a previously deployed URL.
References:
https://developers.cloudflare.com/pages/functions/advanced-mode/
https://developers.cloudflare.com/pages/functions/bindings/#service-bindings
https://developers.cloudflare.com/pages/functions/wrangler-configuration/
