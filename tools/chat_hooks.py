"""Add Improved Chat's hook to the game's own chat scripts.

The in-game chat is stock DiploCorner.lua with or without EUI (EUI only replaces
its layout, with the same control names), and the lobby chat is stock
StagingRoom.lua. The translator stays in its own context; these few lines let it
reach the real rows and the real input box. Nothing is copied from EUI.

One rule keeps this from crashing the game: a control moved into another screen
must be back with its owner before that screen destroys it. Firaxis says so in
UnitFlagManager.lua ("we need to get the selected flag instance back, or we'll
assert clearing the registered button handler") and EUI repeats it. So every place
below where the game destroys rows or closes tells the translator first.

Every fragment must appear exactly once, so a game update that moves one stops
the build instead of shipping a chat that silently lost its hook.
"""
from pathlib import Path

GAME_CHAT = {'event': 'IGT_GameChat', 'padding': 8, 'bar_x': 7, 'bar_y': 3, 'entry': 262,
             'anchor': 'C,C', 'size': 364, 'recipient': 'false', 'target': 'g_iChatTeam, g_iChatPlayer'}
# The lobby has no recipient list of its own, so the bar brings one.
LOBBY_CHAT = {'event': 'IGT_LobbyChat', 'padding': 15, 'bar_x': 0, 'bar_y': 0, 'entry': 561,
              'anchor': 'L,C', 'size': 825, 'recipient': 'true', 'target': '-1, -1'}

ROW_GONE = '''local g_IGT = {};
function g_IGT.Gone( row )
	if( not row.igtGone ) then
		row.igtGone = true;
		if( g_IGT.OnRowGone ) then g_IGT.OnRowGone( row ); end
	end
end
'''

HOOK = '''
-- Improved Chat: this copy of the game's chat script only adds calls to the
-- translator, which lives in its own context. Without it this acts as the original.
g_IGT.Controls = Controls;
g_IGT.RowPadding = {padding};
g_IGT.BarX = {bar_x};
g_IGT.BarY = {bar_y};
g_IGT.EntryWidth = {entry};
g_IGT.EntryAnchor = "{anchor}";
g_IGT.EntrySize = {size};
g_IGT.OwnRecipient = {recipient};
g_IGT.NewRow = function()
	local controlTable = {{}};
	ContextPtr:BuildInstanceForControl( "ChatEntry", controlTable, Controls.ChatStack );
	table.insert( g_ChatInstances, controlTable );
	if( #g_ChatInstances > 100 ) then
		g_IGT.Gone( g_ChatInstances[ 1 ] );
		Controls.ChatStack:ReleaseChild( g_ChatInstances[ 1 ].Box );
		table.remove( g_ChatInstances, 1 );
	end
	if( bFlipper ) then
		controlTable.Box:SetColorChannel( 3, 0.4 );
	end
	bFlipper = not bFlipper;
	return controlTable;
end
ContextPtr:SetShutdown( function()
	g_IGT.Dead = true;
	if( g_IGT.OnShutdown ) then g_IGT.OnShutdown(); end
end );
LuaEvents.{event}Hello.Add( function() LuaEvents.{event}Ready( g_IGT ); end );
LuaEvents.{event}Ready( g_IGT );
'''


def _once(text: str, fragment: str, replacement: str, name: str) -> str:
    if text.count(fragment) != 1:
        raise SystemExit(f'{name}: expected this line exactly once, the game changed: {fragment}')
    return text.replace(fragment, replacement)


def patch_chat(source: str, chat: dict, name: str) -> str:
    """Return the stock chat script with the translator's hook added."""
    text = _once(source, 'local g_ChatInstances = {};', 'local g_ChatInstances = {};\n' + ROW_GONE, name)
    text = _once(text, 'Controls.ChatStack:ReleaseChild( g_ChatInstances[ 1 ].Box );',
                 'g_IGT.Gone( g_ChatInstances[ 1 ] );\n\t\tControls.ChatStack:ReleaseChild( g_ChatInstances[ 1 ].Box );', name)
    text = _once(text, 'Controls.ChatScroll:SetScrollValue( 1 );',
                 'Controls.ChatScroll:SetScrollValue( 1 );\n'
                 '\tif( g_IGT.OnRow ) then g_IGT.OnRow( controlTable, fromPlayer, toPlayer, text, eTargetType'
                 + chat.get('row_extra', '') + ' ); end', name)
    text = _once(text, 'function SendChat( text )',
                 'function SendChat( text )\n'
                 f'    if( g_IGT.OnSend and g_IGT.OnSend( text, {chat["target"]} ) ) then return; end', name)
    text = _once(text, 'Events.GameMessageChat.Add( OnChat );',
                 'Events.GameMessageChat.Add( OnChat );\n' + HOOK.format(**chat), name)
    return text


def patch_lobby(source: str, name: str) -> str:
    """The lobby also wipes its whole chat when it hides, as it does when a game starts.

    The stock list keeps pointing at the wiped rows, and a later hundredth message
    would release one of them, so the copy empties it as well.
    """
    text = patch_chat(source, LOBBY_CHAT, name)
    text = _once(text, 'function ShowHideHandler( bIsHide, bIsInit )',
                 'function ShowHideHandler( bIsHide, bIsInit )\n'
                 '\tif( g_IGT.OnShowHide ) then g_IGT.OnShowHide( bIsHide ); end', name)
    return _once(text, 'Controls.ChatStack:DestroyAllChildren();',
                 'for _, row in ipairs( g_ChatInstances ) do g_IGT.Gone( row ); end\n'
                 '\t\t\tControls.ChatStack:DestroyAllChildren();\n'
                 '\t\t\tg_ChatInstances = {};', name)


# KEK Mod (github.com/OBLASTWAR/kek-mod) ships its own chat and lobby scripts at
# priority 300, so the stock hook never runs under KEK. These add the same hook to
# KEK's own files instead, keeping everything KEK adds:
# - its chat box is 339 px with an emote button at the row's end, so the bar sits left of it;
# - SendChat stores each message in the game (that is how chat reaches the saves), so
#   the translator sends through g_IGT.Send, which does the same, in pieces KEK can store;
# - each row's hover shows KEK's turn and time, which the translator keeps.
KEK_CHAT = dict(GAME_CHAT, entry=237, size=339, bar_x=32, row_extra=', strToolTip')
KEK_STORE = 'Network.SendEnhanceReligion(Game.GetActivePlayer(), -1, text:sub(1,127), iTarget, iToPlayerOrTeam, -1, -1);'
KEK_SEND = '''
-- Improved Chat: the translator's messages are stored the way SendChat stores them.
g_IGT.MaxBytes = 127;
g_IGT.Send = function( text, team, player )
	local iTarget, iToPlayerOrTeam = ChatTargetTypes.CHATTARGET_ALL, -1;
	if( team ~= -1 ) then
		iTarget, iToPlayerOrTeam = ChatTargetTypes.CHATTARGET_TEAM, team;
	elseif( player ~= -1 ) then
		iTarget, iToPlayerOrTeam = ChatTargetTypes.CHATTARGET_PLAYER, player;
	end
	''' + KEK_STORE + '''
	Network.SendChat( text, team, player );
end
'''


TRANSLATOR_PACKAGE = 'c74fe31f-6834-496f-87dc-fb1c471b7fc8'
KEK_LOBBY_LOADER = '''-- Improved Chat, if installed, brings its own part of the lobby.
if( ContentManager ) then
	for _, id in ipairs( ContentManager.GetAllPackageIDs() or {} ) do
		if( tostring( id ):lower():find( "''' + TRANSLATOR_PACKAGE + '''", 1, true ) ) then
			pcall( ContextPtr.LoadNewContext, ContextPtr, "InGameTranslateLobby" );
			break;
		end
	end
end
'''


def patch_kek_chat(source: str, name: str) -> str:
    """KEK's in-game chat (its vanilla-UI and EUI variants) plus the hook."""
    _once(source, KEK_STORE, KEK_STORE, name)  # its SendChat must still store this way
    hook_end = 'LuaEvents.IGT_GameChatReady( g_IGT );\n'
    text = patch_chat(source, KEK_CHAT, name)
    return _once(text, hook_end, KEK_SEND + hook_end, name)


def patch_kek_lobby(source: str, name: str) -> str:
    """KEK's lobby writes its own system lines too, and its kick popup hides it without closing."""
    text = _once(source, 'local g_ChatInstances = {};', 'local g_ChatInstances = {};\n' + ROW_GONE, name)
    release = 'Controls.ChatStack:ReleaseChild( g_ChatInstances[ 1 ].Box );'
    if text.count(release) != 2:
        raise SystemExit(f'{name}: expected two row releases (KekAddSystemChat and OnChat), KEK changed')
    text = text.replace(release, 'g_IGT.Gone( g_ChatInstances[ 1 ] );\n\t\t' + release)
    # Only OnChat's rows are players' messages: its scroll line is the one right before its end.
    on_chat_end = 'Controls.ChatScroll:SetScrollValue( 1 );\n\tend\nend\nEvents.GameMessageChat.Add( OnChat );'
    text = _once(text, on_chat_end, on_chat_end.replace(
        'SetScrollValue( 1 );\n', 'SetScrollValue( 1 );\n'
        '\t\tif( g_IGT.OnRow ) then g_IGT.OnRow( controlTable, fromPlayer, toPlayer, text, eTargetType ); end\n', 1), name)
    text = _once(text, 'function SendChat( text )',
                 'function SendChat( text )\n'
                 f'    if( g_IGT.OnSend and g_IGT.OnSend( text, {LOBBY_CHAT["target"]} ) ) then return; end', name)
    text = _once(text, 'Events.GameMessageChat.Add( OnChat );',
                 'Events.GameMessageChat.Add( OnChat );\n' + HOOK.format(**LOBBY_CHAT), name)
    # KEK's own lobby layout wins over the translator's, so the lobby loads the
    # translator's part itself, only when it is installed: the game's own way to load
    # an add-in screen (InGame.lua), guarded like EUI does (EUI_utilities.lua).
    text = _once(text, 'LuaEvents.IGT_LobbyChatReady( g_IGT );\n', 'LuaEvents.IGT_LobbyChatReady( g_IGT );\n' + KEK_LOBBY_LOADER, name)
    # After the kick-popup early return, which is not a real hide.
    text = _once(text, '    if( bIsHide ) then\n\t\t\tControls.ChatStack:DestroyAllChildren();',
                 '\tif( g_IGT.OnShowHide ) then g_IGT.OnShowHide( bIsHide ); end\n'
                 '    if( bIsHide ) then\n'
                 '\t\t\tfor _, row in ipairs( g_ChatInstances ) do g_IGT.Gone( row ); end\n'
                 '\t\t\tControls.ChatStack:DestroyAllChildren();\n'
                 '\t\t\tg_ChatInstances = {};', name)
    return text


def read_stock(path: Path) -> str:
    """Stock Lua is plain bytes; keep them exactly as shipped."""
    return path.read_bytes().decode('latin-1')


def write_patched(path: Path, text: str) -> None:
    path.write_bytes(text.encode('latin-1'))
