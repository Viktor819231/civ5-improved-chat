# Development

Improved Chat has three parts: the native Civ V overlay, a Windows companion,
and a hosted translation API. Civ V and the companion communicate through a
local SQLite mailbox. Only the native overlay sends messages to game chat.

| Path | Purpose |
| --- | --- |
| `DLC/InGameTranslateMod/UI/` | Shared Lua/XML overlay and player journal |
| `companion/` | Mailbox worker, translation providers, credentials and clipboard |
| `cloudflare/` | Neutral API endpoint and server-side usage controls |
| `tests/` | Client and Lua UI regression tests |
| `preview/` | Browser layout preview with sample data |
| `tools/` | Build, archive and release verification scripts |
| `release-support/` | Windows installer |

## Build the Windows package

Use Python 3.13 and a local installation of Civ V. From the repository root:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe tools\build_package.py --generate-only
.venv\Scripts\python.exe -m unittest discover -s tests -q
.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --name InGameTranslateCompanion --collect-all tkinter run_companion.py
.venv\Scripts\python.exe tools\build_package.py
.venv\Scripts\python.exe tools\verify_package.py
.venv\Scripts\python.exe tools\build_source_archive.py
```

Pass `--game "D:\SteamLibrary\steamapps\common\Sid Meier's Civilization V"`
to `build_package.py` if the game is not in the default Steam location.
Use `--output-dir PATH` on the packaging scripts to keep verification builds
separate from released files. Outputs are ignored under `release/` by default.

The generation step creates lobby scripts and stock game-layout wrappers for
the tests. Edit the shared overlay files, then regenerate; do not hand-edit the
generated copies. Full packaging requires the compiled companion and notices.
Generated game-layout copies are not relicensed as original project code.

## Test the backend

With Node.js installed (the beta was built with Node 24):

```powershell
cd cloudflare
npm ci
npm test
```

Backend tests use mocked inference and service bindings. Development modes with
remote Workers AI enabled can incur usage. Deployment is a separate operator
step described in the [hosting guide](HOSTING.md).

## Preview the layout

Open `preview/index.html` in Edge or Chrome. It uses sample data, makes no
translation requests and does not modify installed DLC. Native fonts, wrapping,
focus and mouse behaviour still require checks in the game.

## Release contents

The source archive is explicitly allowlisted. Local agent notes, settings,
credentials, databases, saves, chat analysis, dependencies and generated files
are excluded. Packaging rejects account-scoped Worker URLs in public files and
inspects compiled companion modules as well.

Keep [third-party notices](../third-party-licenses/README.txt) with redistributed
binaries. The current Windows executable is unsigned; users can build it from
source. See the [security policy](../SECURITY.md) for the service's trust boundary.
