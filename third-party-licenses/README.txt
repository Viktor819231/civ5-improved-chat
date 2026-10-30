IMPROVED CHAT - THIRD-PARTY NOTICES
Prepared 2026-10-30 for the Windows beta companion and DLC.

These notices identify third-party components and preserve their licenses.
They do not select a license for Improved Chat's original code or relicense
Civilization V, Steam, EUI, Cloudflare or other third-party material. Keep the
third-party-licenses directory together with this file when redistributing the
beta package. Recheck dependencies after changing the build environment.

PYTHON 3.13.17
The companion bundles CPython and standard-library/runtime components.
Copyright Python Software Foundation and other contributors; PSF License
Version 2 and historical/component terms are retained in full in
third-party-licenses/Python-3.13.17-LICENSE.txt.
This file is copied from the actual Python installation used for this build,
and includes Windows/Microsoft Distributable Code conditions and additional
runtime component notices. The unchanged Python runtime is redistributed.
Source: https://www.python.org/downloads/release/python-31317/

TCL 8.6.15 / TK 8.6.15
Tkinter uses bundled Tcl/Tk. Their permissive copyright/permission notices are
retained in full in Tcl-8.6.15-license.terms and Tk-8.6-license.terms.
Copyright Regents of the University of California, Sun Microsystems, Scriptics,
ActiveState, Apple (Tk), and other parties identified in those notices.
Tcl's installed package omitted its top-level license file, so the full notice
was obtained from the official Tcl core-8-6-15 tag. Tk's notice was copied from
the installed package. Tcl info patchlevel and the Tk DLL version both report
8.6.15.
Source: https://github.com/tcltk/tcl/blob/core-8-6-15/license.terms

PYINSTALLER 6.22.3
The executable includes the PyInstaller bootloader and runtime hooks.
Copyright 2010-2023 PyInstaller Development Team; 2005-2009 Giovanni Bajo;
based on earlier McMillan Enterprises work, as stated in the full notice.
PyInstaller uses GPLv2-or-later with a bootloader exception permitting combined
executables to be distributed without restrictions from use of those files.
Runtime hooks/additional runtime modules have Apache License 2.0 terms.
The full installed COPYING.txt, including exception and full GPL/Apache texts,
is retained in PyInstaller-6.22.3-COPYING.txt. Installed community-hook terms
are also retained in PyInstaller-hooks-contrib-2026.9-LICENSE.txt.
Source: https://pyinstaller.org/en/stable/license.html

OPENSSL 3.5.9
The Python HTTPS runtime reports OpenSSL 3.5.9. The Apache License 2.0 text from
the official OpenSSL openssl-3.5.9 tag is retained in
OpenSSL-3.5.9-LICENSE.txt. No separately named NOTICE file exists at that tag's
root (the official retrieval returned 404); the license text is unchanged.
Source: https://github.com/openssl/openssl/blob/openssl-3.5.9/LICENSE.txt

SQLITE 3.50.4
The Python SQLite runtime reports version 3.50.4. SQLite's deliverable source
is dedicated to the public domain as described by its official copyright
statement. A complete copy of that statement/page is preserved in
SQLite-copyright.html.
Source: https://www.sqlite.org/copyright.html

UNICODE DATA / GENERATED CHARACTER RANGES
The DLC's generated Unicode letter ranges identify Unicode 15.1.0, matching
the build Python's unicodedata.unidata_version. These are derived Unicode data,
not a claim that the shipped range table uses Unicode 16.0.
Unicode data: Copyright 1991-2026 Unicode, Inc. The complete current Unicode
License V3 copyright/permission notice is retained in Unicode-LICENSE-V3.txt.
The license permits distribution of the data with this notice in associated
documentation. Python's full notice file also preserves its Unicode notices.
Sources: https://www.unicode.org/license.txt
         https://www.unicode.org/Public/15.1.0/ucd/

GAME / SERVICE MATERIAL
Civilization V and its UI assets/trademarks belong to their respective owners.
Users need their own game installation. The DLC adds UI contexts and does not
include or grant rights to the game executable, Steam client or EUI package.
The translation service calls Cloudflare-hosted Meta M2M100; model weights are
not distributed in this Windows/DLC package. Cloudflare/Meta service and model
terms govern that hosted usage separately.
https://developers.cloudflare.com/workers-ai/models/m2m100-1.2b/

DEVELOPMENT-ONLY TOOLS
The source workspace may use additional development, analysis and test tools.
The .venv, node_modules, raw game analysis, model downloads and saves are not
part of the public beta package. The notices above cover the identified beta
runtime components; a future package including new dependencies needs updated
notices. No new license for Improved Chat itself has been selected here.

LUA-LOCKBOX AES-128
DLC-only AES implementation from somesocks/lua-lockbox commit
d91607dfc6d2a0941186bac2234e34d7b7b48365, MIT, copyright 2015 James L.
Bundled into UI/IGT_Crypto.lua with local byte/array helpers replacing require.
License: lua-lockbox.txt. The SIV composition is original project code.

SERVER DEPENDENCIES
miscreant 0.3.2 (MIT) supplies RFC5297 AES-SIV using WebCrypto. Upstream is
archived and unaudited; pinning and interoperability tests do not replace audit.
fflate 0.8.3 (MIT) generates private ZIP downloads. See package-lock.json.
These JavaScript packages run on the hosted service, not inside Civ V.
