"""Windows companion: translation worker and explicitly requested clipboard bridge."""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import queue
import sqlite3
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from contextlib import closing

from companion.bridge import Bridge
from companion.providers import Translator
from companion.credentials import CredentialError, protect_token
from companion.enrollment import CONSENT_VERSION, PUBLIC_BETA_URL, EnrollmentError, EnrollmentManager, online_enabled

APP_DIR = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'InGameTranslateMod'


def game_database() -> Path:
    documents = Path.home() / 'Documents'
    if sys.platform == 'win32':
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0:
            documents = Path(buffer.value)
    return documents / "My Games/Sid Meier's Civilization 5/ModUserData/InGameTranslateMod-1.db"


class App:
    def __init__(self, root):
        self.root = root
        root.title('Improved Chat — companion')
        root.geometry('780x740')
        root.minsize(650, 650)
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self.config_path = APP_DIR / 'settings.json'
        try:
            self.config = json.loads(self.config_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.config = {}
        self.config.setdefault('provider', 'cloudflare')
        self.config.setdefault('cloudflare_url', PUBLIC_BETA_URL)
        self.config.setdefault('db_path', str(game_database()))
        self.enrollment = EnrollmentManager(APP_DIR / 'installation.json')
        self.stop = threading.Event()
        self.messages = queue.Queue()
        self.test_jobs = queue.Queue()
        self.settings_lock = threading.Lock()
        self.version = 0
        self.last_heartbeat = 0
        self.last_history = None
        self.last_session = None
        self.clipboard_seen = None
        self.paste_seen = None
        frame = ttk.Frame(root, padding=14)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Improved Chat', font=('Segoe UI', 17, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Keep this companion running while playing. Open Improved Chat in the lobby or game.').pack(anchor='w', pady=(3, 7))
        ttk.Label(frame, text='Online translation sends message text and your connection IP to the selected service. Player notes, Steam IDs and game history stay on this PC. The public beta needs no account or email.', wraplength=720).pack(anchor='w', pady=(0, 6))
        self.enable_button = ttk.Button(frame, text='Enable online translation', command=self.enable_online)
        self.enable_button.pack(anchor='w', pady=(0, 6))
        if online_enabled(self.config):
            self.enable_button.configure(text='Online translation enabled', state='disabled')
        self.status = tk.StringVar(value='Waiting for Civ V to open the translator…')
        ttk.Label(frame, textvariable=self.status, wraplength=690).pack(anchor='w', pady=(0, 10))
        tabs = ttk.Notebook(frame)
        tabs.pack(fill='both', expand=True)
        chat = ttk.Frame(tabs, padding=10)
        settings = ttk.Frame(tabs, padding=10)
        tabs.add(chat, text='Draft & translations')
        tabs.add(settings, text='Advanced settings')
        ttk.Label(chat, text='Draft text here with normal Ctrl+C / Ctrl+V. Copy it, then click Paste in the game.').pack(anchor='w')
        self.draft = tk.Text(chat, height=5, wrap='word', font=('Segoe UI', 11), undo=True)
        self.draft.pack(fill='x', pady=7)
        buttons = ttk.Frame(chat)
        buttons.pack(fill='x')
        ttk.Button(buttons, text='Copy draft for game', command=self.copy_draft).pack(side='left')
        ttk.Button(buttons, text='Test Russian / Ukrainian / Korean', command=self.test).pack(side='left', padx=8)
        ttk.Label(chat, text='Recent translations (local display; nothing is sent to game chat from this window)').pack(anchor='w', pady=(14, 4))
        self.history = tk.Text(chat, height=12, wrap='word', font=('Segoe UI', 10), state='disabled')
        self.history.pack(fill='both', expand=True)
        self.provider = tk.StringVar(value=self.config['provider'])
        self.email = tk.StringVar(value=self.config.get('mymemory_email', ''))
        self.key = tk.StringVar(value=self.config.get('azure_key', ''))
        self.region = tk.StringVar(value=self.config.get('azure_region', ''))
        self.database = tk.StringVar(value=self.config['db_path'])
        self.cloudflare_url = tk.StringVar(value=self.config.get('cloudflare_url', PUBLIC_BETA_URL))
        self.cloudflare_token = tk.StringVar(value='')
        self.clear_proxy_token = False
        self.proxy_usage = tk.StringVar(value='Cloudflare: no server usage reported yet.')
        ttk.Label(settings, text='Provider').grid(row=0, column=0, sticky='w', pady=5)
        ttk.Combobox(settings, textvariable=self.provider, values=['mymemory', 'azure', 'cloudflare'], state='readonly').grid(row=0, column=1, sticky='ew')
        for row, label, variable in [(1, 'MyMemory contact email (optional)', self.email), (2, 'Azure API key (optional)', self.key), (3, 'Azure region (optional)', self.region), (4, 'Civ V translator database', self.database)]:
            ttk.Label(settings, text=label).grid(row=row, column=0, sticky='w', pady=5)
            ttk.Entry(settings, textvariable=variable, show='*' if row == 2 else '').grid(row=row, column=1, sticky='ew', padx=8)
        ttk.Button(settings, text='Browse…', command=self.browse).grid(row=4, column=2)
        ttk.Label(settings, text='Cloudflare server HTTPS URL').grid(row=5,column=0,sticky='w',pady=5)
        ttk.Entry(settings,textvariable=self.cloudflare_url).grid(row=5,column=1,sticky='ew',padx=8)
        ttk.Label(settings, text='Manual proxy token (optional override)').grid(row=6,column=0,sticky='w',pady=5)
        ttk.Entry(settings,textvariable=self.cloudflare_token,show='*').grid(row=6,column=1,sticky='ew',padx=8)
        ttk.Button(settings,text='Clear token',command=self.clear_cloudflare_token).grid(row=6,column=2)
        ttk.Button(settings, text='Save settings', command=self.save).grid(row=7, column=1, sticky='w', pady=10)
        ttk.Label(settings,textvariable=self.proxy_usage,wraplength=650).grid(row=8,column=0,columnspan=3,sticky='w',pady=3)
        ttk.Label(settings, text='Default: Improved Chat public translation beta. After Enable online translation, this installation registers automatically and receives its allowance. No login, email or key entry is required. Installation credentials are protected by Windows for your user account. An installation is not a verified Steam account.\n\nProvider overrides are optional. MyMemory can work without email; Azure needs your own key. A manual proxy token overrides automatic registration for the configured server. Clear token restores automatic registration after Save. Translation never silently falls back to another provider. Clipboard is read only after Paste in game. Close the companion to stop online translation.', wraplength=650, justify='left').grid(row=9, column=0, columnspan=3, sticky='w', pady=8)
        settings.columnconfigure(1, weight=1)
        root.protocol('WM_DELETE_WINDOW', self.close)
        threading.Thread(target=self.worker, daemon=True).start()
        root.after(350, self.tick)

    def browse(self):
        path = filedialog.askopenfilename(title='Select InGameTranslateMod-1.db', filetypes=[('Civ V database', '*.db')])
        if path:
            self.database.set(path)

    def save(self):
        protected = '' if self.clear_proxy_token else self.config.get('cloudflare_token_protected','')
        new_token = self.cloudflare_token.get().strip()
        try:
            if new_token:
                protected = protect_token(new_token)
        except CredentialError as error:
            self.status.set(str(error))
            return
        with self.settings_lock:
            self.config.update(provider=self.provider.get(), mymemory_email=self.email.get().strip(), azure_key=self.key.get().strip(), azure_region=self.region.get().strip(), db_path=self.database.get().strip(),cloudflare_url=self.cloudflare_url.get().strip(),cloudflare_token_protected=protected)
            if new_token:
                self.config['cloudflare_manual_token'] = True
            elif self.clear_proxy_token:
                self.config['cloudflare_manual_token'] = False
            self.version += 1
            temp = self.config_path.with_suffix('.tmp')
            temp.write_text(json.dumps(self.config, indent=2), encoding='utf-8')
            temp.replace(self.config_path)
        self.cloudflare_token.set('')
        self.clear_proxy_token = False
        self.proxy_usage.set('Cloudflare: no server usage reported yet.')
        self.status.set('Settings saved. Waiting for translation requests…')

    def cancel_old_requests(self, message):
        path = Path(self.config['db_path'])
        if not path.is_file():
            return
        try:
            with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=rw', uri=True, timeout=.2, isolation_level=None)) as db:
                db.execute("UPDATE requests SET status='error',result='',error=? WHERE status IN ('pending','working')", (message,))
        except (sqlite3.Error, OSError):
            pass

    def enable_online(self):
        # A new consent action must not release drafts queued before consent.
        self.cancel_old_requests('Translation was not enabled when this request was queued. Submit it again.')
        with self.settings_lock:
            self.config['online_translation_enabled'] = True
            self.config['online_consent_version'] = CONSENT_VERSION
            temp = self.config_path.with_suffix('.tmp')
            temp.write_text(json.dumps(self.config, indent=2), encoding='utf-8')
            temp.replace(self.config_path)
            self.version += 1
        self.enable_button.configure(text='Online translation enabled', state='disabled')
        self.status.set('Connecting to the translation service. No login or email is needed for the public beta.')

    def refresh_cloudflare_token(self, base):
        with self.settings_lock:
            enabled = online_enabled(self.config) and not self.stop.is_set()
        return self.enrollment.ensure(base, enabled=enabled, force=True).protected_token

    def clear_cloudflare_token(self):
        self.cloudflare_token.set('')
        self.clear_proxy_token = True
        self.status.set('Saved proxy token will be removed when you click Save settings.')

    def copy_draft(self):
        text = self.draft.get('1.0', 'end-1c')
        if len(text.encode('utf-8')) > 6000:
            messagebox.showinfo('Draft too long', 'Keep drafts below 6,000 UTF-8 bytes for this prototype.')
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.set('Draft copied. Click Paste in the in-game translator.')

    def test(self):
        if not online_enabled(self.config):
            self.status.set('Click Enable online translation before sending sample text online.')
            return
        if self.test_jobs.empty():
            self.test_jobs.put(True)
            self.status.set('Testing three short sample messages through the selected provider…')

    def worker(self):
        version, bridge, translator = -1, None, None
        while not self.stop.is_set():
            try:
                with self.settings_lock:
                    config, next_version = self.config.copy(), self.version
                if not online_enabled(config):
                    self.stop.wait(.2)
                    continue
                if version != next_version:
                    if config.get('provider') == 'cloudflare' and not config.get('cloudflare_manual_token'):
                        enrolled = self.enrollment.ensure(config.get('cloudflare_url', PUBLIC_BETA_URL), enabled=True)
                        config['cloudflare_token_protected'] = enrolled.protected_token
                        base = config.get('cloudflare_url', PUBLIC_BETA_URL)
                        config['cloudflare_refresh_token'] = lambda: self.refresh_cloudflare_token(base)
                        self.messages.put(('usage', 'Public beta allowance is shared by this installation’s renewed keys. No Steam login or email required.'))
                    translator = Translator(config)
                    bridge = Bridge(config['db_path'], translator)
                    version = next_version
                if not self.test_jobs.empty():
                    self.test_jobs.get_nowait()
                    lines = []
                    for source, text in [('ru', 'Привет! Нужна помощь?'), ('uk', 'Привіт! Потрібна допомога?'), ('ko', '안녕하세요! 도움이 필요하세요?')]:
                        try:
                            result, detected = translator.translate(text, source, 'en')
                            lines.append(f'{source}: {text}\n(TR {detected}>en) {result}')
                        except Exception as error:
                            lines.append(f'{source}: {error}')
                    self.messages.put(('test', '\n\n'.join(lines)))
                if bridge and not bridge.process_one():
                    self.stop.wait(.2)
                if translator and translator.provider == 'cloudflare' and translator.last_usage:
                    usage = translator.last_usage
                    requests, amount = usage.get('requestsRemaining'), usage.get('inputBytesRemaining')
                    if type(requests) is int and type(amount) is int:
                        self.messages.put(('usage', f'Cloudflare last reported remaining allowance: {max(0,requests)} requests, {max(0,amount)} input bytes.'))
                    translator.last_usage = None
            except EnrollmentError as error:
                self.messages.put(('error', 'Translation service: ' + str(error)))
                self.stop.wait(60)
            except Exception as error:
                self.messages.put(('error', 'Companion: ' + str(error)))
                self.stop.wait(2)

    def tick(self):
        try:
            while True:
                kind, text = self.messages.get_nowait()
                if kind == 'usage':
                    self.proxy_usage.set(text)
                elif kind == 'test':
                    self.set_history(text)
                    self.status.set('Sample test finished. Results below; no messages sent to players.')
                else:
                    self.status.set(text)
        except queue.Empty:
            pass
        path = Path(self.config['db_path'])
        if path.is_file():
            try:
                with closing(sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, timeout=.03, isolation_level=None)) as db:
                    state = dict(db.execute('SELECT key,value FROM igt_state'))
                    session = state.get('session')
                    if session != self.last_session:
                        self.last_session = session
                        self.clipboard_seen = state.get('clipboard_copy')
                        self.paste_seen = state.get('clipboard_paste_request')
                        self.last_history = None
                    if time.monotonic() - self.last_heartbeat > 1:
                        db.execute("INSERT OR REPLACE INTO igt_state(key,value) VALUES('heartbeat',?)", (str(int(time.time())),))
                        db.execute("INSERT OR REPLACE INTO igt_state(key,value) VALUES('online_translation_enabled',?)", ('1' if online_enabled(self.config) else '0',))
                        self.last_heartbeat = time.monotonic()
                    copy = state.get('clipboard_copy')
                    if copy and copy != self.clipboard_seen:
                        self.root.clipboard_clear()
                        self.root.clipboard_append(copy)
                        self.clipboard_seen = copy
                        db.execute("DELETE FROM igt_state WHERE key='clipboard_copy' AND value=?", (copy,))
                        self.clipboard_seen = None
                        self.status.set('Copied from game to Windows clipboard.')
                    token = state.get('clipboard_paste_request')
                    if token and token != self.paste_seen:
                        try:
                            clipboard = self.root.clipboard_get()
                        except tk.TclError:
                            clipboard = ''
                        clipboard = ' '.join(clipboard.replace('\x00', '').splitlines())
                        if len(clipboard.encode('utf-8')) > 6000:
                            clipboard = clipboard.encode('utf-8')[:6000].decode('utf-8', errors='ignore')
                            self.status.set('Clipboard draft shortened to the prototype limit.')
                        db.execute('BEGIN IMMEDIATE')
                        db.execute("INSERT OR REPLACE INTO igt_state(key,value) VALUES('clipboard_paste_result',?)", (clipboard,))
                        db.execute("INSERT OR REPLACE INTO igt_state(key,value) VALUES('clipboard_paste_token',?)", (token,))
                        db.commit()
                        self.paste_seen = token
                    rows = db.execute("SELECT id,text,result,error,detected,target,status FROM requests WHERE session=? AND status IN ('done','error') ORDER BY id DESC LIMIT 30", (session,)).fetchall()
                    signature = tuple((r[0], r[6]) for r in rows)
                    if signature and signature != self.last_history:
                        self.set_history('\n\n'.join(f'{r[1]}\n' + (f'(TR {r[4]}>{r[5]}) {r[2]}' if r[6] == 'done' else f'Error: {r[3]}') for r in reversed(rows)))
                        self.last_history = signature
                        self.status.set('Connected to Civ V. Translation requests appear here and in game.')
            except (sqlite3.Error, tk.TclError, OSError):
                pass  # Game may be creating/updating the mailbox; retry without blocking UI.
        self.root.after(350, self.tick)

    def set_history(self, text):
        self.history.configure(state='normal')
        self.history.delete('1.0', 'end')
        self.history.insert('1.0', text)
        self.history.configure(state='disabled')
        self.history.see('end')

    def close(self):
        self.stop.set()
        self.cancel_old_requests('The translation companion closed. Submit the message again after reopening it.')
        path = Path(self.config['db_path'])
        if path.is_file():
            try:
                with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=rw', uri=True, timeout=.1, isolation_level=None)) as db:
                    db.execute("INSERT OR REPLACE INTO igt_state(key,value) VALUES('online_translation_enabled','0')")
            except (sqlite3.Error, OSError):
                pass
        self.root.destroy()


def main():
    mutex = None
    if sys.platform == 'win32':
        ctypes.windll.kernel32.CreateMutexW.restype = ctypes.c_void_p
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False, 'Local\\InGameTranslateModCompanion')
        if ctypes.windll.kernel32.GetLastError() == 183:
            messagebox.showinfo('InGameTranslateMod', 'The companion is already running. Use its existing window.')
            return
    root = tk.Tk()
    App(root)
    root.mainloop()
    if mutex:
        ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(mutex))


if __name__ == '__main__':
    main()
