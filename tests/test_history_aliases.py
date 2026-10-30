"""Real Lua 5.1 + SQLite checks for owner-scoped names and encounter summaries."""
import sqlite3
import unittest
from pathlib import Path

from lupa.lua51 import LuaRuntime


class HistoryAliasesTests(unittest.TestCase):
    steam = "76561198000000001"
    owner = "steam:76561198000000002"

    def setUp(self):
        self.db = sqlite3.connect(":memory:", isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute((Path(__file__).resolve().parents[1] / "DLC/InGameTranslateMod/UI/IGT_History.lua").read_text(encoding="utf-8"))
        self.h = self.lua.globals().IGT_History.Open(self.query)

    def tearDown(self):
        self.db.close()

    def query(self, sql):
        rows = self.db.execute(sql).fetchall()
        return self.lua.table_from([self.lua.table_from(dict(row)) for row in rows])

    def names(self, array):
        return [array[i] for i in range(1, len(array) + 1)]

    def observe(self, game, name, turn=1, steam=None):
        p = {"name": name, "civ": "Korea", "steamID": self.steam if steam is None else steam}
        return self.h.Observe(game, self.owner, turn, "Rome", self.lua.table_from([self.lua.table_from(p)]))

    def test_aliases_record_without_games_and_are_owner_scoped(self):
        self.assertTrue(self.h.NoteName(self.owner, "Old nickname", self.steam))
        self.assertTrue(self.h.NoteName(self.owner, "Current nickname", self.steam))
        self.h.NoteName("other owner", "Other private nickname", self.steam)
        result = self.h.Summary(self.owner, "steam:" + self.steam, "Current nickname", None)
        self.assertEqual(result.games, 0)
        self.assertEqual(self.names(result.names), ["Old nickname"])

    def test_per_game_names_survive_renames_and_repeated_observations(self):
        game1 = self.h.New(self.owner, "First", "Pangaea")
        self.observe(game1, "First name")
        self.observe(game1, "Second name", 5)
        self.observe(game1, "Second name", 6)
        game2 = self.h.New(self.owner, "Second", "Continents")
        self.observe(game2, "Third name")
        rows = self.h.Encounters(self.owner, "steam:" + self.steam)
        by_game = {int(rows[i].game_id): self.names(rows[i].names) for i in range(1, len(rows) + 1)}
        self.assertEqual(by_game, {game1: ["First name", "Second name"], game2: ["Third name"]})
        summary = self.h.Summary(self.owner, "steam:" + self.steam, "Third name", game2)
        self.assertEqual(summary.games, 1)
        self.assertEqual(self.names(summary.names), ["First name", "Second name"])
        self.assertEqual(self.h.Summary(self.owner, "steam:" + self.steam, "Third name", None).games, 2)

    def test_invalid_or_missing_native_id_does_not_create_account_alias(self):
        for bad in [None, "", "123", 76561198000000001, "00000000000000000"]:
            self.assertFalse(self.h.NoteName(self.owner, "Name", bad))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM igt_seen_names").fetchone()[0], 0)

    def test_summary_reads_legacy_names_and_open_backfills_per_game_names(self):
        game = self.h.New(self.owner, "Legacy", "Pangaea")
        self.db.execute("INSERT INTO igt_encounters VALUES(?,?,?,?,?,?,datetime('now'),datetime('now'),1,7)",
                        (game, "steam:" + self.steam, self.steam, "Legacy name", "Rome", "Korea"))
        result = self.h.Summary(self.owner, "steam:" + self.steam, "New name", None)
        self.assertEqual((result.games, self.names(result.names)), (1, ["Legacy name"]))
        self.h = self.lua.globals().IGT_History.Open(self.query)
        self.observe(game, "New name", 9)
        self.assertEqual(self.names(self.h.Encounters(self.owner, "steam:" + self.steam)[1].names), ["Legacy name", "New name"])

    def test_late_account_lookup_preserves_current_game_names(self):
        game = self.h.New(self.owner, "Late lookup", "Pangaea")
        p = self.lua.table_from({"name": "O'Brien 한국", "civ": "Korea"})
        self.h.Observe(game, self.owner, 1, "Rome", self.lua.table_from([p]))
        self.observe(game, "O'Brien 한국", 2)
        self.observe(game, "Renamed", 3)
        rows = self.h.Encounters(self.owner, "steam:" + self.steam)
        self.assertEqual(len(rows), 1)
        self.assertEqual(self.names(rows[1].names), ["O'Brien 한국", "Renamed"])
        self.assertEqual(self.h.Summary(self.owner, "steam:" + self.steam, "Renamed", None).games, 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM igt_game_names WHERE player_key LIKE 'name:%'").fetchone()[0], 0)

    def test_other_owner_game_counts_and_names_are_not_exposed(self):
        other_game = self.h.New("other owner", "Other game", "Map")
        p = self.lua.table_from({"name": "Other owner history", "steamID": self.steam, "civ": "Korea"})
        self.h.Observe(other_game, "other owner", 1, "Rome", self.lua.table_from([p]))
        summary = self.h.Summary(self.owner, "steam:" + self.steam, "Current", None)
        self.assertEqual((summary.games, len(summary.names)), (0, 0))
        self.assertEqual(len(self.h.Encounters(self.owner, "steam:" + self.steam)), 0)


if __name__ == "__main__":
    unittest.main()
