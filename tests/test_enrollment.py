"""No real service traffic: enrollment identity durability and consent boundaries."""
import hashlib
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
import urllib.error

from companion.app import App
from companion.credentials import CredentialError
from companion.enrollment import CONSENT_VERSION, PUBLIC_BETA_URL, EnrollmentError, EnrollmentManager, _NoRedirect, online_enabled


TOKEN = '1a' * 32
FUTURE = '2030-01-01T00:00:00.000Z'


class Variable:
    def __init__(self, value=''):
        self.value = value

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


class Response:
    def __init__(self, result):
        self.raw = json.dumps(result).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, length):
        return self.raw[:length]


class EnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'installation.json'
        self.sealed = {}
        self.requests = []

        def protect(value):
            encrypted = 'dpapi:' + hashlib.sha256(value.encode()).hexdigest()
            self.sealed[encrypted] = value
            return encrypted

        self.protect = protect
        self.unlock = lambda value: self.sealed[value]

    def tearDown(self):
        self.temp.cleanup()

    def service(self, request, timeout):
        payload = json.loads(request.data)
        self.requests.append((request.full_url, payload))
        return Response({'token': TOKEN, 'subject': 'install:' + payload['installationId'], 'expiresAt': FUTURE})

    def manager(self, opener=None):
        return EnrollmentManager(self.path, protect=self.protect, unlock=self.unlock,
                                 opener=opener or self.service, clock=lambda: 1800000000)

    def test_no_consent_makes_no_request_or_identity(self):
        with self.assertRaises(EnrollmentError):
            self.manager().ensure(PUBLIC_BETA_URL, enabled=False)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.requests, [])

    def test_identity_is_durable_before_network_and_secrets_protected(self):
        def service(request, timeout):
            self.assertTrue(self.path.exists())
            payload = json.loads(request.data)
            on_disk = self.path.read_text()
            self.assertNotIn(payload['registrationSecret'], on_disk)
            self.assertNotIn(TOKEN, on_disk)
            return self.service(request, timeout)

        result = self.manager(service).ensure(PUBLIC_BETA_URL, enabled=True)
        self.assertEqual(self.unlock(result.protected_token), TOKEN)
        self.assertNotIn(TOKEN, self.path.read_text())
        url, payload = self.requests[0]
        self.assertEqual(url, PUBLIC_BETA_URL + '/v1/installations/register')
        self.assertEqual(set(payload), {'version', 'installationId', 'registrationSecret'})
        self.assertEqual(payload['version'], 1)
        self.assertRegex(payload['registrationSecret'], r'^[0-9a-f]{64}$')
        self.assertEqual(result.subject, 'install:' + payload['installationId'])

    def test_cached_token_and_forced_renewal_keep_same_identity_and_secret(self):
        first = self.manager().ensure(PUBLIC_BETA_URL, enabled=True)
        cached = self.manager().ensure(PUBLIC_BETA_URL + '/', enabled=True)
        self.assertEqual(cached, first)
        self.assertEqual(len(self.requests), 1)
        renewed = self.manager().ensure(PUBLIC_BETA_URL, enabled=True, force=True)
        self.assertEqual(renewed.subject, first.subject)
        self.assertEqual(self.requests[1][0], PUBLIC_BETA_URL + '/v1/installations/renew')
        self.assertEqual(self.requests[1][1], self.requests[0][1])

    def test_renewal_happens_before_expiration(self):
        self.manager().ensure(PUBLIC_BETA_URL, enabled=True)
        state = json.loads(self.path.read_text())
        state['services'][PUBLIC_BETA_URL]['expires_at'] = '2027-01-15T08:00:00Z'
        self.path.write_text(json.dumps(state))
        self.manager().ensure(PUBLIC_BETA_URL, enabled=True)
        self.assertEqual(len(self.requests), 2)
        self.assertTrue(self.requests[-1][0].endswith('/renew'))

    def test_network_failure_retry_does_not_create_a_new_installation(self):
        sent = []

        def offline(request, timeout):
            sent.append(json.loads(request.data))
            raise urllib.error.URLError('offline')

        with self.assertRaises(EnrollmentError):
            self.manager(offline).ensure(PUBLIC_BETA_URL, enabled=True)
        self.manager().ensure(PUBLIC_BETA_URL, enabled=True)
        self.assertEqual(sent[0], self.requests[0][1])

    def test_denial_and_quota_failure_keep_existing_identity(self):
        self.manager().ensure(PUBLIC_BETA_URL, enabled=True)
        original = self.path.read_text()
        for code in (403, 429, 503):
            with self.subTest(code=code):
                def denied(request, timeout):
                    raise urllib.error.HTTPError(request.full_url, code, 'denied', {}, None)
                with self.assertRaises(EnrollmentError):
                    self.manager(denied).ensure(PUBLIC_BETA_URL, enabled=True, force=True)
                self.assertEqual(self.path.read_text(), original)

    def test_corrupt_or_unreadable_secret_does_not_recreate_identity(self):
        self.manager().ensure(PUBLIC_BETA_URL, enabled=True)
        original = self.path.read_text()
        manager = self.manager()
        manager.unlock = Mock(side_effect=CredentialError('sensitive secret'))
        with self.assertRaises(EnrollmentError) as raised:
            manager.ensure(PUBLIC_BETA_URL, enabled=True)
        self.assertNotIn('sensitive secret', str(raised.exception))
        self.assertEqual(self.path.read_text(), original)
        self.assertEqual(len(self.requests), 1)

    def test_invalid_response_subject_does_not_save_token(self):
        def wrong(request, timeout):
            return Response({'token': TOKEN, 'subject': 'install:other', 'expiresAt': FUTURE})
        with self.assertRaises(EnrollmentError):
            self.manager(wrong).ensure(PUBLIC_BETA_URL, enabled=True)
        self.assertNotIn('token_protected', self.path.read_text())

    def test_http_or_embedded_credentials_are_rejected_before_registration(self):
        for base in ('http://example.com', 'https://secret@example.com', 'https://example.com/path', 'https://127.0.0.1'):
            with self.subTest(base=base), self.assertRaises(EnrollmentError):
                self.manager().ensure(base, enabled=True)
        self.assertFalse(self.path.exists())

    def test_redirect_never_forwards_registration_secret(self):
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 307, 'redirect', {}, 'https://other.example'))

    def test_credentials_are_scoped_to_service(self):
        self.manager().ensure(PUBLIC_BETA_URL, enabled=True)
        self.manager().ensure('https://another.example.com', enabled=True)
        self.manager().ensure(PUBLIC_BETA_URL, enabled=True)
        self.assertEqual(len(self.requests), 2)
        self.assertNotEqual(self.requests[0][1]['installationId'], self.requests[1][1]['installationId'])


class AppConsentTests(unittest.TestCase):
    def test_old_or_missing_consent_does_not_enable_online(self):
        self.assertFalse(online_enabled({}))
        self.assertFalse(online_enabled({'online_translation_enabled': True}))
        self.assertFalse(online_enabled({'online_translation_enabled': True, 'online_consent_version': 0}))
        self.assertTrue(online_enabled({'online_translation_enabled': True, 'online_consent_version': CONSENT_VERSION}))

    def test_worker_waits_without_enrollment_or_translator_before_consent(self):
        app = object.__new__(App)
        app.config = {'db_path': 'not-created.db'}
        app.version = 0
        app.settings_lock = threading.Lock()
        app.stop = Mock()
        app.stop.is_set.side_effect = [False, True]
        app.enrollment = Mock()
        with patch('companion.app.Translator') as translator, patch('companion.app.Bridge') as bridge:
            app.worker()
        app.enrollment.ensure.assert_not_called()
        translator.assert_not_called()
        bridge.assert_not_called()

    def test_enable_is_explicit_and_cancels_preconsent_drafts(self):
        with tempfile.TemporaryDirectory() as folder:
            db_path = Path(folder) / 'game.db'
            with closing(sqlite3.connect(db_path, isolation_level=None)) as db:
                db.execute('CREATE TABLE requests(status TEXT,result TEXT,error TEXT)')
                db.execute("INSERT INTO requests VALUES('pending',NULL,NULL)")
                db.execute("INSERT INTO requests VALUES('working',NULL,NULL)")
            app = object.__new__(App)
            app.config = {'db_path': str(db_path), 'provider': 'cloudflare'}
            app.config_path = Path(folder) / 'settings.json'
            app.settings_lock = threading.Lock()
            app.version = 0
            app.enable_button = Mock()
            app.status = Variable()
            app.enrollment = Mock()
            app.enable_online()
            self.assertTrue(online_enabled(json.loads(app.config_path.read_text())))
            with closing(sqlite3.connect(db_path)) as db:
                self.assertEqual(db.execute('SELECT status FROM requests').fetchall(), [('error',), ('error',)])
            app.enrollment.ensure.assert_not_called()  # Networking belongs to the worker.


if __name__ == '__main__':
    unittest.main()
