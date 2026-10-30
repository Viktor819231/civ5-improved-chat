import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
from unittest.mock import patch

from companion.credentials import CredentialError, protect_token, unlock_token
from companion.providers import Translator, TranslationError, cloudflare_endpoint
from companion.app import App


TOKEN = 'a' * 64
CONFIG = {'provider':'cloudflare','cloudflare_url':'https://proxy.example.test','cloudflare_token':TOKEN}


def reply(text='Hello', source='ru', target='en', usage=None):
    return io.BytesIO(json.dumps({'text':text,'source':source,'target':target,'usage':usage}).encode())


class Variable:
    def __init__(self,value=''): self.value=value
    def get(self): return self.value
    def set(self,value): self.value=value


class CloudflareProviderTests(unittest.TestCase):
    def test_post_contract_autodetection_and_server_usage(self):
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=reply(usage={'requestsRemaining':83,'inputBytesRemaining':9000})
            t=Translator(CONFIG)
            self.assertEqual(t.translate('Привет','auto','en'),('Hello','ru'))
            req=opener.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url,'https://proxy.example.test/v1/translate')
            self.assertEqual(req.get_header('Authorization'),'Bearer '+TOKEN)
            self.assertEqual(json.loads(req.data),{'text':'Привет','source':'ru','target':'en'})
            self.assertEqual(t.last_usage['requestsRemaining'],83)

    def test_colors_icons_cache_and_whitespace_stay_local(self):
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=reply()
            t=Translator(CONFIG)
            message='[COLOR_RED]Привет[ENDCOLOR] [ICON_GOLD]'
            self.assertEqual(t.translate(message,'ru','en')[0],'[COLOR_RED]Hello[ENDCOLOR] [ICON_GOLD]')
            self.assertEqual(t.translate(message,'ru','en')[0],'[COLOR_RED]Hello[ENDCOLOR] [ICON_GOLD]')
            self.assertEqual(opener.return_value.open.call_count,1)
            self.assertEqual(json.loads(opener.return_value.open.call_args.args[0].data)['text'],'Привет')

    def test_utf8_chunk_limit_and_roundtrip(self):
        chunks=[]
        def fake(req, timeout):
            data=json.loads(req.data);chunks.append(data['text'])
            self.assertLessEqual(len(data['text'].encode()),500)
            return reply(data['text'],'ko','en')
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=fake
            text='안녕하세요 친구 '*300
            self.assertEqual(Translator(CONFIG).translate(text,'auto','en')[0],text)
        self.assertGreater(len(chunks),1)

    def test_missing_configuration_never_falls_back(self):
        with patch('urllib.request.urlopen') as legacy, patch('urllib.request.build_opener') as proxy:
            for config in [{'provider':'cloudflare'},{'provider':'cloudflare','cloudflare_url':'https://proxy.example.test'}]:
                with self.assertRaises(TranslationError): Translator(config).translate('Привет','ru','en')
            legacy.assert_not_called();proxy.assert_not_called()

    def test_https_base_url_rejects_credentials_redirect_targets_and_local_hosts(self):
        for value in ['http://example.com','https://user:password@example.com','https://example.com?token=secret','https://example.com/v1/translate','https://localhost','https://127.0.0.1','https://10.0.0.1','https://[::1]','https://example.com:8000']:
            with self.assertRaises(TranslationError): cloudflare_endpoint(value)
        self.assertEqual(cloudflare_endpoint('https://proxy.example.test/'),'https://proxy.example.test/v1/translate')

    def test_failures_are_specific_and_never_disclose_tokens_or_provider_errors(self):
        for status, phrase in [(401,'token'),(429,'allowance'),(503,'disabled'),(302,'HTTP 302')]:
            with self.subTest(status=status), patch('urllib.request.build_opener') as opener:
                opener.return_value.open.side_effect=urllib.error.HTTPError('https://example.test/'+TOKEN,status,'PRIVATE',{},None)
                with self.assertRaises(TranslationError) as exc: Translator(CONFIG).translate('Привет','ru','en')
                self.assertIn(phrase,str(exc.exception));self.assertNotIn(TOKEN,str(exc.exception));self.assertNotIn('PRIVATE',str(exc.exception))

    def test_redirect_handler_refuses_all_redirects(self):
        from companion.providers import _NoRedirect
        self.assertIsNone(_NoRedirect().redirect_request(None,None,302,'',{},'https://other.test'))

    def test_expired_token_renews_once_without_alternative_provider(self):
        renewed_token='b'*64
        with patch('urllib.request.build_opener') as opener, patch('urllib.request.urlopen') as legacy, patch('companion.providers.unlock_token',return_value=renewed_token), patch('builtins.print'):
            refresh=unittest.mock.Mock(return_value='dpapi:renewed')
            opener.return_value.open.side_effect=[urllib.error.HTTPError('https://proxy.example.test',401,'',{},None),reply()]
            self.assertEqual(Translator({**CONFIG,'cloudflare_refresh_token':refresh}).translate('Привет','ru','en'),('Hello','ru'))
            refresh.assert_called_once_with()
            self.assertEqual(opener.return_value.open.call_args.args[0].get_header('Authorization'),'Bearer '+renewed_token)
            legacy.assert_not_called()

    def test_repeated_unauthorized_or_failed_renewal_does_not_loop(self):
        for failure in [False,True]:
            with self.subTest(failure=failure), patch('urllib.request.build_opener') as opener, patch('companion.providers.unlock_token',return_value='b'*64):
                refresh=unittest.mock.Mock(side_effect=RuntimeError('PRIVATE') if failure else None,return_value='dpapi:renewed')
                opener.return_value.open.side_effect=lambda *args,**kwargs: (_ for _ in ()).throw(urllib.error.HTTPError('https://proxy.example.test',401,'',{},None))
                with self.assertRaises(TranslationError) as error: Translator({**CONFIG,'cloudflare_refresh_token':refresh}).translate('Привет','ru','en')
                self.assertNotIn('PRIVATE',str(error.exception))
                refresh.assert_called_once_with()
                self.assertEqual(opener.return_value.open.call_count,1 if failure else 2)

    def test_mismatched_response_or_unsupported_languages_rejected(self):
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value=reply(source='uk')
            with self.assertRaisesRegex(TranslationError,'invalid'):Translator(CONFIG).translate('Привет','ru','en')
        with self.assertRaisesRegex(TranslationError,'prototype'):Translator(CONFIG).translate('Bonjour','xx','en')

    def test_dpapi_unlock_errors_are_sanitized(self):
        with patch('companion.providers.unlock_token',side_effect=CredentialError('sensitive diagnostic')):
            with self.assertRaises(TranslationError) as exc:Translator({**CONFIG,'cloudflare_token':'','cloudflare_token_protected':'dpapi:test'})
            self.assertNotIn('sensitive diagnostic',str(exc.exception))

    @unittest.skipUnless(sys.platform=='win32','Windows DPAPI integration')
    def test_windows_dpapi_roundtrip(self):
        protected=protect_token(TOKEN)
        self.assertTrue(protected.startswith('dpapi:'))
        self.assertNotIn(TOKEN,protected)
        self.assertEqual(unlock_token(protected),TOKEN)

    def test_unsupported_platform_never_stores_unprotected_token(self):
        with patch('companion.credentials.sys.platform','linux'):
            with self.assertRaises(CredentialError):protect_token(TOKEN)

    def test_settings_save_protects_token_preserves_blank_and_clear_removes_it(self):
        with tempfile.TemporaryDirectory() as folder:
            app=object.__new__(App)
            app.config_path=Path(folder)/'settings.json';app.config={};app.settings_lock=threading.Lock();app.version=0;app.clear_proxy_token=False
            for name,value in [('provider','cloudflare'),('email',''),('key',''),('region',''),('database','test.db'),('cloudflare_url','https://proxy.example.test'),('cloudflare_token',TOKEN),('proxy_usage',''),('status','')]:setattr(app,name,Variable(value))
            with patch('companion.app.protect_token',return_value='dpapi:encrypted') as protect:
                app.save();protect.assert_called_once_with(TOKEN)
            stored=json.loads(app.config_path.read_text())
            self.assertNotIn(TOKEN,app.config_path.read_text());self.assertNotIn('cloudflare_token',stored)
            self.assertEqual(stored['cloudflare_token_protected'],'dpapi:encrypted')
            app.save()
            self.assertEqual(json.loads(app.config_path.read_text())['cloudflare_token_protected'],'dpapi:encrypted')
            app.clear_cloudflare_token();app.save()
            self.assertEqual(json.loads(app.config_path.read_text())['cloudflare_token_protected'],'')


if __name__=='__main__':unittest.main()
