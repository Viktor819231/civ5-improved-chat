"""Reject account-scoped API addresses in public source and packaged code."""
from pathlib import Path
import re

_ACCOUNT_URL=re.compile(rb'https?://[a-z0-9_-]+\.[a-z0-9_-]+\.workers\.dev',re.IGNORECASE)


class PrivacyError(RuntimeError):
    pass


def check_bytes(content: bytes, label: str):
    if _ACCOUNT_URL.search(content):
        # Do not echo the rejected hostname/identity into public build logs.
        raise PrivacyError('Account-scoped API address found in public artifact: '+label)


def check_companion(path: Path):
    import marshal
    from PyInstaller.archive.readers import CArchiveReader
    archive=CArchiveReader(str(path))
    for name in archive.toc:
        data=archive.extract(name)
        if isinstance(data,bytes):check_bytes(data,'companion/'+name)
        if name.endswith('.pyz'):
            modules=archive.open_embedded_archive(name)
            for module in modules.toc:
                code=modules.extract(module)
                if code is not None:check_bytes(marshal.dumps(code),'companion/'+module)


def check_public_files(files):
    for file in files:
        check_bytes(file.read_bytes(),file.name)
        if file.name=='InGameTranslateCompanion.exe':check_companion(file)
