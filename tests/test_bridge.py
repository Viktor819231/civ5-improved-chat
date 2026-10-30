import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from companion.bridge import Bridge, initialize_database


class FakeTranslator:
    def __init__(self, result="Hello, friend!", detected="ru"):
        self.calls = []
        self.result = result
        self.detected = detected

    def translate(self, text, source, target):
        self.calls.append((text, source, target))
        return self.result, self.detected


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "InGameTranslateMod-1.db"
        initialize_database(self.path)
        self.now = 1000.0
        self.translator = FakeTranslator()
        self.bridge = Bridge(self.path, self.translator, clock=lambda: self.now)
        self.sql("INSERT INTO igt_state VALUES('session','first')")

    def sql(self, statement, parameters=()):
        with closing(sqlite3.connect(self.path, isolation_level=None)) as connection:
            return connection.execute(statement, parameters).fetchall()

    def enqueue(self, text="Привет, друг!", session="first", created=None, **extra):
        values = dict(session=session, kind="incoming", source="auto", target="en",
                      text=text, status="pending", created=self.now if created is None else created)
        values.update(extra)
        self.sql("INSERT INTO requests(" + ",".join(values) + ") VALUES(" +
                 ",".join("?" for _ in values) + ")", tuple(values.values()))
        return self.sql("SELECT MAX(id) FROM requests")[0][0]

    def test_unicode_round_trip_and_apostrophe(self):
        original = "Привет! Україна 한국어 O'Brien [COLOR_RED]"
        translated = "Привіт, друже! 안녕하세요 O'Brien"
        self.translator.result = translated
        self.enqueue(original)
        self.assertTrue(self.bridge.process_one())
        self.assertEqual(self.translator.calls, [(original, "auto", "en")])
        self.assertEqual(self.sql("SELECT status,result,detected FROM requests"),
                         [("done", translated, "ru")])

    def test_old_sessions_and_stale_requests_are_not_translated(self):
        self.enqueue(session="old")
        self.enqueue(created=700)
        self.enqueue("Current")
        self.bridge.process_one()
        self.assertEqual([row[0] for row in self.sql("SELECT status FROM requests ORDER BY id")],
                         ["error", "error", "done"])
        self.assertEqual(len(self.translator.calls), 1)

    def test_working_lease_recovers_after_crash(self):
        self.enqueue(status="working", started=930)
        self.assertTrue(self.bridge.process_one())
        self.assertEqual(self.sql("SELECT status FROM requests"), [("done",)])

    def test_active_lease_is_not_claimed(self):
        self.enqueue(status="working", started=990)
        self.assertFalse(self.bridge.process_one())
        self.assertEqual(self.translator.calls, [])

    def test_session_change_during_network_call_discards_result(self):
        def translate(*_):
            self.sql("UPDATE igt_state SET value='second' WHERE key='session'")
            return "Old message", "ru"
        self.translator.translate = translate
        self.enqueue()
        self.bridge.process_one()
        self.assertEqual(self.sql("SELECT status,result,error FROM requests"),
                         [("error", "", "Game session ended.")])

    def test_provider_error_does_not_repeat_or_publish_source(self):
        def translate(*_):
            raise RuntimeError("Translation service unavailable.")
        self.translator.translate = translate
        self.enqueue()
        self.assertTrue(self.bridge.process_one())
        self.assertFalse(self.bridge.process_one())
        self.assertEqual(self.sql("SELECT status,result,error FROM requests"),
                         [("error", "", "Translation service unavailable.")])

    def test_busy_result_write_retries_without_retranslation(self):
        blocker = sqlite3.connect(self.path, isolation_level=None)
        self.addCleanup(blocker.close)
        def translate(text, source, target):
            self.translator.calls.append((text, source, target))
            blocker.execute("BEGIN IMMEDIATE")
            return "Hello", "ru"
        self.translator.translate = translate
        self.enqueue()
        self.assertFalse(self.bridge.process_one())
        blocker.rollback()
        self.assertTrue(self.bridge.process_one())
        self.assertEqual(len(self.translator.calls), 1)
        self.assertEqual(self.sql("SELECT result FROM requests"), [("Hello",)])

    def test_translate_runs_without_database_transaction(self):
        def translate(*_):
            self.sql("INSERT OR REPLACE INTO igt_state VALUES('probe','written')")
            return "Hello", "ru"
        self.translator.translate = translate
        self.enqueue()
        self.bridge.process_one()
        self.assertEqual(self.sql("SELECT value FROM igt_state WHERE key='probe'"), [("written",)])

    def test_terminal_history_is_bounded(self):
        for i in range(6):
            self.enqueue(str(i), status="done")
        self.bridge.max_completed_rows = 3
        self.bridge.process_one()
        self.assertEqual(self.sql("SELECT COUNT(*) FROM requests"), [(3,)])

    def test_missing_database_is_not_created(self):
        missing = Path(self.temp.name) / "missing.db"
        bridge = Bridge(missing, self.translator)
        self.assertFalse(bridge.process_one())
        self.assertFalse(missing.exists())

    def test_no_session_does_not_process(self):
        self.sql("DELETE FROM igt_state")
        self.enqueue()
        self.assertFalse(self.bridge.process_one())
        self.assertEqual(self.translator.calls, [])

    def test_lua_schema_without_started_is_upgraded(self):
        other = Path(self.temp.name) / "lua.db"
        with closing(sqlite3.connect(other, isolation_level=None)) as connection:
            connection.execute("CREATE TABLE requests(id INTEGER PRIMARY KEY, status TEXT)")
        initialize_database(other)
        with closing(sqlite3.connect(other, isolation_level=None)) as connection:
            columns = [row[1] for row in connection.execute("PRAGMA table_info(requests)")]
        self.assertIn("started", columns)


if __name__ == "__main__":
    unittest.main()
