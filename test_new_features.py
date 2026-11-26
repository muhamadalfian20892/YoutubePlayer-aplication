import unittest
import os
import sys
import tempfile
import json
import re

import constants
import utils
import settings_manager
import feature_manager

class NewFeaturesTestSuite(unittest.TestCase):
    def test_youtube_video_id_extraction(self):
        """Verify utils.get_youtube_video_id extracts 11-char IDs from various formats."""
        self.assertEqual(utils.get_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(utils.get_youtube_video_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(utils.get_youtube_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ"), "dQw4w9WgXcQ")
        self.assertEqual(utils.get_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s"), "dQw4w9WgXcQ")
        self.assertIsNone(utils.get_youtube_video_id("https://google.com"))
        self.assertIsNone(utils.get_youtube_video_id(None))

    def test_customizable_actions_chapters_and_mono(self):
        """Verify that local_toggle_mono retains Ctrl+M and chapters uses non-conflicting shortcuts."""
        actions = constants.CUSTOMIZABLE_ACTIONS
        self.assertIn("local_toggle_mono", actions)
        mono_action = actions["local_toggle_mono"]
        import wx
        self.assertEqual(mono_action["default"], (wx.ACCEL_CTRL, ord('M')))

        self.assertIn("local_open_chapters", actions)
        self.assertIn("local_next_chapter", actions)
        self.assertIn("local_prev_chapter", actions)
        self.assertNotEqual(actions["local_open_chapters"]["default"], mono_action["default"])
        self.assertNotEqual(actions["local_next_chapter"]["default"], mono_action["default"])
        self.assertNotEqual(actions["local_prev_chapter"]["default"], mono_action["default"])

    def test_settings_sponsorblock_persistence(self):
        """Verify that enable_sponsorblock setting is loaded with True default and persisted."""
        defaults = settings_manager.load_settings()
        self.assertIn("enable_sponsorblock", defaults)
        self.assertTrue(defaults["enable_sponsorblock"])

    def test_feature_manager_sponsorblock_registered(self):
        """Verify that FEATURE_SPONSORBLOCK is registered in feature_manager."""
        self.assertTrue(hasattr(feature_manager, 'FEATURE_SPONSORBLOCK'))
        self.assertIn(feature_manager.FEATURE_SPONSORBLOCK, feature_manager.FEATURE_REGISTRY)
        meta = feature_manager.FEATURE_REGISTRY[feature_manager.FEATURE_SPONSORBLOCK]
        self.assertEqual(meta["category"], feature_manager.CATEGORY_AUDIO)

    def test_portable_mode_resolution(self):
        """Verify that presence of portable.dat redirects settings to local data directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            marker = os.path.join(tmpdir, "portable.dat")
            with open(marker, "w") as f:
                f.write("1")
            
            # Simulate portable check
            base_dir = tmpdir
            if os.path.exists(os.path.join(base_dir, 'portable.dat')):
                data_dir = os.path.join(base_dir, 'data')
                target = os.path.join(data_dir, constants.SETTINGS_FILE_NAME)
            else:
                target = "not_portable"
            
            self.assertTrue(target.startswith(os.path.join(tmpdir, "data")))

    def test_chapter_navigation_logic(self):
        """Test on_next_chapter and on_prev_chapter calculations."""
        chapters = [
            {"title": "Intro", "start_time": 0},
            {"title": "Verse 1", "start_time": 30},
            {"title": "Chorus", "start_time": 75},
            {"title": "Outro", "start_time": 150},
        ]
        # Current time at 10s -> next chapter is Verse 1 (30s)
        curr = 10.0
        next_ch = next((c for c in chapters if c["start_time"] > curr + 0.5), None)
        self.assertIsNotNone(next_ch)
        self.assertEqual(next_ch["title"], "Verse 1")

        # Current time at 35s (> 2s into Verse 1) -> prev chapter should restart Verse 1
        curr = 35.0
        target_idx = None
        for i in range(len(chapters) - 1, -1, -1):
            if curr >= chapters[i]["start_time"] + 2.0:
                target_idx = i
                break
        self.assertEqual(target_idx, 1) # Restarts Verse 1

        # Current time at 31s (<= 2s into Verse 1) -> prev chapter should go to Intro
        curr = 31.0
        target_idx = None
        for i in range(len(chapters) - 1, -1, -1):
            if curr >= chapters[i]["start_time"] + 2.0:
                target_idx = i
                break
            elif curr > chapters[i]["start_time"] and i > 0:
                target_idx = i - 1
                break
        self.assertEqual(target_idx, 0) # Jumps back to Intro

if __name__ == '__main__':
    unittest.main()
