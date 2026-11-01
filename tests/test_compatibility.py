"""Vanilla guard runs before loading helpers, opening mailboxes or chat hooks."""
import unittest
from pathlib import Path

from lupa.lua51 import LuaRuntime
import test_game_ui

SOURCE = (Path(__file__).resolve().parents[1] / 'DLC/InGameTranslateMod/UI/InGameTranslate.lua').read_text(encoding='utf-8')
GUARD = SOURCE.split('include("IGT_Text");', 1)[0]


class CompatibilityTests(unittest.TestCase):
    def environment(self, setup=''):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute("""
Controls={Panel={},Toggle={}}
function Controls.Panel:SetHide(v) self.hidden=v end
function Controls.Toggle:SetHide(v) self.hidden=v end
function Controls.Toggle:SetDisabled(v) self.disabled=v end
function Controls.Toggle:SetToolTipString(v) self.tooltip=v end
Modding={GetActivatedMods=function()return {}end,OpenUserData=function()error('must not open database')end}
ContentManager={GetAllPackageIDs=function()return {}end,IsActive=function()return false end}
ContentType={GAMEPLAY=1}
function include(_)error('must not load helpers when unsupported')end
""")
        lua.execute(setup)
        return lua

    def test_stock_empty_mod_list_is_allowed(self):
        lua = self.environment()
        lua.execute(GUARD)
        self.assertIsNone(lua.globals().Controls.Toggle.disabled)

    def test_eui_and_official_expansions_are_allowed(self):
        lua = self.environment("""
Modding.GetActivatedMods=function()return {{ID='{570F793E-FC33-417F-AE19-7CECCCDD5F85}'}}end
ContentManager.GetAllPackageIDs=function()return {'{6DA07636-4123-4018-B643-6575B4EC336B}','{0E3751A1-F840-4E1B-9706-519BF484E59D}','{C74FE31F-6834-496F-87DC-FB1C471B7FC8}'}end
ContentManager.IsActive=function()return true end
""")
        lua.execute(GUARD)
        self.assertIsNone(lua.globals().Controls.Toggle.disabled)

    def test_unknown_active_mod_blocks_before_database_or_events(self):
        lua = self.environment("Modding.GetActivatedMods=function()return {{ID='other-mod',Name='EUI'}}end")
        lua.execute(SOURCE)
        self.assertTrue(lua.globals().Controls.Toggle.disabled)
        self.assertTrue(lua.globals().Controls.Toggle.hidden)
        self.assertTrue(lua.globals().Controls.Panel.hidden)
        self.assertIn('Unsupported active mod', lua.globals().Controls.Toggle.tooltip)

    def test_kek_mod_is_allowed(self):
        lua = self.environment("""
ContentManager.GetAllPackageIDs=function()return {'{B5932AE4-0F4F-498F-9333-E2D31B20E095}'}end
ContentManager.IsActive=function()return true end
""")
        lua.execute(GUARD)
        self.assertIsNone(lua.globals().Controls.Toggle.disabled)
        root = Path(__file__).resolve().parents[1] / 'DLC/InGameTranslateMod'
        lobby = (root / 'UI/InGameTranslateLobby.lua').read_text(encoding='utf-8')
        self.assertIn('b5932ae4-0f4f-498f-9333-e2d31b20e095', lobby)
        # Stay under KEK's priority so KEK's lobby screen remains the one in use.
        self.assertIn('<Priority>260</Priority>', (root / 'InGameTranslate_2.Civ5Pkg').read_text(encoding='utf-8'))
        self.assertIn('InGameTranslateLobby', (root / 'UI/StagingRoom.xml').read_text(encoding='utf-8'))
        self.assertIn('UI/InGameTranslate"', (root / 'Skin2/InGame.xml').read_text(encoding='utf-8'))
        self.assertFalse((root / 'UI/StagingRoom.lua').exists())
        self.assertFalse((root / 'UI/InGame.lua').exists())

    def test_active_unknown_gameplay_dlc_blocks_modpack(self):
        lua = self.environment("""
ContentManager.GetAllPackageIDs=function()return {'{unknown-modpack}'}end
ContentManager.IsActive=function(id,kind)assert(kind==1);return true end
""")
        lua.execute(SOURCE)
        self.assertTrue(lua.globals().Controls.Toggle.disabled)
        self.assertTrue(lua.globals().Controls.Toggle.hidden)
        self.assertIn('DLC/modpack', lua.globals().Controls.Toggle.tooltip)

    def test_unknown_ui_only_or_disabled_package_is_allowed(self):
        lua = self.environment("ContentManager.GetAllPackageIDs=function()return {'unknown-ui-package'}end")
        lua.execute(GUARD)
        self.assertIsNone(lua.globals().Controls.Toggle.disabled)

    def test_failed_detection_disables_safely(self):
        for setup in [
            'Modding.GetActivatedMods=nil',
            "Modding.GetActivatedMods=function()error('unsupported')end",
            'ContentManager=nil',
            "ContentManager.GetAllPackageIDs=function()return 'bad result'end",
        ]:
            with self.subTest(setup=setup):
                lua=self.environment(setup)
                lua.execute(SOURCE)
                self.assertTrue(lua.globals().Controls.Toggle.disabled)

    def test_detected_mod_cancels_remaining_chat_parts(self):
        h=test_game_ui.GameUITests()
        h.setUp()
        try:
            h.draft('a'*1000)
            h.click('SendOriginal')
            h.tick(.1)
            self.assertEqual(len(h.lua.globals().Sent),1)
            h.lua.execute("Modding.GetActivatedMods=function()return {{ID='gameplay-mod'}}end")
            h.tick(5)
            self.assertEqual(len(h.lua.globals().Sent),1)
            self.assertTrue(h.lua.globals().Controls.Toggle.disabled)
            self.assertTrue(h.lua.globals().Controls.Toggle.hidden)
            h.lua.globals().Events.GameMessageChat_handler(1,-1,'Привет',0)
            self.assertEqual(h.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)
        finally:
            h.tearDown()

    def test_preloaded_lobby_rechecks_before_opening_mailbox(self):
        h=test_game_ui.GameUITests()
        h.lobby=True
        h.setUp()
        try:
            h.lua.execute("Modding.GetActivatedMods=function()return {{ID='gameplay-mod'}}end")
            h.lua.globals().showhide(False,False)
            self.assertIsNone(h.db.execute("SELECT name FROM sqlite_master WHERE name='requests'").fetchone())
            h.lua.globals().showhide(True,False)
            h.lua.globals().showhide(False,False)
            self.assertFalse(h.lua.globals().input(1,27))
            self.assertTrue(h.lua.globals().Controls.Toggle.disabled)
            self.assertTrue(h.lua.globals().Controls.Toggle.hidden)
        finally:
            h.tearDown()


if __name__ == '__main__':
    unittest.main()
