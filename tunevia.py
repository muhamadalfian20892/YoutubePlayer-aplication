import os
import sys

def _configure_stdio():
    """Ensures stdout/stderr are valid UTF-8 streams even in windowed frozen builds."""
    log_dir = os.path.join(os.getenv('APPDATA') or os.path.expanduser('~'), 'tunevia')
    if sys.stdout is None or sys.stderr is None:
        try:
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, 'tunevia.log')
            mode = 'w' if (os.path.exists(log_path) and os.path.getsize(log_path) > 1024 * 1024) else 'a'
            stream = open(log_path, mode, encoding='utf-8', errors='replace', buffering=1)
        except Exception:
            stream = open(os.devnull, 'w', encoding='utf-8')
        if sys.stdout is None:
            sys.stdout = stream
        if sys.stderr is None:
            sys.stderr = stream
    else:
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, 'reconfigure'):
                try:
                    stream.reconfigure(encoding='utf-8', errors='replace')
                except Exception:
                    pass

_configure_stdio()

# --- Path Initialization for Compiled Builds ---
# This MUST be the very first thing to ensure local modules are found.
if getattr(sys, 'frozen', False):
    base_dir = os.path.dirname(sys.executable)
    internal_dir = os.path.join(base_dir, "_internal")
    # Add paths to sys.path if they aren't there
    for d in [internal_dir, base_dir]:
        if os.path.exists(d) and d not in sys.path:
            sys.path.insert(0, d)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

# --- Standard Library Imports ---
import time
import re
import threading
import webbrowser
import ctypes
import json
from datetime import datetime, timezone

# --- Third-Party Imports ---
import wx
import wx.adv
import requests
from packaging import version

# --- Local Application Imports ---
# Importing these after sys.path is fixed
import path_utils
import constants
import settings_manager
import utils
import nvda
import translation_manager
from translation_manager import _
import feature_manager

# --- Nuitka/Standalone Certifi Patch ---
try:
    if hasattr(sys, 'frozen') or '__compiled__' in globals():
        import certifi.core
        possible_cacert = path_utils.get_resource_path(os.path.join("certifi", "cacert.pem"))
        if os.path.exists(possible_cacert):
            certifi.core.where = lambda: possible_cacert
            os.environ['REQUESTS_CA_BUNDLE'] = possible_cacert
            os.environ['SSL_CERT_FILE'] = possible_cacert
except Exception:
    pass

# --- yt-dlp Setup ---
import yt_dlp_manager
yt_dlp_manager.setup_sys_path()

# --- Initialize Translation ---
translation_manager.set_language()

# --- Configure VLC Environment ---
path_utils.setup_vlc_environment()

# --- Core Component Imports ---
from youtube_panel import YoutubeSearchPanel
from audio_player_panel import AudioPlayerPanel
from settings_panel import SettingsPanel
from help_panel import HelpPanel
from ui_components import LanguageSelectionDialog, SoundSettingsDialog, KeyboardShortcutsDialog, CommandPaletteDialog, WhatsNewDialog

# --- Theme Management ---
class ThemeManager:
    """A simple class to manage color themes for the application."""
    THEMES = {}

    @classmethod
    def initialize(cls):
        """Populates the theme colors with fallback defaults."""
        try:
            sys_win_bg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
            sys_win_fg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
            sys_list_bg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_LISTBOX)
            sys_list_fg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_LISTBOXTEXT)
            sys_btn_bg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
            sys_btn_fg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT)
        except Exception:
            sys_win_bg = wx.Colour(255, 255, 255)
            sys_win_fg = wx.Colour(0, 0, 0)
            sys_list_bg = wx.Colour(255, 255, 255)
            sys_list_fg = wx.Colour(0, 0, 0)
            sys_btn_bg = wx.Colour(240, 240, 240)
            sys_btn_fg = wx.Colour(0, 0, 0)

        cls.THEMES = {
            constants.THEME_LIGHT: {
                "bg": sys_win_bg, "fg": sys_win_fg,
                "list_bg": sys_list_bg, "list_fg": sys_list_fg,
                "btn_bg": sys_btn_bg, "btn_fg": sys_btn_fg,
                "text_bg": sys_win_bg, "text_fg": sys_win_fg,
            },
            constants.THEME_DARK: {
                "bg": wx.Colour(45, 45, 45), "fg": wx.Colour(240, 240, 240),
                "list_bg": wx.Colour(35, 35, 35), "list_fg": wx.Colour(230, 230, 230),
                "btn_bg": wx.Colour(75, 75, 75), "btn_fg": wx.Colour(240, 240, 240),
                "text_bg": wx.Colour(60, 60, 60), "text_fg": wx.Colour(230, 230, 230),
            }
        }

    @classmethod
    def apply(cls, window, theme_name):
        if not cls.THEMES:
            cls.initialize()
        if not window:
            return

        if theme_name == constants.THEME_LIGHT:
            window.Freeze()
            try:
                def reset_colors_recursive(win):
                    win.SetBackgroundColour(wx.NullColour)
                    win.SetForegroundColour(wx.NullColour)
                    for child in win.GetChildren():
                        reset_colors_recursive(child)
                reset_colors_recursive(window)
                window.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE))
                window.Refresh()
            except Exception:
                pass
            finally:
                window.Thaw()
            return

        colors = cls.THEMES.get(theme_name, cls.THEMES.get(constants.THEME_DARK))
        if not colors:
            return

        window.Freeze()
        try:
            def apply_colors_recursive(win):
                if isinstance(win, (wx.ListBox, wx.CheckListBox, wx.ListCtrl)):
                    win.SetBackgroundColour(colors["list_bg"])
                    win.SetForegroundColour(colors["list_fg"])
                elif isinstance(win, (wx.TextCtrl, wx.ComboBox, wx.SearchCtrl)):
                    win.SetBackgroundColour(colors["text_bg"])
                    win.SetForegroundColour(colors["text_fg"])
                elif isinstance(win, wx.Button):
                    win.SetBackgroundColour(colors["btn_bg"])
                    win.SetForegroundColour(colors["btn_fg"])
                elif isinstance(win, (wx.StaticBox, wx.CheckBox, wx.RadioBox, wx.StaticText)):
                    win.SetBackgroundColour(colors["bg"])
                    win.SetForegroundColour(colors["fg"])
                else:
                    win.SetBackgroundColour(colors["bg"])
                    win.SetForegroundColour(colors["fg"])
                for child in win.GetChildren():
                    apply_colors_recursive(child)
            apply_colors_recursive(window)
            window.Refresh()
        finally:
            window.Thaw()

# --- System Tray Icon ---
class AppTaskBarIcon(wx.adv.TaskBarIcon):
    def __init__(self, frame):
        super().__init__()
        self.frame = frame
        self._is_playing = False
        self.set_icon(False)
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self.on_left_dclick)
        self.Bind(wx.EVT_MENU, self.on_menu_item)

    def CreatePopupMenu(self):
        menu = wx.Menu()
        self.show_hide_item = menu.Append(wx.ID_ANY, _("Show/Hide Tunevia"))
        play_label = _("Pause") if self._is_playing else _("Play")
        self.play_pause_item = menu.Append(wx.ID_ANY, play_label)
        menu.AppendSeparator()
        self.exit_item = menu.Append(wx.ID_EXIT, _("Exit Tunevia"))
        return menu

    def on_left_dclick(self, event):
        self.frame.toggle_visibility()

    def on_menu_item(self, event):
        evt_id = event.GetId()
        if hasattr(self, 'show_hide_item') and evt_id == self.show_hide_item.GetId():
            self.frame.toggle_visibility()
        elif hasattr(self, 'play_pause_item') and evt_id == self.play_pause_item.GetId():
            self.frame.audio_player_panel.on_play_pause(None)
        elif hasattr(self, 'exit_item') and evt_id == self.exit_item.GetId():
            self.frame.is_closing_from_tray = True
            self.frame.Close()

    def set_icon(self, is_playing):
        self._is_playing = bool(is_playing)
        try:
            icon_path = path_utils.get_resource_path('app.ico')
            if os.path.exists(icon_path):
                icon = wx.Icon(icon_path, wx.BITMAP_TYPE_ICO)
                self.SetIcon(icon, f"{constants.APP_NAME} - {_('Playing') if self._is_playing else _('Paused')}")
        except Exception as e:
            print(f"Warning: Could not load taskbar icon: {e}")

class MainFrame(wx.Frame):
    """
    The main application frame that holds all the UI panels
    and orchestrates communication between them.
    """
    def __init__(self, *args, settings=None, **kw):
        super().__init__(*args, **kw)
        self.settings = settings if settings is not None else settings_manager.load_settings()
        self.ytdl_dialog = None
        self.video_frame = None
        self.taskbar_icon = None
        self.active_tab_keys = []
        self._ui_ready = False
        self.last_clipboard_url = ""
        self.base_title = f"{constants.APP_NAME} v{constants.APP_VERSION}, by {constants.APP_AUTHOR}"
        
        self.InitUI()
        self._ui_ready = True
        
        # Load theme and always-on-top from settings
        ThemeManager.apply(self, self.settings.get("theme", constants.DEFAULT_THEME))
        if self.settings.get("always_on_top", False):
            self.SetWindowStyle(self.GetWindowStyle() | wx.STAY_ON_TOP)
        if feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_SYSTEM_TRAY) and self.settings.get("minimize_to_tray", False):
            self.setup_taskbar_icon()
        
        # Global hotkey event binding (bound once on frame)
        self.Bind(wx.EVT_HOTKEY, self.on_hotkey)

        # Build accelerators for Ctrl+Number shortcuts
        self.rebuild_accelerators_and_hotkeys()
        
        # Play startup sound with a slight delay
        def play_logo_sound():
            startup_cfg = self.settings.get("sound_settings", {}).get("app_startup", True)
            startup_enabled = startup_cfg.get("enabled", True) if isinstance(startup_cfg, dict) else bool(startup_cfg)
            if self.settings.get("sound_effects_enabled", True) and startup_enabled:
                utils.play_sound(self.settings, "app_startup")
        wx.CallLater(500, play_logo_sound)
        
        # Check for post-update version bump, then optionally check quietly for new app updates
        wx.CallLater(2000, self.check_for_updates_and_show_whats_new)
        if self.settings.get("auto_check_updates", True):
            wx.CallLater(4500, lambda: self.on_check_updates(silent=True))
        
        # Set up clipboard monitoring
        self.clipboard_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_clipboard_check_timer, self.clipboard_timer)
        if feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_CLIPBOARD_DETECTION) and self.settings.get("monitor_clipboard_for_urls", False):
            self.clipboard_timer.Start(2000)

        # User activity tracking for intelligent background memory optimization
        self.last_user_activity = time.time()

        # Automatic background memory trimmer (only trims RAM when genuinely idle for 45s or iconized)
        self.idle_memory_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_idle_memory_timer, self.idle_memory_timer)
        self.idle_memory_timer.Start(15000)

        # Global event binding
        self.Bind(wx.EVT_BUTTON, self.on_any_button_click)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        self.Bind(wx.EVT_ICONIZE, self.on_iconize)
        
        # Set initial title
        self.SetTitle(self.base_title)

    def on_iconize(self, event):
        if event.IsIconized():
            if feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_SYSTEM_TRAY) and self.settings.get("minimize_to_tray", False):
                self.setup_taskbar_icon()
                def _hide_if_still_iconized():
                    if self and self.IsIconized() and self.IsShown():
                        self.Hide()
                        nvda.speak(_("Tunevia minimized to system tray."), constants.NVDA_VERBOSITY_DEFAULT)
                wx.CallAfter(_hide_if_still_iconized)
            wx.CallLater(500, utils.optimize_memory)
        event.Skip()

    def _on_idle_memory_timer(self, event):
        now = time.time()
        # Only trim working set if user has been completely idle for >= 45 seconds or window is minimized
        if self.IsIconized() or not self.IsShown() or (now - getattr(self, 'last_user_activity', now) >= 45.0):
            utils.optimize_memory()

    def on_close(self, event):
        if hasattr(self, 'idle_memory_timer') and self.idle_memory_timer.IsRunning():
            self.idle_memory_timer.Stop()
        if hasattr(self, 'clipboard_timer') and self.clipboard_timer.IsRunning():
            self.clipboard_timer.Stop()
        if hasattr(self, 'audio_player_panel') and self.audio_player_panel:
            try:
                self.audio_player_panel.cleanup_on_exit()
            except Exception as e:
                print(f"Error during audio player cleanup: {e}")
        if hasattr(self, 'youtube_panel') and self.youtube_panel and hasattr(self.youtube_panel, 'http_session'):
            try:
                self.youtube_panel.http_session.close()
            except Exception:
                pass
        if getattr(self, 'taskbar_icon', None):
            try:
                self.taskbar_icon.Destroy()
            except Exception:
                pass
            self.taskbar_icon = None
        self.unregister_global_hotkeys()
        self.save_settings()
        event.Skip()

    def InitUI(self):
        panel = wx.Panel(self)
        self.notebook = wx.Notebook(panel)

        # Initialize Core panels (always created)
        self.youtube_panel = YoutubeSearchPanel(self.notebook, self)
        self.audio_player_panel = AudioPlayerPanel(self.notebook, self)
        self.settings_panel = SettingsPanel(self.notebook, self)
        self.help_panel = HelpPanel(self.notebook, self)

        # Initialize optional panels lazily only if the feature is enabled
        if feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_DISCOVER):
            from discovery_panel import DiscoveryPanel
            self.discovery_panel = DiscoveryPanel(self.notebook, self)
        else:
            self.discovery_panel = None

        if feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_RADAR):
            from radar_panel import RadarPanel
            self.radar_panel = RadarPanel(self.notebook, self)
        else:
            self.radar_panel = None

        if feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_HISTORY):
            from history_panel import HistoryPanel
            self.history_panel = HistoryPanel(self.notebook, self)
        else:
            self.history_panel = None

        if feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_FAVORITES):
            from favorites_panel import FavoritesPanel
            self.favorites_panel = FavoritesPanel(self.notebook, self)
        else:
            self.favorites_panel = None

        if feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_LYRICS_SEARCH):
            from lyrics_panel import LyricsSearchPanel
            self.lyrics_panel = LyricsSearchPanel(self.notebook, self)
        else:
            self.lyrics_panel = None

        if feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_STATS):
            from stats_panel import StatsPanel
            self.stats_panel = StatsPanel(self.notebook, self)
        else:
            self.stats_panel = None

        # Tab configuration - only include enabled panels
        self.panels = {
            "youtube": self.youtube_panel,
            "audio_player": self.audio_player_panel,
            "settings": self.settings_panel,
            "help": self.help_panel
        }
        if self.discovery_panel: self.panels["discovery"] = self.discovery_panel
        if self.radar_panel: self.panels["radar"] = self.radar_panel
        if self.history_panel: self.panels["history"] = self.history_panel
        if self.favorites_panel: self.panels["favorites"] = self.favorites_panel
        if self.lyrics_panel: self.panels["lyrics"] = self.lyrics_panel
        if self.stats_panel: self.panels["stats"] = self.stats_panel

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 5)
        panel.SetSizer(main_sizer)

        # Set application icon
        try:
            icon_path = path_utils.get_resource_path('app.ico')
            if os.path.exists(icon_path):
                self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO))
        except Exception as e:
            print(f"Warning: Could not load application icon: {e}")
        
        self._create_menu()
        self.rebuild_notebook()
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_tab_changed)

        # Explicitly ensure the first tab (YouTube Search) is selected and focused on startup
        if self.notebook.GetPageCount() > 0:
            self.notebook.SetSelection(0)
            wx.CallLater(100, lambda: self._select_tab_and_focus(0, speak=False))

    def on_char_hook(self, event):
        import time
        self.last_user_activity = time.time()
        keyCode = event.GetKeyCode()
        modifiers = event.GetModifiers()
        
        # Handle Tab traversal only when focus is on notebook header and Alt/Ctrl are not held (preserve Alt+Tab!)
        if keyCode == wx.WXK_TAB and not (modifiers & (wx.MOD_ALT | wx.MOD_CONTROL)):
            focus = wx.Window.FindFocus()
            if focus == self.notebook:
                page = self.notebook.GetCurrentPage()
                if page:
                    if modifiers & wx.MOD_SHIFT:
                        page.Navigate(wx.NavigationKeyEvent.IsBackward)
                    else:
                        idx = self.notebook.GetSelection()
                        focus_map = {
                            'youtube': 'search_input', 'discovery': 'charts_list', 'radar': 'scan_button',
                            'lyrics': 'tc_judul', 'history': 'search_ctrl', 'favorites': 'favorites_list', 
                            'audio_player': 'play_pause_button', 'stats': 'refresh_btn', 
                            'settings': 'sidebar_list', 'help': 'the_text_box'
                        }
                        widget_name = None
                        if 0 <= idx < len(self.active_tab_keys):
                            widget_name = focus_map.get(self.active_tab_keys[idx])
                        if widget_name and hasattr(page, widget_name) and getattr(page, widget_name).IsEnabled():
                            getattr(page, widget_name).SetFocus()
                        else:
                            page.Navigate(wx.NavigationKeyEvent.IsForward)
                    return

        # Handle Ctrl + Numbers (1-9, 0)
        if (modifiers & wx.MOD_CONTROL) and (ord('0') <= keyCode <= ord('9')):
            digit = int(chr(keyCode))
            idx = digit - 1 if digit > 0 else 9
            if idx < self.notebook.GetPageCount():
                self._select_tab_and_focus(idx, speak=True)
                return

        # Handle Ctrl + K for Command Palette
        if (modifiers & wx.MOD_CONTROL) and keyCode == ord('K'):
            self.on_command_palette(None)
            return

        # Pass to Audio Player if active
        if getattr(self, 'audio_player_panel', None) and self.notebook.GetCurrentPage() == self.audio_player_panel:
            self.audio_player_panel.handle_key_event(event)
        else:
            event.Skip()

    def _create_menu(self):
        menubar = wx.MenuBar()
        file_menu = wx.Menu()
        open_local_item = file_menu.Append(wx.ID_OPEN, _("&Open Local Audio...\tCtrl+O"), _("Open local or lossless audio files"))
        self.Bind(wx.EVT_MENU, lambda e: self.audio_player_panel.on_open_local_audio(None), open_local_item)
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, _("&Exit\tAlt-F4"), _("Exit the application"))
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        menubar.Append(file_menu, _("&File"))
        
        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, _("&About"), _("Show about dialog"))
        self.Bind(wx.EVT_MENU, self.on_about, about_item)
        check_updates_item = help_menu.Append(wx.ID_ANY, _("&Check for Updates..."), _("Check for a newer version of Tunevia"))
        self.Bind(wx.EVT_MENU, self.on_check_updates, check_updates_item)
        whats_new_item = help_menu.Append(wx.ID_ANY, _("What's &New"), _("Show the latest changes"))
        self.Bind(wx.EVT_MENU, lambda e: self.show_whats_new_dialog(force=True), whats_new_item)
        menubar.Append(help_menu, _("&Help"))
        
        self.SetMenuBar(menubar)

    def rebuild_notebook(self):
        """Adds visible tabs to the notebook in the specified order."""
        while self.notebook.GetPageCount() > 0:
            self.notebook.RemovePage(0)
        self.active_tab_keys = []
        tab_order = self.settings.get("tab_order", constants.DEFAULT_TAB_ORDER)
        visible_tabs = set(self.settings.get("visible_tabs", constants.DEFAULT_TAB_ORDER))
        visible_tabs.add("settings")

        # Ensure every panel in self.panels has a deterministic position even if missing from saved tab_order.
        ordered_keys = list(tab_order) + [k for k in constants.DEFAULT_TAB_ORDER if k not in tab_order]
        for tab_key in ordered_keys:
            if tab_key in self.panels and self.panels[tab_key] is not None and tab_key in visible_tabs:
                panel = self.panels[tab_key]
                tab_name = constants.TABS_CONFIG.get(tab_key, {}).get("name", tab_key.capitalize())
                page_idx = self.notebook.GetPageCount()
                shortcut_hint = ""
                if page_idx < 9:
                    shortcut_hint = f" (Ctrl+{page_idx+1})"
                elif page_idx == 9:
                    shortcut_hint = " (Ctrl+0)"

                self.notebook.AddPage(panel, _(tab_name) + shortcut_hint)
                self.active_tab_keys.append(tab_key)

        if getattr(self, '_ui_ready', False):
            self.rebuild_accelerators_and_hotkeys()

    def on_command_palette(self, event):
        commands = []
        # Add tab switching commands for active tabs
        for idx in range(self.notebook.GetPageCount()):
            tab_label = self.notebook.GetPageText(idx)
            clean_label = re.sub(r'\s*\(.*\)$', '', tab_label)
            commands.append({'id': f'switch_tab_{idx}', 'label': _("Switch to {} tab").format(clean_label)})
        
        # Add basic actions
        commands.extend([
            {'id': 'play_pause', 'label': _("Play/Pause Audio")},
            {'id': 'open_local_audio', 'label': _("Open Local / Lossless Audio")},
            {'id': 'open_queue', 'label': _("Open Up-Next Queue")},
            {'id': 'sleep_timer', 'label': _("Sleep Timer")},
            {'id': 'toggle_ab_loop', 'label': _("Set / Clear A-B Loop")},
            {'id': 'cycle_bass_boost', 'label': _("Cycle Bass Boost")},
            {'id': 'toggle_vocal_clarity', 'label': _("Toggle Vocal Clarity Mode")},
            {'id': 'toggle_night_mode', 'label': _("Toggle Night Listening Mode")},
            {'id': 'toggle_nvda_ducking', 'label': _("Toggle Screen Reader Audio Ducking")},
            {'id': 'toggle_lossless_mode', 'label': _("Toggle Lossless Bit-Perfect Mode")},
            {'id': 'track_audio_info', 'label': _("Announce Track and Audio Info")},
            {'id': 'open_settings', 'label': _("Open Sound Settings")},
            {'id': 'change_language', 'label': _("Change Language")},
            {'id': 'check_updates', 'label': _("Check for Updates")},
            {'id': 'about', 'label': _("About Tunevia")}
        ])

        if feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_EQUALIZER):
            commands.append({'id': 'open_equalizer', 'label': _("Audio Equalizer")})
        if feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_SPATIAL_AUDIO):
            commands.append({'id': 'toggle_spatial', 'label': _("Toggle Spatial Audio")})
            commands.append({'id': 'open_spatial', 'label': _("Spatial Audio Settings")})
        if feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_DOWNLOADER):
            commands.append({'id': 'open_downloader', 'label': _("YouTube Downloader")})

        with CommandPaletteDialog(self, commands) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                cmd_id = dlg.get_selected_command_id()
                if not cmd_id:
                    return
                if cmd_id.startswith('switch_tab_'):
                    idx = int(cmd_id.split('_')[-1])
                    self._select_tab_and_focus(idx, speak=True)
                elif cmd_id == 'play_pause': self.audio_player_panel.on_play_pause(None)
                elif cmd_id == 'open_local_audio': self.audio_player_panel.on_open_local_audio(None)
                elif cmd_id == 'open_queue': self.audio_player_panel.on_open_queue(None)
                elif cmd_id == 'sleep_timer': self.audio_player_panel.on_open_sleep_timer(None)
                elif cmd_id == 'toggle_ab_loop': self.audio_player_panel.on_toggle_ab_loop(None)
                elif cmd_id == 'cycle_bass_boost': self.audio_player_panel.on_cycle_bass_boost(None)
                elif cmd_id == 'toggle_vocal_clarity': self.audio_player_panel.on_toggle_vocal_clarity(None)
                elif cmd_id == 'toggle_night_mode': self.audio_player_panel.on_toggle_night_mode(None)
                elif cmd_id == 'toggle_nvda_ducking': self.audio_player_panel.on_toggle_nvda_ducking(None)
                elif cmd_id == 'toggle_lossless_mode': self.audio_player_panel.on_toggle_lossless_mode(None)
                elif cmd_id == 'track_audio_info': self.audio_player_panel.speak_track_and_audio_info()
                elif cmd_id == 'open_settings': self.on_sound_settings(None)
                elif cmd_id == 'change_language': self.on_change_language(None)
                elif cmd_id == 'check_updates': self.on_check_updates(None)
                elif cmd_id == 'about': self.on_about(None)
                elif cmd_id == 'open_equalizer': self.audio_player_panel.on_open_equalizer(None)
                elif cmd_id == 'toggle_spatial': self.audio_player_panel.on_toggle_spatial_audio(None)
                elif cmd_id == 'open_spatial': self.audio_player_panel.on_open_spatial_audio(None)
                elif cmd_id == 'open_downloader': self.show_ytdl_panel()

    def rebuild_accelerators_and_hotkeys(self):
        """Builds the accelerator table for keyboard shortcuts like Ctrl+1, Ctrl+2, etc."""
        # Unregister existing global hotkeys first
        self.unregister_global_hotkeys()
        
        accel_entries = []
        
        # Add notebook tab shortcuts (Ctrl+1 to Ctrl+9, Ctrl+0)
        for i in range(self.notebook.GetPageCount()):
            if i > 9: break
            key_val = i + 1
            if key_val == 10: key_val = 0
            
            tab_id = wx.NewIdRef()
            accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL, ord(str(key_val)), tab_id.GetId()))
            self.Bind(wx.EVT_MENU, lambda event, idx=i: self._select_tab_and_focus(idx, speak=True), id=tab_id.GetId())

        # Command Palette shortcut
        cp_id = wx.NewIdRef()
        accel_entries.append(wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('K'), cp_id.GetId()))
        self.Bind(wx.EVT_MENU, self.on_command_palette, id=cp_id.GetId())

        # Set the local accelerator table
        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))

        # Register global hotkeys (Media keys, etc.) on Windows only if feature is enabled
        if sys.platform == 'win32' and feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_GLOBAL_HOTKEYS):
            hotkey_config = self.settings.get("hotkey_config", {})
            
            # Map action keys to actual functions
            self.hotkey_ids_actions = {
                constants.ALT_SHIFT_PLAY_PAUSE_HK_ID: self.audio_player_panel.on_play_pause,
                constants.ALT_SHIFT_REWIND_HK_ID: self.audio_player_panel.on_rewind,
                constants.ALT_SHIFT_FFWD_HK_ID: self.audio_player_panel.on_ffwd,
                constants.ALT_SHIFT_VOL_UP_HK_ID: lambda e=None: self.audio_player_panel.set_volume(self.audio_player_panel.volume_slider.GetValue() + 5, True),
                constants.ALT_SHIFT_VOL_DOWN_HK_ID: lambda e=None: self.audio_player_panel.set_volume(self.audio_player_panel.volume_slider.GetValue() - 5, True),
                constants.ALT_SHIFT_SHOW_WINDOW_HK_ID: self.toggle_visibility,
                constants.ALT_SHIFT_PLAY_NEXT_HK_ID: self.audio_player_panel.on_play_next,
                constants.ALT_SHIFT_PLAY_PREV_HK_ID: self.audio_player_panel.on_play_previous
            }
            
            # Register them
            for action_key, action_details in constants.CUSTOMIZABLE_ACTIONS.items():
                if action_details["type"] == "global":
                    config = hotkey_config.get(action_key, action_details["default"])
                    mods, vk = config
                    hk_id = action_details["id"]
                    if hk_id in self.hotkey_ids_actions:
                        self.register_single_global_hotkey(hk_id, mods, vk)

    def register_single_global_hotkey(self, hk_id, mods, vk):
        try:
            user32 = ctypes.windll.user32
            user32.UnregisterHotKey(self.GetHandle(), hk_id)
            if not user32.RegisterHotKey(self.GetHandle(), hk_id, mods, vk):
                err = ctypes.GetLastError()
                print(f"Failed to register global hotkey ID {hk_id} (Win32 Error: {err}).")
        except Exception as e:
            print(f"Error registering global hotkey ID {hk_id}: {e}")

    def on_hotkey(self, event):
        hk_id = event.GetId()
        if hasattr(self, 'hotkey_ids_actions') and hk_id in self.hotkey_ids_actions:
            action = self.hotkey_ids_actions[hk_id]
            try: action(event)
            except TypeError: action()
        event.Skip()

    def unregister_global_hotkeys(self):
        if sys.platform == 'win32' and hasattr(self, 'hotkey_ids_actions'):
            user32 = ctypes.windll.user32
            for hk_id in self.hotkey_ids_actions.keys():
                user32.UnregisterHotKey(self.GetHandle(), hk_id)
            self.hotkey_ids_actions = {}

    def _select_tab_and_focus(self, tab_index, speak=False):
        """Switches to a tab and focuses its primary control."""
        selection_changed = (self.notebook.GetSelection() != tab_index)
        if selection_changed:
            self.notebook.SetSelection(tab_index)
        
        page = self.notebook.GetCurrentPage()
        if speak and not selection_changed:
            # Strip the shortcut hint from the page text before speaking
            tab_label = self.notebook.GetPageText(tab_index)
            tab_name = re.sub(r'\s*\(.*\)$', '', tab_label)
            nvda.speak(tab_name + " " + _("tab"))
        
        # Try to focus a sensible widget on the page
        focus_map = {
            'youtube': 'search_input', 'discovery': 'charts_list', 'radar': 'scan_button',
            'lyrics': 'tc_judul', 'history': 'search_ctrl', 'favorites': 'favorites_list', 
            'audio_player': 'play_pause_button', 'stats': 'refresh_btn', 
            'settings': 'sidebar_list', 'help': 'the_text_box'
        }
        
        # Find which tab key this index corresponds to
        if 0 <= tab_index < len(self.active_tab_keys):
            tab_key = self.active_tab_keys[tab_index]
            widget_name = focus_map.get(tab_key)
            if widget_name and hasattr(page, widget_name) and getattr(page, widget_name).IsEnabled():
                getattr(page, widget_name).SetFocus()

    def on_tab_changed(self, event):
        import time
        self.last_user_activity = time.time()
        idx = event.GetSelection()
        tab_name = self.notebook.GetPageText(idx)
        page = self.notebook.GetPage(idx)
        if hasattr(page, 'ensure_data_loaded'):
            page.ensure_data_loaded()
        nvda.speak(_("Switched to {} tab").format(tab_name), constants.NVDA_VERBOSITY_VERBOSE)
        utils.play_sound(self.settings, "tab_navigation")
        event.Skip()

    def on_exit(self, event): self.Close()
    def on_about(self, event):
        msg = f"{constants.APP_NAME} v{constants.APP_VERSION}\n\n{_('A modern, accessible YouTube music player.')}\n\n{_('Developed by')}: {constants.APP_AUTHOR}"
        wx.MessageBox(msg, _("About Tunevia"), wx.OK | wx.ICON_INFORMATION)

    def on_toggle_always_on_top(self, event):
        is_checked = event.IsChecked(); self.settings["always_on_top"] = is_checked
        style = self.GetWindowStyle()
        self.SetWindowStyle(style | wx.STAY_ON_TOP if is_checked else style & ~wx.STAY_ON_TOP)
        self.save_settings()
        nvda.speak(_("Always on top enabled.") if is_checked else _("Always on top disabled."))

    def on_toggle_minimize_to_tray(self, event):
        if not feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_SYSTEM_TRAY):
            nvda.speak(_("System Tray feature is disabled in Feature Manager."))
            return
        is_checked = event.IsChecked(); self.settings["minimize_to_tray"] = is_checked
        if is_checked:
            self.setup_taskbar_icon()
        elif self.taskbar_icon:
            self.taskbar_icon.Destroy()
            self.taskbar_icon = None
        self.save_settings()
        nvda.speak(_("Minimize to tray enabled.") if is_checked else _("Minimize to tray disabled."))

    def on_set_theme(self, theme_name):
        self.settings["theme"] = theme_name
        self.apply_theme()
        self.save_settings()
        nvda.speak(_("Theme set to {}.").format(theme_name.capitalize()))

    def apply_theme(self):
        theme_name = self.settings.get("theme", constants.DEFAULT_THEME)
        ThemeManager.apply(self, theme_name)

    def setup_taskbar_icon(self):
        if not feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_SYSTEM_TRAY):
            return
        if not self.taskbar_icon: self.taskbar_icon = AppTaskBarIcon(self)

    def update_window_title(self, state=None, track_title=None):
        new_title = self.base_title + (f", {_(state)}, {track_title}" if state and track_title else "")
        self.SetTitle(new_title)

    def toggle_visibility(self):
        if self.IsShown() and not self.IsIconized():
            self.Hide()
        else:
            if self.IsIconized():
                self.Iconize(False)
            self.Show()
            self.Raise()
            self.SetFocus()

    def request_audio_play(self, url, title=None, uploader=None, index=None, is_radio=False, upload_date=None, **kwargs):
        # Switch to audio player tab if available
        for i in range(self.notebook.GetPageCount()):
            if self.notebook.GetPage(i) == self.audio_player_panel:
                self.notebook.SetSelection(i)
                break
        self.audio_player_panel.load_and_play(url, title, uploader, index=index, is_radio=is_radio, upload_date=upload_date)
        if self.video_frame: self.video_frame.play_video(url)
        self.add_to_play_history(title, uploader, url, upload_date, kwargs.get('media_source', 'youtube'), duration=kwargs.get('duration'))

    def request_show_video(self):
        if not feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_VIDEO_PLAYER):
            nvda.speak(_("Video player is disabled in Feature Manager."))
            return
        if not self.audio_player_panel.is_loaded or not self.audio_player_panel.video_url: return
        if self.video_frame: self.video_frame.Raise(); return
        from video_player_frame import VideoPlayerFrame
        self.video_frame = VideoPlayerFrame(self, title=_("Tunevia Video Player"))
        self.audio_player_panel.switch_to_video_stream()
        self.video_frame.Show()

    def request_radio_next(self, last_played_url):
        if not feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_RADIO_MODE):
            return
        next_track = self.youtube_panel.get_next_radio_track(last_played_url)
        if next_track: self.request_audio_play(next_track['url'], next_track['title'], next_track['uploader'], is_radio=True)
        else: nvda.speak(_("Radio finished or could not find more songs."))

    def request_lyrics_fetch(self, title, artist):
        if not feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_AUTO_LYRICS):
            return
        if self.lyrics_panel:
            self.lyrics_panel.search_lyrics_auto(title, artist)

    def add_to_play_history(self, title, uploader, url, upload_date=None, media_source='youtube', duration=None):
        if not url: return
        history = self.settings.get("play_history", [])
        if history and history[-1].get('url') == url: return
        history.append({
            "title": title, "uploader": uploader, "url": url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "upload_date": upload_date,
            "source": media_source,
            "duration": duration
        })
        self.settings["play_history"] = history[-constants.MAX_PLAY_HISTORY_ITEMS:]
        if self.history_panel:
            self.history_panel.refresh_list()

    def request_audio_play_direct_link(self, url):
        """Plays a direct YouTube video link pasted into search or clipboard."""
        if not url:
            return
        self.request_audio_play(url, title=_("Direct Link"), uploader=_("YouTube"), index=None, is_radio=False)

    def show_ytdl_panel(self, initial_urls=None):
        if not feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_DOWNLOADER):
            nvda.speak(_("Downloader is disabled in Feature Manager."))
            utils.show_message_dialog(self, _("YouTube Downloader is currently disabled. You can enable it in Settings, Feature Manager."), _("Feature Disabled"), wx.OK | wx.ICON_INFORMATION)
            return
        if not self.ytdl_dialog:
            from downloader_panel import YoutubeDLPanel
            self.ytdl_dialog = wx.Dialog(self, title=_("Downloader"), size=(850, 580), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
            self.ytdl_panel = YoutubeDLPanel(self.ytdl_dialog, self, initial_urls=initial_urls)
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.Add(self.ytdl_panel, 1, wx.EXPAND)
            self.ytdl_dialog.SetSizer(sizer)
            self.ytdl_dialog.Bind(wx.EVT_CLOSE, self.on_ytdl_close)
            self.ytdl_dialog.Show()
        else:
            if initial_urls: self.ytdl_panel.on_add_url(url=initial_urls)
            self.ytdl_dialog.Raise()

    def on_ytdl_close(self, event):
        if hasattr(self, 'ytdl_panel') and self.ytdl_panel:
            if getattr(self.ytdl_panel, 'is_downloading', False):
                utils.show_message_dialog(self.ytdl_dialog, _("A download is in progress. Please wait for it to finish before closing."), _("Download Active"), wx.OK | wx.ICON_WARNING)
                event.Veto()
                return
            if getattr(self.ytdl_panel, 'is_busy_fetching_info', False):
                utils.show_message_dialog(self.ytdl_dialog, _("Fetching information for links. Please wait for it to finish before closing."), _("Operation in Progress"), wx.OK | wx.ICON_WARNING)
                event.Veto()
                return
        self.ytdl_dialog.Destroy()
        self.ytdl_dialog = None

    def toggle_favorite(self):
        """Toggles the currently loaded audio track in or out of favorites."""
        player = getattr(self, 'audio_player_panel', None)
        if not player or not getattr(player, 'video_url', None):
            nvda.speak(_("No track is currently loaded."))
            return
        url = player.video_url
        if self.is_favorite(url):
            self.remove_from_favorites(url)
            player.update_favorite_button(False)
            nvda.speak(_("Removed from favorites."))
        else:
            track_info = {
                'title': player.video_title or _("Unknown Title"),
                'uploader': player.video_uploader or _("Unknown Artist"),
                'url': url,
                'upload_date': getattr(player, 'upload_date', None),
            }
            self.add_to_favorites(track_info)
            player.update_favorite_button(True)

    def add_to_favorites(self, track_info):
        favorites = self.settings.get("favorites", [])
        if any(f.get('url') == track_info.get('url') for f in favorites):
            nvda.speak(_("Already in favorites."))
            return
        favorites.append(track_info)
        self.settings["favorites"] = favorites
        self.save_settings()
        if self.favorites_panel:
            self.favorites_panel.refresh_list()
        nvda.speak(_("Added to favorites: {}").format(track_info.get('title')))
        utils.play_sound(self.settings, "bookmark_added")

    def is_favorite(self, url):
        favorites = self.settings.get("favorites", [])
        return any(f.get('url') == url for f in favorites)

    def remove_from_favorites(self, url):
        favorites = self.settings.get("favorites", [])
        new_favorites = [f for f in favorites if f.get('url') != url]
        if len(new_favorites) < len(favorites):
            self.settings["favorites"] = new_favorites
            settings_manager.save_settings(self.settings)
            if self.favorites_panel:
                self.favorites_panel.refresh_list()
            return True
        return False

    def save_settings(self): settings_manager.save_settings(self.settings)

    def check_for_updates_and_show_whats_new(self):
        last_version_str = self.settings.get("last_run_version")
        current_version_str = constants.APP_VERSION
        if not last_version_str:
            # First launch: record current version without interrupting user with modal dialog
            self.settings["last_run_version"] = current_version_str
            self.save_settings()
            return

        try:
            if version.parse(current_version_str) > version.parse(last_version_str):
                self.settings["last_run_version"] = current_version_str
                self.save_settings()
                nvda.speak(_("Tunevia has been updated to version {}. Check Help menu for What's New.").format(current_version_str), constants.NVDA_VERBOSITY_DEFAULT)
        except version.InvalidVersion:
            print(f"Could not parse version strings for update check: '{current_version_str}' vs '{last_version_str}'")

    def on_check_updates(self, event=None, silent=False):
        """Checks for a newer Tunevia version cleanly without exposing backend infrastructure."""
        if getattr(self, "_checking_updates", False):
            if not silent:
                nvda.speak(_("Getting updates..."))
            return
        self._checking_updates = True
        if not silent:
            nvda.speak(_("Getting updates..."))

        def _worker():
            import updater
            res = updater.check_for_update(constants.APP_VERSION)
            wx.CallAfter(self._handle_update_check_result, res, silent)

        threading.Thread(target=_worker, daemon=True, name="AppUpdateCheckThread").start()

    def _handle_update_check_result(self, res, silent=False):
        self._checking_updates = False
        if not self:
            return
        status = res.get("status")
        if status == "available":
            ver = res.get("latest_version", "")
            notes = res.get("notes") or ""
            msg = res.get("user_message") or _("A new version of Tunevia ({version}) is available.").format(version=ver)
            if notes:
                msg = f"{msg}\n\n{_('What is new:')}\n{notes}"
            msg += "\n\n" + _("Would you like to download and install this update now?")
            nvda.speak(_("A new version of Tunevia ({version}) is available.").format(version=ver), constants.NVDA_VERBOSITY_DEFAULT)
            with wx.MessageDialog(self, msg, _("Update Available"), wx.YES_NO | wx.ICON_INFORMATION) as dlg:
                dlg.SetYesNoLabels(_("&Update Now"), _("&Later"))
                if dlg.ShowModal() == wx.ID_YES:
                    self._start_update_download(res)
        elif not silent:
            msg = res.get("user_message") or _("You are using the latest version of Tunevia ({version}).").format(version=constants.APP_VERSION)
            title = _("Updates") if status == "up_to_date" else _("Update Check")
            icon = wx.ICON_INFORMATION if status == "up_to_date" else wx.ICON_WARNING
            nvda.speak(msg, constants.NVDA_VERBOSITY_DEFAULT)
            utils.show_message_dialog(self, msg, title, wx.OK | icon)

    def _start_update_download(self, update_info):
        from ui_components import UpdateDownloadDialog
        import tempfile
        import updater
        import webbrowser

        dl_url = update_info.get("download_url") or ""
        asset_name = update_info.get("asset_name") or "tunevia_update.zip"
        ver = update_info.get("latest_version") or ""
        sha_url = update_info.get("sha256_url")

        is_direct_asset = dl_url.lower().endswith((".zip", ".exe"))
        if not getattr(sys, "frozen", False) and not is_direct_asset:
            webbrowser.open(dl_url)
            return

        cancel_evt = threading.Event()
        dlg = UpdateDownloadDialog(self, ver)
        dlg.cancel_event = cancel_evt

        def _download_worker():
            ok, payload = updater.download_and_verify_update(
                dl_url,
                asset_name,
                tempfile.gettempdir(),
                progress_cb=lambda p: wx.CallAfter(dlg.update_progress, p) if dlg else None,
                cancel_event=cancel_evt,
                sha256_url=sha_url,
            )

            def _finish():
                if dlg:
                    dlg.EndModal(wx.ID_OK if ok else wx.ID_CANCEL)
                if not self:
                    return
                if not ok:
                    if not cancel_evt.is_set():
                        nvda.speak(payload, constants.NVDA_VERBOSITY_DEFAULT)
                        utils.show_error_dialog(self, payload, _("Update Error"))
                    else:
                        nvda.speak(_("Update cancelled."))
                    return

                if getattr(sys, "frozen", False):
                    app_dir = os.path.dirname(os.path.abspath(sys.executable))
                    started, install_msg = updater.launch_frozen_update_installer(
                        payload, app_dir, exe_name=os.path.basename(sys.executable)
                    )
                    if started:
                        nvda.speak(install_msg, constants.NVDA_VERBOSITY_DEFAULT)
                        utils.show_message_dialog(self, install_msg, _("Installing Update"), wx.OK | wx.ICON_INFORMATION)
                        self.Close()
                    else:
                        utils.show_error_dialog(self, install_msg, _("Update Error"))
                else:
                    msg = _("Update package downloaded cleanly to your temporary folder:\n{}").format(payload)
                    nvda.speak(_("Update downloaded."), constants.NVDA_VERBOSITY_DEFAULT)
                    utils.show_message_dialog(self, msg, _("Download Complete"), wx.OK | wx.ICON_INFORMATION)

            wx.CallAfter(_finish)

        threading.Thread(target=_download_worker, daemon=True, name="AppUpdateDownloadThread").start()
        dlg.ShowModal()
        dlg.Destroy()

    def show_whats_new_dialog(self, force=False):
        current_lang = self.settings.get("language", constants.DEFAULT_PREFERRED_LANGUAGE)
        name, ext = os.path.splitext(constants.CHANGELOG_FILE_NAME)
        lang_specific_filename = f"{name}_{current_lang}{ext}"
        
        lang_specific_path = path_utils.get_resource_path(os.path.join("docs", lang_specific_filename))
        en_fallback_path = path_utils.get_resource_path(os.path.join("docs", f"{name}_en{ext}"))
        default_path = path_utils.get_resource_path(os.path.join("docs", constants.CHANGELOG_FILE_NAME))
        if os.path.exists(lang_specific_path):
            file_to_open = lang_specific_path
        elif os.path.exists(en_fallback_path):
            file_to_open = en_fallback_path
        else:
            file_to_open = default_path
        content = _("Changelog file not found at: {}").format(file_to_open)
        if os.path.exists(file_to_open):
            try:
                with open(file_to_open, "r", encoding="utf-8") as f: content = f.read()
            except Exception as e: content = _("Error reading changelog: {}").format(e)
        with WhatsNewDialog(self, content) as dlg: dlg.ShowModal()

    def on_clipboard_check_timer(self, event):
        if not self.settings.get("monitor_clipboard_for_urls", False):
            return
        if wx.TheClipboard.IsOpened():
            return

        text_data = ""
        if wx.TheClipboard.Open():
            try:
                if wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_TEXT)):
                    data_object = wx.TextDataObject()
                    if wx.TheClipboard.GetData(data_object):
                        text_data = data_object.GetText().strip()
            finally:
                wx.TheClipboard.Close()

        if text_data and text_data != self.last_clipboard_url:
            youtube_link_pattern = re.compile(r'https?://(?:www\.|m\.|music\.)?(?:youtube\.com/(?:watch\?v=|shorts/|live/|embed/|playlist\?list=)|youtu\.be/)([a-zA-Z0-9_-]+)(?:[?&][^\s]*)?')
            match = youtube_link_pattern.search(text_data)
            if match:
                self.last_clipboard_url = text_data
                url = match.group(0)
                
                # Bring window to front to show dialog
                if self.IsIconized():
                    self.Iconize(False)
                if not self.IsShown():
                    self.Show()
                self.Raise()

                with wx.MessageDialog(self, _("A YouTube URL has been detected in your clipboard:\n\n{url}\n\nWhat would you like to do?").format(url=url), _("YouTube URL Detected"), wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION) as dlg:
                    dlg.SetYesNoCancelLabels(_("&Play"), _("&Download"), _("&Cancel"))
                    utils.play_sound(self.settings, "confirm_prompt")
                    result = dlg.ShowModal()

                    if result == wx.ID_YES:
                        self.request_audio_play(url)
                    elif result == wx.ID_NO:
                        self.show_ytdl_panel(initial_urls=[url])
                    # On Cancel, do nothing.

    def on_change_language(self, event):
        current_lang = self.settings.get("language", constants.DEFAULT_PREFERRED_LANGUAGE)
        with LanguageSelectionDialog(self, current_lang) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                new_lang = dlg.get_selected_language_code()
                if new_lang != current_lang:
                    self.settings["language"] = new_lang
                    self.save_settings()
                    utils.show_message_dialog(self, _("Language changed. Please restart the application for the changes to take effect."), _("Restart Required"), wx.OK | wx.ICON_INFORMATION)

    def on_sound_settings(self, event):
        sfx_vol = self.settings.get("sound_effects_volume", self.settings.get("master_volume", 100))
        sfx_enabled = self.settings.get("sound_effects_enabled", True)
        with SoundSettingsDialog(self, self.settings.get("sound_settings", {}), sfx_vol, sfx_enabled) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                new_settings, new_sfx_vol, new_sfx_enabled = dlg.get_new_settings()
                self.settings["sound_settings"] = new_settings
                self.settings["sound_effects_volume"] = new_sfx_vol
                self.settings["sound_effects_enabled"] = new_sfx_enabled
                self.settings["master_volume"] = new_sfx_vol
                self.save_settings()

    def on_customize_shortcuts(self, event):
        with KeyboardShortcutsDialog(self, self.settings.get("hotkey_config", {})) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                new_shortcuts = dlg.get_new_config()
                self.settings["hotkey_config"] = new_shortcuts
                self.save_settings()
                self.rebuild_accelerators_and_hotkeys()

    def on_any_button_click(self, event):
        """Global handler to play a sound on any button click."""
        import time
        self.last_user_activity = time.time()
        utils.play_sound(self.settings, "click")
        event.Skip()

#--- Main Application Entry Point ---
if __name__ == '__main__':
    print("--- Tunevia Startup Debug ---")
    try:
        print("Loading settings...")
        settings = settings_manager.load_settings()

        print("Initializing translation...")
        translation_manager.set_language(settings.get("language"), settings=settings)

        print("Creating wx.App...")
        app = wx.App(False)

        print("Setting wx locale...")
        translation_manager.set_wx_locale(settings.get("language"), settings=settings)

        print("Initializing ThemeManager...")
        ThemeManager.initialize()

        print("Initializing pygame mixer...")
        try:
            import pygame
            pygame.mixer.init()
            print("Pygame mixer initialized.")
            # Preload sounds in background to avoid stutter during navigation
            utils.preload_sounds_async(settings)
        except Exception as e:
            print(f"Could not initialize pygame mixer for sounds: {e}")

        print("Ensuring yt-dlp...")
        if not yt_dlp_manager.ensure_yt_dlp():
            print("Failed to ensure yt-dlp. Exiting.")
            sys.exit(1)

        print("Checking required folders...")
        for folder in ["sound", "libs", "docs", "locales"]:
            path = path_utils.get_resource_path(folder)
            if not os.path.exists(path):
                print(f"Missing folder: {path}")
            else:
                print(f"Found folder: {path}")

        print("Checking for first launch onboarding...")
        if not settings.get("first_launch_completed", False):
            print("First launch detected. Showing Onboarding Wizard...")
            from onboarding_dialog import OnboardingDialog
            with OnboardingDialog(None, settings) as onboarding_dlg:
                onboarding_dlg.ShowModal()
            print("Onboarding completed.")

        print("Creating MainFrame...")
        frame = MainFrame(None, title="Tunevia", settings=settings)
        print("Showing frame...")
        frame.Show()

        print("Starting MainLoop...")
        app.MainLoop()

    except Exception as e:
        print("\nFATAL ERROR DURING STARTUP:")
        import traceback
        tb_text = traceback.format_exc()
        print(tb_text)
        try:
            log_dir = os.path.join(os.getenv('APPDATA') or os.path.expanduser('~'), 'tunevia')
            os.makedirs(log_dir, exist_ok=True)
            crash_path = os.path.join(log_dir, 'crash.log')
            with open(crash_path, 'w', encoding='utf-8') as cf:
                cf.write(tb_text)
        except Exception:
            crash_path = "crash.log"
        if sys.platform == 'win32':
            try:
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"Tunevia failed to start:\n\n{e}\n\nDetails saved to:\n{crash_path}",
                    "Tunevia Startup Error",
                    0x10
                )
            except Exception:
                pass
        if sys.stdin is not None and not getattr(sys, 'frozen', False):
            try:
                input("\nPress Enter to close...")
            except Exception:
                pass
        sys.exit(1)
