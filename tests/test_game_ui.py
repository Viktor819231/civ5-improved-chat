"""Run the real addon against Lua 5.1, SQLite, and recorded Civ UI calls."""
import sqlite3
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from lupa.lua51 import LuaRuntime


UI = Path(__file__).resolve().parents[1] / "DLC/InGameTranslateMod/UI"


class GameUITests(unittest.TestCase):
    lobby = False
    packaged = False
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.db.row_factory = sqlite3.Row

        def sql(query):
            rows = self.db.execute(query).fetchall()
            return self.lua.table_from([self.lua.table_from(dict(row)) for row in rows])

        self.lua.globals().sql = sql
        self.lua.execute("""
local function control()
 local c={text='',hidden=true,disabled=false}
 function c:SetText(t) self.text=t end
 function c:GetText() return self.text end
 function c:SetHide(v) self.hidden=v end
 function c:IsHidden() return self.hidden end
 function c:IsTrackingLeftMouseButton() return self.tracking==true end
 function c:SetDisabled(v) self.disabled=v end
 function c:SetColorByName(v) self.color=v end
 function c:SetToolTipString(v) self.tooltip=v end
 function c:RegisterCallback(a,b) if a==2 and b then self.rightclick=b elseif a==3 and b then self.doubleclick=b else self.callback=b or a end end
 function c:GetButton() return self end
 function c:ClearEntries() self.entries={} end
 function c:BuildEntry(_,entry) entry.Button=control();self.entries[#self.entries+1]=entry.Button end
 function c:SetVoid1(id) self.value=id end
 function c:RegisterSelectionCallback(fn) self.selection=fn end
 function c:RegisterSliderCallback(fn) self.slider=fn end
 function c:SetValue(v) self.value=v end
 function c:GetSizeY() return rawget(self,'height') or 22 end
 function c:SetSizeY(h) self.height=h end
 function c:SetSizeX(w) self.width=w end
 function c:SetSizeVal(w,h) self.width=w;self.height=h end
 function c:SetAnchor(a) self.anchor=a end
 function c:SetAlpha(a) self.alpha=a end
 function c:SetWrapWidth(w) self.wrap=w end
 function c:SetOffsetVal(x,y) self.x=x;self.y=y end
 setmetatable(c,{__index=function(_,k) return function() end end})
 return c
end
Controls=setmetatable({},{__index=function(t,k) local c=control();rawset(t,k,c); return c end})
ContextPtr={}; Transcript={}
UIManager={GetScreenSizeVal=function() return 1280,900 end}
MouseX,MouseY=0,0
function UIManager:GetMousePos() return MouseX,MouseY end
MouseEvents={LButtonDown=20,LButtonUp=21,MouseMove=22,LButtonDoubleClick=23}
function ContextPtr:BuildInstanceForControl(_,row,_)
 row.Message=control();row.Box=control();row.TranslateButton=control();row.TranslateLabel=control();Transcript[#Transcript+1]=row
end
function ContextPtr:SetInputHandler(fn,...) assert(select('#',...)==0,'Civ V SetInputHandler only accepts one handler');input=fn end
function ContextPtr:SetUpdate(fn) update=fn end
function ContextPtr:SetShowHideHandler(fn) showhide=fn end
function include(_) end
ContentManager={GetAllPackageIDs=function()return {}end,IsActive=function()return false end}
ContentType={GAMEPLAY=1}
Modding={GetActivatedMods=function()return {}end,OpenUserData=function() return {Query=function(q)
 local rows=sql(q); local i=0; return function() i=i+1;return rows[i] end
end} end}
ActivePlayer=0
Turn=27
Game={GetActivePlayer=function() return ActivePlayer end,GetGameTurn=function()return Turn end}
GameDefines={MAX_PLAYERS=3}
Connected={[1]=true,[2]=true}
Names={}
SteamIDs={}
Steam={GetPlayerSteamID=function(id) return SteamIDs[id] and {ID=SteamIDs[id]} or nil end}
GameInfo={Civilizations={[0]={ShortDescription='Rome'},[1]={ShortDescription='Korea'},[2]={ShortDescription='Greece'}}}
Locale={ConvertTextKey=function(s) return s end}
Players=setmetatable({},{__index=function(t,k) return {
 GetCivilizationType=function()return k end,
 GetNickName=function()return Names[k] or 'P'..k end,
 GetName=function()return 'P'..k end,
 IsHuman=function()return k<3 end,
 GetTeam=function()return 2 end} end})
Events=setmetatable({},{__index=function(t,k)
 local event={Add=function(fn) t[k..'_handler']=fn end};rawset(t,k,event);return event
end})
Mouse={eLClick=1,eRClick=2,eLDblClick=3}; KeyEvents={KeyDown=1};Keys={VK_ESCAPE=27}
ChatTargetTypes={CHATTARGET_TEAM=1,CHATTARGET_PLAYER=2}
PreGame={IsMultiplayerGame=function()return true end}
Sent={};Network={IsPlayerConnected=function(id)return Connected[id]==true end, SendChat=function(text,team,player)
 Sent[#Sent+1]={text=text,team=team,player=player}
end}
""")
        if self.lobby:
            self.lua.execute("""
IGT_LOBBY=true
Game=nil; Players=nil
Matchmaking={GetLocalID=function() return ActivePlayer end,GetPlayerList=function()return {{playerID=0,playerName='Me'},{playerID=1,playerName='LobbyP1'},{playerID=2,playerName='LobbyP2'}}end}
SlotStatus={SS_TAKEN=1,SS_OBSERVER=2}
PreGame.GetSlotStatus=function(id)return 1 end
PreGame.GetNickName=function(id) return 'LobbyP'..id end
PreGame.IsMultiplayerGame=function() error('Do not rely on game state in lobby') end
""")
        if self.packaged:
            self.lua.execute("function include(_) error('Packaged lobby must not depend on include resolution') end")
            self.lua.execute((UI / "InGameTranslateLobby.lua").read_text(encoding="utf-8"))
        else:
            self.lua.execute((UI / "IGT_Text.lua").read_text(encoding="utf-8"))
            self.lua.execute((UI / "IGT_History.lua").read_text(encoding="utf-8"))
            self.lua.execute((UI / "InGameTranslate.lua").read_text(encoding="utf-8"))

    def tearDown(self):
        self.db.close()

    def click(self, name):
        self.lua.globals().Controls[name].callback()

    def tick(self, seconds=0.3):
        self.lua.globals().update(seconds)

    def draft(self, text):
        self.lua.globals().Controls.Draft.SetText(self.lua.globals().Controls.Draft, text)

    def select(self, control, value):
        self.lua.globals().Controls[control].selection(value)

    def complete(self, text, detected="ru", request_id=None):
        if request_id is None:
            request_id = self.db.execute("SELECT MAX(id) FROM requests").fetchone()[0]
        self.db.execute("UPDATE requests SET status='done',result=?,detected=? WHERE id=?", (text, detected, request_id))
        self.db.commit()
        self.tick()

    def test_incoming_unicode_and_local_tests_never_send(self):
        session = self.db.execute("SELECT value FROM igt_state WHERE key='session'").fetchone()[0]
        self.assertTrue(session)
        on_chat = self.lua.globals().Events.GameMessageChat_handler
        on_chat(1, 0, "Привіт! 안녕하세요", 0)
        request = self.db.execute("SELECT * FROM requests").fetchone()
        self.assertEqual(request["text"], "Привіт! 안녕하세요")
        self.assertEqual(request["target"], "en")
        on_chat(0, -1, "self message", 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 1)
        self.complete("Hello friends", "uk", request["id"])
        transcript = self.lua.globals().Transcript
        lines = [transcript[i].Message.text for i in range(1, len(transcript) + 1)]
        self.assertIn("(TR uk>en) P1: Hello friends", lines)
        self.assertIn("You: self message", lines)
        self.click("Test")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM requests WHERE kind='test'").fetchone()[0], 3)
        self.assertEqual(len(self.lua.globals().Sent), 0)

    def test_stale_translation_cannot_send_replaced_draft(self):
        self.draft("old draft")
        self.click("Translate")
        old_id = self.db.execute("SELECT MAX(id) FROM requests").fetchone()[0]
        self.draft("new draft")
        self.complete("устаревший перевод", "en", old_id)
        self.assertTrue(self.lua.globals().Controls.SendTranslated.disabled)
        self.click("SendTranslated")
        self.tick()
        self.assertEqual(len(self.lua.globals().Sent), 0)
        self.click("Translate")
        self.complete("новый перевод", "en")
        self.assertFalse(self.lua.globals().Controls.SendTranslated.disabled)
        self.assertEqual(len(self.lua.globals().Sent), 0)

    def test_draft_uses_chat_mode_and_setting_changes_keep_unsent_text(self):
        for filename in ['InGameTranslate.xml','InGameTranslateLobby.xml']:
            draft=ET.parse(UI/filename).find(".//EditBox[@ID='Draft']")
            self.assertEqual(draft.get('EditMode'),'0', 'Draft must not commit on focus loss')
            self.assertEqual(draft.get('CallOnChar'),'0', 'Typing must not submit')
        self.draft('Still composing my message')
        self.click('SendMode')
        self.select('Source',2)
        self.select('Target',3)
        self.select('Recipient',2)
        self.assertEqual(self.lua.globals().Controls.Draft.text,'Still composing my message')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)
        self.assertEqual(len(self.lua.globals().Sent),0)
        self.click('Draft')  # Explicit Enter after changing settings.
        request=self.db.execute('SELECT text,source,target FROM requests').fetchone()
        self.assertEqual(tuple(request),('Still composing my message','en','ko'))
        self.assertEqual(self.lua.globals().Controls.Draft.text,'')

    def test_explicit_send_private_icon_and_byte_limit(self):
        self.draft("Hello")
        self.click("Translate")
        self.complete("Привет " * 75, "en")
        self.click("IconGold")
        self.select("Recipient", 1)
        self.click("SendTranslated")
        for _ in range(20):
            self.tick(0.81)
        sent = self.lua.globals().Sent
        self.assertGreater(len(sent), 1)
        for i in range(1, len(sent) + 1):
            self.assertLessEqual(len(sent[i].text.encode("utf-8")), 240)
            self.assertTrue(sent[i].text.startswith("(TranslatorMod) [ICON_GOLD] "))
            self.assertEqual(sent[i].team, -1)
            self.assertEqual(sent[i].player, 1)

    def test_clipboard_handshake_and_activeplayer_cancels_queue(self):
        self.click("Paste")
        token = self.db.execute("SELECT value FROM igt_state WHERE key='clipboard_paste_request'").fetchone()[0]
        self.db.executemany("INSERT OR REPLACE INTO igt_state VALUES(?,?)", [
            ("clipboard_paste_token", token), ("clipboard_paste_result", "Unicode Привіт\n안녕하세요")])
        self.db.commit()
        self.tick()
        self.assertEqual(self.lua.globals().Controls.Draft.text, "Unicode Привіт 안녕하세요")
        self.click("CopyDraft")
        self.assertEqual(self.db.execute("SELECT value FROM igt_state WHERE key='clipboard_copy'").fetchone()[0], "Unicode Привіт 안녕하세요")
        self.draft("a" * 1000)
        self.click("SendOriginal")
        self.tick(0.1)
        self.assertEqual(len(self.lua.globals().Sent), 1)
        self.lua.globals().ActivePlayer = 1
        self.lua.globals().Events.GameplaySetActivePlayer_handler()
        self.tick(10)
        self.assertEqual(len(self.lua.globals().Sent), 1)
        self.assertEqual(self.lua.globals().Controls.Draft.text, "")

    def test_compact_overlay_expands_and_hides_options(self):
        controls = self.lua.globals().Controls
        self.assertEqual(controls.Panel.height, 400)
        self.click('Expand')
        self.assertEqual(controls.Panel.height, 700)
        self.assertEqual(controls.Panel.width, 960)
        self.assertEqual(controls.Panel.anchor, 'L,T')
        self.assertEqual(controls.TranscriptScroll.height, 516)
        self.assertEqual(controls.DraftBox.y, 600)
        self.assertEqual(controls.PanelBackdrop.alpha, .80)
        self.click('Expand')
        self.assertEqual(controls.Panel.height, 400)
        self.click('More')
        self.assertFalse(controls.Settings.hidden)
        self.click('Minimize')
        self.assertTrue(controls.Panel.hidden)
        self.assertTrue(controls.Settings.hidden)

    def test_own_translated_reply_shows_readable_draft_without_echo_duplicate(self):
        self.draft('Can we trade?')
        self.click('Translate')
        self.complete('Можем ли мы торговать?', 'en')
        self.click('SendTranslated')
        self.tick()
        transcript = self.lua.globals().Transcript
        self.assertEqual(transcript[len(transcript)].Message.text, 'You -> ru: Can we trade?')
        count = len(transcript)
        self.lua.globals().Events.GameMessageChat_handler(0, -1, '(TranslatorMod) Можем ли мы торговать?', 0)
        self.assertEqual(len(transcript), count)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM requests WHERE kind='incoming'").fetchone()[0], 0)

    def test_own_native_chat_is_visible_even_when_auto_translate_disabled(self):
        self.click('Receive')
        self.lua.globals().Events.GameMessageChat_handler(0, -1, 'Hello everyone', 0)
        transcript = self.lua.globals().Transcript
        self.assertEqual(transcript[len(transcript)].Message.text, 'You: Hello everyone')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 0)

    def test_selected_color_sent_in_every_part_with_byte_budget(self):
        self.click('MessageColor')  # Default -> Red
        self.draft('Привет ' * 100)
        self.click('IconGold')
        self.click('SendOriginal')
        for _ in range(20):
            self.tick(.81)
        sent = self.lua.globals().Sent
        self.assertGreater(len(sent), 1)
        for i in range(1, len(sent) + 1):
            self.assertTrue(sent[i].text.startswith('[COLOR_RED][ICON_GOLD] '))
            self.assertTrue(sent[i].text.endswith('[ENDCOLOR]'))
            self.assertLessEqual(len(sent[i].text.encode('utf-8')), 240)
        transcript = self.lua.globals().Transcript
        self.assertTrue(transcript[len(transcript)].Message.text.startswith('[COLOR_RED]You: '))

    def test_incoming_colors_and_team_tint_survive_translation(self):
        self.lua.globals().Events.GameMessageChat_handler(1, -1, '[COLOR_CYAN]Привет[ENDCOLOR]', 1)
        transcript = self.lua.globals().Transcript
        row = transcript[len(transcript)]
        self.assertEqual(row.Message.color, 'Green_Chat')
        self.assertIn('[COLOR_CYAN]Привет[ENDCOLOR]', row.Message.text)
        self.complete('[COLOR_CYAN]Hello[ENDCOLOR]')
        self.assertIn('[COLOR_CYAN]Hello[ENDCOLOR]', row.Message.text)
        self.assertEqual(row.Message.color, 'Green_Chat')

    def test_repeated_enter_translation_captures_language_and_recipient(self):
        self.click('SendMode')
        self.select('Recipient', 1)
        self.select('Target', 2)  # Ukrainian
        self.draft('First message')
        self.click('Draft')  # Enter
        first = self.db.execute('SELECT MAX(id) FROM requests').fetchone()[0]
        self.assertEqual(self.lua.globals().Controls.Draft.text, '')
        self.assertFalse(self.lua.globals().Controls.CancelSend.disabled)
        self.select('Recipient', 2)
        self.select('Target', 3)  # Korean
        self.draft('Second message')
        self.click('Draft')
        second = self.db.execute('SELECT MAX(id) FROM requests').fetchone()[0]
        self.assertEqual([r[0] for r in self.db.execute('SELECT target FROM requests ORDER BY id')], ['uk', 'ko'])
        self.complete('Перший', 'en', first)
        self.complete('두번째', 'en', second)
        self.tick(.81)
        sent = self.lua.globals().Sent
        self.assertEqual(len(sent), 2)
        self.assertEqual((sent[1].text, sent[1].player, sent[1].team), ('(TranslatorMod) Перший', 1, -1))
        self.assertEqual((sent[2].text, sent[2].player, sent[2].team), ('(TranslatorMod) 두번째', 2, -1))
        self.assertEqual(self.lua.globals().Controls.SendModeLabel.text, 'Translate: ON')

    def test_private_recipient_disconnect_never_broadcasts(self):
        self.click('SendMode')
        self.select('Recipient', 1)
        self.draft('Private message')
        self.click('Draft')
        self.lua.globals().Connected[1] = False
        self.complete('Личное сообщение', 'en')
        self.tick(3)
        self.assertEqual(len(self.lua.globals().Sent), 0)
        self.assertIn('Not sent: Private message', self.lua.globals().Transcript[len(self.lua.globals().Transcript)].Message.text)

    def test_failed_translation_does_not_send_original(self):
        self.click('SendMode')
        self.draft('Keep this unsent if translation fails')
        self.click('Draft')
        self.db.execute("UPDATE requests SET status='error',error='Quota reached'")
        self.db.commit()
        self.tick(3)
        self.tick(3)
        self.assertEqual(len(self.lua.globals().Sent), 0)
        self.assertIn('Not sent: Keep this unsent', self.lua.globals().Transcript[len(self.lua.globals().Transcript)].Message.text)
        self.assertTrue(self.lua.globals().Controls.CancelSend.disabled)

    def test_cancel_pending_translation_prevents_late_send(self):
        self.click('SendMode')
        self.draft('Do not send after cancellation')
        self.click('Draft')
        self.click('CancelSend')
        self.complete('Отменено', 'en')
        self.tick(3)
        self.assertEqual(len(self.lua.globals().Sent), 0)

    def test_disabled_online_cancels_completed_translation_before_send(self):
        self.click('SendMode')
        self.draft('Must not send after closing companion')
        self.click('Draft')
        self.db.execute("INSERT OR REPLACE INTO igt_state VALUES('online_translation_enabled','0')")
        self.complete('Отменено', 'en')
        self.tick(3)
        self.assertEqual(len(self.lua.globals().Sent),0)

    def test_disabled_online_keeps_new_draft_unsent_and_original_send_works(self):
        self.db.execute("INSERT OR REPLACE INTO igt_state VALUES('online_translation_enabled','0')")
        self.click('SendMode')
        self.draft('Keep draft')
        self.click('Draft')
        self.assertEqual(self.lua.globals().Controls.Draft.text,'Keep draft')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)
        self.click('SendMode')
        self.click('Draft')
        self.tick(1)
        self.assertEqual(len(self.lua.globals().Sent),1)

    def test_turn_stamp_keeps_receive_turn_after_translation(self):
        self.lua.globals().Events.GameMessageChat_handler(1, -1, 'Привет', 0)
        row = self.lua.globals().Transcript[len(self.lua.globals().Transcript)]
        self.lua.globals().Turn = 28
        self.complete('Hello')
        self.assertIn('Turn 27', row.Message.tooltip)
        self.assertNotIn('Turn 28', row.Message.tooltip)

    def test_incoming_whisper_keeps_purple_on_translation_and_original_toggle(self):
        g=self.lua.globals()
        g.Events.GameMessageChat_handler(1,0,'Привет',g.ChatTargetTypes.CHATTARGET_PLAYER)
        row=g.Transcript[len(g.Transcript)]
        self.assertEqual(row.Message.color,'Magenta_Chat')
        self.complete('Hello','ru')
        self.assertEqual(row.Message.color,'Magenta_Chat')
        row.TranslateButton.callback()
        self.assertEqual(row.Message.color,'Magenta_Chat')

    def test_outgoing_whisper_uses_purple_for_original_and_translated_lines(self):
        self.select('Recipient',1)
        self.draft('Private original')
        self.click('Draft');self.tick(1)
        g=self.lua.globals()
        self.assertEqual(g.Transcript[len(g.Transcript)].Message.color,'Magenta_Chat')
        self.click('SendMode');self.draft('Private translated');self.click('Draft')
        self.complete('Личное','en');self.tick(1)
        self.assertEqual(g.Transcript[len(g.Transcript)].Message.color,'Magenta_Chat')

    def test_lobby_chat_without_target_enum_is_displayed(self):
        g=self.lua.globals();g.ChatTargetTypes=None
        g.Events.GameMessageChat_handler(1,-1,'hello',None)
        self.assertIn('hello',g.Transcript[len(g.Transcript)].Message.text)

    def test_header_drag_preserves_draft_clamps_position_and_restores_size(self):
        self.click('Toggle')
        self.draft('Unsent while moving')
        g=self.lua.globals()
        g.MouseX,g.MouseY=870,40
        g.Controls.HeaderDrag.tracking=True;self.tick(.01)
        g.MouseX,g.MouseY=770,140
        self.tick(.01)
        self.assertEqual((g.Controls.Panel.x,g.Controls.Panel.y),(620,130))
        g.Controls.HeaderDrag.tracking=False;self.tick(.01)
        self.assertEqual(g.Controls.Draft.text,'Unsent while moving')
        self.assertEqual(len(g.Sent),0)
        self.click('Expand')
        self.click('Expand')
        self.assertEqual((g.Controls.Panel.x,g.Controls.Panel.y),(620,130))
        g.MouseX,g.MouseY=770,140
        g.Controls.HeaderDrag.tracking=True;self.tick(.01)
        g.MouseX,g.MouseY=-1000,-1000
        self.tick(.01)
        g.Controls.HeaderDrag.tracking=False;self.tick(.01)
        self.assertEqual((g.Controls.Panel.x,g.Controls.Panel.y),(0,0))
        self.assertEqual((g.Controls.Toggle.x,g.Controls.Toggle.y),(390,0))

    def test_turn_is_tooltip_only_for_incoming_and_own_messages(self):
        self.lua.globals().Events.GameMessageChat_handler(1,-1,'Hello',0)
        row=self.lua.globals().Transcript[len(self.lua.globals().Transcript)]
        self.assertEqual(row.Message.text,'P1: Hello')
        self.assertIn('Turn 27',row.Message.tooltip)
        self.draft('My reply')
        self.click('SendOriginal');self.tick()
        row=self.lua.globals().Transcript[len(self.lua.globals().Transcript)]
        self.assertEqual(row.Message.text,'You: My reply')
        self.assertEqual(row.Message.tooltip,'Turn 27')

    def test_native_header_stops_after_release_and_doubleclick_preserves_draft(self):
        self.click('Toggle');self.draft('Keep draft')
        g=self.lua.globals();g.MouseX,g.MouseY=870,40
        g.Controls.HeaderDrag.tracking=True;self.tick(.01)
        g.MouseX,g.MouseY=800,90;self.tick(.01)
        position=(g.Controls.Panel.x,g.Controls.Panel.y)
        g.Controls.HeaderDrag.tracking=False;self.tick(.01)
        g.MouseX,g.MouseY=300,300;self.tick(.01)
        self.assertEqual((g.Controls.Panel.x,g.Controls.Panel.y),position)
        g.Controls.HeaderDrag.doubleclick()
        self.assertEqual(g.Controls.Panel.width,960)
        self.assertEqual(g.Controls.Draft.text,'Keep draft')
        self.assertEqual(len(g.Sent),0)

    def test_collapsed_button_replaced_by_integrated_header(self):
        self.click('Toggle')
        self.assertFalse(self.lua.globals().Controls.Panel.hidden)
        self.assertTrue(self.lua.globals().Controls.Toggle.hidden)
        self.click('Minimize')
        self.assertTrue(self.lua.globals().Controls.Panel.hidden)
        self.assertFalse(self.lua.globals().Controls.Toggle.hidden)

    def test_player_dropdown_has_all_and_humans_without_team(self):
        entries = self.lua.globals().Controls.Recipient.entries
        self.assertEqual([(entries[i].value, entries[i].text) for i in range(1, len(entries) + 1)], [(-1, 'All players'), (1, 'P1'), (2, 'P2')])

    def save_profile(self, name='P1', alias='Trading friend', note="Prefers peace; don't rush"):
        self.click('PlayerNotes')
        entries = self.lua.globals().Controls.ProfilePlayer.entries
        entry = next(entries[i] for i in range(1, len(entries) + 1) if entries[i].text == name)
        self.select('ProfilePlayer', entry.value)
        self.lua.globals().Controls.ProfileAlias.text = alias
        self.lua.globals().Controls.ProfileNote.text = note
        self.click('ProfileSave')

    def test_profile_updates_history_and_translation_without_leaking_note(self):
        self.lua.globals().Events.GameMessageChat_handler(1, -1, 'Привет', 0)
        row = self.lua.globals().Transcript[len(self.lua.globals().Transcript)]
        self.save_profile()
        self.assertEqual(row.Message.text, 'P1(Trading friend): Привет')
        self.assertIn("Note: Prefers peace; don't rush", row.Message.tooltip)
        self.assertIn('Original name: P1', row.Message.tooltip)
        self.complete('Hello')
        self.assertEqual(row.Message.text, '(TR ru>en) P1(Trading friend): Hello')
        self.assertEqual(self.db.execute('SELECT text FROM requests').fetchone()[0], 'Привет')
        self.assertEqual(len(self.lua.globals().Sent), 0)

    def test_nickname_does_not_change_private_routing_or_message_payload(self):
        self.select('Recipient', 1)
        self.save_profile(alias='P2', note='Secret local note')
        self.assertEqual(self.lua.globals().Controls.Recipient.text, 'To: P1(P2)')
        self.draft('Actual message')
        self.click('SendOriginal')
        self.tick()
        sent = self.lua.globals().Sent[1]
        self.assertEqual((sent.text, sent.player, sent.team), ('Actual message', 1, -1))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 0)

    def test_saved_profile_survives_session_reload_and_can_be_cleared(self):
        self.save_profile()
        self.lua.globals().Events.GameplaySetActivePlayer_handler()
        self.lua.globals().Events.GameMessageChat_handler(1, -1, 'Hello', 0)
        row = self.lua.globals().Transcript[len(self.lua.globals().Transcript)]
        self.assertEqual(row.Message.text, 'P1(Trading friend): Hello')
        self.click('PlayerNotes')
        self.assertEqual(self.lua.globals().Controls.ProfileAlias.text, 'Trading friend')
        self.click('ProfileDelete')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM igt_profiles').fetchone()[0], 0)
        self.assertEqual(row.Message.text, 'P1: Hello')

    def test_changed_slot_name_does_not_inherit_profile(self):
        self.save_profile()
        self.lua.globals().Names[1] = 'New person'
        self.tick(3)
        self.lua.globals().Events.GameMessageChat_handler(1, -1, 'Hello', 0)
        row = self.lua.globals().Transcript[len(self.lua.globals().Transcript)]
        self.assertEqual(row.Message.text, 'New person: Hello')
        self.assertNotIn('Prefers peace', row.Message.tooltip)

    def test_duplicate_names_do_not_apply_saved_alias_or_allow_save(self):
        self.save_profile()
        self.lua.globals().Names[2] = 'P1'
        self.tick(3)
        self.lua.globals().Events.GameMessageChat_handler(1, -1, 'Hello', 0)
        row = self.lua.globals().Transcript[len(self.lua.globals().Transcript)]
        self.assertEqual(row.Message.text, 'P1: Hello')
        self.assertIn('Duplicate name', row.Message.tooltip)
        self.click('CloseProfiles')
        self.click('PlayerNotes')
        self.assertTrue(self.lua.globals().Controls.ProfileSave.disabled)

    def test_profile_quotes_unicode_and_markup_are_local_plain_text(self):
        self.lua.globals().Names[1] = "O'Brien"
        self.save_profile(name="O'Brien", alias='Друг [ICON_GOLD]', note="한글 ' note [NEWLINE] example")
        profile = self.db.execute('SELECT * FROM igt_profiles').fetchone()
        self.assertEqual(tuple(profile), ("O'Brien", 'Друг (ICON_GOLD)', "한글 ' note (NEWLINE) example"))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 0)

    def test_profile_editor_closes_with_main_panel(self):
        self.click('PlayerNotes')
        self.assertFalse(self.lua.globals().Controls.ProfilesPanel.hidden)
        self.click('Minimize')
        self.assertTrue(self.lua.globals().Controls.ProfilesPanel.hidden)

    def test_steam_profile_follows_account_after_name_change(self):
        self.lua.globals().SteamIDs[1] = '76561198000000001'
        self.save_profile(alias='Friend account', note='Persistent account note')
        self.assertEqual(self.db.execute('SELECT steam_id FROM igt_account_profiles').fetchone()[0], '76561198000000001')
        self.lua.globals().Names[1] = 'New nickname'
        self.tick(3)
        self.lua.globals().Events.GameMessageChat_handler(1, -1, 'Hello', 0)
        row = self.lua.globals().Transcript[len(self.lua.globals().Transcript)]
        self.assertEqual(row.Message.text, 'New nickname(Friend account): Hello')
        self.assertIn('76561198000000001', row.Message.tooltip)
        self.lua.globals().Events.GameplaySetActivePlayer_handler()
        self.lua.globals().Events.GameMessageChat_handler(1, -1, 'Again', 0)
        row = self.lua.globals().Transcript[len(self.lua.globals().Transcript)]
        self.assertEqual(row.Message.text, 'New nickname(Friend account): Again')

    def test_steam_identity_rejects_rounded_numbers_and_binding_errors(self):
        self.lua.globals().SteamIDs[1] = 76561198000000001
        self.assertIsNone(self.lua.globals().IGT_History.SteamID(1))
        self.lua.execute("Steam.GetPlayerSteamID=function() error('Unavailable') end")
        self.assertIsNone(self.lua.globals().IGT_History.SteamID(1))

    def test_history_records_civs_dates_and_counts_games_by_steam(self):
        self.lua.globals().SteamIDs[1] = '76561198000000001'
        self.click('HistoryTab')
        self.click('HistoryNew')
        row = self.db.execute("SELECT * FROM igt_encounters WHERE steam_id='76561198000000001'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual((row['my_civ'], row['their_civ'], row['first_turn'], row['last_turn']), ('Rome','Korea',27,27))
        self.assertRegex(row['first_utc'], r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d$')
        self.lua.globals().Turn = 32
        self.tick(10)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM igt_games').fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT last_turn FROM igt_encounters WHERE steam_id='76561198000000001'").fetchone()[0], 32)
        self.click('HistoryNew')  # Double-click cannot create another active game.
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM igt_games').fetchone()[0], 1)
        self.click('HistoryStop')
        self.lua.globals().Names[1] = 'Different nickname'
        self.click('HistoryNew')
        self.assertEqual(self.db.execute("SELECT COUNT(DISTINCT game_id) FROM igt_encounters WHERE steam_id='76561198000000001'").fetchone()[0], 2)
        entries=self.lua.globals().Controls.HistoryPlayer.entries
        entry=next(entries[i] for i in range(1,len(entries)+1) if entries[i].text.startswith('Different nickname'))
        self.select('HistoryPlayer',entry.value)
        self.assertIn('2 recorded game(s)', self.lua.globals().Controls.HistorySummary.text)
        self.assertIn('You: Rome    Them: Korea', self.lua.globals().Controls.HistoryText.text)

    def test_history_resume_after_reload_does_not_count_another_game(self):
        self.click('HistoryTab')
        self.click('HistoryNew')
        first = self.db.execute('SELECT id FROM igt_games').fetchone()[0]
        self.lua.globals().Events.GameplaySetActivePlayer_handler()
        self.lua.globals().Turn = 40
        self.tick(10)
        self.assertEqual(self.db.execute('SELECT MAX(last_turn) FROM igt_encounters').fetchone()[0], 27)
        self.click('HistoryTab')
        self.click('HistoryResume')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM igt_games').fetchone()[0], 1)
        self.assertEqual(self.db.execute('SELECT MAX(last_turn) FROM igt_encounters WHERE game_id=?',(first,)).fetchone()[0], 40)
        self.lua.globals().Turn = 29  # Earlier save; retain maximum observed turn.
        self.tick(10)
        self.assertEqual(self.db.execute('SELECT MAX(last_turn) FROM igt_encounters').fetchone()[0], 40)

    def test_history_late_steam_id_upgrades_current_record_only(self):
        self.click('HistoryTab')
        self.click('HistoryNew')
        self.lua.globals().SteamIDs[1] = '76561198000000001'
        self.tick(10)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM igt_encounters WHERE original_name='P1'").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT player_key FROM igt_encounters WHERE original_name='P1'").fetchone()[0], 'steam:76561198000000001')

    def test_history_records_nothing_until_started_and_stops_cleanly(self):
        self.tick(30)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM igt_games').fetchone()[0], 0)
        self.click('HistoryTab')
        self.click('HistoryNew')
        self.click('HistoryStop')
        self.lua.globals().Turn = 70
        self.tick(30)
        self.assertEqual(self.db.execute('SELECT MAX(last_turn) FROM igt_encounters').fetchone()[0], 27)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 0)
        self.assertEqual(len(self.lua.globals().Sent), 0)

    def test_tabs_and_opacity_preserve_draft_and_chat(self):
        self.draft('Unsent draft')
        self.click('Expand')
        self.click('SettingsTab')
        self.assertTrue(self.lua.globals().Controls.ChatPage.hidden)
        self.assertFalse(self.lua.globals().Controls.Settings.hidden)
        self.click('Opacity')
        self.assertEqual(self.lua.globals().Controls.PanelBackdrop.alpha, 0.96)
        self.click('ChatTab')
        self.assertFalse(self.lua.globals().Controls.ChatPage.hidden)
        self.assertEqual(self.lua.globals().Controls.Draft.text, 'Unsent draft')
        self.click('Expand')
        self.assertEqual(self.lua.globals().Controls.Panel.anchor, 'L,T')
        self.assertTrue(self.lua.globals().Controls.TabBar.hidden)

    def test_expanded_window_fits_small_screen_and_keeps_chat_majority(self):
        self.lua.execute('UIManager.GetScreenSizeVal=function() return 1024,768 end')
        self.click('Expand')
        c=self.lua.globals().Controls
        self.assertEqual((c.Panel.width,c.Panel.height), (960,698))
        self.assertGreater(c.TranscriptScroll.height, c.Panel.height/2)
        self.assertLess(c.DraftBox.y+28, c.Panel.height)

    def test_reopen_restores_selected_tab(self):
        self.click('Toggle')
        self.click('SettingsTab')
        self.click('Minimize')
        self.click('Toggle')
        self.assertFalse(self.lua.globals().Controls.Panel.hidden)
        self.assertFalse(self.lua.globals().Controls.Settings.hidden)
        self.assertTrue(self.lua.globals().Controls.ChatPage.hidden)

    def test_private_translation_is_cancelled_when_account_changes_in_slot(self):
        self.lua.globals().SteamIDs[1] = '76561198000000001'
        self.select('Recipient',1)
        self.click('SendMode')
        self.draft('Private text')
        self.click('Draft')
        self.lua.globals().SteamIDs[1] = '76561198000000002'
        self.complete('Личный текст','en')
        self.tick(3)
        self.assertEqual(len(self.lua.globals().Sent),0)

    def test_same_name_different_steam_accounts_keep_separate_encounters(self):
        self.lua.globals().SteamIDs[1] = '76561198000000001'
        self.click('HistoryTab')
        self.click('HistoryNew')
        self.click('HistoryStop')
        self.lua.globals().SteamIDs[1] = '76561198000000002'
        self.click('HistoryNew')
        rows=self.db.execute("SELECT player_key,COUNT(DISTINCT game_id) FROM igt_encounters WHERE original_name='P1' GROUP BY player_key").fetchall()
        self.assertEqual([tuple(r) for r in rows],[('steam:76561198000000001',1),('steam:76561198000000002',1)])

    def test_custom_size_presets_sliders_persist_and_fit_changed_display(self):
        self.draft('Keep my draft')
        self.click('SizeLarge')
        c=self.lua.globals().Controls
        self.assertEqual((c.Panel.width,c.Panel.height),(1100,820))
        c.WidthSlider.slider(0)
        c.HeightSlider.slider(0)
        self.assertEqual((c.Panel.width,c.Panel.height),(700,620))
        self.assertEqual(c.Draft.text,'Keep my draft')
        self.lua.globals().Events.GameplaySetActivePlayer_handler()
        self.click('Expand') if c.Panel.width==550 else None
        self.assertEqual((c.Panel.width,c.Panel.height),(700,620))
        self.click('SizeLarge')
        self.lua.execute('UIManager.GetScreenSizeVal=function()return 1024,768 end')
        self.tick(3)
        self.assertEqual((c.Panel.width,c.Panel.height),(976,698))
        self.assertGreaterEqual(c.Panel.x,0)
        self.assertLessEqual(c.Panel.x+c.Panel.width,1024)

    def test_join_summary_uses_history_and_former_account_names_once(self):
        g=self.lua.globals();g.SteamIDs[1]='76561198000000001'
        self.tick(3)
        self.click('HistoryTab');self.click('HistoryNew');self.click('HistoryStop')
        g.Names[1]='New name'
        g.Events.GameplaySetActivePlayer_handler()
        lines=[g.Transcript[i].Message.text for i in range(1,len(g.Transcript)+1)]
        summary=next(line for line in reversed(lines) if line.startswith('Player: New name'))
        self.assertIn('1 recorded game(s) together',summary)
        self.assertIn('previously: P1',summary)
        count=len(g.Transcript);self.tick(3)
        self.assertEqual(len(g.Transcript),count)
        self.assertEqual(len(g.Sent),0)

    def test_emoji_picker_inserts_icon_without_submitting_draft(self):
        self.draft('Trade')
        self.click('EmojiButton');self.click('EmojiGold')
        self.assertEqual(self.lua.globals().Controls.Draft.text,'Trade [ICON_GOLD] ')
        self.assertTrue(self.lua.globals().Controls.EmojiPanel.hidden)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)
        self.assertEqual(len(self.lua.globals().Sent),0)

    def test_right_click_chat_opens_notes_and_keeps_real_name_with_nickname(self):
        self.save_profile(alias='thechatter',note='Talkative')
        self.lua.globals().Events.GameMessageChat_handler(1,-1,'Hello',0)
        row=self.lua.globals().Transcript[len(self.lua.globals().Transcript)]
        self.assertEqual(row.Message.text,'P1(thechatter): Hello')
        row.Box.rightclick()
        self.assertFalse(self.lua.globals().Controls.PlayerMenu.hidden)
        self.click('PlayerMenuNote')
        self.assertFalse(self.lua.globals().Controls.ProfilesPanel.hidden)
        self.assertEqual(self.lua.globals().Controls.ProfileNote.text,'Talkative')
        self.assertEqual(self.lua.globals().Controls.ProfileAlias.text,'thechatter')
        self.assertEqual(len(self.lua.globals().Sent),0)
        self.click('ChatTab');row.Box.rightclick();self.click('PlayerMenuDetails')
        self.assertIn('P1(thechatter)',self.lua.globals().Controls.HistorySummary.text)
        self.tick(10)
        self.assertIn('P1(thechatter)',self.lua.globals().Controls.HistorySummary.text)


if __name__ == "__main__":
    unittest.main()
