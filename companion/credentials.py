"""Protect the proxy access token with Windows DPAPI for this Windows user."""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import sys


class CredentialError(RuntimeError):
    pass


class _Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(data: bytes, decrypt: bool) -> bytes:
    if sys.platform != "win32":
        raise CredentialError("Protected token storage requires Windows.")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    buffer = ctypes.create_string_buffer(data)
    source = _Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = _Blob()
    blobp = ctypes.POINTER(_Blob)
    if decrypt:
        function = crypt32.CryptUnprotectData
        function.argtypes = [blobp, ctypes.c_void_p, blobp, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, blobp]
        second = None
    else:
        function = crypt32.CryptProtectData
        function.argtypes = [blobp, wintypes.LPCWSTR, blobp, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, blobp]
        second = "Improved Chat proxy token"
    function.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(source), second, None, None, None, 1, ctypes.byref(output)):
        raise CredentialError("Windows could not protect or unlock the proxy token. Enter it again under this Windows account.")
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel32.LocalFree(ctypes.cast(output.data, ctypes.c_void_p))


def protect_token(token: str) -> str:
    return "dpapi:" + base64.b64encode(_crypt(token.encode("utf-8"), False)).decode("ascii")


def unlock_token(protected: str) -> str:
    try:
        if not protected.startswith("dpapi:"):
            raise ValueError()
        return _crypt(base64.b64decode(protected[6:], validate=True), True).decode("utf-8")
    except (ValueError, UnicodeError, TypeError):
        raise CredentialError("The saved proxy token is invalid. Enter it again.") from None
