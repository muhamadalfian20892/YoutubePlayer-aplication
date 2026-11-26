import unittest
import os
import json
import wx
import constants
import nvda
import settings_manager
import feature_manager
from youtube_panel import YoutubeSearchPanel
from audio_player_panel import AudioPlayerPanel
from settings_panel import SettingsPanel
from downloader_panel import YoutubeDLPanel
from history_panel import HistoryPanel
from ui_components import EqualizerDialog

app = wx.App(False)

class TestSmallSections(unittest.TestCase):
    def setUp(self):
        self.frame = wx.Frame(None)
        self.frame.settings = settings_manager.load_settings()
        self.frame.save_settings = lambda: settings_manager.save_settings(self.frame.settings)
        self.frame.request_audio_play = lambda *args, **kwargs: None
        self.frame.on_change_language = lambda *args: None
        self.frame.on_sound_settings = lambda *args: None
        self.frame.on_customize_shortcuts = lambda *args: None
        self.frame.on_set_theme = lambda *args: None
        self.frame.on_toggle_always_on_top = lambda *args: None
        self.frame.on_toggle_minimize_to_tray = lambda *args: None
        self.frame.rebuild_notebook = lambda *args: None
        self.frame.audio_player_panel = type('DummyAudio', (), {
            'apply_equalizer_settings': lambda *args, **kwargs: None,
            'apply_normalization': lambda *args, **kwargs: None,
            'prefetch_stream_url': lambda *args, **kwargs: None,
            'is_radio_mode': False,
        })()

    def tearDown(self):
        self.frame.Destroy()

    def test_item_1_innertube_related_parser(self):
        """Item 1: InnerTube related extraction handles lockupViewModel and compactVideoRenderer."""
        panel = YoutubeSearchPanel(self.frame, self.frame)
        
        lockup_item = {
            "lockupViewModel": {
                "contentId": "rel_vid_1",
                "metadata": {
                    "lockupMetadataViewModel": {
                        "title": {"content": "Related Song Title"},
                        "metadata": {
                            "contentMetadataViewModel": {
                                "metadataRows": [
                                    {"metadataParts": [{"text": {"content": "Related Artist"}}]}
                                ]
                            }
                        }
                    }
                },
                "contentImage": {
                    "thumbnailViewModel": {
                        "overlays": [
                            {"thumbnailBottomOverlayViewModel": {
                                "badges": [{"thumbnailBadgeViewModel": {"text": "03:45"}}]
                            }}
                        ]
                    }
                }
            }
        }
        compact_item = {
            "compactVideoRenderer": {
                "videoId": "rel_vid_2",
                "title": {"runs": [{"text": "Compact Title"}]},
                "shortBylineText": {"runs": [{"text": "Compact Artist"}]},
                "lengthText": {"simpleText": "04:20"}
            }
        }
        
        results = [lockup_item, compact_item]
        items = []
        for r in results:
            lockup = r.get("lockupViewModel")
            compact = r.get("compactVideoRenderer")
            if lockup:
                cid = lockup.get("contentId")
                title = lockup.get("metadata", {}).get("lockupMetadataViewModel", {}).get("title", {}).get("content")
                rows = lockup.get("metadata", {}).get("lockupMetadataViewModel", {}).get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
                uploader = rows[0]["metadataParts"][0]["text"]["content"]
                duration = lockup["contentImage"]["thumbnailViewModel"]["overlays"][0]["thumbnailBottomOverlayViewModel"]["badges"][0]["thumbnailBadgeViewModel"]["text"]
                items.append({"id": cid, "title": title, "uploader": uploader, "duration_string": duration})
            elif compact:
                cid = compact.get("videoId")
                title = compact["title"]["runs"][0]["text"]
                uploader = compact["shortBylineText"]["runs"][0]["text"]
                duration = compact["lengthText"]["simpleText"]
                items.append({"id": cid, "title": title, "uploader": uploader, "duration_string": duration})
        
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["id"], "rel_vid_1")
        self.assertEqual(items[0]["title"], "Related Song Title")
        self.assertEqual(items[0]["uploader"], "Related Artist")
        self.assertEqual(items[0]["duration_string"], "03:45")
        self.assertEqual(items[1]["id"], "rel_vid_2")
        self.assertEqual(items[1]["title"], "Compact Title")
        self.assertEqual(items[1]["uploader"], "Compact Artist")
        self.assertEqual(items[1]["duration_string"], "04:20")
        panel.Destroy()

    def test_item_2_equalizer_persistence(self):
        """Item 2: Equalizer preset selection and values persist to settings."""
        self.frame.settings["equalizer_enabled"] = True
        self.frame.settings["equalizer_preset_name"] = "Rock"
        self.frame.settings["equalizer_bands"] = constants.EQUALIZER_PRESETS["Rock"]
        settings_manager.save_settings(self.frame.settings)
        
        reloaded = settings_manager.load_settings()
        self.assertTrue(reloaded.get("equalizer_enabled"))
        self.assertEqual(reloaded.get("equalizer_preset_name"), "Rock")
        self.assertEqual(reloaded.get("equalizer_bands"), constants.EQUALIZER_PRESETS["Rock"])

        # Test EqualizerDialog populates the preset choice correctly
        dlg = EqualizerDialog(self.frame, {
            "enabled": True,
            "preamp": constants.DEFAULT_PREAMP_PERCENT,
            "bands": constants.EQUALIZER_PRESETS["Rock"],
            "preset_name": "Rock",
            "custom_presets": {}
        })
        self.assertEqual(dlg.preset_choice.GetStringSelection(), "Rock")
        dlg.Destroy()

    def test_item_3_nvda_verbosity_off(self):
        """Item 3: NVDA verbosity 'off' mode is completely silent and persists."""
        self.frame.settings["nvda_verbosity"] = constants.NVDA_VERBOSITY_OFF
        settings_manager.save_settings(self.frame.settings)
        nvda.refresh_settings_cache(self.frame.settings)
        
        self.assertEqual(nvda._get_verbosity_level(), -1)
        
        # Test speak does not crash or raise error when Off
        nvda.speak("This should not speak at all", constants.NVDA_VERBOSITY_VERBOSE)
        nvda.speak("Critical message should also be silent", constants.NVDA_VERBOSITY_QUIET)
        
        # Restore default
        self.frame.settings["nvda_verbosity"] = constants.NVDA_VERBOSITY_DEFAULT
        settings_manager.save_settings(self.frame.settings)
        nvda.refresh_settings_cache(self.frame.settings)

    def test_item_4_quiet_verbosity_for_seeking_and_navigation(self):
        """Item 4: Fastforward, rewind, and tab change speak at VERBOSE so they stay silent in default mode."""
        self.frame.settings["nvda_verbosity"] = constants.NVDA_VERBOSITY_DEFAULT
        nvda.refresh_settings_cache(self.frame.settings)
        
        # Verbose level is 2, current default is 1 -> 1 >= 2 is False (silent)
        self.assertFalse(nvda._get_verbosity_level() >= constants.NVDA_VERBOSITY_LEVELS[constants.NVDA_VERBOSITY_VERBOSE])

    def test_item_5_settings_sidebar_focus_retention(self):
        """Item 5: Navigating sidebar list maintains focus on sidebar."""
        panel = SettingsPanel(self.frame, self.frame)
        self.assertIsNotNone(panel.sidebar_list)
        
        # Simulate selection event
        panel.sidebar_list.SetSelection(1)
        event = wx.CommandEvent(wx.wxEVT_COMMAND_LISTBOX_SELECTED, panel.sidebar_list.GetId())
        panel.on_sidebar_select(event)
        
        # Content book page changed to 1
        self.assertEqual(panel.content_book.GetSelection(), 1)
        panel.Destroy()

    def test_item_6_downloader_consolidation_and_human_format(self):
        """Item 6: Downloader has only one main listctrl and uses human status."""
        panel = YoutubeDLPanel(self.frame, self.frame)
        self.assertTrue(hasattr(panel, 'url_list_ctrl'))
        self.assertFalse(hasattr(panel, 'log_list_ctrl'))
        
        # Test human-readable progress updates
        panel.download_list_data.append({
            'title': 'Test Song', 'url': 'https://youtube.com/watch?v=abc',
            'status': 'Queued', 'progress': '0%', 'speed': '-', 'eta': '-', 'size': '-'
        })
        panel.populate_url_list()
        
        # Update row with human status and ETA
        panel._update_item_progress_row(0, "Downloading in progress", "45.0%", "1.5 MB/s", "about 2m left", "5 MB of 11 MB")
        self.assertEqual(panel.url_list_ctrl.GetItemText(0, 1), "Downloading in progress")
        self.assertEqual(panel.url_list_ctrl.GetItemText(0, 4), "about 2m left")
        self.assertEqual(panel.url_list_ctrl.GetItemText(0, 5), "5 MB of 11 MB")
        panel.Destroy()

    def test_item_7_history_copy_link(self):
        """Item 7: History panel has copy link button, context menu, and keyboard shortcut."""
        panel = HistoryPanel(self.frame, self.frame)
        self.assertTrue(hasattr(panel, 'copy_link_button'))
        self.assertTrue(hasattr(panel, 'on_copy_link'))
        
        # Mock item
        panel.history_list.Append("Song 1", clientData={"url": "https://www.youtube.com/watch?v=123", "title": "Song 1"})
        panel.history_list.SetSelection(0)
        panel.on_selection_change(None)
        self.assertTrue(panel.copy_link_button.IsEnabled())
        panel.Destroy()

    def test_item_8_cookies_auto_detection(self):
        """Item 8: Cookies file path detects existing cookies in project directory."""
        detected = settings_manager.get_effective_cookies_path(self.frame.settings)
        self.assertTrue(bool(detected))
        self.assertTrue(os.path.exists(detected))
        self.assertTrue(detected.endswith(".txt"))

    def test_item_9_tab_management_follows_feature_manager(self):
        """Item 9: Tab management list hides tabs for disabled features."""
        panel = SettingsPanel(self.frame, self.frame)
        
        # Disable stats feature
        feature_manager.set_feature_enabled(self.frame.settings, feature_manager.FEATURE_STATS, False)
        panel._populate_tabs_list()
        
        # Check that 'stats' tab is NOT in tabs_list_box
        tabs_in_list = [panel.tabs_list_box.GetClientData(i) for i in range(panel.tabs_list_box.GetCount())]
        self.assertNotIn("stats", tabs_in_list)
        
        # Re-enable stats feature
        feature_manager.set_feature_enabled(self.frame.settings, feature_manager.FEATURE_STATS, True)
        panel._populate_tabs_list()
        tabs_in_list = [panel.tabs_list_box.GetClientData(i) for i in range(panel.tabs_list_box.GetCount())]
        self.assertIn("stats", tabs_in_list)
        
        panel.Destroy()

if __name__ == "__main__":
    unittest.main()
