import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit

from companion.enrollment import PUBLIC_BETA_URL
from tools.release_privacy import PrivacyError,check_bytes


class ReleasePrivacyTests(unittest.TestCase):
    def test_default_api_is_neutral_and_backend_routes_are_disabled(self):
        self.assertEqual(urlsplit(PUBLIC_BETA_URL).hostname,'civ5-improved-chat-api.pages.dev')
        root=Path(__file__).resolve().parents[1]
        config=json.loads((root/'cloudflare/wrangler.jsonc').read_text(encoding='utf-8'))
        for environment in [config,*config['env'].values()]:
            self.assertIs(environment['workers_dev'],False)
            self.assertIs(environment['preview_urls'],False)

    def test_release_check_blocks_account_hostname_without_echoing_identity(self):
        host='translation.'+'example-account'+'.workers.dev'
        for scheme in ['https','HTTP']:
            with self.assertRaises(PrivacyError) as error:
                check_bytes((scheme+'://'+host+'/v1/translate').encode(),'test-artifact')
            self.assertNotIn(host,str(error.exception))
        check_bytes(PUBLIC_BETA_URL.encode(),'neutral-api')
        check_bytes(b'https://developers.cloudflare.com/workers/','official-docs')
