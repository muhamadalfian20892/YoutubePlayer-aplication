"""
test_feature_manager_system.py

Comprehensive test suite verifying:
1. Feature Registry & Categories & Presets
2. Dependency Enforcement (Cascading Enable/Disable)
3. Settings Persistence, Validation & Legacy Migration
4. User Data Preservation (Favorites, History, Bookmarks)
5. Onboarding Dialog Flow & Presets
6. Selective Startup & Lazy Loading
7. Dynamic Feature Toggling & Restart Advisory
"""

import os
import sys
import json
import unittest

# Ensure imports work from current directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import wx
# Create wxApp instance for tests
if not wx.GetApp():
    app = wx.App(False)
else:
    app = wx.GetApp()

def setUpModule():
    if not wx.GetApp():
        wx.App(False)

import path_utils
import feature_manager
import settings_manager
import constants
from onboarding_dialog import OnboardingDialog

# Backup actual settings file to guarantee test run leaves user settings in pristine state
_SETTINGS_BACKUP = None
_settings_path = path_utils.get_resource_path(constants.SETTINGS_FILE_NAME)
if os.path.exists(_settings_path):
    with open(_settings_path, "r", encoding="utf-8") as _f:
        _SETTINGS_BACKUP = _f.read()

def tearDownModule():
    if _SETTINGS_BACKUP is not None:
        with open(_settings_path, "w", encoding="utf-8") as _f:
            _f.write(_SETTINGS_BACKUP)


class TestFeatureManagerCore(unittest.TestCase):
    def test_registry_and_categories(self):
        """Verify all categories and 22+ features are registered with proper attributes."""
        self.assertEqual(len(feature_manager.CATEGORIES), 6)
        self.assertIn(feature_manager.CATEGORY_CORE, feature_manager.CATEGORIES)
        self.assertIn(feature_manager.CATEGORY_DISCOVERY, feature_manager.CATEGORIES)
        self.assertIn(feature_manager.CATEGORY_LYRICS, feature_manager.CATEGORIES)
        self.assertIn(feature_manager.CATEGORY_DOWNLOADS, feature_manager.CATEGORIES)
        self.assertIn(feature_manager.CATEGORY_AUDIO, feature_manager.CATEGORIES)
        self.assertIn(feature_manager.CATEGORY_ADVANCED, feature_manager.CATEGORIES)

        self.assertGreaterEqual(len(feature_manager.FEATURE_REGISTRY), 22)
        for fid, spec in feature_manager.FEATURE_REGISTRY.items():
            self.assertEqual(fid, spec["id"])
            self.assertIn("name", spec)
            self.assertIn("category", spec)
            self.assertIn("description", spec)
            self.assertIn("default", spec)
            self.assertIn("dependencies", spec)
            self.assertIn("requires_restart", spec)

    def test_presets(self):
        """Verify the 4 presets and their specific requirements."""
        self.assertIn(feature_manager.PRESET_MUSIC_PLAYER, feature_manager.PRESETS_CONFIG)
        self.assertIn(feature_manager.PRESET_MUSIC_DISCOVERY, feature_manager.PRESETS_CONFIG)
        self.assertIn(feature_manager.PRESET_POWER_USER, feature_manager.PRESETS_CONFIG)
        self.assertIn(feature_manager.PRESET_RECOMMENDED, feature_manager.PRESETS_CONFIG)

        # Music player preset must have core audio, no discovery/downloader/video
        mp = feature_manager.PRESETS_CONFIG[feature_manager.PRESET_MUSIC_PLAYER]["features"]
        self.assertTrue(mp[feature_manager.FEATURE_AUDIO_PLAYER])
        self.assertTrue(mp[feature_manager.FEATURE_YOUTUBE_SEARCH])
        self.assertFalse(mp[feature_manager.FEATURE_DISCOVER])
        self.assertFalse(mp[feature_manager.FEATURE_RADAR])
        self.assertFalse(mp[feature_manager.FEATURE_DOWNLOADER])

        # Music + Discovery must have discover & radar
        md = feature_manager.PRESETS_CONFIG[feature_manager.PRESET_MUSIC_DISCOVERY]["features"]
        self.assertTrue(md[feature_manager.FEATURE_DISCOVER])
        self.assertTrue(md[feature_manager.FEATURE_RADAR])
        self.assertFalse(md[feature_manager.FEATURE_DOWNLOADER])

        # Power User must have all features enabled
        pu = feature_manager.PRESETS_CONFIG[feature_manager.PRESET_POWER_USER]["features"]
        for fid in feature_manager.FEATURE_REGISTRY:
            self.assertTrue(pu.get(fid, False), f"Feature {fid} should be True in Power User")

    def test_dependency_cascading(self):
        """Verify enabling child enables parent, and disabling parent disables child."""
        s = {"enabled_features": feature_manager.get_default_features()}

        # MP3 conversion depends on Downloader
        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_DOWNLOADER, False)
        self.assertFalse(feature_manager.is_feature_enabled(s, feature_manager.FEATURE_DOWNLOADER))
        self.assertFalse(feature_manager.is_feature_enabled(s, feature_manager.FEATURE_MP3_CONVERSION))

        # Enabling MP3 should auto-enable Downloader
        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_MP3_CONVERSION, True)
        self.assertTrue(feature_manager.is_feature_enabled(s, feature_manager.FEATURE_DOWNLOADER))
        self.assertTrue(feature_manager.is_feature_enabled(s, feature_manager.FEATURE_MP3_CONVERSION))

        # Disabling Downloader should auto-disable MP3 and Download Notifications
        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_DOWNLOAD_NOTIFICATIONS, True)
        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_DOWNLOADER, False)
        self.assertFalse(feature_manager.is_feature_enabled(s, feature_manager.FEATURE_MP3_CONVERSION))
        self.assertFalse(feature_manager.is_feature_enabled(s, feature_manager.FEATURE_DOWNLOAD_NOTIFICATIONS))

        # Auto Lyrics depends on Lyrics Search
        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_AUTO_LYRICS, True)
        self.assertTrue(feature_manager.is_feature_enabled(s, feature_manager.FEATURE_LYRICS_SEARCH))
        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_LYRICS_SEARCH, False)
        self.assertFalse(feature_manager.is_feature_enabled(s, feature_manager.FEATURE_AUTO_LYRICS))
        self.assertFalse(feature_manager.is_feature_enabled(s, feature_manager.FEATURE_SAVE_LYRICS))

        # Video Comments depends on Video Player
        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_VIDEO_COMMENTS, True)
        self.assertTrue(feature_manager.is_feature_enabled(s, feature_manager.FEATURE_VIDEO_PLAYER))
        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_VIDEO_PLAYER, False)
        self.assertFalse(feature_manager.is_feature_enabled(s, feature_manager.FEATURE_VIDEO_COMMENTS))

    def test_legacy_settings_sync(self):
        """Verify legacy settings are synchronized when feature manager changes."""
        s = {}
        feature_manager.sync_all_features(s)

        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_SEARCH_SUGGESTIONS, False)
        self.assertFalse(s.get("enable_search_suggestions"))

        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_CLIPBOARD_DETECTION, True)
        self.assertTrue(s.get("monitor_clipboard_for_urls"))

        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_AUDIO_NORMALIZATION, True)
        self.assertTrue(s.get("audio_normalization"))

        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_MONO_AUDIO, True)
        # Enabling mono_audio capability must not force mono playback on automatically
        self.assertFalse(s.get("mono_audio", False))
        # Disabling the capability turns mono playback off
        s["mono_audio"] = True
        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_MONO_AUDIO, False)
        self.assertFalse(s.get("mono_audio"))

    def test_presets_keep_mono_off_by_default(self):
        """Verify applying presets never forces mono audio playback on."""
        for preset_id in (
            feature_manager.PRESET_MUSIC_PLAYER,
            feature_manager.PRESET_MUSIC_DISCOVERY,
            feature_manager.PRESET_RECOMMENDED,
            feature_manager.PRESET_POWER_USER,
        ):
            s = {}
            feature_manager.apply_preset(s, preset_id)
            self.assertFalse(s.get("mono_audio", False), f"Preset {preset_id} forced mono_audio=True")


class TestSettingsManagerPersistence(unittest.TestCase):
    def test_load_and_save_settings_with_features(self):
        """Verify settings_manager saves and loads first_launch_completed and enabled_features."""
        test_settings = settings_manager.load_settings()
        self.assertIn("first_launch_completed", test_settings)
        self.assertIn("enabled_features", test_settings)

        # Test preserving existing data
        test_favorites = [{"title": "Test Song", "url": "https://youtube.com/watch?v=123"}]
        test_settings["favorites"] = test_favorites
        test_settings["enabled_features"][feature_manager.FEATURE_FAVORITES] = False
        settings_manager.save_settings(test_settings)

        # Reload
        reloaded = settings_manager.load_settings()
        self.assertEqual(reloaded["favorites"], test_favorites)
        self.assertFalse(feature_manager.is_feature_enabled(reloaded, feature_manager.FEATURE_FAVORITES))

        # Re-enable favorites and restore
        test_settings["enabled_features"][feature_manager.FEATURE_FAVORITES] = True
        settings_manager.save_settings(test_settings)


class TestOnboardingDialog(unittest.TestCase):
    def test_onboarding_lifecycle(self):
        """Test OnboardingDialog pages, presets, and completion."""
        test_settings = {
            "first_launch_completed": False,
            "enabled_features": {}
        }
        dlg = OnboardingDialog(None, test_settings)
        self.assertEqual(dlg.current_step, 1)

        # Go to Step 2 (Presets)
        dlg.on_continue(None)
        self.assertEqual(dlg.current_step, 2)

        # Select Music Player preset
        dlg.presets_radio.SetSelection(0)
        dlg.on_continue(None)
        # Should jump to step 4 (Confirmation)
        self.assertEqual(dlg.current_step, 4)

        # Finish onboarding
        dlg.finish_onboarding()
        self.assertTrue(test_settings["first_launch_completed"])
        self.assertTrue(test_settings["enabled_features"][feature_manager.FEATURE_AUDIO_PLAYER])
        self.assertFalse(test_settings["enabled_features"][feature_manager.FEATURE_DISCOVER])

        dlg.Destroy()


class TestLazyLoadingAndPanels(unittest.TestCase):
    def test_discovery_lazy_loading(self):
        """Verify DiscoveryPanel does not run scraping threads in __init__."""
        from discovery_panel import DiscoveryPanel
        dummy_frame = wx.Frame(None)
        disc_panel = DiscoveryPanel(dummy_frame, dummy_frame)

        # Should not have loaded data immediately
        self.assertFalse(disc_panel.has_loaded)
        self.assertFalse(disc_panel.is_loading)

        dummy_frame.Destroy()


class TestSettingsPanelIntegration(unittest.TestCase):
    def test_settings_panel_feature_manager(self):
        """Verify Feature Manager section in SettingsPanel."""
        from settings_panel import SettingsPanel

        class DummyMainFrame(wx.Frame):
            def __init__(self):
                super().__init__(None)
                self.settings = settings_manager.load_settings()
            def save_settings(self):
                pass
            def rebuild_accelerators_and_hotkeys(self):
                pass
            def on_change_language(self, event):
                pass
            def on_sound_settings(self, event):
                pass
            def on_customize_shortcuts(self, event):
                pass
            def on_about(self, event):
                pass
            def check_for_updates_and_show_whats_new(self):
                pass

        dummy_mf = DummyMainFrame()
        panel = SettingsPanel(dummy_mf, dummy_mf)

        # Verify all feature checkboxes exist
        self.assertEqual(len(panel.fm_checkboxes), len(feature_manager.FEATURE_REGISTRY))
        for fid in feature_manager.FEATURE_REGISTRY:
            self.assertIn(fid, panel.fm_checkboxes)

        # Test applying a preset via SettingsPanel
        panel.on_apply_preset(feature_manager.PRESET_MUSIC_PLAYER)
        self.assertFalse(dummy_mf.settings["enabled_features"][feature_manager.FEATURE_DISCOVER])
        self.assertTrue(dummy_mf.settings["enabled_features"][feature_manager.FEATURE_AUDIO_PLAYER])

        # Test toggling via checkbox
        dummy_event = wx.CommandEvent(wx.EVT_CHECKBOX.typeId)
        dummy_event.SetEventObject(panel.fm_checkboxes[feature_manager.FEATURE_DISCOVER])
        panel.fm_checkboxes[feature_manager.FEATURE_DISCOVER].SetValue(True)
        panel.on_feature_manager_toggle(dummy_event, feature_manager.FEATURE_DISCOVER)
        self.assertTrue(dummy_mf.settings["enabled_features"][feature_manager.FEATURE_DISCOVER])

        dummy_mf.Destroy()

    def test_duplicate_controls_removed(self):
        """Verify that duplicate controls were removed from regular settings in SettingsPanel."""
        from settings_panel import SettingsPanel

        class DummyMainFrame(wx.Frame):
            def __init__(self):
                super().__init__(None)
                self.settings = settings_manager.load_settings()
            def save_settings(self):
                pass
            def rebuild_accelerators_and_hotkeys(self):
                pass
            def on_change_language(self, event):
                pass
            def on_sound_settings(self, event):
                pass
            def on_customize_shortcuts(self, event):
                pass
            def on_about(self, event):
                pass
            def check_for_updates_and_show_whats_new(self):
                pass

        dummy_mf = DummyMainFrame()
        panel = SettingsPanel(dummy_mf, dummy_mf)

        # Ensure duplicate controls do NOT exist on the panel
        self.assertFalse(hasattr(panel, "enable_suggestions_check"))
        self.assertFalse(hasattr(panel, "normalization_check"))
        self.assertFalse(hasattr(panel, "minimize_to_tray_check"))
        self.assertFalse(hasattr(panel, "auto_fetch_lyrics_check"))
        self.assertFalse(hasattr(panel, "monitor_clipboard_check"))
        self.assertFalse(hasattr(panel, "enable_shortcuts_check"))

        # Verify accessible names on remaining controls
        self.assertTrue(bool(panel.search_mode_radio.GetName()))
        self.assertTrue(bool(panel.comment_limit_choice.GetName()))
        self.assertTrue(bool(panel.clear_cache_button.GetName()))
        self.assertTrue(bool(panel.seek_interval_choice.GetName()))
        self.assertTrue(bool(panel.autoplay_check.GetName()))
        self.assertTrue(bool(panel.remember_position_check.GetName()))
        self.assertTrue(bool(panel.theme_choice.GetName()))
        self.assertTrue(bool(panel.always_on_top_check.GetName()))
        self.assertTrue(bool(panel.nvda_verbosity_radio.GetName()))
        self.assertTrue(bool(panel.cookies_path_text.GetName()))
        self.assertTrue(bool(panel.cookies_browse_button.GetName()))
        self.assertTrue(bool(panel.cookies_clear_button.GetName()))
        self.assertTrue(bool(panel.equalizer_button.GetName()))
        self.assertTrue(bool(panel.pref_lang_button.GetName()))
        self.assertTrue(bool(panel.change_lang_button.GetName()))
        self.assertTrue(bool(panel.sound_settings_button.GetName()))
        self.assertTrue(bool(panel.shortcuts_button.GetName()))

        dummy_mf.Destroy()

    def test_accessible_labels_across_panels(self):
        """Verify that edit boxes and buttons across panels have accessible names."""
        from youtube_panel import YoutubeSearchPanel
        from lyrics_panel import LyricsSearchPanel
        from history_panel import HistoryPanel
        from favorites_panel import FavoritesPanel

        class DummyMF(wx.Frame):
            def __init__(self):
                super().__init__(None)
                self.settings = settings_manager.load_settings()
                self.audio_player_panel = None
            def save_settings(self): pass
            def add_to_favorites(self, d): pass

        mf = DummyMF()
        
        # YouTube Panel
        yt_panel = YoutubeSearchPanel(mf, mf)
        self.assertTrue(bool(yt_panel.search_input.GetName()))
        self.assertTrue(bool(yt_panel.search_label.GetLabel()))
        self.assertTrue(bool(yt_panel.playlist_button.GetName()))
        self.assertTrue(bool(yt_panel.results_list.GetName()))
        self.assertTrue(bool(yt_panel.related_videos_list.GetName()))
        self.assertTrue(bool(yt_panel.load_more_button.GetName()))
        self.assertTrue(bool(yt_panel.run_ytdl_button.GetName()))
        self.assertTrue(bool(yt_panel.exit_button.GetName()))
        yt_panel.Destroy()

        # Lyrics Panel
        lyrics_panel = LyricsSearchPanel(mf, mf)
        self.assertTrue(bool(lyrics_panel.tc_judul.GetName()))
        self.assertTrue(bool(lyrics_panel.tc_artis.GetName()))
        self.assertTrue(bool(lyrics_panel.cb_no_artist.GetName()))
        self.assertTrue(bool(lyrics_panel.button_cari.GetName()))
        self.assertTrue(bool(lyrics_panel.display_area.GetName()))
        self.assertTrue(bool(lyrics_panel.button_copy.GetName()))
        self.assertTrue(bool(lyrics_panel.button_save.GetName()))
        lyrics_panel.Destroy()

        # History Panel
        hist_panel = HistoryPanel(mf, mf)
        self.assertTrue(bool(hist_panel.search_ctrl.GetName()))
        self.assertTrue(bool(hist_panel.history_list.GetName()))
        self.assertTrue(bool(hist_panel.play_button.GetName()))
        self.assertTrue(bool(hist_panel.remove_button.GetName()))
        self.assertTrue(bool(hist_panel.export_button.GetName()))
        self.assertTrue(bool(hist_panel.clear_button.GetName()))
        hist_panel.Destroy()

        # Favorites Panel
        fav_panel = FavoritesPanel(mf, mf)
        self.assertTrue(bool(fav_panel.favorites_list.GetName()))
        self.assertTrue(bool(fav_panel.play_button.GetName()))
        self.assertTrue(bool(fav_panel.remove_button.GetName()))
        fav_panel.Destroy()

        mf.Destroy()


class TestMainFrameSelectiveStartup(unittest.TestCase):
    def test_disabled_panels_not_initialized(self):
        """Verify MainFrame skips initializing disabled panels."""
        import tunevia

        # Save backup settings
        orig_settings = settings_manager.load_settings()

        try:
            # Set minimal features using set_feature_enabled for proper cascading
            test_settings = orig_settings.copy()
            feature_manager.set_feature_enabled(test_settings, feature_manager.FEATURE_DISCOVER, False)
            feature_manager.set_feature_enabled(test_settings, feature_manager.FEATURE_RADAR, False)
            feature_manager.set_feature_enabled(test_settings, feature_manager.FEATURE_STATS, False)
            feature_manager.set_feature_enabled(test_settings, feature_manager.FEATURE_LYRICS_SEARCH, False)
            feature_manager.set_feature_enabled(test_settings, feature_manager.FEATURE_CLIPBOARD_DETECTION, False)
            feature_manager.set_feature_enabled(test_settings, feature_manager.FEATURE_SYSTEM_TRAY, False)
            test_settings["first_launch_completed"] = True
            settings_manager.save_settings(test_settings)

            # Create MainFrame
            frame = tunevia.MainFrame(None, title="Test Tunevia")

            # Disabled panels must be None!
            self.assertIsNone(frame.discovery_panel)
            self.assertIsNone(frame.radar_panel)
            self.assertIsNone(frame.stats_panel)
            self.assertIsNone(frame.lyrics_panel)

            # Enabled panels must NOT be None
            self.assertIsNotNone(frame.youtube_panel)
            self.assertIsNotNone(frame.audio_player_panel)
            self.assertIsNotNone(frame.settings_panel)
            self.assertIsNotNone(frame.help_panel)

            # Panels dict must not contain disabled panels
            self.assertNotIn("discovery", frame.panels)
            self.assertNotIn("radar", frame.panels)
            self.assertNotIn("stats", frame.panels)
            self.assertNotIn("lyrics", frame.panels)

            # Rebuild notebook must only show enabled panels
            frame.rebuild_notebook()
            page_count = frame.notebook.GetPageCount()
            for i in range(page_count):
                page_text = frame.notebook.GetPageText(i)
                self.assertNotIn("Discovery", page_text)
                self.assertNotIn("Radar", page_text)
                self.assertNotIn("Lyrics", page_text)
                self.assertNotIn("Statistics", page_text)

            # Clipboard timer must not be running
            self.assertFalse(frame.clipboard_timer.IsRunning())

            # System tray icon must not be created
            self.assertIsNone(frame.taskbar_icon)

            frame.Destroy()

        finally:
            # Restore original settings
            settings_manager.save_settings(orig_settings)


class TestDataPreservation(unittest.TestCase):
    def test_data_intact_when_features_disabled(self):
        """Verify disabling history, favorites, bookmarks never deletes user data."""
        test_settings = settings_manager.load_settings()

        sample_history = [{"title": "Track 1", "uploader": "Artist 1", "url": "https://youtu.be/1", "timestamp": "2026-09-03T12:00:00Z"}]
        sample_favorites = [{"title": "Fav 1", "url": "https://youtu.be/2"}]
        sample_bookmarks = {"https://youtu.be/3": [{"time": 5000, "desc": "Intro"}]}

        test_settings["play_history"] = sample_history
        test_settings["favorites"] = sample_favorites
        test_settings["playback_bookmarks"] = sample_bookmarks

        # Disable all related features
        feature_manager.set_feature_enabled(test_settings, feature_manager.FEATURE_HISTORY, False)
        feature_manager.set_feature_enabled(test_settings, feature_manager.FEATURE_FAVORITES, False)
        feature_manager.set_feature_enabled(test_settings, feature_manager.FEATURE_BOOKMARKS, False)

        settings_manager.save_settings(test_settings)

        # Reload and check data intact
        reloaded = settings_manager.load_settings()
        self.assertEqual(reloaded["play_history"], sample_history)
        self.assertEqual(reloaded["favorites"], sample_favorites)
        self.assertEqual(reloaded["playback_bookmarks"], sample_bookmarks)



class TestPlayerShortcutsInPresets(unittest.TestCase):
    def test_music_player_preset_has_player_shortcuts(self):
        """Verify that Music Player and Music+Discovery presets include player keyboard shortcuts & hotkeys."""
        mp_preset = feature_manager.PRESETS_CONFIG[feature_manager.PRESET_MUSIC_PLAYER]["features"]
        self.assertTrue(mp_preset[feature_manager.FEATURE_GLOBAL_HOTKEYS])

        md_preset = feature_manager.PRESETS_CONFIG[feature_manager.PRESET_MUSIC_DISCOVERY]["features"]
        self.assertTrue(md_preset[feature_manager.FEATURE_GLOBAL_HOTKEYS])

        # Category should be Audio & Playback
        spec = feature_manager.FEATURE_REGISTRY[feature_manager.FEATURE_GLOBAL_HOTKEYS]
        self.assertEqual(spec["category"], feature_manager.CATEGORY_AUDIO)

    def test_audio_player_volume_shortcuts_work_when_unloaded(self):
        """Verify that volume up/down shortcuts adjust volume even when no track is currently loaded."""
        from audio_player_panel import AudioPlayerPanel

        class DummyMain(wx.Frame):
            def __init__(self):
                super().__init__(None)
                self.settings = {"enable_player_shortcuts": True, "volume": 50}
                self.video_frame = None
            def update_window_title(self, *args, **kwargs):
                pass
            def is_favorite(self, url):
                return False

        dummy = DummyMain()
        panel = AudioPlayerPanel(dummy, dummy)
        self.assertFalse(panel.is_loaded)

        panel.set_volume(70)
        self.assertEqual(panel.volume_slider.GetValue(), 70)
        self.assertEqual(dummy.settings["volume"], 70)

        dummy.Destroy()

    def test_bundled_vlc_initializes_without_system_vlc(self):
        """Verify that bundled VLC initializes properly even on machines without system-installed VLC."""
        import path_utils
        import ctypes.util
        import winreg

        orig_find_library = ctypes.util.find_library
        orig_openkey = winreg.OpenKey
        try:
            ctypes.util.find_library = lambda name: None
            winreg.OpenKey = lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("No VLC in registry"))

            # Ensure setup_vlc_environment correctly points to bundled VLC
            path_utils.setup_vlc_environment()
            self.assertIn("PYTHON_VLC_LIB_PATH", os.environ)
            self.assertTrue(os.path.exists(os.environ["PYTHON_VLC_LIB_PATH"]))

            import vlc
            instance = vlc.Instance("--no-xlib", "--quiet")
            self.assertIsNotNone(instance)
            instance.release()
        finally:
            ctypes.util.find_library = orig_find_library
            winreg.OpenKey = orig_openkey


if __name__ == '__main__':
    unittest.main()

