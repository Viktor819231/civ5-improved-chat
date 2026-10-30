"""Ensure bootstrap layouts preserve stock UI and contain the right contexts."""
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

root = Path(__file__).resolve().parents[1]
game = Path("C:/Program Files (x86)/Steam/steamapps/common/Sid Meier's Civilization V")
dlc = root / 'DLC/InGameTranslateMod'
for path in [*dlc.rglob('*.xml'), *dlc.glob('*.Civ5Pkg')]:
    ET.parse(path)
for name in ['InGameTranslate.xml','InGameTranslateLobby.xml']:
    tree = ET.parse(dlc / 'UI' / name)
    ids = {e.get('ID') for e in tree.iter()}
    for control in ['ChatPage','HistoryPage','ProfilesPanel','Settings','TabBar','PanelBackdrop','HistoryNew','HistoryResume']:
        assert control in ids, control
original = (game / 'Assets/UI/FrontEnd/Multiplayer/StagingRoom.xml').read_text(encoding='utf-8-sig')
patched = (dlc / 'UI/StagingRoom.xml').read_text(encoding='utf-8')
addition = '\t<LuaContext FileName="Assets/DLC/InGameTranslateMod/UI/InGameTranslateLobby" ID="InGameTranslateLobby" Hidden="0" />\n'
assert patched.replace(addition, '') == original
assert (dlc / 'UI/InGameTranslateLobby.lua').exists()
assert 'include(' not in (dlc / 'UI/InGameTranslateLobby.lua').read_text(encoding='utf-8')
assert 'String="Improved Chat"' in (dlc / 'UI/InGameTranslateLobby.xml').read_text(encoding='utf-8')
with zipfile.ZipFile(root / 'release/Improved-Chat-beta.zip') as archive:
    assert archive.testzip() is None
    for path in ['InGameTranslateCompanion.exe', 'README.txt','Install Improved Chat.cmd','install.ps1','THIRD_PARTY_NOTICES.txt','MANIFEST.sha256',
                 'InGameTranslateMod/UI/StagingRoom.xml',
                 'InGameTranslateMod/UI/InGameTranslateLobby.xml',
                 'InGameTranslateMod/UI/IGT_History.lua',
                 'InGameTranslateMod/UI/InGameTranslateLobby.lua']:
        assert path in archive.namelist(), path
    import hashlib
    for line in archive.read('MANIFEST.sha256').decode().splitlines():
        expected,name=line.split('  ',1)
        assert hashlib.sha256(archive.read(name)).hexdigest()==expected,name
    forbidden=('settings.json','installation.json','.db','.env','.dev.vars','.civ5replay','.Civ5Save')
    for name in archive.namelist():
        assert not name.endswith(forbidden),name
print('XML, stock lobby preservation, lobby bootstrap and release contents verified.')
