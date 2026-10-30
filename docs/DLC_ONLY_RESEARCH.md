# DLC-only translation: working transport prototype

Investigation on 2026-10-30. This is a proof of feasibility, not a released or
security-reviewed implementation. The existing release still needs its companion.

## Installation experience

The user approved downloading a personalized ZIP from the website, then copying
one folder into `Assets/DLC`. No companion, installer, account or manual key entry.
GitHub can host source and link to the download. A single publicly shared keyed
ZIP is not an acceptable replacement: each download needs its own secret.

The HTTPS download service generates a cryptographic installation key and places
it in the downloaded Lua configuration. Lua encrypts and authenticates requests
before sending them through Civ V's native `Network.HttpRequest`. The hosted
endpoint verifies them, enforces quotas, translates, and encrypts responses.

This avoids needing either a native DLL or a secure random generator inside Civ V.
It protects message contents at the application layer; it does not turn the
game's HTTP connection into HTTPS or hide traffic metadata.

## Evidence

- The actual DLC UI on Windows DX9, Civ V 1.0.3.279, exposes
  `Network.HttpRequest`, `Finished`, and `PopReceivedData`.
- It does not expose `package`, `require`, `io`, or `os.execute`.
- A loopback wire test proved that an `https://` URL still produced plaintext
  `GET /probe HTTP/1.1`. Successful service health checks alone were misleading:
  automatic HTTP-to-HTTPS redirects can return a successful response.
- Both DX9 and DX11 executables were inspected for the native WinHTTP request
  flags. Live testing in this investigation was DX9: Steam relaunched that
  executable despite starting the DX11 executable directly.
- An isolated pure Lua 5.1 AES-SIV prototype passed RFC 5297 Appendix A.1,
  independent PyCryptodome interoperability checks, block-boundary and Unicode
  tests, and tampering/associated-data rejection tests.
- A second actual main-menu DLC test encrypted `Hello, can you help?`, sent it
  through native networking to a local backend stand-in, and authenticated and
  decrypted a real English-to-Korean result. The stand-in used the existing
  hosted translator for inference. No real player chat was sent.
- The DLC rejected a deliberately modified encrypted response. The stand-in
  confirmed that neither the sample plaintext nor installation key appeared in
  the HTTP request body.
- Crypto work yielded between AES blocks and resumed through the UI update
  callback. This establishes that cooperative scheduling works; it is not a
  multiplayer stability or performance certification.

Research scripts, credential-free results, and the private test archive are in
ignored `analysis/`. They must not be added to a public release. The private test
ZIP contains an ephemeral demo key and a loopback address, not a usable product.

## Cryptography used by the proof

AES-SIV as specified in [RFC 5297](https://www.rfc-editor.org/rfc/rfc5297) uses
two AES-128 keys (32 secret bytes total). It authenticates both encrypted content
and associated data and tolerates repeated nonces without CTR keystream reuse.
Repeated identical messages with identical metadata remain recognizable.

The AES primitive is from MIT-licensed
[lua-lockbox](https://github.com/somesocks/lua-lockbox), pinned to
`d91607dfc6d2a0941186bac2234e34d7b7b48365`. The prototype adds RFC 5297 CMAC/S2V/CTR
composition and byte-only Lua helpers so no `require` or bit-operation extension
is needed. The resulting implementation has not received an independent security
review. Tests establish interoperability, not an absence of implementation flaws.

Request associated data binds protocol version, direction, installation ID and
sequence. Response associated data additionally binds the request's SIV tag.
The client must authenticate the complete response before displaying its text.
No provider/operator secrets belong in the package, only that installation's key.

## Required before replacing the companion

1. Build HTTPS-only personalized ZIP issuance with `Cache-Control: no-store`,
   no shared CDN caching, bounded issuance, and no key logging. Generate keys on
   the server using its cryptographic RNG. Keep the downloaded file private.
2. Implement the encrypted hosted transport behind the neutral Pages endpoint.
   HTTP may carry only authenticated ciphertext. Preserve service-binding-only
   backend access and avoid redirects changing POST semantics. Never silently
   fall back to plaintext chat or credentials.
3. Persist installation revocation, request sequencing and idempotent retries
   transactionally. Authenticate before accepting a sequence or consuming paid
   inference. Preserve existing per-installation, network and global limits.
   The demo's in-memory replay set is deliberately not production storage.
4. Protect server-side encryption keys with a server-only secret or equivalent
   key-management design. The existing token-hash-only credential store cannot
   itself decrypt these requests. Plan key rotation and revocation.
5. Integrate bounded asynchronous requests, cancellation, timeout handling,
   authentication errors, opt-in and translation settings into the normal overlay.
   Store counters before transmission; handle reinstalls and copied ZIPs without
   resetting allowance. A copied ZIP shares its installation identity.
6. Replace companion-only clipboard features or explain their absence. This
   transport proof does not establish native clipboard access.
7. Verify DX11, lobby and in-game contexts, EUI compatibility, simultaneous
   translation, service failures and a controlled multiplayer session. Never use
   the synchronized gameplay RNG, change gameplay state, or broadcast service
   traffic over multiplayer messaging.
8. Review the cryptographic protocol and implementation before public release.
   Do not describe the prototype as audited, TLS-equivalent, or forward-secret.

At the end of the initial investigation, no production backend had been deployed
and the public GitHub release had not changed. See the implementation update below. Temporary diagnostic DLCs were removed after testing.


## Release candidate implementation

A companion-free personalized download is now deployed at the neutral API
homepage. See NO_COMPANION_GUIDE.txt, HOSTING.md and SECURITY.md. The downloaded
IGT_Native/IGT_Crypto modules completed a hosted English-to-Korean translation
in native Civ V DX9 at the main menu in 3.5 seconds, without a local helper.
The user accepted removal of Windows clipboard controls. Multiplayer testing
and independent security review remain outstanding.
