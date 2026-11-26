#--- START OF FILE constants.py ---

import wx

# --- Application Details ---
APP_NAME = "Tunevia"
APP_AUTHOR = "Technokers Lab"
APP_VERSION = "1.7.0"

# --- App Update Endpoints (internal only; never expose to user UI) ---
UPDATE_RELEASE_API_URL = "https://api.github.com/repos/muhamadalfian20892/YoutubePlayer-aplication/releases/latest"
UPDATE_RELEASES_PAGE_URL = "https://github.com/muhamadalfian20892/YoutubePlayer-aplication/releases/latest"

# --- File Names ---
SETTINGS_FILE_NAME = "youtube_player_settings.json"
README_FILE_NAME = "readme.txt"
CHANGELOG_FILE_NAME = "changelog.txt"

# --- Sound Files ---
NOTIFICATION_SOUND_FILE = "notification_complete_Load.mp3"
UI_CLICK_SOUND_FILE = "ui-click.mp3"
STARTUP_SOUND_FILE = "startup.mp3"
RADIO_START_SOUND_FILE = "radio_enable.wav"
BOOKMARK_ADD_SOUND_FILE = "bookmark-add.mp3"
DOWNLOAD_ITEM_COMPLETE_SOUND_FILE = "download-complete.mp3"
ERROR_SOUND_FILE = "error.wav"
TAB_NAV_SOUND_FILE = "tab_navigation.wav"
POPUP_SOUND_FILE = "Hover Options.wav"
POPUP_NAV_SOUND_FILE = "hover_navigation.wav"
CLICK_SOUND_FILE = "click.wav"
CONFIRM_SOUND_FILE = "Confirm.wav"

# --- Sound Events Mapping ---
# The 'description' values are the message IDs used for translation in the Sound Settings dialog.
SOUND_EVENTS = {
    "app_startup": { "description": "Application startup", "file": STARTUP_SOUND_FILE },
    "load_complete": { "description": "Audio stream loaded successfully", "file": NOTIFICATION_SOUND_FILE },
    "list_navigate": { "description": "Navigating items in lists (search results, history)", "file": UI_CLICK_SOUND_FILE },
    "radio_start": { "description": "Radio mode starts", "file": RADIO_START_SOUND_FILE },
    "bookmark_added": { "description": "Bookmark added to a track", "file": BOOKMARK_ADD_SOUND_FILE },
    "download_item_complete": { "description": "A single download item finishes", "file": DOWNLOAD_ITEM_COMPLETE_SOUND_FILE },
    "error": { "description": "Error occurred", "file": ERROR_SOUND_FILE },
    "tab_navigation": { "description": "Switching between tabs", "file": TAB_NAV_SOUND_FILE },
    "popup_open": { "description": "Popup or dialog opens", "file": POPUP_SOUND_FILE },
    "popup_navigate": { "description": "Navigating within a popup", "file": POPUP_NAV_SOUND_FILE },
    "click": { "description": "Any click action", "file": CLICK_SOUND_FILE },
    "confirm_prompt": { "description": "Confirmation (Yes/No) prompt", "file": CONFIRM_SOUND_FILE },
}

# --- Music Discovery ---
DISCOVERY_CHARTS_URL = "https://www.youtube.com/playlist?list=PL4fGSI1pDJn6jJ8-5PjpGPF1tG5xI5d5e" # Top 100 Songs Global
DISCOVERY_NEW_RELEASES_URL = "https://www.youtube.com/playlist?list=PL4fGSI1pDJn5kI81J1dP15Uuk7wReDkVl" # New Music Friday

# --- Language and Translation ---
DEFAULT_PREFERRED_LANGUAGE = "en"
AVAILABLE_LANGUAGES = {
    "en": "English",
    "id": "Bahasa Indonesia",
}

# --- UI & THEMES ---
THEME_LIGHT = "light"
THEME_DARK = "dark"
DEFAULT_THEME = THEME_LIGHT

# --- NVDA Verbosity ---
NVDA_VERBOSITY_OFF = "off"
NVDA_VERBOSITY_QUIET = "quiet"
NVDA_VERBOSITY_DEFAULT = "default"
NVDA_VERBOSITY_VERBOSE = "verbose"
DEFAULT_NVDA_VERBOSITY = NVDA_VERBOSITY_DEFAULT
NVDA_VERBOSITY_LEVELS = {
    NVDA_VERBOSITY_OFF: -1,
    NVDA_VERBOSITY_QUIET: 0,
    NVDA_VERBOSITY_DEFAULT: 1,
    NVDA_VERBOSITY_VERBOSE: 2
}

# --- Configuration Values ---
DEFAULT_SEEK_INTERVAL_SECONDS = 10
MIN_SEEK_INTERVAL_SECONDS = 1
MAX_SEEK_INTERVAL_SECONDS = 3600
DEFAULT_VOLUME_PERCENT = 100
MIN_VOLUME_PERCENT = 0
MAX_VOLUME_PERCENT = 100
VOLUME_ADJUST_STEP_PERCENT = 5
MAX_SEARCH_RESULTS = 10000
INITIAL_RESULTS_PER_PAGE = 50
RESULTS_PER_PAGE_INCREMENT = 50
MAX_PLAY_HISTORY_ITEMS = 100
MAX_SAVED_POSITIONS = 200
MAX_YT_SEARCH_HISTORY_ITEMS = 50
DEFAULT_COMMENT_FETCH_LIMIT = 20
COMMENT_FETCH_LIMIT_OPTIONS = ["10", "20", "50", "100", "200", "500", "all"]

# --- Playback Rate Slider Constants ---
MIN_RATE_SLIDER = 25
MAX_RATE_SLIDER = 200
DEFAULT_RATE_SLIDER = 100
RATE_SLIDER_STEP = 5
MIN_PLAYBACK_RATE_FLOAT = MIN_RATE_SLIDER / 100.0
MAX_PLAYBACK_RATE_FLOAT = MAX_RATE_SLIDER / 100.0
DEFAULT_PLAYBACK_RATE_FLOAT = DEFAULT_RATE_SLIDER / 100.0

# --- Playback Modes ---
REPEAT_MODE_NONE = 0
REPEAT_MODE_ONE = 1
REPEAT_MODE_ALL = 2

# --- Audio Processing ---
EQUALIZER_BANDS = 10
EQUALIZER_FREQUENCIES = [60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000]
EQUALIZER_MIN_GAIN = -20.0
EQUALIZER_MAX_GAIN = 20.0
EQUALIZER_PRESETS = {
    "Flat": [0.0] * EQUALIZER_BANDS, "Rock": [5.0, 3.0, -2.0, -4.0, -1.0, 2.0, 4.0, 5.0, 6.0, 7.0],
    "Pop": [-1.0, 2.0, 4.0, 5.0, 3.0, -1.0, -2.0, -2.0, -1.0, 0.0], "Jazz": [4.0, 2.0, -2.0, -2.0, 0.0, 3.0, 2.0, 1.0, 3.0, 4.0],
    "Classical": [5.0, 4.0, 3.0, 2.0, -2.0, -3.0, -2.0, 2.0, 3.0, 4.0], "Vocal Boost": [-3.0, -2.0, -1.0, 2.0, 5.0, 5.0, 3.0, 1.0, 0.0, -2.0],
    "Bass Boost": [8.0, 6.0, 4.0, 2.0, 0.0, -2.0, -3.0, -4.0, -4.0, -5.0], "Treble Boost": [-5.0, -4.0, -3.0, -2.0, 0.0, 2.0, 4.0, 6.0, 7.0, 8.0],
}
PREAMP_MIN_PERCENT = 0
PREAMP_MAX_PERCENT = 200
DEFAULT_PREAMP_PERCENT = 100

# --- Spatial Audio & Enhanced DSP Processing ---
DSP_SAMPLE_RATE = 48000
BASS_BOOST_MIN = 0
BASS_BOOST_MAX = 100
DEFAULT_BASS_BOOST = 0
LOCAL_AUDIO_EXTENSIONS = (
    ".flac", ".wav", ".aiff", ".aif", ".wv", ".ape", ".alac",
    ".m4a", ".mp3", ".ogg", ".opus", ".aac", ".wma",
)
LOSSLESS_AUDIO_EXTENSIONS = (".flac", ".wav", ".aiff", ".aif", ".wv", ".ape", ".alac")
SLEEP_TIMER_PRESETS = [0, 15, 30, 45, 60, -1]

SPATIAL_WIDTH_MIN = 100
SPATIAL_WIDTH_MAX = 250
DEFAULT_SPATIAL_WIDTH = 175
SPATIAL_ROOM_MIN = 0
SPATIAL_ROOM_MAX = 100
DEFAULT_SPATIAL_ROOM = 35
SPATIAL_DEPTH_MIN = 0
SPATIAL_DEPTH_MAX = 100
DEFAULT_SPATIAL_DEPTH = 45
DEFAULT_SPATIAL_PRESET = "Concert Hall"
SPATIAL_AUDIO_PRESETS = {
    "Subtle Air": {"width": 125, "room_size": 15, "depth": 15},
    "Studio Wide": {"width": 145, "room_size": 18, "depth": 25},
    "Concert Hall": {"width": 175, "room_size": 55, "depth": 45},
    "3D Headphones": {"width": 190, "room_size": 35, "depth": 65},
    "Ultra Wide": {"width": 225, "room_size": 45, "depth": 55},
}

# --- Playback Bookmarks ---
MAX_BOOKMARKS_PER_VIDEO = 50
MAX_TOTAL_BOOKMARKS = 500

# --- Tab Management ---
DEFAULT_TAB_ORDER = [
    "youtube", "discovery", "radar", "audio_player", 
    "history", "favorites", "lyrics", "stats", "settings", "help"
]
# These keys MUST match the panel class names in tunevia.py (e.g., YoutubeSearchPanel -> youtube)
TABS_CONFIG = {
    "youtube": {"name": "YouTube"},
    "discovery": {"name": "Discovery"},
    "radar": {"name": "Radar"},
    "audio_player": {"name": "Audio Player"},
    "history": {"name": "History"},
    "favorites": {"name": "Favorites"},
    "lyrics": {"name": "Lyrics"},
    "stats": {"name": "Stats"},
    "settings": {"name": "Settings"},
    "help": {"name": "Help"},
}

# Tab indices
YOUTUBE_TAB_INDEX = 0
DISCOVERY_TAB_INDEX = 1
RADAR_TAB_INDEX = 2
AUDIO_PLAYER_TAB_INDEX = 3
HISTORY_TAB_INDEX = 4
FAVORITES_TAB_INDEX = 5
LYRICS_TAB_INDEX = 6
STATS_TAB_INDEX = 7
SETTINGS_TAB_INDEX = 8
HELP_TAB_INDEX = 9


# --- Global Hotkey IDs (Windows) ---
ALT_SHIFT_PLAY_PAUSE_HK_ID = 1
ALT_SHIFT_REWIND_HK_ID = 2
ALT_SHIFT_FFWD_HK_ID = 3
ALT_SHIFT_VOL_UP_HK_ID = 4
ALT_SHIFT_VOL_DOWN_HK_ID = 5
ALT_SHIFT_SHOW_WINDOW_HK_ID = 6
ALT_SHIFT_PLAY_NEXT_HK_ID = 7
ALT_SHIFT_PLAY_PREV_HK_ID = 8

# --- Windows Specific Constants ---
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
VK_LEFT = 0x25
VK_RIGHT = 0x27
VK_UP = 0x26
VK_DOWN = 0x28
VK_P = 0x50
VK_W = 0x57
VK_N = 0x4E
VK_B = 0x42

# --- Action Keys for Hotkey Customization ---
CUSTOMIZABLE_ACTIONS = {
    "global_play_pause": { "id": ALT_SHIFT_PLAY_PAUSE_HK_ID, "description": "Global: Toggle Play/Pause", "type": "global", "default": (MOD_ALT | MOD_SHIFT, VK_P) },
    "global_rewind": { "id": ALT_SHIFT_REWIND_HK_ID, "description": "Global: Rewind", "type": "global", "default": (MOD_ALT | MOD_SHIFT, VK_LEFT) },
    "global_ffwd": { "id": ALT_SHIFT_FFWD_HK_ID, "description": "Global: Fast Forward", "type": "global", "default": (MOD_ALT | MOD_SHIFT, VK_RIGHT) },
    "global_vol_up": { "id": ALT_SHIFT_VOL_UP_HK_ID, "description": "Global: Volume Up", "type": "global", "default": (MOD_ALT | MOD_SHIFT, VK_UP) },
    "global_vol_down": { "id": ALT_SHIFT_VOL_DOWN_HK_ID, "description": "Global: Volume Down", "type": "global", "default": (MOD_ALT | MOD_SHIFT, VK_DOWN) },
    "global_show_window": { "id": ALT_SHIFT_SHOW_WINDOW_HK_ID, "description": "Global: Show/Hide Window", "type": "global", "default": (MOD_ALT | MOD_SHIFT, VK_W) },
    "global_play_next": { "id": ALT_SHIFT_PLAY_NEXT_HK_ID, "description": "Global: Play Next Track", "type": "global", "default": (MOD_ALT | MOD_SHIFT, VK_N) },
    "global_play_previous": { "id": ALT_SHIFT_PLAY_PREV_HK_ID, "description": "Global: Play Previous Track", "type": "global", "default": (MOD_ALT | MOD_SHIFT, VK_B) },
    "local_play_pause": { "id": "local_play_pause", "description": "Player: Toggle Play/Pause", "type": "local", "default": (wx.ACCEL_CTRL, ord('P')) },
    "local_rewind": { "id": "local_rewind", "description": "Player: Rewind", "type": "local", "default": (wx.ACCEL_NORMAL, wx.WXK_LEFT) },
    "local_ffwd": { "id": "local_ffwd", "description": "Player: Fast Forward", "type": "local", "default": (wx.ACCEL_NORMAL, wx.WXK_RIGHT) },
    "local_vol_up": { "id": "local_vol_up", "description": "Player: Volume Up", "type": "local", "default": (wx.ACCEL_NORMAL, wx.WXK_UP) },
    "local_vol_down": { "id": "local_vol_down", "description": "Player: Volume Down", "type": "local", "default": (wx.ACCEL_NORMAL, wx.WXK_DOWN) },
    "local_speak_time": { "id": "local_speak_time", "description": "Player: Announce Time", "type": "local", "default": (wx.ACCEL_NORMAL, ord('T')) },
    "local_toggle_repeat": { "id": "local_toggle_repeat", "description": "Player: Cycle Repeat Mode", "type": "local", "default": (wx.ACCEL_CTRL, ord('R')) },
    "local_toggle_shuffle": { "id": "local_toggle_shuffle", "description": "Player: Toggle Shuffle", "type": "local", "default": (wx.ACCEL_CTRL, ord('S')) },
    "local_toggle_mono": { "id": "local_toggle_mono", "description": "Player: Toggle Mono Audio", "type": "local", "default": (wx.ACCEL_CTRL, ord('M')) },
    "local_add_bookmark": { "id": "local_add_bookmark", "description": "Player: Add Bookmark", "type": "local", "default": (wx.ACCEL_CTRL, ord('B')) },
    "local_open_equalizer": { "id": "local_open_equalizer", "description": "Player: Open Equalizer", "type": "local", "default": (wx.ACCEL_CTRL, ord('E')) },
    "local_open_chapters": { "id": "local_open_chapters", "description": "Player: Open Chapters List", "type": "local", "default": (wx.ACCEL_CTRL, ord('H')) },
    "local_next_chapter": { "id": "local_next_chapter", "description": "Player: Next Chapter", "type": "local", "default": (wx.ACCEL_CTRL, ord(']')) },
    "local_prev_chapter": { "id": "local_prev_chapter", "description": "Player: Previous Chapter", "type": "local", "default": (wx.ACCEL_CTRL, ord('[')) },
    "local_toggle_spatial": { "id": "local_toggle_spatial", "description": "Player: Toggle Spatial Audio", "type": "local", "default": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('S')) },
    "local_open_spatial": { "id": "local_open_spatial", "description": "Player: Open Spatial Audio Settings", "type": "local", "default": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('E')) },
    "local_open_local_audio": { "id": "local_open_local_audio", "description": "Player: Open Local / Lossless Audio", "type": "local", "default": (wx.ACCEL_CTRL, ord('O')) },
    "local_toggle_lossless": { "id": "local_toggle_lossless", "description": "Player: Toggle Lossless Bit-Perfect Mode", "type": "local", "default": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('L')) },
    "local_cycle_bass_boost": { "id": "local_cycle_bass_boost", "description": "Player: Cycle Bass Boost", "type": "local", "default": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('B')) },
    "local_toggle_vocal_boost": { "id": "local_toggle_vocal_boost", "description": "Player: Toggle Vocal Clarity Mode", "type": "local", "default": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('V')) },
    "local_toggle_night_mode": { "id": "local_toggle_night_mode", "description": "Player: Toggle Night Listening Mode", "type": "local", "default": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('N')) },
    "local_toggle_ab_loop": { "id": "local_toggle_ab_loop", "description": "Player: Set or Clear A-B Loop", "type": "local", "default": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('A')) },
    "local_sleep_timer": { "id": "local_sleep_timer", "description": "Player: Open Sleep Timer", "type": "local", "default": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('Z')) },
    "local_open_queue": { "id": "local_open_queue", "description": "Player: Open Up-Next Queue", "type": "local", "default": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('Q')) },
    "local_toggle_nvda_ducking": { "id": "local_toggle_nvda_ducking", "description": "Player: Toggle Screen Reader Audio Ducking", "type": "local", "default": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord('D')) },
    "local_speak_track_info": { "id": "local_speak_track_info", "description": "Player: Announce Track and Audio Info", "type": "local", "default": (wx.ACCEL_NORMAL, ord('I')) },
}
