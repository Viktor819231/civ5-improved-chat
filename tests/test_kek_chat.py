"""The translator inside KEK Mod's own chat and lobby (tools/kek_skin.py).

KEK's files are not in this repository (it has no licence to copy them): these run
against analysis/kek-fixture, saved from github.com/OBLASTWAR/kek-mod, and skip
without it. Every in-game chat test also runs on KEK's chat, then KEK's own parts.
"""
import sys
import unittest
from pathlib import Path

import test_native_chat
from test_native_chat import CONTEXT, NativeChatTests, harness, load_source

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from chat_hooks import KEK_CHAT, patch_kek_chat, patch_kek_lobby  # noqa: E402

FIXTURE = ROOT / 'analysis/kek-fixture'

# What KEK's chat script needs from the game beyond the stock one.
KEK_GAME = r"""
ChatTargetTypes.CHATTARGET_ALL=ChatTargetTypes.CHATTARGET_ALL or 0
Stored={}
Network.SendEnhanceReligion=function(player,_,text,target,to) Stored[#Stored+1]={player=player,text=text,target=target,to=to} end
rawset(Chat,'GameInfo',{IconFontMapping=function() return function() return nil end end})
rawset(Chat,'InstanceManager',{new=function() return {GetInstance=function() return {Dummy=NewControl()} end} end})
rawset(Chat,'Modding',{OpenUserData=function() return {GetValue=function() return 0 end} end})
rawset(Chat.Game,'GetReplayMessages',function() return {} end)
rawset(Chat.Game,'GetElapsedGameTurns',function() return 12 end)
rawset(Chat.Game,'GetTurnTimeElapsed',function() return 34000 end)
rawset(Chat.PreGame,'GetGameOption',function() return 0 end)
"""


def kek_file(*parts):
    return (FIXTURE.joinpath(*parts)).read_bytes().decode('latin-1')


@unittest.skipUnless(FIXTURE.exists(), 'needs analysis/kek-fixture (KEK files from its GitHub)')
class KekEuiChatTests(NativeChatTests):
    CHAT = KEK_CHAT
    VARIANT = 'eui'

    def chat_script(self):
        return load_source(patch_kek_chat(kek_file('2.4', self.VARIANT, 'DiploCorner.lua'), 'test'), KEK_GAME)

    def stored(self):
        stored = self.g.Stored
        return [(stored[i].text, stored[i].target, stored[i].to) for i in range(1, len(stored) + 1)]

    def test_translated_messages_are_stored_in_the_game_like_keks_own(self):
        self.choose_send_language(1)
        self.press_enter('hello')
        self.complete('привет', 'en')
        self.tick(1)
        self.assertEqual(self.sent(), [('привет', -1, -1)])
        self.assertEqual(self.stored(), [('привет', 0, -1)])

    def test_a_private_translation_is_stored_as_private(self):
        self.choose_send_language(1)
        self.chat.OnChatTarget(-1, 2)
        self.press_enter('secret')
        self.complete('тайна', 'en')
        self.tick(1)
        self.assertEqual(self.stored(), [('тайна', self.g.ChatTargetTypes.CHATTARGET_PLAYER, 2)])

    def test_plain_messages_stay_keks_own_send(self):
        self.press_enter('gg')
        self.assertEqual(self.sent(), [('gg', -1, -1)])
        self.assertEqual(self.stored(), [('gg', 0, -1)])

    def test_long_translations_come_in_pieces_kek_can_store_whole(self):
        self.choose_send_language(1)
        self.press_enter('a long message')
        self.complete('привет мир ' * 30, 'en')
        for _ in range(12):  # one piece goes out per 0.8 s
            self.tick(1)
        pieces = self.sent()
        self.assertGreater(len(pieces), 1)
        for text, _, _ in pieces:
            self.assertLessEqual(len(text.encode('utf-8')), 127)
        self.assertEqual([text for text, _, _ in pieces], [text for text, _, _ in self.stored()])

    def test_rows_keep_keks_turn_and_time_also_from_the_save(self):
        row = self.incoming('Привет')
        self.assertEqual(row.Box.tooltip, 'T12, 34s')
        self.assertIn('T12, 34s', row.Hit.tooltip)
        self.chat.OnChat(1, -1, 'old line', 0, True, 7, 5000)
        self.assertIn('T7, 5s', self.rows()[-1].Hit.tooltip)

    def test_keks_desync_checks_never_reach_the_translator(self):
        before = len(self.rows())
        self.chat.OnChat(1, -1, '~~KS|12|3|abcdef', 0)
        self.assertEqual(len(self.rows()), before)
        self.assertEqual(self.requests(), [])

    def test_the_bar_leaves_keks_emote_button_free(self):
        self.assertEqual((self.c.ChatBar.x, self.c.ChatBar.y), (32, 3))
        self.assertEqual(self.gc.ChatEntry.width, 237)


class KekVanillaUiChatTests(KekEuiChatTests):
    VARIANT = 'ui'


@unittest.skipUnless(FIXTURE.exists(), 'needs analysis/kek-fixture (KEK files from its GitHub)')
class KekLobbyTests(unittest.TestCase):
    VERSION = '2.4'

    TRANSLATOR = '{C74FE31F-6834-496F-87DC-FB1C471B7FC8}'

    def lobby(self, packages=(TRANSLATOR,)):
        source = patch_kek_lobby(kek_file(self.VERSION, 'ui', 'StagingRoom.lua'), 'test')
        installed = 'Loaded={}\nrawset(Chat.ContextPtr,"LoadNewContext",function(_,name) Loaded[#Loaded+1]=name end)\n'
        installed += "rawset(Chat,'ContentManager',{GetAllPackageIDs=function() return {%s} end})\n" % ','.join(
            "'%s'" % p for p in packages)
        game = harness(CONTEXT + load_source(source, KEK_GAME + installed), lobby=True, packaged=True)
        self.addCleanup(game.tearDown)
        g = game.lua.globals()
        g.Chat.BuildPlayerNames()
        g.showhide(False, False)
        return g

    def test_the_lobby_loads_the_translator_only_when_it_is_installed(self):
        g = self.lobby()
        self.assertEqual(list(g.Loaded.values()), ['InGameTranslateLobby'])
        g = self.lobby(packages=('{B5932AE4-0F4F-498F-9333-E2D31B20E095}',))
        self.assertEqual(list(g.Loaded.values()), [])
        g = self.lobby(packages=())
        self.assertEqual(list(g.Loaded.values()), [])

    def test_hiding_the_lobby_brings_everything_home_first(self):
        g = self.lobby()
        for text in ['Привет', 'hello']:
            g.Chat.OnChat(1, -1, text, 0)
        rows = [g.Rows[i] for i in range(1, len(g.Rows) + 1)]
        self.assertTrue(any(row.tools for row in rows))
        g.Chat.ShowHideHandler(True, False)
        self.assertTrue(g.Controls.ChatBar.hidden)
        self.assertTrue(g.Same(g.Controls.ChatBar.parent, g.ContextPtr))
        self.assertTrue(all(row.Box.released and not row.tools for row in rows))

    def test_the_kick_popup_closing_leaves_the_bar_and_chat_in_place(self):
        g = self.lobby()
        g.Chat.OnChat(1, -1, 'Привет', 0)
        # KEK raises its flag before the popup; the rest of the kick needs real lobby slots.
        g.Chat.GetPlayerIDBySelectionIndex = lambda index: 1
        g.pcall(g.Chat.OnKickPlayer, 1)
        g.Chat.ShowHideHandler(True, False)
        self.assertFalse(g.Controls.ChatBar.hidden)
        self.assertTrue(g.Same(g.Controls.ChatBar.parent, g.Chat.Controls.ChatPanel))
        self.assertIsNone(g.rawget(g.Rows[len(g.Rows)].Box, 'released'))

    def test_keks_system_lines_get_no_translate_button(self):
        g = self.lobby()
        g.Chat.KekAddSystemChat('KEK Mod 2.4')
        rows = g.Rows
        self.assertIsNone(rows[len(rows)].tools)

    def test_a_hundred_lines_after_hiding_never_release_a_wiped_row(self):
        g = self.lobby()
        g.Chat.OnChat(1, -1, 'Привет', 0)
        g.Chat.KekAddSystemChat('system')
        g.Chat.ShowHideHandler(True, False)
        g.ShowLobby()
        # Both of KEK's writers drop the oldest line past 100, also a player's with a button.
        for i in range(100):
            g.Chat.OnChat(1, -1, 'line %d' % i, 0)
        for i in range(5):
            g.Chat.KekAddSystemChat('system %d' % i)
        for i in range(5):
            g.Chat.OnChat(1, -1, 'more %d' % i, 0)


class KekBetaLobbyTests(KekLobbyTests):
    VERSION = '2.5-beta15'


@unittest.skipUnless(FIXTURE.exists(), 'needs analysis/kek-fixture (KEK files from its GitHub)')
class KekPackageTests(unittest.TestCase):
    def installed_kek(self, variant='eui'):
        """A KEK folder as its ui_check leaves it next to EUI."""
        import tempfile
        root = Path(tempfile.mkdtemp())
        self.addCleanup(__import__('shutil').rmtree, root)
        kek = root / 'KEK Mod v2.4'
        (kek / 'UI').mkdir(parents=True)
        (kek / 'MPModsPack.Civ5Pkg').write_bytes((FIXTURE / '2.4/MPModsPack.Civ5Pkg').read_bytes())
        for name in ['DiploCorner.lua', 'DiploCorner.xml']:
            (kek / 'UI' / name).write_bytes((FIXTURE / '2.4' / variant / name).read_bytes())
        for name in ['StagingRoom.lua', 'StagingRoom.xml']:
            (kek / 'UI' / name).write_bytes((FIXTURE / '2.4/ui' / name).read_bytes())
        return kek

    def test_the_package_lives_inside_kek_and_outranks_it(self):
        import kek_skin
        from lupa.lua51 import LuaRuntime
        kek = self.installed_kek()
        before = {p: p.read_bytes() for p in kek.rglob('*') if p.is_file()}
        out = kek_skin.build(kek)
        self.assertEqual(out.parent, kek)
        self.assertEqual({p: p.read_bytes() for p in before}, before, 'KEK files must stay as they are')
        manifest = (out / 'ImprovedChatKEK.Civ5Pkg').read_text(encoding='utf-8')
        self.assertIn('<Priority>310</Priority>', manifest)
        lua = LuaRuntime()
        for name in ['DiploCorner.lua', 'StagingRoom.lua']:
            source = (out / 'Skin' / name).read_bytes().decode('latin-1')
            lua.execute('assert(loadstring(%s))' % test_native_chat.lua_string(source))
            self.assertIn('LuaEvents.IGT_', source)
        # KEK's lobby layout stays KEK's: its script loads the translator's part.
        self.assertFalse((out / 'Skin/StagingRoom.xml').exists())
        self.assertIn('"InGameTranslateLobby"', (out / 'Skin/StagingRoom.lua').read_text(encoding='latin-1'))
        # The chat script goes with the very layout KEK chose for it.
        self.assertEqual((out / 'Skin/DiploCorner.xml').read_bytes(), (kek / 'UI/DiploCorner.xml').read_bytes())
        kek_skin.remove(kek)
        self.assertFalse(out.exists())
        self.assertEqual({p: p.read_bytes() for p in kek.rglob('*') if p.is_file()}, before)

    def test_a_folder_without_keks_ui_set_up_is_refused(self):
        import kek_skin
        kek = self.installed_kek()
        (kek / 'UI/DiploCorner.lua').unlink()
        with self.assertRaises(SystemExit):
            kek_skin.build(kek)
        self.assertFalse((kek / kek_skin.FOLDER).exists())


if __name__ == '__main__':
    unittest.main()
