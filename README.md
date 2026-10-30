# Improved Chat for Civilization V

An English-perspective multiplayer chat overlay for the lobby and in-game chat.
Original project code is [MIT licensed](LICENSE.txt).

**Beta:** online translation and clipboard access currently require the included
Windows companion to remain running. This is not a companion-free DLC release.

## Features

- Compact and expanded chat, a draggable header, window size settings and turn
  information on hover.
- Incoming non-Latin messages can translate automatically to English. Individual
  messages can be translated manually by choosing their source language.
- Russian written using Latin letters has an explicit **Russian (Latin letters)**
  source option. Informal spelling and mixed-language chat remain approximate.
- Translate an outgoing draft or send its original text, to all players or an
  individual player. Long messages use paced numbered parts.
- Private-chat styling, Civ icon picker, explicit clipboard buttons, local
  nicknames, player notes and recorded encounter history.

The target is stock Civ V with EUI support. Unsupported gameplay mods cause the
overlay to disable when detected. This check cannot detect every modified game
file or guarantee compatibility with arbitrary modpacks.

## Install the Windows beta

1. Extract **Improved-Chat-beta.zip** to a folder you will keep.
2. Exit Civ V and run **Install Improved Chat.cmd**, or copy **only the inner
   InGameTranslateMod folder** into the game's **Assets\DLC** folder.
3. Run **InGameTranslateCompanion.exe**. On first use choose **Enable online
   translation**. Keep the companion running while playing.
4. Start Civ V and open **Improved Chat** in the lobby or game.

Do not install two copies of the DLC. Updating the UI requires a full game
restart. The DLC-only ZIP needs a matching companion from the same beta build.
Full usage and uninstall instructions: [README.txt](README.txt).

The default hosted beta needs no email, Steam login or manually entered API key.
It assigns an installation credential automatically after opt-in. Its current
allowance is 2,000 service requests and 100,000 UTF-8 input bytes per installation
per UTC day. Shared service/network limits also apply. One chat message can use
multiple requests. An installation is not a verified person or Steam account.

## Privacy and hosting

Online translation sends selected message text to the chosen service; the
service also receives the connection IP. Player notes, local Steam-ID lookups
and encounter history remain on the user's PC. Clipboard reads require an
explicit Paste action.

The open-source client contains no shared account API secret. The server owns
registration, expiry, rate limits, daily quotas and concurrency reservations.
The public endpoint uses a neutral Pages hostname and an internal service
binding. Direct account-scoped Worker and preview URLs are disabled. Packaging
checks source files and compiled companion modules for accidental exposure of
account-scoped API addresses.
Current request/input-byte limits **are not guaranteed dollar billing caps**.
Read [SECURITY.txt](SECURITY.txt) before exposing your own hosted endpoint and
[cloudflare/README.txt](cloudflare/README.txt) for its API and configuration.

## Source layout and development

| Folder | Purpose |
| --- | --- |
| `DLC/InGameTranslateMod/UI` | Shared Civ V Lua/XML overlay and local journal |
| `companion` | Windows companion, SQLite mailbox, providers and credentials |
| `cloudflare` | Translation proxy and server-side abuse/usage controls |
| `tests` | Python/Lua UI and client tests |
| `preview` | Local browser design canvas using sample data |
| `tools`, `release-support` | Packaging, verification and Windows installer |

Build and test instructions: [SOURCE_README.txt](SOURCE_README.txt).
Generated stock game-layout wrappers are excluded from Git and generated from
the developer's installed Civ V. Bundled runtimes retain their separate
[third-party licenses](THIRD_PARTY_NOTICES.txt).
