# Security and privacy

Improved Chat is a beta mod, Windows companion and hosted translation service. Assume that clients can be modified and the HTTP API can be called without running Civilization V. Client-side counters, reported Steam IDs and a “game is running” check are not trusted authentication.

## Service boundary

The public API is **https://civ5-improved-chat-api.pages.dev**. A Pages front door forwards only supported API routes through an internal service binding; direct backend `workers.dev` and preview routes are disabled. Admin routes are not exposed by that front door. Backend redirects and internal error details are not relayed to clients.

Access uses anonymous installation credentials; no email or mandatory Steam login is required. The server stores credential hashes and enforces shared request, input-byte, registration, rate and concurrency limits. Renewal preserves usage; revocation blocks access and secret-based recovery. The Windows companion protects its installation secret and token with DPAPI. These controls identify installations and networks, not verified people, and cannot prevent every form of multi-identity abuse or credential theft.

Server-side transactional reservations occur before inference. **These are request/input-byte controls, not guaranteed per-user or global dollar spending caps.** M2M100 has no documented output-token cap, and Cloudflare AI Gateway spend limits have eventual-consistency and pricing-estimation limitations. Rejected traffic, Workers/Pages requests, Durable Objects and storage can incur separate charges. See [hosting documentation](docs/HOSTING.md) for exact ceilings, retention and billing gaps.

## Data handling

Translation sends message text to Cloudflare for inference. The service's own code intentionally persists neither chat text nor raw IP addresses. Network-limit identifiers are HMAC hashed with a server secret. Cloudflare still sees connections and inference text and applies its own processing/retention terms. Worker observability is disabled; any future Gateway logging must be configured separately.

Expired server tokens and inactive network/issuance counters are cleaned up on a daily schedule. Stable registration proofs and subject usage are retained for recovery. Player notes and game history are local. Treat local databases and configuration backups as private.

Never publish access tokens, installation secrets, `ADMIN_SECRET`, `IP_HASH_SECRET`, Cloudflare credentials, `.dev.vars`, private settings or chat logs. Public source and release archives should contain examples without live credentials.

## Reporting a concern

Use a private contact method published by the repository maintainer when available. Do not assume that private GitHub advisory reporting is enabled. If no private channel is listed, open an issue requesting one **without** posting an exploit, live credential, private player information or chat content.

Include the affected version, component, expected and observed behavior, and a minimal redacted reproduction. If credentials may have leaked, revoke them promptly rather than posting them for diagnosis. Real-client, abuse-load and operational-budget testing remain necessary as the beta develops.
