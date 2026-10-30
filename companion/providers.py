"""Translation backends for the prototype; no third-party Python dependencies.

MyMemory has no language detector: automatic source selection here is deliberately
limited to the prototype's English, Russian, Ukrainian and Korean languages.
Short Ukrainian without distinctive letters can be mistaken for Russian. Choose
the source language explicitly when this happens.
"""

from __future__ import annotations

import html
import ipaddress
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict

from companion.credentials import CredentialError, unlock_token
from companion.transliteration import russian_from_latin


class TranslationError(RuntimeError):
    """A provider failure safe to show without exposing chat text or API keys."""


_TOKEN = re.compile(r"(\[ICON_[A-Z0-9_]+\]|\[COLOR_[A-Z0-9_]+\]|\[ENDCOLOR\]|\[TR(?:[^\]\r\n]{0,32})?\])")
_COLOR = re.compile(r"\[(?:COLOR_[A-Z0-9_]+|ENDCOLOR)\]")
_LANGUAGE = re.compile(r"^[a-z]{2,3}(?:-[a-zA-Z]{2,8})?$")
_QUOTA_MARKERS = ("MYMEMORY WARNING", "YOU USED ALL AVAILABLE FREE TRANSLATIONS", "NEXT AVAILABLE IN")
_CLOUDFLARE_LANGUAGES = {"en","ru","uk","ko","fr","de","es","pl","pt","tr","it","nl","sv","zh","ja","ar"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None  # Never forward the bearer token to a redirected host.


def cloudflare_endpoint(base: str) -> str:
    try:
        url = urllib.parse.urlsplit(base.strip())
        host = url.hostname or ""
        if url.scheme != "https" or not host or url.username is not None or url.password is not None or url.query or url.fragment or url.path not in ("", "/") or url.port not in (None,443):
            raise ValueError()
        if host.lower() == "localhost" or host.lower().endswith((".localhost", ".local")):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address and not address.is_global:
            raise ValueError()
        return urllib.parse.urlunsplit(("https",url.netloc,"/v1/translate","",""))
    except (ValueError, AttributeError):
        raise TranslationError("Enter the Cloudflare server's HTTPS base URL, without credentials or a path.") from None


def detect_source(text: str) -> str:
    """Conservative script heuristic, not a general language detection model."""
    plain = _COLOR.sub("", _TOKEN.sub("", text))
    letters = [c for c in plain if c.isalpha()]
    if not letters:
        return "en"
    korean = sum("HANGUL" in unicodedata.name(c, "") for c in letters)
    cyrillic = sum("CYRILLIC" in unicodedata.name(c, "") for c in letters)
    latin = sum("LATIN" in unicodedata.name(c, "") for c in letters)
    # A message can contain ASCII game terms alongside another language.
    if korean and korean >= cyrillic:
        return "ko"
    if cyrillic:
        # Other Cyrillic languages need an explicit source, not a Russian guess.
        allowed = set("абвгґдеєжзиіїйклмнопрстуфхцчшщъыьэюяё")
        if any("CYRILLIC" in unicodedata.name(c, "") and c.lower() not in allowed for c in letters):
            raise TranslationError("Choose the source language: this Cyrillic script is not recognised automatically.")
        return "uk" if any(c in plain.lower() for c in "іїєґ") else "ru"
    if latin == len(letters):
        # English is the documented fallback, not a claim to detect all Latin languages.
        return "en"
    raise TranslationError("Choose the source language: automatic detection supports English, Russian, Ukrainian and Korean.")


def split_utf8(text: str, limit: int = 500) -> list[str]:
    """Split on whitespace when practical, preserving every byte of the input."""
    if limit < 4:
        raise ValueError("The UTF-8 chunk limit must be at least four bytes.")
    chunks = []
    while text:
        size, end, last_space = 0, 0, 0
        for index, char in enumerate(text):
            width = len(char.encode("utf-8"))
            if size + width > limit:
                break
            size += width
            end = index + 1
            if char.isspace():
                last_space = end
        if end < len(text) and last_space > end // 2:
            end = last_space
        chunks.append(text[:end])
        text = text[end:]
    return chunks


class Translator:
    """Thread-confined synchronous client. Keep one instance in the worker."""

    def __init__(self, config: dict | None = None):
        self.config = dict(config or {})
        self.provider = str(self.config.get("provider", "mymemory")).lower()
        if self.provider not in ("mymemory", "azure", "cloudflare"):
            raise ValueError("Choose provider mymemory, azure or cloudflare.")
        self.last_usage = None
        self._proxy_token = str(self.config.pop("cloudflare_token", "")).strip()
        if self.provider == "cloudflare" and not self._proxy_token and self.config.get("cloudflare_token_protected"):
            try:
                self._proxy_token = unlock_token(self.config["cloudflare_token_protected"])
            except CredentialError:
                raise TranslationError("Cannot unlock the saved Cloudflare token. Enter it again in Settings.") from None
        self._cache: OrderedDict[tuple[str, str, str], tuple[str, str]] = OrderedDict()

    def translate(self, text: str, source: str, target: str) -> tuple[str, str]:
        if not isinstance(text, str):
            raise TranslationError("The message must be text.")
        source, target = (source or "auto").lower(), (target or "en").lower()
        if not _LANGUAGE.fullmatch(target) or (source != "auto" and not _LANGUAGE.fullmatch(source)):
            raise TranslationError("Choose a valid source and target language.")
        if len(text.encode("utf-8")) > 16000:
            raise TranslationError("This message is too long. Translate at most 16,000 UTF-8 bytes at a time.")
        # Keep colour boundaries locally; translate only the text between tags.
        if not text.strip():
            return text, source if source != "auto" else "en"
        if self.provider == "cloudflare":
            self._proxy_endpoint = cloudflare_endpoint(str(self.config.get("cloudflare_url", "")))
            if not re.fullmatch(r"[a-f0-9]{64}", self._proxy_token):
                raise TranslationError("Add your Cloudflare proxy access token in companion Settings. No alternative provider will be used.")
        latin_russian = source == "ru-latn"
        resolved = "ru" if latin_russian else detect_source(text) if source == "auto" and self.provider in ("mymemory", "cloudflare") else source
        if self.provider == "cloudflare" and (resolved not in _CLOUDFLARE_LANGUAGES or target not in _CLOUDFLARE_LANGUAGES):
            raise TranslationError("Choose a language supported by the Cloudflare prototype.")
        key = (text, "ru-latn" if latin_russian else resolved, target)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        if latin_russian:
            text = ''.join(part if _TOKEN.fullmatch(part) else russian_from_latin(part) for part in _TOKEN.split(text) if part)
        if resolved == target:
            return text, resolved
        if self.provider == "azure" and not self.config.get("azure_key", "").strip():
            raise TranslationError("Add your Azure API key in the companion settings first.")
        deadline = time.monotonic() + 30
        output, detected = [], resolved
        for part in _TOKEN.split(text):
            if not part:
                continue
            if _TOKEN.fullmatch(part) or not any(c.isalpha() for c in part):
                output.append(part)
                continue
            limit = {"mymemory": 500, "azure": 8000, "cloudflare": 500}[self.provider]
            for chunk in split_utf8(part, limit):
                left = chunk[:len(chunk) - len(chunk.lstrip())]
                right = chunk[len(chunk.rstrip()):]
                core = chunk.strip()
                if not core or not any(c.isalpha() for c in core):
                    output.append(chunk)
                    continue
                if self.provider == "mymemory":
                    result = self._mymemory(core, resolved, target, deadline)
                elif self.provider == "cloudflare":
                    result = self._cloudflare(core, resolved, target, deadline)
                else:
                    result, detected = self._azure(core, resolved, target, deadline)
                output.append(left + result + right)
        result = ("".join(output), detected if detected != "auto" else "unknown")
        self._cache[key] = result
        if len(self._cache) > 500:
            self._cache.popitem(last=False)
        return result

    def _request(self, request: urllib.request.Request, deadline: float, renewed: bool = False):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TranslationError("Translation timed out. Try a shorter message.")
        try:
            open_request = urllib.request.build_opener(_NoRedirect()).open if self.provider == "cloudflare" else urllib.request.urlopen
            with open_request(request, timeout=min(10, remaining)) as response:
                raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise TranslationError("The translation service returned an oversized response.")
            return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as error:
            if self.provider == "cloudflare":
                refresh = self.config.get("cloudflare_refresh_token")
                if error.code == 401 and not renewed and callable(refresh):
                    error.close()
                    try:
                        token = unlock_token(refresh())
                        if not re.fullmatch(r"[a-f0-9]{64}", token):
                            raise ValueError()
                    except Exception:
                        raise TranslationError("Cannot renew online translation access. Try again later; your installation allowance has not been reset.") from None
                    self._proxy_token = token
                    request.add_header("Authorization", "Bearer " + token)
                    return self._request(request, deadline, renewed=True)
                messages = {401:"Cloudflare access token is invalid, expired or revoked. Update it in Settings.",403:"Cloudflare denied this account access.",429:"Cloudflare account or service allowance/rate limit reached. Try again later.",503:"The Cloudflare translation service is currently disabled.",413:"Cloudflare rejected this message as too large."}
                raise TranslationError(messages.get(error.code,"Cloudflare translation failed (HTTP %s)." % error.code)) from None
            if error.code == 429:
                raise TranslationError("Translation quota or rate limit reached. Please try again later.") from None
            if error.code in (401, 403):
                message = "Azure rejected the API key or region." if self.provider == "azure" else "MyMemory denied this request or its free quota is exhausted."
                raise TranslationError(message) from None
            raise TranslationError("The translation service is unavailable (HTTP %s)." % error.code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise TranslationError("Cannot reach the translation service. Check your connection and try again.") from None
        except (ValueError, UnicodeError):
            raise TranslationError("The translation service returned an invalid response.") from None

    def _cloudflare(self, text: str, source: str, target: str, deadline: float) -> str:
        request = urllib.request.Request(self._proxy_endpoint,
            data=json.dumps({"text":text,"source":source,"target":target},ensure_ascii=False).encode("utf-8"),
            headers={"Authorization":"Bearer " + self._proxy_token,"Content-Type":"application/json","Accept":"application/json","User-Agent":"ImprovedChat/0.8"},method="POST")
        payload = self._request(request,deadline)
        if not isinstance(payload,dict) or not isinstance(payload.get("text"),str) or not payload["text"].strip() or payload.get("source") != source or payload.get("target") != target:
            raise TranslationError("Cloudflare returned an invalid translation response.")
        # Usage is an informational server snapshot, never a client-side quota authority.
        self.last_usage = payload.get("usage") if isinstance(payload.get("usage"),dict) else None
        return payload["text"].replace("\x00", "").strip()

    def _mymemory(self, text: str, source: str, target: str, deadline: float) -> str:
        params = {"q": text, "langpair": source + "|" + target}
        email = str(self.config.get("mymemory_email", "")).strip()
        if email:
            params["de"] = email
        request = urllib.request.Request(
            "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode(params),
            headers={"User-Agent": "InGameTranslateMod/0.1", "Accept": "application/json"},
        )
        payload = self._request(request, deadline)
        if not isinstance(payload, dict):
            raise TranslationError("MyMemory returned an invalid response.")
        status = str(payload.get("responseStatus", ""))
        if status in ("403", "429") or payload.get("quotaFinished") is True:
            raise TranslationError("MyMemory's free translation quota is exhausted. Try again after its daily reset.")
        if status != "200":
            raise TranslationError("MyMemory could not translate this language pair. Check the source and target settings.")
        data = payload.get("responseData")
        result = data.get("translatedText") if isinstance(data, dict) else None
        if not isinstance(result, str) or not result.strip():
            raise TranslationError("MyMemory returned no translation.")
        if any(marker in result.upper() for marker in _QUOTA_MARKERS):
            raise TranslationError("MyMemory's free translation quota is exhausted. Try again after its daily reset.")
        return html.unescape(result).replace("\x00", "").strip()

    def _azure(self, text: str, source: str, target: str, deadline: float) -> tuple[str, str]:
        params = {"api-version": "3.0", "to": target, "textType": "plain"}
        if source != "auto":
            params["from"] = source
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Ocp-Apim-Subscription-Key": str(self.config["azure_key"]).strip(),
            "User-Agent": "InGameTranslateMod/0.1",
        }
        region = str(self.config.get("azure_region", "")).strip()
        if region:
            headers["Ocp-Apim-Subscription-Region"] = region
        request = urllib.request.Request(
            "https://api.cognitive.microsofttranslator.com/translate?" + urllib.parse.urlencode(params),
            data=json.dumps([{"Text": text}], ensure_ascii=False).encode("utf-8"),
            headers=headers, method="POST",
        )
        payload = self._request(request, deadline)
        try:
            result = payload[0]["translations"][0]["text"]
            detected = payload[0].get("detectedLanguage", {}).get("language", source)
            if not isinstance(result, str) or not isinstance(detected, str):
                raise ValueError()
            return result.replace("\x00", ""), detected
        except (KeyError, IndexError, TypeError, ValueError):
            raise TranslationError("Azure returned an invalid translation response.") from None
