# Improved Chat for Civilization V

Translate multiplayer chat, whisper to individual players, and keep local player
notes in a compact overlay. Works in the lobby and in-game chat.

**[Download the Windows beta](https://github.com/Viktor819231/civ5-improved-chat/releases/tag/v0.9.1-beta)**

The current beta requires the included Windows companion to stay running for
translation and clipboard access. No email, Steam login or API key setup is
needed for the default translation service.

## Features

- Translate incoming messages into English automatically for non-Latin text,
  or manually choose the source language for any message.
- Read Russian written in Latin letters using **Russian (Latin letters)**.
- Translate your replies or send the original text, to everyone or one player.
- Expand, collapse, resize and drag the chat window. Turn details appear on hover.
- Use Civ icons, message colours, local nicknames, player notes and encounter history.

## Install

1. Download **Improved-Chat-beta.zip** from the release page and extract it.
2. Close Civ V and run **Install Improved Chat.cmd**. For manual installation,
   copy only the inner **InGameTranslateMod** folder into **Assets\DLC**.
3. Start **InGameTranslateCompanion.exe**, choose **Enable online translation**,
   and keep it running.
4. Launch Civ V and open **Improved Chat** in the lobby or game.

The beta targets stock Civ V with EUI support. Other gameplay mods are not
supported. Install one copy of the DLC; updates to its UI require a game restart.
The DLC-only download needs the matching companion from the full package.

See the [user guide](docs/USER_GUIDE.txt) for controls, troubleshooting and uninstall.

## Privacy and availability

Translation sends message text to the configured service. Player notes and
encounter history stay on your PC; clipboard reads require a Paste action.
The hosted beta allows 2,000 requests and 100,000 UTF-8 input bytes per installation
per UTC day, with shared service and network limits. One message can use multiple
requests. Machine translations, especially slang and informal spelling, can be imperfect.

## Development

- [Build and test](docs/DEVELOPMENT.md)
- [Host the translation service](docs/HOSTING.md)
- [Security and privacy](SECURITY.md)
- [Third-party notices](third-party-licenses/README.txt)

Original project code is [MIT licensed](LICENSE.txt). Game-layout wrappers are
generated from your installed Civ V and are not included in the source repository.
