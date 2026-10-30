import re
import unittest
from pathlib import Path
from lupa.lua51 import LuaRuntime

ROOT = Path(__file__).resolve().parents[1]


class TextTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute((ROOT / 'DLC/InGameTranslateMod/UI/IGT_Text.lua').read_text(encoding='utf-8'))
        self.helper = self.lua.globals().IGT_Text

    def test_multilingual_long_message_preserves_utf8_and_icons(self):
        for body in ['Привет мир! ' * 100, '안녕하세요 친구! ' * 100, 'Потрібна допомога? ' * 80, '[ICON_GOLD] gold ' * 100]:
            chunks = list(self.helper.Split('(TR) ' + body, 240).values())
            self.assertTrue(all(len(c.encode('utf-8')) <= 240 for c in chunks))
            self.assertTrue(all(c.startswith('(TR) ') for c in chunks))
            restored = ''.join(re.sub(r'^\(TR\) \(\d+/\d+\) ', '', c) for c in chunks)
            self.assertEqual(body, restored)
            if '[ICON_GOLD]' in body:
                self.assertEqual(sum(c.count('[ICON_GOLD]') for c in chunks), 100)

    def test_safe_display_preserves_balanced_colors_and_icons(self):
        self.assertEqual(self.helper.SafeDisplay('[COLOR_RED]hello[ENDCOLOR] [ICON_GOLD] [TR]'), '[COLOR_RED]hello[ENDCOLOR] [ICON_GOLD] (TR)')
        self.assertEqual(self.helper.SafeDisplay('[ENDCOLOR][COLOR_CYAN]hello'), '[COLOR_CYAN]hello[ENDCOLOR]')

    def test_colored_parts_balance_and_preserve_text(self):
        text = '[COLOR_RED]' + ('Привет ' * 50) + '[COLOR_CYAN]' + ('안녕 ' * 70) + '[ENDCOLOR] done[ENDCOLOR]'
        chunks = list(self.helper.Split(text, 240).values())
        plain = []
        for chunk in chunks:
            self.assertLessEqual(len(chunk.encode('utf-8')), 240)
            depth = 0
            for tag in re.findall(r'\[(?:COLOR_[A-Z0-9_]+|ENDCOLOR)\]', chunk):
                depth += -1 if tag == '[ENDCOLOR]' else 1
                self.assertGreaterEqual(depth, 0)
            self.assertEqual(depth, 0)
            plain.append(re.sub(r'^\(\d+/\d+\) ', '', self.helper.StripColors(chunk)))
        self.assertEqual(''.join(plain), self.helper.StripColors(text))

    def test_short_message_unchanged(self):
        self.assertEqual(list(self.helper.Split('(TR) Hi', 240).values()), ['(TR) Hi'])

    def test_non_latin_letter_trigger_ignores_latin_symbols_and_icons(self):
        for text in ['Hello gg', 'bonjour café déjà vu', 'für Straße', 'zażółć gęślą', '123 + :)', '🦆 ❤️ → —', '[ICON_GOLD] [COLOR_RED]10[ENDCOLOR]', 'e\u0301']:
            self.assertFalse(self.helper.HasNonLatinLetters(text), text)
        for text in ['Привет', 'Привіт', '안녕하세요', '你好', '日本語', 'مرحبا', 'Ελλάδα', '[ICON_GOLD] 10 золота']:
            self.assertTrue(self.helper.HasNonLatinLetters(text), text)


if __name__ == '__main__':
    unittest.main()
