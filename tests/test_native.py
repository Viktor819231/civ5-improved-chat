"""Real shared UI + cooperative Lua worker + independent authenticated server."""
import unittest
from Crypto.Cipher import AES
import test_game_ui
UI = test_game_ui.UI

class NativeUITests(unittest.TestCase):
    def setUp(self):
        self.host=test_game_ui.GameUITests();self.host.setUp()
        self.lua,self.db=self.host.lua,self.host.db
        self.calls=[];self.tamper=False;self.finish=True
        self.lua.globals().native_response=self.response
        self.lua.execute('''
Network.HttpRequest=function(options)
 local body=native_response(options.url);local n=native_count();local popped=false
 return {Finished=function()return native_finished(n)end,PopReceivedData=function()if not popped and native_finished(n) then popped=true;return body end;return '' end}
end
''')
        # Requests listed in self.lost never answer and never report finished, like the
        # one that stopped a real game's chat (2026-11-09).
        self.lost=set()
        self.lua.globals().native_count=lambda:len(self.calls)
        self.lua.globals().native_finished=lambda n:self.finish and n not in self.lost
        for name in ['IGT_Crypto.lua','IGT_Native.lua']:
            self.lua.execute((UI/name).read_text(encoding='utf-8'))
        source=(UI/'InGameTranslate.lua').read_text(encoding='utf-8').replace('IGT_Config = false; -- PERSONALIZED_DOWNLOAD_CONFIG', 'IGT_Config={id="00000000-0000-4000-8000-000000000001",key="'+'ab'*32+'",url="http://example.test"};')
        self.lua.execute(source)

    def tearDown(self):self.host.tearDown()

    def response(self,url):
        ident,seq,sealed=url.rsplit('/',3)[1:];sealed=bytes.fromhex(sealed)
        c=AES.new(bytes.fromhex('ab'*32),AES.MODE_SIV)
        for item in ['IGT-request/v1',ident,seq]:c.update(item.encode())
        plain=c.decrypt_and_verify(sealed[16:],sealed[:16]).decode()
        self.calls.append((seq,plain))
        c=AES.new(bytes.fromhex('ab'*32),AES.MODE_SIV)
        for item in [b'IGT-response/v1',ident.encode(),seq.encode(),sealed[:16]]:c.update(item)
        data,tag=c.encrypt_and_digest('ok\nen\nì•ˆë…•í•˜ì„¸ìš”'.encode())
        out=tag+data
        if self.tamper:out=bytes([out[0]^1])+out[1:]
        return out.hex()

    def ticks(self,count=300):
        for _ in range(count):self.host.tick(0.05)

    def test_default_enabled_encrypted_send_and_hidden_clipboard(self):
        self.host.draft('Hello');self.host.click('SendOriginal');self.ticks()
        self.assertEqual(len(self.calls),1)
        self.assertIn('Hello',self.calls[0][1]);self.assertEqual(len(self.lua.globals().Sent),1)
        self.assertIn('ì•ˆë…•í•˜ì„¸ìš”',self.lua.globals().Sent[1].text)
        self.assertTrue(self.lua.globals().Controls.Paste.hidden)
        self.assertTrue(self.lua.globals().Controls.CopyDraft.hidden)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)

    def test_tampering_and_disabling_cannot_send_original(self):
        self.tamper=True
        self.host.draft('Hello');self.host.click('SendOriginal');self.ticks()
        self.assertEqual(len(self.lua.globals().Sent),0)
        status,error=self.db.execute('SELECT status,error FROM native_requests').fetchone()
        self.assertEqual(status,'seen');self.assertTrue(error)
        self.host.draft('Another');self.host.click('SendOriginal');self.ticks(5)
        self.host.click('OnlineTranslation');self.ticks()
        self.assertEqual(len(self.lua.globals().Sent),0)

    def test_own_message_is_translated_before_automatic_incoming(self):
        self.lua.globals().Events.GameMessageChat_handler(1,-1,'Привет всем',0)
        self.host.draft('Hello');self.host.click('SendOriginal');self.ticks()
        self.assertEqual(len(self.calls),2)
        self.assertIn('Hello',self.calls[0][1]);self.assertIn('Привет всем',self.calls[1][1])

    def status(self):
        return [tuple(r) for r in self.db.execute('SELECT status,error FROM native_requests ORDER BY id')]

    def test_one_lost_answer_is_asked_again_and_chat_goes_on(self):
        # The real game: one answer never came and every later line said "Working" forever.
        self.lost={1}
        g=self.lua.globals()
        g.Events.GameMessageChat_handler(1,-1,'ну да',0);self.ticks(500)
        self.assertEqual([x[0] for x in self.calls],['1','2'])
        self.assertEqual(self.status()[0],('seen',''))
        g.Events.GameMessageChat_handler(1,-1,'у меня петраспот)',0)
        self.host.draft('Hello');self.host.click('SendOriginal');self.ticks()
        self.assertEqual([x[0] for x in self.calls],['1','2','3','4'])
        self.assertEqual(len(g.Sent),1)
        self.assertEqual([x[0] for x in self.status()],['seen','seen','seen'])

    def test_lost_answers_never_stop_the_queue_or_stack_requests(self):
        self.finish=False
        self.host.draft('Hello');self.host.click('Translate');self.ticks(450)
        self.assertEqual(len(self.calls),2)  # asked again once after 15 s
        self.ticks(450)
        self.assertEqual(self.status()[0],('seen','Translation service is unavailable. Try later.'))
        self.host.draft('Next');self.host.click('Translate');self.ticks(300)
        self.assertEqual(len(self.calls),2)  # two dead requests: wait, never a third
        self.ticks(400)
        self.assertEqual([x[0] for x in self.calls],['1','2','3'])  # the oldest expired after 60 s
        self.finish=True;self.ticks(300)
        self.assertEqual([x[0] for x in self.calls],['1','2','3'])
        self.assertEqual(len(self.lua.globals().Sent),0)


    def test_any_mod_keeps_the_translator_working(self):
        self.lua.execute("Modding.GetActivatedMods=function()return {{ID='any-gameplay-mod'}}end")
        self.host.draft('Hello');self.host.click('SendOriginal')
        self.host.tick(5)
        self.ticks()
        self.assertEqual(len(self.lua.globals().Sent),1)
        self.assertFalse(self.lua.globals().Controls.Toggle.disabled)
