# Improved Chat 0.10.0 beta

Download: https://civ5-improved-chat-api.pages.dev/

- Companion-free installation: copy InGameTranslateMod into Assets\DLC.
- Translation is enabled by default; no account or manual API key entry.
- Each HTTPS download has its own installation key. Keep your ZIP private;
  share the download page so friends receive their own copy.
- Retains incoming/outgoing translation, source selection, Russian Latin-letter
  conversion, private replies, icons, colours, notes and encounter history.
- Unsupported gameplay mods/modpacks disable translation and hide the overlay,
  including its launcher. Stock Civ V, official DLC/expansions and EUI remain
  supported. Compatibility checks do not prove detection of every modification.
- Removes companion-dependent Windows clipboard buttons.
- Encrypted native transport with authenticated responses, durable replay
  protection, existing server quotas, cooperative processing and timeouts.
- Fixes browser download rejection caused by the form's referrer policy.

Upgrade with Civ V closed, replacing the existing InGameTranslateMod folder.
Local notes/history remain in the same database. Messages are limited to
6,000 UTF-8 bytes. Personal downloads share usage and replay state if copied;
use a separate download for each PC. Public download limits apply.

Validation: 151 client tests and 41 backend tests; hosted English-to-Korean
translation succeeded in native Civ V DX9 1.0.3.279 at the main menu without
a companion or local server. Multiplayer stability, DX11 coverage and an
independent cryptographic security review remain outstanding. This is an
experimental beta, not audited secure messaging.

GitHub source archives are for development. Use the website for an install-ready
personalized ZIP; no installation credentials are distributed in this repository.
