import unittest
import test_game_ui


class IncomingFilterTests(unittest.TestCase):
    def setUp(self):
        self.h=test_game_ui.GameUITests();self.h.setUp()
        self.lua,self.db=self.h.lua,self.h.db

    def tearDown(self):
        self.h.tearDown()

    def chat(self,text,own=False):
        self.lua.globals().Events.GameMessageChat_handler(0 if own else 1,-1,text,0)
        rows=self.lua.globals().Transcript
        return rows[len(rows)]

    def count(self):
        return self.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]

    def test_latin_emoji_and_icons_visible_without_translation_requests(self):
        for text in ['hello','bonjour café','[ICON_GOLD] 123','🦆 :)']:
            row=self.chat(text)
            self.assertIn(text,row.Message.text)
            self.assertFalse(row.TranslateButton.hidden)
        self.assertEqual(self.count(),0)

    def test_non_latin_translates_to_fixed_english_without_duplicate_requests(self):
        row=self.chat('[COLOR_CYAN]Привет[ENDCOLOR] [ICON_GOLD]')
        self.assertEqual(self.count(),1)
        self.assertEqual(self.db.execute('SELECT target FROM requests').fetchone()[0],'en')
        row.TranslateButton.callback()
        self.assertEqual(self.count(),1)
        self.h.complete('[COLOR_CYAN]Hello[ENDCOLOR] [ICON_GOLD]')
        self.assertIn('Hello',row.Message.text)
        row.TranslateButton.callback()
        self.assertIn('Привет',row.Message.text)
        row.TranslateButton.callback()
        self.assertIn('Hello',row.Message.text)
        self.assertEqual(self.count(),1)

    def test_latin_click_lets_service_detect_and_right_click_forces_language(self):
        row=self.chat('hola amigo')
        row.TranslateButton.callback()
        self.assertTrue(self.lua.globals().Controls.ForcePanel.hidden)
        request=self.db.execute('SELECT kind,source,target,text FROM requests').fetchone()
        self.assertEqual(tuple(request),('incoming','auto','en','hola amigo'))
        self.h.complete('hi friend','es')
        self.assertIn('(TR es>en) P1: hi friend',row.Message.text)
        row=self.chat('bonjour mon ami')
        row.TranslateButton.rightclick()
        self.assertFalse(self.lua.globals().Controls.ForcePanel.hidden)
        self.h.select('ForceSource',5)  # French
        self.h.click('ForceGo')
        request=self.db.execute('SELECT source,target,text FROM requests ORDER BY id DESC').fetchone()
        self.assertEqual(tuple(request),('fr','en','bonjour mon ami'))
        self.h.complete('Hello my friend','fr')
        self.assertIn('Hello my friend',row.Message.text)
        self.assertEqual(len(self.lua.globals().Sent),0)

    def test_manual_translation_works_with_automatic_receive_off(self):
        self.h.click('Receive')
        row=self.chat('Привет')
        self.assertEqual(self.count(),0)
        row.TranslateButton.callback()
        self.assertEqual(self.count(),1)

    def test_latinized_russian_is_manual_and_keeps_original_message(self):
        text='a kstati mogu vot tak pisat'
        row=self.chat(text)
        self.assertEqual(self.count(),0)
        row.TranslateButton.rightclick()
        self.h.select('ForceSource',2)
        self.h.click('ForceGo')
        request=self.db.execute('SELECT source,target,text FROM requests').fetchone()
        self.assertEqual(tuple(request),('ru-latn','en',text))
        self.h.complete('By the way, I can write like this.','ru')
        self.assertIn('By the way',row.Message.text)
        row.TranslateButton.callback()
        self.assertIn(text,row.Message.text)
        self.assertEqual(len(self.lua.globals().Sent),0)

    def test_translated_message_can_be_retried_as_latinized_russian(self):
        row=self.chat('privet drug')
        row.TranslateButton.callback()
        self.h.complete('Bad translation','ru')
        row.TranslateButton.rightclick()
        self.assertFalse(self.lua.globals().Controls.ForcePanel.hidden)
        self.h.select('ForceSource',2);self.h.click('ForceGo')
        self.assertEqual(self.db.execute('SELECT source FROM requests ORDER BY id DESC').fetchone()[0],'ru-latn')
        self.h.complete('Hello friend','ru')
        self.assertIn('Hello friend',row.Message.text)
        row.TranslateButton.callback()
        self.assertIn('privet drug',row.Message.text)

    def test_own_messages_never_trigger_incoming_translation(self):
        row=self.chat('Привет',own=True)
        self.assertEqual(self.count(),0)
        self.assertTrue(row.TranslateButton.hidden)

    def test_failed_request_allows_source_choice_and_retry(self):
        row=self.chat('你好')
        self.db.execute("UPDATE requests SET status='error',error='Choose source'")
        self.h.tick()
        row.TranslateButton.callback()
        self.assertFalse(self.lua.globals().Controls.ForcePanel.hidden)
        self.h.select('ForceSource',14)  # Chinese
        self.h.click('ForceGo')
        self.assertEqual(self.db.execute('SELECT source FROM requests ORDER BY id DESC LIMIT 1').fetchone()[0],'zh')
