"""Build the keyless input for private HTTPS downloads; no companion executable."""
from pathlib import Path
import zipfile
from build_package import build
from release_privacy import check_public_files

ROOT=Path(__file__).resolve().parents[1]
GAME=Path("C:/Program Files (x86)/Steam/steamapps/common/Sid Meier's Civilization V")
def build_template(game=GAME):
    build(game,generate_only=True)
    dlc=ROOT/'DLC/InGameTranslateMod'
    names=['UI/InGameTranslate.lua','UI/InGameTranslate.xml','UI/InGameTranslateLobby.lua','UI/InGameTranslateLobby.xml','UI/IGT_Crypto.lua','UI/IGT_Native.lua','UI/IGT_Text.lua','UI/IGT_History.lua','UI/StagingRoom.xml','UI/StagingRoom.lua']
    for n in range(3):
        names.extend([f'InGameTranslate_{n}.Civ5Pkg',f'Skin{n}/InGame.xml',f'Skin{n}/DiploCorner.lua'])
    sources={f'InGameTranslateMod/{name}':dlc/name for name in names}
    sources.update({'README.txt':ROOT/'docs/NO_COMPANION_GUIDE.txt','LICENSE.txt':ROOT/'LICENSE.txt','third-party-licenses/lua-lockbox.txt':ROOT/'third-party-licenses/lua-lockbox.txt'})
    for name in ['InGameTranslate.lua','InGameTranslateLobby.lua']:
        text=(dlc/'UI'/name).read_text(encoding='utf-8')
        assert text.count('IGT_Config = false; -- PERSONALIZED_DOWNLOAD_CONFIG')==1
        assert 'IGT_Config = {' not in text,'Never build a template from a private installation'
    check_public_files(sources.values())
    output=ROOT/'cloudflare/edge/public/dlc-template.zip'
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for name,path in sources.items():z.write(path,name)
    print('Built keyless download template:',output)
    return output

if __name__=='__main__':build_template()
