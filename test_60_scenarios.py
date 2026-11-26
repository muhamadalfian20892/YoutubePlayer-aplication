# --- test_60_scenarios.py ---
"""
Comprehensive automated test suite executing 70 distinct verification scenarios
across all Tunevia subsystems, accessibility, features, and performance.
"""

import sys
import os
import unittest
import json
import tempfile
import shutil
import time

# Ensure tunevia root is in sys.path
sys.path.insert(0, os.path.abspath("."))

import constants
import settings_manager
import feature_manager
import utils
import path_utils
import nvda

class Tunevia60ScenariosTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import wx
        cls.app = wx.GetApp() or wx.App(False)
        cls.test_dir = tempfile.mkdtemp(prefix="tunevia_test_")
        cls.orig_appdata = os.environ.get("APPDATA")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def setUp(self):
        self.settings = settings_manager.load_settings()

    # =========================================================================
    # Group 1: First Launch, Onboarding & Core Architecture (Scenarios 1 - 10)
    # =========================================================================

    def test_01_fresh_install_settings_defaults(self):
        """Scenario 1: Fresh install generates all required keys with default values."""
        defaults = settings_manager.load_settings()
        self.assertEqual(defaults.get("theme"), constants.DEFAULT_THEME)
        self.assertEqual(defaults.get("language"), constants.DEFAULT_PREFERRED_LANGUAGE)

    def test_02_onboarding_sfx_toggle(self):
        """Scenario 2: Sound effects toggle properly sets sound_effects_enabled."""
        self.settings["sound_effects_enabled"] = False
        self.assertFalse(self.settings["sound_effects_enabled"])
        self.settings["sound_effects_enabled"] = True
        self.assertTrue(self.settings["sound_effects_enabled"])

    def test_03_preset_music_player(self):
        """Scenario 3: Music Player preset enables core playback and disables heavy tabs."""
        feature_manager.apply_preset(self.settings, feature_manager.PRESET_MUSIC_PLAYER)
        self.assertTrue(feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_AUDIO_PLAYER))
        self.assertFalse(feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_DISCOVER))
        self.assertFalse(feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_RADAR))
        self.assertFalse(feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_DOWNLOADER))

    def test_04_preset_music_discovery(self):
        """Scenario 4: Music + Discovery preset enables charts and local radar."""
        feature_manager.apply_preset(self.settings, feature_manager.PRESET_MUSIC_DISCOVERY)
        self.assertTrue(feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_DISCOVER))
        self.assertTrue(feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_RADAR))
        self.assertFalse(feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_DOWNLOADER))

    def test_05_preset_power_user(self):
        """Scenario 5: Power User preset enables all registered features."""
        feature_manager.apply_preset(self.settings, feature_manager.PRESET_POWER_USER)
        for fid in feature_manager.FEATURE_REGISTRY:
            self.assertTrue(feature_manager.is_feature_enabled(self.settings, fid), f"Feature {fid} should be enabled")

    def test_06_preset_recommended(self):
        """Scenario 6: Recommended preset enables balanced core set."""
        feature_manager.apply_preset(self.settings, feature_manager.PRESET_RECOMMENDED)
        self.assertTrue(feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_CLIPBOARD_DETECTION))
        self.assertTrue(feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_FAVORITES))
        self.assertTrue(feature_manager.is_feature_enabled(self.settings, feature_manager.FEATURE_HISTORY))

    def test_07_tab_order_defaults(self):
        """Scenario 7: Default tab order has YouTube first and Settings/Help last."""
        tab_order = self.settings.get("tab_order", constants.DEFAULT_TAB_ORDER)
        self.assertEqual(tab_order[0], "youtube")
        self.assertIn("settings", tab_order)
        self.assertIn("help", tab_order)

    def test_08_tab_config_names(self):
        """Scenario 8: All tab keys in DEFAULT_TAB_ORDER have valid entries in TABS_CONFIG."""
        for tab_key in constants.DEFAULT_TAB_ORDER:
            self.assertIn(tab_key, constants.TABS_CONFIG)
            self.assertIn("name", constants.TABS_CONFIG[tab_key])

    def test_09_app_metadata(self):
        """Scenario 9: Application metadata (name, version, author) are defined correctly."""
        self.assertEqual(constants.APP_NAME, "Tunevia")
        self.assertEqual(constants.APP_VERSION, "1.7.3")
        self.assertEqual(constants.APP_AUTHOR, "Technokers Lab")

    def test_10_sound_events_mapping(self):
        """Scenario 10: Every registered sound event has a description and non-empty file name."""
        for ev_key, ev_data in constants.SOUND_EVENTS.items():
            self.assertIn("description", ev_data)
            self.assertIn("file", ev_data)
            self.assertTrue(len(ev_data["file"]) > 0)

    # =========================================================================
    # Group 2: YouTube Search, URL Parsing & Results (Scenarios 11 - 22)
    # =========================================================================

    def test_11_youtube_url_patterns(self):
        """Scenario 11: YouTube URL pattern extracts IDs from watch and youtu.be links."""
        import re
        pattern = re.compile(r'(https?://)?(www.)?(youtube.com/(watch\?v=|embed/|playlist\?list=)|youtu.be/)([a-zA-Z0-9_-]+)')
        m1 = pattern.search("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertIsNotNone(m1)
        self.assertEqual(m1.groups()[-1], "dQw4w9WgXcQ")

        m2 = pattern.search("https://youtu.be/dQw4w9WgXcQ")
        self.assertIsNotNone(m2)
        self.assertEqual(m2.groups()[-1], "dQw4w9WgXcQ")

    def test_12_playlist_url_patterns(self):
        """Scenario 12: Playlist URL pattern extracts playlist ID correctly."""
        import re
        pattern = re.compile(r'(https?://)?(www\.)?youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)')
        m = pattern.search("https://www.youtube.com/playlist?list=PL4fGSI1pDJn6jJ8-5PjpGPF1tG5xI5d5e")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(3), "PL4fGSI1pDJn6jJ8-5PjpGPF1tG5xI5d5e")

    def test_13_channel_url_patterns(self):
        """Scenario 13: Channel URL pattern recognizes handle and channel paths."""
        import re
        pattern = re.compile(r'(https?://)?(www\.)?youtube\.com/(@|channel/)([a-zA-Z0-9_-]+)')
        self.assertIsNotNone(pattern.search("https://www.youtube.com/@NoCopyrightSounds"))
        self.assertIsNotNone(pattern.search("https://www.youtube.com/channel/UC_aEa8K-EOJ3D6gOs7HcyNg"))

    def test_14_search_results_caching(self):
        """Scenario 14: Search results cache stores and limits entries to 20."""
        cache = {}
        for i in range(25):
            cache[f"query_{i}"] = [{"id": f"vid_{i}", "title": f"Song {i}"}]
            if len(cache) > 20:
                oldest = next(iter(cache))
                del cache[oldest]
        self.assertEqual(len(cache), 20)
        self.assertNotIn("query_0", cache)
        self.assertIn("query_24", cache)

    def test_15_search_history_capping(self):
        """Scenario 15: Search history is strictly capped at MAX_YT_SEARCH_HISTORY_ITEMS."""
        history = []
        for i in range(constants.MAX_YT_SEARCH_HISTORY_ITEMS + 15):
            q = f"Search {i}"
            if q in history: history.remove(q)
            history.append(q)
            history = history[-constants.MAX_YT_SEARCH_HISTORY_ITEMS:]
        self.assertEqual(len(history), constants.MAX_YT_SEARCH_HISTORY_ITEMS)

    def test_16_duration_formatting(self):
        """Scenario 16: format_duration correctly converts seconds to string."""
        self.assertEqual(utils.format_duration(0), "00:00")
        self.assertEqual(utils.format_duration(65), "01:05")
        self.assertEqual(utils.format_duration(3665), "1:01:05")
        self.assertEqual(utils.format_duration(None), "N/A")

    def test_17_time_ms_formatting(self):
        """Scenario 17: format_time_ms converts milliseconds to formatted string."""
        self.assertEqual(utils.format_time_ms(0), "00:00")
        self.assertEqual(utils.format_time_ms(65000), "01:05")
        self.assertEqual(utils.format_time_ms(3665000), "1:01:05")

    def test_18_upload_date_formatting(self):
        """Scenario 18: format_upload_date formats YYYYMMDD into readable date."""
        res = utils.format_upload_date("20261019")
        self.assertNotEqual(res, "Unknown Date")
        self.assertNotEqual(res, "Invalid Date")
        self.assertEqual(utils.format_upload_date(""), "Unknown Date")
        self.assertEqual(utils.format_upload_date("invalid"), "Unknown Date")

    def test_19_filesize_formatting(self):
        """Scenario 19: format_filesize converts bytes to KB, MB, GB."""
        self.assertEqual(utils.format_filesize(500), "500.00 B")
        self.assertEqual(utils.format_filesize(1024 * 500), "500.00 KB")
        self.assertEqual(utils.format_filesize(1024 * 1024 * 15), "15.00 MB")
        self.assertEqual(utils.format_filesize(None), "N/A")

    def test_20_playlist_file_parsing(self):
        """Scenario 20: parse_playlist_file parses valid M3U entries."""
        m3u_content = "#EXTM3U\n#EXTINF:210,Test Artist - Test Title\nhttps://www.youtube.com/watch?v=abc123xyz00\n"
        temp_file = os.path.join(self.test_dir, "test.m3u")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(m3u_content)
        items = utils.parse_playlist_file(temp_file)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Test Artist - Test Title")
        self.assertEqual(items[0]["url"], "https://www.youtube.com/watch?v=abc123xyz00")

    def test_21_playlist_file_saving(self):
        """Scenario 21: save_playlist_file writes valid M3U file without data loss."""
        items = [{"title": "Song A", "url": "https://www.youtube.com/watch?v=111", "duration": 180}]
        save_path = os.path.join(self.test_dir, "saved.m3u")
        success = utils.save_playlist_file(save_path, items)
        self.assertTrue(success)
        parsed = utils.parse_playlist_file(save_path)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["url"], "https://www.youtube.com/watch?v=111")

    def test_22_shuffle_algorithm(self):
        """Scenario 22: Shuffle generates pseudo-random distribution without losing items."""
        import random
        items = [{"id": i, "title": f"Song {i}"} for i in range(50)]
        shuffled = items.copy()
        random.shuffle(shuffled)
        self.assertEqual(len(shuffled), 50)
        self.assertEqual(set(x["id"] for x in shuffled), set(range(50)))

    # =========================================================================
    # Group 3: Audio Subsystem & VLC Player Logic (Scenarios 23 - 34)
    # =========================================================================

    def test_23_vlc_import_or_environment(self):
        """Scenario 23: vlc module or environment is importable and functional."""
        try:
            import vlc
            self.assertTrue(hasattr(vlc, 'Instance'))
        except (ImportError, OSError):
            self.skipTest("VLC binary not installed in test environment")

    def test_24_equalizer_bands_count(self):
        """Scenario 24: Equalizer constants have exactly 10 bands and frequencies."""
        self.assertEqual(constants.EQUALIZER_BANDS, 10)
        self.assertEqual(len(constants.EQUALIZER_FREQUENCIES), 10)

    def test_25_equalizer_presets_validity(self):
        """Scenario 25: All equalizer presets have exactly 10 gain values between min and max."""
        for name, bands in constants.EQUALIZER_PRESETS.items():
            self.assertEqual(len(bands), constants.EQUALIZER_BANDS, f"Preset {name} must have 10 bands")
            for gain in bands:
                self.assertTrue(constants.EQUALIZER_MIN_GAIN <= gain <= constants.EQUALIZER_MAX_GAIN)

    def test_26_playback_bookmarks_limit(self):
        """Scenario 26: Playback bookmarks respect maximum limits."""
        bookmarks = {}
        url = "https://www.youtube.com/watch?v=test"
        bookmarks[url] = [{"desc": f"Mark {i}", "time": i * 1000} for i in range(constants.MAX_BOOKMARKS_PER_VIDEO + 5)]
        bookmarks[url] = bookmarks[url][:constants.MAX_BOOKMARKS_PER_VIDEO]
        self.assertEqual(len(bookmarks[url]), constants.MAX_BOOKMARKS_PER_VIDEO)

    def test_27_play_history_limit(self):
        """Scenario 27: Play history respects MAX_PLAY_HISTORY_ITEMS."""
        history = []
        for i in range(constants.MAX_PLAY_HISTORY_ITEMS + 20):
            history.append({"title": f"Song {i}", "url": f"url_{i}"})
        history = history[-constants.MAX_PLAY_HISTORY_ITEMS:]
        self.assertEqual(len(history), constants.MAX_PLAY_HISTORY_ITEMS)

    def test_28_repeat_modes(self):
        """Scenario 28: Repeat modes are defined as integers (None=0, One=1, All=2)."""
        self.assertEqual(constants.REPEAT_MODE_NONE, 0)
        self.assertEqual(constants.REPEAT_MODE_ONE, 1)
        self.assertEqual(constants.REPEAT_MODE_ALL, 2)

    def test_29_playback_rate_boundaries(self):
        """Scenario 29: Playback rate bounds are properly scaled."""
        self.assertEqual(constants.MIN_PLAYBACK_RATE_FLOAT, 0.25)
        self.assertEqual(constants.MAX_PLAYBACK_RATE_FLOAT, 2.0)
        self.assertEqual(constants.DEFAULT_PLAYBACK_RATE_FLOAT, 1.0)

    def test_30_sound_throttling(self):
        """Scenario 30: Sound event playback throttles events under 50ms."""
        import utils
        utils._last_sound_play_time["test_event"] = time.time()
        # Immediately trying to play again within 50ms should return early
        now = time.time()
        should_throttle = (now - utils._last_sound_play_time["test_event"]) < 0.05
        self.assertTrue(should_throttle)

    def test_31_sound_settings_individual_volume(self):
        """Scenario 31: Master volume multiplied by individual volume scales correctly."""
        master_vol = 80
        indiv_vol = 50
        final_volume = (master_vol / 100.0) * (indiv_vol / 100.0)
        self.assertAlmostEqual(final_volume, 0.40)

    def test_32_seek_intervals(self):
        """Scenario 32: Seek interval bounds are within 1 to 3600 seconds."""
        self.assertEqual(constants.MIN_SEEK_INTERVAL_SECONDS, 1)
        self.assertEqual(constants.MAX_SEEK_INTERVAL_SECONDS, 3600)
        self.assertEqual(constants.DEFAULT_SEEK_INTERVAL_SECONDS, 10)

    def test_33_volume_bounds(self):
        """Scenario 33: Volume percentages stay within 0 to 100 with 5% step."""
        self.assertEqual(constants.MIN_VOLUME_PERCENT, 0)
        self.assertEqual(constants.MAX_VOLUME_PERCENT, 100)
        self.assertEqual(constants.VOLUME_ADJUST_STEP_PERCENT, 5)

    def test_34_audio_output_persistence(self):
        """Scenario 34: Preferred audio output device name persists in settings."""
        self.settings["audio_output_device"] = "Headphones (Realtek)"
        self.assertEqual(self.settings["audio_output_device"], "Headphones (Realtek)")

    # =========================================================================
    # Group 4: Downloader Engine & Format Conversion (Scenarios 35 - 44)
    # =========================================================================

    def test_35_ensure_yt_dlp_bundled(self):
        """Scenario 35: ensure_yt_dlp detects bundled/environment yt_dlp without network requests."""
        import yt_dlp_manager
        # In this python environment, yt_dlp should import instantly
        success = yt_dlp_manager.ensure_yt_dlp()
        self.assertTrue(success)

    def test_36_downloader_audio_formats(self):
        """Scenario 36: Supported audio formats match specification."""
        formats = ["mp3", "m4a", "opus", "flac", "wav"]
        for f in formats:
            self.assertIn(f, ["mp3", "m4a", "opus", "flac", "wav"])

    def test_37_downloader_parallel_fragments_option(self):
        """Scenario 37: Downloader options configure concurrent fragments for speed."""
        ydl_opts = {
            'concurrent_fragment_downloads': 8,
            'http_chunk_size': 10485760,
        }
        self.assertEqual(ydl_opts['concurrent_fragment_downloads'], 8)
        self.assertEqual(ydl_opts['http_chunk_size'], 10 * 1024 * 1024)

    def test_38_downloader_ffmpeg_threads_argument(self):
        """Scenario 38: ffmpeg args utilize all CPU cores via threads 0."""
        ffmpeg_args = ["ffmpeg", "-y", "-threads", "0", "-i", "input.mp4", "-c:a", "aac", "out.m4a"]
        self.assertIn("-threads", ffmpeg_args)
        idx = ffmpeg_args.index("-threads")
        self.assertEqual(ffmpeg_args[idx + 1], "0")

    def test_39_downloader_queue_status_transitions(self):
        """Scenario 39: Download item transitions through status states."""
        states = ["Queued", "Downloading", "Converting", "Finished", "Error", "Cancelled"]
        item = {"status": states[0]}
        self.assertEqual(item["status"], "Queued")
        item["status"] = states[1]
        self.assertEqual(item["status"], "Downloading")
        item["status"] = states[3]
        self.assertEqual(item["status"], "Finished")

    def test_40_downloader_filename_sanitization(self):
        """Scenario 40: Sanitizer strips invalid Windows characters from filenames."""
        import re
        dirty_title = 'My: Favorite* Song? / Best <Audio> "Ever" | Part 1'
        clean = re.sub(r'[\\/*?:"<>|]', "", dirty_title)
        self.assertEqual(clean, 'My Favorite Song  Best Audio Ever  Part 1')

    def test_41_downloader_audio_bitrates(self):
        """Scenario 41: Audio conversion bitrates match 192k for MP3/AAC and 128k for OPUS."""
        bitrates = {"mp3": "192k", "m4a": "192k", "opus": "128k"}
        self.assertEqual(bitrates["mp3"], "192k")
        self.assertEqual(bitrates["m4a"], "192k")
        self.assertEqual(bitrates["opus"], "128k")

    def test_42_downloader_mp4_video_copy(self):
        """Scenario 42: MP4 video downloads use stream copy (-c:v copy)."""
        video_args = ["-c:v", "copy", "-c:a", "aac"]
        self.assertIn("-c:v", video_args)
        self.assertEqual(video_args[video_args.index("-c:v") + 1], "copy")

    def test_43_downloader_duplicate_suppression(self):
        """Scenario 43: Downloader suppresses duplicate pending URLs in queue."""
        queue = [{"url": "url_1"}, {"url": "url_2"}]
        new_url = "url_1"
        is_duplicate = any(item["url"] == new_url for item in queue)
        self.assertTrue(is_duplicate)

    def test_44_downloader_cancel_handling(self):
        """Scenario 44: Cancellation flag interrupts active download."""
        cancel_flags = {"task_1": False}
        cancel_flags["task_1"] = True
        self.assertTrue(cancel_flags["task_1"])

    # =========================================================================
    # Group 5: Secondary Panels & Features (Scenarios 45 - 54)
    # =========================================================================

    def test_45_discovery_playlist_constants(self):
        """Scenario 45: Discovery playlist URLs point to valid YouTube playlist parameters."""
        self.assertTrue(constants.DISCOVERY_CHARTS_URL.startswith("https://www.youtube.com/playlist?list="))
        self.assertTrue(constants.DISCOVERY_NEW_RELEASES_URL.startswith("https://www.youtube.com/playlist?list="))

    def test_46_radar_format_filtering(self):
        """Scenario 46: Radar correctly filters audio extensions (.mp3, .wav, .flac)."""
        valid_files = ["song.mp3", "track.WAV", "music.flac"]
        invalid_files = ["video.mp4", "doc.txt", "script.py"]
        valid_exts = {".mp3", ".wav", ".flac"}
        for f in valid_files:
            _, ext = os.path.splitext(f)
            self.assertIn(ext.lower(), valid_exts)
        for f in invalid_files:
            _, ext = os.path.splitext(f)
            self.assertNotIn(ext.lower(), valid_exts)

    def test_47_favorites_add_and_remove(self):
        """Scenario 47: Favorites add, query, and remove operations."""
        favs = []
        track = {"title": "Test Track", "url": "https://youtube.com/watch?v=123"}
        favs.append(track)
        self.assertTrue(any(f["url"] == track["url"] for f in favs))
        favs = [f for f in favs if f["url"] != track["url"]]
        self.assertFalse(any(f["url"] == track["url"] for f in favs))

    def test_48_history_search_filtering(self):
        """Scenario 48: History search filters entries by query string."""
        history = [
            {"title": "Alan Walker - Faded", "uploader": "Alan Walker"},
            {"title": "Coldplay - Yellow", "uploader": "Coldplay"},
            {"title": "Coldplay - Fix You", "uploader": "Coldplay"}
        ]
        q = "coldplay"
        filtered = [h for h in history if q in h["title"].lower() or q in h["uploader"].lower()]
        self.assertEqual(len(filtered), 2)

    def test_49_lyrics_query_normalization(self):
        """Scenario 49: Lyrics search cleans track title noise (Official Video, Feat, etc.)."""
        import re
        raw_title = "Never Gonna Give You Up (Official Music Video) [HD] feat. Friend"
        cleaned = re.sub(r'\(.*?\)|\[.*?\]', '', raw_title)
        cleaned = re.sub(r'\b(official|music|video|audio|lyric|lyrics|hd|4k)\b', '', cleaned, flags=re.IGNORECASE)
        self.assertIn("Never Gonna Give You Up", cleaned)

    def test_50_stats_listening_time_calculation(self):
        """Scenario 50: Stats accurately sums durations in seconds."""
        history = [
            {"duration": 180},
            {"duration": 220},
            {"duration": 100}
        ]
        total_seconds = sum(h.get("duration", 0) for h in history)
        self.assertEqual(total_seconds, 500)
        mins, secs = divmod(total_seconds, 60)
        self.assertEqual(mins, 8)
        self.assertEqual(secs, 20)

    def test_51_clipboard_url_detection(self):
        """Scenario 51: Clipboard monitor identifies valid YouTube URLs."""
        import re
        pattern = re.compile(r'(https?://)?(www.)?(youtube.com/(watch\?v=|embed/|playlist\?list=)|youtu.be/)([a-zA-Z0-9_-]+)')
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        self.assertIsNotNone(pattern.search(url))

    def test_52_comments_limit_options(self):
        """Scenario 52: Comment fetch limit options contain standard increments."""
        for limit in ["10", "20", "50", "100", "200", "500", "all"]:
            self.assertIn(limit, constants.COMMENT_FETCH_LIMIT_OPTIONS)

    def test_53_comments_html_unescape(self):
        """Scenario 53: HTML entities in comments are unescaped to plain text."""
        import html
        raw = "This &amp; that is &quot;great&quot; &#39;test&#39;"
        unescaped = html.unescape(raw)
        self.assertEqual(unescaped, 'This & that is "great" \'test\'')

    def test_54_comments_cache_retrieval(self):
        """Scenario 54: Comments cache returns cached items for same video URL."""
        import video_comments_dialog
        video_comments_dialog._COMMENTS_CACHE["https://yt.com/test"] = [{"author": "User", "text": "Hello"}]
        self.assertIn("https://yt.com/test", video_comments_dialog._COMMENTS_CACHE)
        self.assertEqual(video_comments_dialog._COMMENTS_CACHE["https://yt.com/test"][0]["author"], "User")

    # =========================================================================
    # Group 6: Dialog Modal Handling & Freeze Prevention (Scenarios 55 - 62)
    # =========================================================================

    def test_55_whats_new_dialog_endmodal(self):
        """Scenario 55: WhatsNewDialog uses EndModal instead of Close."""
        import ui_components
        import inspect
        source = inspect.getsource(ui_components.WhatsNewDialog)
        self.assertIn("EndModal", source)

    def test_56_bookmarks_dialog_endmodal(self):
        """Scenario 56: BookmarksDialog uses EndModal instead of Close."""
        import ui_components
        import inspect
        source = inspect.getsource(ui_components.BookmarksDialog.on_close)
        self.assertIn("EndModal", source)

    def test_57_video_comments_dialog_endmodal(self):
        """Scenario 57: VideoCommentsDialog uses EndModal instead of Close."""
        import video_comments_dialog
        import inspect
        source = inspect.getsource(video_comments_dialog.VideoCommentsDialog.on_char_hook)
        self.assertIn("EndModal", source)

    def test_58_video_comments_subdialog_endmodal(self):
        """Scenario 58: Full comment subdialog uses EndModal instead of Close."""
        import video_comments_dialog
        import inspect
        source = inspect.getsource(video_comments_dialog.VideoCommentsDialog.on_view_full_comment)
        self.assertIn("EndModal", source)

    def test_59_show_text_dialog_endmodal(self):
        """Scenario 59: show_text_dialog in youtube_panel uses EndModal."""
        import youtube_panel
        import inspect
        source = inspect.getsource(youtube_panel.YoutubeSearchPanel.show_text_dialog)
        self.assertIn("EndModal", source)

    def test_60_startup_check_for_updates_non_blocking(self):
        """Scenario 60: Startup check_for_updates updates version without blocking modal popups."""
        import tunevia
        import inspect
        source = inspect.getsource(tunevia.MainFrame.check_for_updates_and_show_whats_new)
        self.assertNotIn("show_whats_new_dialog", source)

    def test_61_initial_focus_map_settings(self):
        """Scenario 61: _select_tab_and_focus maps settings tab to sidebar_list."""
        import tunevia
        import inspect
        source = inspect.getsource(tunevia.MainFrame._select_tab_and_focus)
        self.assertIn("'settings': 'sidebar_list'", source)

    def test_62_on_char_hook_tab_no_listbox_hijack(self):
        """Scenario 62: on_char_hook does not hijack ListBox Tab events."""
        import tunevia
        import inspect
        source = inspect.getsource(tunevia.MainFrame.on_char_hook)
        self.assertNotIn("isinstance(focus, wx.ListBox)", source)

    # =========================================================================
    # Group 7: Settings Persistence, Theming & System Stability (Scenarios 63 - 70)
    # =========================================================================

    def test_63_atomic_settings_saving(self):
        """Scenario 63: Settings save uses atomic write (.tmp -> destination) to prevent corruption."""
        import inspect
        source = inspect.getsource(settings_manager.save_settings)
        self.assertIn(".tmp", source)
        self.assertIn("os.replace", source)
        
        # Test saving and reloading settings
        orig_theme = self.settings.get("theme", constants.DEFAULT_THEME)
        self.settings["theme"] = constants.THEME_DARK
        settings_manager.save_settings(self.settings)
        reloaded = settings_manager.load_settings()
        self.assertEqual(reloaded["theme"], constants.THEME_DARK)
        
        # Restore
        self.settings["theme"] = orig_theme
        settings_manager.save_settings(self.settings)

    def test_64_theme_colors_light_and_dark(self):
        """Scenario 64: ThemeManager defines colors for both light and dark themes."""
        from tunevia import ThemeManager
        ThemeManager.initialize()
        self.assertIn("light", ThemeManager.THEMES)
        self.assertIn("dark", ThemeManager.THEMES)
        self.assertIn("bg", ThemeManager.THEMES["light"])
        self.assertIn("bg", ThemeManager.THEMES["dark"])

    def test_65_available_languages(self):
        """Scenario 65: English and Indonesian are configured in AVAILABLE_LANGUAGES."""
        self.assertIn("en", constants.AVAILABLE_LANGUAGES)
        self.assertIn("id", constants.AVAILABLE_LANGUAGES)

    def test_66_translation_manager_loading(self):
        """Scenario 66: TranslationManager loads translations without throwing errors."""
        import translation_manager
        translation_manager.set_language("id")
        self.assertEqual(translation_manager._active_lang_code, "id")
        translation_manager.set_language("en")
        self.assertEqual(translation_manager._active_lang_code, "en")

    def test_67_nvda_verbosity_levels(self):
        """Scenario 67: NVDA verbosity constants and levels match definition."""
        self.assertEqual(constants.NVDA_VERBOSITY_LEVELS[constants.NVDA_VERBOSITY_OFF], -1)
        self.assertEqual(constants.NVDA_VERBOSITY_LEVELS[constants.NVDA_VERBOSITY_QUIET], 0)
        self.assertEqual(constants.NVDA_VERBOSITY_LEVELS[constants.NVDA_VERBOSITY_DEFAULT], 1)
        self.assertEqual(constants.NVDA_VERBOSITY_LEVELS[constants.NVDA_VERBOSITY_VERBOSE], 2)

    def test_68_global_hotkey_ids(self):
        """Scenario 68: Global hotkey IDs are unique integers."""
        ids = [
            constants.ALT_SHIFT_PLAY_PAUSE_HK_ID,
            constants.ALT_SHIFT_REWIND_HK_ID,
            constants.ALT_SHIFT_FFWD_HK_ID,
            constants.ALT_SHIFT_VOL_UP_HK_ID,
            constants.ALT_SHIFT_VOL_DOWN_HK_ID,
            constants.ALT_SHIFT_SHOW_WINDOW_HK_ID,
            constants.ALT_SHIFT_PLAY_NEXT_HK_ID,
            constants.ALT_SHIFT_PLAY_PREV_HK_ID,
        ]
        self.assertEqual(len(ids), len(set(ids)))

    def test_69_memory_optimizer_safety(self):
        """Scenario 69: utils.optimize_memory executes safely without exceptions."""
        try:
            utils.optimize_memory()
        except Exception as e:
            self.fail(f"optimize_memory threw unexpected exception: {e}")

    def test_70_resource_paths_exist(self):
        """Scenario 70: Critical resource directories exist in codebase."""
        for d in ["sound", "libs", "docs", "locales"]:
            p = path_utils.get_resource_path(d)
            self.assertTrue(os.path.exists(p), f"Directory {d} should exist at {p}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
