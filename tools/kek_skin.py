"""Let Improved Chat translate inside KEK Mod's own chat and lobby.

KEK ships its own chat and lobby scripts at priority 300, above the translator's
hooked stock copies, so under KEK the translator stays a separate window. This
builds KEK's own installed scripts plus the hook (tools/chat_hooks.py) into a small
package at priority 310, inside KEK's folder: it then lives and dies with that KEK
version, because KEK's scripts must never run without KEK (its SendChat stores
messages through a network call that means something else in the plain game).
KEK's ui_check rewrites only KEK's UI folder; run this again after it.

    python tools/kek_skin.py "<...>/Assets/DLC/KEK Mod v2.4"            build into it
    python tools/kek_skin.py "<...>/Assets/DLC/KEK Mod v2.4" --remove   take it out
"""
from pathlib import Path
import argparse
import hashlib
import shutil

from chat_hooks import patch_kek_chat, patch_kek_lobby, read_stock, write_patched

FOLDER = 'Improved Chat for KEK'
GUID = '{5f49ec56-47a5-4f8e-9695-a429d6a4b023}'
SOURCES = ['DiploCorner.lua', 'DiploCorner.xml', 'StagingRoom.lua']


def build(kek: Path) -> Path:
    ui = kek / 'UI'
    if not (kek / 'MPModsPack.Civ5Pkg').is_file() or not all((ui / name).is_file() for name in SOURCES):
        raise SystemExit(f'Not an installed KEK Mod folder with its UI set up (run its ui_check first): {kek}')
    out = kek / FOLDER
    if out.exists():
        shutil.rmtree(out)
    skin = out / 'Skin'
    skin.mkdir(parents=True)
    write_patched(skin / 'DiploCorner.lua', patch_kek_chat(read_stock(ui / 'DiploCorner.lua'), 'KEK DiploCorner.lua'))
    # KEK picks its chat script and layout as a pair (vanilla UI or EUI): keep that pair
    # together, so a later ui_check run cannot leave our script on the other layout.
    shutil.copyfile(ui / 'DiploCorner.xml', skin / 'DiploCorner.xml')
    write_patched(skin / 'StagingRoom.lua', patch_kek_lobby(read_stock(ui / 'StagingRoom.lua'), 'KEK StagingRoom.lua'))
    # The lobby script itself loads the translator's lobby part (KEK_LOBBY_LOADER), as
    # KEK would ship it: KEK's own lobby layout stays as it is.
    # KEK lists its folders as a GameplaySkin, the translator as a Skin: list ours both ways.
    (out / 'ImprovedChatKEK.Civ5Pkg').write_text(f'''<?xml version="1.0" encoding="utf-8"?>
<Civ5Package>
  <GUID>{GUID}</GUID><Version>1</Version><Priority>310</Priority>
  <PTags><Tag>Version</Tag></PTags>
  <Name><Value language="en_US">Improved Chat for KEK</Value></Name>
  <Description><Value language="en_US">KEK Mod's own chat and lobby with Improved Chat's hook</Value></Description>
  <UISkin name="Expansion2Primary" set="Expansion2" platform="Common">
    <Skin><Directory>Skin</Directory></Skin>
    <GameplaySkin><Directory>Skin</Directory></GameplaySkin>
  </UISkin>
</Civ5Package>
''', encoding='utf-8')
    # Which KEK files this was made from, to see when KEK's UI changed under it.
    (out / 'built-from.txt').write_text(''.join(
        f'{hashlib.sha256((ui / name).read_bytes()).hexdigest()}  UI/{name}\n' for name in SOURCES), encoding='utf-8')
    return out


def remove(kek: Path) -> None:
    out = kek / FOLDER
    if out.exists():
        shutil.rmtree(out)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('kek', type=Path, help='the installed "KEK Mod v<version>" folder in Assets/DLC')
    parser.add_argument('--remove', action='store_true')
    args = parser.parse_args()
    if args.remove:
        remove(args.kek)
        print('Removed', args.kek / FOLDER)
    else:
        print('Built', build(args.kek))
