import io
import json
import unittest
import urllib.error
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from companion.providers import Translator, TranslationError, detect_source, split_utf8


def response(payload):
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


def mymemory(text="Hello"):
    return response({"responseStatus": 200, "responseData": {"translatedText": text}})


class ProviderTests(unittest.TestCase):
    def test_color_spans_preserved_without_translating_color_codes(self):
        with patch('urllib.request.urlopen', side_effect=[mymemory('Hello'), mymemory('friend')]) as request:
            result, detected = Translator({}).translate('[COLOR_RED]Привет[ENDCOLOR] [COLOR_CYAN]друг[ENDCOLOR]', 'auto', 'en')
            self.assertEqual(result, '[COLOR_RED]Hello[ENDCOLOR] [COLOR_CYAN]friend[ENDCOLOR]')
            self.assertEqual(detected, 'ru')
            self.assertEqual([parse_qs(urlsplit(c.args[0].full_url).query)['q'][0] for c in request.call_args_list], ['Привет', 'друг'])

    def test_same_language_keeps_colors_without_api(self):
        text = '[COLOR_GREEN]hello[ENDCOLOR]'
        with patch('urllib.request.urlopen') as request:
            self.assertEqual(Translator({}).translate(text, 'auto', 'en'), (text, 'en'))
            request.assert_not_called()

    def test_script_detection(self):
        for text, expected in [("Привет!", "ru"), ("Привіт!", "uk"), ("안녕하세요", "ko"), ("Hello", "en"), ("[ICON_GOLD] 10", "en")]:
            self.assertEqual(detect_source(text), expected)
        with self.assertRaises(TranslationError):
            detect_source("你好")

    def test_utf8_chunk_roundtrip(self):
        for text in ["Привет мир! " * 120, "안녕하세요 " * 100, "🦆" * 501, "word " * 300]:
            chunks = split_utf8(text)
            self.assertEqual("".join(chunks), text)
            self.assertTrue(all(0 < len(c.encode("utf-8")) <= 500 for c in chunks))

    def test_auto_source_and_cache(self):
        with patch("urllib.request.urlopen", return_value=mymemory()) as request:
            translator = Translator({})
            self.assertEqual(translator.translate("Привет", "auto", "en"), ("Hello", "ru"))
            self.assertEqual(translator.translate("Привет", "auto", "en"), ("Hello", "ru"))
            self.assertEqual(request.call_count, 1)
            params = parse_qs(urlsplit(request.call_args.args[0].full_url).query)
            self.assertEqual(params["langpair"], ["ru|en"])

    def test_same_language_no_network(self):
        with patch("urllib.request.urlopen") as request:
            self.assertEqual(Translator({}).translate("Hello", "auto", "en"), ("Hello", "en"))
            request.assert_not_called()

    def test_icons_tags_and_spacing_preserved(self):
        with patch("urllib.request.urlopen", side_effect=[mymemory("Дай 5"), mymemory("сейчас")]) as request:
            result, _ = Translator({}).translate("[TR] Give 5 [ICON_GOLD] now", "en", "ru")
            self.assertEqual(result, "[TR] Дай 5 [ICON_GOLD] сейчас")
            for call in request.call_args_list:
                query = parse_qs(urlsplit(call.args[0].full_url).query)["q"][0]
                self.assertNotIn("[ICON_", query)
                self.assertNotIn("[TR]", query)

    def test_large_korean_request_byte_limits(self):
        calls = []
        def fake(request, timeout):
            query = parse_qs(urlsplit(request.full_url).query)["q"][0]
            calls.append(query)
            self.assertLessEqual(len(query.encode("utf-8")), 500)
            self.assertLessEqual(timeout, 10)
            return mymemory(query)
        text = "안녕하세요 친구 " * 100
        with patch("urllib.request.urlopen", side_effect=fake):
            result, detected = Translator({}).translate(text, "auto", "en")
        self.assertEqual(detected, "ko")
        self.assertEqual(result, text)
        self.assertGreater(len(calls), 1)

    def test_quota_body_rejected(self):
        for payload in [
            {"responseStatus": "403", "responseData": {"translatedText": "quota"}},
            {"responseStatus": 200, "quotaFinished": True},
            {"responseStatus": 200, "responseData": {"translatedText": "MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS"}},
        ]:
            with patch("urllib.request.urlopen", return_value=response(payload)):
                with self.assertRaisesRegex(TranslationError, "quota"):
                    Translator({}).translate("Привет", "ru", "en")

    def test_html_unescape(self):
        with patch("urllib.request.urlopen", return_value=mymemory("Tom &amp; Jerry&#39;s")):
            self.assertEqual(Translator({}).translate("пример", "ru", "en")[0], "Tom & Jerry's")

    def test_email_and_explicit_other_language(self):
        with patch("urllib.request.urlopen", return_value=mymemory("Hello")) as request:
            Translator({"mymemory_email": "test@example.com"}).translate("Bonjour", "fr", "en")
            params = parse_qs(urlsplit(request.call_args.args[0].full_url).query)
            self.assertEqual(params["de"], ["test@example.com"])
            self.assertEqual(params["langpair"], ["fr|en"])

    def test_http_error_does_not_leak_url(self):
        error = urllib.error.HTTPError("https://secret/?q=PRIVATE", 429, "PRIVATE", {}, None)
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaises(TranslationError) as result:
                Translator({}).translate("Привет", "ru", "en")
        self.assertNotIn("PRIVATE", str(result.exception))

    def test_azure_auto(self):
        payload = [{"detectedLanguage": {"language": "ko"}, "translations": [{"text": "Hello", "to": "en"}]}]
        with patch("urllib.request.urlopen", return_value=response(payload)) as request:
            result = Translator({"provider": "azure", "azure_key": "fake", "azure_region": "swedencentral"}).translate("안녕하세요", "auto", "en")
            self.assertEqual(result, ("Hello", "ko"))
            req = request.call_args.args[0]
            self.assertEqual(req.method, "POST")
            self.assertNotIn("from=", req.full_url)
            self.assertEqual(json.loads(req.data)[0]["Text"], "안녕하세요")

    def test_missing_azure_key(self):
        with self.assertRaisesRegex(TranslationError, "API key"):
            Translator({"provider": "azure"}).translate("Hello", "en", "ru")


if __name__ == "__main__":
    unittest.main()
