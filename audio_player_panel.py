import wx
import sys
import threading
import time
import os
import re
import ctypes

# Local application imports
import nvda
import constants
import utils
import path_utils
import feature_manager
import spatial_audio
from translation_manager import _
from ui_components import EqualizerDialog, BookmarksDialog, SpatialAudioDialog, SleepTimerDialog, UpNextQueueDialog

# Ensure VLC DLL paths and environment are configured before importing vlc
path_utils.setup_vlc_environment()

# Safely import the vlc library
try:
    import vlc
    VLC_ENABLED = True
except (Exception, SystemExit) as e:
    VLC_ENABLED = False
    print(f"FATAL: VLC library failed to load ({e}). Please ensure VLC SDK/binaries are available.")

# TurboStream Predictive Stream URL Cache & Concurrency Controls
_STREAM_CACHE_TTL = 14400  # 4 hours TTL
_stream_url_cache = {}
_stream_cache_lock = threading.Lock()
_prefetch_events = {}
_prefetch_lock = threading.Lock()
_ydl_local = threading.local()

def _get_thread_ydl(ydl_opts):
    global _ydl_local
    inst = getattr(_ydl_local, 'instance', None)
    if inst is None:
        import yt_dlp
        inst = yt_dlp.YoutubeDL(ydl_opts)
        _ydl_local.instance = inst
    else:
        inst.params.update(ydl_opts)
    return inst

def _get_vlc_path():
    """Determines the path to the bundled VLC plugins directory."""
    plugins_path = path_utils.get_resource_path('plugins')
    if os.path.isdir(plugins_path):
        return plugins_path
    return None

class AudioPlayerPanel(wx.Panel):
    """
    A wx.Panel that contains all controls for audio playback, using a VLC backend.
    """
    def __init__(self, parent, main_frame):
        super().__init__(parent)
        self.main_frame = main_frame

        # VLC Player State
        self.vlc_instance = None
        self.player = None
        self.vlc_events = None
        self.equalizer = None
        self.equalizer_dialog = None
        self.bookmarks_dialog = None
        self.spatial_dialog = None

        # Spatial Audio & DSP Output State
        self.spatial_processor = spatial_audio.SpatialAudioProcessor(sample_rate=constants.DSP_SAMPLE_RATE)
        self.winmm_output = spatial_audio.WinMMOutput()
        self._using_dsp_output = False
        self._dsp_callbacks = None

        # Audiophile & Blind-First Playback Enhancements
        self.is_local_file = False
        self.local_file_path = None
        self.up_next_queue = []
        self.loop_a_ms = None
        self.loop_b_ms = None
        self._sleep_timer_minutes = 0
        self._sleep_end_time = None
        self._sleep_at_track_end = False

        # Track Information
        self.video_url = None
        self.video_title = None
        self.video_uploader = None
        self.upload_date = None
        self.current_track_index = None
        self.available_audio_tracks = []
        self.current_audio_format_id = None
        self.resume_position_ms = None
        self.audio_url = None
        self.chapters = []

        # Playback State
        self.is_playing = False
        self.is_loaded = False
        self.is_radio_mode = False
        self.is_finished = False
        self.status_message = ""
        self.notification_sound_played = False

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)

        self._current_request_id = 0
        self._pending_seek_pos = None
        self._target_seek_pos = None
        self._seek_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_debounced_seek_timer, self._seek_timer)
        self._pending_spoken_volume = None
        self._vol_speak_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_vol_speak_timer, self._vol_speak_timer)

        # StreamGuard: Resilient Playback & Longform Video Engine
        self._last_valid_pos_ms = 0
        self._last_known_length_ms = 0
        self._last_seek_time = 0.0
        self._is_seeking = False
        self._stream_recovery_count = 0
        self._last_seek_spoken_time = 0.0
        self._is_recovering = False

        self.shortcut_disabling_controls = set()
        self.sponsor_segments = []
        self._skipped_sponsor_segments = set()
        self._is_refreshing_signed_url = False

        # UI elements
        self.volume_box = None
        self.speed_box = None
        self.audio_device_choice = None
        self.video_button = None
        self.shuffle_button = None
        self.repeat_button = None
        self.spatial_toggle_button = None
        self.spatial_settings_button = None
        self.audio_devices = []
        self.devices_populated = False

        self._init_vlc()
        self.init_ui()
        self._sync_dsp_settings()
        self._apply_nvda_duck_hook()
        self._disable_controls()

        wx.CallLater(2000, self.populate_audio_devices_choice)

    def _on_debounced_seek_timer(self, event):
        if self._pending_seek_pos is not None and self.player and self.is_loaded:
            target_pos = self._pending_seek_pos
            self._pending_seek_pos = None
            self._last_valid_pos_ms = target_pos
            self._last_seek_time = time.time()
            self._is_seeking = True
            try:
                self.player.set_time(int(target_pos))
            except Exception as e:
                print(f"Debounced seek error: {e}")
            finally:
                wx.CallLater(1000, self._clear_seeking_flag)

    def _clear_seeking_flag(self):
        self._is_seeking = False
        self._target_seek_pos = None
        self._pending_seek_pos = None

    def _init_vlc(self):
        """Initializes the VLC instance and media player with PyInstaller awareness and robust logging."""
        global VLC_ENABLED
        import traceback

        is_frozen = getattr(sys, 'frozen', False)
        meipass_dir = getattr(sys, '_MEIPASS', None)

        print("=== VLC Initialization Diagnostics ===")
        print(f"[VLC Log] Running from frozen bundle: {is_frozen}")
        if meipass_dir:
            print(f"[VLC Log] sys._MEIPASS directory: {meipass_dir}")

        if not VLC_ENABLED:
            print("[VLC Log] VLC_ENABLED is False (import failed).")
            utils.show_error_dialog(self.main_frame, _("VLC library is not installed. Playback is disabled."), _("VLC Error"))
            return

        # 1. Ensure VLC DLL directory and environment are configured
        path_utils.setup_vlc_environment()
        vlc_dll_file = path_utils.get_resource_path('libvlc.dll')
        vlc_bin_dir = os.path.dirname(vlc_dll_file) if (vlc_dll_file and os.path.exists(vlc_dll_file)) else None

        print(f"[VLC Log] Resolved libvlc.dll path: {vlc_dll_file}")
        print(f"[VLC Log] libvlc.dll exists: {os.path.exists(vlc_dll_file) if vlc_dll_file else False}")
        print(f"[VLC Log] Resolved VLC bin directory: {vlc_bin_dir}")

        # 2. Resolve VLC plugins directory
        plugin_path = path_utils.get_resource_path('plugins')
        plugin_exists = os.path.isdir(plugin_path) if plugin_path else False

        print(f"[VLC Log] Resolved VLC plugin path: {plugin_path}")
        print(f"[VLC Log] VLC plugin path exists: {plugin_exists}")

        # 3. Create VLC Instance and Media Player
        # Note: In VLC 3.0+, VLC_PLUGIN_PATH env var is used; --plugin-path is deprecated.
        try:
            vlc_args = [
                "--no-xlib",
                "--quiet",
                "--no-plugins-cache",
                "--network-caching=500",
                "--file-caching=500",
                "--live-caching=500",
                "--sout-mux-caching=500",
                "--http-reconnect"
            ]

            print(f"[VLC Log] Creating vlc.Instance with args: {vlc_args}")
            self.vlc_instance = vlc.Instance(*vlc_args)

            if self.vlc_instance is None:
                raise RuntimeError("vlc.Instance(...) returned None. Plugin path or VLC binaries may be invalid.")

            print("[VLC Log] VLC Instance creation succeeded.")
            self.player = self.vlc_instance.media_player_new()

            if self.player is None:
                raise RuntimeError("media_player_new() returned None.")

            print("[VLC Log] VLC Media Player creation succeeded.")
            self.equalizer = vlc.AudioEqualizer()
            self._bind_vlc_events()

        except Exception as e:
            VLC_ENABLED = False
            self.vlc_instance = None
            self.player = None
            tb_str = traceback.format_exc()
            print(f"[VLC Log] ERROR: VLC Instance creation failed: {e}")
            print(f"[VLC Log] Exception Traceback:\n{tb_str}")

            error_msg = _(
                "Failed to initialize VLC player backend: {}\n\n"
                "Troubleshooting Information:\n"
                "- Verify that 'libvlc.dll', 'libvlccore.dll', and the 'plugins' directory exist in the application folder.\n"
                "- Verify Microsoft Visual C++ Redistributable is installed.\n"
                "- The application will continue in degraded mode with playback disabled."
            ).format(e)

            utils.show_error_dialog(self.main_frame, error_msg, _("VLC Initialization Error"))
        finally:
            print("========================================")

    def _bind_vlc_events(self):
        """Binds callbacks to VLC media player events."""
        if not self.player: return
        self.vlc_events = self.player.event_manager()
        self.vlc_events.event_attach(vlc.EventType.MediaPlayerEncounteredError, lambda e: wx.CallAfter(self.vlc_on_error, e))
        self.vlc_events.event_attach(vlc.EventType.MediaPlayerEndReached, lambda e: wx.CallAfter(self.vlc_on_finished, e))
        self.vlc_events.event_attach(vlc.EventType.MediaPlayerPlaying, lambda e: wx.CallAfter(self.vlc_on_playing, e))
        self.vlc_events.event_attach(vlc.EventType.MediaPlayerPaused, lambda e: wx.CallAfter(self.vlc_on_paused, e))
        self.vlc_events.event_attach(vlc.EventType.MediaPlayerStopped, lambda e: wx.CallAfter(self.vlc_on_stopped, e))

    def init_ui(self):
        self.hidden_video_panel = wx.Panel(self, size=(1, 1))
        self.hidden_video_panel.Hide()

        vbox = wx.BoxSizer(wx.VERTICAL)

        self.title_text = wx.TextCtrl(self, value="", style=wx.TE_READONLY | wx.TE_CENTER | wx.NO_BORDER)
        self.title_text.SetBackgroundColour(self.GetBackgroundColour())
        vbox.Add(self.title_text, flag=wx.EXPAND | wx.ALL, border=10)

        self.status_display = wx.TextCtrl(self, value="", style=wx.TE_READONLY | wx.TE_CENTER)
        vbox.Add(self.status_display, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        controls_sizer = wx.GridBagSizer(vgap=5, hgap=10)
        self._create_sliders(controls_sizer)
        vbox.Add(controls_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        controls_rows = wx.BoxSizer(wx.VERTICAL)
        self._create_buttons(controls_rows)
        vbox.Add(controls_rows, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        self.SetSizer(vbox)
        self.retranslate_ui()

    def retranslate_ui(self):
        """Updates all translatable text on the panel."""
        self.title_text.SetName(_("Current Track Title"))
        self.title_text.SetToolTip(_("Currently playing audio title and uploader"))
        if not self.is_loaded:
            self.title_text.SetValue(_("No audio loaded"))
            self.status_message = _("No audio loaded. Select 'Play Audio' from YouTube tab.")
            self.status_display.SetValue(self.status_message)

        self.status_display.SetName(_("Playback Status and Time"))
        self.status_display.SetToolTip(_("Current playback time / Total duration. Press shortcut to speak time."))

        if self.volume_box: self.volume_box.SetLabel(_("Volume:"))
        if self.speed_box: self.speed_box.SetLabel(_("Playback Speed:"))

        self.volume_slider.SetName(_("Volume"))
        self.volume_slider.SetToolTip(_("Adjust the audio volume ({min}-{max}%). Arrow keys adjust slider when focused.").format(min=constants.MIN_VOLUME_PERCENT, max=constants.MAX_VOLUME_PERCENT))
        self.speed_slider.SetName(_("Playback Speed"))
        self.speed_slider.SetToolTip(_("Adjust playback speed ({min:.2f}x to {max:.2f}x). Arrow keys adjust slider when focused.").format(min=constants.MIN_PLAYBACK_RATE_FLOAT, max=constants.MAX_PLAYBACK_RATE_FLOAT))

        if hasattr(self, 'audio_device_label') and self.audio_device_label:
            self.audio_device_label.SetLabel(_("Audio Output:"))
        if self.audio_device_choice:
            self.audio_device_choice.SetName(_("Audio Output Device"))
            self.audio_device_choice.SetToolTip(_("Select the audio output device."))

        rate_val = self.speed_slider.GetValue() / 100.0
        self.speed_label.SetLabel(_("Speed: {:.2f}x").format(rate_val))
        self.speed_label.SetToolTip(_("Current playback speed."))

        self.prev_button.SetLabel(_("Previous"))
        self.prev_button.SetName(_("Previous Track"))
        self.prev_button.SetToolTip(_("Play the previous track in the list. (Configurable shortcut)."))

        self.rewind_button.SetLabel(_("Rewind"))
        self.rewind_button.SetName(_("Rewind"))
        self.rewind_button.SetToolTip(_("Seek backward by the interval set in Settings. (Configurable shortcut)."))

        if self.is_finished:
            play_pause_label = _("Replay")
        else:
            play_pause_label = _("Pause") if self.is_playing else _("Play")
        self._set_play_pause_label(play_pause_label)
        self.play_pause_button.SetToolTip(_("Play or pause the audio. (Configurable shortcut)."))

        self.ffwd_button.SetLabel(_("Fast Forward"))
        self.ffwd_button.SetName(_("Fast Forward"))
        self.ffwd_button.SetToolTip(_("Seek forward by the interval set in Settings. (Configurable shortcut)."))

        self.next_button.SetLabel(_("Next"))
        self.next_button.SetName(_("Next Track"))
        self.next_button.SetToolTip(_("Play the next track in the list. (Configurable shortcut)."))

        self.stop_button.SetLabel(_("Stop"))
        self.stop_button.SetName(_("Stop"))
        self.stop_button.SetToolTip(_("Stop audio playback and clear player."))

        self.shuffle_button.SetLabel(_("Shuffle"))
        self.shuffle_button.SetName(_("Shuffle Mode"))
        self.shuffle_button.SetToolTip(_("Toggle shuffle mode for the current playlist/search results."))
        self._update_repeat_button_ui()

        has_video = feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_VIDEO_PLAYER)
        self.video_button.Show(has_video)
        self.video_button.SetName(_("Video Player"))
        self.update_video_button_label()

        has_eq = feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_EQUALIZER)
        self.equalizer_button.Show(has_eq)
        self.equalizer_button.SetLabel(_("Equalizer"))
        self.equalizer_button.SetName(_("Audio Equalizer"))
        self.equalizer_button.SetToolTip(_("Open the audio equalizer settings."))

        has_spatial = feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_SPATIAL_AUDIO)
        self.spatial_toggle_button.Show(has_spatial)
        self.spatial_settings_button.Show(has_spatial)
        self.spatial_settings_button.SetLabel(_("Spatial Settings..."))
        self.spatial_settings_button.SetName(_("Spatial Audio Settings"))
        self.spatial_settings_button.SetToolTip(_("Configure spatial soundstage width, room size, and 3D depth."))
        self._update_spatial_button_ui()

        has_bm = feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_BOOKMARKS)
        self.bookmarks_button.Show(has_bm)
        self.bookmarks_button.SetLabel(_("Bookmarks"))
        self.bookmarks_button.SetName(_("Bookmarks"))
        self.bookmarks_button.SetToolTip(_("View and manage bookmarks for the current track."))

        self.chapters_button.SetLabel(_("Chapters"))
        self.chapters_button.SetName(_("Chapters"))
        self.chapters_button.SetToolTip(_("View and jump to video chapters."))

        has_mono = feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_MONO_AUDIO)
        self.mono_toggle_button.Show(has_mono)
        self.mono_toggle_button.SetLabel(_("Mono"))
        self.mono_toggle_button.SetName(_("Mono Audio"))
        self.mono_toggle_button.SetToolTip(_("Toggle mono/stereo audio output."))

        self.change_track_button.SetLabel(_("Change Audio Track"))
        self.change_track_button.SetName(_("Change Audio Track"))
        self.change_track_button.SetToolTip(_("Change the audio track (e.g., language) if available for the current video."))

        self.share_button.SetLabel(_("Share Current Track"))
        self.share_button.SetName(_("Share Current Track"))
        self.share_button.SetToolTip(_("Copy title, uploader, and URL of the current track to the clipboard for sharing."))

        has_fav = feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_FAVORITES)
        self.favorite_button.Show(has_fav)
        self.update_favorite_button(is_favorite=self.favorite_button.GetValue())

        self.autoplay_checkbox.SetLabel(_("Autoplay Next Track"))
        self.autoplay_checkbox.SetName(_("Autoplay Next Track"))
        self.autoplay_checkbox.SetToolTip(_("Automatically play the next track from the YouTube search results/playlist when the current one finishes"))
        self.Layout()

    def _create_sliders(self, sizer):
        self.volume_box = wx.StaticBox(self, label="")
        volume_sizer = wx.StaticBoxSizer(self.volume_box, wx.VERTICAL)
        vol_val = self.main_frame.settings.get("volume", constants.DEFAULT_VOLUME_PERCENT)
        self.volume_slider = wx.Slider(self, value=vol_val, minValue=constants.MIN_VOLUME_PERCENT, maxValue=constants.MAX_VOLUME_PERCENT, style=wx.SL_HORIZONTAL | wx.SL_LABELS)
        self.volume_slider.SetLineSize(constants.VOLUME_ADJUST_STEP_PERCENT)
        self.volume_slider.SetPageSize(10)
        self.volume_slider.Bind(wx.EVT_SLIDER, self.on_volume_change)
        volume_sizer.Add(self.volume_slider, 1, wx.EXPAND)
        sizer.Add(volume_sizer, pos=(0, 0), span=(1, 1), flag=wx.EXPAND)
        self.shortcut_disabling_controls.add(self.volume_slider)

        self.speed_box = wx.StaticBox(self, label="")
        speed_box_sizer = wx.StaticBoxSizer(self.speed_box, wx.VERTICAL)
        rate_val = self.main_frame.settings.get("playback_rate", constants.DEFAULT_PLAYBACK_RATE_FLOAT)
        slider_val = int(round(rate_val * 100))
        self.speed_label = wx.StaticText(self, label="")
        speed_box_sizer.Add(self.speed_label, flag=wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM, border=2)
        self.speed_slider = wx.Slider(self, value=slider_val, minValue=constants.MIN_RATE_SLIDER, maxValue=constants.MAX_RATE_SLIDER, style=wx.SL_HORIZONTAL)
        self.speed_slider.SetPageSize(constants.RATE_SLIDER_STEP)
        self.speed_slider.Bind(wx.EVT_SLIDER, self.on_speed_slider_change)
        speed_box_sizer.Add(self.speed_slider, 1, wx.EXPAND)
        sizer.Add(speed_box_sizer, pos=(0, 1), span=(1, 1), flag=wx.EXPAND)
        self.shortcut_disabling_controls.add(self.speed_slider)

        sizer.AddGrowableCol(0)
        sizer.AddGrowableCol(1)
        sizer.AddGrowableRow(0)

    def _create_buttons(self, sizer):
        self.prev_button = wx.Button(self, label="")
        self.prev_button.Bind(wx.EVT_BUTTON, self.on_play_previous)
        self.rewind_button = wx.Button(self, label="")
        self.rewind_button.Bind(wx.EVT_BUTTON, self.on_rewind)
        self.play_pause_button = wx.Button(self, label="")
        self.play_pause_button.Bind(wx.EVT_BUTTON, self.on_play_pause)
        self.ffwd_button = wx.Button(self, label="")
        self.ffwd_button.Bind(wx.EVT_BUTTON, self.on_ffwd)
        self.next_button = wx.Button(self, label="")
        self.next_button.Bind(wx.EVT_BUTTON, self.on_play_next)
        self.stop_button = wx.Button(self, label="")
        self.stop_button.Bind(wx.EVT_BUTTON, self.on_stop)
        self.shuffle_button = wx.ToggleButton(self, label="")
        self.shuffle_button.Bind(wx.EVT_TOGGLEBUTTON, self.on_toggle_shuffle)
        self.repeat_button = wx.Button(self, label="")
        self.repeat_button.Bind(wx.EVT_BUTTON, self.on_cycle_repeat)

        self.equalizer_button = wx.Button(self, label="")
        self.equalizer_button.Bind(wx.EVT_BUTTON, self.on_open_equalizer)
        self.spatial_toggle_button = wx.ToggleButton(self, label="")
        self.spatial_toggle_button.Bind(wx.EVT_TOGGLEBUTTON, self.on_toggle_spatial_audio)
        self.spatial_settings_button = wx.Button(self, label="")
        self.spatial_settings_button.Bind(wx.EVT_BUTTON, self.on_open_spatial_audio)
        self.mono_toggle_button = wx.Button(self, label="")
        self.mono_toggle_button.Bind(wx.EVT_BUTTON, self.on_toggle_mono)
        self.bookmarks_button = wx.Button(self, label="")
        self.bookmarks_button.Bind(wx.EVT_BUTTON, self.on_open_bookmarks)
        self.chapters_button = wx.Button(self, label="")
        self.chapters_button.Bind(wx.EVT_BUTTON, self.on_open_chapters)

        self.video_button = wx.Button(self, label="")
        self.video_button.Bind(wx.EVT_BUTTON, self.on_toggle_video)
        self.change_track_button = wx.Button(self, label="")
        self.change_track_button.Bind(wx.EVT_BUTTON, self.on_change_audio_track)
        self.share_button = wx.Button(self, label="")
        self.share_button.Bind(wx.EVT_BUTTON, self.on_share_current_track)
        self.favorite_button = wx.ToggleButton(self, label=_("Favorite"), name=_("Favorite"))
        self.favorite_button.Bind(wx.EVT_TOGGLEBUTTON, self.on_toggle_favorite)
        self.audio_device_label = wx.StaticText(self, label="")
        self.audio_device_choice = wx.Choice(self, choices=[_("Loading Devices...")], name=_("Audio Output Device"))
        self.audio_device_choice.Bind(wx.EVT_CHOICE, self.on_select_audio_device)
        self.shortcut_disabling_controls.add(self.audio_device_choice)
        self.autoplay_checkbox = wx.CheckBox(self, label="", name=_("Autoplay Next Track"))
        self.autoplay_checkbox.SetValue(self.main_frame.settings.get("autoplay_enabled", False))
        self.autoplay_checkbox.Bind(wx.EVT_CHECKBOX, self.on_autoplay_toggle)

        row_transport = wx.BoxSizer(wx.HORIZONTAL)
        for btn in [self.prev_button, self.rewind_button, self.play_pause_button, self.ffwd_button, self.next_button, self.stop_button]:
            row_transport.Add(btn, 0, wx.RIGHT, 5)
        row_transport.Add(self.shuffle_button, 0, wx.LEFT | wx.RIGHT, 5)
        row_transport.Add(self.repeat_button, 0)

        row_audio = wx.BoxSizer(wx.HORIZONTAL)
        for btn in [self.equalizer_button, self.spatial_toggle_button, self.spatial_settings_button, self.mono_toggle_button, self.bookmarks_button]:
            row_audio.Add(btn, 0, wx.RIGHT, 5)
        row_audio.Add(self.chapters_button, 0)

        row_track = wx.BoxSizer(wx.HORIZONTAL)
        for btn in [self.video_button, self.change_track_button, self.share_button, self.favorite_button]:
            row_track.Add(btn, 0, wx.RIGHT, 5)
        row_track.Add(self.audio_device_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 5)
        row_track.Add(self.audio_device_choice, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        row_track.Add(self.autoplay_checkbox, 0, wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(row_transport, 0, wx.ALIGN_CENTER | wx.BOTTOM, 6)
        sizer.Add(row_audio, 0, wx.ALIGN_CENTER | wx.BOTTOM, 6)
        sizer.Add(row_track, 0, wx.ALIGN_CENTER)

    def _set_play_pause_label(self, label):
        if self.play_pause_button:
            self.play_pause_button.SetLabel(label)
            self.play_pause_button.SetName(label)

    def _update_spatial_button_ui(self):
        if not self.spatial_toggle_button:
            return
        is_on = feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_SPATIAL_AUDIO) and self.main_frame.settings.get("spatial_audio_enabled", False)
        self.spatial_toggle_button.SetValue(is_on)
        label = _("Spatial Audio: On") if is_on else _("Spatial Audio: Off")
        self.spatial_toggle_button.SetLabel(label)
        self.spatial_toggle_button.SetName(label)
        self.spatial_toggle_button.SetToolTip(_("Toggle wide spatial soundstage audio processing."))

    def _enable_controls(self, enable=True):
        if not VLC_ENABLED: enable = False
        for ctrl in [self.prev_button, self.rewind_button, self.play_pause_button, 
                     self.ffwd_button, self.next_button, self.stop_button, 
                     self.video_button, self.bookmarks_button, self.favorite_button]:
            if ctrl: ctrl.Enable(enable)
        for ctrl in [self.volume_slider, self.speed_slider, self.audio_device_choice,
                     self.equalizer_button, self.spatial_toggle_button, self.spatial_settings_button,
                     self.mono_toggle_button, self.shuffle_button, self.repeat_button]:
            if ctrl: ctrl.Enable(VLC_ENABLED)
        self.autoplay_checkbox.Enable(VLC_ENABLED)
        self.change_track_button.Enable(enable and len(self.available_audio_tracks) > 1)
        self.share_button.Enable(enable and bool(self.video_url))

    def _disable_controls(self):
        self._enable_controls(False)

    def load_and_play(self, video_url, video_title, video_uploader, index=None, is_radio=False, upload_date=None):
        if not VLC_ENABLED: return
        self.stop_playback(silent=True)
        self.is_local_file = False
        self.local_file_path = None
        self._current_request_id += 1
        request_id = self._current_request_id
        self.video_url, self.video_title, self.video_uploader, self.current_track_index = video_url, video_title, video_uploader, index
        self.is_radio_mode = is_radio
        self.is_playing = self.is_loaded = self.is_finished = self.notification_sound_played = False
        self.audio_url = self.resume_position_ms = self.current_audio_format_id = None
        self._last_valid_pos_ms = 0
        self._last_known_length_ms = 0
        self._pending_seek_pos = None
        self._stream_recovery_count = 0
        self._is_recovering = False
        self._is_seeking = False
        self.upload_date = upload_date
        self.available_audio_tracks = []
        self.chapters = []
        self.chapters_button.Hide()
        self.title_text.SetValue(f"{self.video_title or '...'} - {self.video_uploader or '...'}")
        self._disable_controls()
        self.update_favorite_button(is_favorite=self.main_frame.is_favorite(self.video_url))
        self.main_frame.update_window_title()
        self.shuffle_button.SetValue(self.main_frame.settings.get("shuffle_mode", False))
        self._update_repeat_button_ui()
        if self.main_frame.settings.get("remember_playback_position", False) and not self.is_radio_mode:
            saved_pos_ms = self.main_frame.settings.get("playback_positions", {}).get(self.video_url)
            if saved_pos_ms and saved_pos_ms > 1000:
                self._prompt_to_resume(saved_pos_ms)
        if self.main_frame.settings.get("auto_fetch_lyrics", False):
            self.main_frame.request_lyrics_fetch(self.video_title, self.video_uploader)

        self.sponsor_segments = []
        self._skipped_sponsor_segments = set()
        vid = utils.get_youtube_video_id(self.video_url)
        if vid and self.main_frame.settings.get("enable_sponsorblock", True):
            self.fetch_sponsorblock_segments(vid)

        # TurboStream Instant Cache Hit Check:
        cached_info = self.get_cached_stream_info(video_url)
        if cached_info and cached_info.get('audio_url'):
            print(f"[TurboStream] Instant cache hit for {video_url}! Starting playback immediately.")
            self.audio_url = cached_info['audio_url']
            self.chapters = cached_info.get('chapters', [])
            if self.chapters:
                self.chapters_button.Show()
            else:
                self.chapters_button.Hide()
            self.Layout()
            if not self.upload_date:
                self.upload_date = cached_info.get('upload_date')
            if cached_info.get('formats'):
                self._process_audio_formats(cached_info['formats'])
            self.update_status(_("Starting playback..."))
            self._play_media_with_vlc(request_id)
            wx.CallLater(1500, self.prefetch_next_track_in_queue)
            return

        self.update_status(_("Loading audio stream..."))
        self._fetch_audio_info_and_url(request_id)

    def get_cached_stream_info(self, video_url):
        if not video_url: return None
        with _stream_cache_lock:
            entry = _stream_url_cache.get(video_url)
            if entry:
                if time.time() < entry.get('expires_at', 0):
                    return entry
                else:
                    del _stream_url_cache[video_url]
        return None

    def cache_stream_info(self, video_url, stream_data):
        if not video_url or not stream_data: return
        slim_formats = []
        for f in stream_data.get('formats') or []:
            if f.get('acodec') != 'none' and f.get('format_id'):
                slim_formats.append({
                    'format_id': f.get('format_id'),
                    'acodec': f.get('acodec'),
                    'language': f.get('language'),
                    'format_note': f.get('format_note'),
                    'abr': f.get('abr'),
                    'url': f.get('url'),
                })
        with _stream_cache_lock:
            if len(_stream_url_cache) >= 20:
                oldest_key = min(_stream_url_cache.keys(), key=lambda k: _stream_url_cache[k].get('expires_at', 0))
                del _stream_url_cache[oldest_key]
            _stream_url_cache[video_url] = {
                'audio_url': stream_data.get('audio_url'),
                'chapters': stream_data.get('chapters', []),
                'upload_date': stream_data.get('upload_date'),
                'formats': slim_formats,
                'current_format_id': stream_data.get('current_format_id'),
                'title': stream_data.get('title'),
                'uploader': stream_data.get('uploader'),
                'expires_at': time.time() + _STREAM_CACHE_TTL,
            }

    def prefetch_stream_url(self, video_url):
        """
        TurboStream Predictive Prefetcher: Resolves direct stream URL and metadata
        in a background thread before the user activates playback, caching for instant start.
        """
        if not video_url or not VLC_ENABLED:
            return

        if self.get_cached_stream_info(video_url):
            return

        with _prefetch_lock:
            if video_url in _prefetch_events:
                return
            evt = threading.Event()
            _prefetch_events[video_url] = evt

        def _prefetch_worker():
            try:
                import yt_dlp
                fast_ydl_opts = self._get_base_ydl_opts()
                pref_lang = self.main_frame.settings.get("preferred_audio_language", "").lower().strip()
                if pref_lang:
                    format_selector = f'bestaudio[ext=m4a][language={pref_lang}]/bestaudio[language={pref_lang}]/bestaudio[ext=m4a]/bestaudio/best[ext=mp4]/best'
                else:
                    format_selector = 'bestaudio[ext=m4a]/bestaudio/best[ext=mp4]/best'
                
                if self.main_frame and self.main_frame.video_frame:
                    format_selector = 'best[ext=mp4][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]/best'
                    
                fast_ydl_opts['format'] = format_selector
                ydl = self._get_shared_ydl(fast_ydl_opts)
                info = ydl.extract_info(video_url, download=False)
                if info:
                    audio_url, fmt_id = self._pick_audio_stream(info)
                    if audio_url:
                        self.cache_stream_info(video_url, {
                            'audio_url': audio_url,
                            'chapters': info.get('chapters', []),
                            'upload_date': info.get('upload_date'),
                            'formats': info.get('formats', []),
                            'current_format_id': fmt_id,
                            'title': info.get('title'),
                            'uploader': info.get('uploader') or info.get('channel'),
                        })
                        print(f"[TurboStream] Successfully pre-cached stream for: {video_url}")
            except Exception as e:
                print(f"[TurboStream] Background prefetch error for {video_url}: {e}")
            finally:
                with _prefetch_lock:
                    evt.set()
                    _prefetch_events.pop(video_url, None)

        threading.Thread(target=_prefetch_worker, daemon=True).start()

    def prefetch_next_track_in_queue(self):
        """Predictively pre-caches the upcoming track so playlist/queue transitions are instantaneous."""
        try:
            yt_panel = getattr(self.main_frame, 'youtube_panel', None)
            if not yt_panel: return
            settings = self.main_frame.settings
            next_track = None
            if self.is_radio_mode:
                if hasattr(yt_panel, 'radio_mode_queue') and yt_panel.radio_mode_queue:
                    next_track = yt_panel.radio_mode_queue[0]
            elif settings.get("shuffle_mode", False):
                if hasattr(yt_panel, 'shuffled_search_results') and yt_panel.shuffled_search_results:
                    next_track = yt_panel.shuffled_search_results[0]
            else:
                if hasattr(yt_panel, 'get_next_track_info') and self.current_track_index is not None:
                    next_track = yt_panel.get_next_track_info(self.current_track_index)

            if next_track and isinstance(next_track, dict) and next_track.get('url'):
                print(f"[TurboStream] Pre-caching upcoming queue item: {next_track.get('title')}")
                self.prefetch_stream_url(next_track['url'])
        except Exception as e:
            print(f"[TurboStream] prefetch_next_track_in_queue error: {e}")

    def _prompt_to_resume(self, saved_pos_ms):
        saved_pos_str = utils.format_time_ms(saved_pos_ms)
        prompt_msg = _("Resume playback from saved position ({})?").format(saved_pos_str)
        with wx.MessageDialog(self, prompt_msg, _("Resume Playback?"), wx.YES_NO | wx.ICON_QUESTION | wx.CENTRE) as dlg:
            dlg.SetYesNoLabels(_("&Resume"), _("&Start Over"))
            if dlg.ShowModal() == wx.ID_YES:
                self.resume_position_ms = saved_pos_ms
                nvda.speak(_("Resuming playback at {}").format(saved_pos_str), constants.NVDA_VERBOSITY_VERBOSE)
            else:
                self.clear_saved_position(self.video_url)
                nvda.speak(_("Starting playback from the beginning."), constants.NVDA_VERBOSITY_DEFAULT)

    def update_status(self, message):
        self.status_message = message
        if self.status_display:
            def _set_val():
                if self and self.status_display and self.status_display.GetValue() != self.status_message:
                    self.status_display.SetValue(self.status_message)
            wx.CallAfter(_set_val)

    def _format_track_label(self, fmt):
        lang = fmt.get('language') or ''
        note = fmt.get('format_note') or ''
        codec = fmt.get('acodec', 'N/A').replace('mp4a.40.2', 'aac').replace('mp4a.40.5', 'aac-he')
        bitrate = fmt.get('abr')
        fid = fmt.get('format_id') or ''

        lang_map = {
            'en': 'English', 'en-us': 'English (US)', 'en-gb': 'English (UK)',
            'id': 'Indonesian', 'es': 'Spanish', 'fr': 'French', 'de': 'German',
            'ja': 'Japanese', 'ko': 'Korean', 'zh': 'Chinese', 'pt': 'Portuguese',
            'ru': 'Russian', 'it': 'Italian', 'hi': 'Hindi', 'ar': 'Arabic'
        }
        lang_clean = lang.lower().strip()
        lang_display = lang_map.get(lang_clean, lang.upper() if lang and lang != 'und' else '')

        parts = []
        if lang_display:
            parts.append(lang_display)
        if note and note.lower() not in (lang_display.lower() if lang_display else ''):
            parts.append(note)

        details = []
        if codec != 'N/A':
            details.append(codec)
        if bitrate:
            details.append(f"{bitrate:.0f} kbps")
        elif not details and fid:
            details.append(f"format {fid}")

        header = " - ".join(parts) if parts else (_("Audio Track") + f" {fid}")
        if details:
            return f"{header} ({', '.join(details)})"
        return header

    def _pick_audio_stream(self, info):
        """Returns (url, format_id) for an audio-bearing stream, avoiding video-only fallbacks."""
        if not info or not isinstance(info, dict):
            return None, None
        direct_url = info.get('url')
        if direct_url and info.get('acodec') != 'none':
            return direct_url, info.get('format_id')
        for f in info.get('requested_formats') or []:
            if f.get('url') and f.get('acodec') not in (None, 'none'):
                return f.get('url'), f.get('format_id')
        audio_fmts = [
            f for f in (info.get('formats') or [])
            if f.get('url') and f.get('acodec') not in (None, 'none')
        ]
        if audio_fmts:
            audio_fmts.sort(key=lambda f: (f.get('ext') == 'm4a', f.get('abr') or 0), reverse=True)
            best = audio_fmts[0]
            return best.get('url'), best.get('format_id')
        return direct_url, info.get('format_id')

    def _get_base_ydl_opts(self):
        """Returns a base dictionary of yt-dlp options, including cookie settings."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'noprogress': True,
            'noplaylist': True,
            'check_formats': False,
            'forcejson': True,
            'nocheckcertificate': True,
            'socket_timeout': 6,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'player_skip': ['configs', 'webpage']
                }
            },
        }
        import settings_manager
        cookies_path = settings_manager.get_effective_cookies_path(self.main_frame.settings)
        if cookies_path and os.path.exists(cookies_path):
            ydl_opts['cookiefile'] = cookies_path
        return ydl_opts

    def _get_shared_ydl(self, ydl_opts):
        return _get_thread_ydl(ydl_opts)

    def _fetch_audio_info_and_url(self, request_id):
        if not self.video_url: return
        self.update_status(_("Loading audio info..."))
        nvda.speak(_("Loading audio..."), constants.NVDA_VERBOSITY_DEFAULT)
        wx.BeginBusyCursor()
        threading.Thread(target=self._fetch_audio_info_thread, args=(request_id,), daemon=True).start()

    def _process_audio_formats(self, formats):
        try:
            audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('format_id')]
            if not audio_formats:
                return

            seen_ids = set()
            new_tracks = []
            for f in audio_formats:
                fid = str(f.get('format_id'))
                if fid in seen_ids:
                    continue
                seen_ids.add(fid)

                lang = (f.get('language') or 'und').lower()
                bitrate = f.get('abr') or 0
                label = self._format_track_label(f)
                new_tracks.append({
                    'id': fid,
                    'url': f.get('url'),
                    'label': label,
                    'lang': lang,
                    'bitrate': bitrate,
                })

            if not new_tracks:
                return

            existing_map = {t['id']: t for t in self.available_audio_tracks}
            for t in new_tracks:
                if t['id'] in existing_map:
                    if not existing_map[t['id']].get('url') and t.get('url'):
                        existing_map[t['id']]['url'] = t.get('url')
                else:
                    self.available_audio_tracks.append(t)

            self.available_audio_tracks.sort(key=lambda x: (x['lang'] != 'und', x['lang'], -(x['bitrate'] or 0)))

            if not self.current_audio_format_id and self.available_audio_tracks:
                self.current_audio_format_id = self.available_audio_tracks[0]['id']

            has_multiple = len(self.available_audio_tracks) > 1
            wx.CallAfter(self.change_track_button.Enable, has_multiple)
        except Exception as e:
            print(f"Error processing audio formats: {e}")

    def _fetch_audio_info_thread(self, request_id):
        """
        Fast-path thread for immediate playback. Fetches only the best audio stream URL.
        """
        if request_id != self._current_request_id:
            wx.CallAfter(lambda: wx.EndBusyCursor() if wx.IsBusy() else None)
            return
        import yt_dlp
        target_url = self.video_url
        try:
            # Check if this URL is currently being pre-cached by the background prefetcher
            prefetch_evt = None
            with _prefetch_lock:
                prefetch_evt = _prefetch_events.get(target_url)
            if prefetch_evt:
                print(f"[TurboStream] Awaiting in-flight prefetch for {target_url}...")
                prefetch_evt.wait(timeout=5.0)
                if request_id != self._current_request_id: return
                cached = self.get_cached_stream_info(target_url)
                if cached and cached.get('audio_url'):
                    print(f"[TurboStream] Picked up stream from completed prefetch: {target_url}")
                    self.audio_url = cached['audio_url']
                    self.current_audio_format_id = cached.get('current_format_id')
                    self.chapters = cached.get('chapters', [])
                    if self.chapters:
                        wx.CallAfter(self.chapters_button.Show)
                    else:
                        wx.CallAfter(self.chapters_button.Hide)
                    wx.CallAfter(self.Layout)
                    if not self.upload_date:
                        self.upload_date = cached.get('upload_date')
                    if cached.get('title') and self.video_title in (None, "", _("Direct Link")):
                        self.video_title = cached['title']
                        self.video_uploader = cached.get('uploader') or self.video_uploader
                        wx.CallAfter(self.title_text.SetValue, f"{self.video_title} - {self.video_uploader or '...'}")
                    if cached.get('formats'):
                        self._process_audio_formats(cached['formats'])
                    wx.CallAfter(self._play_media_with_vlc, request_id)
                    threading.Thread(target=self._fetch_full_formats_thread, args=(request_id, target_url), daemon=True).start()
                    return

            fast_ydl_opts = self._get_base_ydl_opts()
            pref_lang = self.main_frame.settings.get("preferred_audio_language", "").lower().strip()
            # StreamGuard Optimization:
            # YouTube M4A (AAC / format 140) contains exact moov/stbl sample indexes,
            # enabling sample-accurate, near-instant HTTP Range seeks in VLC without
            # cluster-seeking stalls or premature EOFs seen in WebM/Opus.
            if pref_lang:
                format_selector = f'bestaudio[ext=m4a][language={pref_lang}]/bestaudio[language={pref_lang}]/bestaudio[ext=m4a]/bestaudio/best[ext=mp4]/best'
            elif self.main_frame.settings.get("prefer_high_bitrate_audio", True):
                format_selector = 'bestaudio[acodec*=opus]/bestaudio[ext=m4a]/bestaudio/best[ext=mp4]/best'
            else:
                format_selector = 'bestaudio[ext=m4a]/bestaudio/best[ext=mp4]/best'
            
            if self.main_frame.video_frame:
                format_selector = 'best[ext=mp4][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]/best'
                
            fast_ydl_opts['format'] = format_selector
            
            ydl = self._get_shared_ydl(fast_ydl_opts)
            info = ydl.extract_info(target_url, download=False)
            
            if request_id != self._current_request_id: return
            if not info:
                raise ValueError(_("Could not extract any media information."))
            
            self.chapters = info.get('chapters', [])
            if self.chapters:
                wx.CallAfter(self.chapters_button.Show)
            else:
                wx.CallAfter(self.chapters_button.Hide)
            wx.CallAfter(self.Layout)
            
            self.upload_date = info.get('upload_date')
            if info.get('title') and self.video_title in (None, "", _("Direct Link")):
                self.video_title = info.get('title')
                self.video_uploader = info.get('uploader') or info.get('channel') or self.video_uploader
                wx.CallAfter(self.title_text.SetValue, f"{self.video_title} - {self.video_uploader or '...'}")

            self.audio_url, picked_fmt_id = self._pick_audio_stream(info)

            if self.audio_url:
                self.current_audio_format_id = picked_fmt_id
                self.cache_stream_info(target_url, {
                    'audio_url': self.audio_url,
                    'chapters': self.chapters,
                    'upload_date': self.upload_date,
                    'formats': info.get('formats', []),
                    'current_format_id': self.current_audio_format_id,
                    'title': self.video_title,
                    'uploader': self.video_uploader,
                })
                wx.CallAfter(self._play_media_with_vlc, request_id)
                # Process formats from initial extraction first
                if 'formats' in info and info['formats']:
                    self._process_audio_formats(info['formats'])
                # Fetch full formats and alternative dubbed tracks in the background
                threading.Thread(target=self._fetch_full_formats_thread, args=(request_id, target_url), daemon=True).start()
            else:
                raise ValueError(_("Fast stream extraction failed to find a URL."))

        except Exception as e:
            if request_id != self._current_request_id: return
            error_str = str(e).lower()
            is_age_restricted = any(keyword in error_str for keyword in ["age restricted", "login required", "sign in", "confirm your age"])
            
            if is_age_restricted:
                cookies_path = self.main_frame.settings.get("cookies_file_path", "")
                if cookies_path and os.path.exists(cookies_path):
                    error_details = _("Playback failed. The video may be private, or your cookies file might be invalid or expired. Please check your cookies file in Settings.")
                else:
                    error_details = _("This video is age-restricted and requires a login. Please provide a cookies.txt file in the Settings panel to play such content.")
                wx.CallAfter(self._playback_failed, error_details)
            else:
                if "video unavailable" in error_str:
                    error_details = _("Video unavailable. This often happens due to YouTube changes or age restrictions. Try updating yt-dlp from the Downloader panel or providing a cookies.txt file in Settings.")
                else:
                    error_details = _("Failed to get audio stream: {}").format(e)
                wx.CallAfter(self._playback_failed, error_details)
        finally:
            wx.CallAfter(lambda: wx.EndBusyCursor() if wx.IsBusy() else None)

    def _fetch_full_formats_thread(self, request_id=None, target_url=None):
        """
        Slow background thread to fetch all available audio formats for the 'Change Track' feature.
        This runs after playback has already started and does not block the UI.
        """
        import yt_dlp
        import settings_manager
        url = target_url or self.video_url
        if not url:
            return
        if request_id is not None and request_id != self._current_request_id:
            return
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'noprogress': True,
                'noplaylist': True,
                'check_formats': False,
                'nocheckcertificate': True,
                'socket_timeout': 10,
            }
            cookies_path = settings_manager.get_effective_cookies_path(self.main_frame.settings)
            if cookies_path and os.path.exists(cookies_path):
                ydl_opts['cookiefile'] = cookies_path
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
            
            if request_id is not None and (request_id != self._current_request_id or url != self.video_url):
                return
            if not info or 'formats' not in info: return
            self._process_audio_formats(info['formats'])
            print(f"Successfully loaded {len(self.available_audio_tracks)} audio tracks in the background.")
        except Exception as e:
            print(f"Background fetch for all audio tracks failed: {e}")

    def _is_lossless_active(self):
        if not self.main_frame.settings.get("lossless_mode", False):
            return False
        if not self.is_local_file or not self.local_file_path:
            return False
        _, ext = os.path.splitext(self.local_file_path.lower())
        return ext in constants.LOSSLESS_AUDIO_EXTENSIONS

    def _needs_dsp_pipeline(self):
        if self._is_lossless_active():
            return False
        s = self.main_frame.settings
        spatial_on = feature_manager.is_feature_enabled(s, feature_manager.FEATURE_SPATIAL_AUDIO) and s.get("spatial_audio_enabled", False)
        mono_on = feature_manager.is_feature_enabled(s, feature_manager.FEATURE_MONO_AUDIO) and s.get("mono_audio", False)
        norm_on = feature_manager.is_feature_enabled(s, feature_manager.FEATURE_AUDIO_NORMALIZATION) and s.get("audio_normalization", False)
        bass_on = int(s.get("bass_boost", 0)) > 0
        vocal_on = bool(s.get("vocal_clarity_enabled", False))
        night_on = bool(s.get("night_mode_enabled", False))
        duck_on = bool(s.get("nvda_ducking_enabled", False))
        return bool(spatial_on or mono_on or norm_on or bass_on or vocal_on or night_on or duck_on)

    def _sync_dsp_settings(self):
        s = self.main_frame.settings
        spatial_on = feature_manager.is_feature_enabled(s, feature_manager.FEATURE_SPATIAL_AUDIO) and s.get("spatial_audio_enabled", False)
        mono_on = feature_manager.is_feature_enabled(s, feature_manager.FEATURE_MONO_AUDIO) and s.get("mono_audio", False)
        norm_on = feature_manager.is_feature_enabled(s, feature_manager.FEATURE_AUDIO_NORMALIZATION) and s.get("audio_normalization", False)
        self.spatial_processor.configure(
            spatial_enabled=spatial_on,
            width=s.get("spatial_audio_width", constants.DEFAULT_SPATIAL_WIDTH),
            room_size=s.get("spatial_audio_room_size", constants.DEFAULT_SPATIAL_ROOM),
            depth=s.get("spatial_audio_depth", constants.DEFAULT_SPATIAL_DEPTH),
            mono_enabled=mono_on,
            normalization_enabled=norm_on,
            volume_percent=s.get("volume", constants.DEFAULT_VOLUME_PERCENT),
            bass_boost=s.get("bass_boost", constants.DEFAULT_BASS_BOOST),
            vocal_clarity=s.get("vocal_clarity_enabled", False),
            night_mode=s.get("night_mode_enabled", False),
        )

    def _get_selected_device_description(self):
        dev_id = self.main_frame.settings.get("audio_output_device", "")
        if not dev_id:
            return ""
        if not self.audio_devices:
            self.audio_devices = self.get_audio_devices()
        for did, desc in self.audio_devices:
            if did == dev_id:
                return desc
        return dev_id

    def _configure_player_audio_backend(self, use_dsp: bool):
        if not self.player or not self.vlc_instance:
            return
        if use_dsp:
            dev_idx = spatial_audio.WinMMOutput.match_device_id(self._get_selected_device_description())
            if self.winmm_output.is_open() and self.winmm_output._device_id == dev_idx:
                self.winmm_output.flush()
                ok = True
            else:
                ok = self.winmm_output.open(
                    device_id=dev_idx,
                    sample_rate=constants.DSP_SAMPLE_RATE,
                    channels=2,
                    bits=16,
                    processor_fn=self.spatial_processor.process_chunk,
                )
            if not ok:
                print("[SpatialAudio] WinMM waveOut unavailable; falling back to native VLC output.")
                if self._using_dsp_output:
                    self._recreate_native_player()
                self._using_dsp_output = False
                return

            if not self._dsp_callbacks:
                @vlc.CallbackDecorators.AudioPlayCb
                def _on_play(opaque, samples, count, pts):
                    byte_len = int(count) * 4
                    if byte_len <= 0 or not samples:
                        return
                    raw = ctypes.string_at(samples, byte_len)
                    self.winmm_output.write(raw)

                @vlc.CallbackDecorators.AudioPauseCb
                def _on_pause(opaque, pts):
                    self.winmm_output.pause()

                @vlc.CallbackDecorators.AudioResumeCb
                def _on_resume(opaque, pts):
                    self.winmm_output.resume()

                @vlc.CallbackDecorators.AudioFlushCb
                def _on_flush(opaque, pts):
                    self.winmm_output.flush()
                    self.spatial_processor.reset()

                @vlc.CallbackDecorators.AudioDrainCb
                def _on_drain(opaque):
                    pass

                @vlc.CallbackDecorators.AudioSetVolumeCb
                def _on_volume(opaque, volume, mute):
                    # Volume is controlled directly in SpatialAudioProcessor so VLC startup resets never override saved volume.
                    pass

                # Hold references so GC never collects ctypes callbacks.
                self._dsp_callbacks = (_on_play, _on_pause, _on_resume, _on_flush, _on_drain, _on_volume)

            cb_play, cb_pause, cb_resume, cb_flush, cb_drain, cb_vol = self._dsp_callbacks
            self.player.audio_set_callbacks(cb_play, cb_pause, cb_resume, cb_flush, cb_drain, None)
            self.player.audio_set_format(b"S16N", constants.DSP_SAMPLE_RATE, 2)
            self.player.audio_set_volume_callback(cb_vol)
            self._using_dsp_output = True
        else:
            self.winmm_output.close()
            if self._using_dsp_output:
                self._recreate_native_player()
            self._using_dsp_output = False

    def _recreate_native_player(self):
        if self.player:
            try:
                self.player.stop()
                self.player.release()
            except Exception:
                pass
        self.player = self.vlc_instance.media_player_new()
        self._bind_vlc_events()

    def _play_media_with_vlc(self, request_id=None):
        if request_id is not None and request_id != self._current_request_id:
            return
        if not self.player or not self.audio_url:
            self._playback_failed(_("VLC player not ready or no audio URL."))
            return

        self._sync_dsp_settings()
        self.spatial_processor.reset()
        self._configure_player_audio_backend(self._needs_dsp_pipeline())

        if self.is_local_file and self.local_file_path and os.path.exists(self.local_file_path):
            media = self.vlc_instance.media_new_path(self.local_file_path)
            media.add_option(":file-caching=500")
        else:
            media = self.vlc_instance.media_new(self.audio_url)
            # StreamGuard + TurboStream: Fast responsive start with 500ms caching and auto-reconnect
            media.add_option(":network-caching=500")
            media.add_option(":http-reconnect")

        self.player.set_media(media)
        media.release()

        if self.main_frame and self.main_frame.video_frame:
            hwnd = self.main_frame.video_frame.panel.GetHandle()
        else:
            hwnd = self.hidden_video_panel.GetHandle()
            
        if sys.platform == 'win32':
            self.player.set_hwnd(hwnd)
        else:
            self.player.set_xwindow(hwnd)
        
        if not self._using_dsp_output:
            saved_device = self.main_frame.settings.get("audio_output_device", "")
            if saved_device:
                self.set_audio_device(saved_device)
        self._current_audio_channel = None

        self.set_volume(self.volume_slider.GetValue(), speak_value=False)
        rate = self.speed_slider.GetValue() / 100.0
        self.player.set_rate(rate)
        
        eq_settings = {
            "enabled": (not self._is_lossless_active()) and feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_EQUALIZER) and self.main_frame.settings.get("equalizer_enabled", False),
            "preamp": self.main_frame.settings.get("equalizer_preamp", constants.DEFAULT_PREAMP_PERCENT),
            "bands": self.main_frame.settings.get("equalizer_bands", constants.EQUALIZER_PRESETS["Flat"]),
        }
        self.apply_equalizer_settings(eq_settings)

        def start_playback():
            if not self:
                return
            if request_id is not None and request_id != self._current_request_id:
                return
            if self.player.play() == -1:
                self._playback_failed(_("VLC could not play the media."))
            else:
                self.is_loaded = True
                self._enable_controls()
        
        wx.CallLater(100, start_playback)

    def _playback_failed(self, error_msg):
        if wx.IsBusy():
            wx.CallAfter(wx.EndBusyCursor)
        self._disable_controls()
        self.update_status(f"{_('Error')}: {error_msg}")
        nvda.speak(_("Error loading media."), constants.NVDA_VERBOSITY_QUIET)
        utils.show_error_dialog(self.main_frame, f"{_('Could not load audio.')}\n{_('Reason')}: {error_msg}", _("Playback Error"))
        self.main_frame.update_window_title()

    def vlc_on_playing(self, event):
        if not self:
            return
        self.is_playing = True
        self.is_finished = False
        self._is_recovering = False
        self._is_seeking = False
        self._set_play_pause_label(_("Pause"))
        tick_ms = 250 if (self.loop_a_ms is not None and self.loop_b_ms is not None) else 500
        if not self.timer.IsRunning(): self.timer.Start(tick_ms)
        self.main_frame.update_window_title("Playing", self.video_title)
        if self._using_dsp_output and hasattr(self, "winmm_output") and self.winmm_output:
            self.winmm_output.resume()
        self.set_volume(self.volume_slider.GetValue(), speak_value=False)
        self.apply_mono_setting()

        if not self.devices_populated:
            self.populate_audio_devices_choice()

        if not self.notification_sound_played:
            utils.play_sound(self.main_frame.settings, "load_complete")
            self.notification_sound_played = True

        wx.CallLater(1500, self.prefetch_next_track_in_queue)

        if self.resume_position_ms:
            target = self.resume_position_ms
            self.resume_position_ms = None
            self.seek_to(target)

    def vlc_on_paused(self, event):
        if not self:
            return
        self.is_playing = False
        self.is_finished = False
        self._set_play_pause_label(_("Play"))
        if self.timer.IsRunning(): self.timer.Stop()
        self.save_current_position()
        self.update_status(_("Paused"))
        self.main_frame.update_window_title("Paused", self.video_title)

    def vlc_on_stopped(self, event):
        if not self:
            return
        self.is_playing = False
        self.is_finished = False
        self._set_play_pause_label(_("Play"))
        if self.timer.IsRunning(): self.timer.Stop()
        if self.status_message not in [_("Switching audio track..."), _("Re-buffering stream...")]:
            self.update_status(_("Stopped"))
        self.save_current_position()
        self.main_frame.update_window_title()

    def vlc_on_finished(self, event):
        if not self or not self.is_loaded:
            return

        # StreamGuard: Verify whether track genuinely reached the end or dropped prematurely
        cur_time = self.player.get_time() if self.player else -1
        length = self.player.get_length() if self.player else -1
        if length <= 0:
            length = getattr(self, '_last_known_length_ms', -1)
        if cur_time <= 0:
            cur_time = getattr(self, '_last_valid_pos_ms', 0)

        time_since_seek = time.time() - getattr(self, '_last_seek_time', 0)
        is_seeking = getattr(self, '_is_seeking', False) or (getattr(self, '_target_seek_pos', None) is not None)

        # Premature EOF detection:
        # 1. Total length is known (> 10s) and stream terminated more than 4s before the real end
        # 2. Or a seek operation happened recently (< 2.5s) and position is not near the end
        is_premature = False
        if length > 10000 and cur_time < (length - 4000):
            is_premature = True
        elif (time_since_seek < 2.5 or is_seeking) and (length <= 0 or cur_time < (length - 2000)):
            is_premature = True

        if is_premature:
            target_recovery_pos = getattr(self, '_target_seek_pos', None) if getattr(self, '_target_seek_pos', None) is not None else cur_time
            print(f"[StreamGuard] Premature EOF intercepted at {target_recovery_pos}ms / {length}ms (seek {time_since_seek:.1f}s ago). Auto-recovering...")
            self._recover_stream(target_recovery_pos)
            return

        self.is_playing = False
        self.is_finished = True
        if self.timer.IsRunning(): self.timer.Stop()
        self.update_status(_("Finished."))
        nvda.speak(_("Playback finished."), constants.NVDA_VERBOSITY_DEFAULT)
        self.clear_saved_position(self.video_url)
        self.main_frame.update_window_title()

        if self.main_frame.video_frame:
            self.main_frame.video_frame.on_playback_finished()

        settings = self.main_frame.settings
        yt_panel = self.main_frame.youtube_panel
        if self._sleep_at_track_end:
            self._sleep_at_track_end = False
            self._sleep_timer_minutes = 0
            self.is_playing = False
            self.is_finished = True
            if self.timer.IsRunning(): self.timer.Stop()
            self._set_play_pause_label(_("Replay"))
            self.update_status(_("Sleep timer ended."))
            nvda.speak(_("Sleep timer ended. Playback stopped."), constants.NVDA_VERBOSITY_DEFAULT)
            return

        if settings.get("repeat_mode") != constants.REPEAT_MODE_ONE and self.up_next_queue:
            next_q = self.up_next_queue.pop(0)
            self.play_queue_entry(next_q)
            return

        next_track = None
        if settings.get("repeat_mode") == constants.REPEAT_MODE_ONE:
            next_track = yt_panel.get_track_info_at_index(self.current_track_index)
            if next_track: nvda.speak(_("Repeating track."), constants.NVDA_VERBOSITY_DEFAULT)
        elif self.is_radio_mode:
            self.main_frame.request_radio_next(self.video_url)
            return
        elif settings.get("shuffle_mode", False):
            next_track = yt_panel.get_shuffled_track_info()
            if next_track: nvda.speak(_("Playing next shuffled track."), constants.NVDA_VERBOSITY_DEFAULT)
        else:
            is_last = yt_panel.is_last_track(self.current_track_index)
            if is_last and settings.get("repeat_mode") == constants.REPEAT_MODE_ALL:
                next_track = yt_panel.get_track_info_at_index(0)
                if next_track: nvda.speak(_("Repeating playlist."), constants.NVDA_VERBOSITY_DEFAULT)
            elif not is_last and (settings.get("autoplay_enabled", False) or settings.get("repeat_mode") == constants.REPEAT_MODE_ALL):
                next_track = yt_panel.get_next_track_info(self.current_track_index)
        if next_track:
            self.main_frame.request_audio_play(
                next_track['url'], next_track['title'], next_track['uploader'],
                index=next_track['index'], is_radio=False
            )
        else:
            self._set_play_pause_label(_("Replay"))
            nvda.speak(_("End of playlist."), constants.NVDA_VERBOSITY_DEFAULT)

    def on_play_next(self, event=None):
        if not self.is_loaded: return
        
        settings = self.main_frame.settings
        yt_panel = self.main_frame.youtube_panel
        if self.up_next_queue:
            next_q = self.up_next_queue.pop(0)
            self.play_queue_entry(next_q)
            return

        next_track = None

        if self.is_radio_mode:
            self.main_frame.request_radio_next(self.video_url)
            return
        elif settings.get("shuffle_mode", False):
            next_track = yt_panel.get_shuffled_track_info()
            if next_track: nvda.speak(_("Playing next shuffled track."), constants.NVDA_VERBOSITY_DEFAULT)
        else:
            # For manual "Next", we generally just want the next track, ignoring repeat-one if invoked manually?
            # Or standard behavior: just next.
            # Let's go to next track in list.
            if yt_panel.is_last_track(self.current_track_index):
                 # Loop to start if repeat all, or just nothing? 
                 # Let's wrap to start if Repeat All is on, else msg.
                 if settings.get("repeat_mode") == constants.REPEAT_MODE_ALL:
                      next_track = yt_panel.get_track_info_at_index(0)
                 else:
                      nvda.speak(_("No more tracks."), constants.NVDA_VERBOSITY_DEFAULT)
                      return
            else:
                next_track = yt_panel.get_next_track_info(self.current_track_index)

        if next_track:
            self.main_frame.request_audio_play(
                next_track['url'], next_track['title'], next_track['uploader'],
                index=next_track['index'], is_radio=False
            )

    def on_play_previous(self, event=None):
        if not self.is_loaded: return
        if self.is_radio_mode:
            nvda.speak(_("Previous track not available in radio mode."), constants.NVDA_VERBOSITY_DEFAULT)
            return

        # If played > 5 seconds, restart current track? Standard behavior.
        # But user asked for "Play previous track".
        # Let's just go to previous.
        
        yt_panel = self.main_frame.youtube_panel
        prev_track = yt_panel.get_previous_track_info(self.current_track_index)
        
        if prev_track:
            self.main_frame.request_audio_play(
                prev_track['url'], prev_track['title'], prev_track['uploader'],
                index=prev_track['index'], is_radio=False
            )
        else:
            # If at timeline start, maybe seeking to 0 is better? 
            # Or just say "First track".
            nvda.speak(_("This is the first track."), constants.NVDA_VERBOSITY_DEFAULT)
            self.seek_to(0)

    def vlc_on_error(self, event):
        if not self:
            return
        # StreamGuard: If playback was active and dropped during seek, attempt auto-recovery
        if self.is_loaded and getattr(self, '_last_valid_pos_ms', 0) > 0 and not getattr(self, '_is_recovering', False):
            target = getattr(self, '_pending_seek_pos', None) or getattr(self, '_last_valid_pos_ms', 0)
            print(f"[StreamGuard] VLC playback error intercepted at {target}ms. Attempting auto-recovery...")
            self._recover_stream(target)
            return

        error_msg = _("VLC encountered an error during playback.")
        self._playback_failed(error_msg)

    def _recover_stream(self, target_pos_ms):
        """
        StreamGuard Auto-Recovery: Seamlessly recovers streaming on longform videos
        when YouTube drops the connection during rapid seek or token timeout.
        """
        if not self.is_loaded or not self.video_url:
            return

        if getattr(self, '_is_recovering', False):
            return
        self._is_recovering = True

        self.update_status(_("Re-buffering stream..."))
        nvda.speak(_("Re-buffering..."), constants.NVDA_VERBOSITY_QUIET)

        self._stream_recovery_count = getattr(self, '_stream_recovery_count', 0) + 1
        recovery_count = self._stream_recovery_count

        # If dropped multiple times (or URL token expired on multi-hour video), re-extract fresh stream URL
        if recovery_count > 2 or not self.audio_url:
            print(f"[StreamGuard] Persistent stream drop ({recovery_count}). Re-fetching fresh URL from YouTube...")
            self._stream_recovery_count = 0
            self.resume_position_ms = target_pos_ms
            self._fetch_audio_info_and_url(self._current_request_id)
            return

        def _do_fast_recovery():
            if not self or not self.player or not self.vlc_instance or not self.audio_url:
                self._is_recovering = False
                return
            try:
                self._sync_dsp_settings()
                self.spatial_processor.reset()
                self._configure_player_audio_backend(self._needs_dsp_pipeline())
                media = self.vlc_instance.media_new(self.audio_url)
                media.add_option(":network-caching=500")
                media.add_option(":http-reconnect")
                self.player.set_media(media)
                media.release()

                if self.main_frame and self.main_frame.video_frame:
                    hwnd = self.main_frame.video_frame.panel.GetHandle()
                else:
                    hwnd = self.hidden_video_panel.GetHandle()
                if sys.platform == 'win32':
                    self.player.set_hwnd(hwnd)

                self.player.play()
                self.is_playing = True
                self.is_finished = False
                self._set_play_pause_label(_("Pause"))
                if not self.timer.IsRunning():
                    self.timer.Start(500)

                wx.CallLater(250, lambda: self.player.set_time(int(target_pos_ms)) if self.player else None)
                wx.CallLater(1000, lambda: setattr(self, '_is_recovering', False))
            except Exception as e:
                print(f"[StreamGuard] Fast recovery failed: {e}. Falling back to URL re-fetch.")
                self.resume_position_ms = target_pos_ms
                self._is_recovering = False
                self._fetch_audio_info_and_url(self._current_request_id)

        wx.CallLater(200, _do_fast_recovery)

    def on_play_pause(self, event):
        if not self.player or not self.is_loaded:
            nvda.speak(_("No audio loaded."), constants.NVDA_VERBOSITY_DEFAULT)
            return
        if self.is_finished or self.play_pause_button.GetLabel() == _("Replay"):
            self.is_finished = False
            self.resume_position_ms = None
            self.player.stop()
            self._play_media_with_vlc(self._current_request_id)
            self.is_playing = True
            self._set_play_pause_label(_("Pause"))
            if not self.timer.IsRunning(): self.timer.Start(500)
            self.update_status(_("Playing"))
            nvda.speak(_("Replaying"), constants.NVDA_VERBOSITY_DEFAULT)
        elif self.is_playing:
            self.player.set_pause(1)
            self.is_playing = False
            self._set_play_pause_label(_("Play"))
            if self.timer.IsRunning(): self.timer.Stop()
            self.update_status(_("Paused"))
            self.main_frame.update_window_title("Paused", self.video_title)
            nvda.speak(_("Paused"), constants.NVDA_VERBOSITY_DEFAULT)
            wx.CallAfter(self.save_current_position)
        else:
            self.player.set_pause(0)
            self.is_playing = True
            self._set_play_pause_label(_("Pause"))
            if not self.timer.IsRunning(): self.timer.Start(500)
            self.update_status(_("Playing"))
            self.main_frame.update_window_title("Playing", self.video_title)
            nvda.speak(_("Playing"), constants.NVDA_VERBOSITY_DEFAULT)
            
        if self.main_frame.taskbar_icon:
            self.main_frame.taskbar_icon.set_icon(self.is_playing)

    def on_stop(self, event):
        if not self.is_loaded: return
        self.stop_playback()

    def stop_playback(self, silent=False):
        if not self.player: return
        if not silent: nvda.speak(_("Stopping playback."), constants.NVDA_VERBOSITY_DEFAULT)
        if self.timer.IsRunning(): self.timer.Stop()
        if not silent: self.save_current_position()
        if self.player.is_playing():
            self.player.stop()
        self.winmm_output.flush()
        self.spatial_processor.reset()
        if self.main_frame.video_frame:
            self.main_frame.video_frame.on_playback_finished()
        self.is_playing = self.is_loaded = self.is_radio_mode = self.is_finished = False
        self.is_local_file = False
        self.local_file_path = None
        self.loop_a_ms = None
        self.loop_b_ms = None
        self.audio_url = self.video_url = self.video_title = self.video_uploader = self.upload_date = None
        self.current_track_index = self.resume_position_ms = None
        self.chapters = []
        self.chapters_button.Hide()
        self._current_audio_channel = None
        self._last_valid_pos_ms = 0
        self._last_known_length_ms = 0
        self._pending_seek_pos = None
        self._target_seek_pos = None
        self._stream_recovery_count = 0
        self._is_recovering = False
        self._is_seeking = False
        self._disable_controls()
        self.retranslate_ui()
        if not silent: self.main_frame.update_window_title()

    def on_rewind(self, event):
        if not self.is_loaded: return
        seek_seconds = self.main_frame.settings.get("seek_interval", constants.DEFAULT_SEEK_INTERVAL_SECONDS)
        self.seek_by(-seek_seconds * 1000)

    def on_ffwd(self, event):
        if not self.is_loaded: return
        seek_seconds = self.main_frame.settings.get("seek_interval", constants.DEFAULT_SEEK_INTERVAL_SECONDS)
        self.seek_by(seek_seconds * 1000)

    def seek_by(self, delta_ms):
        if not self.player or not self.is_loaded: return
        try:
            now = time.time()
            time_since_last_seek = now - getattr(self, '_last_seek_time', 0.0)
            
            # If recent seek (< 0.8s), use target position to prevent querying mid-seek stale VLC time
            if getattr(self, '_target_seek_pos', None) is not None and time_since_last_seek < 0.8:
                base_pos = self._target_seek_pos
            else:
                cur = self.player.get_time()
                base_pos = cur if cur > 0 else getattr(self, '_last_valid_pos_ms', 0)
                
            length = self.player.get_length()
            if length <= 0:
                length = getattr(self, '_last_known_length_ms', 0)
                
            new_pos = max(0, base_pos + delta_ms)
            if length > 0:
                new_pos = min(new_pos, max(0, length - 500))
                
            self._target_seek_pos = new_pos
            self._pending_seek_pos = new_pos
            self._last_valid_pos_ms = new_pos
            self._last_seek_time = now
            self._is_seeking = True

            # 1. Direct VLC seek with 0ms delay!
            self.player.set_time(int(new_pos))

            # 2. Instant visual status update
            length_str = utils.format_time_ms(length) if length > 0 else "--:--"
            self.update_status(f"{utils.format_time_ms(new_pos)} / {length_str}")

            # 3. Announce to NVDA immediately on every tap
            direction_word = _("Fast forward") if delta_ms > 0 else _("Rewind")
            nvda.speak(f"{direction_word} {utils.format_time_ms(new_pos)}", constants.NVDA_VERBOSITY_VERBOSE)

            wx.CallLater(800, self._clear_seeking_flag)
        except Exception as e:
            print(f"Error during seek_by: {e}")

    def seek_to(self, time_ms):
        if not self.player or not self.is_loaded: return
        try:
            length = self.player.get_length()
            if length <= 0:
                length = getattr(self, '_last_known_length_ms', 0)
            if length > 0:
                time_ms = min(int(time_ms), max(0, length - 500))
            time_ms = max(0, int(time_ms))
            self._pending_seek_pos = None
            self._target_seek_pos = time_ms
            self._last_seek_time = time.time()
            self._last_valid_pos_ms = time_ms
            self._is_seeking = True
            
            # 1. Direct VLC seek with 0ms delay
            self.player.set_time(int(time_ms))

            # 2. Instant visual status update
            length_str = utils.format_time_ms(length) if length > 0 else "--:--"
            self.update_status(f"{utils.format_time_ms(time_ms)} / {length_str}")
            nvda.speak(_("Seek to {}").format(utils.format_time_ms(time_ms)), constants.NVDA_VERBOSITY_VERBOSE)

            wx.CallLater(800, self._clear_seeking_flag)
        except Exception as e:
            print(f"Error during seek_to: {e}")

    def on_volume_change(self, event):
        val = self.volume_slider.GetValue()
        self.set_volume(val, speak_value=True)

    def _on_vol_speak_timer(self, event):
        pct = getattr(self, "_pending_spoken_volume", None)
        if pct is not None:
            self._pending_spoken_volume = None
            nvda.speak(_("Volume {} percent").format(pct), constants.NVDA_VERBOSITY_DEFAULT)

    def set_volume(self, percent, speak_value=False):
        percent = max(constants.MIN_VOLUME_PERCENT, min(constants.MAX_VOLUME_PERCENT, int(percent)))
        if self.volume_slider.GetValue() != percent:
            self.volume_slider.SetValue(percent)
        self.spatial_processor.configure(volume_percent=percent)
        if self.player and not self._using_dsp_output:
            self.player.audio_set_volume(percent)
        self.main_frame.settings["volume"] = percent
        if speak_value:
            self._pending_spoken_volume = percent
            if hasattr(self, "_vol_speak_timer"):
                self._vol_speak_timer.Start(70, oneShot=True)

    def on_speed_slider_change(self, event):
        if not self.player: return
        slider_val = self.speed_slider.GetValue()
        rate = slider_val / 100.0
        self.speed_label.SetLabel(_("Speed: {:.2f}x").format(rate))
        self.player.set_rate(rate)
        self.main_frame.settings["playback_rate"] = rate
        nvda.speak(_("Playback speed {:.2f}x").format(rate), constants.NVDA_VERBOSITY_DEFAULT)

    def on_autoplay_toggle(self, event):
        is_checked = self.autoplay_checkbox.IsChecked()
        self.main_frame.settings["autoplay_enabled"] = is_checked
        nvda.speak(_("Autoplay enabled.") if is_checked else _("Autoplay disabled."), constants.NVDA_VERBOSITY_DEFAULT)
        if is_checked and self.is_radio_mode:
            self.is_radio_mode = False
            nvda.speak(_("Radio mode disabled to allow autoplay."), constants.NVDA_VERBOSITY_VERBOSE)

    def on_toggle_shuffle(self, event):
        is_checked = self.shuffle_button.GetValue()
        self.main_frame.settings["shuffle_mode"] = is_checked
        nvda.speak(_("Shuffle enabled.") if is_checked else _("Shuffle disabled."), constants.NVDA_VERBOSITY_DEFAULT)
        if is_checked and self.is_radio_mode:
            self.is_radio_mode = False
            nvda.speak(_("Radio mode disabled."), constants.NVDA_VERBOSITY_VERBOSE)
        if self.main_frame.youtube_panel.related_videos_data:
            self.main_frame.youtube_panel.reshuffle_related_if_needed()

    def on_cycle_repeat(self, event):
        current_mode = self.main_frame.settings.get("repeat_mode", constants.REPEAT_MODE_NONE)
        new_mode = (current_mode + 1) % 3
        self.main_frame.settings["repeat_mode"] = new_mode
        self._update_repeat_button_ui()
        
        mode_text = {
            constants.REPEAT_MODE_NONE: _("Repeat off."),
            constants.REPEAT_MODE_ONE: _("Repeat one."),
            constants.REPEAT_MODE_ALL: _("Repeat all.")
        }.get(new_mode)
        nvda.speak(mode_text, constants.NVDA_VERBOSITY_DEFAULT)

    def _update_repeat_button_ui(self):
        if not self.repeat_button: return
        mode = self.main_frame.settings.get("repeat_mode", constants.REPEAT_MODE_NONE)
        label_map = {
            constants.REPEAT_MODE_NONE: _("Repeat"),
            constants.REPEAT_MODE_ONE: _("Repeat (One)"),
            constants.REPEAT_MODE_ALL: _("Repeat (All)"),
        }
        tooltip_map = {
            constants.REPEAT_MODE_NONE: _("Cycle repeat mode (Currently Off)."),
            constants.REPEAT_MODE_ONE: _("Cycle repeat mode (Currently repeating one track)."),
            constants.REPEAT_MODE_ALL: _("Cycle repeat mode (Currently repeating all tracks)."),
        }
        self.repeat_button.SetLabel(label_map.get(mode))
        self.repeat_button.SetToolTip(tooltip_map.get(mode))

    def on_toggle_video(self, event):
        if not feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_VIDEO_PLAYER):
            nvda.speak(_("Video player is disabled in Feature Manager."), constants.NVDA_VERBOSITY_DEFAULT)
            return
        if not self.is_loaded:
            nvda.speak(_("No video is currently loaded."), constants.NVDA_VERBOSITY_DEFAULT)
            return
        if self.main_frame.video_frame:
            self.main_frame.video_frame.Close()
        else:
            self.main_frame.request_show_video()
        self.update_video_button_label()

    def update_video_button_label(self):
        if not self.video_button: return
        if self.main_frame and getattr(self.main_frame, 'video_frame', None):
            self.video_button.SetLabel(_("Hide Video"))
            self.video_button.SetToolTip(_("Close the video player window."))
        else:
            self.video_button.SetLabel(_("Show Video"))
            self.video_button.SetToolTip(_("Open a window to watch the current video."))

    def on_open_chapters(self, event=None):
        if not self.is_loaded or not self.chapters:
            nvda.speak(_("No chapters available for this video."), constants.NVDA_VERBOSITY_DEFAULT)
            return

        chapter_titles = []
        for i, chapter in enumerate(self.chapters):
            title = chapter.get('title', f"Chapter {i+1}")
            start_time = utils.format_duration(chapter.get('start_time', 0))
            chapter_titles.append(f"{start_time} - {title}")

        with wx.SingleChoiceDialog(self, _("Choose a chapter:"), _("Chapters"), chapter_titles) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                selected_index = dlg.GetSelection()
                chapter = self.chapters[selected_index]
                start_time_seconds = chapter.get('start_time', 0)
                self.seek_to(start_time_seconds * 1000)

    def on_next_chapter(self, event=None):
        if not self.is_loaded or not self.chapters or not self.player:
            nvda.speak(_("No chapters available."), constants.NVDA_VERBOSITY_DEFAULT)
            return
        current_time_sec = (self.player.get_time() or 0) / 1000.0
        for i, chapter in enumerate(self.chapters):
            start = chapter.get('start_time', 0)
            if start > current_time_sec + 0.5:
                self.seek_to(int(start * 1000))
                title = chapter.get('title', f"Chapter {i+1}")
                nvda.speak(_("Chapter {num}: {title}").format(num=i+1, title=title), constants.NVDA_VERBOSITY_DEFAULT)
                return
        nvda.speak(_("Already at the last chapter."), constants.NVDA_VERBOSITY_DEFAULT)

    def on_prev_chapter(self, event=None):
        if not self.is_loaded or not self.chapters or not self.player:
            nvda.speak(_("No chapters available."), constants.NVDA_VERBOSITY_DEFAULT)
            return
        current_time_sec = (self.player.get_time() or 0) / 1000.0
        target_idx = None
        for i in range(len(self.chapters) - 1, -1, -1):
            start = self.chapters[i].get('start_time', 0)
            if current_time_sec >= start + 2.0:
                target_idx = i
                break
            elif current_time_sec > start and i > 0:
                target_idx = i - 1
                break
        if target_idx is not None and 0 <= target_idx < len(self.chapters):
            chapter = self.chapters[target_idx]
            self.seek_to(int(chapter.get('start_time', 0) * 1000))
            title = chapter.get('title', f"Chapter {target_idx+1}")
            nvda.speak(_("Chapter {num}: {title}").format(num=target_idx+1, title=title), constants.NVDA_VERBOSITY_DEFAULT)
        else:
            if self.chapters:
                self.seek_to(int(self.chapters[0].get('start_time', 0) * 1000))
                title = self.chapters[0].get('title', "Chapter 1")
                nvda.speak(_("Chapter 1: {title}").format(title=title), constants.NVDA_VERBOSITY_DEFAULT)

    def fetch_sponsorblock_segments(self, video_id):
        def _worker():
            try:
                import urllib.request
                import json
                api_url = f"https://sponsor.ajay.app/api/skipSegments?videoID={video_id}&categories=[\"sponsor\",\"selfpromo\",\"interaction\",\"intro\"]"
                req = urllib.request.Request(api_url, headers={"User-Agent": "Tunevia/1.5.8"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    segments = []
                    for item in data:
                        seg = item.get("segment")
                        cat = item.get("category", "sponsor")
                        if seg and len(seg) == 2:
                            segments.append((float(seg[0]), float(seg[1]), cat))
                    self.sponsor_segments = segments
            except Exception:
                self.sponsor_segments = []
        threading.Thread(target=_worker, daemon=True).start()

    def _refresh_signed_stream_url_background(self):
        if self._is_refreshing_signed_url or not self.video_url: return
        self._is_refreshing_signed_url = True
        target_url = self.video_url
        def _worker():
            try:
                opts = self._get_base_ydl_opts()
                opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best[ext=mp4]/best'
                ydl = self._get_shared_ydl(opts)
                info = ydl.extract_info(target_url, download=False)
                new_url = info.get('url') if info else None
                if new_url and new_url != self.audio_url and target_url == self.video_url:
                    self.audio_url = new_url
                    print(f"[ProactiveRefresh] Refreshed stream URL for {target_url}")
            except Exception as e:
                print(f"[ProactiveRefresh] Error refreshing stream URL: {e}")
            finally:
                self._is_refreshing_signed_url = False
        threading.Thread(target=_worker, daemon=True).start()

    def on_timer(self, event):
        if not self:
            return
        if self.player and self.is_loaded and self.is_playing:
            current = self.player.get_time()
            length = self.player.get_length()
            if current >= 0:
                self._last_valid_pos_ms = current
                if length > 0:
                    self._last_known_length_ms = length
                # Only update status if the user is not actively fast-forwarding or debouncing a seek
                if self._pending_seek_pos is None:
                    self.update_status(f"{utils.format_time_ms(current)} / {utils.format_time_ms(length)}")

                # SponsorBlock auto-skip
                if self.sponsor_segments and self.main_frame.settings.get("enable_sponsorblock", True) and not self._is_seeking:
                    current_sec = current / 1000.0
                    for seg_start, seg_end, category in self.sponsor_segments:
                        if seg_start <= current_sec < seg_end:
                            seg_key = (round(seg_start, 1), round(seg_end, 1))
                            if seg_key not in self._skipped_sponsor_segments:
                                self._skipped_sponsor_segments.add(seg_key)
                                target_ms = int(seg_end * 1000)
                                self.seek_to(target_ms)
                                cat_name = category.replace('_', ' ').capitalize()
                                nvda.speak(_("Skipped {category} segment").format(category=cat_name), constants.NVDA_VERBOSITY_DEFAULT)
                                break

                # Proactive Signed URL Refresh
                if self.audio_url and 'expire=' in self.audio_url and not self._is_refreshing_signed_url:
                    try:
                        m_exp = re.search(r'expire=(\d+)', self.audio_url)
                        if m_exp and (int(m_exp.group(1)) - time.time() < 600):
                            self._refresh_signed_stream_url_background()
                    except Exception:
                        pass

                # A-B Loop
                if self.loop_a_ms is not None and self.loop_b_ms is not None and not self._is_seeking:
                    if current >= self.loop_b_ms:
                        self.seek_to(self.loop_a_ms)

                # Sleep Timer with 15-second gradual fade-out
                if self._sleep_end_time is not None:
                    rem_s = self._sleep_end_time - time.time()
                    base_vol = self.main_frame.settings.get("volume", constants.DEFAULT_VOLUME_PERCENT)
                    if rem_s <= 0:
                        self._sleep_end_time = None
                        self._sleep_timer_minutes = 0
                        if self.is_playing:
                            self.on_play_pause(None)
                        self.spatial_processor.configure(volume_percent=base_vol)
                        if self.player and not self._using_dsp_output:
                            self.player.audio_set_volume(base_vol)
                        nvda.speak(_("Sleep timer ended. Playback paused."), constants.NVDA_VERBOSITY_DEFAULT)
                    elif rem_s <= 15.0:
                        fade_pct = max(2, int(base_vol * (rem_s / 15.0)))
                        self.spatial_processor.configure(volume_percent=fade_pct)
                        if self.player and not self._using_dsp_output:
                            self.player.audio_set_volume(fade_pct)

    def handle_key_event(self, event):
        if wx.Window.FindFocus() in self.shortcut_disabling_controls:
            event.Skip()
            return
        if not self.main_frame.settings.get("enable_player_shortcuts", True):
            event.Skip()
            return
        keyCode = event.GetKeyCode()
        mods = event.GetModifiers()
        wx_mods = wx.ACCEL_NORMAL
        if mods & wx.ACCEL_ALT: wx_mods |= wx.ACCEL_ALT
        if mods & wx.ACCEL_CTRL: wx_mods |= wx.ACCEL_CTRL
        if mods & wx.ACCEL_SHIFT: wx_mods |= wx.ACCEL_SHIFT
        pressed_combo = (wx_mods, keyCode)
        hotkey_config = self.main_frame.settings.get("hotkey_config", {})
        action_handlers = self._get_action_handlers()
        for action_key, handler in action_handlers.items():
            action_details = constants.CUSTOMIZABLE_ACTIONS.get(action_key)
            if not action_details: continue
            config_combo = hotkey_config.get(action_key, action_details["default"])
            if pressed_combo == config_combo:
                handler(None)
                return
        # Number keys 0-9 jump directly to 0%..90% of track duration
        if not mods and self.is_loaded and ord('0') <= keyCode <= ord('9'):
            self.seek_to_percent((keyCode - ord('0')) * 10)
            return
        event.Skip()

    def _get_action_handlers(self):
        if not hasattr(self, '_cached_action_handlers'):
            self._cached_action_handlers = {
                "local_play_pause": self.on_play_pause,
                "local_rewind": self.on_rewind,
                "local_ffwd": self.on_ffwd,
                "local_vol_up": lambda e: self.set_volume(self.volume_slider.GetValue() + constants.VOLUME_ADJUST_STEP_PERCENT, True),
                "local_vol_down": lambda e: self.set_volume(self.volume_slider.GetValue() - constants.VOLUME_ADJUST_STEP_PERCENT, True),
                "local_speak_time": lambda e: self.speak_current_time(),
                "local_toggle_repeat": self.on_cycle_repeat,
                "local_toggle_shuffle": lambda e: self.shuffle_button.SetValue(not self.shuffle_button.GetValue()) or self.on_toggle_shuffle(e),
                "local_toggle_mono": self.on_toggle_mono,
                "local_add_bookmark": self.on_add_bookmark_hotkey,
                "local_open_equalizer": self.on_open_equalizer,
                "local_toggle_spatial": self.on_toggle_spatial_audio,
                "local_open_spatial": self.on_open_spatial_audio,
                "local_open_local_audio": self.on_open_local_audio,
                "local_toggle_lossless": self.on_toggle_lossless_mode,
                "local_cycle_bass_boost": self.on_cycle_bass_boost,
                "local_toggle_vocal_boost": self.on_toggle_vocal_clarity,
                "local_toggle_night_mode": self.on_toggle_night_mode,
                "local_toggle_ab_loop": self.on_toggle_ab_loop,
                "local_sleep_timer": self.on_open_sleep_timer,
                "local_open_queue": self.on_open_queue,
                "local_toggle_nvda_ducking": self.on_toggle_nvda_ducking,
                "local_speak_track_info": lambda e: self.speak_track_and_audio_info(),
                "local_open_chapters": self.on_open_chapters,
                "local_next_chapter": self.on_next_chapter,
                "local_prev_chapter": self.on_prev_chapter,
            }
        return self._cached_action_handlers

    def speak_current_time(self):
        if self.player and self.is_loaded:
            current = self.player.get_time()
            length = self.player.get_length()
            if current >= 0:
                nvda.speak(_("Time: {current} of {total}").format(current=utils.format_time_ms(current), total=utils.format_time_ms(length)), constants.NVDA_VERBOSITY_DEFAULT)
            else:
                nvda.speak(_("Time not available."), constants.NVDA_VERBOSITY_DEFAULT)
        else:
            nvda.speak(_("No audio loaded."), constants.NVDA_VERBOSITY_DEFAULT)

    def cleanup_on_exit(self):
        nvda.set_speech_hook(None)
        self.save_current_position()
        if self.timer.IsRunning(): self.timer.Stop()
        if hasattr(self, '_seek_timer') and self._seek_timer.IsRunning():
            self._seek_timer.Stop()
        if hasattr(self, '_vol_speak_timer') and self._vol_speak_timer.IsRunning():
            self._vol_speak_timer.Stop()
        if hasattr(self, 'winmm_output') and self.winmm_output:
            self.winmm_output.close()
        if self.equalizer:
            self.equalizer.release()
            self.equalizer = None
        if self.player:
            self.player.stop()
            self.player.release()
            self.player = None
        if self.vlc_instance:
            self.vlc_instance.release()
            self.vlc_instance = None

    def save_current_position(self):
        if not self.main_frame.settings.get("remember_playback_position", False) or not self.video_url or not self.is_loaded or not self.player or self.is_radio_mode:
            return
        try:
            pos_ms = self.player.get_time()
            length_ms = self.player.get_length()
            if pos_ms > 1000 and (length_ms <= 0 or pos_ms < length_ms - 5000):
                self.main_frame.settings.get("playback_positions", {})[self.video_url] = int(pos_ms)
        except Exception as e: print(_("Error saving playback position: {}").format(e))

    def clear_saved_position(self, url):
        if url and url in self.main_frame.settings.get("playback_positions", {}):
            del self.main_frame.settings["playback_positions"][url]

    def on_change_audio_track(self, event):
        if not self.is_loaded or len(self.available_audio_tracks) <= 1:
            nvda.speak(_("No other audio tracks available for this video."), constants.NVDA_VERBOSITY_DEFAULT)
            return
        choices = [track['label'] for track in self.available_audio_tracks]
        current_choice_idx = next((i for i, t in enumerate(self.available_audio_tracks) if str(t['id']) == str(self.current_audio_format_id)), 0)
        with wx.SingleChoiceDialog(self, _("Choose an audio track:"), _("Select Audio Track"), choices) as dlg:
            if current_choice_idx >= 0:
                dlg.SetSelection(current_choice_idx)
            if dlg.ShowModal() == wx.ID_OK:
                selected_idx = dlg.GetSelection()
                new_track = self.available_audio_tracks[selected_idx]
                if str(new_track['id']) != str(self.current_audio_format_id):
                    self._initiate_track_switch(new_track)

    def _initiate_track_switch(self, track_or_id):
        if isinstance(track_or_id, dict):
            new_track = track_or_id
            new_format_id = str(new_track['id'])
        else:
            new_format_id = str(track_or_id)
            new_track = next((t for t in self.available_audio_tracks if str(t['id']) == new_format_id), {'id': new_format_id, 'label': str(new_format_id)})

        resume_pos = 0
        if self.player and self.is_loaded:
            resume_pos = self.player.get_time()

        cached_url = new_track.get('url')
        if cached_url:
            self.current_audio_format_id = new_format_id
            self.audio_url = cached_url
            self.resume_position_ms = resume_pos
            self.update_status(_("Switched to audio track: {}").format(new_track['label']))
            nvda.speak(_("Switched to track: {}").format(new_track['label']), constants.NVDA_VERBOSITY_DEFAULT)
            if self.player:
                self.player.stop()
            self._play_media_with_vlc()
            return

        if self.player and self.is_playing:
            self.player.pause()

        self.update_status(_("Switching audio track..."))
        nvda.speak(_("Switching to track: {}").format(new_track['label']), constants.NVDA_VERBOSITY_DEFAULT)
        self._disable_controls()
        wx.BeginBusyCursor()
        threading.Thread(target=self._fetch_specific_audio_url_thread, args=(new_track, resume_pos), daemon=True).start()

    def switch_to_video_stream(self):
        resume_pos = 0
        if self.player and self.is_loaded:
            resume_pos = self.player.get_time()
            if self.is_playing: self.player.pause()
        self.update_status(_("Loading video stream..."))
        self._disable_controls()
        self.player.stop()
        wx.BeginBusyCursor()
        threading.Thread(target=self._fetch_video_url_thread, args=(resume_pos,), daemon=True).start()

    def _fetch_video_url_thread(self, resume_pos_ms):
        import yt_dlp
        try:
            ydl_opts = self._get_base_ydl_opts()
            ydl_opts['format'] = 'best'
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.video_url, download=False)
            stream_url = info.get('url') or (info['formats'][0].get('url') if 'formats' in info else None)
            if stream_url:
                self.audio_url = stream_url
                self.resume_position_ms = resume_pos_ms
                wx.CallAfter(self._play_media_with_vlc)
            else:
                raise ValueError(_("Could not extract stream URL for video."))
        except Exception as e:
            wx.CallAfter(self._playback_failed, _("Failed to load video stream: {}").format(e))
        finally:
            wx.CallAfter(lambda: wx.EndBusyCursor() if wx.IsBusy() else None)

    def _fetch_specific_audio_url_thread(self, new_track, resume_pos_ms):
        import yt_dlp
        import settings_manager
        format_id = str(new_track['id'])
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'noprogress': True,
                'noplaylist': True,
                'check_formats': False,
                'nocheckcertificate': True,
                'socket_timeout': 10,
                'format': format_id,
            }
            cookies_path = settings_manager.get_effective_cookies_path(self.main_frame.settings)
            if cookies_path and os.path.exists(cookies_path):
                ydl_opts['cookiefile'] = cookies_path

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.video_url, download=False)

            stream_url = info.get('url')
            if not stream_url and 'formats' in info:
                for f in info['formats']:
                    if str(f.get('format_id')) == format_id and f.get('url'):
                        stream_url = f.get('url')
                        break
                if not stream_url and info['formats']:
                    for f in info['formats']:
                        if f.get('acodec') != 'none' and f.get('url'):
                            stream_url = f.get('url')
                            break

            if stream_url:
                new_track['url'] = stream_url
                self.audio_url = stream_url
                self.resume_position_ms = resume_pos_ms
                self.current_audio_format_id = format_id

                def _apply_switch():
                    if self.player:
                        self.player.stop()
                    self._play_media_with_vlc()
                    self.update_status(_("Switched to audio track: {}").format(new_track['label']))
                    nvda.speak(_("Switched to track: {}").format(new_track['label']), constants.NVDA_VERBOSITY_DEFAULT)
                wx.CallAfter(_apply_switch)
            else:
                raise ValueError(_("Could not extract stream URL for format {}.").format(format_id))

        except Exception as e:
            print(f"Failed to switch audio track: {e}")
            def _handle_failure():
                self._enable_controls()
                if self.player and not self.is_playing:
                    self.player.play()
                    self.is_playing = True
                    self._set_play_pause_label(_("Pause"))
                self.update_status(_("Could not switch audio track."))
                nvda.speak(_("Failed to switch audio track. Current track kept."), constants.NVDA_VERBOSITY_DEFAULT)
            wx.CallAfter(_handle_failure)
        finally:
            wx.CallAfter(lambda: wx.EndBusyCursor() if wx.IsBusy() else None)

    def on_share_current_track(self, event):
        if self.video_url and self.video_title:
            share_text = _("Listening to: {title} - {uploader} via Tunevia {url}").format(
                title=self.video_title,
                uploader=self.video_uploader or _("Unknown Uploader"),
                url=self.video_url
            )
            utils.copy_text_to_clipboard(share_text)
        else:
            nvda.speak(_("No track is currently loaded to share."), constants.NVDA_VERBOSITY_DEFAULT)

    def on_toggle_favorite(self, event):
        self.main_frame.toggle_favorite()

    def update_favorite_button(self, is_favorite):
        self.favorite_button.SetValue(is_favorite)
        if is_favorite:
            self.favorite_button.SetLabel(_("Favorited"))
            self.favorite_button.SetName(_("Remove from Favorites"))
            self.favorite_button.SetToolTip(_("Remove this song from favorites"))
        else:
            self.favorite_button.SetLabel(_("Favorite"))
            self.favorite_button.SetName(_("Add to Favorites"))
            self.favorite_button.SetToolTip(_("Add this song to favorites"))

    def get_audio_devices(self):
        if not self.player or not self.vlc_instance:
            return []
        devices = []
        enum_player = self.player
        tmp_player = None
        if self._using_dsp_output:
            tmp_player = self.vlc_instance.media_player_new()
            enum_player = tmp_player
        try:
            outputs = enum_player.audio_output_device_enum() if enum_player else None
            if outputs:
                try:
                    dev = outputs
                    while dev:
                        device_val = dev.contents.device
                        desc_val = dev.contents.description
                        if desc_val is not None:
                            d_val = device_val.decode('utf-8', 'ignore') if device_val else ""
                            d_desc = desc_val.decode('utf-8', 'ignore')
                            devices.append((d_val, d_desc))
                        if not dev.contents.next:
                            break
                        dev = dev.contents.next
                finally:
                    vlc.libvlc_audio_output_device_list_release(outputs)
        finally:
            if tmp_player:
                tmp_player.release()
        return devices

    def set_audio_device(self, device_id):
        if self.player and not self._using_dsp_output:
            dev_str = device_id if device_id else ""
            self.player.audio_output_device_set(None, dev_str)

    def populate_audio_devices_choice(self):
        if not self or not self.audio_device_choice or self.devices_populated: return
        self.audio_devices = self.get_audio_devices()
        if not self.audio_devices:
            self.audio_device_choice.Clear()
            self.audio_device_choice.Append(_("No devices found"))
            self.audio_device_choice.Disable()
            return
        self.devices_populated = True
        self.audio_device_choice.Clear()
        current_device_id = self.main_frame.settings.get("audio_output_device", "")
        selection_index = -1
        for i, (dev_id, dev_desc) in enumerate(self.audio_devices):
            self.audio_device_choice.Append(dev_desc)
            if dev_id == current_device_id:
                selection_index = i
        if selection_index != -1:
            self.audio_device_choice.SetSelection(selection_index)
        elif self.audio_device_choice.GetCount() > 0:
            self.audio_device_choice.SetSelection(0)
        self.on_select_audio_device(None, speak=False)
        self.audio_device_choice.Enable()

    def on_select_audio_device(self, event, speak=True):
        sel_index = self.audio_device_choice.GetSelection()
        if sel_index == wx.NOT_FOUND or not self.audio_devices:
            return
        device_id, device_desc = self.audio_devices[sel_index]
        self.main_frame.settings["audio_output_device"] = device_id
        if self._using_dsp_output:
            dev_idx = spatial_audio.WinMMOutput.match_device_id(device_desc)
            if not self.winmm_output.is_open() or self.winmm_output._device_id != dev_idx:
                self.winmm_output.open(
                    device_id=dev_idx,
                    sample_rate=44100,
                    channels=2,
                    bits=16,
                    processor_fn=self.spatial_processor.process_chunk,
                )
        else:
            self.set_audio_device(device_id)
        if speak:
            nvda.speak(_("Audio output set to {}").format(device_desc), constants.NVDA_VERBOSITY_DEFAULT)

    def on_open_equalizer(self, event):
        if not feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_EQUALIZER):
            nvda.speak(_("Equalizer is disabled in Feature Manager."), constants.NVDA_VERBOSITY_DEFAULT)
            return
        if not self.is_loaded:
            nvda.speak(_("Load an audio track to use the equalizer."), constants.NVDA_VERBOSITY_DEFAULT)
            return
        if self.equalizer_dialog and self.equalizer_dialog.IsShown():
            self.equalizer_dialog.Raise()
            return
        eq_settings = {
            "enabled": self.main_frame.settings.get("equalizer_enabled", False),
            "preamp": self.main_frame.settings.get("equalizer_preamp", constants.DEFAULT_PREAMP_PERCENT),
            "bands": self.main_frame.settings.get("equalizer_bands", constants.EQUALIZER_PRESETS["Flat"]),
            "custom_presets": self.main_frame.settings.get("equalizer_presets", {}),
            "preset_name": self.main_frame.settings.get("equalizer_preset_name", "Flat")
        }
        self.equalizer_dialog = EqualizerDialog(self.main_frame, eq_settings)
        if self.equalizer_dialog.ShowModal() == wx.ID_OK:
            new_settings = self.equalizer_dialog.get_new_settings()
            self.main_frame.settings["equalizer_enabled"] = new_settings["enabled"]
            self.main_frame.settings["equalizer_preamp"] = new_settings["preamp"]
            self.main_frame.settings["equalizer_bands"] = new_settings["bands"]
            self.main_frame.settings["equalizer_presets"] = new_settings.get("custom_presets", {})
            self.main_frame.settings["equalizer_preset_name"] = new_settings.get("preset_name", "Flat")
            self.apply_equalizer_settings(new_settings)
            self.main_frame.save_settings()
            nvda.speak(_("Equalizer settings applied."), constants.NVDA_VERBOSITY_DEFAULT)
        else:
            self.apply_equalizer_settings({
                "enabled": self.main_frame.settings.get("equalizer_enabled", False),
                "preamp": self.main_frame.settings.get("equalizer_preamp", constants.DEFAULT_PREAMP_PERCENT),
                "bands": self.main_frame.settings.get("equalizer_bands", constants.EQUALIZER_PRESETS["Flat"]),
            })
        self.equalizer_dialog.Destroy()
        self.equalizer_dialog = None

    def apply_equalizer_settings(self, settings):
        if not self.player or not self.equalizer: return
        is_enabled = settings.get("enabled", False)
        if not is_enabled:
            self.player.set_equalizer(None)
            return
        preamp_percent = settings.get("preamp", constants.DEFAULT_PREAMP_PERCENT)
        preamp_db = constants.EQUALIZER_MIN_GAIN + (preamp_percent / constants.PREAMP_MAX_PERCENT) * (constants.EQUALIZER_MAX_GAIN - constants.EQUALIZER_MIN_GAIN)
        self.equalizer.set_preamp(preamp_db)
        bands = settings.get("bands", constants.EQUALIZER_PRESETS["Flat"])
        for i, gain in enumerate(bands):
            if i < constants.EQUALIZER_BANDS:
                self.equalizer.set_amp_at_index(float(gain), i)
        self.player.set_equalizer(self.equalizer)

    def _apply_dsp_backend_transition(self):
        """Updates live DSP parameters in 0 ms, or switches VLC output backend smoothly."""
        self._sync_dsp_settings()
        need_dsp = self._needs_dsp_pipeline()
        if need_dsp == self._using_dsp_output:
            return
        if self.is_loaded and self.player and self.audio_url:
            cur_time = self.player.get_time()
            was_playing = self.is_playing
            self.resume_position_ms = cur_time if cur_time > 0 else self._last_valid_pos_ms
            self.player.stop()
            self._play_media_with_vlc(self._current_request_id)
            if not was_playing:
                wx.CallLater(250, lambda: self.player.set_pause(1) if self.player else None)

    def on_toggle_spatial_audio(self, event=None):
        if not feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_SPATIAL_AUDIO):
            nvda.speak(_("Spatial Audio is disabled in Feature Manager."), constants.NVDA_VERBOSITY_DEFAULT)
            self._update_spatial_button_ui()
            return
        is_spatial = not self.main_frame.settings.get("spatial_audio_enabled", False)
        self.main_frame.settings["spatial_audio_enabled"] = is_spatial
        if is_spatial and self.main_frame.settings.get("mono_audio", False):
            self.main_frame.settings["mono_audio"] = False
        self._update_spatial_button_ui()
        self._apply_dsp_backend_transition()
        self.main_frame.save_settings()
        preset = self.main_frame.settings.get("spatial_audio_preset", constants.DEFAULT_SPATIAL_PRESET)
        nvda.speak(
            _("Spatial Audio enabled ({preset}).").format(preset=preset) if is_spatial else _("Spatial Audio disabled."),
            constants.NVDA_VERBOSITY_DEFAULT
        )

    def on_open_spatial_audio(self, event=None):
        if not feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_SPATIAL_AUDIO):
            nvda.speak(_("Spatial Audio is disabled in Feature Manager."), constants.NVDA_VERBOSITY_DEFAULT)
            return
        if self.spatial_dialog and self.spatial_dialog.IsShown():
            self.spatial_dialog.Raise()
            return
        spatial_cfg = {
            "enabled": self.main_frame.settings.get("spatial_audio_enabled", False),
            "preset": self.main_frame.settings.get("spatial_audio_preset", constants.DEFAULT_SPATIAL_PRESET),
            "width": self.main_frame.settings.get("spatial_audio_width", constants.DEFAULT_SPATIAL_WIDTH),
            "room_size": self.main_frame.settings.get("spatial_audio_room_size", constants.DEFAULT_SPATIAL_ROOM),
            "depth": self.main_frame.settings.get("spatial_audio_depth", constants.DEFAULT_SPATIAL_DEPTH),
        }
        self.spatial_dialog = SpatialAudioDialog(self.main_frame, spatial_cfg)
        if self.spatial_dialog.ShowModal() == wx.ID_OK:
            new_cfg = self.spatial_dialog.get_new_settings()
            self.apply_spatial_audio_settings(new_cfg)
            self.main_frame.save_settings()
            nvda.speak(_("Spatial Audio settings applied."), constants.NVDA_VERBOSITY_DEFAULT)
        else:
            self.apply_spatial_audio_settings(spatial_cfg)
        self.spatial_dialog.Destroy()
        self.spatial_dialog = None

    def apply_spatial_audio_settings(self, cfg):
        if not cfg:
            return
        enabled = bool(cfg.get("enabled", False))
        self.main_frame.settings["spatial_audio_enabled"] = enabled
        self.main_frame.settings["spatial_audio_preset"] = cfg.get("preset", constants.DEFAULT_SPATIAL_PRESET)
        self.main_frame.settings["spatial_audio_width"] = int(cfg.get("width", constants.DEFAULT_SPATIAL_WIDTH))
        self.main_frame.settings["spatial_audio_room_size"] = int(cfg.get("room_size", constants.DEFAULT_SPATIAL_ROOM))
        self.main_frame.settings["spatial_audio_depth"] = int(cfg.get("depth", constants.DEFAULT_SPATIAL_DEPTH))
        if enabled and self.main_frame.settings.get("mono_audio", False):
            self.main_frame.settings["mono_audio"] = False
        self._update_spatial_button_ui()
        self._apply_dsp_backend_transition()

    def apply_normalization(self, enabled):
        self._apply_dsp_backend_transition()

    def on_toggle_mono(self, event=None):
        if not feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_MONO_AUDIO):
            nvda.speak(_("Mono audio is disabled in Feature Manager."), constants.NVDA_VERBOSITY_DEFAULT)
            return
        is_mono = not self.main_frame.settings.get("mono_audio", False)
        self.main_frame.settings["mono_audio"] = is_mono
        if is_mono and self.main_frame.settings.get("spatial_audio_enabled", False):
            self.main_frame.settings["spatial_audio_enabled"] = False
            self._update_spatial_button_ui()
        self.apply_mono_setting()
        self.main_frame.save_settings()
        nvda.speak(_("Mono audio enabled.") if is_mono else _("Stereo audio enabled."), constants.NVDA_VERBOSITY_DEFAULT)

    def apply_mono_setting(self):
        if not self.player: return
        self._apply_dsp_backend_transition()

    def on_open_bookmarks(self, event):
        if not feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_BOOKMARKS):
            nvda.speak(_("Bookmarks are disabled in Feature Manager."), constants.NVDA_VERBOSITY_DEFAULT)
            return
        if not self.is_loaded:
            nvda.speak(_("Load an audio track to manage bookmarks."), constants.NVDA_VERBOSITY_DEFAULT)
            return
        if self.bookmarks_dialog and self.bookmarks_dialog.IsShown():
            self.bookmarks_dialog.Raise()
            return
        self.bookmarks_dialog = BookmarksDialog(self.main_frame, self.main_frame, self.video_url)
        self.bookmarks_dialog.ShowModal()
        self.bookmarks_dialog.Destroy()
        self.bookmarks_dialog = None
    
    def on_add_bookmark_hotkey(self, event):
        if not self.is_loaded: return
        current_time = self.get_current_time()
        time_str = utils.format_time_ms(current_time)
        with wx.TextEntryDialog(self.main_frame, _("Enter a description for the bookmark at {}:").format(time_str), _("Add Bookmark")) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                desc = dlg.GetValue().strip()
                if desc:
                    self.add_bookmark(desc, current_time)
                else:
                    utils.show_error_dialog(self.main_frame, _("Description cannot be empty."))

    def add_bookmark(self, description, time_ms):
        if not self.video_url: return
        all_bookmarks = self.main_frame.settings.get("playback_bookmarks", {})
        if self.video_url not in all_bookmarks:
            all_bookmarks[self.video_url] = []
        video_bookmarks = all_bookmarks[self.video_url]
        if len(video_bookmarks) >= constants.MAX_BOOKMARKS_PER_VIDEO:
            nvda.speak(_("Maximum bookmarks reached for this video."), constants.NVDA_VERBOSITY_DEFAULT)
            return
        new_bookmark = {"time": time_ms, "desc": description}
        video_bookmarks.append(new_bookmark)
        self.main_frame.save_settings()
        utils.play_sound(self.main_frame.settings, "bookmark_added")
        nvda.speak(_("Bookmark added at {}.").format(utils.format_time_ms(time_ms)), constants.NVDA_VERBOSITY_DEFAULT)

    def get_current_time(self):
        if self.player and self.is_loaded:
            return self.player.get_time()
        return 0

    def _apply_nvda_duck_hook(self):
        if self.main_frame.settings.get("nvda_ducking_enabled", False):
            def _on_nvda_speak(spoken_text):
                if self.is_playing and self._using_dsp_output and not self._is_lossless_active():
                    dur = max(0.8, min(4.0, len(spoken_text) * 0.055 + 0.5))
                    self.spatial_processor.trigger_duck(duration_s=dur, level=0.30)
            nvda.set_speech_hook(_on_nvda_speak)
        else:
            nvda.set_speech_hook(None)

    def seek_to_percent(self, percent):
        if not self.player or not self.is_loaded:
            return
        length = self.player.get_length()
        if length <= 0:
            length = getattr(self, '_last_known_length_ms', 0)
        if length <= 0:
            nvda.speak(_("Duration not available for percentage jump."))
            return
        pct = max(0, min(99, int(percent)))
        target_ms = int((pct / 100.0) * length)
        self.seek_to(target_ms)
        nvda.speak(_("Jumped to {pct} percent, {time}").format(pct=pct, time=utils.format_time_ms(target_ms)))

    def speak_track_and_audio_info(self):
        if not self.is_loaded:
            nvda.speak(_("No audio loaded."), constants.NVDA_VERBOSITY_DEFAULT)
            return
        cur = max(0, self.get_current_time())
        length = self.player.get_length() if self.player else 0
        if length <= 0:
            length = getattr(self, '_last_known_length_ms', 0)
        pct = int((cur / length) * 100) if length > 0 else 0
        rem = max(0, length - cur) if length > 0 else 0

        modes = []
        s = self.main_frame.settings
        if self._is_lossless_active():
            modes.append(_("Lossless Bit-Perfect"))
        else:
            if s.get("spatial_audio_enabled"): modes.append(_("Spatial Audio"))
            if int(s.get("bass_boost", 0)) > 0: modes.append(_("Bass Boost {}%").format(s.get("bass_boost")))
            if s.get("vocal_clarity_enabled"): modes.append(_("Vocal Clarity"))
            if s.get("night_mode_enabled"): modes.append(_("Night Mode"))
            if s.get("mono_audio"): modes.append(_("Mono"))
            if s.get("equalizer_enabled"): modes.append(_("Equalizer"))
            if s.get("nvda_ducking_enabled"): modes.append(_("NVDA Ducking"))
        mode_str = ", ".join(modes) if modes else _("Standard")

        ext_info = _("Local File") if self.is_local_file else _("YouTube Stream")
        if self.is_local_file and self.local_file_path:
            ext = os.path.splitext(self.local_file_path)[1].lstrip('.').upper()
            if ext:
                ext_info = ext

        rate = self.speed_slider.GetValue() / 100.0
        vol = self.volume_slider.GetValue()
        msg = _("{title}, by {artist}. {cur} of {total}, {pct} percent, {rem} remaining. Volume {vol} percent, speed {rate:.2f}x. Audio mode: {modes}. Source: {src}.").format(
            title=self.video_title or _("Untitled"),
            artist=self.video_uploader or _("Unknown"),
            cur=utils.format_time_ms(cur),
            total=utils.format_time_ms(length) if length > 0 else "--:--",
            pct=pct,
            rem=utils.format_time_ms(rem) if length > 0 else "--:--",
            vol=vol,
            rate=rate,
            modes=mode_str,
            src=ext_info,
        )
        nvda.speak(msg, constants.NVDA_VERBOSITY_DEFAULT)

    def load_and_play_local(self, file_path):
        if not VLC_ENABLED or not file_path or not os.path.exists(file_path):
            nvda.speak(_("Audio file not found."))
            return
        self.stop_playback(silent=True)
        self._current_request_id += 1
        request_id = self._current_request_id

        self.is_local_file = True
        self.local_file_path = os.path.abspath(file_path)
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        ext = os.path.splitext(file_path)[1].lstrip('.').upper() or "AUDIO"

        self.video_url = self.local_file_path
        self.audio_url = self.local_file_path
        self.video_title = base_name
        self.video_uploader = _("Local {}").format(ext)
        self.current_track_index = None
        self.is_radio_mode = False
        self.is_playing = self.is_loaded = self.is_finished = self.notification_sound_played = False
        self.available_audio_tracks = []
        self.chapters = []
        self.chapters_button.Hide()
        self.title_text.SetValue(f"{self.video_title} - {self.video_uploader}")
        self.update_favorite_button(False)
        self.main_frame.update_window_title("Loading", self.video_title)
        self._play_media_with_vlc(request_id)

    def on_open_local_audio(self, event=None):
        wildcard = (
            "Audio Files (*.flac;*.wav;*.aiff;*.wv;*.ape;*.alac;*.m4a;*.mp3;*.ogg;*.opus;*.aac)|"
            "*.flac;*.wav;*.aiff;*.aif;*.wv;*.ape;*.alac;*.m4a;*.mp3;*.ogg;*.opus;*.aac|"
            "Lossless Audio (*.flac;*.wav;*.aiff;*.wv;*.ape;*.alac)|*.flac;*.wav;*.aiff;*.aif;*.wv;*.ape;*.alac|"
            "All Files (*.*)|*.*"
        )
        with wx.FileDialog(
            self.main_frame,
            message=_("Open Local or Lossless Audio"),
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                paths = dlg.GetPaths()
                if paths:
                    self.load_and_play_local(paths[0])
                    for extra_path in paths[1:]:
                        self.add_to_queue({
                            "url": extra_path,
                            "title": os.path.splitext(os.path.basename(extra_path))[0],
                            "uploader": _("Local Audio"),
                            "is_local": True,
                        }, play_next=False, announce=False)
                    if len(paths) > 1:
                        nvda.speak(_("Playing first file and added {} file(s) to Up-Next queue.").format(len(paths) - 1))

    def on_toggle_lossless_mode(self, event=None):
        new_val = not self.main_frame.settings.get("lossless_mode", False)
        self.main_frame.settings["lossless_mode"] = new_val
        self.main_frame.save_settings()
        self._apply_dsp_backend_transition()
        nvda.speak(_("Lossless Bit-Perfect mode enabled.") if new_val else _("Lossless Bit-Perfect mode disabled."))

    def on_cycle_bass_boost(self, event=None):
        levels = [0, 35, 70, 100]
        cur = int(self.main_frame.settings.get("bass_boost", 0))
        next_level = next((lv for lv in levels if lv > cur), 0)
        self.main_frame.settings["bass_boost"] = next_level
        self.main_frame.save_settings()
        self._apply_dsp_backend_transition()
        nvda.speak(_("Bass boost {} percent.").format(next_level) if next_level > 0 else _("Bass boost off."))

    def on_toggle_vocal_clarity(self, event=None):
        new_val = not self.main_frame.settings.get("vocal_clarity_enabled", False)
        self.main_frame.settings["vocal_clarity_enabled"] = new_val
        self.main_frame.save_settings()
        self._apply_dsp_backend_transition()
        nvda.speak(_("Vocal Clarity mode enabled.") if new_val else _("Vocal Clarity mode disabled."))

    def on_toggle_night_mode(self, event=None):
        new_val = not self.main_frame.settings.get("night_mode_enabled", False)
        self.main_frame.settings["night_mode_enabled"] = new_val
        self.main_frame.save_settings()
        self._apply_dsp_backend_transition()
        nvda.speak(_("Night Listening mode enabled.") if new_val else _("Night Listening mode disabled."))

    def on_toggle_nvda_ducking(self, event=None):
        new_val = not self.main_frame.settings.get("nvda_ducking_enabled", False)
        self.main_frame.settings["nvda_ducking_enabled"] = new_val
        self.main_frame.save_settings()
        self._apply_nvda_duck_hook()
        self._apply_dsp_backend_transition()
        nvda.speak(_("Screen reader audio ducking enabled.") if new_val else _("Screen reader audio ducking disabled."))

    def on_toggle_ab_loop(self, event=None):
        if not self.is_loaded or not self.player:
            nvda.speak(_("No audio loaded."))
            return
        cur = max(0, self.get_current_time())
        if self.loop_a_ms is None:
            self.loop_a_ms = cur
            nvda.speak(_("Loop point A set at {}.").format(utils.format_time_ms(cur)))
        elif self.loop_b_ms is None:
            if cur <= self.loop_a_ms + 300:
                nvda.speak(_("Loop point B must be after point A."))
                return
            self.loop_b_ms = cur
            if self.timer.IsRunning():
                self.timer.Stop()
                self.timer.Start(250)
            self.seek_to(self.loop_a_ms)
            nvda.speak(_("A-B Loop active from {a} to {b}.").format(a=utils.format_time_ms(self.loop_a_ms), b=utils.format_time_ms(self.loop_b_ms)))
        else:
            self.loop_a_ms = None
            self.loop_b_ms = None
            if self.timer.IsRunning():
                self.timer.Stop()
                self.timer.Start(500)
            nvda.speak(_("A-B Loop cleared."))

    def set_sleep_timer(self, minutes):
        self._sleep_timer_minutes = int(minutes)
        if minutes == 0:
            self._sleep_end_time = None
            self._sleep_at_track_end = False
            base_vol = self.main_frame.settings.get("volume", constants.DEFAULT_VOLUME_PERCENT)
            self.spatial_processor.configure(volume_percent=base_vol)
            if self.player and not self._using_dsp_output:
                self.player.audio_set_volume(base_vol)
            nvda.speak(_("Sleep timer turned off."))
        elif minutes == -1:
            self._sleep_end_time = None
            self._sleep_at_track_end = True
            nvda.speak(_("Sleep timer set to stop at the end of current track."))
        else:
            self._sleep_at_track_end = False
            self._sleep_end_time = time.time() + (minutes * 60.0)
            nvda.speak(_("Sleep timer set for {} minutes.").format(minutes))

    def on_open_sleep_timer(self, event=None):
        with SleepTimerDialog(self.main_frame, self._sleep_timer_minutes) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.set_sleep_timer(dlg.get_selected_minutes())

    def add_to_queue(self, track_info, play_next=True, announce=True):
        if not track_info or not isinstance(track_info, dict) or not track_info.get("url"):
            return
        if play_next:
            self.up_next_queue.insert(0, dict(track_info))
        else:
            self.up_next_queue.append(dict(track_info))
        if not track_info.get("is_local") and str(track_info["url"]).startswith("http"):
            self.prefetch_stream_url(track_info["url"])
        if announce:
            title = track_info.get("title") or _("track")
            nvda.speak(_("Added {} to Up-Next queue.").format(title), constants.NVDA_VERBOSITY_DEFAULT)

    def play_queue_entry(self, entry):
        if not entry:
            return
        if entry.get("is_local") or (entry.get("url") and not str(entry["url"]).startswith("http")):
            self.load_and_play_local(entry.get("url"))
        else:
            self.main_frame.request_audio_play(
                entry.get("url"),
                entry.get("title"),
                entry.get("uploader"),
                upload_date=entry.get("upload_date"),
            )

    def on_open_queue(self, event=None):
        with UpNextQueueDialog(self.main_frame, self) as dlg:
            dlg.ShowModal()