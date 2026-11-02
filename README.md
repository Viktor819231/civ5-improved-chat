# Improved Chat for Civilization V

Translate multiplayer chat, whisper to individual players, and keep local player
notes in a compact overlay. Works in the lobby and in-game chat.

**Version 0.11.2 beta** — Civ 5-aware translation, your own language (window in 10 languages), 31 send languages.

**[Download the companion-free beta](https://civ5-improved-chat-api.pages.dev/)**

Each download is a personal ZIP: extract it and copy **InGameTranslateMod** into
**Assets\DLC**. Translation is enabled by default. No companion,
account, installer or API key entry is required. Keep your ZIP private; share
the download page so each user receives their own installation key.

This beta preserves translation and chat/journal features. Windows clipboard
Copy/Paste buttons are unavailable. The native encrypted transport is
experimental; multiplayer stability and independent security review remain
outstanding. [Details and installation guide](docs/NO_COMPANION_GUIDE.txt).

## Features

- Translate incoming messages into **your language** automatically. It follows
  the language Civ V runs in (English, Russian, Korean, German, French, Spanish,
  Italian, Polish, Japanese or Chinese) and can be changed in Settings. The
  overlay itself switches to that language too.
- Civ 5-aware translations: the game's official names in each language, player
  shorthand (gg, DoW, NC, спс, ㅋㅋ) and a casual gamer tone.
- Translate your replies into 31 languages, including **Russian (Latin letters)**
  for players whose game cannot show Cyrillic. Read Russian written in Latin letters too.
- Spam-safe: automatic translations are rationed per player, a repeated line is
  translated once, and your own messages always go first.
- Translate your replies or send the original text, to everyone or one player.
- Expand, collapse, resize and drag the chat window. Turn details appear on hover.
- Use Civ icons, message colours, local nicknames, player notes and encounter history.

## Install

1. Download your personal ZIP from the link above and extract it.
2. Close Civ V and copy the inner **InGameTranslateMod** folder into **Assets\DLC**.
3. Launch Civ V and open **Improved Chat**. Choose a language and send.

The beta targets stock Civ V with EUI or KEK Mod. Copy the folder into
**Assets\DLC** as usual. Other gameplay mods stay off: the overlay hides
itself and stops translation when one is detected. Install one copy of the
DLC; updates to its UI require a game restart.

See the [companion-free guide](docs/NO_COMPANION_GUIDE.txt) for controls, troubleshooting and uninstall.

## Privacy and availability

Translation sends message text to the configured service. Player notes and
encounter history stay on your PC. This version has no clipboard access.
The hosted beta allows 2,000 requests and 100,000 UTF-8 input bytes per installation
per UTC day, with shared service and network limits. One message can use multiple
requests; native messages are limited to 6,000 UTF-8 bytes. Translations use Google's Gemma 4 model on Cloudflare Workers AI, with Meta's
M2M100 as automatic fallback. Machine translations can still be imperfect.

## Development

- [Build and test](docs/DEVELOPMENT.md)
- [Host the translation service](docs/HOSTING.md)
- [Security and privacy](SECURITY.md)
- [Third-party notices](third-party-licenses/README.txt)

Original project code is [MIT licensed](LICENSE.txt). Game-layout wrappers are
generated from your installed Civ V and are not included in the source repository.
