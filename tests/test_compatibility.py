"""Improved Chat runs with any mod or DLC (user, 2026-11-08): nothing switches it off."""
import unittest
from pathlib import Path

from lupa.lua51 import LuaRuntime
import test_game_ui

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'DLC/InGameTranslateMod/UI/InGameTranslate.lua').read_text(encoding='utf-8')


class AnyModTests(unittest.TestCase):
    def test_no_mod_or_package_check_is_left(self):
        for name in ['UI/InGameTranslate.lua', 'UI/InGameTranslateLobby.lua']:
            source = (ROOT / 'DLC/InGameTranslateMod' / name).read_text(encoding='utf-8')
            self.assertNotIn('GetActivatedMods', source, name)
            self.assertNotIn('GetAllPackageIDs', source, name)

    def test_it_starts_with_any_mod_and_gameplay_package_active(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute("""
Controls=setmetatable({},{__index=function(t,k) local c={};rawset(t,k,c);return c end})
Modding={GetActivatedMods=function() return {{ID='any-gameplay-mod',Name='Vox Populi'}} end}
ContentManager={GetAllPackageIDs=function() return {'{unknown-modpack}'} end,IsActive=function() return true end}
ContentType={GAMEPLAY=1}
Included={}
function include(name) Included[#Included+1]=name; error('stop after the first helper') end
""")
        lua.globals().source = SOURCE
        ok, _ = lua.execute('return pcall(assert(loadstring(source)))')
        self.assertFalse(ok)
        # It got past where the old guard stopped it, to loading its helpers.
        self.assertEqual(lua.globals().Included[1], 'IGT_Text')

    def test_a_mod_turned_on_mid_game_changes_nothing(self):
        h = test_game_ui.GameUITests()
        h.setUp()
        try:
            h.draft('a' * 1000)
            h.click('SendOriginal')
            h.tick(.1)
            sent = len(h.lua.globals().Sent)
            h.lua.execute("Modding.GetActivatedMods=function()return {{ID='gameplay-mod'}}end")
            h.tick(5)
            self.assertGreater(len(h.lua.globals().Sent), sent)
            self.assertFalse(h.lua.globals().Controls.Toggle.disabled)
            h.lua.globals().Events.GameMessageChat_handler(1, -1, 'Привет', 0)
            self.assertEqual(h.db.execute("SELECT COUNT(*) FROM requests WHERE kind='auto'").fetchone()[0], 1)
        finally:
            h.tearDown()

    def test_the_lobby_opens_with_a_mod_active(self):
        h = test_game_ui.GameUITests()
        h.lobby = True
        h.setUp()
        try:
            h.lua.execute("Modding.GetActivatedMods=function()return {{ID='gameplay-mod'}}end")
            h.lua.globals().showhide(True, False)
            h.lua.globals().showhide(False, False)
            self.assertIsNotNone(h.db.execute("SELECT name FROM sqlite_master WHERE name='requests'").fetchone())
            self.assertFalse(h.lua.globals().Controls.Toggle.disabled)
        finally:
            h.tearDown()

    def test_package_layout_under_other_dlc(self):
        root = ROOT / 'DLC/InGameTranslateMod'
        # Above the game (0/100/200) and EUI (50/150/250); a mod with its own chat
        # script outranks it and gets the separate window.
        self.assertIn('<Priority>260</Priority>', (root / 'InGameTranslate_2.Civ5Pkg').read_text(encoding='utf-8'))
        self.assertIn('InGameTranslateLobby', (root / 'UI/StagingRoom.xml').read_text(encoding='utf-8'))
        self.assertIn('UI/InGameTranslate"', (root / 'Skin2/InGame.xml').read_text(encoding='utf-8'))
        self.assertIn('IGT_LobbyChatReady', (root / 'UI/StagingRoom.lua').read_text(encoding='latin-1'))
        self.assertFalse((root / 'UI/InGame.lua').exists())


if __name__ == '__main__':
    unittest.main()
