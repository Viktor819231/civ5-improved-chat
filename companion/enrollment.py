"""Automatic installation credentials for the opt-in public translation beta.

An installation is not a verified Steam account. Its durable identity is saved
before registration, so renewal/retry uses the same server allowance.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import secrets
import time
import urllib.error
import urllib.request
import uuid

from companion.credentials import CredentialError, protect_token, unlock_token
from companion.providers import TranslationError, cloudflare_endpoint

PUBLIC_BETA_URL = 'https://civ5-improved-chat-api.pages.dev'
CONSENT_VERSION = 1
_SECRET = re.compile(r'^[a-f0-9]{64}$')


class EnrollmentError(RuntimeError):
    """Safe registration failure; never includes access or recovery credentials."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def online_enabled(config: dict) -> bool:
    return config.get('online_translation_enabled') is True and config.get('online_consent_version') == CONSENT_VERSION


@dataclass(frozen=True)
class Enrollment:
    protected_token: str
    subject: str
    expires_at: str


class EnrollmentManager:
    def __init__(self, path: str | Path, *, protect=protect_token, unlock=unlock_token,
                 opener=None, clock=time.time):
        self.path = Path(path)
        self.protect, self.unlock, self.clock = protect, unlock, clock
        self.opener = opener or urllib.request.build_opener(_NoRedirect()).open

    def _read(self):
        if not self.path.exists():
            return {'version': 1, 'services': {}}
        try:
            state = json.loads(self.path.read_text(encoding='utf-8'))
            if state.get('version') != 1 or not isinstance(state.get('services'), dict):
                raise ValueError()
            return state
        except (OSError, ValueError, TypeError, AttributeError):
            raise EnrollmentError('Saved installation credentials could not be read. Registration was stopped; no replacement identity was created.') from None

    def _write(self, state):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix('.tmp')
            temp.write_text(json.dumps(state, indent=2), encoding='utf-8')
            temp.replace(self.path)
        except OSError:
            raise EnrollmentError('Installation credentials could not be saved. Translation registration was stopped.') from None

    @staticmethod
    def _expiry(value):
        if not isinstance(value, str):
            raise ValueError()
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if date.tzinfo is None:
            raise ValueError()
        return date.timestamp()

    def ensure(self, base: str, *, enabled: bool, force: bool = False) -> Enrollment:
        if enabled is not True:
            raise EnrollmentError('Enable online translation before connecting to the translation service.')
        try:
            base = cloudflare_endpoint(base).removesuffix('/v1/translate')
        except TranslationError:
            raise EnrollmentError('Use the translation service HTTPS base URL, without a path or login information.') from None
        state = self._read()
        entry = state['services'].get(base)
        new = entry is None
        try:
            if new:
                entry = {'installation_id': str(uuid.uuid4()),
                         'registration_secret_protected': self.protect(secrets.token_hex(32))}
                state['services'][base] = entry
                # Never issue a request until the same identity is durable locally.
                self._write(state)
            installation = entry['installation_id']
            if str(uuid.UUID(installation, version=4)) != installation or uuid.UUID(installation).version != 4:
                raise ValueError()
            secret = self.unlock(entry['registration_secret_protected'])
            if not _SECRET.fullmatch(secret):
                raise ValueError()
            subject = 'install:' + installation
            if not force and entry.get('token_protected'):
                token = self.unlock(entry['token_protected'])
                if not _SECRET.fullmatch(token):
                    raise ValueError()
                if self._expiry(entry.get('expires_at')) > self.clock() + 86400:
                    return Enrollment(entry['token_protected'], subject, entry['expires_at'])
        except CredentialError:
            raise EnrollmentError('Windows could not unlock this installation’s credentials. Use the Windows account that enabled translation; no replacement identity was created.') from None
        except (KeyError, TypeError, ValueError, AttributeError):
            raise EnrollmentError('Saved installation credentials are invalid. Registration was stopped; no replacement identity was created.') from None

        request = urllib.request.Request(
            base + ('/v1/installations/register' if new or not entry.get('token_protected') else '/v1/installations/renew'),
            data=json.dumps({'version': 1, 'installationId': installation, 'registrationSecret': secret}).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'Accept': 'application/json',
                     'User-Agent': 'ImprovedChat/0.9'}, method='POST')
        try:
            with self.opener(request, timeout=10) as response:
                raw = response.read(16385)
            if len(raw) > 16384:
                raise ValueError()
            result = json.loads(raw.decode('utf-8'))
            if not isinstance(result, dict) or not _SECRET.fullmatch(result.get('token', '')) or result.get('subject') != subject:
                raise ValueError()
            expires = result.get('expiresAt')
            if self._expiry(expires) <= self.clock():
                raise ValueError()
            protected = self.protect(result['token'])
        except urllib.error.HTTPError as error:
            messages = {403: 'Translation registration was denied. The saved installation identity was kept.',
                        429: 'Translation registration is temporarily limited. Try again later; your identity and allowance were kept.',
                        503: 'The public translation beta is currently paused. Try again later.'}
            raise EnrollmentError(messages.get(error.code, 'Translation registration could not be completed. Try again later.')) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise EnrollmentError('Cannot reach the translation service. Your saved installation identity was kept; check your connection and retry.') from None
        except CredentialError:
            raise EnrollmentError('Windows could not protect the translation access token. Registration was stopped.') from None
        except (ValueError, UnicodeError, TypeError, AttributeError):
            raise EnrollmentError('The translation service returned invalid registration information.') from None
        entry['token_protected'], entry['expires_at'] = protected, expires
        self._write(state)
        return Enrollment(protected, subject, expires)
