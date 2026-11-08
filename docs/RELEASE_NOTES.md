# Improved Chat 0.12.0 beta

- Translation now happens in the game's own chat instead of a separate overlay,
  in game and in the lobby, with or without EUI. Messages are translated on
  their own line, you type in the normal chat box, and team chat and the
  game's To: list work with translated messages.
- A small TR menu on the chat row picks the language you send in. TR: - sends
  exactly what you type, and is where a new install starts; your choice is kept.
- The ... button on the chat row opens settings, player notes and history.
- Translated messages you send no longer start with (TranslatorMod): other
  players see only the message.
- Hover a translated line for its original text. T translates a line, < shows
  the original again, right-click T chooses the language.
- Runs with any mod or DLC: it no longer switches itself off when a gameplay
  mod or modpack is active.
- If another mod replaces the game's chat script, the separate window returns
  by itself. KEK Mod has its own chat and lobby, so with KEK the translator is
  the separate window in game; a KEK version with the small hook gets the
  in-chat buttons too.

Upgrade: download again from the website and replace InGameTranslateMod with
Civ V closed. Notes and history are kept.

# Improved Chat 0.11.2 beta

- Mongolian: choose it as My language to read incoming chat in Mongolian, or
  under Send in and Translate. Civ V has no Mongolian version, so the window
  shows in Russian when the game runs in Russian (Mongolian letters need the
  game's Russian font) and in English otherwise.
- Mongolian messages are no longer mistaken for Kazakh.

# Improved Chat 0.11.1 beta

- The overlay window speaks all ten My language choices: English, Russian,
  Korean, German, French, Spanish, Italian, Polish, Japanese and Chinese
  (Traditional, like Civ V's Chinese). Changing My language changes the window.
- A language the game's font cannot draw (Cyrillic, Polish, Korean, Japanese,
  Chinese in an English game) keeps the window in English with a note, so it
  always stays readable.

Upgrade: download again from the website and replace InGameTranslateMod with
Civ V closed. Notes and history are kept.

# Improved Chat 0.11.0 beta

- Civ 5-aware translation: a language model (Gemma 4 on Cloudflare Workers AI)
  translates chat as players talk, uses the game's official names in each
  language (generated from the game's own localisation) and understands player
  shorthand (gg, DoW, NC, CBs, спс, объява, ㅋㅋ, 도국). M2M100 remains the
  automatic fallback. Every request has a hard output limit.
- My language: incoming chat is translated into the language Civ V runs in
  (English, Russian, Korean, German, French, Spanish, Italian, Polish, Japanese
  or Chinese) and the overlay is shown in English, Russian or Korean. Change it
  in Settings; the choice is remembered.
- 30 send languages, including Russian (Latin letters) for players whose game
  cannot show Cyrillic. Messages in Latin letters are never auto-translated,
  for any reader language; when you click Translate the service recognises
  the language (Spanish, German, translit Russian...);
  right-click still lets you choose the language.
- Spam protection: automatic translations are rationed per player (4 at once,
  then one every 6 seconds) and at most 6 wait at a time; a repeated line is
  translated once; your own messages are translated first; reaching the daily
  limit pauses automatic translation for 5 minutes. Finished requests are read
  once and old ones are cleared, so a long or spammy game does not slow the UI.
- Translated messages you send are tagged (TranslatorMod) instead of (TR), in
  English whatever the language, so other players know where they come from.

Upgrade: download again from the website and replace InGameTranslateMod with
Civ V closed. Notes and history are kept.

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

2026-10-31: Public download page and ZIP filename now use Civ5TranslatorMod (0.10.0 beta). Existing in-game Improved Chat labels and InGameTranslateMod installation paths remain compatible. Rebuilt and published the current keyless template; service binding and backend secrets unchanged. 151 Python/UI and 41 backend tests passed.
