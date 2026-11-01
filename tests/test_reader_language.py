"""My language: translated overlay and chat, spam guard and request cleanup."""
import unittest
import test_game_ui


class ReaderLanguageTests(unittest.TestCase):
    def setUp(self):
        self.h=test_game_ui.GameUITests();self.h.setUp()
        self.lua,self.db=self.h.lua,self.h.db
        self.controls=self.lua.globals().Controls

    def tearDown(self):
        self.h.tearDown()

    def chat(self,text,sender=1):
        self.lua.globals().Events.GameMessageChat_handler(sender,-1,text,0)
        rows=self.lua.globals().Transcript
        return rows[len(rows)]

    def requests(self,kind=None):
        rows=[tuple(r) for r in self.db.execute('SELECT kind,source,target,text FROM requests ORDER BY id')]
        return [r for r in rows if kind is None or r[0]==kind]

    def test_russian_reader_gets_russian_window_and_foreign_chat_in_russian(self):
        self.h.select('Incoming',2)  # Русский
        self.assertEqual(self.controls.SendText.text,'Отправить')
        self.assertEqual(self.controls.Incoming.text,'Русский')
        self.assertEqual(self.controls.ForceHelp.text,'Перевести это сообщение на язык: Русский. Выберите язык сообщения:')
        self.assertEqual(self.db.execute("SELECT value FROM igt_state WHERE key='reader_language'").fetchone()[0],'ru')
        self.chat('Привет, как дела?')
        self.assertEqual(self.requests(),[])
        # Latin letters wait for a click, whatever the reader's language.
        row=self.chat('want peace?')
        self.assertEqual(self.requests(),[])
        self.assertEqual(row.TranslateLabel.text,'Перевести')
        row.TranslateButton.callback()
        self.assertEqual(self.requests(),[('incoming','auto','ru','want peace?')])
        self.h.complete('мир?','en')
        self.assertIn('(TR en>ru) P1: мир?',row.Message.text)
        self.assertEqual(row.TranslateLabel.text,'Оригинал')
        row.TranslateButton.callback()
        self.assertEqual(row.TranslateLabel.text,'Русский')
        self.assertIn('want peace?',row.Message.text)
        # Another alphabet is still translated automatically.
        self.chat('평화 ㄱㄱ?')
        self.assertEqual(self.requests()[-1],('auto','auto','ru','평화 ㄱㄱ?'))

    def test_latin_script_reader_translates_other_alphabets_only(self):
        self.h.select('Incoming',4)  # German
        self.chat('hallo, Frieden?')
        self.chat('hello, peace?')
        self.assertEqual(self.requests(),[])
        self.chat('Привет')
        self.assertEqual(self.requests(),[('auto','auto','de','Привет')])

    def test_game_language_is_the_default_and_an_explicit_choice_wins(self):
        self.lua.execute("Locale.GetCurrentLanguage=function() return {Type='ko_KR',DisplayName='Korean'} end")
        self.lua.globals().Events.GameplaySetActivePlayer_handler()
        self.assertEqual(self.controls.SendText.text,'보내기')
        self.assertEqual(self.controls.Target.text,'보낼 언어: 영어')
        self.chat('Привет')
        self.assertEqual(self.requests()[-1][2],'ko')
        self.chat('안녕 ㅋㅋ')
        self.assertEqual(len(self.requests()),1)
        self.h.select('Incoming',1)  # English
        self.lua.globals().Events.GameplaySetActivePlayer_handler()
        self.assertEqual(self.controls.SendText.text,'Send')

    def test_send_languages_are_remembered(self):
        self.h.select('Target',5)  # Russian (Latin letters)
        self.h.select('Source',3)  # Russian
        self.lua.globals().Events.GameplaySetActivePlayer_handler()
        self.assertEqual(self.controls.Target.text,'Send in: Russian (Latin letters)')
        self.assertEqual(self.controls.Source.text,'Russian')

    def test_spam_from_one_player_is_rationed_and_never_blocks_own_messages(self):
        rows=[self.chat('спам %d' % i) for i in range(10)]
        self.assertEqual(len(self.requests('auto')),4)
        self.assertIn('Many messages from P1',self.controls.ActionStatus.text)
        self.assertTrue(all(not row.TranslateButton.hidden for row in rows))
        self.chat('привет',sender=2)
        self.assertEqual(len(self.requests('auto')),5)
        self.h.click('SendMode');self.h.draft('hello');self.h.click('SendOriginal')
        self.assertEqual(self.requests('outgoing'),[('outgoing','auto','ru','hello')])
        self.chat('ещё спам')
        self.assertEqual(len(self.requests('auto')),5)
        self.h.tick(6.1)
        self.chat('и ещё')
        self.assertEqual(len(self.requests('auto')),6)
        self.chat('кто-то ещё',sender=2)
        self.assertEqual(len(self.requests('auto')),6)
        self.assertIn('Many messages at once',self.controls.ActionStatus.text)

    def test_repeated_spam_line_is_translated_once(self):
        first=self.chat('ГГ ИЗИ')
        second=self.chat('ГГ ИЗИ')
        self.assertEqual(len(self.requests()),1)
        self.h.complete('GG EZ','ru')
        self.assertIn('GG EZ',first.Message.text)
        for _ in range(8):row=self.chat('ГГ ИЗИ',sender=2)
        self.assertIn('(TR ru>en) P2: GG EZ',row.Message.text)
        second.TranslateButton.callback()
        self.assertIn('GG EZ',second.Message.text)
        self.assertEqual(len(self.requests()),1)

    def test_translation_limit_pauses_automatic_translation(self):
        self.chat('Привет')
        self.db.execute("UPDATE requests SET status='error',error='Translation allowance or request limit reached. Try later.'")
        self.h.tick()
        self.assertIn('paused for 5 minutes',self.controls.ActionStatus.text)
        self.chat('Как дела')
        self.assertEqual(len(self.requests()),1)
        self.h.tick(301)
        self.chat('Ну что')
        self.assertEqual(len(self.requests()),2)

    def test_finished_requests_are_read_once_and_old_sessions_cleared(self):
        self.chat('Привет')
        self.h.complete('Hello','ru')
        self.assertEqual(self.db.execute('SELECT status FROM requests').fetchone()[0],'seen')
        self.lua.globals().Events.GameplaySetActivePlayer_handler()
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)
        indexes=[r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='index'")]
        self.assertIn('igt_requests_session',indexes)

    def test_new_send_and_read_languages_are_offered(self):
        target=[e.text for e in self.controls.Target.entries.values()]
        reader=[e.text for e in self.controls.Incoming.entries.values()]
        for name in ['Russian (Latin letters)','Chinese','Japanese','German','Spanish','Polish','Turkish','Kazakh','Portuguese']:
            self.assertIn(name,target)
        self.assertNotIn('Arabic',target)
        self.assertEqual(reader,['English','Russian','Korean','German','French','Spanish','Italian','Polish','Japanese','Chinese'])


if __name__=='__main__':
    unittest.main()
