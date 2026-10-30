import io
import json
import unittest
from unittest.mock import patch

from companion.providers import Translator
from companion.transliteration import russian_from_latin


class TransliterationTests(unittest.TestCase):
    def test_common_informal_spellings_case_and_existing_cyrillic(self):
        self.assertEqual(russian_from_latin('Privet! Ya hochu gold, moy drug. Спасибо :)'),
                         'Привет! Я хочу голд, мой друг. Спасибо :)')
        self.assertEqual(russian_from_latin("SHCH shh sch zh kh ts ch sh yu ju ya ja yo jo ye eh pisat' russkii"),
                         'Щ щ щ ж х ц ч ш ю ю я я ё ё е э писать русский')

    def test_links_emails_and_punctuation_stay_unchanged(self):
        text='privet https://example.org/ru?id=test www.example.com/a foo.bar@example.org 123 :)))'
        self.assertEqual(russian_from_latin(text),'привет https://example.org/ru?id=test www.example.com/a foo.bar@example.org 123 :)))')

    def test_explicit_mode_converts_locally_and_uses_existing_russian_api_contract(self):
        config={'provider':'cloudflare','cloudflare_url':'https://proxy.example.test','cloudflare_token':'a'*64}
        calls=[]
        def response(request,timeout):
            value=json.loads(request.data);calls.append(value)
            return io.BytesIO(json.dumps({'text':'Hello','source':'ru','target':'en'}).encode())
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=response
            translator=Translator(config)
            self.assertEqual(translator.translate('privet','auto','en'),('privet','en'))
            message='[COLOR_CYAN]privet[ENDCOLOR] [ICON_GOLD]'
            self.assertEqual(translator.translate(message,'ru-Latn','en'),('[COLOR_CYAN]Hello[ENDCOLOR] [ICON_GOLD]','ru'))
            translator.translate(message,'ru-Latn','en')
            translator.translate(message,'ru','en')
        self.assertEqual(calls,[{'text':'привет','source':'ru','target':'en'},{'text':'privet','source':'ru','target':'en'}])

    def test_same_language_can_convert_to_cyrillic_without_network(self):
        with patch('urllib.request.urlopen') as request:
            self.assertEqual(Translator({}).translate("[ICON_GOLD] ya mogu pisat'",'ru-latn','ru'),('[ICON_GOLD] я могу писать','ru'))
            request.assert_not_called()

    def test_converted_bytes_are_chunked_at_the_server_limit(self):
        config={'provider':'cloudflare','cloudflare_url':'https://proxy.example.test','cloudflare_token':'a'*64}
        calls=[]
        def response(request,timeout):
            value=json.loads(request.data);calls.append(value['text'])
            self.assertLessEqual(len(value['text'].encode()),500)
            return io.BytesIO(json.dumps({'text':value['text'],'source':'ru','target':'en'}).encode())
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=response
            self.assertEqual(Translator(config).translate('privet '*90,'ru-latn','en')[0],'привет '*90)
        self.assertGreater(len(calls),1)
