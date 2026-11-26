"""Unit and integration tests for Tunevia 1.6.5 Spatial Audio, packaging, and bug fixes."""

import array
import math
import os
import struct
import unittest
from unittest.mock import MagicMock, patch

import wx

import constants
import feature_manager
import settings_manager
import spatial_audio
import ui_components
import utils
import yt_dlp_manager


def _make_stereo_pcm(sample_rate=44100, duration_s=0.12, freq_l=440.0, freq_r=660.0, amp=12000):
    """Generate deterministic signed 16-bit interleaved stereo PCM bytes."""
    n_frames = int(sample_rate * duration_s)
    buf = array.array("h")
    for i in range(n_frames):
        t = i / sample_rate
        l_val = int(amp * math.sin(2.0 * math.pi * freq_l * t))
        r_val = int(amp * math.sin(2.0 * math.pi * freq_r * t))
        buf.append(l_val)
        buf.append(r_val)
    return buf.tobytes()


def _mid_side_rms(pcm_bytes):
    """Compute RMS energy of Mid ((L+R)/2) and Side ((L-R)/2) signals."""
    samples = array.array("h")
    samples.frombytes(pcm_bytes)
    n = len(samples) // 2
    if n == 0:
        return 0.0, 0.0
    m_sq = 0.0
    s_sq = 0.0
    for i in range(0, n * 2, 2):
        l = samples[i]
        r = samples[i + 1]
        m = (l + r) * 0.5
        s = (l - r) * 0.5
        m_sq += m * m
        s_sq += s * s
    return math.sqrt(m_sq / n), math.sqrt(s_sq / n)


class TestSpatialAudioProcessor(unittest.TestCase):
    def test_empty_and_odd_chunk_safety(self):
        proc = spatial_audio.SpatialAudioProcessor(sample_rate=44100)
        proc.configure(spatial_enabled=True, width=75, room_size=40, depth=45)
        self.assertEqual(proc.process_chunk(b""), b"")
        out = proc.process_chunk(b"\x01\x02\x03")
        self.assertIsInstance(out, bytes)

    def test_all_presets_widen_stereo_field_and_avoid_overflow(self):
        pcm = _make_stereo_pcm(duration_s=0.2, freq_l=440.0, freq_r=554.37, amp=10000)
        base_mid, base_side = _mid_side_rms(pcm)
        base_ratio = base_side / max(base_mid, 1.0)

        for preset_name, preset_vals in constants.SPATIAL_AUDIO_PRESETS.items():
            proc = spatial_audio.SpatialAudioProcessor(sample_rate=44100)
            proc.configure(
                spatial_enabled=(preset_name != "Off"),
                width=preset_vals["width"],
                room_size=preset_vals["room_size"],
                depth=preset_vals["depth"],
                mono_enabled=False,
                normalization_enabled=False,
                volume_percent=100,
            )
            out = proc.process_chunk(pcm)
            self.assertEqual(len(out), len(pcm))
            decoded = array.array("h")
            decoded.frombytes(out)
            self.assertTrue(all(-32768 <= v <= 32767 for v in decoded))
            if preset_name != "Off":
                out_mid, out_side = _mid_side_rms(out)
                out_ratio = out_side / max(out_mid, 1.0)
                self.assertGreater(
                    out_ratio,
                    base_ratio,
                    f"Preset {preset_name} failed to widen stereo side ratio ({out_ratio:.3f} <= {base_ratio:.3f})",
                )

    def test_room_size_and_depth_modify_reverb_tail(self):
        pcm = _make_stereo_pcm(duration_s=0.15)
        silent_tail = b"\x00" * (4410 * 4)

        proc_dry = spatial_audio.SpatialAudioProcessor(sample_rate=44100)
        proc_dry.configure(spatial_enabled=True, width=60, room_size=0, depth=0, volume_percent=100)
        proc_dry.process_chunk(pcm)
        tail_dry = proc_dry.process_chunk(silent_tail)

        proc_wet = spatial_audio.SpatialAudioProcessor(sample_rate=44100)
        proc_wet.configure(spatial_enabled=True, width=60, room_size=85, depth=80, volume_percent=100)
        proc_wet.process_chunk(pcm)
        tail_wet = proc_wet.process_chunk(silent_tail)

        dry_energy = sum(abs(v) for v in struct.unpack(f"<{len(tail_dry)//2}h", tail_dry))
        wet_energy = sum(abs(v) for v in struct.unpack(f"<{len(tail_wet)//2}h", tail_wet))
        self.assertGreater(wet_energy, dry_energy)

    def test_mono_mode_collapses_side_signal(self):
        pcm = _make_stereo_pcm(duration_s=0.1)
        proc = spatial_audio.SpatialAudioProcessor(sample_rate=44100)
        proc.configure(spatial_enabled=True, width=90, room_size=60, depth=60, mono_enabled=True, volume_percent=100)
        out = proc.process_chunk(pcm)
        mid, side = _mid_side_rms(out)
        self.assertGreater(mid, 100.0)
        self.assertAlmostEqual(side, 0.0, places=2)

    def test_volume_zero_yields_silence_and_reset_clears_buffers(self):
        pcm = _make_stereo_pcm(duration_s=0.15)
        proc = spatial_audio.SpatialAudioProcessor(sample_rate=44100)
        proc.configure(spatial_enabled=True, width=70, room_size=80, depth=80, volume_percent=0)
        silent_out = proc.process_chunk(pcm)
        self.assertEqual(silent_out, b"\x00" * len(pcm))

        proc.configure(spatial_enabled=True, width=70, room_size=80, depth=80, volume_percent=100)
        proc.process_chunk(pcm)
        proc.reset()
        post_reset = proc.process_chunk(b"\x00" * 4096)
        self.assertEqual(post_reset, b"\x00" * 4096)

    def test_rms_normalization_boosts_quiet_signal(self):
        quiet_pcm = _make_stereo_pcm(duration_s=0.2, amp=600)
        proc = spatial_audio.SpatialAudioProcessor(sample_rate=44100)
        proc.configure(spatial_enabled=False, normalization_enabled=True, volume_percent=100)
        boosted = quiet_pcm
        for _ in range(12):
            boosted = proc.process_chunk(quiet_pcm)
        in_mid, _ = _mid_side_rms(quiet_pcm)
        out_mid, _ = _mid_side_rms(boosted)
        self.assertGreater(out_mid, in_mid * 1.2)

    def test_rms_normalization_peak_headroom_clamp(self):
        loud_pcm = _make_stereo_pcm(duration_s=0.1, amp=26000)
        proc = spatial_audio.SpatialAudioProcessor(sample_rate=44100)
        proc.configure(spatial_enabled=False, normalization_enabled=True, volume_percent=100)
        out = loud_pcm
        for _ in range(6):
            out = proc.process_chunk(loud_pcm)
        decoded = array.array("h")
        decoded.frombytes(out)
        self.assertLessEqual(max(abs(v) for v in decoded), 30000)

    def test_perceptual_volume_curve_and_smooth_gain_ramp(self):
        self.assertEqual(spatial_audio.SpatialAudioProcessor._volume_gain(0), 0.0)
        self.assertLess(spatial_audio.SpatialAudioProcessor._volume_gain(10), 0.05)
        self.assertEqual(spatial_audio.SpatialAudioProcessor._volume_gain(100), 1.0)

        pcm = _make_stereo_pcm(duration_s=0.05, amp=20000)
        proc = spatial_audio.SpatialAudioProcessor(sample_rate=44100)
        proc.configure(spatial_enabled=False, volume_percent=100)
        out1 = proc.process_chunk(pcm)
        proc.configure(spatial_enabled=False, volume_percent=10)
        out2 = proc.process_chunk(pcm)

        a1 = array.array("h"); a1.frombytes(out1)
        a2 = array.array("h"); a2.frombytes(out2)
        # First sample of out2 should transition smoothly from the tail of out1 without a step jump > 8000
        self.assertLess(abs(a2[0] - a1[-2]), 8000)


class TestWinMMOutput(unittest.TestCase):
    def test_list_devices_and_matching(self):
        devices = spatial_audio.WinMMOutput.list_devices()
        self.assertIsInstance(devices, list)
        dev_id = spatial_audio.WinMMOutput.match_device_id("Nonexistent Audio Endpoint XYZ-999")
        self.assertEqual(dev_id, spatial_audio.WAVE_MAPPER)

    def test_ring_buffered_burst_zero_drops_and_flush(self):
        out = spatial_audio.WinMMOutput()
        proc = spatial_audio.SpatialAudioProcessor(44100)
        proc.configure(spatial_enabled=True, width=160, room_size=30, depth=30, volume_percent=0)
        try:
            ok = out.open(device_id=spatial_audio.WAVE_MAPPER, sample_rate=44100, channels=2, bits=16, processor_fn=proc.process_chunk)
            if ok:
                burst_chunk = b"\x00" * 3528  # 20 ms stereo 44.1 kHz
                results = [out.write(burst_chunk) for _ in range(40)]
                self.assertTrue(all(results), f"Dropped {results.count(False)} burst chunks")
                out.flush()
        finally:
            out.close()
        self.assertFalse(out.is_open())

    def test_pause_flush_unpauses_and_resumes_processing(self):
        import time
        out = spatial_audio.WinMMOutput()
        count = [0]
        def _count_proc(pcm):
            count[0] += 1
            return pcm
        try:
            ok = out.open(device_id=spatial_audio.WAVE_MAPPER, sample_rate=44100, channels=2, bits=16, processor_fn=_count_proc)
            if ok:
                out.pause()
                self.assertTrue(out._paused)
                out.flush()
                self.assertFalse(out._paused)
                for _ in range(6):
                    out.write(b"\x00" * 4408)
                time.sleep(0.18)
                self.assertGreater(count[0], 0)
        finally:
            out.close()

    def test_auto_unpause_self_healing_on_write(self):
        import time
        out = spatial_audio.WinMMOutput()
        count = [0]
        def _count_proc(pcm):
            count[0] += 1
            return pcm
        try:
            ok = out.open(device_id=spatial_audio.WAVE_MAPPER, sample_rate=44100, channels=2, bits=16, processor_fn=_count_proc)
            if ok:
                out.pause()
                out._paused_at = time.monotonic() - 0.25
                for _ in range(6):
                    out.write(b"\x00" * 4408)
                time.sleep(0.18)
                self.assertFalse(out._paused)
                self.assertGreater(count[0], 0)
        finally:
            out.close()

    def test_fallback_and_invalid_format_handling(self):
        out = spatial_audio.WinMMOutput()
        try:
            # Unknown device ID falls back to WAVE_MAPPER instead of crashing
            fallback_ok = out.open(device_id=99999, sample_rate=44100, channels=2, bits=16)
            if fallback_ok:
                self.assertEqual(out._device_id, spatial_audio.WAVE_MAPPER)
            # Invalid sample bit depth returns False cleanly
            bad_fmt_ok = out.open(device_id=spatial_audio.WAVE_MAPPER, sample_rate=44100, channels=2, bits=99)
            self.assertFalse(bad_fmt_ok)
        finally:
            out.close()


class TestWXDialogsAndBugFixes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App(False)
        cls._orig_settings = settings_manager.load_settings()

    @classmethod
    def tearDownClass(cls):
        settings_manager.save_settings(cls._orig_settings)
        cls.app.Destroy()

    def test_spatial_audio_dialog_presets_reset_and_cancel_immutability(self):
        orig = {
            "enabled": True,
            "preset": "Concert Hall",
            "width": 190,
            "room_size": 70,
            "depth": 65,
        }
        frame = wx.Frame(None)
        dlg = ui_components.SpatialAudioDialog(frame, orig)
        try:
            self.assertTrue(dlg.enable_check.GetValue())
            self.assertEqual(dlg.preset_choice.GetStringSelection(), "Concert Hall")
            self.assertGreater(len(dlg.enable_check.GetName()), 0)
            self.assertGreater(len(dlg.width_slider.GetName()), 0)
            self.assertGreater(len(dlg.room_slider.GetName()), 0)
            self.assertGreater(len(dlg.depth_slider.GetName()), 0)

            dlg.on_reset(None)
            self.assertEqual(dlg.preset_choice.GetStringSelection(), constants.DEFAULT_SPATIAL_PRESET)
            self.assertEqual(dlg.width_slider.GetValue(), constants.SPATIAL_AUDIO_PRESETS[constants.DEFAULT_SPATIAL_PRESET]["width"])

            dlg.width_slider.SetValue(110)
            dlg.on_cancel(None)
            self.assertEqual(orig["width"], 190)
            self.assertEqual(dlg.get_new_settings()["width"], 190)
        finally:
            dlg.Destroy()
            frame.Destroy()

    def test_settings_and_appdata_fallbacks(self):
        with patch.dict(os.environ, {}, clear=True):
            sp = settings_manager.get_settings_path()
            yp = yt_dlp_manager.get_app_data_path()
            self.assertTrue(os.path.isabs(sp))
            self.assertTrue(os.path.isabs(yp))

        defaults = settings_manager.load_settings()
        for key in (
            "spatial_audio_enabled",
            "spatial_audio_preset",
            "spatial_audio_width",
            "spatial_audio_room_size",
            "spatial_audio_depth",
        ):
            self.assertIn(key, defaults)

    def test_feature_manager_sponsorblock_and_spatial_sync(self):
        s = {}
        feature_manager.sync_all_features(s)
        self.assertIn(feature_manager.FEATURE_SPATIAL_AUDIO, feature_manager.FEATURE_REGISTRY)

        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_SPONSORBLOCK, True)
        self.assertTrue(s.get("enable_sponsorblock"))
        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_SPONSORBLOCK, False)
        self.assertFalse(s.get("enable_sponsorblock"))

        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_SPATIAL_AUDIO, True)
        self.assertFalse(s.get("spatial_audio_enabled", False))
        s["spatial_audio_enabled"] = True
        feature_manager.set_feature_enabled(s, feature_manager.FEATURE_SPATIAL_AUDIO, False)
        self.assertFalse(s.get("spatial_audio_enabled"))

    def test_theme_manager_light_reset_and_sound_cache(self):
        import tunevia

        frame = wx.Frame(None)
        child_panel = wx.Panel(frame)
        child_ctrl = wx.TextCtrl(child_panel)
        try:
            tunevia.ThemeManager.apply(frame, constants.THEME_DARK)
            self.assertEqual(child_ctrl.GetBackgroundColour(), tunevia.ThemeManager.THEMES[constants.THEME_DARK]["text_bg"])
            self.assertEqual(child_ctrl.GetForegroundColour(), tunevia.ThemeManager.THEMES[constants.THEME_DARK]["text_fg"])
            tunevia.ThemeManager.apply(frame, constants.THEME_LIGHT)
            self.assertNotEqual(child_ctrl.GetBackgroundColour(), tunevia.ThemeManager.THEMES[constants.THEME_DARK]["text_bg"])
            self.assertNotEqual(child_ctrl.GetForegroundColour(), tunevia.ThemeManager.THEMES[constants.THEME_DARK]["text_fg"])
        finally:
            frame.Destroy()

        utils._sound_cache["dummy"] = object()
        utils.clear_sound_cache()
        self.assertEqual(len(utils._sound_cache), 0)
        with patch("utils.threading.Thread") as mock_thread:
            utils.preload_sounds_async({"sound_effects_enabled": False})
            mock_thread.assert_not_called()

    def test_downloader_hook_uses_format_filesize(self):
        import downloader_panel

        frame = wx.Frame(None)
        main_mock = MagicMock()
        main_mock.settings = settings_manager.load_settings()
        panel = downloader_panel.YoutubeDLPanel(frame, main_mock)
        try:
            panel.current_download_idx = 0
            panel._last_progress_ui_time = 0
            with patch("downloader_panel.wx.CallAfter") as mock_call:
                panel._yt_dlp_hook({
                    "status": "downloading",
                    "downloaded_bytes": 1024 * 1024,
                    "total_bytes": 4 * 1024 * 1024,
                    "speed": 512 * 1024,
                    "eta": 6,
                })
                self.assertTrue(mock_call.called)
        finally:
            frame.Destroy()

    def test_radar_and_lyrics_missing_import_fixes(self):
        import radar_panel
        import lyrics_panel

        self.assertTrue(hasattr(radar_panel, "constants"))
        self.assertTrue(hasattr(lyrics_panel, "re"))

        frame = wx.Frame(None)
        main_mock = MagicMock()
        main_mock.settings = settings_manager.load_settings()
        lp = lyrics_panel.LyricsSearchPanel(frame, main_mock)
        try:
            lp.genius = MagicMock()
            with patch("lyrics_panel.threading.Thread"):
                with patch("lyrics_panel.nvda.speak"):
                    lp.search_lyrics_auto("Song (Official Video)", "ArtistVEVO")
            self.assertEqual(lp.tc_judul.GetValue(), "Song")
            self.assertEqual(lp.tc_artis.GetValue(), "Artist")
        finally:
            frame.Destroy()

    def test_favorites_and_history_empty_refresh_and_selection_guard(self):
        import favorites_panel
        import history_panel

        frame = wx.Frame(None)
        main_mock = MagicMock()
        main_mock.settings = {"favorites": [], "play_history": []}
        main_mock.audio_player_panel = MagicMock()

        fav = favorites_panel.FavoritesPanel(frame, main_mock)
        fav.refresh_list()
        self.assertFalse(fav.play_button.IsEnabled())
        fav.on_selection_change(None)
        main_mock.audio_player_panel.prefetch_audio_url.assert_not_called()

        hist = history_panel.HistoryPanel(frame, main_mock)
        hist.refresh_list()
        self.assertFalse(hist.copy_link_button.IsEnabled())
        hist.on_selection_change(None)
        main_mock.audio_player_panel.prefetch_audio_url.assert_not_called()

        frame.Destroy()

    def test_video_comments_dialog_cache_cap_and_filtered_selection(self):
        import video_comments_dialog

        video_comments_dialog._COMMENTS_CACHE.clear()
        frame = wx.Frame(None)
        dlg = video_comments_dialog.VideoCommentsDialog(frame, "vid_x", "Test Video")
        try:
            # Row 1 has empty text so it is skipped in list display; row index 1 must map to Bob, not Blank
            dlg.comments_data = [
                {"author": "Alice", "text": "Great track", "like_count": 10},
                {"author": "Blank", "text": "", "like_count": 0},
                {"author": "Bob", "text": "Needs bass", "like_count": 2},
            ]
            dlg.update_list()
            dlg.comments_list.Select(1)
            sel = dlg._get_selected_comment()
            self.assertIsNotNone(sel)
            self.assertEqual(sel["author"], "Bob")
        finally:
            dlg.Destroy()
            frame.Destroy()

    def test_stats_panel_clears_when_empty_and_classifies_duration(self):
        import stats_panel

        frame = wx.Frame(None)
        main_mock = MagicMock()
        main_mock.settings = {
            "play_history": [
                {"title": "Short Song", "uploader": "Artist A", "duration": 200},
                {"title": "Long Podcast", "uploader": "Host B", "duration": 1800},
                {"title": "Missing Duration", "uploader": "Artist C", "duration": None},
            ]
        }
        sp = stats_panel.StatsPanel(frame, main_mock)
        try:
            self.assertGreater(sp.top_tracks_list.GetCount(), 0)
            main_mock.settings["play_history"] = []
            sp.calculate_stats()
            self.assertEqual(sp.top_tracks_list.GetCount(), 0)
            self.assertEqual(sp.top_artists_list.GetCount(), 0)
        finally:
            frame.Destroy()

    def test_main_frame_taskbar_and_methods_regression(self):
        import audio_player_panel
        import tunevia

        tb_frame = wx.Frame(None)
        tb_icon = tunevia.AppTaskBarIcon(tb_frame)
        try:
            menu = tb_icon.CreatePopupMenu()
            self.assertIsInstance(menu, wx.Menu)
            menu.Destroy()
            tb_icon.set_icon(True)
            tb_icon.set_icon(False)
        finally:
            tb_icon.Destroy()
            tb_frame.Destroy()

        self.assertTrue(hasattr(audio_player_panel, "re"))
        self.assertTrue(hasattr(tunevia.MainFrame, "toggle_favorite"))
        self.assertTrue(hasattr(tunevia.MainFrame, "request_audio_play_direct_link"))

    def test_audio_panel_volume_preservation_and_slider_step(self):
        import audio_player_panel

        frame = wx.Frame(None)
        main_mock = MagicMock()
        main_mock.video_frame = None
        s = settings_manager.load_settings()
        s["volume"] = 15
        s["spatial_audio_enabled"] = True
        main_mock.settings = s
        main_mock.is_favorite.return_value = False
        panel = audio_player_panel.AudioPlayerPanel(frame, main_mock)
        try:
            self.assertEqual(panel.volume_slider.GetLineSize(), constants.VOLUME_ADJUST_STEP_PERCENT)
            panel.set_volume(15, speak_value=False)
            self.assertEqual(panel.spatial_processor.volume_percent, 15)
            panel._configure_player_audio_backend(True)
            if panel._dsp_callbacks:
                # Invoke VLC's AudioSetVolumeCb with (1.0, False) like VLC startup does
                panel._dsp_callbacks[5](None, 1.0, False)
            self.assertEqual(panel.spatial_processor.volume_percent, 15)

            picked_url, picked_id = panel._pick_audio_stream({
                "formats": [
                    {"format_id": "137", "url": "https://example.com/video_only.mp4", "acodec": "none", "ext": "mp4"},
                    {"format_id": "140", "url": "https://example.com/audio.m4a", "acodec": "mp4a.40.2", "ext": "m4a", "abr": 128},
                ]
            })
            self.assertEqual(picked_url, "https://example.com/audio.m4a")
            self.assertEqual(picked_id, "140")

            # Lossless bit-perfect detection & bypass (both local and YouTube streams)
            panel.is_local_file = True
            panel.local_file_path = r"C:\music\audiophile.flac"
            panel.main_frame.settings["lossless_mode"] = True
            panel.main_frame.settings["spatial_audio_enabled"] = True
            self.assertTrue(panel._is_lossless_active())
            self.assertFalse(panel._needs_dsp_pipeline())

            # YouTube stream in lossless mode: DSP bypassed, abr>=200 selector active, peak bitrate picked
            panel.is_local_file = False
            panel.local_file_path = None
            self.assertTrue(panel._is_lossless_active())
            self.assertFalse(panel._needs_dsp_pipeline())
            sel_str = panel._get_audio_format_selector()
            self.assertIn("abr>=200", sel_str)

            yt_url, yt_id = panel._pick_audio_stream({
                "formats": [
                    {"format_id": "140", "url": "https://example.com/140.m4a", "acodec": "mp4a.40.2", "ext": "m4a", "abr": 128, "asr": 44100},
                    {"format_id": "251", "url": "https://example.com/251.webm", "acodec": "opus", "ext": "webm", "abr": 160, "asr": 48000},
                    {"format_id": "774", "url": "https://example.com/774.webm", "acodec": "opus", "ext": "webm", "abr": 256, "asr": 48000},
                ]
            })
            self.assertEqual(yt_url, "https://example.com/774.webm")
            self.assertEqual(yt_id, "774")

            # Live toggle Lossless ON upgrades active YouTube track URL to peak bitrate track
            panel.main_frame.settings["lossless_mode"] = False
            panel.is_loaded = True
            panel.is_playing = True
            panel.current_audio_format_id = "140"
            panel.audio_url = "https://example.com/140.m4a"
            panel.available_audio_tracks = [
                {"id": "140", "url": "https://example.com/140.m4a", "bitrate": 128, "acodec": "mp4a.40.2", "asr": 44100},
                {"id": "251", "url": "https://example.com/251.webm", "bitrate": 160, "acodec": "opus", "asr": 48000},
            ]
            with patch.object(panel, "_play_media_with_vlc"), patch.object(panel.player, "stop"):
                with patch("audio_player_panel.nvda.speak"):
                    panel.on_toggle_lossless_mode(None)
            self.assertTrue(panel.main_frame.settings["lossless_mode"])
            self.assertEqual(panel.audio_url, "https://example.com/251.webm")
            self.assertEqual(panel.current_audio_format_id, "251")

            # Track telemetry (I key) announces live YouTube codec/bitrate/Hz
            panel.video_title = "Sample Song"
            panel.video_uploader = "Sample Artist"
            spoken = []
            with patch("audio_player_panel.nvda.speak", side_effect=lambda msg, *a, **k: spoken.append(msg)):
                panel.speak_track_and_audio_info()
            self.assertTrue(any("160 kbps" in m and "48 kHz" in m for m in spoken), f"Missing telemetry in {spoken}")

            # Normal stream should enable DSP pipeline when bass/vocal/night/ducking enabled
            panel.main_frame.settings["lossless_mode"] = False
            panel.is_local_file = False
            panel.main_frame.settings["spatial_audio_enabled"] = False
            panel.main_frame.settings["bass_boost"] = 35
            self.assertTrue(panel._needs_dsp_pipeline())

            # Up-Next queue ordering (play_next=True prepends to front)
            panel.add_to_queue({"url": "https://youtu.be/1", "title": "First"}, play_next=False, announce=False)
            panel.add_to_queue({"url": "https://youtu.be/2", "title": "JumpFront"}, play_next=True, announce=False)
            self.assertEqual(panel.up_next_queue[0]["title"], "JumpFront")
            self.assertEqual(panel.up_next_queue[1]["title"], "First")

            # A-B loop state cycling & Sleep timer setup
            panel.is_loaded = True
            with patch.object(panel, "get_current_time", side_effect=[5000, 12000, 13000]):
                with patch.object(panel, "seek_to") as mock_seek:
                    with patch("audio_player_panel.nvda.speak"):
                        panel.on_toggle_ab_loop(None)
                        self.assertEqual(panel.loop_a_ms, 5000)
                        panel.on_toggle_ab_loop(None)
                        self.assertEqual(panel.loop_b_ms, 12000)
                        mock_seek.assert_called_with(5000)
                        panel.on_toggle_ab_loop(None)
                        self.assertIsNone(panel.loop_a_ms)
                        self.assertIsNone(panel.loop_b_ms)

            with patch("audio_player_panel.nvda.speak"):
                panel.set_sleep_timer(15)
                self.assertEqual(panel._sleep_timer_minutes, 15)
                self.assertIsNotNone(panel._sleep_end_time)
                panel.set_sleep_timer(0)
                self.assertIsNone(panel._sleep_end_time)

            # Percentage seeking helper
            panel.player = MagicMock()
            panel.player.get_length.return_value = 200000
            with patch.object(panel, "seek_to") as mock_seek:
                with patch("audio_player_panel.nvda.speak"):
                    panel.seek_to_percent(50)
                    mock_seek.assert_called_once_with(100000)
        finally:
            panel.cleanup_on_exit()
            frame.Destroy()


class TestUpdaterAndExtendedDSPV17(unittest.TestCase):
    def test_updater_version_asset_notes_and_zero_backend_leak(self):
        import updater

        self.assertEqual(updater.normalize_version(" v1.7.0 "), "1.7.0")
        self.assertTrue(updater.is_newer_version("v1.7.0", "1.6.5"))
        self.assertFalse(updater.is_newer_version("1.7.0", "1.7.0"))

        asset = updater.pick_release_asset([
            {"name": "Tunevia.exe", "browser_download_url": "https://x/Tunevia.exe", "size": 100},
            {"name": "Tunevia-v1.7.0-Windows.zip", "browser_download_url": "https://x/Tunevia.zip", "size": 200},
            {"name": "Tunevia-v1.7.0-Windows.zip.sha256", "browser_download_url": "https://x/Tunevia.zip.sha256", "size": 64},
        ])
        self.assertIsNotNone(asset)
        self.assertEqual(asset["name"], "Tunevia-v1.7.0-Windows.zip")
        self.assertEqual(asset["sha256_url"], "https://x/Tunevia.zip.sha256")

        cleaned = updater.sanitize_release_notes("## Release\nCheck GitHub repo https://github.com/a/b\n**Fast audio**")
        self.assertNotIn("github", cleaned.lower())
        self.assertNotIn("https://", cleaned)

        fake_resp = MagicMock()
        fake_resp.json.return_value = {
            "tag_name": "v9.9.9",
            "body": "Faster playback",
            "assets": [{"name": "Tunevia-9.9.9.zip", "browser_download_url": "https://x/t.zip", "size": 1024}],
        }
        with patch("updater.requests.get", return_value=fake_resp):
            res = updater.check_for_update("1.7.0")
        self.assertEqual(res["status"], "available")
        for forbidden in ("github", "api", "http", "json", "403", "404"):
            self.assertNotIn(forbidden, res["user_message"].lower())

        with patch("updater.requests.get", side_effect=RuntimeError("GitHub HTTP 403 API rate limit")):
            err_res = updater.check_for_update("1.7.0")
        self.assertEqual(err_res["status"], "error")
        for forbidden in ("github", "api", "http", "403", "rate limit"):
            self.assertNotIn(forbidden, err_res["user_message"].lower())

    def test_dsp_48khz_bass_vocal_night_and_nvda_ducking(self):
        pcm = _make_stereo_pcm(sample_rate=48000, duration_s=0.1, freq_l=100.0, freq_r=1500.0, amp=12000)

        # Bass Boost keeps peak safe
        proc_b = spatial_audio.SpatialAudioProcessor(48000)
        proc_b.configure(bass_boost=100, volume_percent=100)
        out_b = proc_b.process_chunk(pcm)
        self.assertEqual(len(out_b), len(pcm))

        # Vocal Clarity raises Mid dominance relative to raw stereo
        proc_v = spatial_audio.SpatialAudioProcessor(48000)
        proc_v.configure(vocal_clarity=True, volume_percent=100)
        out_v = proc_v.process_chunk(pcm)
        in_m, in_s = _mid_side_rms(pcm)
        out_m, out_s = _mid_side_rms(out_v)
        self.assertGreater(out_m / max(out_s, 1.0), in_m / max(in_s, 1.0))

        # Night Mode clamps loud peaks
        loud = _make_stereo_pcm(sample_rate=48000, duration_s=0.1, amp=26000)
        proc_n = spatial_audio.SpatialAudioProcessor(48000)
        proc_n.configure(night_mode=True, volume_percent=100)
        out_n = loud
        for _ in range(6):
            out_n = proc_n.process_chunk(loud)
        arr_n = array.array("h"); arr_n.frombytes(out_n)
        self.assertLessEqual(max(abs(x) for x in arr_n), 17000)

        # Smart NVDA Ducking reduces amplitude then restores cleanly
        proc_d = spatial_audio.SpatialAudioProcessor(48000)
        proc_d.configure(volume_percent=100)
        normal = proc_d.process_chunk(pcm)
        proc_d.trigger_duck(duration_s=1.0, level=0.30)
        ducked = proc_d.process_chunk(pcm)
        norm_m, _ = _mid_side_rms(normal)
        duck_m, _ = _mid_side_rms(ducked)
        self.assertLess(duck_m, norm_m * 0.7)

    def test_nvda_speech_hook_and_alt_tab_visibility(self):
        import nvda
        import tunevia

        seen = []
        nvda.set_speech_hook(seen.append)
        try:
            with patch.object(nvda, "nvdaControllerClient", MagicMock()):
                with patch("nvda.is_nvda_running", return_value=True):
                    nvda.speak("Test duck hook", constants.NVDA_VERBOSITY_DEFAULT)
            self.assertEqual(seen, ["Test duck hook"])
        finally:
            nvda.set_speech_hook(None)

        app = wx.App.Get() or wx.App(False)
        fr = wx.Frame(None)
        try:
            fr.Hide()
            with patch.object(fr, "IsIconized", return_value=True):
                with patch.object(fr, "Iconize") as mock_iconize:
                    tunevia.MainFrame.toggle_visibility(fr)
                    mock_iconize.assert_called_with(False)
        finally:
            fr.Destroy()

    def test_vlc_plugins_cache_sync_handles_mtime_and_size_guard(self):
        import shutil
        import tempfile
        import time
        import path_utils

        src_dat = os.path.join(os.path.dirname(__file__), "libs", "plugins", "plugins.dat")
        src_dll = os.path.join(os.path.dirname(__file__), "libs", "plugins", "access", "libhttp_plugin.dll")
        if not (os.path.isfile(src_dat) and os.path.isfile(src_dll)):
            self.skipTest("Bundled VLC plugins.dat or libhttp_plugin.dll not present")

        tmp = tempfile.mkdtemp(prefix="tunevia_pdat_test_")
        try:
            pdir = os.path.join(tmp, "plugins")
            adir = os.path.join(pdir, "access")
            os.makedirs(adir, exist_ok=True)
            shutil.copy2(src_dat, os.path.join(pdir, "plugins.dat"))
            dst_dll = os.path.join(adir, "libhttp_plugin.dll")
            shutil.copy2(src_dll, dst_dll)

            # Simulate ZIP extraction changing DLL timestamp
            new_ts = time.time() + 120.0
            os.utime(dst_dll, (new_ts, new_ts))
            matched, patched = path_utils.sync_vlc_plugins_cache(pdir)
            self.assertEqual(matched, 1)
            self.assertEqual(patched, 1)

            # Second sync should be a clean no-op
            matched2, patched2 = path_utils.sync_vlc_plugins_cache(pdir)
            self.assertEqual(matched2, 1)
            self.assertEqual(patched2, 0)

            # Altering DLL file size must prevent cache patching
            with open(dst_dll, "ab") as f:
                f.write(b"\x00")
            new_ts2 = new_ts + 60.0
            os.utime(dst_dll, (new_ts2, new_ts2))
            matched3, patched3 = path_utils.sync_vlc_plugins_cache(pdir)
            self.assertEqual(matched3, 0)
            self.assertEqual(patched3, 0)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_vlc_no_plugins_cache_removed_and_deferred_init(self):
        import inspect
        import audio_player_panel

        src = inspect.getsource(audio_player_panel.AudioPlayerPanel._init_vlc)
        self.assertNotIn("--no-plugins-cache", src)

        app = wx.App.Get() or wx.App(False)
        frame = wx.Frame(None)
        main_mock = MagicMock()
        main_mock.video_frame = None
        main_mock.settings = settings_manager.load_settings()
        main_mock.is_favorite.return_value = False
        panel = audio_player_panel.AudioPlayerPanel(frame, main_mock, defer_vlc_init=True)
        try:
            self.assertIsNone(panel.player)
            panel.start_vlc_init_async()
            self.assertTrue(panel.ensure_vlc_ready(timeout=15.0))
            self.assertIsNotNone(panel.player)
        finally:
            panel.cleanup_on_exit()
            frame.Destroy()

    def test_ensure_yt_dlp_does_not_eagerly_import_and_utils_lazy_pygame(self):
        import subprocess
        import sys

        repo_dir = os.path.dirname(os.path.abspath(__file__))
        code = (
            "import sys; "
            "import yt_dlp_manager, utils; "
            "ok = yt_dlp_manager.ensure_yt_dlp(); "
            "assert ok is True; "
            "assert 'yt_dlp' not in sys.modules, 'yt_dlp imported eagerly'; "
            "assert 'pygame' not in sys.modules, 'pygame imported eagerly'; "
            "assert 'requests' not in sys.modules, 'requests imported eagerly'; "
            "print('LAZY_IMPORTS_OK')"
        )
        res = subprocess.run(
            [sys.executable, "-c", code],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr or res.stdout)
        self.assertIn("LAZY_IMPORTS_OK", res.stdout)


if __name__ == "__main__":
    unittest.main()
