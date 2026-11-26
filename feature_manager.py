#--- START OF FILE feature_manager.py ---

"""
feature_manager.py

Centralized Feature Registry and Manager for Tunevia.
Handles feature metadata, categories, dependencies, presets,
and helper functions for runtime querying and state persistence.
"""

def get_text(text):
    """Safely translates a string using translation_manager if available."""
    try:
        from translation_manager import _
        return _(text)
    except Exception:
        return text

# --- Category Identifiers ---
CATEGORY_CORE = "core"
CATEGORY_DISCOVERY = "discovery"
CATEGORY_LYRICS = "lyrics"
CATEGORY_DOWNLOADS = "downloads"
CATEGORY_AUDIO = "audio"
CATEGORY_ADVANCED = "advanced"

CATEGORIES = [
    CATEGORY_CORE,
    CATEGORY_DISCOVERY,
    CATEGORY_LYRICS,
    CATEGORY_DOWNLOADS,
    CATEGORY_AUDIO,
    CATEGORY_ADVANCED,
]

CATEGORY_NAMES = {
    CATEGORY_CORE: "Core",
    CATEGORY_DISCOVERY: "Discovery",
    CATEGORY_LYRICS: "Lyrics",
    CATEGORY_DOWNLOADS: "Downloads",
    CATEGORY_AUDIO: "Audio",
    CATEGORY_ADVANCED: "Advanced",
}

def get_category_name(category):
    return get_text(CATEGORY_NAMES.get(category, category.capitalize()))

# --- Feature Identifiers ---
# Core
FEATURE_YOUTUBE_SEARCH = "youtube_search"
FEATURE_AUDIO_PLAYER = "audio_player"
FEATURE_HISTORY = "history"
FEATURE_FAVORITES = "favorites"
FEATURE_PLAYLISTS = "playlists"

# Discovery
FEATURE_DISCOVER = "discover"
FEATURE_RADAR = "radar"
FEATURE_RADIO_MODE = "radio_mode"
FEATURE_SEARCH_SUGGESTIONS = "search_suggestions"
FEATURE_CHANNEL_BROWSER = "channel_browser"

# Lyrics
FEATURE_LYRICS_SEARCH = "lyrics_search"
FEATURE_AUTO_LYRICS = "auto_lyrics"
FEATURE_SAVE_LYRICS = "save_lyrics"

# Downloads
FEATURE_DOWNLOADER = "downloader"
FEATURE_MP3_CONVERSION = "mp3_conversion"
FEATURE_CLIPBOARD_DETECTION = "clipboard_detection"
FEATURE_DOWNLOAD_NOTIFICATIONS = "download_notifications"

# Audio
FEATURE_SOUND_EFFECTS = "sound_effects"
FEATURE_EQUALIZER = "equalizer"
FEATURE_SPATIAL_AUDIO = "spatial_audio"
FEATURE_AUDIO_NORMALIZATION = "audio_normalization"
FEATURE_MONO_AUDIO = "mono_audio"
FEATURE_BOOKMARKS = "bookmarks"
FEATURE_SPONSORBLOCK = "sponsorblock"

# Advanced
FEATURE_VIDEO_PLAYER = "video_player"
FEATURE_VIDEO_COMMENTS = "video_comments"
FEATURE_STATS = "stats"
FEATURE_SYSTEM_TRAY = "system_tray"
FEATURE_GLOBAL_HOTKEYS = "global_hotkeys"

# --- Feature Registry ---
FEATURE_REGISTRY = {
    # Core Features
    FEATURE_YOUTUBE_SEARCH: {
        "id": FEATURE_YOUTUBE_SEARCH,
        "name": "YouTube Search",
        "category": CATEGORY_CORE,
        "description": "Search YouTube for tracks and videos.",
        "default": True,
        "dependencies": [],
        "tab_key": "youtube",
        "requires_restart": True,
        "is_core": True,
    },
    FEATURE_AUDIO_PLAYER: {
        "id": FEATURE_AUDIO_PLAYER,
        "name": "Audio Player",
        "category": CATEGORY_CORE,
        "description": "Main playback engine and controls.",
        "default": True,
        "dependencies": [],
        "tab_key": "audio_player",
        "requires_restart": True,
        "is_core": True,
    },
    FEATURE_HISTORY: {
        "id": FEATURE_HISTORY,
        "name": "History",
        "category": CATEGORY_CORE,
        "description": "Track playback history and replay past songs.",
        "default": True,
        "dependencies": [],
        "tab_key": "history",
        "requires_restart": True,
        "is_core": False,
    },
    FEATURE_FAVORITES: {
        "id": FEATURE_FAVORITES,
        "name": "Favorites",
        "category": CATEGORY_CORE,
        "description": "Save favorite tracks for quick access.",
        "default": True,
        "dependencies": [],
        "tab_key": "favorites",
        "requires_restart": True,
        "is_core": False,
    },
    FEATURE_PLAYLISTS: {
        "id": FEATURE_PLAYLISTS,
        "name": "Playlists",
        "category": CATEGORY_CORE,
        "description": "Create and manage playlists, with M3U and PLS import/export.",
        "default": True,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },

    # Discovery Features
    FEATURE_DISCOVER: {
        "id": FEATURE_DISCOVER,
        "name": "Discover",
        "category": CATEGORY_DISCOVERY,
        "description": "Browse trending releases and popular music.",
        "default": False,
        "dependencies": [],
        "tab_key": "discovery",
        "requires_restart": True,
        "is_core": False,
    },
    FEATURE_RADAR: {
        "id": FEATURE_RADAR,
        "name": "Radar Recommendations",
        "category": CATEGORY_DISCOVERY,
        "description": "Discover tracks based on your listening habits.",
        "default": False,
        "dependencies": [],
        "tab_key": "radar",
        "requires_restart": True,
        "is_core": False,
    },
    FEATURE_RADIO_MODE: {
        "id": FEATURE_RADIO_MODE,
        "name": "Radio Mode",
        "category": CATEGORY_DISCOVERY,
        "description": "Keep playing similar tracks when your current queue ends.",
        "default": True,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
    FEATURE_SEARCH_SUGGESTIONS: {
        "id": FEATURE_SEARCH_SUGGESTIONS,
        "name": "Live Search Suggestions",
        "category": CATEGORY_DISCOVERY,
        "description": "Show suggestions as you type in search.",
        "default": True,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
    FEATURE_CHANNEL_BROWSER: {
        "id": FEATURE_CHANNEL_BROWSER,
        "name": "Channel & Artist Navigation",
        "category": CATEGORY_DISCOVERY,
        "description": "Browse channel uploads and open artist pages.",
        "default": True,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },

    # Lyrics Features
    FEATURE_LYRICS_SEARCH: {
        "id": FEATURE_LYRICS_SEARCH,
        "name": "Lyrics Search",
        "category": CATEGORY_LYRICS,
        "description": "Search for song lyrics manually.",
        "default": True,
        "dependencies": [],
        "tab_key": "lyrics",
        "requires_restart": True,
        "is_core": False,
    },
    FEATURE_AUTO_LYRICS: {
        "id": FEATURE_AUTO_LYRICS,
        "name": "Automatic Lyrics",
        "category": CATEGORY_LYRICS,
        "description": "Look up lyrics automatically when a track plays.",
        "default": True,
        "dependencies": [FEATURE_LYRICS_SEARCH],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
    FEATURE_SAVE_LYRICS: {
        "id": FEATURE_SAVE_LYRICS,
        "name": "Save Lyrics",
        "category": CATEGORY_LYRICS,
        "description": "Save lyrics to text files.",
        "default": True,
        "dependencies": [FEATURE_LYRICS_SEARCH],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },

    # Downloads Features
    FEATURE_DOWNLOADER: {
        "id": FEATURE_DOWNLOADER,
        "name": "YouTube Downloader",
        "category": CATEGORY_DOWNLOADS,
        "description": "Download videos, audio, or playlists for offline listening.",
        "default": False,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
    FEATURE_MP3_CONVERSION: {
        "id": FEATURE_MP3_CONVERSION,
        "name": "MP3 Conversion",
        "category": CATEGORY_DOWNLOADS,
        "description": "Convert audio downloads to MP3 with FFmpeg.",
        "default": False,
        "dependencies": [FEATURE_DOWNLOADER],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
    FEATURE_CLIPBOARD_DETECTION: {
        "id": FEATURE_CLIPBOARD_DETECTION,
        "name": "Clipboard URL Detection",
        "category": CATEGORY_DOWNLOADS,
        "description": "Prompt to play or download when you copy a YouTube link.",
        "default": True,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
    FEATURE_DOWNLOAD_NOTIFICATIONS: {
        "id": FEATURE_DOWNLOAD_NOTIFICATIONS,
        "name": "Download Notifications",
        "category": CATEGORY_DOWNLOADS,
        "description": "Show a notification when downloads finish.",
        "default": True,
        "dependencies": [FEATURE_DOWNLOADER],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },

    # Audio Features
    FEATURE_SOUND_EFFECTS: {
        "id": FEATURE_SOUND_EFFECTS,
        "name": "Sound Effects",
        "category": CATEGORY_AUDIO,
        "description": "Play sound effects for navigation and player actions.",
        "default": True,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
    FEATURE_EQUALIZER: {
        "id": FEATURE_EQUALIZER,
        "name": "Equalizer",
        "category": CATEGORY_AUDIO,
        "description": "10-band equalizer to adjust tone and frequencies.",
        "default": True,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
    FEATURE_SPATIAL_AUDIO: {
        "id": FEATURE_SPATIAL_AUDIO,
        "name": "Spatial Audio",
        "category": CATEGORY_AUDIO,
        "description": "Widen stereo soundstage with spatial audio and room effects.",
        "default": True,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
    FEATURE_AUDIO_NORMALIZATION: {
        "id": FEATURE_AUDIO_NORMALIZATION,
        "name": "Audio Normalization",
        "category": CATEGORY_AUDIO,
        "description": "Keep volume steady across different tracks.",
        "default": True,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
    FEATURE_MONO_AUDIO: {
        "id": FEATURE_MONO_AUDIO,
        "name": "Mono Audio",
        "category": CATEGORY_AUDIO,
        "description": "Mix stereo output into a single mono channel.",
        "default": True,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
    FEATURE_SPONSORBLOCK: {
        "id": FEATURE_SPONSORBLOCK,
        "name": "SponsorBlock",
        "category": CATEGORY_AUDIO,
        "description": "Skip sponsors, intros, and promos automatically.",
        "default": True,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
    FEATURE_BOOKMARKS: {
        "id": FEATURE_BOOKMARKS,
        "name": "Bookmarks",
        "category": CATEGORY_AUDIO,
        "description": "Save timestamps to jump back to later.",
        "default": True,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },

    # Advanced Features
    FEATURE_VIDEO_PLAYER: {
        "id": FEATURE_VIDEO_PLAYER,
        "name": "Video Player",
        "category": CATEGORY_ADVANCED,
        "description": "Watch video playback inside Tunevia.",
        "default": False,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
    FEATURE_VIDEO_COMMENTS: {
        "id": FEATURE_VIDEO_COMMENTS,
        "name": "Video Comments",
        "category": CATEGORY_ADVANCED,
        "description": "Read comments on the currently playing video.",
        "default": False,
        "dependencies": [FEATURE_VIDEO_PLAYER],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
    FEATURE_STATS: {
        "id": FEATURE_STATS,
        "name": "Statistics",
        "category": CATEGORY_ADVANCED,
        "description": "View listening time, top artists, and played tracks.",
        "default": False,
        "dependencies": [],
        "tab_key": "stats",
        "requires_restart": True,
        "is_core": False,
    },
    FEATURE_SYSTEM_TRAY: {
        "id": FEATURE_SYSTEM_TRAY,
        "name": "System Tray",
        "category": CATEGORY_ADVANCED,
        "description": "Minimize to system tray and control playback from the background.",
        "default": True,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
    FEATURE_GLOBAL_HOTKEYS: {
        "id": FEATURE_GLOBAL_HOTKEYS,
        "name": "Player Keyboard Shortcuts",
        "category": CATEGORY_AUDIO,
        "description": "Control playback with hotkeys, including when Tunevia is in the background.",
        "default": True,
        "dependencies": [],
        "tab_key": None,
        "requires_restart": False,
        "is_core": False,
    },
}

def get_feature_name(feature_id):
    spec = FEATURE_REGISTRY.get(feature_id, {})
    return get_text(spec.get("name", feature_id))

def get_feature_description(feature_id):
    spec = FEATURE_REGISTRY.get(feature_id, {})
    return get_text(spec.get("description", ""))

# --- Presets ---
PRESET_MUSIC_PLAYER = "music_player"
PRESET_MUSIC_DISCOVERY = "music_discovery"
PRESET_POWER_USER = "power_user"
PRESET_RECOMMENDED = "recommended"
PRESET_CUSTOM = "custom"

PRESETS_CONFIG = {
    PRESET_MUSIC_PLAYER: {
        "id": PRESET_MUSIC_PLAYER,
        "name": "Music Player",
        "description": "Essential playback with search, queue, history, and favorites.",
        "features": {
            FEATURE_YOUTUBE_SEARCH: True,
            FEATURE_AUDIO_PLAYER: True,
            FEATURE_HISTORY: True,
            FEATURE_FAVORITES: True,
            FEATURE_PLAYLISTS: True,
            FEATURE_DISCOVER: False,
            FEATURE_RADAR: False,
            FEATURE_RADIO_MODE: False,
            FEATURE_SEARCH_SUGGESTIONS: True,
            FEATURE_CHANNEL_BROWSER: True,
            FEATURE_LYRICS_SEARCH: True,
            FEATURE_AUTO_LYRICS: False,
            FEATURE_SAVE_LYRICS: False,
            FEATURE_DOWNLOADER: False,
            FEATURE_MP3_CONVERSION: False,
            FEATURE_CLIPBOARD_DETECTION: False,
            FEATURE_DOWNLOAD_NOTIFICATIONS: False,
            FEATURE_EQUALIZER: False,
            FEATURE_SPATIAL_AUDIO: True,
            FEATURE_AUDIO_NORMALIZATION: True,
            FEATURE_MONO_AUDIO: True,
            FEATURE_SOUND_EFFECTS: True,
            FEATURE_SPONSORBLOCK: True,
            FEATURE_BOOKMARKS: False,
            FEATURE_VIDEO_PLAYER: False,
            FEATURE_VIDEO_COMMENTS: False,
            FEATURE_STATS: False,
            FEATURE_SYSTEM_TRAY: False,
            FEATURE_GLOBAL_HOTKEYS: True,
        }
    },
    PRESET_MUSIC_DISCOVERY: {
        "id": PRESET_MUSIC_DISCOVERY,
        "name": "Music + Discovery",
        "description": "Music Player features plus Radio mode, Discover, and recommendations.",
        "features": {
            FEATURE_YOUTUBE_SEARCH: True,
            FEATURE_AUDIO_PLAYER: True,
            FEATURE_HISTORY: True,
            FEATURE_FAVORITES: True,
            FEATURE_PLAYLISTS: True,
            FEATURE_DISCOVER: True,
            FEATURE_RADAR: True,
            FEATURE_RADIO_MODE: True,
            FEATURE_SEARCH_SUGGESTIONS: True,
            FEATURE_CHANNEL_BROWSER: True,
            FEATURE_LYRICS_SEARCH: True,
            FEATURE_AUTO_LYRICS: True,
            FEATURE_SAVE_LYRICS: False,
            FEATURE_DOWNLOADER: False,
            FEATURE_MP3_CONVERSION: False,
            FEATURE_CLIPBOARD_DETECTION: False,
            FEATURE_DOWNLOAD_NOTIFICATIONS: False,
            FEATURE_EQUALIZER: False,
            FEATURE_SPATIAL_AUDIO: True,
            FEATURE_AUDIO_NORMALIZATION: True,
            FEATURE_MONO_AUDIO: True,
            FEATURE_SOUND_EFFECTS: True,
            FEATURE_SPONSORBLOCK: True,
            FEATURE_BOOKMARKS: False,
            FEATURE_VIDEO_PLAYER: False,
            FEATURE_VIDEO_COMMENTS: False,
            FEATURE_STATS: False,
            FEATURE_SYSTEM_TRAY: False,
            FEATURE_GLOBAL_HOTKEYS: True,
        }
    },
    PRESET_POWER_USER: {
        "id": PRESET_POWER_USER,
        "name": "Power User",
        "description": "Enables all features, including downloading, video, stats, and audio tools.",
        "features": {fid: True for fid in FEATURE_REGISTRY}
    },
    PRESET_RECOMMENDED: {
        "id": PRESET_RECOMMENDED,
        "name": "Recommended Settings",
        "description": "Fast startup with common tools enabled, including lyrics, equalizer, and tray controls.",
        "features": {
            FEATURE_YOUTUBE_SEARCH: True,
            FEATURE_AUDIO_PLAYER: True,
            FEATURE_HISTORY: True,
            FEATURE_FAVORITES: True,
            FEATURE_PLAYLISTS: True,
            FEATURE_DISCOVER: False,
            FEATURE_RADAR: False,
            FEATURE_RADIO_MODE: True,
            FEATURE_SEARCH_SUGGESTIONS: True,
            FEATURE_CHANNEL_BROWSER: True,
            FEATURE_LYRICS_SEARCH: True,
            FEATURE_AUTO_LYRICS: True,
            FEATURE_SAVE_LYRICS: True,
            FEATURE_DOWNLOADER: False,
            FEATURE_MP3_CONVERSION: False,
            FEATURE_CLIPBOARD_DETECTION: True,
            FEATURE_DOWNLOAD_NOTIFICATIONS: False,
            FEATURE_EQUALIZER: True,
            FEATURE_SPATIAL_AUDIO: True,
            FEATURE_AUDIO_NORMALIZATION: True,
            FEATURE_MONO_AUDIO: True,
            FEATURE_SOUND_EFFECTS: True,
            FEATURE_SPONSORBLOCK: True,
            FEATURE_BOOKMARKS: True,
            FEATURE_VIDEO_PLAYER: False,
            FEATURE_VIDEO_COMMENTS: False,
            FEATURE_STATS: False,
            FEATURE_SYSTEM_TRAY: True,
            FEATURE_GLOBAL_HOTKEYS: True,
        }
    }
}

def get_preset_name(preset_id):
    p = PRESETS_CONFIG.get(preset_id, {})
    return get_text(p.get("name", preset_id))

def get_preset_description(preset_id):
    p = PRESETS_CONFIG.get(preset_id, {})
    return get_text(p.get("description", ""))

def get_default_features():
    """Returns a dict of feature_id -> default boolean from the recommended preset."""
    return PRESETS_CONFIG[PRESET_RECOMMENDED]["features"].copy()

def get_features_by_category(category):
    """Returns a list of feature dictionaries belonging to the specified category."""
    return [f for f in FEATURE_REGISTRY.values() if f["category"] == category]

def is_feature_enabled(settings, feature_id):
    """
    Checks if a feature is enabled in the given settings dictionary.
    Falls back to the feature's default state if not explicitly recorded.
    """
    if not isinstance(settings, dict):
        return FEATURE_REGISTRY.get(feature_id, {}).get("default", True)
    
    enabled_features = settings.get("enabled_features", {})
    if isinstance(enabled_features, dict) and feature_id in enabled_features:
        return bool(enabled_features[feature_id])
    
    # Check if this feature has an existing legacy setting mapping
    legacy_val = _get_legacy_setting_value(settings, feature_id)
    if legacy_val is not None:
        return legacy_val
        
    return FEATURE_REGISTRY.get(feature_id, {}).get("default", True)

def set_feature_enabled(settings, feature_id, enabled):
    """
    Sets a feature's enabled state in settings, enforcing dependencies.
    Disabling a dependency will automatically disable dependent features.
    Enabling a dependent feature will automatically enable required dependencies.
    """
    if not isinstance(settings, dict):
        return
    
    if "enabled_features" not in settings or not isinstance(settings["enabled_features"], dict):
        settings["enabled_features"] = get_default_features()
        
    enabled = bool(enabled)
    settings["enabled_features"][feature_id] = enabled

    # Enforce dependencies
    if enabled:
        # If enabling this feature, ensure all parents are enabled
        deps = FEATURE_REGISTRY.get(feature_id, {}).get("dependencies", [])
        for dep in deps:
            set_feature_enabled(settings, dep, True)
    else:
        # If disabling this feature, disable any feature that depends on it
        for other_id, spec in FEATURE_REGISTRY.items():
            if feature_id in spec.get("dependencies", []):
                set_feature_enabled(settings, other_id, False)

    # Sync with legacy settings where applicable
    _sync_legacy_setting(settings, feature_id, enabled)

def apply_preset(settings, preset_id):
    """Applies a named preset to the given settings dictionary."""
    if preset_id not in PRESETS_CONFIG:
        preset_id = PRESET_RECOMMENDED
        
    preset_features = PRESETS_CONFIG[preset_id]["features"]
    if "enabled_features" not in settings or not isinstance(settings["enabled_features"], dict):
        settings["enabled_features"] = {}
        
    for fid, enabled in preset_features.items():
        set_feature_enabled(settings, fid, enabled)

def get_enabled_tab_keys(settings):
    """
    Returns the list of tab keys that are enabled based on feature configuration.
    Always includes core tabs like 'settings' and 'help'.
    """
    enabled_tabs = []
    always_included = ["settings", "help"]

    for fid, spec in FEATURE_REGISTRY.items():
        tab_key = spec.get("tab_key")
        if tab_key and is_feature_enabled(settings, fid):
            if tab_key not in enabled_tabs:
                enabled_tabs.append(tab_key)

    for tab in always_included:
        if tab not in enabled_tabs:
            enabled_tabs.append(tab)

    return enabled_tabs

def sync_all_features(settings):
    """
    Ensures that all features in the registry are present in settings['enabled_features'],
    migrating from existing legacy settings if not present.
    """
    if "enabled_features" not in settings or not isinstance(settings["enabled_features"], dict):
        settings["enabled_features"] = get_default_features()
        
    for fid in FEATURE_REGISTRY:
        if fid not in settings["enabled_features"]:
            legacy_val = _get_legacy_setting_value(settings, fid)
            if legacy_val is not None:
                settings["enabled_features"][fid] = legacy_val
            else:
                settings["enabled_features"][fid] = FEATURE_REGISTRY[fid]["default"]

    # Validate dependencies across all
    for fid, spec in FEATURE_REGISTRY.items():
        if settings["enabled_features"].get(fid):
            for dep in spec.get("dependencies", []):
                if not settings["enabled_features"].get(dep):
                    settings["enabled_features"][dep] = True

def _get_legacy_setting_value(settings, feature_id):
    """Maps existing legacy settings to feature flags."""
    if feature_id == FEATURE_SEARCH_SUGGESTIONS:
        return settings.get("enable_search_suggestions")
    elif feature_id == FEATURE_CLIPBOARD_DETECTION:
        return settings.get("monitor_clipboard_for_urls")
    elif feature_id == FEATURE_AUTO_LYRICS:
        return settings.get("auto_fetch_lyrics")
    elif feature_id == FEATURE_AUDIO_NORMALIZATION:
        return settings.get("audio_normalization")
    elif feature_id == FEATURE_SPONSORBLOCK:
        return settings.get("enable_sponsorblock")
    elif feature_id == FEATURE_SOUND_EFFECTS:
        return settings.get("sound_effects_enabled")
    elif feature_id == FEATURE_SYSTEM_TRAY:
        return settings.get("minimize_to_tray")
    elif feature_id == FEATURE_GLOBAL_HOTKEYS:
        return settings.get("enable_player_shortcuts")
    return None

def _sync_legacy_setting(settings, feature_id, enabled):
    """Syncs a feature flag change back into the legacy setting key."""
    if feature_id == FEATURE_SEARCH_SUGGESTIONS:
        settings["enable_search_suggestions"] = enabled
    elif feature_id == FEATURE_CLIPBOARD_DETECTION:
        settings["monitor_clipboard_for_urls"] = enabled
    elif feature_id == FEATURE_AUTO_LYRICS:
        settings["auto_fetch_lyrics"] = enabled
    elif feature_id == FEATURE_AUDIO_NORMALIZATION:
        settings["audio_normalization"] = enabled
    elif feature_id == FEATURE_SPONSORBLOCK:
        settings["enable_sponsorblock"] = enabled
    elif feature_id == FEATURE_MONO_AUDIO:
        if not enabled:
            settings["mono_audio"] = False
    elif feature_id == FEATURE_EQUALIZER:
        if not enabled:
            settings["equalizer_enabled"] = False
    elif feature_id == FEATURE_SPATIAL_AUDIO:
        if not enabled:
            settings["spatial_audio_enabled"] = False
    elif feature_id == FEATURE_SOUND_EFFECTS:
        settings["sound_effects_enabled"] = enabled
    elif feature_id == FEATURE_SYSTEM_TRAY:
        settings["minimize_to_tray"] = enabled
    elif feature_id == FEATURE_GLOBAL_HOTKEYS:
        settings["enable_player_shortcuts"] = enabled
