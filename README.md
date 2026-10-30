# Improved Chat for Civilization V

Translate multiplayer chat, whisper to individual players, and keep local player
notes in a compact overlay. Works in the lobby and in-game chat.

**Version 0.10.0 beta** — companion-free translation, enabled by default.

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

- Translate incoming messages into English automatically for non-Latin text,
  or manually choose the source language for any message.
- Read Russian written in Latin letters using **Russian (Latin letters)**.
- Translate your replies or send the original text, to everyone or one player.
- Expand, collapse, resize and drag the chat window. Turn details appear on hover.
- Use Civ icons, message colours, local nicknames, player notes and encounter history.

## Install

1. Download your personal ZIP from the link above and extract it.
2. Close Civ V and copy the inner **InGameTranslateMod** folder into **Assets\DLC**.
3. Launch Civ V and open **Improved Chat**. Choose a language and send.

The beta targets stock Civ V with EUI support. Other gameplay mods are not
supported: the overlay hides itself and stops translation/queued sends when
unsupported gameplay mods are detected. Install one copy of the DLC; updates to its UI require a game restart.

See the [companion-free guide](docs/NO_COMPANION_GUIDE.txt) for controls, troubleshooting and uninstall.

## Privacy and availability

Translation sends message text to the configured service. Player notes and
encounter history stay on your PC. This version has no clipboard access.
The hosted beta allows 2,000 requests and 100,000 UTF-8 input bytes per installation
per UTC day, with shared service and network limits. One message can use multiple
requests; native messages are limited to 6,000 UTF-8 bytes. Machine translations, especially slang and informal spelling, can be imperfect.

## Development

- [Build and test](docs/DEVELOPMENT.md)
- [Host the translation service](docs/HOSTING.md)
- [Security and privacy](SECURITY.md)
- [Third-party notices](third-party-licenses/README.txt)

Original project code is [MIT licensed](LICENSE.txt). Game-layout wrappers are
generated from your installed Civ V and are not included in the source repository.
