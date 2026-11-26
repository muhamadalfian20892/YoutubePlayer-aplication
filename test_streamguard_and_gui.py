# --- test_streamguard_and_gui.py ---
"""
Automated unit tests validating:
1. YouTube Panel GUI navigation & screen reader accessibility fix.
2. StreamGuard: Resilient Playback & Longform Video Engine in AudioPlayerPanel.
"""

import sys
import os
import unittest
import time
import wx

sys.path.insert(0, os.path.abspath("."))

import constants
import settings_manager
import feature_manager
import youtube_panel
import audio_player_panel

class StreamGuardAndGuiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.GetApp()
        if not cls.app:
            cls.app = wx.App(False)

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        self.frame = wx.Frame(None)
        class DummyMainFrame:
            settings = settings_manager.load_settings()
            video_frame = None
            taskbar_icon = None
            def update_window_title(self, *args, **kwargs): pass
            def is_favorite(self, url): return False
            def add_to_play_history(self, *args, **kwargs): pass
            def request_lyrics_fetch(self, *args, **kwargs): pass
            def request_radio_next(self, *args, **kwargs): pass
            def request_audio_play(self, *args, **kwargs): pass
            def Close(self): pass
        self.main_frame = DummyMainFrame()
        self.frame.main_frame = self.main_frame

    def tearDown(self):
        if hasattr(self, 'frame') and self.frame:
            self.frame.Destroy()

    def test_youtube_panel_tab_navigation_forward(self):
        """Verify that pressing TAB on search_input, results_list, and related_videos_list navigates forward smoothly."""
        feature_manager.set_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_PLAYLISTS, True)
        yt_panel = youtube_panel.YoutubeSearchPanel(self.frame, self.main_frame)
        self.frame.Show()

        yt_panel.search_input.SetFocus()
        chain = []
        cur = yt_panel.search_input

        for _ in range(7):
            focused = wx.Window.FindFocus()
            chain.append(focused.GetName())
            # Simulate Tab navigation
            flags = wx.NavigationKeyEvent.IsForward
            focused.Navigate(flags)

        expected_elements = ["Search YouTube", "Playlist", "Search Results", "Related Videos", "Exit Application"]
        for elem in expected_elements:
            self.assertIn(elem, chain, f"{elem} should be reachable during forward Tab traversal")

    def test_youtube_panel_tab_navigation_backward(self):
        """Verify that pressing Shift+Tab navigates backward seamlessly through all controls."""
        yt_panel = youtube_panel.YoutubeSearchPanel(self.frame, self.main_frame)
        self.frame.Show()

        yt_panel.search_input.SetFocus()
        chain = []
        cur = yt_panel.search_input

        for _ in range(6):
            focused = wx.Window.FindFocus()
            chain.append(focused.GetName())
            # Simulate Shift+Tab navigation
            flags = wx.NavigationKeyEvent.IsBackward
            focused.Navigate(flags)

        self.assertIn("Exit Application", chain)
        self.assertIn("Related Videos", chain)
        self.assertIn("Search Results", chain)

    def test_smartseek_debouncer_and_position_tracking(self):
        """Verify that rapid seeks accumulate target positions and debounce low-level VLC calls."""
        player_panel = audio_player_panel.AudioPlayerPanel(self.frame, self.main_frame)
        player_panel.is_loaded = True
        player_panel.video_url = "https://www.youtube.com/watch?v=dummy"
        player_panel._last_valid_pos_ms = 60000 # 1 minute in
        player_panel._last_known_length_ms = 3600000 # 1 hour longform video

        # Single tap: seeks immediately with zero latency
        player_panel.seek_by(10000)
        self.assertEqual(player_panel._last_valid_pos_ms, 70000)
        self.assertTrue(player_panel._is_seeking)

        # Rapid subsequent taps within burst window: debounces hardware call and accumulates target
        player_panel.seek_by(10000)
        self.assertEqual(player_panel._pending_seek_pos, 80000)

        player_panel.seek_by(10000)
        self.assertEqual(player_panel._pending_seek_pos, 90000)

        # Status text should reflect the new target timestamp immediately
        self.assertIn("01:30", player_panel.status_message)

    def test_instant_play_pause_state_toggle(self):
        """Verify play/pause toggles UI state and timer immediately without waiting for async VLC callbacks."""
        player_panel = audio_player_panel.AudioPlayerPanel(self.frame, self.main_frame)
        player_panel.is_loaded = True
        player_panel.is_playing = True
        player_panel.play_pause_button.SetLabel("Pause")

        # Pause toggle: should immediately flip state, label, and update status
        player_panel.on_play_pause(None)
        self.assertFalse(player_panel.is_playing)
        self.assertEqual(player_panel.play_pause_button.GetLabel(), "Play")
        self.assertEqual(player_panel.status_message, "Paused")

        # Resume toggle: should immediately flip back
        player_panel.on_play_pause(None)
        self.assertTrue(player_panel.is_playing)
        self.assertEqual(player_panel.play_pause_button.GetLabel(), "Pause")
        self.assertEqual(player_panel.status_message, "Playing")

    def test_streamguard_premature_eof_interception(self):
        """Verify that StreamGuard prevents premature MediaPlayerEndReached from killing playback."""
        player_panel = audio_player_panel.AudioPlayerPanel(self.frame, self.main_frame)
        player_panel.is_loaded = True
        player_panel.video_url = "https://www.youtube.com/watch?v=dummy_longform"
        player_panel.audio_url = "https://rr1---sn-dummy.googlevideo.com/videoplayback"
        player_panel._last_valid_pos_ms = 1800000 # 30 minutes into a 2-hour video
        player_panel._last_known_length_ms = 7200000 # 2 hours
        player_panel._last_seek_time = time.time() # recent seek occurred

        recovered_called = []
        def mock_recover_stream(target_pos):
            recovered_called.append(target_pos)
        player_panel._recover_stream = mock_recover_stream

        # Simulate premature VLC EOF event
        player_panel.vlc_on_finished(None)

        # StreamGuard MUST intercept and trigger recovery instead of marking playback as finished
        self.assertEqual(len(recovered_called), 1)
        self.assertEqual(recovered_called[0], 1800000)
        self.assertFalse(player_panel.is_finished)

    def test_turbostream_stream_caching_and_instant_hit(self):
        """Verify that TurboStream cache returns direct stream instantly on load_and_play."""
        player_panel = audio_player_panel.AudioPlayerPanel(self.frame, self.main_frame)
        dummy_url = "https://www.youtube.com/watch?v=turbostream_test"
        stream_data = {
            'audio_url': 'https://rr2---sn-dummy.googlevideo.com/faststream.m4a',
            'chapters': [{'title': 'Intro', 'start_time': 0}],
            'upload_date': '20261023',
            'formats': [{'format_id': '140', 'url': 'https://rr2---sn-dummy.googlevideo.com/faststream.m4a', 'acodec': 'mp4a.40.2'}]
        }
        player_panel.cache_stream_info(dummy_url, stream_data)

        # Cache retrieval verification
        cached = player_panel.get_cached_stream_info(dummy_url)
        self.assertIsNotNone(cached)
        self.assertEqual(cached['audio_url'], stream_data['audio_url'])

        # Mock playback to verify instant launch
        played = []
        player_panel._play_media_with_vlc = lambda req_id: played.append(req_id)
        player_panel.load_and_play(dummy_url, "Turbo Title", "Turbo Artist")

        # Instant hit should immediately assign audio_url and call _play_media_with_vlc without thread wait
        self.assertEqual(player_panel.audio_url, stream_data['audio_url'])
        self.assertEqual(len(played), 1)
        self.assertEqual(len(player_panel.chapters), 1)

    def test_turbostream_base_ydl_opts_optimization(self):
        """Verify that extractor_args is configured with android client and webpage skip to prevent 403 errors and speed up extraction."""
        player_panel = audio_player_panel.AudioPlayerPanel(self.frame, self.main_frame)
        opts = player_panel._get_base_ydl_opts()

        self.assertIn('extractor_args', opts)
        self.assertEqual(opts['extractor_args']['youtube']['player_client'], ['android'])
        self.assertIn('webpage', opts['extractor_args']['youtube']['player_skip'])
        self.assertTrue(opts.get('noplaylist'))
        self.assertFalse(opts.get('check_formats'))
        self.assertEqual(opts.get('socket_timeout'), 6)

    def test_youtube_panel_prefetch_trigger_on_selection(self):
        """Verify that selecting an item in YouTube search results schedules predictive prefetching."""
        yt_panel = youtube_panel.YoutubeSearchPanel(self.frame, self.main_frame)
        target_video_url = "https://www.youtube.com/watch?v=prefetch_test"

        yt_panel._trigger_prefetch_for_url(target_video_url)
        self.assertEqual(yt_panel._pending_prefetch_url, target_video_url)
        self.assertTrue(yt_panel.prefetch_timer.IsRunning())

        # Simulate timer firing
        prefetched = []
        dummy_player = type('DummyPlayer', (), {'prefetch_stream_url': lambda self, u: prefetched.append(u)})()
        self.main_frame.audio_player_panel = dummy_player

        yt_panel._on_prefetch_timer(None)
        self.assertIn(target_video_url, prefetched)
        self.assertIsNone(yt_panel._pending_prefetch_url)

if __name__ == "__main__":
    unittest.main()
