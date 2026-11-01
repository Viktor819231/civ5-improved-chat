# Development

The current beta has a native Civ V overlay and a hosted translation API.
Personalized HTTPS downloads supply installation credentials; Lua handles
encrypted asynchronous requests directly. Only the overlay sends game chat.
The companion code remains for legacy builds and regression tests.

| Path | Purpose |
| --- | --- |
| `DLC/InGameTranslateMod/UI/` | Shared Lua/XML overlay and player journal |
| `companion/` | Mailbox worker, translation providers, credentials and clipboard |
| `cloudflare/` | Neutral API endpoint and server-side usage controls |
| `tests/` | Client and Lua UI regression tests |
| `preview/` | Browser layout preview with sample data |
| `tools/` | Build, archive and release verification scripts |
| `release-support/` | Windows installer |

## Build the companion-free download

Create the Python environment and install requirements-dev.txt, then run:

```powershell
.venv\Scripts\python.exe tools\build_dlc_template.py
.venv\Scripts\python.exe -m unittest discover -s tests -q
.venv\Scripts\python.exe tools\build_source_archive.py
```

The generated template is keyless and is not an install-ready public ZIP.
The hosted download personalizes it. Never upload a user ZIP to GitHub.
See HOSTING.md for the backend and Pages deployment commands.

## Build the legacy companion package

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

Backend tests use mocked inference and service bindings; they run without the
generated official-name table. Before deploying, generate it from the local game
with `.venv\Scripts\python.exe tools\build_glossary.py`. Development modes with
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


## Native companion-free build

The download injects IGT_Config into both shared and generated lobby scripts.
Source contains a false placeholder for compatibility with companion builds.
IGT_Native processes native_requests in the same local database, preserving
notes/history while preventing the old companion from claiming native jobs.
Online translation defaults on; an explicit disable choice is preserved.
Enable/disable preferences and sequence state are separate. Never copy keyed Lua back into source.

Run tools/build_dlc_template.py after UI edits. tests/test_siv.py cross-checks
Lua 5.1 against PyCryptodome; tests/test_native.py tests the shared UI and native
worker. Backend tests cover authentication, replay, quotas and private downloads.
The hosted downloaded client translated a synthetic English sample to Korean
in Civ V DX9 1.0.3.279 at the main menu in 3.5 seconds on 2026-10-30, without
a companion/local server. This does not verify multiplayer stability.
