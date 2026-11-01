-- InGameTranslateMod: independent UI, no changes to DiploCorner or EUI.
print("IGT shared script loaded (0.8 chat journal)");
-- Stock gameplay, optional EUI, and KEK Mod. KEK does not replace the in-game
-- screen, so this window can be added there without covering KEK's files.
-- Exact package IDs come from the installed official Civ5Pkg manifests;
-- display names are not trusted because modpacks can use arbitrary names.
local compatiblePackages = {};
for _, id in ipairs({
    "293c1ee3-1176-44f6-ac1f-59663826de74", "b685d5de-7cca-4e75-81b4-2f60754e6330",
    "ecf7c605-ba11-4cac-8d80-d71306aac471", "b3030d39-c0d8-4bc7-91b1-7ad1caf585ab",
    "112c22b2-5308-42b6-b734-171ccab3037b", "bbb0d085-a0b1-4475-b007-3e549cf3adc3",
    "ea67aed5-5859-4875-bf3a-360fe9e55d1b", "7459ba32-5764-44ae-8e95-01ad0e0efd48",
    "3f49df54-68b6-44d1-a930-a168628faa59", "46eaeffc-7b1d-443d-bfc8-f825dfefb094",
    "4255f5f7-d3ab-4e55-acee-4670082040ed", "0e3751a1-f840-4e1b-9706-519bf484e59d",
    "6da07636-4123-4018-b643-6575b4ec336b", "8871e748-29a4-4910-8c57-8c99e32d0167",
    "cbe91af6-0683-4326-bc77-58bb489e509f", "570f793e-fc33-417f-ae19-7cecccdd5f85",
    "c74fe31f-6834-496f-87dc-fb1c471b7fc8", "b5932ae4-0f4f-498f-9333-e2d31b20e095"
}) do compatiblePackages[id] = true; end

local function PackageKey(id)
    return tostring(id or ""):lower():gsub("[{}]", "");
end

local function CompatibilityProblem()
    if not Modding or type(Modding.GetActivatedMods) ~= "function" then
        return "Cannot check active mods; Improved Chat is disabled for this session.";
    end
    local ok, mods = pcall(Modding.GetActivatedMods);
    if not ok or type(mods) ~= "table" then return "Active mod check failed; Improved Chat is disabled for this session."; end
    for _, mod in pairs(mods) do
        if type(mod) ~= "table" or not compatiblePackages[PackageKey(mod.ID)] then
            return "Unsupported active mod detected. Improved Chat supports stock gameplay, optional EUI, and KEK Mod.";
        end
    end
    if not ContentManager or type(ContentManager.GetAllPackageIDs) ~= "function" or
       type(ContentManager.IsActive) ~= "function" or not ContentType or ContentType.GAMEPLAY == nil then
        return "Cannot check gameplay packages; Improved Chat is disabled for this session.";
    end
    local packagesOK, packages = pcall(ContentManager.GetAllPackageIDs);
    if not packagesOK or type(packages) ~= "table" then return "Gameplay package check failed; Improved Chat is disabled for this session."; end
    for _, id in pairs(packages) do
        if not compatiblePackages[PackageKey(id)] then
            local activeOK, active = pcall(ContentManager.IsActive, id, ContentType.GAMEPLAY);
            if not activeOK then return "Gameplay package check failed; Improved Chat is disabled for this session."; end
            if active then return "Unsupported gameplay DLC/modpack detected. Improved Chat supports stock gameplay, optional EUI, and KEK Mod."; end
        end
    end
    return nil;
end

local compatibilityDisabled = false;
local function ShowCompatibilityDisabled(reason)
    compatibilityDisabled = true;
    Controls.Panel:SetHide(true);
    if Controls.EmojiPanel then Controls.EmojiPanel:SetHide(true);end
    if Controls.PlayerMenu then Controls.PlayerMenu:SetHide(true);end
    if Controls.ForcePanel then Controls.ForcePanel:SetHide(true); end
    Controls.Toggle:SetHide(true);
    Controls.Toggle:SetDisabled(true);
    Controls.Toggle:SetToolTipString(reason);
    print("Improved Chat compatibility guard: " .. reason);
end

local initialCompatibilityProblem = CompatibilityProblem();
if initialCompatibilityProblem then
    ShowCompatibilityDisabled(initialCompatibilityProblem);
    return;
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

local db;
local native;
local requestTable = IGT_Config and "native_requests" or "requests";
local session = "";
local pending = {};
local chatRows = {};
local lastTranslation = "";
-- New languages are appended so saved positions and older lists stay valid.
local sourceLanguages = { "auto", "en", "ru", "uk", "ko", "ru-latn", "zh", "ja", "de", "fr", "es", "pt", "it", "pl", "tr",
    "be", "kk", "cs", "sk", "nl", "sv", "da", "no", "fi", "hu", "ro", "bg", "sr", "hr", "vi", "id" };
-- Civ V has no Arabic or Greek font, so those are read-only languages.
local targetLanguages = { "ru", "uk", "ko", "en", "ru-latn", "zh", "ja", "de", "fr", "es", "pt", "it", "pl", "tr",
    "be", "kk", "cs", "sk", "nl", "sv", "da", "no", "fi", "hu", "ro", "bg", "sr", "hr", "vi", "id" };
-- My language: the ten languages Civ V ships, whose letters its fonts can show.
local incomingLanguages = { "en", "ru", "ko", "de", "fr", "es", "it", "pl", "ja", "zh" };
local readerScripts = { en="latin", de="latin", fr="latin", es="latin", it="latin", pl="latin", ru="cyrillic", ko="hangul", ja="kana", zh="han" };
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
local compatibilityElapsed = 0;
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
    "en", "be", "kk", "cs", "sk", "da", "no", "fi", "hu", "ro", "bg", "sr", "hr", "el", "vi", "id" };
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

local function T(key, ...) return IGT_Text.T(readerLanguage, key, ...); end
local function LanguageName(code) return T("lang." .. tostring(code)); end
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

local function AddLine(text, stamp, channelColor)
    local row = {};
    ContextPtr:BuildInstanceForControl("IGTChatRow", row, Controls.TranscriptStack);
    row.Message:SetWrapWidth(transcriptWidth);
    row.Box:SetSizeX(transcriptWidth + 104);
    row.TranslateButton:SetHide(true);
    row.stamp = stamp == nil and TurnStamp() or stamp;
    row.channelColor = channelColor;
    row.Message:SetText(IGT_Text.SafeDisplay(text));
    if row.channelColor then row.Message:SetColorByName(row.channelColor); end
    row.Message:SetToolTipString(row.stamp);
    row.Box:SetSizeY(math.max(24, row.Message:GetSizeY() + 8));
    row.Box:ReprocessAnchoring();
    chatRows[#chatRows + 1] = row;
    if #chatRows > 100 then
        Controls.TranscriptStack:ReleaseChild(chatRows[1].Box);
        table.remove(chatRows, 1);
    end
    Controls.TranscriptStack:CalculateSize();
    Controls.TranscriptScroll:CalculateInternalSize();
    Controls.TranscriptScroll:SetScrollValue(1);
    return row;
end

local function UpdateLine(row, text)
    if not row then return AddLine(text); end
    -- A response can arrive after a busy transcript has evicted its row.
    local present = false;
    for _, active in ipairs(chatRows) do if active == row then present = true; break; end; end
    if not present then return; end
    row.Message:SetText(IGT_Text.SafeDisplay(text));
    if row.channelColor then row.Message:SetColorByName(row.channelColor); end
    row.Box:SetSizeY(math.max(24, row.Message:GetSizeY() + 8));
    row.Box:ReprocessAnchoring();
    Controls.TranscriptStack:CalculateSize();
    Controls.TranscriptScroll:CalculateInternalSize();
end

local function RenderChat(row)
    local present = false;
    for _, active in ipairs(chatRows) do if active == row then present = true; break; end end
    if not present then return; end
    local chat = row.chat;
    local name = chat.own and T("you") or DisplayName(chat.name, chat.steamID);
    if chat.targetName then name = name .. " -> " .. DisplayName(chat.targetName, chat.targetSteam); end
    UpdateLine(row, (chat.prefix or "") .. name .. chat.audience .. ": " .. chat.text);
    row.Message:SetToolTipString((row.stamp ~= "" and (row.stamp .. "[NEWLINE]") or "") .. ProfileTooltip(chat.targetName or chat.name, chat.targetName and chat.targetSteam or chat.steamID));
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
    for _, row in ipairs(chatRows) do
        row.Message:SetWrapWidth(transcriptWidth); row.Box:SetSizeX(transcriptWidth + 104);
        row.Box:SetSizeY(math.max(24, row.Message:GetSizeY() + 8)); row.Box:ReprocessAnchoring();
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

ShowPage = function(page, compact)
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
    EmojiButton="tip.emoji", SendMode="tip.sendmode", SendOriginal="tip.send", Translate="tip.preview", Test="tip.test",
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
                    AddLine(T("player.joined", PlainText(DisplayName(name,steam)), summary.games, former .. (not steam and T("name.match") or "")));
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
    State("reader_language", code);
    SetupDropdowns();
    ApplyFixedTexts();
    ShowPage(activePage, not expanded);
    InvalidateDraft();
    RefreshChatNames();
    SetStatus(T("status.language", LanguageName(code)));
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
    for _, setting in ipairs(Query("SELECT key,value FROM igt_state WHERE key IN ('window_width','window_height','reader_language','target_language','source_language')")) do
        saved[setting.key] = setting.value;
        local value=tonumber(setting.value);
        if value then
            if setting.key=='window_width' then expandedWidth=math.max(700,math.min(1600,math.floor(value)));
            elseif setting.key=='window_height' then expandedHeight=math.max(620,math.min(1000,math.floor(value))); end
        end
    end
    readerLanguage = IndexOf(incomingLanguages, saved.reader_language) and saved.reader_language or GameLanguage();
    targetIndex = IndexOf(targetLanguages, saved.target_language) or IndexOf(targetLanguages, readerLanguage == "en" and "ru" or "en");
    sourceIndex = IndexOf(sourceLanguages, saved.source_language) or 1;
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

local function RowIsLive(row)
    for _, active in ipairs(chatRows) do if active == row then return true; end end
    return false;
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
    row.TranslateButton:SetDisabled(false); row.TranslateLabel:SetText(T("original"));
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
        row.TranslateLabel:SetText(row.showOriginal and LanguageName(row.translationTarget or readerLanguage) or T("original"));
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
        row.translationPending=true; row.TranslateButton:SetDisabled(true); row.TranslateLabel:SetText(T("working"));
    end
end

local function OnChat(fromPlayer, toPlayer, text, targetType)
    if not initialized then return; end
    if type(text) ~= "string" or text == "" then return; end
    Safe(function()
        local own = fromPlayer == LocalPlayer();
        if own then
            for i, echo in ipairs(expectedEchoes) do
                if echo.text == text then table.remove(expectedEchoes, i); return; end
            end
        end
        local audience = "";
        -- The front-end lobby does not expose ChatTargetTypes in vanilla.
        local team = ChatTargetTypes and targetType == ChatTargetTypes.CHATTARGET_TEAM;
        local private = ChatTargetTypes and targetType == ChatTargetTypes.CHATTARGET_PLAYER;
        if team then audience = T("team");
        elseif private then audience = T("private"); end
        local row = AddLine("",nil,private and "Magenta_Chat" or team and "Green_Chat" or own and "Gray_Chat" or nil);
        row.chat = { original=text,name = PlayerName(fromPlayer), steamID=IGT_History.SteamID(fromPlayer), own = own, audience = audience, text = text,
            targetSteam=own and private and IGT_History.SteamID(toPlayer) or nil,
            targetName = own and private and PlayerName(toPlayer) or nil };
        RenderChat(row);
        if not own and Mouse.eRClick then
            row.Box:RegisterCallback(Mouse.eRClick,function()
                if not initialized or not RowIsLive(row) then return;end
                contextPlayer={name=row.chat.name,steam=row.chat.steamID};
                local x,y=UIManager:GetMousePos();local sw,sh=UIManager:GetScreenSizeVal();
                Controls.PlayerMenu:SetOffsetVal(math.max(0,math.min(x,sw-220)),math.max(0,math.min(y,sh-112)));
                Controls.PlayerMenu:SetHide(false);
            end);
        end
        if not own then
            row.TranslateButton:SetHide(false); row.TranslateLabel:SetText(T("translate"));
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
        Enqueue("outgoing", Controls.Draft:GetText(), sourceLanguages[sourceIndex], targetLanguages[targetIndex], {
            generation = draftGeneration, draft = Controls.Draft:GetText()
        });
    end);
end

local function BeginSend(text, translated, options)
    if not initialized then SetStatus(T("status.open.game")); return; end
    if #sendQueue > 100 then SetStatus(T("status.send.full")); return; end
    if not isLobby and not PreGame.IsMultiplayerGame() then SetStatus(T("status.mp.only")); return; end
    if not text or not text:find("%S") then SetStatus(T("status.nothing")); return; end
    options = options or { original = Controls.Draft:GetText(), recipient = recipientID, name = selectedRecipientName, steamID = recipientID ~= -1 and IGT_History.SteamID(recipientID) or nil, target = targetLanguages[targetIndex], icon = selectedIcon, color = colors[colorIndex][2] };
    if options.recipient ~= -1 and (PlayerRoster()[options.recipient] ~= options.name or (options.steamID and IGT_History.SteamID(options.recipient) ~= options.steamID)) then
        SetStatus(T("status.recipient.changed")); return;
    end
    local prefix = (translated and "(TranslatorMod) " or "") .. (options.icon ~= "" and options.icon .. " " or "");
    local color = options.color;
    local colorBytes = color ~= "" and (#color + 12) or 0;
    text = IGT_Text.SafeDisplay(color ~= "" and IGT_Text.StripColors(text) or text);
    local chunks, splitError = IGT_Text.Split(text, 240 - #prefix - colorBytes);
    if not chunks or #chunks == 0 then SetStatus(splitError or T("status.nothing")); return; end
    if #chunks > 20 then SetStatus(T("status.too.long")); return; end
    local player = LocalPlayer();
    local batch = { original = options.original,
        label = (translated and T("you.to", options.target) or T("you")) .. (options.recipient ~= -1 and T("to.private", DisplayName(options.name,options.steamID)) or ""),
        total = #chunks, sent = 0, color = color, translated = translated,
        channelColor = options.recipient ~= -1 and "Magenta_Chat" or "Gray_Chat" };
    for i, chunk in ipairs(chunks) do
        sendQueue[#sendQueue + 1] = { text = IGT_Text.Colorize(prefix .. chunk, color), team = -1, player = options.recipient, recipientName = options.name, steamID = options.steamID, active = player, session = session, batch = batch };
    end
    Controls.CancelSend:SetDisabled(false);
    SetStatus(T("status.sending", #chunks, options.recipient == -1 and T("all") or options.name));
    return true;
end

local function SubmitDraft()
    Safe(function()
        local text = Controls.Draft:GetText();
        if not text or not text:find("%S") then return; end
        local roster = PlayerRoster();
        if recipientID ~= -1 and (not roster[recipientID] or roster[recipientID] ~= selectedRecipientName) then SetStatus(T("status.select.recipient")); return; end
        local options = { original = text, recipient = recipientID, name = roster[recipientID], steamID = recipientID ~= -1 and IGT_History.SteamID(recipientID) or nil, target = targetLanguages[targetIndex], icon = selectedIcon, color = colors[colorIndex][2] };
        local accepted;
        if translateOnSend then
            accepted = Enqueue("outgoing", text, sourceLanguages[sourceIndex], options.target, {
                autoSend = true, options = options, generation = submissionGeneration, active = LocalPlayer()
            });
        else accepted = BeginSend(text, false, options); end
        if accepted then
            Controls.Draft:SetText("");
            InvalidateDraft();
            Controls.Draft:TakeFocus();
        end
    end);
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
                info.row.TranslateLabel:SetText(row.status == "error" and T("retry") or T("original"));
                info.row.forceChoose=row.status == "error";
            end
            if row.status == "error" then
                local reason = ErrorText(row.error);
                if info.kind == "auto" and row.error == LIMIT_ERROR then
                    autoPausedUntil = clock + 300; SetStatus(T("status.auto.paused"));
                end
                if info.autoSend then
                    AddLine(T("not.sent", info.original, row.error and reason or T("translation.failed")));
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
                        if not BeginSend(tostring(row.result or ""), true, info.options) then AddLine(T("not.sent.short", info.original)); end
                    end
                elseif info.generation == draftGeneration and info.draft == Controls.Draft:GetText() then
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
        Controls.Draft:SetText(tostring(state.clipboard_paste_result or ""):gsub("[\r\n\t]", " "));
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
    compatibilityElapsed = compatibilityElapsed + delta;
    if compatibilityElapsed >= 5 then
        compatibilityElapsed = 0;
        local reason = CompatibilityProblem();
        if reason then
            sendQueue, pending, initialized = {}, {}, false;
            ShowCompatibilityDisabled(reason);
            return;
        end
    end
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
                    if isLobby and item.player == -1 then Network.SendChat(item.text);
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
Controls.Minimize:RegisterCallback(Mouse.eLClick, function() Controls.Panel:SetHide(true); Controls.Settings:SetHide(true); Controls.ProfilesPanel:SetHide(true); Controls.EmojiPanel:SetHide(true); Controls.PlayerMenu:SetHide(true); Controls.ForcePanel:SetHide(true); forceRow=nil; Controls.Toggle:SetHide(false); end);
Controls.Expand:RegisterCallback(Mouse.eLClick, function() ShowPage("chat", expanded); end);
Controls.More:RegisterCallback(Mouse.eLClick, function() ShowPage("settings"); end);
Controls.ChatTab:RegisterCallback(Mouse.eLClick, function() ShowPage("chat"); end);
Controls.NotesTab:RegisterCallback(Mouse.eLClick, function() Safe(function() OpenProfiles(selectedRecipientName or editingName); end); end);
Controls.HistoryTab:RegisterCallback(Mouse.eLClick, function() Safe(function() ShowPage("history"); RefreshHistory(); end); end);
Controls.SettingsTab:RegisterCallback(Mouse.eLClick, function() ShowPage("settings"); end);
Controls.EmojiButton:RegisterCallback(Mouse.eLClick,function()
    if panelBounds then Controls.EmojiPanel:SetOffsetVal(math.max(0,panelBounds.x+panelBounds.w-362),math.max(0,panelBounds.y+panelBounds.h-254));end
    Controls.EmojiPanel:SetHide(not Controls.EmojiPanel:IsHidden());
end);
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
Controls.SizeMedium:RegisterCallback(Mouse.eLClick,function() Safe(function() expandedWidth,expandedHeight=960,700;SaveWindowSize();ShowPage("chat");end);end);
Controls.SizeLarge:RegisterCallback(Mouse.eLClick,function() Safe(function() expandedWidth,expandedHeight=1100,820;SaveWindowSize();ShowPage("chat");end);end);
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
        if translatedSource ~= Controls.Draft:GetText() then InvalidateDraft(); SetStatus(T("status.draft.changed")); return; end
        if BeginSend(translatedDraft, true) then Controls.Draft:SetText(""); InvalidateDraft(); Controls.Draft:TakeFocus(); end
    end);
end);
Controls.SendOriginal:RegisterCallback(Mouse.eLClick, SubmitDraft);
Controls.CancelSend:RegisterCallback(Mouse.eLClick, CancelSend);
-- Draft uses EditMode=0 (chat/Enter mode). EditMode=1 also commits on focus
-- loss, which would send while clicking a language or translation control.
Controls.Draft:RegisterCallback(SubmitDraft);
Controls.Paste:RegisterCallback(Mouse.eLClick, function()
    Safe(function()
        pasteCounter = pasteCounter + 1;
        pasteToken = session .. ":" .. pasteCounter;
        State("clipboard_paste_request", pasteToken);
        SetStatus(T("status.paste.asking"));
    end);
end);
Controls.CopyDraft:RegisterCallback(Mouse.eLClick, function()
    Safe(function() State("clipboard_copy", Controls.Draft:GetText()); SetStatus(T("status.copied.draft")); end);
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
        Controls.Draft:SetText(Controls.Draft:GetText() .. " " .. token .. " ");
        InvalidateDraft();Controls.EmojiPanel:SetHide(true);Controls.Draft:TakeFocus();
    end);
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
    local reason = CompatibilityProblem();
    if reason then sendQueue, pending, initialized = {}, {}, false; ShowCompatibilityDisabled(reason); return; end
    Safe(function()
        for _, row in ipairs(chatRows) do Controls.TranscriptStack:ReleaseChild(row.Box); end
        chatRows = {};
        Controls.TranscriptStack:CalculateSize();
        Controls.TranscriptScroll:CalculateInternalSize();
        Controls.Draft:SetText("");
        lastTranslation = "";
        StartSession();
        SetupDropdowns();
        ApplyFixedTexts();
        SetStatus(T("status.player.changed"));
    end);
end); end

ContextPtr:SetInputHandler(function(uiMsg, key)
    if compatibilityDisabled then return false; end
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
        Controls.Toggle:SetHide(false);
        return true;
    end
    return false;
end);
Controls.HeaderDrag:RegisterCallback(Mouse.eLClick,function() end);
if Mouse.eLDblClick then Controls.HeaderDrag:RegisterCallback(Mouse.eLDblClick,function() dragging=nil;ShowPage("chat",expanded);end); end

Initialize = function()
    if compatibilityDisabled then return; end
    local reason = CompatibilityProblem();
    if reason then initialized = false; ShowCompatibilityDisabled(reason); return; end
    db = Modding.OpenUserData("InGameTranslateMod", 1);
    StartSession();
    initialized = true;
    SetupDropdowns();
    ApplyFixedTexts();
    RefreshLabels();
    ResizeOverlay();
    SetStatus(IGT_Config and "" or T("status.companion"));
    AddLine(T("ready"), "");
    print("InGameTranslateMod initialized session " .. session);
end

-- Hidden staging rooms also exist inside a running game. Only the visible
-- lobby owns a mailbox; it must never steal the in-game translator's session.
if isLobby then
    ContextPtr:SetShowHideHandler(function(hidden)
        if compatibilityDisabled then return; end
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
                Controls.Toggle:SetHide(false);
                InvalidateDraft();
                if db then
                    Query("UPDATE igt_state SET value='' WHERE key='session' AND value=" .. Quote(session));
                end
            else
                for _, row in ipairs(chatRows) do Controls.TranscriptStack:ReleaseChild(row.Box); end
                chatRows = {};
                Controls.Draft:SetText("");
                lastTranslation = "";
                Initialize();
            end
        end);
    end);
else
    Safe(Initialize);
end
ContextPtr:SetUpdate(Update);
