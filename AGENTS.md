# Improved Chat agent instructions

This is the standalone Civilization V Improved Chat project. It is independent
of the replay viewer/testproject repository; do not edit or deploy that project
while working here. This repository currently starts on codex/public-release.

Read README.md, SOURCE_README.txt and SECURITY.txt before making changes.

- Never expose an operator's personal username through API hostnames or public
  artifacts. Use the neutral Pages API hostname and internal service binding;
  keep direct account-scoped Worker routes and preview URLs disabled. Do not
  rename the account-wide Workers subdomain or modify unrelated services.

- Edit shared InGameTranslate.lua/XML and IGT_Text.lua/IGT_History.lua. Do not
  hand-edit generated lobby files or copied stock game bootstrap layouts.
- Generate native files with `.venv\Scripts\python.exe tools\build_package.py
  --generate-only` before running tests in a fresh checkout. `--game` selects
  the local Civ V installation. No generated stock game layouts go in Git.
- Run `.venv\Scripts\python.exe -m unittest discover -s tests -q` for relevant
  companion/UI changes. Backend tests are `npm test` inside cloudflare.
- Native Civ V APIs differ from Civ VI and browsers. Verify bindings in the
  shipped game/source; mocks alone do not prove in-game behavior.
- Do not restart/close Civ V, force a UI reload, send chat to real players or
  change gameplay as part of testing without user authorization.
- Keep installation credentials, Cloudflare secrets, local settings, databases,
  saves, raw chat, analysis, dependencies and generated binaries out of Git.
  Source archives are explicitly allowlisted by tools/build_source_archive.py.
- All enforcement stays server-side. Client identity/Steam ID/game-running
  claims are untrusted. Request/byte quotas are not exact dollar billing caps.
- Cloudflare deployments and inference may consume the operator's allowance.
  Never change paid plans or deploy unrelated projects as a routine build.
- The user selected Viktor819231/civ5-improved-chat as the publishing target.
  Use that account's GitHub noreply address for commits. Do not reuse another
  project's commit history, personal author email, or signing identity. Check
  the actual signed-in/pushing account before publishing. Keep operator
  Cloudflare identity and all local credentials out of public artifacts.
