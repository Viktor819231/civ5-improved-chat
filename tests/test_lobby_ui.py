"""Lobby has no Game/Players objects; hidden lobbies must not own the bridge."""
import unittest
import test_game_ui


class LobbyUITests(unittest.TestCase):
    def setUp(self):
        self.h = test_game_ui.GameUITests()
        self.h.lobby = True
        self.h.packaged = True
        self.h.setUp()
        self.lua, self.db = self.h.lua, self.h.db

    def tearDown(self):
        self.h.tearDown()

    def show(self):
        self.lua.globals().showhide(False, False)

    def test_hidden_startup_never_opens_mailbox(self):
        self.h.tick()
        self.lua.globals().Events.GameMessageChat_handler(1, -1, 'Привет', 0)
        self.assertIsNone(self.db.execute("SELECT name FROM sqlite_master WHERE name='requests'").fetchone())

    def test_button_opens_panel_without_initial_show_callback(self):
        self.h.click('Toggle')
        self.assertFalse(self.lua.globals().Controls.Panel.hidden)
        self.assertIsNotNone(self.db.execute("SELECT value FROM igt_state WHERE key='session'").fetchone())
        self.h.click('Toggle')
        self.assertTrue(self.lua.globals().Controls.Panel.hidden)

    def test_lobby_unicode_player_names_and_explicit_send(self):
        self.show()
        self.lua.globals().Events.GameMessageChat_handler(1, -1, 'Привет', 0)
        self.h.complete('Hello')
        transcript = self.lua.globals().Transcript
        self.assertIn('LobbyP1: Hello', transcript[len(transcript)].Message.text)
        self.lua.globals().Events.GameMessageChat_handler(0, -1, 'own chat', 0)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM requests').fetchone()[0], 1)
        self.h.draft('Hello friends')
        self.h.click('Translate')
        self.h.complete('Привет друзья', 'en')
        self.assertEqual(len(self.lua.globals().Sent), 0)
        self.assertFalse(self.lua.globals().Controls.Recipient.disabled)
        self.h.select('Recipient', -1)
        self.h.click('SendTranslated')
        self.h.tick()
        sent = self.lua.globals().Sent[1]
        self.assertEqual(sent.text, '(TR) Привет друзья')
        self.assertIsNone(sent.team)
        self.assertIsNone(sent.player)

    def test_lobby_private_enter_send_uses_selected_player(self):
        self.show()
        self.h.select('Recipient', 2)
        self.h.click('SendMode')
        self.h.draft('Hello privately')
        self.h.click('Draft')
        self.h.complete('Привет', 'en')
        self.h.tick(.81)
        sent = self.lua.globals().Sent[1]
        self.assertEqual((sent.text, sent.team, sent.player), ('(TR) Привет', -1, 2))
        transcript = self.lua.globals().Transcript
        self.assertIn('You -> ru to LobbyP2 (private): Hello privately', transcript[len(transcript)].Message.text)

    def test_leaving_lobby_cancels_send_and_rejoining_creates_session(self):
        self.show()
        old = self.db.execute("SELECT value FROM igt_state WHERE key='session'").fetchone()[0]
        self.h.draft('a' * 1000)
        self.h.click('SendOriginal')
        self.h.tick(.1)
        self.assertEqual(len(self.lua.globals().Sent), 1)
        self.lua.globals().showhide(True, False)
        self.h.tick(10)
        self.assertEqual(len(self.lua.globals().Sent), 1)
        self.assertEqual(self.db.execute("SELECT value FROM igt_state WHERE key='session'").fetchone()[0], '')
        self.show()
        current = self.db.execute("SELECT value FROM igt_state WHERE key='session'").fetchone()[0]
        self.assertNotEqual(old, current)
        self.assertEqual(self.lua.globals().Controls.Draft.text, '')
        self.assertTrue(self.lua.globals().Controls.SendTranslated.disabled)

    def test_hidden_lobby_cannot_clear_new_game_session(self):
        self.show()
        self.db.execute("UPDATE igt_state SET value='new-game-session' WHERE key='session'")
        self.db.commit()
        self.lua.globals().showhide(True, False)
        self.assertEqual(self.db.execute("SELECT value FROM igt_state WHERE key='session'").fetchone()[0], 'new-game-session')

    def test_lobby_profile_persists_after_rejoining(self):
        self.show()
        self.h.save_profile(name='LobbyP1', alias='Lobby friend', note='Local lobby note')
        self.lua.globals().showhide(True, False)
        self.show()
        self.lua.globals().Events.GameMessageChat_handler(1, -1, 'Hello', 0)
        row = self.lua.globals().Transcript[len(self.lua.globals().Transcript)]
        self.assertEqual(row.Message.text, 'LobbyP1(Lobby friend): Hello')
        self.assertIn('Local lobby note', row.Message.tooltip)

    def test_lobby_history_does_not_record_game_encounters(self):
        self.show()
        self.h.click('HistoryTab')
        self.h.click('HistoryNew')
        self.h.tick(30)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM igt_games').fetchone()[0], 0)
        self.assertTrue(self.lua.globals().Controls.HistoryNew.disabled)


if __name__ == '__main__':
    unittest.main()
