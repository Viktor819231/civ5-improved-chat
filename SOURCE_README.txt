Improved Chat beta - source and development

Original project code is MIT licensed; see LICENSE.txt and third-party notices.
This is a standalone project, separate from the Civ replay viewer.

The current beta needs its Windows companion. Civ V's Lua addon writes a local
SQLite mailbox; Python handles HTTPS translation and explicit clipboard actions.
The native mod never embeds a shared Cloudflare credential. Each installation
opts in, registers and receives its own expiring credential. All allowances
belong to the server. Read SECURITY.txt before operating a public proxy.

BUILD ON WINDOWS
Use Python 3.13. From this folder:
  py -3.13 -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements-dev.txt
  .venv\Scripts\python.exe tools\build_package.py --generate-only --game "C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization V"
  .venv\Scripts\python.exe -m unittest discover -s tests -q
  .venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --name InGameTranslateCompanion --collect-all tkinter run_companion.py
  .venv\Scripts\python.exe tools\build_package.py --game "C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization V"
  .venv\Scripts\python.exe tools\verify_package.py

The Lua tests use the original shared scripts and generated lobby scripts.
The --generate-only step creates those layouts without requiring a compiled
companion. Full release packaging requires the executable and notices.

The source archive intentionally excludes generated stock game-layout copies,
generated lobby files, private credentials, saves, chat analysis, local player
databases, binaries and dependency folders. The packaging tool regenerates
layouts from your installed Civ V, retaining its normal lobby and in-game UI.
The generated bootstrap layouts are not licensed as original project assets.

The downloadable Windows beta is not code-signed. Rebuild it from reviewed
source if preferred; the runtime does not require a Python installation.

BACKEND
Use Node.js and npm, then:
  cd cloudflare
  npm ci
  npm test
Configure your OWN Cloudflare account, Worker and server secrets. Do not deploy
the included public_beta configuration into someone else's hosted service.
cloudflare/README.txt documents environments, automatic enrollment, quotas,
operator provisioning and outstanding cost-budget work. Changing the endpoint
requires rebuilding the default or using Advanced settings. No server secret
or existing user's installation credential is included in this source archive.

PREVIEW
Open preview/index.html in Edge or Chrome. It is a local mockup, uses sample
data, and does not call translation services or change installed game files.
