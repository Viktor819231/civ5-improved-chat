-- Local journal. A game record is explicitly started/resumed because the
-- vanilla UI has no verified persistent game GUID. Reloads never guess.
IGT_History = {};

function IGT_History.SteamID(playerID)
    if not Steam or type(Steam.GetPlayerSteamID) ~= "function" then return nil; end
    local ok, info = pcall(Steam.GetPlayerSteamID, playerID);
    -- The installed Windows game's Lua binding returns { ID = decimal string,
    -- PlayerName = ..., IsOnline = ... }. Never round a 64-bit ID through Lua numbers.
    if not ok or type(info) ~= "table" then return nil; end
    local id = info.ID;
    if type(id) == "string" and #id == 17 and id:match("^%d+$") and id ~= "00000000000000000" then return id; end
    return nil;
end

function IGT_History.Key(name, steamID)
    return steamID and ("steam:" .. steamID) or ("name:" .. name);
end

function IGT_History.Open(query)
    local h = {};
    local function q(value) return "'" .. tostring(value or ""):gsub("'", "''") .. "'"; end
    query("CREATE TABLE IF NOT EXISTS igt_account_profiles(steam_id TEXT PRIMARY KEY,original_name TEXT NOT NULL,alias TEXT NOT NULL,note TEXT NOT NULL)");
    query("CREATE TABLE IF NOT EXISTS igt_games(id INTEGER PRIMARY KEY AUTOINCREMENT,owner_key TEXT NOT NULL,title TEXT NOT NULL,map TEXT NOT NULL,created_utc TEXT NOT NULL,last_utc TEXT NOT NULL)");
    query("CREATE TABLE IF NOT EXISTS igt_encounters(game_id INTEGER NOT NULL,player_key TEXT NOT NULL,steam_id TEXT NOT NULL,original_name TEXT NOT NULL,my_civ TEXT NOT NULL,their_civ TEXT NOT NULL,first_utc TEXT NOT NULL,last_utc TEXT NOT NULL,first_turn INTEGER NOT NULL,last_turn INTEGER NOT NULL,PRIMARY KEY(game_id,player_key))");
    query("CREATE TABLE IF NOT EXISTS igt_seen_names(owner_key TEXT NOT NULL,player_key TEXT NOT NULL,original_name TEXT NOT NULL,first_utc TEXT NOT NULL,last_utc TEXT NOT NULL,PRIMARY KEY(owner_key,player_key,original_name))");
    query("CREATE TABLE IF NOT EXISTS igt_game_names(game_id INTEGER NOT NULL,player_key TEXT NOT NULL,original_name TEXT NOT NULL,PRIMARY KEY(game_id,player_key,original_name))");
    -- Older versions kept only the most recently observed name per game.
    -- Preserve what remains; earlier overwritten names cannot be reconstructed.
    query("INSERT OR IGNORE INTO igt_game_names SELECT game_id,player_key,original_name FROM igt_encounters");

    function h.NoteName(owner, name, steamID)
        -- This is local native-ID observation, not server authentication.
        if type(owner) ~= "string" or owner == "" or type(name) ~= "string" or name == "" or
            type(steamID) ~= "string" or #steamID ~= 17 or not steamID:match("^%d+$") or steamID == "00000000000000000" then return false; end
        local key = IGT_History.Key(name, steamID);
        query("INSERT OR IGNORE INTO igt_seen_names VALUES(" .. q(owner) .. "," .. q(key) .. "," .. q(name) .. ",datetime('now'),datetime('now'))");
        query("UPDATE igt_seen_names SET last_utc=datetime('now') WHERE owner_key=" .. q(owner) .. " AND player_key=" .. q(key) .. " AND original_name=" .. q(name));
        return true;
    end

    function h.New(owner, title, map)
        query("INSERT INTO igt_games(owner_key,title,map,created_utc,last_utc) VALUES(" .. q(owner) .. "," .. q(title) .. "," .. q(map) .. ",datetime('now'),datetime('now'))");
        return tonumber(query("SELECT last_insert_rowid() AS id")[1].id);
    end

    function h.Games(owner)
        return query("SELECT * FROM igt_games WHERE owner_key=" .. q(owner) .. " ORDER BY id DESC");
    end

    function h.Observe(gameID, owner, turn, myCiv, participants)
        turn = math.floor(assert(tonumber(turn), "Game turn is unavailable"));
        local game = query("SELECT id FROM igt_games WHERE id=" .. q(gameID) .. " AND owner_key=" .. q(owner));
        if #game == 0 then return false; end
        query("BEGIN TRANSACTION");
        local ok, err = pcall(function()
            for _, p in ipairs(participants) do
                local key = IGT_History.Key(p.name, p.steamID);
                -- A late Steam lookup upgrades a name-only row in THIS record.
                -- Other games are not silently linked by a possibly shared name.
                if p.steamID and not p.duplicate then
                    local prior = query("SELECT * FROM igt_encounters WHERE game_id=" .. q(gameID) .. " AND player_key=" .. q("name:" .. p.name));
                    if #prior > 0 then
                        query("UPDATE OR IGNORE igt_encounters SET player_key=" .. q(key) .. ",steam_id=" .. q(p.steamID) .. " WHERE game_id=" .. q(gameID) .. " AND player_key=" .. q("name:" .. p.name));
                        local old = prior[1];
                        query("UPDATE igt_encounters SET first_turn=MIN(first_turn," .. tonumber(old.first_turn) .. "),last_turn=MAX(last_turn," .. tonumber(old.last_turn) .. "),first_utc=MIN(first_utc," .. q(old.first_utc) .. ") WHERE game_id=" .. q(gameID) .. " AND player_key=" .. q(key));
                        query("DELETE FROM igt_encounters WHERE game_id=" .. q(gameID) .. " AND player_key=" .. q("name:" .. p.name));
                        query("INSERT OR IGNORE INTO igt_game_names SELECT game_id," .. q(key) .. ",original_name FROM igt_game_names WHERE game_id=" .. q(gameID) .. " AND player_key=" .. q("name:" .. p.name));
                        query("DELETE FROM igt_game_names WHERE game_id=" .. q(gameID) .. " AND player_key=" .. q("name:" .. p.name));
                    end
                end
                if p.steamID or not p.duplicate then
                    query("INSERT OR IGNORE INTO igt_encounters VALUES(" .. q(gameID) .. "," .. q(key) .. "," .. q(p.steamID) .. "," .. q(p.name) .. "," .. q(myCiv) .. "," .. q(p.civ) .. ",datetime('now'),datetime('now')," .. q(turn) .. "," .. q(turn) .. ")");
                    query("UPDATE igt_encounters SET original_name=" .. q(p.name) .. ",my_civ=" .. q(myCiv) .. ",their_civ=" .. q(p.civ) .. ",last_utc=datetime('now'),first_turn=MIN(first_turn," .. turn .. "),last_turn=MAX(last_turn," .. turn .. ") WHERE game_id=" .. q(gameID) .. " AND player_key=" .. q(key));
                    query("INSERT OR IGNORE INTO igt_game_names VALUES(" .. q(gameID) .. "," .. q(key) .. "," .. q(p.name) .. ")");
                    if p.steamID then h.NoteName(owner,p.name,p.steamID); end
                end
            end
            query("UPDATE igt_games SET last_utc=datetime('now') WHERE id=" .. q(gameID));
        end);
        if ok then query("COMMIT"); else query("ROLLBACK"); error(err); end
        return true;
    end

    function h.Players(owner)
        return query("SELECT e.player_key,e.steam_id,(SELECT e2.original_name FROM igt_encounters e2 JOIN igt_games g2 ON g2.id=e2.game_id WHERE e2.player_key=e.player_key AND g2.owner_key=" .. q(owner) .. " ORDER BY e2.last_utc DESC,e2.game_id DESC LIMIT 1) AS original_name,COUNT(DISTINCT e.game_id) AS games,MIN(e.first_utc) AS first_utc,MAX(e.last_utc) AS last_utc FROM igt_encounters e JOIN igt_games g ON g.id=e.game_id WHERE g.owner_key=" .. q(owner) .. " GROUP BY e.player_key,e.steam_id ORDER BY last_utc DESC,e.player_key");
    end

    function h.Encounters(owner, key)
        local rows = query("SELECT e.*,g.title,g.map FROM igt_encounters e JOIN igt_games g ON g.id=e.game_id WHERE g.owner_key=" .. q(owner) .. " AND e.player_key=" .. q(key) .. " ORDER BY e.last_utc DESC,e.game_id DESC");
        for _, row in ipairs(rows) do
            row.names = {};
            for _, name in ipairs(query("SELECT original_name FROM igt_game_names WHERE game_id=" .. q(row.game_id) .. " AND player_key=" .. q(key) .. " UNION SELECT " .. q(row.original_name) .. " AS original_name ORDER BY original_name")) do row.names[#row.names + 1] = name.original_name; end
        end
        return rows;
    end

    function h.Summary(owner, key, currentName, excludeGameID)
        local filter = excludeGameID and (" AND e.game_id<>" .. q(excludeGameID)) or "";
        local count = query("SELECT COUNT(DISTINCT e.game_id) AS games FROM igt_encounters e JOIN igt_games g ON g.id=e.game_id WHERE g.owner_key=" .. q(owner) .. " AND e.player_key=" .. q(key) .. filter);
        local result = { games = tonumber(count[1].games), names = {} };
        local names = query("SELECT original_name FROM igt_seen_names WHERE owner_key=" .. q(owner) .. " AND player_key=" .. q(key) ..
            " UNION SELECT e.original_name FROM igt_encounters e JOIN igt_games g ON g.id=e.game_id WHERE g.owner_key=" .. q(owner) .. " AND e.player_key=" .. q(key) ..
            " UNION SELECT n.original_name FROM igt_game_names n JOIN igt_games g ON g.id=n.game_id WHERE g.owner_key=" .. q(owner) .. " AND n.player_key=" .. q(key) .. " ORDER BY original_name");
        for _, row in ipairs(names) do if row.original_name ~= currentName then result.names[#result.names + 1] = row.original_name; end end
        return result;
    end
    return h;
end
