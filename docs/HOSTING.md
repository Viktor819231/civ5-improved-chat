# Hosting Improved Chat

The beta translation service uses [Cloudflare Pages](https://developers.cloudflare.com/pages/functions/advanced-mode/), Workers AI and a SQLite-backed Durable Object. The public endpoint is **https://civ5-improved-chat-api.pages.dev**. Users do not need an email, Steam login or personal provider key.

## Architecture

```text
Companion → Pages API → internal translation Worker → Workers AI
                              ↓
                     shared Durable Object
```

The Pages project in `cloudflare/edge/` uses advanced-mode `_worker.js`. Its `TRANSLATION` service binding invokes `improved-chat-translation-beta` without a public backend HTTP request. Backend `workers_dev` and preview routes are disabled in every configured environment. Do not add a publicly accessible alternative ingress.

The front door forwards only these routes and methods:

| Method | Route |
| --- | --- |
| GET | `/health` |
| GET | `/v1/usage` |
| POST | `/v1/installations/register` |
| POST | `/v1/installations/renew` |
| POST | `/v1/translate` |

Admin and legacy authentication routes are blocked. Query parameters are rejected. The edge preserves Cloudflare's ingress `CF-Connecting-IP`, bearer authorization and content type across the trusted service binding. It does not forward `X-Forwarded-For`. Missing network identity or binding fails closed. Backend redirects are rejected; errors, response headers and success JSON are restricted to the public contract. Other paths, including `/`, return 404. Keep public URLs and technical responses free of account-specific hostnames; message text itself is preserved.

See [the backend API reference](../cloudflare/README.txt) for request/response formats and [the security policy](../SECURITY.md) for reporting guidance.

## Deploying

Deployment requires an authorized Cloudflare account with permission to manage Pages, Workers, Workers AI, service bindings and Durable Objects. Use the checked-in configuration as the source of truth:

| Configuration | Purpose |
| --- | --- |
| `cloudflare/wrangler.jsonc`, default | Disabled service configuration |
| `public_beta` environment | Internal beta translator and shared quota store |
| `private_test` environment | Separate operator-provisioned test service |
| `cloudflare/edge/wrangler.jsonc` | Neutral Pages API and `TRANSLATION` binding |

1. Set a cryptographically random `IP_HASH_SECRET` of at least 32 characters as a **server secret** on the beta Worker. Do not put its value in source, configuration examples or client releases. Missing protection configuration makes registration and translation unavailable.
2. Review the quota variables below, the Workers AI model and the billing limitations before enabling traffic. Keep `ADMIN_PROVISIONING_ENABLED=false` for the public beta. `TRANSLATION_ENABLED` and `REGISTRATION_ENABLED` are separate service switches.
3. Deploy the backend with its Durable Object migration, AI binding and public routes disabled. Deploy the Pages project with `TRANSLATION` bound to the beta Worker. Do not change an account-wide subdomain or purchase a domain to configure this endpoint.
4. Verify the neutral `/health` endpoint and service binding, and independently verify that old direct backend and preview URLs no longer serve traffic. A source configuration edit alone does not disable a deployed route.
5. Test registration, renewal and usage before running a deliberately limited real translation test. Deployment and real inference are operator actions that may incur charges.

Local validation from `cloudflare/`:

```sh
npm test
npx wrangler deploy --dry-run --env public_beta
npx wrangler pages functions build --project-directory edge --build-output-directory edge/public --outdir .wrangler/edge-dry-run
```

Unit tests mock AI and transactional storage. Dry-run compilation does not verify native Durable Object integration, network identity propagation, provider quality or latency. Workers AI can use remote inference even during local Wrangler development when enabled.

## Credentials and recovery

The companion generates an installation UUID and a 256-bit registration secret, protecting the secret and access token with Windows DPAPI and binding them to the service URL. Registration and renewal preserve the same server subject and allowance. Changing a token or reinstalling while retaining this identity does not reset usage; clients must not generate new identities after a failed request.

The server stores registration-secret and token hashes. A different secret cannot claim an existing UUID. Tokens expire after 30 days in the beta; only the latest three unexpired token hashes are retained. Revocation invalidates tokens and blocks registration-secret recovery until operator intervention.

Optional internal operator endpoints can issue/revoke installation or independently verified account credentials. They require a separate `ADMIN_SECRET` and explicit administrative enablement, and are not forwarded by Pages. Never distribute that secret or use a client-reported Steam ID as authentication. A private installation UUID cannot enter public secret recovery without its existing valid credential.

## Quotas and abuse controls

Daily counters reset at **00:00 UTC**. Limits measure **requests and UTF-8 input bytes**, not characters, model tokens or dollars. The following are the configured public-beta ceilings:

| Scope | Daily requests | Daily input bytes | Requests/minute | Concurrent inference |
| --- | ---: | ---: | ---: | ---: |
| Installation | 2,000 | 100,000 | 60 | 2 |
| Service | 10,000 | 500,000 | — | 4 |
| IP address | 6,000 translations | 250,000 | 120 front-door requests | — |
| Subnet | 12,000 translations | 500,000 | 240 front-door requests | — |

Individual inference input is limited to **500 bytes**. Network grouping uses IPv4 `/24` and IPv6 `/64` subnets.

| Registration/credential control | Ceiling |
| --- | --- |
| New installations | 3/IP/day; 12/subnet/day; 200/service/day |
| Credential issuance | 12/installation/day; 30/IP/hour; 100/IP/day; 1,000/service/day |
| Enrollment attempts | 10/IP/minute |
| General admitted requests | 20,000/IP/day; 40,000/service/day |

Failed or malformed enrollment requests also face front-door admission limits. Credentials for one subject share usage. The coordinating Durable Object reserves installation, network and global allowances **before** inference using server time and actual input size. Failed inferences remain charged conservatively. Client claims about quota, subject, model, clock, reservations or billed tokens are rejected.

Concurrency leases expire after two minutes for crash recovery. Monitor requests that outlast a lease. The singleton is deliberately a throughput bottleneck; independent eventually consistent KV counters would not provide equivalent strict shared quotas.

These controls identify installations and networks, not verified people. Users sharing a home, university or VPN share network ceilings. A determined attacker can obtain identities through different networks or steal local credentials. Maintain operational monitoring and perform abuse-load testing before treating the beta as a production service.

## Billing limitations

**The configured quotas do not guarantee $0.01 per installation per day or a $5 service-wide daily spending cap.** The Worker calls Cloudflare-hosted Meta M2M100 directly through Workers AI. Its documented API exposes no maximum-output-token parameter. Input-byte limits therefore do not establish a verified worst-case output cost; rejecting or truncating output after inference cannot undo its charges.

AI Gateway dollar spend rules are not part of the active enforcement path. To add them, an administrator with appropriate AI Gateway permissions must configure a dedicated gateway, a fixed daily global **block** rule, no paid fallback, and disabled prompt/response logging. Every inference must use that gateway and fail closed when configuration is absent. Verify M2M100 cost reporting before relying on this additional guard.

Cloudflare documents that [Gateway spend limits](https://developers.cloudflare.com/ai-gateway/features/spend-limits/) are eventually consistent, record cost after completion and use best-effort pricing estimates; concurrent calls can exceed the threshold. A provable inference ceiling needs a verified maximum output cost and conservative atomic worst-case reservations before each call, or a model/provider with enforceable output-token limits. [Prepaid credits](https://developers.cloudflare.com/ai-gateway/features/unified-billing/) are not an absolute cap either: Cloudflare documents rare negative balances charged later.

Workers requests, Durable Object operations and storage are separate costs. Rejected traffic can incur those charges. Neither inference quotas nor the translation kill switch cap the complete Cloudflare bill. Account for Pages/service-binding requests and keep billing monitoring separate from application quotas.

## Privacy and retention

The service intentionally stores no chat text or raw IP addresses. Cloudflare still receives connections and inference text, and its processing/retention terms apply. Worker observability is disabled in configuration. A future AI Gateway requires separate request/response logging settings; disabling Workers logs does not disable Gateway logs.

Network identifiers are HMAC-SHA256 hashes using `IP_HASH_SECRET` and separate IP/subnet labels. Only Cloudflare's edge-supplied identity is trusted. A daily Durable Object alarm removes expired token records and network/issuance counters inactive for over two days. Stable registration proofs and subject usage records remain for recovery and reset prevention; review retention requirements when operating the service at larger scale. Local player notes, native account lookups and game history are not server authentication.

Keep secrets, credentials, local settings/backups, personal databases, saves and raw chat-analysis material out of source and release archives. Ignore rules do not remove already-committed files: inspect the actual staged files and repository history. Third-party license notices are in [the notices directory](../third-party-licenses/README.txt).


## Companion-free downloads

New routes: GET / serves the download page; POST /download creates a private
ZIP; GET /v2/dlc/{installation}/{sequence}/{ciphertext-hex} handles encrypted
native requests. /v2/dlc/enroll is internal to the service binding and is not
forwarded as a public key API. Existing companion routes remain available.
DLC_ENABLED enables the new path; missing DLC_KEY_SECRET fails closed. Set
the latter once using wrangler secret put with a random 32-byte hex secret.
Never rotate it on redeployment: that invalidates all existing downloads.

Build the keyless template with tools/build_dlc_template.py from the repo root.
The generated edge/public/dlc-template.zip contains no key and is ignored.
The edge blocks direct public access to that static asset. Existing registration
and network quotas also limit fresh downloads; do not disable them for tests.

Deploy backend from cloudflare: npx wrangler deploy --env public_beta
Deploy Pages FROM cloudflare/edge:
npx wrangler pages deploy --project-name civ5-improved-chat-api --branch production --commit-dirty=true
The production branch is production; main creates a preview. Keep observability
off and treat ciphertext request paths as private metadata. Verify native
transport in Civ V: Python HTTPS alone cannot verify the game's HTTP behavior.
