"""The translator working inside the game's own chat.

These tests run the real generated chat scripts (the stock Firaxis Lua plus the
hook) next to the real translator, each with its own Controls like two contexts.
What they cannot prove is how Civ V draws it: that needs a look in the game.
"""
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from lupa.lua51 import LuaRuntime

import test_game_ui

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from chat_hooks import GAME_CHAT, LOBBY_CHAT, patch_chat, patch_lobby  # noqa: E402

GAME = Path("C:/Program Files (x86)/Steam/steamapps/common/Sid Meier's Civilization V")
DLC = ROOT / 'DLC/InGameTranslateMod'
CHAT_SCRIPT = DLC / 'Skin2/DiploCorner.lua'
LOBBY_SCRIPT = DLC / 'UI/StagingRoom.lua'

# A second context, as Civ V gives every screen: its own Controls and ContextPtr,
# and anything the test does not care about answers harmlessly.
CONTEXT = r"""
function Same(a,b) return rawequal(a,b) end
function HoldsNothing(box) return next(rawget(box,'kids') or {})==nil end
-- The hook is the handler's first line; what follows builds lobby slots this test has no data for.
function ShowLobby() pcall(Chat.ShowHideHandler,false,false) end
LuaEvents.IGT_GameChatReady.Add(function(hook) GameHook=hook end)
function MakeContext(rows)
 local anything
 anything=setmetatable({},{__index=function() return anything end,__call=function() return anything end,
  __concat=function(a,b) return tostring(a=='' and b or a) end,__lt=function() return false end,__le=function() return false end})
 local controls=setmetatable({},{__index=function(t,k) local c=NewControl();rawset(t,k,c);return c end})
 local env=setmetatable({},{__index=function(_,k) local v=_G[k];if v==nil then return anything end;return v end})
 env.Controls=controls
 env.ContextPtr=setmetatable({},{__index=function() return function() return anything end end})
 env.ContextPtr.IsHidden=function() return false end
 env.ContextPtr.SetShutdown=function(_,fn) env.Shutdown=fn end
 env.ContextPtr.BuildInstanceForControl=function(_,name,row,parent)
  row.Box=NewControl();row.String=NewControl();row.name=name;rows[#rows+1]=row
  row.String.SetColorByName=function(s,c) s.color=c end
 end
 -- What the real game must never see: a row destroyed with a translator control inside.
 local function destroy(box)
  assert(HoldsNothing(box),'the game destroyed a row holding a translator control')
  assert(not rawget(box,'released'),'the game released a row that was already gone')
  box.released=true
 end
 controls.ChatStack.ReleaseChild=function(_,box) destroy(box) end
 controls.ChatStack.DestroyAllChildren=function()
  for _,row in ipairs(rows) do if not rawget(row.Box,'released') then destroy(row.Box) end end
 end
 controls.ChatEntry.ClearString=function(s) s.text='' end
 controls.ChatEntry.GetSizeX=function() return 364 end
 controls.ChatPull.GetSizeX=function() return 136 end
 controls.ChatPull.BuildEntry=function(_,_,entry)
  entry.Button=NewControl();entry.Button.GetTextControl=function() return NewControl() end
 end
 env.Events=setmetatable({},{__index=function(t,k)
  local e=setmetatable({Add=function() end},{__call=function() end});rawset(t,k,e);return e end})
 env.include=function() end
 env.TruncateString=function(c,_,text) c:SetText(text) end
 env.Game=setmetatable({IsGameMultiPlayer=function() return true end,IsHotSeat=function() return false end,GetNumActiveLeagues=function() return 0 end},{__index=function(_,k) return Game[k] or anything end})
 env.Players=setmetatable({},{__index=function(_,id)
  local player=Players[id]
  return setmetatable({},{__index=function(_,k) return player[k] or function() return 0 end end})
 end})
 env.Teams=anything
 env.UIManager=setmetatable({},{__index=function(_,k) return UIManager[k] or function() return anything end end})
 env.Matchmaking=setmetatable({},{__index=function(_,k) return Matchmaking[k] or anything end})
 env.Modding=setmetatable({},{__index=function(_,k) return Modding[k] or anything end})
 env.PreGame=setmetatable({IsInternetGame=function() return false end},{__index=function(_,k) return PreGame[k] or anything end})
 return env
end
"""


def load_script(path, setup=''):
    return load_source(path.read_bytes().decode('latin-1'), setup)


def load_source(source, setup=''):
    # The stock file is plain Lua 5.1: load it as the game does. `setup` adds what
    # a mod's copy needs from the game before its first line runs.
    return '\n'.join(['do', 'Rows={}', 'Chat=MakeContext(Rows)', setup,
                      'local fn=assert(loadstring(%s))' % lua_string(source), 'setfenv(fn,Chat)', 'fn()', 'end'])


def lua_string(text):
    level = '=' * 8
    return '[' + level + '[\n' + text + ']' + level + ']'


def harness(before='', lobby=False, packaged=False):
    """The real translator in the shared test game, without the overlay's own tests."""
    class Harness(test_game_ui.GameUITests):
        pass
    Harness.before_engine, Harness.lobby, Harness.packaged = before, lobby, packaged
    game = Harness()
    game.setUp()
    return game


@unittest.skipUnless(CHAT_SCRIPT.exists(), 'run tools/build_package.py --generate-only first')
class NativeChatTests(unittest.TestCase):
    CHAT = GAME_CHAT

    def chat_script(self):
        return load_script(CHAT_SCRIPT)

    def setUp(self):
        self.game = harness(CONTEXT + self.chat_script())
        self.lua, self.db = self.game.lua, self.game.db
        self.complete, self.tick = self.game.complete, self.game.tick
        self.g = self.lua.globals()
        self.chat = self.g.Chat
        self.c = self.g.Controls
        self.gc = self.chat.Controls

    def tearDown(self):
        self.game.tearDown()

    def rows(self):
        rows = self.g.Rows
        return [rows[i] for i in range(1, len(rows) + 1)]

    def incoming(self, text, sender=1, to=-1, kind=0):
        self.chat.OnChat(sender, to, text, kind)
        return self.rows()[-1]

    def press_enter(self, text):
        self.gc.ChatEntry.SetText(self.gc.ChatEntry, text)
        self.chat.SendChat(text)

    def requests(self):
        return [tuple(r) for r in self.db.execute('SELECT kind,target,text FROM requests ORDER BY id')]

    def sent(self):
        sent = self.g.Sent
        return [(sent[i].text, sent[i].team, sent[i].player) for i in range(1, len(sent) + 1)]

    def choose_send_language(self, code_index):
        self.c.SendLanguage.selection(code_index)

    def test_the_overlay_steps_aside_for_the_games_chat(self):
        self.assertTrue(self.c.Toggle.hidden)
        self.assertTrue(self.c.Panel.hidden)
        self.assertFalse(self.c.ChatBar.hidden)
        self.assertEqual(self.gc.ChatEntry.width, self.CHAT['entry'])
        self.assertEqual(self.gc.ChatEntry.anchor, 'L,C')
        # The game's chat stays plain until a language is picked.
        self.assertEqual(self.c.SendLanguage.text, 'TR: -')

    def test_plain_chat_is_exactly_the_games(self):
        self.press_enter('gg wp')
        self.assertEqual(self.sent(), [('gg wp', -1, -1)])
        self.assertEqual(self.requests(), [])
        self.assertEqual(self.gc.ChatEntry.text, '')
        row = self.incoming('gg wp', sender=0)
        self.assertEqual(row.String.text, 'P0: gg wp')
        self.assertEqual(row.String.color, 'Gray_Chat')

    def test_foreign_message_is_translated_on_the_games_own_row(self):
        row = self.incoming('Привет всем')
        self.assertEqual(row.String.text, 'P1: Привет всем')
        self.assertEqual(self.requests(), [('auto', 'en', 'Привет всем')])
        self.complete('Hello everyone', 'ru')
        self.assertEqual(row.String.text, '(TR ru>en) P1: Hello everyone')
        self.assertIn('Original: Привет всем', row.Hit.tooltip)
        self.assertEqual(row.TranslateLabel.text, '<')
        row.TranslateButton.callback()
        self.assertEqual(row.String.text, 'P1: Привет всем')
        self.assertEqual(row.TranslateLabel.text, 'T')

    def test_whisper_keeps_the_games_wording_and_colour(self):
        self.lua.execute("Locale.ConvertTextKey=function(s,a) return s=='TXT_KEY_YOU' and 'You' or s end")
        row = self.incoming('Привет', to=0, kind=2)
        self.assertEqual(row.String.text, 'P1 (You): Привет')
        self.complete('Hello', 'ru')
        self.assertEqual(row.String.text, '(TR ru>en) P1 (You): Hello')
        self.assertEqual(row.String.color, 'Magenta_Chat')

    def test_latin_message_waits_for_the_small_button(self):
        row = self.incoming('hola amigos')
        self.assertEqual(self.requests(), [])
        self.assertFalse(row.TranslateButton.hidden)
        self.assertEqual(row.TranslateLabel.text, 'T')
        row.TranslateButton.callback()
        self.assertEqual(self.requests(), [('incoming', 'en', 'hola amigos')])
        self.assertEqual(row.TranslateLabel.text, '..')
        self.complete('hello friends', 'es')
        self.assertEqual(row.String.text, '(TR es>en) P1: hello friends')

    def test_own_row_gets_no_translate_button(self):
        row = self.incoming('hello', sender=0)
        self.assertIsNone(row.Hit)

    def test_translated_send_uses_the_games_box_and_its_own_row(self):
        self.choose_send_language(1)  # Russian
        self.assertEqual(self.c.SendLanguage.text, 'TR: RU')
        self.press_enter('hello')
        self.assertEqual(self.gc.ChatEntry.text, '')
        self.assertEqual(self.sent(), [])
        self.assertEqual(self.requests(), [('outgoing', 'ru', 'hello')])
        row = self.rows()[-1]
        self.assertEqual(row.String.text, 'You -> ru: hello (Working...)')
        self.complete('привет', 'en')
        self.tick(1)
        self.assertEqual(self.sent(), [('привет', -1, -1)])
        self.assertEqual(row.String.text, 'You -> ru: hello')
        echo = self.incoming('привет', sender=0)
        self.assertTrue(echo.Box.hidden)
        self.assertIsNot(echo, row)

    def test_chosen_recipient_and_team_of_the_games_list_are_used(self):
        self.choose_send_language(1)
        self.chat.OnChatTarget(-1, 2)
        self.press_enter('secret')
        self.assertEqual(self.rows()[-1].String.color, 'Magenta_Chat')
        self.complete('тайна', 'en')
        self.tick(1)
        self.chat.OnChatTarget(5, -1)
        self.press_enter('team plan')
        self.complete('план', 'en')
        self.tick(1)
        self.assertEqual(self.sent(), [('тайна', -1, 2), ('план', 5, -1)])

    def test_failed_translation_says_so_and_sends_nothing(self):
        self.choose_send_language(1)
        self.press_enter('hello')
        row = self.rows()[-1]
        self.db.execute("UPDATE requests SET status='error',error='Translation service is unavailable. Try later.'")
        self.tick()
        self.assertIn('Not sent: hello', row.String.text)
        self.assertEqual(self.sent(), [])

    def test_offline_keeps_the_typed_text_and_tells_why(self):
        self.choose_send_language(1)
        self.db.execute("INSERT OR REPLACE INTO igt_state VALUES('online_translation_enabled','0')")
        self.press_enter('hello')
        self.assertEqual(self.gc.ChatEntry.text, 'hello')
        self.assertIn('Not sent: hello', self.rows()[-1].String.text)
        self.assertEqual(self.sent(), [])

    def test_a_row_the_game_dropped_is_never_touched(self):
        first = self.incoming('Привет всем')
        for i in range(100):
            self.incoming('line %d' % i)
        self.assertTrue(first.Box.released)
        self.assertTrue(first.igtGone)
        first.String.text = 'untouched'
        self.complete('Hello everyone', 'ru')
        self.assertEqual(first.String.text, 'untouched')

    def test_buttons_are_recycled_and_never_die_with_a_row(self):
        for i in range(250):
            self.incoming('line %d' % i)
        self.assertLessEqual(self.g.ToolsBuilt, 101)
        row = self.rows()[-1]
        self.assertTrue(self.g.Same(row.Hit.parent, row.Box))
        self.assertEqual(row.TranslateLabel.text, 'T')
        row.TranslateButton.callback()
        self.assertEqual(self.requests()[-1][2], 'line 249')
        self.complete('Line 249', 'ru')
        self.assertEqual(row.TranslateLabel.text, '<')

    def assert_everything_is_home(self, rows):
        self.assertTrue(self.g.Same(self.c.ChatBar.parent, self.g.ContextPtr))
        self.assertTrue(self.c.ChatBar.hidden)
        for row in rows:
            self.assertTrue(self.g.HoldsNothing(row.Box))
        for name in ['OnRow', 'OnSend', 'OnRowGone', 'OnShutdown']:
            self.assertIsNone(self.g.GameHook[name])

    def test_everything_comes_home_when_the_game_closes_its_chat(self):
        self.incoming('Привет всем')
        self.incoming('hello')
        rows = self.rows()
        self.chat.Shutdown()
        self.assert_everything_is_home(rows)

    def test_everything_comes_home_when_the_translator_closes_first(self):
        self.incoming('Привет всем')
        rows = self.rows()
        self.assertTrue(self.g.GameHook.Taken)
        self.g.shutdown()
        self.assert_everything_is_home(rows)
        # A translator loaded later may take the chat again.
        self.assertIsNone(self.g.GameHook.Taken)
        # The game's chat keeps working on its own until it closes too.
        self.assertEqual(self.incoming('later').String.text, 'P1: later')
        self.chat.Shutdown()

    def test_a_late_answer_touches_nothing_after_closing(self):
        row = self.incoming('Привет всем')
        self.chat.Shutdown()
        self.g.shutdown()
        row.String.text = 'untouched'
        self.complete('Hello everyone', 'ru')
        self.assertEqual(row.String.text, 'untouched')

    def test_translator_rows_are_the_games_rows_and_share_its_limit(self):
        self.choose_send_language(1)
        self.press_enter('one')
        mine = self.rows()[-1]
        self.assertEqual(mine.name, 'ChatEntry')
        for i in range(100):
            self.incoming('line %d' % i)
        self.assertTrue(mine.Box.released)

    def test_settings_window_opens_from_the_chat_and_has_no_chat_page(self):
        self.c.ChatSettings.callback()
        self.assertFalse(self.c.Panel.hidden)
        self.assertFalse(self.c.Settings.hidden)
        self.assertTrue(self.c.ChatPage.hidden)
        self.assertTrue(self.c.ChatTab.hidden)
        self.c.CloseSettings.callback()
        self.assertTrue(self.c.Panel.hidden)
        self.assertTrue(self.c.Toggle.hidden)

    def test_icon_goes_into_the_games_box(self):
        self.gc.ChatEntry.SetText(self.gc.ChatEntry, 'gold')
        self.c.EmojiGold.callback()
        self.assertIn('[ICON_GOLD]', self.gc.ChatEntry.text)

    def test_send_choice_is_remembered_and_off_is_the_default(self):
        self.choose_send_language(3)
        saved = self.db.execute("SELECT value FROM igt_state WHERE key='send_translate'").fetchone()[0]
        self.assertEqual(saved, '1')
        self.choose_send_language(0)
        self.assertEqual(self.c.SendLanguage.text, 'TR: -')
        self.press_enter('plain again')
        self.assertEqual(self.sent(), [('plain again', -1, -1)])

    def test_any_mod_leaves_the_chat_hooked(self):
        self.lua.execute("Modding.GetActivatedMods=function() return {{ID='any-gameplay-mod'}} end")
        self.tick(6)
        self.assertFalse(self.c.ChatBar.hidden)
        self.assertEqual(self.gc.ChatEntry.width, self.CHAT['entry'])
        self.incoming('Привет')
        self.assertEqual(self.requests(), [('auto', 'en', 'Привет')])


class OverlayFallbackTests(unittest.TestCase):
    """No hook in the game's chat script: everything stays the separate window."""

    def setUp(self):
        self.game = harness()
        self.lua = self.game.lua

    def tearDown(self):
        self.game.tearDown()

    def test_window_stays_when_nothing_answers(self):
        g = self.lua.globals()
        self.assertTrue(g.Controls.ChatBar.hidden)
        rows = len(g.Transcript)
        g.Events.GameMessageChat_handler(1, -1, 'hello', 0)
        self.assertEqual(len(g.Transcript), rows + 1)

    def test_a_shut_down_screen_is_not_used(self):
        self.lua.execute("""
LuaEvents.IGT_GameChatReady({Dead=true,Controls={}})
""")
        self.assertTrue(self.lua.globals().Controls.ChatBar.hidden)

    def test_a_chat_another_copy_works_in_switches_this_copy_off(self):
        self.lua.execute("""
LuaEvents.IGT_GameChatReady({Taken=true,Controls={}})
""")
        g = self.lua.globals()
        self.assertTrue(g.Controls.ChatBar.hidden)
        self.assertTrue(g.Controls.Toggle.hidden)
        self.assertTrue(g.Controls.Toggle.disabled)
        g.Events.GameMessageChat_handler(1, -1, 'Привет', 0)
        self.assertEqual(self.game.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 0)

    def test_a_hook_that_fails_leaves_the_window_working(self):
        self.lua.execute("""
Hook={Controls={ChatEntry=NewControl(),ChatStack=NewControl(),ChatScroll=NewControl(),ChatPanel=nil},EntryAnchor='C,C',EntrySize=364,BarX=7,BarY=3,EntryWidth=262,RowPadding=8}
Controls.ChatBar.ChangeParent=function() error('no such parent') end
LuaEvents.IGT_GameChatReady(Hook)
""")
        controls = self.lua.globals().Controls
        self.assertTrue(controls.ChatBar.hidden)
        self.assertFalse(controls.Toggle.hidden)
        self.assertIsNone(self.lua.globals().Hook.OnSend)
        self.game.draft('still the overlay')
        self.game.click('SendOriginal')
        self.assertEqual(controls.Draft.text, '')


@unittest.skipUnless(LOBBY_SCRIPT.exists(), 'run tools/build_package.py --generate-only first')
class LobbyChatTests(unittest.TestCase):
    HOOK = CONTEXT + r"""
Hook={Controls=setmetatable({},{__index=function(t,k) local c=NewControl();rawset(t,k,c);return c end}),RowPadding=15,BarX=0,BarY=0,EntryWidth=561,EntryAnchor='L,C',EntrySize=825,OwnRecipient=true}
HookRows={}
Hook.NewRow=function() local row={Box=NewControl(),String=NewControl()};HookRows[#HookRows+1]=row;return row end
LuaEvents.IGT_LobbyChatHello.Add(function() LuaEvents.IGT_LobbyChatReady(Hook) end)
"""

    def setUp(self):
        self.game = harness(self.HOOK, lobby=True, packaged=True)
        self.lua, self.db = self.game.lua, self.game.db
        self.complete, self.tick, self.select = self.game.complete, self.game.tick, self.game.select

    def tearDown(self):
        self.game.tearDown()

    def test_lobby_row_is_translated_in_place_and_join_lines_are_left_alone(self):
        g = self.lua.globals()
        g.showhide(False, False)
        hook = g.Hook
        row = self.lua.eval("{Box=NewControl(),String=NewControl()}")
        row.String.text = 'LobbyP1: Привет'
        hook.OnRow(row, 1, -1, 'Привет', 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 1)
        self.complete('Hello', 'ru')
        self.assertEqual(row.String.text, '(TR ru>en) LobbyP1: Hello')
        joined = self.lua.eval("{Box=NewControl(),String=NewControl()}")
        joined.String.text = 'LobbyP1: Подключился'
        hook.OnRow(joined, 1, -1, 'Подключился', None)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 1)

    def test_lobby_whisper_comes_from_the_bar(self):
        g = self.lua.globals()
        g.showhide(False, False)
        hook = g.Hook
        self.assertEqual(g.Controls.ChatBar.width, 262)
        self.assertFalse(hook.OnSend('plain', -1, -1))
        self.select('Recipient', 1)
        self.assertTrue(hook.OnSend('psst', -1, -1))
        self.tick(1)
        sent = g.Sent
        self.assertEqual((sent[1].text, sent[1].player), ('psst', 1))


@unittest.skipUnless((GAME / 'Assets').exists(), 'needs an installed Civ V')
class HookTextTests(unittest.TestCase):
    def stock(self, relative):
        return (GAME / 'Assets' / relative).read_bytes().decode('latin-1')

    def test_every_game_version_takes_the_hook_and_changes_nothing_else(self):
        for relative in ['UI/InGame/WorldView/DiploCorner.lua', 'DLC/Expansion/UI/InGame/WorldView/DiploCorner.lua',
                         'DLC/Expansion2/UI/InGame/WorldView/DiploCorner.lua']:
            stock = self.stock(relative)
            patched = patch_chat(stock, GAME_CHAT, relative)
            self.assertIn('IGT_GameChatReady( g_IGT )', patched)
            lines = {line.strip() for line in patched.splitlines()}
            self.assertEqual([l for l in stock.splitlines() if l.strip() not in lines], [])

    def test_the_lobby_takes_the_hook(self):
        patched = patch_lobby(self.stock('UI/FrontEnd/Multiplayer/StagingRoom.lua'), 'StagingRoom.lua')
        self.assertIn('IGT_LobbyChatReady( g_IGT )', patched)
        self.assertIn('row.igtGone = true', patched)

    def test_a_moved_line_stops_the_build(self):
        stock = self.stock('DLC/Expansion2/UI/InGame/WorldView/DiploCorner.lua')
        with self.assertRaises(SystemExit):
            patch_chat(stock.replace('function SendChat( text )', 'function SendChat(text)'), GAME_CHAT, 'test')

    def test_every_generated_script_compiles(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        compile_lua = lua.eval('function(text) local fn, err = loadstring(text); return err or "ok" end')
        for path in [*DLC.glob('Skin*/DiploCorner.lua'), DLC / 'UI/StagingRoom.lua', DLC / 'UI/InGameTranslateLobby.lua']:
            self.assertEqual(compile_lua(path.read_bytes().decode('latin-1')), 'ok', path)

    def test_the_real_lobby_script_shakes_hands_with_the_translator(self):
        game = harness(CONTEXT + load_script(LOBBY_SCRIPT), lobby=True, packaged=True)
        self.addCleanup(game.tearDown)
        g = game.lua.globals()
        self.assertFalse(g.Controls.ChatBar.hidden)
        self.assertEqual(g.Chat.Controls.ChatEntry.width, LOBBY_CHAT['entry'])

    def real_lobby(self):
        game = harness(CONTEXT + load_script(LOBBY_SCRIPT), lobby=True, packaged=True)
        self.addCleanup(game.tearDown)
        g = game.lua.globals()
        g.Chat.BuildPlayerNames()
        g.showhide(False, False)
        return g

    def test_hiding_the_lobby_brings_everything_home_first(self):
        g = self.real_lobby()
        for text in ['Привет', 'hello']:
            g.Chat.OnChat(1, -1, text, 0)
        rows = [g.Rows[i] for i in range(1, len(g.Rows) + 1)]
        self.assertTrue(any(row.tools for row in rows))
        g.Chat.ShowHideHandler(True, False)
        self.assertTrue(g.Same(g.Controls.ChatBar.parent, g.ContextPtr))
        self.assertTrue(all(row.Box.released and not row.tools for row in rows))
        g.ShowLobby()
        self.assertTrue(g.Same(g.Controls.ChatBar.parent, g.Chat.Controls.ChatPanel))
        self.assertFalse(g.Controls.ChatBar.hidden)

    def test_a_hundred_lines_after_hiding_never_release_a_wiped_row(self):
        g = self.real_lobby()
        g.Chat.OnChat(1, -1, 'before', 0)
        g.Chat.ShowHideHandler(True, False)
        g.ShowLobby()
        for i in range(120):
            g.Chat.OnChat(1, -1, 'line %d' % i, 0)

    def test_no_eui_code_is_shipped(self):
        names = [p.name for p in DLC.rglob('*') if p.is_file()]
        self.assertNotIn('NotificationPanel.lua', names)
        self.assertNotIn('DiploCorner.xml', names)
        for path in [*DLC.glob('Skin*/DiploCorner.lua'), DLC / 'UI/StagingRoom.lua']:
            self.assertNotIn('EUI', path.read_bytes().decode('latin-1'))


class ChatBarLayoutTests(unittest.TestCase):
    def test_the_send_menu_list_is_wide_enough_for_its_names(self):
        # The game draws an AutoSizePopUp="1" list exactly as wide as its button (its
        # own chat menu cuts names to ChatPull:GetSizeX()); the TR button is 72 px.
        for name in ['InGameTranslate.xml', 'InGameTranslateLobby.xml']:
            menu = ET.parse(DLC / 'UI' / name).find(".//PullDown[@ID='SendLanguage']")
            self.assertEqual(menu.get('AutoSizePopUp'), '0', name)
            entry = int(menu.find('InstanceData/GridButton').get('Size').split(',')[0])
            panel = int(menu.find('ScrollPanelData').get('Size').split(',')[0])
            self.assertGreaterEqual(panel, entry, name)
            self.assertEqual(menu.find('GridData').get('AutoSize'), '1', name)


if __name__ == '__main__':
    unittest.main()
