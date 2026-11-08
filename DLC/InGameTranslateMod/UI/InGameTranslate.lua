-- InGameTranslateMod: translates in the game's own chat through a small hook in a
-- generated copy of its chat script (tools/chat_hooks.py). Nothing is copied from EUI.
-- When that hook does not answer, this same file runs as a separate overlay window.
print("IGT shared script loaded (0.8 chat journal)");
-- It runs with any mod or DLC. A mod that replaces the game's chat script leaves
-- no hook to answer, so this file then stays the separate window.
local switchedOff = false;
local DetachNativeChat;
local function SwitchOff(reason)
    switchedOff = true;
    if DetachNativeChat then DetachNativeChat(); end
    Controls.Panel:SetHide(true);
    if Controls.EmojiPanel then Controls.EmojiPanel:SetHide(true);end
    if Controls.PlayerMenu then Controls.PlayerMenu:SetHide(true);end
    if Controls.ForcePanel then Controls.ForcePanel:SetHide(true); end
    Controls.Toggle:SetHide(true);
    Controls.Toggle:SetDisabled(true);
    Controls.Toggle:SetToolTipString(reason);
    print("Improved Chat switched off: " .. reason);
end

IGT_Config = false; -- PERSONALIZED_DOWNLOAD_CONFIG
include("IGT_Text");
include("IGT_Crypto");
include("IGT_Native");
include("IGT_History");
local isLobby = IGT_LOBBY == true;
local function LocalPlayer()
    if isLobby then return Matchmaking.GetLocalID(); end
    return Game.GetActivePlayer();
end

-- The game's own chat, once its hook has answered. Chat rows and the box the
-- player types in then belong to the game; this file only changes their text.
local nativeChat;
local rowStack, rowScroll = Controls.TranscriptStack, Controls.TranscriptScroll;
local function Draft() return nativeChat and nativeChat.Controls.ChatEntry or Controls.Draft; end

local db;
local native;
local requestTable = IGT_Config and "native_requests" or "requests";
local session = "";
local pending = {};
local chatRows = {};
local lastTranslation = "";
-- New languages are appended so saved positions and older lists stay valid.
local sourceLanguages = { "auto", "en", "ru", "uk", "ko", "ru-latn", "zh", "ja", "de", "fr", "es", "pt", "it", "pl", "tr",
    "be", "kk", "cs", "sk", "nl", "sv", "da", "no", "fi", "hu", "ro", "bg", "sr", "hr", "vi", "id", "mn" };
-- Civ V has no Arabic or Greek font, so those are read-only languages.
local targetLanguages = { "ru", "uk", "ko", "en", "ru-latn", "zh", "ja", "de", "fr", "es", "pt", "it", "pl", "tr",
    "be", "kk", "cs", "sk", "nl", "sv", "da", "no", "fi", "hu", "ro", "bg", "sr", "hr", "vi", "id", "mn" };
-- My language: the ten languages Civ V ships, whose letters its fonts can show,
-- and Mongolian, which Civ V draws with its Russian font.
local incomingLanguages = { "en", "ru", "ko", "de", "fr", "es", "it", "pl", "ja", "zh", "mn" };
local readerScripts = { en="latin", de="latin", fr="latin", es="latin", it="latin", pl="latin", ru="cyrillic", ko="hangul", ja="kana", zh="han", mn="cyrillic" };
local readerLanguage = "en";
local sourceIndex, targetIndex = 1, 1;
local receiving = true;
local recipientID = -1;
local selectedRecipientName;
local recipientNames = {};
local recipientSignature = "";
local translateOnSend = IGT_Config ~= false;
local submissionGeneration = 0;
local rosterElapsed = 0;
local selectedIcon = "";
local colorIndex = 1;
local colors = {
    { "color.default", "" }, { "color.red", "COLOR_RED" }, { "color.green", "COLOR_GREEN" },
    { "color.cyan", "COLOR_CYAN" }, { "color.yellow", "COLOR_YELLOW" },
    { "color.magenta", "COLOR_MAGENTA" }, { "color.white", "COLOR_WHITE" }, { "color.blue", "COLOR_BLUE" }
};
local translatedDraft;
local translatedSource;
local draftGeneration = 0;
local sendQueue = {};
local sendDelay = 0.8;
local elapsed = 0;
local pasteCounter = 0;
local pasteToken;
local statusText = IGT_Text.T("en", "status.companion");
local initialized = false;
local Initialize;
local ErrorText;
local RefreshRecipients;
local expanded = false;
local expectedEchoes = {};
local profiles = {};
local duplicateNames = {};
local editingName;
local OpenProfiles;
local accountProfiles = {};
local nameAccounts = {};
local editingSteam;
local activePage = "chat";
local opacityIndex = 1;
local opacities = { 0.80, 0.96, 1 };
local transcriptWidth = 495;
local history;
local activeGame;
local selectedGame;
local selectedHistoryKey;
local historyElapsed = 0;
local historySignature;
local historyOwner;
local RefreshHistory;
local ShowPage;
local TranslateRow;
local forceRow;
local forceSource;
local manualLanguages = { "ru", "ru-latn", "uk", "ko", "fr", "de", "es", "pl", "pt", "tr", "it", "nl", "sv", "zh", "ja", "ar",
    "en", "be", "kk", "cs", "sk", "da", "no", "fi", "hu", "ro", "bg", "sr", "hr", "el", "vi", "id", "mn" };
local windowPositions = {};
local panelBounds;
local dragging;
local expandedWidth,expandedHeight=960,700;
local lastScreenW,lastScreenH;
local syncingSize=false;
local announcedPlayers={};
local contextPlayer;
local historyPerson;
-- Spam guard: automatic translations are rationed per sender and in total, so
-- a flood of chat can neither use up the daily allowance nor delay your own
-- messages. Every message keeps its Translate button for a manual request.
local AUTO_BURST, AUTO_REFILL_SECONDS, AUTO_WAITING, AUTO_MAX_BYTES = 4, 6, 6, 600;
local autoBudget = {};
local autoPausedUntil = 0;
local clock = 0;
local recentTranslations, recentOrder = {}, {};

local function IndexOf(list, value)
    for i, item in ipairs(list) do if item == value then return i; end end
end
-- Civ V draws text with the font of its own language. Following the game's
-- language means every letter of this window and its translations can show.
local function GameLanguage()
    local ok, info = pcall(function() return Locale.GetCurrentLanguage(); end);
    local code = ok and type(info) == "table" and tostring(info.Type or ""):sub(1, 2):lower() or "";
    return IndexOf(incomingLanguages, code) and code or "en";
end
-- The window speaks My language when the game's font can draw it. The English
-- font has Western European letters only, so other alphabets need the game
-- itself in that language; otherwise the window stays readable in English.
local westernLetters = { en=true, de=true, fr=true, es=true, it=true };
-- Civ V has no Mongolian version: Mongolian players run it in Russian and get the Russian window.
local windowFallback = { mn="ru" };
local windowLanguage = "en";
local function UpdateWindowLanguage()
    local game = GameLanguage();
    local wanted = windowFallback[readerLanguage] or readerLanguage;
    windowLanguage = (wanted == game or (westernLetters[wanted] and westernLetters[game])) and wanted or "en";
end
local function T(key, ...) return IGT_Text.T(windowLanguage, key, ...); end
local function LanguageName(code) return T("lang." .. tostring(code)); end

local function Quote(value)
    return "'" .. tostring(value or ""):gsub("'", "''") .. "'";
end

-- Fully consume every iterator so no read transaction is kept open.
local function Query(sql)
    local rows = {};
    for row in db.Query(sql) do rows[#rows + 1] = row; end
    return rows;
end

local function State(key, value)
    Query("INSERT OR REPLACE INTO igt_state(key,value) VALUES(" .. Quote(key) .. "," .. Quote(value) .. ")");
end

local function SetStatus(text)
    statusText = tostring(text or "");
    Controls.ActionStatus:SetText(IGT_Text.SafeDisplay(statusText));
end

local function Safe(action)
    local ok, err = pcall(action);
    if not ok then
        SetStatus(T("status.error", tostring(err)));
        print("InGameTranslateMod: " .. tostring(err));
    end
    return ok;
end

local function PlayerName(id)
    if isLobby then
        local name = PreGame.GetNickName(id);
        return name and name ~= "" and name or T("player.n", id);
    end
    local player = Players and Players[id];
    if not player then return T("player.n", id); end
    local name = player:GetNickName();
    if not name or name == "" then name = player:GetName(); end
    return name;
end

-- Name matching is explicit: the vanilla UI exposes no verified IP identity.
-- Keep raw network names separate from local aliases and all routing checks.
local function PlainText(text)
    return tostring(text or ""):gsub("[\r\n\t]", " "):gsub("%[", "("):gsub("%]", ")");
end

local function ProfileFor(name, steamID)
    steamID = steamID or (not duplicateNames[name] and nameAccounts[name]);
    return steamID and accountProfiles[steamID] or (not duplicateNames[name] and profiles[name]);
end

local function DisplayName(name, steamID)
    local profile = ProfileFor(name, steamID);
    return profile and profile.alias ~= "" and (name .. "(" .. profile.alias .. ")") or name;
end

local function ProfileTooltip(name, steamID)
    steamID = steamID or (not duplicateNames[name] and nameAccounts[name]);
    local profile = ProfileFor(name, steamID);
    return T("profile.original", PlainText(name)) .. "[NEWLINE]" ..
        (steamID and T("profile.steam", steamID) or T("profile.name.only")) .. "[NEWLINE]" ..
        (duplicateNames[name] and not steamID and T("profile.duplicate") or
        (profile and profile.note ~= "" and T("profile.note", PlainText(profile.note)) or T("profile.no.note")));
end

local function TurnStamp()
    if isLobby then return T("lobby"); end
    return T("turn", Game.GetGameTurn());
end

-- The game releases its oldest rows on its own and tells this file first, through
-- igtGone; a row that is gone must never be touched again.
local function RowIsLive(row)
    if row.igtGone then return false; end
    for _, active in ipairs(chatRows) do if active == row then return true; end end
    return false;
end

local function FitRow(row)
    local height = nativeChat and row.Message:GetSizeY() + nativeChat.RowPadding or math.max(24, row.Message:GetSizeY() + 8);
    row.Box:SetSizeY(height);
    if row.Hit then row.Hit:SetSizeY(height); end
    row.Box:ReprocessAnchoring();
end

local function RefreshTranscript()
    rowStack:CalculateSize();
    rowScroll:CalculateInternalSize();
end

local function TrackRow(row)
    chatRows[#chatRows + 1] = row;
    while chatRows[1] and chatRows[1].igtGone do table.remove(chatRows, 1); end
    if not nativeChat and #chatRows > 100 then
        rowStack:ReleaseChild(chatRows[1].Box);
        table.remove(chatRows, 1);
    end
end

local function AddLine(text, stamp, channelColor)
    local row;
    if nativeChat then
        row = nativeChat.NewRow();
        row.Message = row.String;
    else
        row = {};
        ContextPtr:BuildInstanceForControl("IGTChatRow", row, Controls.TranscriptStack);
        row.Message:SetWrapWidth(transcriptWidth);
        row.Box:SetSizeX(transcriptWidth + 104);
        row.TranslateButton:SetHide(true);
    end
    row.stamp = stamp == nil and TurnStamp() or stamp;
    row.channelColor = channelColor;
    row.Message:SetText(IGT_Text.SafeDisplay(text));
    if row.channelColor then row.Message:SetColorByName(row.channelColor); end
    row.Message:SetToolTipString(row.stamp);
    FitRow(row);
    TrackRow(row);
    RefreshTranscript();
    rowScroll:SetScrollValue(1);
    return row;
end

local function UpdateLine(row, text)
    if not row then return AddLine(text); end
    -- A response can arrive after a busy transcript has evicted its row.
    if not RowIsLive(row) then return; end
    row.Message:SetText(IGT_Text.SafeDisplay(text));
    if row.channelColor then row.Message:SetColorByName(row.channelColor); end
    FitRow(row);
    RefreshTranscript();
end

-- The game already wrote "Name: " or "Name (To You): " on its own row. Keep that
-- wording and only add a local nickname to it.
local function NativePrefix(chat)
    local first, last = chat.nativePrefix:find(chat.name, 1, true);
    if not first then return chat.nativePrefix; end
    return chat.nativePrefix:sub(1, first - 1) .. DisplayName(chat.name, chat.steamID) .. chat.nativePrefix:sub(last + 1);
end

local function RowTooltip(row)
    local chat = row.chat;
    local tip = (row.stamp ~= "" and (row.stamp .. "[NEWLINE]") or "") .. ProfileTooltip(chat.targetName or chat.name, chat.targetName and chat.targetSteam or chat.steamID);
    if nativeChat and chat.translated and not row.showOriginal then
        tip = T("original") .. ": " .. IGT_Text.SafeDisplay(chat.original) .. "[NEWLINE]" .. tip;
    end
    (row.Hit or row.Message):SetToolTipString(tip);
end

local function RenderChat(row)
    if not RowIsLive(row) then return; end
    local chat = row.chat;
    if chat.nativePrefix then
        UpdateLine(row, (chat.prefix or "") .. NativePrefix(chat) .. chat.text);
    else
        local name = chat.own and T("you") or DisplayName(chat.name, chat.steamID);
        if chat.targetName then name = name .. " -> " .. DisplayName(chat.targetName, chat.targetSteam); end
        UpdateLine(row, (chat.prefix or "") .. name .. chat.audience .. ": " .. chat.text);
    end
    RowTooltip(row);
end

local function RefreshChatNames()
    for _, row in ipairs(chatRows) do if row.chat then RenderChat(row); end end
end

local function ResizeOverlay()
    Controls.EmojiPanel:SetHide(true);Controls.PlayerMenu:SetHide(true);
    local screenW, screenH = 1280, 900;
    if UIManager and UIManager.GetScreenSizeVal then screenW, screenH = UIManager:GetScreenSizeVal(); end
    lastScreenW,lastScreenH=screenW,screenH;
    local w = expanded and math.min(expandedWidth, screenW - 48) or math.min(550,screenW-24);
    local h = expanded and math.min(expandedHeight, screenH - 70) or math.min(400,screenH-48);
    local position = windowPositions[expanded and "expanded" or "compact"];
    local x = position and position.x or (expanded and (screenW-w)/2 or screenW-w-10);
    local y = position and position.y or (expanded and (screenH-h)/2 or 30);
    x,y=math.max(0,math.min(x,screenW-w)),math.max(0,math.min(y,screenH-h));
    panelBounds={x=x,y=y,w=w,h=h}; dragging=nil;
    Controls.Panel:SetAnchor("L,T");
    Controls.Panel:SetOffsetVal(x,y);
    Controls.Toggle:SetAnchor("L,T"); Controls.Toggle:SetOffsetVal(x+w-160,y);
    local dragStart = expanded and 8 or 124;
    Controls.HeaderDrag:SetOffsetVal(dragStart,0);
    Controls.HeaderDrag:SetSizeVal(math.max(30,w-248-dragStart),28);
    Controls.Panel:SetSizeVal(w, h);
    Controls.PanelBackdrop:SetSizeVal(w, h);
    Controls.PanelBackdrop:SetAlpha(opacities[opacityIndex]);
    Controls.ChatPage:SetSizeVal(w, h);
    Controls.TabBar:SetHide(not expanded);
    Controls.PlayerNotes:SetHide(expanded);
    local transcriptTop = expanded and 72 or 40;
    Controls.TranscriptScroll:SetOffsetVal(12, transcriptTop);
    Controls.TranscriptScroll:SetSizeVal(w - 40, h - transcriptTop - 112);
    transcriptWidth = w - 149;
    if not nativeChat then
        for _, row in ipairs(chatRows) do
            row.Message:SetWrapWidth(transcriptWidth); row.Box:SetSizeX(transcriptWidth + 104);
            FitRow(row);
        end
    end
    Controls.DraftBox:SetOffsetVal(12, h - 100); Controls.DraftBox:SetSizeX(w - 24);
    Controls.DraftBorder:SetSizeX(w - 224); Controls.DraftBackground:SetSizeX(w - 226); Controls.Draft:SetSizeX(w - 230);
    Controls.ComposerButtons:SetOffsetVal(10, h - 66); Controls.ComposerButtons:SetSizeX(w - 20);
    Controls.ActionStatus:SetOffsetVal(12, h - 34); Controls.ActionStatus:SetWrapWidth(w - 30);
    Controls.HistoryPage:SetSizeVal(w - 24, h - 150);
    Controls.HistoryScroll:SetOffsetVal(0,146);
    Controls.HistoryScroll:SetSizeVal(w - 48, h - 450);
    Controls.HistoryText:SetWrapWidth(w - 70);
    Controls.HistorySummary:SetWrapWidth(w - 40);
    Controls.HistoryFooter:SetOffsetVal(0, h - 290);
    Controls.HistoryFooter:SetSizeX(w - 24);
    Controls.HistoryStatus:SetWrapWidth(w - 40); Controls.HistoryHelp:SetWrapWidth(w - 40);
    local gameWidth = math.max(170, w - 540);
    Controls.HistoryGame:SetSizeX(gameWidth);
    Controls.HistoryNew:SetOffsetVal(gameWidth + 10, 42);
    Controls.HistoryResume:SetOffsetVal(gameWidth + 166, 42);
    Controls.HistoryStop:SetOffsetVal(gameWidth + 330, 42);
    Controls.ExpandLabel:SetText(expanded and T("compact") or T("expand"));
    Controls.WindowDimensions:SetText(T("current.size", w, h));
    syncingSize=true;
    Controls.WidthSlider:SetValue((expandedWidth-700)/900);
    Controls.HeightSlider:SetValue((expandedHeight-620)/380);
    syncingSize=false;
    Controls.PreviewScroll:SetOffsetVal(12,math.min(460,h-180));
    Controls.TranscriptStack:CalculateSize();
    Controls.Panel:ReprocessAnchoring();
    Controls.TranscriptScroll:CalculateInternalSize();
end

local function MinimizeWindow()
    Controls.Panel:SetHide(true); Controls.Settings:SetHide(true); Controls.ProfilesPanel:SetHide(true);
    Controls.EmojiPanel:SetHide(true); Controls.PlayerMenu:SetHide(true); Controls.ForcePanel:SetHide(true);
    forceRow = nil;
    Controls.Toggle:SetHide(nativeChat ~= nil);
end

ShowPage = function(page, compact)
    -- With the game's chat this window holds only notes, history and settings.
    if nativeChat and page == "chat" then MinimizeWindow(); return; end
    activePage, expanded = page, not compact;
    Controls.ChatPage:SetHide(page ~= "chat");
    Controls.ProfilesPanel:SetHide(page ~= "notes");
    Controls.HistoryPage:SetHide(page ~= "history");
    Controls.Settings:SetHide(page ~= "settings");
    for _, tab in ipairs({{"ChatTabLabel","chat","tab.chat"},{"NotesTabLabel","notes","tab.notes"},{"HistoryTabLabel","history","tab.history"},{"SettingsTabLabel","settings","tab.settings"}}) do
        Controls[tab[1]]:SetText(page == tab[2] and ("( " .. T(tab[3]) .. " )") or T(tab[3]));
    end
    ResizeOverlay();
end

local function Preview(text)
    Controls.PreviewText:SetText(IGT_Text.SafeDisplay(text));
    Controls.PreviewScroll:CalculateInternalSize();
end

local function InvalidateDraft()
    draftGeneration = draftGeneration + 1;
    translatedDraft = nil;
    translatedSource = nil;
    Controls.SendTranslated:SetDisabled(true);
    Preview(T("preview.hint"));
end

local function RefreshSendState()
    local busy = #sendQueue > 0;
    for _, info in pairs(pending) do
        if info.autoSend and info.generation == submissionGeneration then busy = true; break; end
    end
    Controls.CancelSend:SetDisabled(not busy);
    Controls.CancelSend:SetHide(not busy);
    Controls.Paste:SetHide(busy or IGT_Config ~= false);
end

local function RefreshLabels()
    Controls.Source:GetButton():SetText(LanguageName(sourceLanguages[sourceIndex]));
    Controls.Target:GetButton():SetText(T("send.in", LanguageName(targetLanguages[targetIndex])));
    Controls.Target:GetButton():SetToolTipString(T("tip.target"));
    Controls.Incoming:GetButton():SetText(LanguageName(readerLanguage));
    Controls.Incoming:GetButton():SetToolTipString(T("tip.reader"));
    local recipientSteam = recipientID ~= -1 and IGT_History.SteamID(recipientID) or nil;
    Controls.Recipient:GetButton():SetText(recipientID == -1 and T("to.all") or T("to.player", IGT_Text.StripColors(DisplayName(selectedRecipientName or T("player.left"), recipientSteam)) .. (recipientNames[recipientID] ~= selectedRecipientName and T("left.suffix") or "")));
    Controls.Recipient:GetButton():SetToolTipString(recipientID == -1 and T("tip.to.all") or ProfileTooltip(selectedRecipientName, recipientSteam));
    Controls.SendModeLabel:SetText(translateOnSend and T("translate.on") or T("translate.off"));
    if nativeChat then
        local code = targetLanguages[targetIndex];
        Controls.SendLanguage:GetButton():SetText("TR: " .. (translateOnSend and code:upper():gsub("%-LATN$", "-L") or "-"));
        Controls.SendLanguage:GetButton():SetToolTipString(translateOnSend and (T("send.in", LanguageName(code)) .. "[NEWLINE]" .. T("tip.target")) or T("translate.off"));
    end
    Controls.ReceiveLabel:SetText(receiving and T("auto.on") or T("auto.off"));
    Controls.PrefixLabel:SetText(T("prefix", selectedIcon ~= "" and selectedIcon or T("prefix.none")));
    Controls.MessageColorLabel:SetText(IGT_Text.Colorize(T("colour", T(colors[colorIndex][1])), colors[colorIndex][2]));
end

-- Fixed labels of the layout, in the reader's language.
local fixedTexts = { DragHint="drag", MinimizeText="minimize", PlayerNotesText="notes", SendText="send", PasteText="paste",
    CancelSendText="cancel", MoreText="settings", SettingsTitle="settings.title", CloseSettingsText="close",
    TranslateText="preview", SendTranslatedText="send.preview", CopyLastText="copy.last", ClearPrefixText="no.icon",
    TestText="test", SettingsHelp="settings.help", SourceCaption="source.caption", IncomingCaption="reader.caption",
    CopyDraftText="copy.draft", TranslationPrivacy="privacy", WindowSizeTitle="window.size", SizeSmallText="small",
    SizeMediumText="medium", SizeLargeText="large", WidthCaption="width", HeightCaption="height", WindowHelp="window.help",
    ProfilesTitle="notes.title", CloseProfilesText="close", AliasCaption="alias.caption", NoteCaption="note.caption",
    ProfileSaveText="save.local", ProfileDeleteText="clear.saved", NotesPrivacy="notes.privacy", HistoryTitle="history.title",
    HistoryNewText="history.new", HistoryResumeText="history.resume", HistoryStopText="history.stop", HistoryHelp="history.help",
    ForceGoText="translate", ForceCancelText="cancel", EmojiTitle="emoji.title", EmojiCloseText="close",
    PlayerMenuNoteText="menu.note", PlayerMenuDetailsText="menu.details", PlayerMenuCloseText="close" };
local fixedTips = { Toggle="tip.toggle", HeaderDrag="tip.drag", Minimize="tip.minimize", PlayerNotes="tip.notes",
    EmojiButton="tip.emoji", SettingsEmoji="tip.emoji", ChatSettings="settings", SendMode="tip.sendmode", SendOriginal="tip.send", Translate="tip.preview", Test="tip.test",
    MessageColor="tip.color", Receive="tip.auto", IconGold="icon.gold", IconFood="icon.food", IconProduction="icon.production",
    IconScience="icon.science", IconCulture="icon.culture", IconFaith="icon.faith", IconHappiness="icon.happiness",
    IconMoves="icon.moves", IconStrength="icon.strength", EmojiGold="icon.gold", EmojiFood="icon.food",
    EmojiProduction="icon.production", EmojiScience="icon.science", EmojiCulture="icon.culture", EmojiFaith="icon.faith",
    EmojiHappiness="icon.happiness", EmojiMoves="icon.moves", EmojiStrength="icon.strength" };
local function ApplyFixedTexts()
    for id, key in pairs(fixedTexts) do if Controls[id] then Controls[id]:SetText(T(key)); end end
    for id, key in pairs(fixedTips) do if Controls[id] then Controls[id]:SetToolTipString(T(key)); end end
    Controls.ForceHelp:SetText(T("force.help", LanguageName(readerLanguage)));
    Controls.OpacityLabel:SetText(T("background", math.floor(opacities[opacityIndex] * 100)));
end

local function Dropdown(control, entries, selected)
    control:ClearEntries();
    for _, entry in ipairs(entries) do
        local instance = {};
        control:BuildEntry("IGTDropdownEntry", instance);
        instance.Button:SetText(IGT_Text.SafeDisplay(entry.name));
        instance.Button:SetVoid1(entry.id);
        if entry.tooltip then instance.Button:SetToolTipString(entry.tooltip); end
    end
    control:CalculateInternals();
    control:RegisterSelectionCallback(selected);
end

local function PlayerRoster()
    local result = {};
    if isLobby then
        for _, info in ipairs(Matchmaking.GetPlayerList() or {}) do
            local id = info.playerID;
            local status = PreGame.GetSlotStatus(id);
            if id ~= LocalPlayer() and (status == SlotStatus.SS_TAKEN or status == SlotStatus.SS_OBSERVER) then
                result[id] = info.playerName or PlayerName(id);
            end
        end
    else
        for id = 0, GameDefines.MAX_PLAYERS do
            local player = Players[id];
            if id ~= LocalPlayer() and player and player:IsHuman() and Network.IsPlayerConnected(id) then
                result[id] = PlayerName(id);
            end
        end
    end
    return result;
end

local function CivilizationName(id)
    local player = Players and Players[id];
    if not player or not GameInfo or not GameInfo.Civilizations then return T("unknown"); end
    local civ = GameInfo.Civilizations[player:GetCivilizationType()];
    if not civ then return T("unknown"); end
    return Locale.ConvertTextKey(civ.ShortDescription);
end

local function ObserveGame()
    if not initialized or isLobby or not activeGame or not PreGame.IsMultiplayerGame() then return; end
    local roster, counts, participants, signature = PlayerRoster(), {}, {}, {};
    for _, name in pairs(roster) do counts[name] = (counts[name] or 0) + 1; end
    for id, name in pairs(roster) do
        local steam = IGT_History.SteamID(id);
        local civ = CivilizationName(id);
        participants[#participants + 1] = {name=name,steamID=steam,civ=civ,duplicate=counts[name]>1};
        signature[#signature + 1] = tostring(id) .. ":" .. name .. ":" .. (steam or "") .. ":" .. civ;
    end
    table.sort(signature);
    local turn, myCiv = Game.GetGameTurn(), CivilizationName(LocalPlayer());
    local snapshot = tostring(activeGame) .. ":" .. turn .. ":" .. myCiv .. ":" .. table.concat(signature,"|");
    if snapshot ~= historySignature then
        if history.Observe(activeGame, historyOwner, turn, myCiv, participants) then historySignature = snapshot; end
    end
end

local function HistoryDetails(key)
    selectedHistoryKey = key;
    local encounters = key and history.Encounters(historyOwner,key) or {};
    if #encounters == 0 then
        Controls.HistorySummary:SetText(T("history.none"));
        Controls.HistoryText:SetText(T("history.start"));
    else
        local latest = encounters[1];
        local identity = latest.steam_id ~= "" and T("profile.steam", latest.steam_id) or T("history.no.account");
        Controls.HistorySummary:SetText(T("history.games", PlainText(latest.original_name), #encounters) .. "[NEWLINE]" .. identity .. "[NEWLINE]" .. T("history.last.seen", latest.last_utc));
        local lines = {};
        for i, e in ipairs(encounters) do
            if i > 100 then lines[#lines + 1] = T("history.latest100"); break; end
            local names={};for _, name in ipairs(e.names or {e.original_name}) do names[#names+1]=PlainText(name);end
            lines[#lines + 1] = T("history.entry", e.game_id, e.first_utc, PlainText(e.title), PlainText(e.my_civ), PlainText(e.their_civ), table.concat(names,", "), e.first_turn, e.last_turn, e.last_utc, PlainText(e.map));
        end
        Controls.HistoryText:SetText(table.concat(lines,"[NEWLINE][NEWLINE]"));
    end
    local person=historyPerson and IGT_History.Key(historyPerson.name,historyPerson.steam)==key and historyPerson or nil;
    local name=person and person.name or (#encounters>0 and encounters[1].original_name or nil);
    if name and key then
        local summary=history.Summary(historyOwner,key,name,activeGame);
        local names={};for _, previous in ipairs(summary.names) do names[#names+1]=PlainText(previous);end
        Controls.HistoryText:SetText(T("history.known", #names>0 and table.concat(names,", ") or T("history.no.names")) .. "[NEWLINE][NEWLINE]" .. Controls.HistoryText:GetText());
        if person then Controls.HistorySummary:SetText(T("history.prior", PlainText(DisplayName(person.name,person.steam)), summary.games) .. "[NEWLINE]" .. (person.steam and T("profile.steam", person.steam) or T("profile.name.only")));end
    end
    Controls.HistoryScroll:CalculateInternalSize();
end

RefreshHistory = function()
    if not initialized or not history then return; end
    ObserveGame();
    local people = history.Players(historyOwner);
    local entries, chosen = {}, nil;
    for i, person in ipairs(people) do
        entries[#entries + 1] = { id=i,name=PlainText(DisplayName(person.original_name,person.steam_id ~= "" and person.steam_id or nil)) .. " (" .. person.games .. ")" };
        if person.player_key == selectedHistoryKey then chosen = i; end
    end
    chosen = chosen or (not historyPerson and #people > 0 and 1 or nil);
    Dropdown(Controls.HistoryPlayer,entries,function(id)
        historyPerson=nil;Controls.HistoryPlayer:GetButton():SetText(entries[id].name); HistoryDetails(people[id].player_key);
    end);
    Controls.HistoryPlayer:GetButton():SetText(chosen and entries[chosen].name or (historyPerson and PlainText(DisplayName(historyPerson.name,historyPerson.steam)) or T("history.no.players")));
    HistoryDetails(chosen and people[chosen].player_key or (historyPerson and IGT_History.Key(historyPerson.name,historyPerson.steam)));
    local games, gameEntries, gameChoice = history.Games(historyOwner), {}, nil;
    for i, game in ipairs(games) do
        gameEntries[#gameEntries + 1] = {id=i,name="#" .. game.id .. " | " .. game.created_utc .. " | " .. PlainText(game.title)};
        if tonumber(game.id) == (selectedGame or activeGame) then gameChoice=i; end
    end
    gameChoice = gameChoice or (#games > 0 and 1 or nil);
    selectedGame = gameChoice and tonumber(games[gameChoice].id) or nil;
    Dropdown(Controls.HistoryGame,gameEntries,function(id)
        selectedGame=tonumber(games[id].id); Controls.HistoryGame:GetButton():SetText(gameEntries[id].name);
    end);
    Controls.HistoryGame:GetButton():SetText(gameChoice and gameEntries[gameChoice].name or T("history.no.games"));
    local available = not isLobby and PreGame.IsMultiplayerGame();
    Controls.HistoryNew:SetDisabled(not available or activeGame ~= nil);
    Controls.HistoryResume:SetDisabled(not available or activeGame ~= nil or not selectedGame);
    Controls.HistoryStop:SetDisabled(not activeGame);
    Controls.HistoryStatus:SetText(isLobby and T("history.lobby") or
        (activeGame and T("history.recording", activeGame) or T("history.off")));
end

local function StartRecording(resume)
    if not initialized or isLobby or not PreGame.IsMultiplayerGame() or activeGame then return; end
    if resume then
        for _, game in ipairs(history.Games(historyOwner)) do if tonumber(game.id) == selectedGame then activeGame=selectedGame; break; end end
    else
        local title = Matchmaking and Matchmaking.GetCurrentGameName and Matchmaking.GetCurrentGameName() or "Multiplayer game";
        local map = PreGame.GetMapScript and PreGame.GetMapScript() or "Unknown";
        activeGame = history.New(historyOwner,title ~= "" and title or "Multiplayer game",map);
        selectedGame = activeGame;
    end
    historySignature = nil;
    RefreshHistory();
end

RefreshRecipients = function()
    local roster, ids, signature = PlayerRoster(), {}, {};
    local counts = {};
    duplicateNames = {};
    nameAccounts = {};
    for _, name in pairs(roster) do counts[name] = (counts[name] or 0) + 1; end
    for name, count in pairs(counts) do if count > 1 then duplicateNames[name] = true; end end
    for id, name in pairs(roster) do if not duplicateNames[name] then nameAccounts[name] = IGT_History.SteamID(id); end end
    for id in pairs(roster) do ids[#ids + 1] = id end
    table.sort(ids);
    for _, id in ipairs(ids) do signature[#signature + 1] = tostring(id) .. ":" .. roster[id] .. ":" .. (IGT_History.SteamID(id) or "") end
    local joined = table.concat(signature, "|");
    recipientNames = roster;
    if joined ~= recipientSignature then
        recipientSignature = joined;
        local entries = { { id = -1, name = T("all.players") } };
        for _, id in ipairs(ids) do entries[#entries + 1] = { id = id, name = DisplayName(roster[id], IGT_History.SteamID(id)), tooltip = ProfileTooltip(roster[id], IGT_History.SteamID(id)) } end
        Dropdown(Controls.Recipient, entries, function(id)
            recipientID = id;
            selectedRecipientName = roster[id];
            RefreshLabels();
        end);
        RefreshChatNames();
        if history and historyOwner and initialized then
            for _, id in ipairs(ids) do
                local name=roster[id];local steam=IGT_History.SteamID(id);
                local key=IGT_History.Key(name,steam);
                if steam then history.NoteName(historyOwner,name,steam);end
                if not announcedPlayers[key] then
                    announcedPlayers[key]=true;
                    local summary=history.Summary(historyOwner,key,name,activeGame);
                    local names={};for i=1,math.min(3,#summary.names) do names[#names+1]=PlainText(summary.names[i]);end
                    local former=#names>0 and T("previously", table.concat(names,", ") .. (#summary.names>3 and T("more", #summary.names-3) or "")) or "";
                    -- The game's chat is small: only players you have met before get a line there.
                    if not nativeChat or summary.games>0 then
                        AddLine(T("player.joined", PlainText(DisplayName(name,steam)), summary.games, former .. (not steam and T("name.match") or "")));
                    end
                end
            end
        end
    end
    RefreshLabels();
end

local function LoadProfileEditor(name, steamID)
    editingName = name;
    editingSteam = steamID or nameAccounts[name];
    local profile = ProfileFor(name, editingSteam) or { alias = "", note = "" };
    Controls.ProfilePlayer:GetButton():SetText(name and PlainText(name) or T("profile.no.players"));
    Controls.ProfileAlias:SetText(profile.alias);
    Controls.ProfileNote:SetText(profile.note);
    Controls.ProfileSave:SetDisabled(not name or (duplicateNames[name] == true and not editingSteam));
    Controls.ProfileDelete:SetDisabled(not name or not ProfileFor(name, editingSteam));
    Controls.ProfileStatus:SetText(name and (duplicateNames[name] and not editingSteam and T("profile.dup.status") or T("profile.hint")) or T("profile.join"));
    Controls.ProfileIdentity:SetText(editingSteam and T("profile.steam.follow", editingSteam) or T("profile.no.steam"));
end

OpenProfiles = function(preferred)
    RefreshRecipients();
    if preferred and preferred~=editingName then editingSteam=nameAccounts[preferred];end
    local choices, seen, entries = {}, {}, {};
    local function add(name, steam)
        local key = IGT_History.Key(name, steam);
        if not seen[key] then seen[key] = true; choices[#choices + 1] = {name=name,steam=steam}; end
    end
    for id, name in pairs(recipientNames) do add(name, IGT_History.SteamID(id)); end
    if preferred then add(preferred,editingSteam);end
    for steam, profile in pairs(accountProfiles) do add(profile.original_name, steam); end
    for name in pairs(profiles) do if not nameAccounts[name] then add(name); end end
    table.sort(choices, function(a,b) return a.name == b.name and (a.steam or "") < (b.steam or "") or a.name < b.name; end);
    local chosen;
    for i, choice in ipairs(choices) do
        entries[#entries + 1] = { id = i, name = PlainText(choice.name) .. (duplicateNames[choice.name] and choice.steam and (" [" .. choice.steam:sub(-4) .. "]") or ""), tooltip = ProfileTooltip(choice.name,choice.steam) };
        if choice.name == preferred and (not editingSteam or editingSteam == choice.steam) then chosen = choice; end
    end
    Dropdown(Controls.ProfilePlayer, entries, function(id) local c=choices[id]; LoadProfileEditor(c.name,c.steam); end);
    chosen = chosen or choices[1];
    LoadProfileEditor(chosen and chosen.name, chosen and chosen.steam);
    ShowPage("notes");
end

local function SaveProfile(remove)
    if not initialized or not editingName then return; end
    RefreshRecipients();
    if not remove and duplicateNames[editingName] and not editingSteam then Controls.ProfileStatus:SetText(T("profile.dup.status")); return; end
    local alias = PlainText(Controls.ProfileAlias:GetText()):match("^%s*(.-)%s*$");
    local note = PlainText(Controls.ProfileNote:GetText()):match("^%s*(.-)%s*$");
    if not remove and (#alias > 160 or #note > 2000) then Controls.ProfileStatus:SetText(T("profile.too.long")); return; end
    if remove or (alias == "" and note == "") then
        Query("DELETE FROM igt_profiles WHERE original_name=" .. Quote(editingName));
        profiles[editingName] = nil;
        if editingSteam then Query("DELETE FROM igt_account_profiles WHERE steam_id=" .. Quote(editingSteam)); accountProfiles[editingSteam] = nil; end
    elseif editingSteam then
        Query("INSERT OR REPLACE INTO igt_account_profiles VALUES(" .. Quote(editingSteam) .. "," .. Quote(editingName) .. "," .. Quote(alias) .. "," .. Quote(note) .. ")");
        accountProfiles[editingSteam] = { original_name=editingName,alias=alias,note=note };
    else
        Query("INSERT OR REPLACE INTO igt_profiles(original_name,alias,note) VALUES(" .. Quote(editingName) .. "," .. Quote(alias) .. "," .. Quote(note) .. ")");
        profiles[editingName] = { alias = alias, note = note };
    end
    recipientSignature = "<profiles changed>";
    RefreshRecipients();
    OpenProfiles(editingName);
    Controls.ProfileStatus:SetText(remove and T("profile.removed") or T("profile.saved"));
end

local SetupDropdowns;
local function SetReaderLanguage(code)
    readerLanguage = code;
    UpdateWindowLanguage();
    State("reader_language", code);
    SetupDropdowns();
    ApplyFixedTexts();
    ShowPage(activePage, not expanded);
    InvalidateDraft();
    RefreshChatNames();
    local fallback = windowFallback[code];
    local status = (windowLanguage == code or windowLanguage == fallback) and "status.language" or fallback and "status.language.fallback" or "status.language.font";
    SetStatus(T(status, LanguageName(code), fallback and LanguageName(fallback)));
end

SetupDropdowns = function()
    for _, spec in ipairs({ {Controls.Source, sourceLanguages, "source"}, {Controls.Target, targetLanguages, "target"}, {Controls.Incoming, incomingLanguages, "incoming"} }) do
        local entries, kind = {}, spec[3];
        for i, code in ipairs(spec[2]) do entries[#entries + 1] = { id = i, name = LanguageName(code) } end
        Dropdown(spec[1], entries, function(id)
            if kind == "source" then sourceIndex = id; State("source_language", sourceLanguages[id]); InvalidateDraft();
            elseif kind == "target" then targetIndex = id; State("target_language", targetLanguages[id]); InvalidateDraft();
            else SetReaderLanguage(incomingLanguages[id]); end
            RefreshLabels();
        end);
    end
    if nativeChat then
        -- One menu on the chat row: send as typed, or translated into a language.
        local entries = { { id = 0, name = T("translate.off") } };
        for i, code in ipairs(targetLanguages) do entries[#entries + 1] = { id = i, name = LanguageName(code) }; end
        Dropdown(Controls.SendLanguage, entries, function(id)
            translateOnSend = id ~= 0;
            State("send_translate", translateOnSend and "1" or "0");
            if id ~= 0 then targetIndex = id; State("target_language", targetLanguages[id]); end
            InvalidateDraft();
            RefreshLabels();
        end);
    end
    recipientSignature = "<uninitialized>";
    RefreshRecipients();
    Controls.Incoming:SetDisabled(false);
end

local function StartSession()
    Query("CREATE TABLE IF NOT EXISTS " .. requestTable .. "(id INTEGER PRIMARY KEY AUTOINCREMENT, session TEXT, kind TEXT, source TEXT, target TEXT, text TEXT, status TEXT, result TEXT, detected TEXT, error TEXT, created REAL, started REAL)");
    Query("CREATE TABLE IF NOT EXISTS igt_state(key TEXT PRIMARY KEY,value TEXT)");
    -- Spam must not slow every frame: look up this session's rows by index.
    Query("CREATE INDEX IF NOT EXISTS igt_" .. requestTable .. "_session ON " .. requestTable .. "(session,status,id)");
    local saved = {};
    for _, setting in ipairs(Query("SELECT key,value FROM igt_state WHERE key IN ('window_width','window_height','reader_language','target_language','source_language','send_translate')")) do
        saved[setting.key] = setting.value;
        local value=tonumber(setting.value);
        if value then
            if setting.key=='window_width' then expandedWidth=math.max(700,math.min(1600,math.floor(value)));
            elseif setting.key=='window_height' then expandedHeight=math.max(620,math.min(1000,math.floor(value))); end
        end
    end
    readerLanguage = IndexOf(incomingLanguages, saved.reader_language) and saved.reader_language or GameLanguage();
    UpdateWindowLanguage();
    targetIndex = IndexOf(targetLanguages, saved.target_language) or IndexOf(targetLanguages, readerLanguage == "en" and "ru" or "en");
    sourceIndex = IndexOf(sourceLanguages, saved.source_language) or 1;
    -- The game's chat stays plain until the player picks a language; the choice is kept.
    if nativeChat then translateOnSend = saved.send_translate == "1"; end
    Query("CREATE TABLE IF NOT EXISTS igt_profiles(original_name TEXT PRIMARY KEY,alias TEXT NOT NULL,note TEXT NOT NULL)");
    history = IGT_History.Open(Query);
    historyOwner = IGT_History.Key(PlayerName(LocalPlayer()), IGT_History.SteamID(LocalPlayer()));
    activeGame, selectedGame, selectedHistoryKey, historySignature = nil, nil, nil, nil;
    announcedPlayers={};
    historyPerson=nil;
    accountProfiles = {};
    for _, row in ipairs(Query("SELECT * FROM igt_account_profiles")) do accountProfiles[row.steam_id] = row; end
    profiles = {};
    for _, row in ipairs(Query("SELECT original_name,alias,note FROM igt_profiles")) do profiles[row.original_name] = { alias = row.alias, note = row.note }; end
    editingName = nil;
    editingSteam = nil;
    Controls.ProfilesPanel:SetHide(true);
    Controls.EmojiPanel:SetHide(true);Controls.PlayerMenu:SetHide(true);contextPlayer=nil;
    Controls.ForcePanel:SetHide(true);
    forceRow,forceSource=nil,nil;
    ShowPage("chat", not expanded);
    local rows = Query("SELECT strftime('%s','now') || '-' || lower(hex(randomblob(8))) AS token");
    session = rows[1].token;
    State("session", session);
    -- Finished work of earlier sessions is never read again; keep the table small.
    Query("DELETE FROM " .. requestTable .. " WHERE session IS NULL OR session<>" .. Quote(session));
    autoBudget, autoPausedUntil = {}, 0;
    State("clipboard_paste_request", "");
    State("clipboard_paste_token", "");
    State("clipboard_copy", "");
    if IGT_Config then
        native = IGT_Native.Open(IGT_Config,Query,State,session);
        Controls.Paste:SetHide(true); Controls.CopyDraft:SetHide(true); Controls.CopyLast:SetHide(true);
        Controls.OnlineTranslation:SetHide(false);
        Controls.OnlineTranslationLabel:SetText(native.Enabled() and T("online.on") or T("online.enable"));
        Controls.TranslationPrivacy:SetHide(false);
    end
    pending = {};
    pasteToken = nil;
    sendQueue = {};
    expectedEchoes = {};
    submissionGeneration = submissionGeneration + 1;
    recipientID = -1;
    selectedRecipientName = nil;
    translatedDraft = nil;
    Controls.CancelSend:SetDisabled(true);
    InvalidateDraft();
end

local function Enqueue(kind, text, source, target, info)
    if not initialized then SetStatus(T("status.db")); return; end
    local online = Query("SELECT value FROM igt_state WHERE key=" .. Quote(IGT_Config and "native_online_enabled" or "online_translation_enabled"));
    if online[1] and online[1].value == "0" then SetStatus(IGT_Config and T("status.enable") or T("status.enable.companion")); return; end
    if not text or not text:find("%S") then SetStatus(T("status.type")); return; end
    local count = 0;
    for _ in pairs(pending) do count = count + 1; end
    if count >= 50 then SetStatus(T("status.queue.full")); return; end
    Query("INSERT INTO " .. requestTable .. "(session,kind,source,target,text,status,created) VALUES(" ..
        Quote(session) .. "," .. Quote(kind) .. "," .. Quote(source) .. "," .. Quote(target) .. "," ..
        Quote(text) .. ",'pending',CAST(strftime('%s','now') AS REAL))");
    local rows = Query("SELECT last_insert_rowid() AS id");
    info = info or {};
    info.kind, info.target, info.original, info.source = kind, target, text, source;
    pending[tonumber(rows[1].id)] = info;
    RefreshSendState();
    SetStatus(IGT_Config and T("status.translating") or T("status.queued"));
    return true;
end

-- The game's rows have room for one small button, so it shows a mark, not a word.
local rowMarks = { translate="T", original="<", working="..", retry="!" };
local function SetRowLabel(row, key, text)
    row.TranslateLabel:SetText(nativeChat and rowMarks[key] or text or T(key));
end

-- A message is foreign when its letters are not the reader's alphabet. Latin
-- messages are never automatic: most players read English chat, and the
-- Translate button is there when one is not understood.
local function IsForeign(text)
    local script = IGT_Text.Script(text);
    if not script or script == "latin" then return false; end
    return script ~= (readerScripts[readerLanguage] or "latin");
end

local function Remember(target, original, result, detected)
    local key = target .. "\n" .. original;
    if not recentTranslations[key] then recentOrder[#recentOrder + 1] = key; end
    recentTranslations[key] = { text = result, detected = detected };
    if #recentOrder > 100 then recentTranslations[table.remove(recentOrder, 1)] = nil; end
end

local function ShowIncomingTranslation(row, target, result, detected)
    if not RowIsLive(row) or not row.chat then return; end
    local tag = result ~= row.chat.original and ("(TR " .. tostring(detected or "?") .. ">" .. target .. ") ") or "";
    row.translationPending = false; row.forceChoose = false; row.translationTarget = target;
    row.chat.translated = result; row.translationTag = tag; row.showOriginal = false;
    row.chat.prefix, row.chat.text = tag, result;
    row.TranslateButton:SetDisabled(false); SetRowLabel(row, "original");
    RenderChat(row);
end

-- Per-sender token bucket plus a cap on waiting automatic requests.
local function AutomaticAllowed(chat, text)
    if #text > AUTO_MAX_BYTES or clock < autoPausedUntil then return false; end
    local waiting = 0;
    for _, info in pairs(pending) do
        if info.kind == "auto" then
            waiting = waiting + 1;
            -- The same spam line already on its way is shown from the cache later.
            if info.original == text and info.target == readerLanguage then return false; end
        end
    end
    if waiting >= AUTO_WAITING then SetStatus(T("status.auto.busy")); return false; end
    local sender = chat.steamID or chat.name;
    local budget = autoBudget[sender] or { tokens = AUTO_BURST, time = clock };
    budget.tokens = math.min(AUTO_BURST, budget.tokens + (clock - budget.time) / AUTO_REFILL_SECONDS);
    budget.time = clock;
    autoBudget[sender] = budget;
    if budget.tokens < 1 then SetStatus(T("status.auto.limited", DisplayName(chat.name, chat.steamID))); return false; end
    budget.tokens = budget.tokens - 1;
    return true;
end

TranslateRow = function(row, source, choose, automatic)
    if not initialized or not RowIsLive(row) or not row.chat or row.chat.own or row.translationPending then return; end
    if row.chat.translated and not source and not choose then
        row.showOriginal = not row.showOriginal;
        row.chat.text = row.showOriginal and row.chat.original or row.chat.translated;
        row.chat.prefix = row.showOriginal and "" or row.translationTag;
        SetRowLabel(row, row.showOriginal and "translate" or "original", row.showOriginal and LanguageName(row.translationTarget or readerLanguage) or nil);
        RenderChat(row); return;
    end
    if not source and (choose or row.forceChoose) then
        forceRow,forceSource=row,nil;
        local entries={};
        for i, code in ipairs(manualLanguages) do entries[#entries+1]={id=i,name=LanguageName(code)}; end
        Dropdown(Controls.ForceSource,entries,function(id)
            forceSource=manualLanguages[id]; Controls.ForceSource:GetButton():SetText(LanguageName(forceSource)); Controls.ForceGo:SetDisabled(false);
        end);
        Controls.ForceSource:GetButton():SetText(T("choose.language"));
        Controls.ForceHelp:SetText(T("force.help", LanguageName(readerLanguage)));
        Controls.ForceGo:SetDisabled(true); Controls.ForcePanel:SetHide(false);
        return;
    end
    source = source or "auto";
    local known = source == "auto" and recentTranslations[readerLanguage .. "\n" .. row.chat.original];
    if known then ShowIncomingTranslation(row, readerLanguage, known.text, known.detected); return; end
    if automatic and not AutomaticAllowed(row.chat, row.chat.original) then return; end
    if Enqueue(automatic and "auto" or "incoming",row.chat.original,source,readerLanguage,{row=row}) then
        row.translationPending=true; row.TranslateButton:SetDisabled(true); SetRowLabel(row, "working");
    end
end

-- A row of the game's chat gets one invisible button over it, for the hover text
-- and right-click menu, holding the small translate button. It is built here and
-- moved into the game's row, the way the game moves unit flags between screens.
-- Like those flags it stays this file's own: it comes back to RowScrap before the
-- game destroys the row (ParkRowTools) and serves a later row, the way the game
-- keeps its yield icons in a Scrap box. The game must never destroy one of these.
local freeTools = {};

local function AttachRowTools(row)
    local tools = table.remove(freeTools);
    if not tools then
        tools = {};
        ContextPtr:BuildInstanceForControl("IGTRowTools", tools, Controls.RowScrap);
    end
    tools.Hit:ChangeParent(row.Box);
    tools.Hit:SetSizeX(row.Box:GetSizeX());
    tools.TranslateButton:SetDisabled(false);
    row.tools = tools;
    row.Hit, row.TranslateButton, row.TranslateLabel = tools.Hit, tools.TranslateButton, tools.TranslateLabel;
end

local function ParkRowTools(row)
    local tools = row.tools;
    if not tools then return; end
    row.tools, row.Hit, row.TranslateButton, row.TranslateLabel = nil, nil, nil, nil;
    tools.Hit:ChangeParent(Controls.RowScrap);
    freeTools[#freeTools + 1] = tools;
end

local function OnChat(fromPlayer, toPlayer, text, targetType, nativeRow)
    if not initialized then return; end
    if nativeChat and not nativeRow then return; end
    if type(text) ~= "string" or text == "" then return; end
    -- KEK's hidden desync checks travel as chat; its own chat never shows them.
    if text:sub(1, 5) == "~~KS|" then return; end
    Safe(function()
        local own = fromPlayer == LocalPlayer();
        if own then
            for i, echo in ipairs(expectedEchoes) do
                if echo.text == text then
                    table.remove(expectedEchoes, i);
                    -- The translator already wrote this message on its own row.
                    if nativeRow then nativeRow.Box:SetHide(true); RefreshTranscript(); rowScroll:SetScrollValue(1); end
                    return;
                end
            end
        end
        local audience = "";
        -- The front-end lobby does not expose ChatTargetTypes in vanilla.
        local team = ChatTargetTypes and targetType == ChatTargetTypes.CHATTARGET_TEAM;
        local private = ChatTargetTypes and targetType == ChatTargetTypes.CHATTARGET_PLAYER;
        if team then audience = T("team");
        elseif private then audience = T("private"); end
        local row = nativeRow;
        if row then
            row.Message, row.stamp = row.String, row.gameStamp or TurnStamp();
            TrackRow(row);
            if not own then AttachRowTools(row); end
        else
            row = AddLine("",nil,private and "Magenta_Chat" or team and "Green_Chat" or own and "Gray_Chat" or nil);
        end
        row.chat = { original=text,name = PlayerName(fromPlayer), steamID=IGT_History.SteamID(fromPlayer), own = own, audience = audience, text = text,
            targetSteam=own and private and IGT_History.SteamID(toPlayer) or nil,
            targetName = own and private and PlayerName(toPlayer) or nil };
        if nativeRow then
            local shown = tostring(row.String:GetText() or "");
            row.chat.nativePrefix = shown:sub(-#text) == text and shown:sub(1, #shown - #text) or (row.chat.name .. ": ");
            -- A row with nothing to add stays exactly as the game wrote it.
            if ProfileFor(row.chat.name, row.chat.steamID) then RenderChat(row); else RowTooltip(row); end
            FitRow(row);
        else
            RenderChat(row);
        end
        if not own and Mouse.eRClick then
            (row.Hit or row.Box):RegisterCallback(Mouse.eRClick,function()
                if not initialized or not RowIsLive(row) then return;end
                contextPlayer={name=row.chat.name,steam=row.chat.steamID};
                local x,y=UIManager:GetMousePos();local sw,sh=UIManager:GetScreenSizeVal();
                Controls.PlayerMenu:SetOffsetVal(math.max(0,math.min(x,sw-220)),math.max(0,math.min(y,sh-112)));
                Controls.PlayerMenu:SetHide(false);
            end);
        end
        if not own then
            row.TranslateButton:SetHide(false); SetRowLabel(row, "translate");
            row.TranslateButton:SetToolTipString(T("tip.row", LanguageName(readerLanguage)));
            row.TranslateButton:RegisterCallback(Mouse.eLClick,function() Safe(function() TranslateRow(row); end); end);
            if Mouse.eRClick then row.TranslateButton:RegisterCallback(Mouse.eRClick,function() Safe(function() TranslateRow(row,nil,true); end); end); end
        end
        if receiving and not own and IsForeign(text) then TranslateRow(row,"auto",nil,true); end
    end);
end

local function TranslateDraft()
    Safe(function()
        InvalidateDraft();
        Enqueue("outgoing", Draft():GetText(), sourceLanguages[sourceIndex], targetLanguages[targetIndex], {
            generation = draftGeneration, draft = Draft():GetText()
        });
    end);
end

local function SendLabel(options, translated)
    local team = options.team and options.team ~= -1;
    return (translated and T("you.to", options.target) or T("you")) .. (team and T("team") or "") ..
        (options.recipient ~= -1 and T("to.private", DisplayName(options.name,options.steamID)) or "");
end

local function SendColor(options)
    if options.recipient ~= -1 then return "Magenta_Chat"; end
    return options.team and options.team ~= -1 and "Green_Chat" or "Gray_Chat";
end

local function BeginSend(text, translated, options)
    if not initialized then SetStatus(T("status.open.game")); return; end
    if #sendQueue > 100 then SetStatus(T("status.send.full")); return; end
    if not isLobby and not PreGame.IsMultiplayerGame() then SetStatus(T("status.mp.only")); return; end
    if not text or not text:find("%S") then SetStatus(T("status.nothing")); return; end
    options = options or { original = Draft():GetText(), recipient = recipientID, name = selectedRecipientName, steamID = recipientID ~= -1 and IGT_History.SteamID(recipientID) or nil, target = targetLanguages[targetIndex], icon = selectedIcon, color = colors[colorIndex][2] };
    if options.recipient ~= -1 and (PlayerRoster()[options.recipient] ~= options.name or (options.steamID and IGT_History.SteamID(options.recipient) ~= options.steamID)) then
        SetStatus(T("status.recipient.changed")); return;
    end
    -- Translated messages go out as plain text, with no tag (user, 2026-11-08).
    local prefix = options.icon ~= "" and options.icon .. " " or "";
    local color = options.color;
    local colorBytes = color ~= "" and (#color + 12) or 0;
    text = IGT_Text.SafeDisplay(color ~= "" and IGT_Text.StripColors(text) or text);
    -- A chat that stores what it sends (KEK) says how much one message may hold.
    local chunks, splitError = IGT_Text.Split(text, (nativeChat and nativeChat.MaxBytes or 240) - #prefix - colorBytes);
    if not chunks or #chunks == 0 then SetStatus(splitError or T("status.nothing")); return; end
    if #chunks > 20 then SetStatus(T("status.too.long")); return; end
    local player = LocalPlayer();
    local batch = { original = options.original, row = options.row,
        label = SendLabel(options, translated),
        total = #chunks, sent = 0, color = color, translated = translated,
        channelColor = SendColor(options) };
    for i, chunk in ipairs(chunks) do
        sendQueue[#sendQueue + 1] = { text = IGT_Text.Colorize(prefix .. chunk, color), team = options.team or -1, player = options.recipient, recipientName = options.name, steamID = options.steamID, active = player, session = session, batch = batch };
    end
    Controls.CancelSend:SetDisabled(false);
    SetStatus(T("status.sending", #chunks, options.recipient == -1 and T("all") or options.name));
    return true;
end

-- In the game's chat nothing else shows a status, so a refusal goes on a row.
local function Refuse(row)
    if not nativeChat then return; end
    if row then UpdateLine(row, T("not.sent", row.draftText, statusText)); else AddLine(statusText, ""); end
end

local function SubmitDraft(typed, team)
    Safe(function()
        local text = typed or Draft():GetText();
        if not text or not text:find("%S") then return; end
        local roster = PlayerRoster();
        if recipientID ~= -1 and (not roster[recipientID] or roster[recipientID] ~= selectedRecipientName) then SetStatus(T("status.select.recipient")); Refuse(); return; end
        local options = { original = text, recipient = recipientID, team = team or -1, name = roster[recipientID], steamID = recipientID ~= -1 and IGT_History.SteamID(recipientID) or nil, target = targetLanguages[targetIndex], icon = selectedIcon, color = colors[colorIndex][2] };
        local accepted;
        if translateOnSend then
            -- Translating takes a moment: show the message right away, on the row it will keep.
            if nativeChat then
                options.row = AddLine(SendLabel(options, true) .. ": " .. text .. " (" .. T("working") .. ")", nil, SendColor(options));
                options.row.draftText = text;
            end
            accepted = Enqueue("outgoing", text, sourceLanguages[sourceIndex], options.target, {
                autoSend = true, options = options, generation = submissionGeneration, active = LocalPlayer()
            });
        else accepted = BeginSend(text, false, options); end
        if accepted then
            Draft():SetText("");
            InvalidateDraft();
            if not nativeChat then Draft():TakeFocus(); end
        else
            Refuse(options.row);
        end
    end);
end

-- Enter in the game's own chat box. Returning nothing leaves the message to the
-- game, so with translation off this chat is exactly the original one.
local function OnNativeSend(text, team, player)
    if not initialized or type(text) ~= "string" or not text:find("%S") then return; end
    if nativeChat.OwnRecipient then player = recipientID;
    else recipientID, selectedRecipientName = player, PlayerRoster()[player]; end
    if not translateOnSend and selectedIcon == "" and colors[colorIndex][2] == "" and (player == -1 or not nativeChat.OwnRecipient) then return; end
    SubmitDraft(text, team);
    return true;
end

local function CancelSend()
    submissionGeneration = submissionGeneration + 1;
    if sendQueue[1] then
        local batch = sendQueue[1].batch;
        if batch.row then UpdateLine(batch.row, IGT_Text.Colorize(T("stopped.after", batch.label, batch.sent, batch.total, batch.original), batch.color)); end
    end
    sendQueue = {};
    RefreshSendState();
    SetStatus(T("status.cancelled"));
end

local LIMIT_ERROR = "Translation allowance or request limit reached. Try later.";
local serviceErrors = {
    [LIMIT_ERROR]="err.limit", ["Translation service is unavailable. Try later."]="err.unavailable",
    ["Translation service timed out. Try a shorter message."]="err.timeout",
    ["Translation is too long. Try a shorter message."]="err.toolong",
    ["Translation failed. Try a shorter message."]="err.failed", ["Shorten the message to 6,000 UTF-8 bytes."]="err.shorten",
    ["Choose supported source and target languages."]="err.languages", ["Online translation is disabled."]="err.disabled",
    ["Cannot verify the translation service response. Check your connection and try again."]="err.verify",
    ["Translation did not finish."]="err.unfinished",
    ["Request expired, was already used, or this download was revoked. Download a fresh copy if needed."]="err.expired" };
ErrorText = function(err)
    local key = serviceErrors[tostring(err or "")];
    return key and T(key) or tostring(err or T("unknown.error"));
end

local function Poll()
    if not initialized then return; end
    local state = {};
    for _, row in ipairs(Query("SELECT key,value FROM igt_state WHERE key IN ('heartbeat','session','online_translation_enabled','native_online_enabled','clipboard_paste_token','clipboard_paste_result')")) do
        state[row.key] = row.value;
    end
    if native then state.online_translation_enabled = state.native_online_enabled; end
    if state.session and state.session ~= session then
        sendQueue = {};
        initialized = false;
        Controls.CancelSend:SetDisabled(true);
        SetStatus(T("status.replaced"));
        return;
    end
    local nowRows = Query("SELECT CAST(strftime('%s','now') AS REAL) AS now");
    local alive = native ~= nil or tonumber(state.heartbeat or 0) > tonumber(nowRows[1].now) - 8;
    if state.online_translation_enabled == "0" or (state.heartbeat and not alive) then
        local translating = false;
        for _, info in pairs(pending) do
            if info.autoSend and info.generation == submissionGeneration then translating = true; break; end
        end
        for _, item in ipairs(sendQueue) do if item.batch.translated then translating = true; break; end end
        if translating then CancelSend(); SetStatus(T("status.stopped")); end
    end
    local rows = Query("SELECT id,status,result,detected,error FROM " .. requestTable .. " WHERE session=" .. Quote(session) ..
        " AND (status='done' OR status='error') ORDER BY id");
    for _, row in ipairs(rows) do
        local id = tonumber(row.id);
        local info = pending[id];
        -- Read once: finished rows are not fetched again on later polls.
        Query("UPDATE " .. requestTable .. " SET status='seen' WHERE id=" .. id);
        if info then
            pending[id] = nil;
            if info.row and info.row.chat and RowIsLive(info.row) then
                info.row.translationPending=false; info.row.TranslateButton:SetDisabled(false);
                SetRowLabel(info.row, row.status == "error" and "retry" or "original");
                info.row.forceChoose=row.status == "error";
            end
            if row.status == "error" then
                local reason = ErrorText(row.error);
                if info.kind == "auto" and row.error == LIMIT_ERROR then
                    autoPausedUntil = clock + 300; SetStatus(T("status.auto.paused"));
                    if nativeChat then AddLine(statusText, ""); end
                end
                if info.autoSend then
                    local line = T("not.sent", info.original, row.error and reason or T("translation.failed"));
                    if info.options and info.options.row then UpdateLine(info.options.row, line); else AddLine(line); end
                    SetStatus(T("status.failed.unsent"));
                elseif info.kind ~= "outgoing" or info.generation == draftGeneration then
                    if not (info.kind == "auto" and row.error == LIMIT_ERROR) then SetStatus(T("status.failed", row.error and reason or T("unknown.error"))); end
                    if info.kind ~= "outgoing" then
                        if info.row and info.row.chat then
                            info.row.chat.prefix = T("unavailable"); RenderChat(info.row);
                        else UpdateLine(info.row, T("unavailable") .. (info.name or "Test") .. ": " .. info.original); end
                    end
                end
            elseif info.kind == "outgoing" then
                if info.autoSend then
                    if info.generation == submissionGeneration and info.active == LocalPlayer() then
                        if not BeginSend(tostring(row.result or ""), true, info.options) then
                            local line = T("not.sent.short", info.original);
                            if info.options.row then UpdateLine(info.options.row, line); else AddLine(line); end
                        end
                    end
                elseif info.generation == draftGeneration and info.draft == Draft():GetText() then
                    translatedDraft = tostring(row.result or "");
                    translatedSource = info.draft;
                    lastTranslation = translatedDraft;
                    Preview("(TR " .. tostring(row.detected or "?") .. ">" .. info.target .. ") " .. translatedDraft);
                    Controls.SendTranslated:SetDisabled(translatedDraft == "");
                    SetStatus(T("status.ready"));
                end
            else
                lastTranslation = tostring(row.result or "");
                if info.source == "auto" then Remember(info.target, info.original, lastTranslation, row.detected); end
                if info.row and info.row.chat then ShowIncomingTranslation(info.row, info.target, lastTranslation, row.detected);
                else
                    local tag = lastTranslation ~= info.original and ("(TR " .. tostring(row.detected or "?") .. ">" .. info.target .. ") ") or "";
                    UpdateLine(info.row, tag .. (info.name or "Test") .. ": " .. lastTranslation);
                end
                SetStatus(T("status.received"));
            end
        end
    end
    RefreshSendState();
    Controls.CompanionStatus:SetText(native and (native.Enabled() and T("online.enabled") or T("online.disabled")) or alive and T("companion.connected") or T("companion.offline"));
    if pasteToken and state.clipboard_paste_token == pasteToken then
        Draft():SetText(tostring(state.clipboard_paste_result or ""):gsub("[\r\n\t]", " "));
        InvalidateDraft();
        pasteToken = nil;
        SetStatus(T("status.pasted"));
    end
end

local function UpdateWindowDrag()
    if Controls.Panel:IsHidden() or not panelBounds or not UIManager or not UIManager.GetMousePos or not Controls.HeaderDrag:IsTrackingLeftMouseButton() then
        dragging=nil; return;
    end
    local mx,my=UIManager:GetMousePos();
    local b=panelBounds;
    if not dragging then dragging={dx=mx-b.x,dy=my-b.y}; return; end
    local sw,sh=UIManager:GetScreenSizeVal();
    b.x=math.max(0,math.min(mx-dragging.dx,sw-b.w));
    b.y=math.max(0,math.min(my-dragging.dy,sh-b.h));
    windowPositions[expanded and "expanded" or "compact"]={x=b.x,y=b.y};
    Controls.Panel:SetOffsetVal(b.x,b.y);
    Controls.Toggle:SetOffsetVal(b.x+b.w-160,b.y);
    Controls.Panel:ReprocessAnchoring();
end

local function Update(delta)
    if native and initialized then Safe(function() native.Update(delta); end); end
    if not initialized then return; end
    clock = clock + delta;
    UpdateWindowDrag();
    if native then Safe(function() native.Update(delta); end); end
    historyElapsed = historyElapsed + delta;
    if historyElapsed >= 10 then
        historyElapsed = 0;
        Safe(function() if activePage == "history" and not Controls.Panel:IsHidden() then RefreshHistory(); else ObserveGame(); end end);
    end
    rosterElapsed = rosterElapsed + delta;
    if rosterElapsed >= 2 then
        rosterElapsed = 0; Safe(RefreshRecipients);
        if UIManager and UIManager.GetScreenSizeVal then
            local sw,sh=UIManager:GetScreenSizeVal();
            if sw~=lastScreenW or sh~=lastScreenH then Safe(ResizeOverlay); end
        end
    end
    for i = #expectedEchoes, 1, -1 do
        expectedEchoes[i].age = expectedEchoes[i].age + delta;
        if expectedEchoes[i].age > 30 then table.remove(expectedEchoes, i); end
    end
    elapsed = elapsed + delta;
    sendDelay = sendDelay + delta;
    if #sendQueue > 0 then
        if sendDelay >= 0.8 then
            sendDelay = 0;
            -- Recheck consent/heartbeat before sending a translated part, even
            -- when the regular quarter-second poll has not run yet this frame.
            if sendQueue[1].batch.translated then Safe(Poll); end
            if #sendQueue == 0 or not initialized then return; end
            local item = sendQueue[1];
            if item.active ~= LocalPlayer() or item.session ~= session then CancelSend();
            elseif item.player ~= -1 and (PlayerRoster()[item.player] ~= item.recipientName or (item.steamID and IGT_History.SteamID(item.player) ~= item.steamID)) then
                CancelSend(); SetStatus(T("status.private.left"));
            else
                local echo = { text = item.text, age = 0 };
                expectedEchoes[#expectedEchoes + 1] = echo;
                local ok = Safe(function()
                    -- KEK's chat stores every message in the game; its hook sends the same way.
                    if nativeChat and nativeChat.Send then nativeChat.Send(item.text, item.team, item.player);
                    elseif isLobby and item.player == -1 then Network.SendChat(item.text);
                    else Network.SendChat(item.text, item.team, item.player); end
                end);
                if ok then
                    table.remove(sendQueue, 1);
                    local batch = item.batch;
                    batch.sent = batch.sent + 1;
                    local label = batch.sent < batch.total and T("sending", batch.label, batch.sent, batch.total) or batch.label;
                    local line = IGT_Text.Colorize(label .. ": " .. batch.original, batch.color);
                    if batch.row then UpdateLine(batch.row, line); else batch.row = AddLine(line,nil,batch.channelColor); end
                else
                    for i, queued in ipairs(expectedEchoes) do if queued == echo then table.remove(expectedEchoes, i); break; end; end
                    CancelSend();
                end
                RefreshSendState();
                if ok then SetStatus(#sendQueue > 0 and T("status.remaining", #sendQueue) or T("status.sent")); end
            end
        end
    end
    if elapsed >= 0.25 then
        elapsed = 0;
        Safe(Poll);
    end
end

Controls.Toggle:RegisterCallback(Mouse.eLClick, function()
    print("IGT toggle clicked");
    -- Some frontend contexts do not propagate an initial ShowHide notification.
    -- A user click is also a reliable indication that this lobby is active.
    if isLobby and not initialized then Safe(Initialize); end
    Controls.Panel:SetHide(not Controls.Panel:IsHidden());
    Controls.Toggle:SetHide(not Controls.Panel:IsHidden());
    if Controls.Panel:IsHidden() then Controls.Settings:SetHide(true); Controls.ProfilesPanel:SetHide(true); Controls.EmojiPanel:SetHide(true); Controls.PlayerMenu:SetHide(true); Controls.ForcePanel:SetHide(true); forceRow=nil;
    else ShowPage(activePage,not expanded); end
end);
Controls.Minimize:RegisterCallback(Mouse.eLClick, MinimizeWindow);
-- The small button on the chat row opens the window; it toggles like the old launcher.
Controls.ChatSettings:RegisterCallback(Mouse.eLClick, function()
    Safe(function()
        if isLobby and not initialized then Initialize(); end
        if not Controls.Panel:IsHidden() then MinimizeWindow(); return; end
        Controls.Panel:SetHide(false);
        ShowPage("settings");
    end);
end);
Controls.Expand:RegisterCallback(Mouse.eLClick, function() ShowPage("chat", expanded); end);
Controls.More:RegisterCallback(Mouse.eLClick, function() ShowPage("settings"); end);
Controls.ChatTab:RegisterCallback(Mouse.eLClick, function() ShowPage("chat"); end);
Controls.NotesTab:RegisterCallback(Mouse.eLClick, function() Safe(function() OpenProfiles(selectedRecipientName or editingName); end); end);
Controls.HistoryTab:RegisterCallback(Mouse.eLClick, function() Safe(function() ShowPage("history"); RefreshHistory(); end); end);
Controls.SettingsTab:RegisterCallback(Mouse.eLClick, function() ShowPage("settings"); end);
local function ToggleEmoji()
    if panelBounds then Controls.EmojiPanel:SetOffsetVal(math.max(0,panelBounds.x+panelBounds.w-362),math.max(0,panelBounds.y+panelBounds.h-254));end
    Controls.EmojiPanel:SetHide(not Controls.EmojiPanel:IsHidden());
end
Controls.EmojiButton:RegisterCallback(Mouse.eLClick,ToggleEmoji);
Controls.SettingsEmoji:RegisterCallback(Mouse.eLClick,ToggleEmoji);
Controls.EmojiClose:RegisterCallback(Mouse.eLClick,function() Controls.EmojiPanel:SetHide(true);end);
Controls.PlayerMenuClose:RegisterCallback(Mouse.eLClick,function() Controls.PlayerMenu:SetHide(true);contextPlayer=nil;end);
Controls.PlayerMenuNote:RegisterCallback(Mouse.eLClick,function()
    Safe(function()
        if not contextPlayer then return;end
        editingName,editingSteam=contextPlayer.name,contextPlayer.steam;
        OpenProfiles(editingName);Controls.PlayerMenu:SetHide(true);
    end);
end);
Controls.PlayerMenuDetails:RegisterCallback(Mouse.eLClick,function()
    Safe(function()
        if not contextPlayer then return;end
        local person=contextPlayer;local key=IGT_History.Key(person.name,person.steam);
        historyPerson={name=person.name,steam=person.steam};selectedHistoryKey=key;
        ShowPage("history");RefreshHistory();
        Controls.PlayerMenu:SetHide(true);
    end);
end);
local function SaveWindowSize()
    if initialized then State("window_width",expandedWidth);State("window_height",expandedHeight);end
end
Controls.WidthSlider:RegisterSliderCallback(function(value)
    if syncingSize then return;end
    Safe(function() expandedWidth=math.floor((700+math.max(0,math.min(1,value))*900)/10+0.5)*10;SaveWindowSize();ResizeOverlay();end);
end);
Controls.HeightSlider:RegisterSliderCallback(function(value)
    if syncingSize then return;end
    Safe(function() expandedHeight=math.floor((620+math.max(0,math.min(1,value))*380)/10+0.5)*10;SaveWindowSize();ResizeOverlay();end);
end);
Controls.SizeSmall:RegisterCallback(Mouse.eLClick,function() ShowPage("chat",true);end);
Controls.SizeMedium:RegisterCallback(Mouse.eLClick,function() Safe(function() expandedWidth,expandedHeight=960,700;SaveWindowSize();ShowPage(nativeChat and "settings" or "chat");end);end);
Controls.SizeLarge:RegisterCallback(Mouse.eLClick,function() Safe(function() expandedWidth,expandedHeight=1100,820;SaveWindowSize();ShowPage(nativeChat and "settings" or "chat");end);end);
Controls.HistoryNew:RegisterCallback(Mouse.eLClick, function() Safe(function() StartRecording(false); end); end);
Controls.HistoryResume:RegisterCallback(Mouse.eLClick, function() Safe(function() StartRecording(true); end); end);
Controls.HistoryStop:RegisterCallback(Mouse.eLClick, function() Safe(function() ObserveGame(); activeGame=nil; RefreshHistory(); end); end);
Controls.Opacity:RegisterCallback(Mouse.eLClick, function()
    opacityIndex=opacityIndex % #opacities + 1;
    Controls.PanelBackdrop:SetAlpha(opacities[opacityIndex]);
    Controls.OpacityLabel:SetText(T("background", math.floor(opacities[opacityIndex]*100)));
end);
Controls.ForceCancel:RegisterCallback(Mouse.eLClick,function() Controls.ForcePanel:SetHide(true); forceRow=nil; end);
Controls.ForceGo:RegisterCallback(Mouse.eLClick,function()
    Safe(function()
        if forceRow and forceSource then TranslateRow(forceRow,forceSource); end
        Controls.ForcePanel:SetHide(true); forceRow=nil;
    end);
end);
Controls.PlayerNotes:RegisterCallback(Mouse.eLClick, function()
    Safe(function()
        if not initialized then SetStatus(T("status.open.first")); return; end
        if not Controls.ProfilesPanel:IsHidden() then ShowPage("chat");
        else OpenProfiles(selectedRecipientName or editingName); end
    end);
end);
Controls.CloseProfiles:RegisterCallback(Mouse.eLClick, function() ShowPage("chat"); end);
Controls.ProfileSave:RegisterCallback(Mouse.eLClick, function() Safe(function() SaveProfile(false); end); end);
Controls.ProfileDelete:RegisterCallback(Mouse.eLClick, function() Safe(function() SaveProfile(true); end); end);
Controls.OnlineTranslation:RegisterCallback(Mouse.eLClick, function()
    if native then
        native.Enable(not native.Enabled());
        Controls.OnlineTranslationLabel:SetText(native.Enabled() and T("online.on") or T("online.enable"));
        SetStatus(native.Enabled() and T("status.online.on") or T("status.online.off"));
        if not native.Enabled() then CancelSend(); end
    end
end);
Controls.CloseSettings:RegisterCallback(Mouse.eLClick, function() ShowPage("chat"); end);
Controls.SendMode:RegisterCallback(Mouse.eLClick, function() translateOnSend = not translateOnSend; RefreshLabels(); end);
Controls.Receive:RegisterCallback(Mouse.eLClick, function() receiving = not receiving; RefreshLabels(); end);
Controls.Translate:RegisterCallback(Mouse.eLClick, TranslateDraft);
Controls.SendTranslated:RegisterCallback(Mouse.eLClick, function()
    Safe(function()
        if translatedSource ~= Draft():GetText() then InvalidateDraft(); SetStatus(T("status.draft.changed")); return; end
        if BeginSend(translatedDraft, true) then Draft():SetText(""); InvalidateDraft(); Draft():TakeFocus(); end
    end);
end);
Controls.SendOriginal:RegisterCallback(Mouse.eLClick, function() SubmitDraft(); end);
Controls.CancelSend:RegisterCallback(Mouse.eLClick, CancelSend);
-- Draft uses EditMode=0 (chat/Enter mode). EditMode=1 also commits on focus
-- loss, which would send while clicking a language or translation control.
Controls.Draft:RegisterCallback(function() SubmitDraft(); end);
Controls.Paste:RegisterCallback(Mouse.eLClick, function()
    Safe(function()
        pasteCounter = pasteCounter + 1;
        pasteToken = session .. ":" .. pasteCounter;
        State("clipboard_paste_request", pasteToken);
        SetStatus(T("status.paste.asking"));
    end);
end);
Controls.CopyDraft:RegisterCallback(Mouse.eLClick, function()
    Safe(function() State("clipboard_copy", Draft():GetText()); SetStatus(T("status.copied.draft")); end);
end);
Controls.CopyLast:RegisterCallback(Mouse.eLClick, function()
    Safe(function() State("clipboard_copy", lastTranslation); SetStatus(T("status.copied.last")); end);
end);
Controls.ClearPrefix:RegisterCallback(Mouse.eLClick, function() selectedIcon = ""; RefreshLabels(); end);
Controls.MessageColor:RegisterCallback(Mouse.eLClick, function() colorIndex = colorIndex % #colors + 1; RefreshLabels(); end);

local icons = {
    { "IconGold", "[ICON_GOLD]" }, { "IconFood", "[ICON_FOOD]" },
    { "IconProduction", "[ICON_PRODUCTION]" }, { "IconScience", "[ICON_RESEARCH]" },
    { "IconCulture", "[ICON_CULTURE]" }, { "IconFaith", "[ICON_PEACE]" },
    { "IconHappiness", "[ICON_HAPPINESS_1]" }, { "IconMoves", "[ICON_MOVES]" },
    { "IconStrength", "[ICON_STRENGTH]" }
};
for _, entry in ipairs(icons) do
    local control=Controls[entry[1]:gsub("^Icon","Emoji")];local token=entry[2];
    control:RegisterCallback(Mouse.eLClick,function()
        if not initialized then return;end
        Draft():SetText(Draft():GetText() .. " " .. token .. " ");
        InvalidateDraft();Controls.EmojiPanel:SetHide(true);Draft():TakeFocus();
    end);
end
-- Rows of the game's chat stay with the game; only the overlay removes its own.
local function ClearRows()
    if not nativeChat then
        for _, row in ipairs(chatRows) do Controls.TranscriptStack:ReleaseChild(row.Box); end
    end
    chatRows = {};
    RefreshTranscript();
end
for _, entry in ipairs(icons) do
    local token = entry[2];
    Controls[entry[1]]:RegisterCallback(Mouse.eLClick, function()
        selectedIcon = selectedIcon == token and "" or token;
        RefreshLabels();
    end);
end

Controls.Test:RegisterCallback(Mouse.eLClick, function()
    Safe(function()
        -- Three samples in languages other than the reader's, translated into it.
        local queued = 0;
        for _, sample in ipairs({ {"ru","Привет! Давай торговать."}, {"ko","안녕하세요! 거래합시다."}, {"en","Hi! Want to trade?"},
                                  {"uk","Привіт! Давай торгувати."}, {"es","¡Hola! ¿Comerciamos?"} }) do
            if queued < 3 and sample[1] ~= readerLanguage then
                queued = queued + 1;
                Enqueue("test", sample[2], sample[1], readerLanguage, { name = T("test.name", LanguageName(sample[1])) });
            end
        end
        SetStatus(T("status.test"));
    end);
end);

Events.GameMessageChat.Add(OnChat);
if not isLobby then Events.GameplaySetActivePlayer.Add(function()
    if not initialized then return; end
    Safe(function()
        ClearRows();
        Draft():SetText("");
        lastTranslation = "";
        StartSession();
        SetupDropdowns();
        ApplyFixedTexts();
        SetStatus(T("status.player.changed"));
    end);
end); end

ContextPtr:SetInputHandler(function(uiMsg, key)
    if switchedOff then return false; end
    if uiMsg == KeyEvents.KeyDown and key == Keys.VK_ESCAPE then
        if not Controls.EmojiPanel:IsHidden() then Controls.EmojiPanel:SetHide(true);return true;end
        if not Controls.PlayerMenu:IsHidden() then Controls.PlayerMenu:SetHide(true);contextPlayer=nil;return true;end
    end
    if uiMsg == KeyEvents.KeyDown and key == Keys.VK_ESCAPE then dragging=nil; end
    if uiMsg == KeyEvents.KeyDown and key == Keys.VK_ESCAPE and not Controls.ForcePanel:IsHidden() then
        Controls.ForcePanel:SetHide(true); forceRow=nil; return true;
    end
    if uiMsg == KeyEvents.KeyDown and key == Keys.VK_ESCAPE and not Controls.Panel:IsHidden() then
        Controls.Panel:SetHide(true);
        Controls.Settings:SetHide(true);
        Controls.ProfilesPanel:SetHide(true);
        Controls.Toggle:SetHide(nativeChat ~= nil);
        return true;
    end
    return false;
end);
Controls.HeaderDrag:RegisterCallback(Mouse.eLClick,function() end);
if Mouse.eLDblClick then Controls.HeaderDrag:RegisterCallback(Mouse.eLDblClick,function() dragging=nil;if not nativeChat then ShowPage("chat",expanded);end;end); end

-- The game's chat offers a hook when this mod's copy of its script is the one
-- running. Any other script, such as another mod's, simply never answers and this
-- file stays the overlay. The layout numbers come with the hook, beside the stock
-- layout they fit: the input row keeps its place and gives up its right end.
local contextAlive = true;

local function PlaceBar(hook)
    local bar = Controls.ChatBar;
    bar:ChangeParent(hook.Controls.ChatPanel);
    bar:SetAnchor("R,B"); bar:SetOffsetVal(hook.BarX, hook.BarY); bar:SetHide(false);
    bar:ReprocessAnchoring();
end

local function ParkBar()
    Controls.ChatBar:SetHide(true);
    Controls.ChatBar:ChangeParent(ContextPtr);
end

-- Nothing of this file may be inside the game's chat when that screen goes, so
-- whichever of the two closes first brings everything home.
local function TakeBackControls()
    local hook = nativeChat;
    if not hook then return; end
    nativeChat = nil;
    hook.OnRow, hook.OnSend, hook.OnRowGone, hook.OnShowHide, hook.OnShutdown = nil, nil, nil, nil, nil;
    hook.Taken = nil;
    rowStack, rowScroll = Controls.TranscriptStack, Controls.TranscriptScroll;
    for _, row in ipairs(chatRows) do pcall(ParkRowTools, row); end
    chatRows = {};
    pcall(ParkBar);
    print("Improved Chat: took its controls back from the game's chat");
    return hook;
end

ContextPtr:SetShutdown(function() contextAlive = false; initialized = false; TakeBackControls(); end);

local function AttachNativeChat(hook)
    if nativeChat or hook.Dead or switchedOff or not contextAlive then return; end
    -- One translator per chat: a second copy of this screen (KEK's lobby loads one
    -- itself) switches off rather than adding a second bar or translating twice.
    if hook.Taken then
        sendQueue, pending, initialized = {}, {}, false;
        SwitchOff("Another copy of Improved Chat already works in this chat.");
        return;
    end
    local ok, err = pcall(function()
        nativeChat = hook;
        hook.Taken = true;
        rowStack, rowScroll = hook.Controls.ChatStack, hook.Controls.ChatScroll;
        local bar, entry = Controls.ChatBar, hook.Controls.ChatEntry;
        if hook.OwnRecipient then
            bar:SetSizeX(262);
            Controls.Recipient:ChangeParent(bar); Controls.Recipient:SetOffsetVal(0, 0);
            Controls.SendLanguage:SetOffsetVal(160, 0);
        end
        PlaceBar(hook);
        entry:SetAnchor("L,C"); entry:SetSizeX(hook.EntryWidth); entry:ReprocessAnchoring();
        Controls.Toggle:SetHide(true); Controls.Panel:SetHide(true);
        Controls.Expand:SetHide(true); Controls.SizeSmall:SetHide(true); Controls.ChatTab:SetHide(true);
        Controls.SettingsEmoji:SetHide(false);
        Controls.NotesTab:SetOffsetVal(0, 0); Controls.HistoryTab:SetOffsetVal(154, 0); Controls.SettingsTab:SetOffsetVal(308, 0);
        activePage = "settings";
        hook.OnRow = function(row, fromPlayer, toPlayer, text, targetType, stamp)
            -- KEK gives each row its own turn and time, also for chat reloaded from the save.
            row.gameStamp = stamp;
            -- The lobby writes "connected" and the like on rows of its own, with no chat type.
            if targetType ~= nil then OnChat(fromPlayer, toPlayer, text, targetType, row); end
        end;
        hook.OnSend = OnNativeSend;
        hook.OnRowGone = function(row) pcall(ParkRowTools, row); end;
        hook.OnShutdown = TakeBackControls;
        -- Only the lobby calls this: starting a game hides it before anything closes.
        hook.OnShowHide = function(hidden) pcall(function() if hidden then ParkBar(); else PlaceBar(hook); end end); end;
        if initialized then
            local saved = Query("SELECT value FROM igt_state WHERE key='send_translate'");
            translateOnSend = saved[1] ~= nil and saved[1].value == "1";
            SetupDropdowns(); ApplyFixedTexts(); RefreshLabels();
        end
        print("Improved Chat: translating in the game's own chat");
    end);
    if not ok then
        print("Improved Chat: staying a separate window: " .. tostring(err));
        DetachNativeChat();
    end
end

DetachNativeChat = function()
    local hook = TakeBackControls();
    if not hook then return; end
    Controls.Toggle:SetHide(false); Controls.Expand:SetHide(false); Controls.SizeSmall:SetHide(false); Controls.ChatTab:SetHide(false);
    Controls.SettingsEmoji:SetHide(true);
    local entry = hook.Controls.ChatEntry;
    entry:SetAnchor(hook.EntryAnchor); entry:SetSizeX(hook.EntrySize); entry:ReprocessAnchoring();
end

local chatEvent = isLobby and "IGT_LobbyChat" or "IGT_GameChat";
LuaEvents[chatEvent .. "Ready"].Add(AttachNativeChat);
LuaEvents[chatEvent .. "Hello"]();

Initialize = function()
    if switchedOff then return; end
    db = Modding.OpenUserData("InGameTranslateMod", 1);
    StartSession();
    initialized = true;
    SetupDropdowns();
    ApplyFixedTexts();
    RefreshLabels();
    ResizeOverlay();
    SetStatus(IGT_Config and "" or T("status.companion"));
    if not nativeChat then AddLine(T("ready"), ""); end
    print("InGameTranslateMod initialized session " .. session);
end

-- Hidden staging rooms also exist inside a running game. Only the visible
-- lobby owns a mailbox; it must never steal the in-game translator's session.
if isLobby then
    ContextPtr:SetShowHideHandler(function(hidden)
        if switchedOff then return; end
        print("IGT lobby visibility", hidden);
        Safe(function()
            if hidden then
                sendQueue = {};
                pending = {};
                pasteToken = nil;
                initialized = false;
                Controls.CancelSend:SetDisabled(true);
                Controls.Panel:SetHide(true);
                Controls.Settings:SetHide(true);
                Controls.ProfilesPanel:SetHide(true);
                Controls.Toggle:SetHide(nativeChat ~= nil);
                InvalidateDraft();
                if db then
                    Query("UPDATE igt_state SET value='' WHERE key='session' AND value=" .. Quote(session));
                end
            else
                ClearRows();
                Draft():SetText("");
                lastTranslation = "";
                Initialize();
            end
        end);
    end);
else
    Safe(Initialize);
end
ContextPtr:SetUpdate(Update);
