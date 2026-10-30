"""Allowlist source for sharing; never include machine state or game layouts."""
import argparse
from pathlib import Path
import zipfile
from release_privacy import check_public_files

ROOT=Path(__file__).resolve().parents[1]
files=[ROOT/n for n in ['.gitignore','LICENSE.txt','README.md','SECURITY.md','requirements-dev.txt','run_companion.py']]
for folder,pattern in [('companion','*.py'),('tests','*.py'),('tools','*.py'),('release-support','*.cmd'),('release-support','*.ps1'),('third-party-licenses','*')]:
    files.extend(p for p in (ROOT/folder).glob(pattern) if p.is_file())
for name in ['InGameTranslate.lua','InGameTranslate.xml','IGT_Text.lua','IGT_History.lua','IGT_Crypto.lua','IGT_Native.lua']:
    files.append(ROOT/'DLC/InGameTranslateMod/UI'/name)
files.extend(ROOT/'cloudflare'/n for n in ['.gitignore','package.json','package-lock.json','wrangler.jsonc','README.txt'])
for folder in ['src','test']:
    files.extend((ROOT/'cloudflare'/folder).rglob('*.js'))
files.extend(ROOT/'preview'/n for n in ['index.html','README.txt'])
files.extend(ROOT/'cloudflare/edge'/n for n in ['wrangler.jsonc','public/_worker.js','public/dlc-download.js','public/index.html'])
files.extend((ROOT/'docs').glob('*.md'))
files.extend((ROOT/'docs').glob('*.txt'))
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir',type=Path,default=ROOT/'release')
destination=parser.parse_args().output_dir/'Improved-Chat-source.zip'
destination.parent.mkdir(parents=True,exist_ok=True)
check_public_files(set(files))
with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(set(files)):
        assert p.is_file(),p
        archive.write(p,p.relative_to(ROOT).as_posix())
print(destination)
