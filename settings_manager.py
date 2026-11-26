import time
import json
import os
import sys
import threading
import tempfile
import wx # Needed for wx.ACCEL_* constants

# Local application imports
import constants
import path_utils

_settings_lock = threading.Lock()

def get_settings_path():
    """Returns the persistent settings file path, prioritizing portable data dir or APPDATA in frozen builds."""
    base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(sys.argv[0]))
    if os.path.exists(os.path.join(base_dir, 'portable.dat')) or os.path.exists(os.path.join(base_dir, 'portable.txt')):
        data_dir = os.path.join(base_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, constants.SETTINGS_FILE_NAME)
    if getattr(sys, 'frozen', False):
        appdata = os.getenv('APPDATA') or os.getenv('LOCALAPPDATA')
        if appdata:
            tunevia_dir = os.path.join(appdata, 'tunevia')
        else:
            home = os.path.expanduser("~")
            tunevia_dir = os.path.join(home, ".tunevia") if home and home != "~" else os.path.abspath(os.path.join(os.getcwd(), ".tunevia"))
        os.makedirs(tunevia_dir, exist_ok=True)
        appdata_file = os.path.join(tunevia_dir, constants.SETTINGS_FILE_NAME)
        # If appdata settings file doesn't exist yet, copy from bundled resource if available
        if not os.path.exists(appdata_file):
            bundled = path_utils.get_resource_path(constants.SETTINGS_FILE_NAME)
            if bundled and os.path.exists(bundled) and bundled != appdata_file:
                try:
                    import shutil
                    shutil.copyfile(bundled, appdata_file)
                except Exception:
                    pass
        return appdata_file
    return path_utils.get_resource_path(constants.SETTINGS_FILE_NAME)

def get_default_sound_settings():
    """Generates the default sound settings dictionary with all sounds enabled and at full volume."""
    return {key: {"enabled": True, "volume": 100} for key in constants.SOUND_EVENTS.keys()}

def load_settings():
    """
    Loads settings from the JSON file.
    Validates data types and values, falling back to defaults for invalid entries.
    Returns a dictionary of settings.
    """
    defaults = {
        "download_dir": os.path.expanduser("~"),
        "volume": constants.DEFAULT_VOLUME_PERCENT,
        "seek_interval": constants.DEFAULT_SEEK_INTERVAL_SECONDS,
        "autoplay_enabled": False,
        "playback_rate": constants.DEFAULT_PLAYBACK_RATE_FLOAT,
        "auto_fetch_lyrics": False,
        "remember_playback_position": False,
        "enable_player_shortcuts": True,
        "preferred_audio_language": constants.DEFAULT_PREFERRED_LANGUAGE,
        "language": constants.DEFAULT_PREFERRED_LANGUAGE,
        "search_mode": "youtube", # Can be 'youtube' or 'ytmusic'
        "audio_output_device": "",
        "window_size": [800, 700],
        "window_position": [-1, -1],
        "play_history": [],
        "playback_positions": {},
        "youtube_search_history": [],
        "search_results_cache": {},
        "mic_permission_granted": None, # Can be None (not asked), True (granted), or False (denied)
        "sound_effects_enabled": True,
        "sound_effects_volume": 100,
        "sound_settings": get_default_sound_settings(),
        "hotkey_config": {},
        "audio_normalization": False,
        "mono_audio": False,
        "spatial_audio_enabled": False,
        "spatial_audio_preset": constants.DEFAULT_SPATIAL_PRESET,
        "spatial_audio_width": constants.DEFAULT_SPATIAL_WIDTH,
        "spatial_audio_room_size": constants.DEFAULT_SPATIAL_ROOM,
        "spatial_audio_depth": constants.DEFAULT_SPATIAL_DEPTH,
        "auto_check_updates": True,
        "lossless_mode": False,
        "prefer_high_bitrate_audio": True,
        "bass_boost": constants.DEFAULT_BASS_BOOST,
        "vocal_clarity_enabled": False,
        "night_mode_enabled": False,
        "nvda_ducking_enabled": False,
        "equalizer_enabled": False,
        "equalizer_preamp": constants.DEFAULT_PREAMP_PERCENT,
        "equalizer_bands": constants.EQUALIZER_PRESETS["Flat"],
        "equalizer_presets": {}, # User-saved custom presets
        "equalizer_preset_name": "Flat",
        "playback_bookmarks": {}, # { "video_url": [{"time": 12345, "desc": "Note"}, ...], ... }
        "theme": constants.DEFAULT_THEME,
        "always_on_top": False,
        "minimize_to_tray": False,
        "shuffle_mode": False,
        "repeat_mode": constants.REPEAT_MODE_NONE,
        "download_queue": [], # Persisted download queue items
        # New in 1.5.8
        "nvda_verbosity": constants.DEFAULT_NVDA_VERBOSITY,
        "last_run_version": "0.0.0",
        "monitor_clipboard_for_urls": False,
        "comment_fetch_limit": constants.DEFAULT_COMMENT_FETCH_LIMIT,
        # Feature Manager & First Launch
        "first_launch_completed": False,
        "enabled_features": {},
        "enable_search_suggestions": True,
        "favorites": [],
        "tab_order": constants.DEFAULT_TAB_ORDER,
        "visible_tabs": constants.DEFAULT_TAB_ORDER,
        "cookies_file_path": "",
        "enable_sponsorblock": True,
    }

    settings_path = get_settings_path()

    if not os.path.exists(settings_path):
        return defaults.copy()

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        validated = defaults.copy()
        for key, default_val in defaults.items():
            if key in loaded:
                val = loaded[key]
                # Apply specific validation rules
                if key == "sound_settings" and isinstance(val, dict):
                    # This handles the old format (bool) and the new format (dict)
                    current_sound_settings = get_default_sound_settings()
                    for skey, sval in val.items():
                        if skey not in current_sound_settings:
                            continue
                        if isinstance(sval, bool): # Old format
                            current_sound_settings[skey]["enabled"] = sval
                        elif isinstance(sval, dict): # New format
                            if "enabled" in sval and isinstance(sval["enabled"], bool):
                                current_sound_settings[skey]["enabled"] = sval["enabled"]
                            if "volume" in sval and isinstance(sval["volume"], (int, float)):
                                current_sound_settings[skey]["volume"] = max(0, min(100, int(sval["volume"])))
                    validated[key] = current_sound_settings
                elif key == "sound_effects_volume" and isinstance(val, (int, float)):
                    validated[key] = max(0, min(100, int(val)))
                elif key == "hotkey_config" and isinstance(val, dict):
                    validated_config = {}
                    for action_key, key_combo in val.items():
                        if action_key in constants.CUSTOMIZABLE_ACTIONS and isinstance(key_combo, (list, tuple)) and len(key_combo) == 2:
                            validated_config[action_key] = tuple(key_combo)
                    validated[key] = validated_config
                elif key == "volume" and isinstance(val, (int, float)):
                    validated[key] = max(constants.MIN_VOLUME_PERCENT, min(constants.MAX_VOLUME_PERCENT, int(val)))
                elif key == "seek_interval" and isinstance(val, (int, float)):
                    validated[key] = max(constants.MIN_SEEK_INTERVAL_SECONDS, min(constants.MAX_SEEK_INTERVAL_SECONDS, int(val)))
                elif key == "playback_rate" and isinstance(val, (int, float)):
                    validated[key] = max(constants.MIN_PLAYBACK_RATE_FLOAT, min(constants.MAX_PLAYBACK_RATE_FLOAT, float(val)))
                elif key in [
                    "autoplay_enabled", "auto_fetch_lyrics", "remember_playback_position",
                    "enable_player_shortcuts", "audio_normalization", "mono_audio",
                    "spatial_audio_enabled", "equalizer_enabled", "sound_effects_enabled",
                    "enable_sponsorblock", "auto_check_updates", "lossless_mode",
                    "prefer_high_bitrate_audio", "vocal_clarity_enabled",
                    "night_mode_enabled", "nvda_ducking_enabled",
                ] and isinstance(val, bool):
                    validated[key] = bool(val)
                elif key == "bass_boost" and isinstance(val, (int, float)):
                    validated[key] = max(constants.BASS_BOOST_MIN, min(constants.BASS_BOOST_MAX, int(val)))
                elif key == "spatial_audio_preset" and isinstance(val, str):
                    validated[key] = val
                elif key == "spatial_audio_width" and isinstance(val, (int, float)):
                    validated[key] = max(constants.SPATIAL_WIDTH_MIN, min(constants.SPATIAL_WIDTH_MAX, int(val)))
                elif key == "spatial_audio_room_size" and isinstance(val, (int, float)):
                    validated[key] = max(constants.SPATIAL_ROOM_MIN, min(constants.SPATIAL_ROOM_MAX, int(val)))
                elif key == "spatial_audio_depth" and isinstance(val, (int, float)):
                    validated[key] = max(constants.SPATIAL_DEPTH_MIN, min(constants.SPATIAL_DEPTH_MAX, int(val)))
                elif key == "mic_permission_granted" and (isinstance(val, bool) or val is None):
                    validated[key] = val
                elif key == "window_size" and isinstance(val, list) and len(val) == 2:
                    validated[key] = [max(400, int(v)) for v in val]
                elif key == "window_position" and isinstance(val, list) and len(val) == 2:
                    validated[key] = [int(v) for v in val]
                elif key in ["download_dir", "preferred_audio_language", "language", "audio_output_device"] and isinstance(val, str):
                    validated[key] = str(val) if val else default_val
                elif key == "search_mode" and isinstance(val, str) and val in ["youtube", "ytmusic"]:
                    validated[key] = val
                elif key == "play_history" and isinstance(val, list):
                    history = [item for item in val if isinstance(item, dict) and all(k in item for k in ['title', 'uploader', 'url', 'timestamp'])]
                    validated[key] = history[-constants.MAX_PLAY_HISTORY_ITEMS:]
                elif key == "playback_positions" and isinstance(val, dict):
                    positions = {k: int(v) for k, v in val.items() if isinstance(k, str) and isinstance(v, (int, float)) and v >= 0}
                    if len(positions) > constants.MAX_SAVED_POSITIONS:
                        keys_to_keep = list(positions.keys())[-constants.MAX_SAVED_POSITIONS:]
                        positions = {k: positions[k] for k in keys_to_keep}
                    validated[key] = positions
                elif key == "youtube_search_history" and isinstance(val, list):
                    search_hist = [str(item) for item in val if isinstance(item, str)]
                    validated[key] = search_hist[-constants.MAX_YT_SEARCH_HISTORY_ITEMS:]
                elif key == "search_results_cache" and isinstance(val, dict):
                    validated[key] = val
                elif key == "equalizer_preamp" and isinstance(val, (int, float)):
                    validated[key] = max(constants.PREAMP_MIN_PERCENT, min(constants.PREAMP_MAX_PERCENT, int(val)))
                elif key == "equalizer_bands" and isinstance(val, list) and len(val) == constants.EQUALIZER_BANDS:
                    validated[key] = [max(constants.EQUALIZER_MIN_GAIN, min(constants.EQUALIZER_MAX_GAIN, float(g))) for g in val]
                elif key == "equalizer_presets" and isinstance(val, dict):
                    validated[key] = val # Basic validation, more complex validation is tricky
                elif key == "equalizer_preset_name" and isinstance(val, str):
                    validated[key] = val
                elif key == "playback_bookmarks" and isinstance(val, dict):
                    validated[key] = val # Basic validation
                elif key == "theme" and isinstance(val, str) and val in [constants.THEME_LIGHT, constants.THEME_DARK]:
                    validated[key] = val
                elif key in ["always_on_top", "minimize_to_tray", "shuffle_mode", "monitor_clipboard_for_urls"] and isinstance(val, bool):
                    validated[key] = bool(val)
                elif key == "repeat_mode" and isinstance(val, int) and val in [constants.REPEAT_MODE_NONE, constants.REPEAT_MODE_ONE, constants.REPEAT_MODE_ALL]:
                    validated[key] = val
                elif key == "download_queue" and isinstance(val, list):
                    # Basic validation for queue items
                    queue = [item for item in val if isinstance(item, dict) and 'url' in item and 'status' in item]
                    validated[key] = queue
                # New in 1.5.8
                elif key == "nvda_verbosity" and isinstance(val, str) and val in constants.NVDA_VERBOSITY_LEVELS.keys():
                    validated[key] = val
                elif key == "last_run_version" and isinstance(val, str):
                    validated[key] = val
                elif key == "comment_fetch_limit":
                    if isinstance(val, int) or (isinstance(val, str) and (val.isdigit() or val == "all")):
                         validated[key] = val
                    else:
                         validated[key] = default_val
                elif key in ["first_launch_completed", "enable_search_suggestions"] and isinstance(val, bool):
                    validated[key] = bool(val)
                elif key == "enabled_features" and isinstance(val, dict):
                    validated[key] = {str(k): bool(v) for k, v in val.items()}
                elif key == "favorites" and isinstance(val, list):
                    validated[key] = val
                elif key in ["tab_order", "visible_tabs"] and isinstance(val, list):
                    validated[key] = [str(x) for x in val]
                elif key == "cookies_file_path" and isinstance(val, str):
                    validated[key] = val
            else:
                pass

        # Preserve any additional unhandled keys from loaded
        for k, v in loaded.items():
            if k not in validated:
                validated[k] = v

        # Sync feature manager
        import feature_manager
        feature_manager.sync_all_features(validated)

        return validated
    except (json.JSONDecodeError, IOError, OSError, Exception) as e:
        print(f"Error loading settings: {e}. Using defaults.")
        return defaults.copy()

def save_settings(settings_data):
    """
    Saves the provided settings dictionary to the JSON file.
    Performs final validation/cleanup before writing.
    """
    settings_path = get_settings_path()

    with _settings_lock:
        try:
            # Final cleanup before saving
            if not isinstance(settings_data.get("sound_effects_enabled"), bool):
                settings_data["sound_effects_enabled"] = True

            if not isinstance(settings_data.get("sound_effects_volume"), (int, float)):
                settings_data["sound_effects_volume"] = 100
            else:
                settings_data["sound_effects_volume"] = max(0, min(100, int(settings_data["sound_effects_volume"])))

            if not isinstance(settings_data.get("play_history"), list):
                settings_data["play_history"] = []
            elif len(settings_data["play_history"]) > constants.MAX_PLAY_HISTORY_ITEMS:
                settings_data["play_history"] = settings_data["play_history"][-constants.MAX_PLAY_HISTORY_ITEMS:]

            if not isinstance(settings_data.get("playback_positions"), dict):
                settings_data["playback_positions"] = {}
            elif len(settings_data["playback_positions"]) > constants.MAX_SAVED_POSITIONS:
                keys_to_keep = list(settings_data["playback_positions"].keys())[-constants.MAX_SAVED_POSITIONS:]
                settings_data["playback_positions"] = {k: settings_data["playback_positions"][k] for k in keys_to_keep}

            if not isinstance(settings_data.get("youtube_search_history"), list):
                settings_data["youtube_search_history"] = []
            elif len(settings_data["youtube_search_history"]) > constants.MAX_YT_SEARCH_HISTORY_ITEMS:
                settings_data["youtube_search_history"] = settings_data["youtube_search_history"][-constants.MAX_YT_SEARCH_HISTORY_ITEMS:]
                
            if not isinstance(settings_data.get("search_results_cache"), dict):
                settings_data["search_results_cache"] = {}
            MAX_SEARCH_CACHE_ITEMS = 20
            if len(settings_data.get("search_results_cache", {})) > MAX_SEARCH_CACHE_ITEMS:
                keys_to_keep = list(settings_data["search_results_cache"].keys())[-MAX_SEARCH_CACHE_ITEMS:]
                settings_data["search_results_cache"] = {k: settings_data["search_results_cache"][k] for k in keys_to_keep}

            if "mic_permission_granted" not in settings_data or settings_data["mic_permission_granted"] not in [True, False, None]:
                settings_data["mic_permission_granted"] = None
            
            if not isinstance(settings_data.get("sound_settings"), dict):
                settings_data["sound_settings"] = get_default_sound_settings()
                
            if not isinstance(settings_data.get("language"), str):
                settings_data["language"] = constants.DEFAULT_PREFERRED_LANGUAGE

            if not isinstance(settings_data.get("audio_output_device"), str):
                settings_data["audio_output_device"] = ""

            if not isinstance(settings_data.get("hotkey_config"), dict):
                settings_data["hotkey_config"] = {}
                
            if settings_data.get("search_mode") not in ["youtube", "ytmusic"]:
                settings_data["search_mode"] = "youtube"

            if not isinstance(settings_data.get("playback_bookmarks"), dict):
                settings_data["playback_bookmarks"] = {}
            total_bookmarks = sum(len(v) for v in settings_data["playback_bookmarks"].values())
            if total_bookmarks > constants.MAX_TOTAL_BOOKMARKS:
                # This is a simple trimming strategy, more complex ones could be used
                keys_to_trim = list(settings_data["playback_bookmarks"].keys())
                while total_bookmarks > constants.MAX_TOTAL_BOOKMARKS and keys_to_trim:
                    key = keys_to_trim.pop(0)
                    num_in_key = len(settings_data["playback_bookmarks"][key])
                    del settings_data["playback_bookmarks"][key]
                    total_bookmarks -= num_in_key
                    print(f"Trimming bookmarks for video {key} to manage total size.")

            if settings_data.get("theme") not in [constants.THEME_LIGHT, constants.THEME_DARK]:
                settings_data["theme"] = constants.DEFAULT_THEME
            if not isinstance(settings_data.get("always_on_top"), bool):
                settings_data["always_on_top"] = False
            if not isinstance(settings_data.get("minimize_to_tray"), bool):
                settings_data["minimize_to_tray"] = False
            if not isinstance(settings_data.get("monitor_clipboard_for_urls"), bool):
                settings_data["monitor_clipboard_for_urls"] = False
            if not isinstance(settings_data.get("shuffle_mode"), bool):
                settings_data["shuffle_mode"] = False
            if settings_data.get("repeat_mode") not in [constants.REPEAT_MODE_NONE, constants.REPEAT_MODE_ONE, constants.REPEAT_MODE_ALL]:
                settings_data["repeat_mode"] = constants.REPEAT_MODE_NONE
            if not isinstance(settings_data.get("download_queue"), list):
                settings_data["download_queue"] = []

            # New in 1.5.8
            if settings_data.get("nvda_verbosity") not in constants.NVDA_VERBOSITY_LEVELS.keys():
                settings_data["nvda_verbosity"] = constants.DEFAULT_NVDA_VERBOSITY
            if not isinstance(settings_data.get("last_run_version"), str):
                settings_data["last_run_version"] = "0.0.0"
            
            c_limit = settings_data.get("comment_fetch_limit")
            if not (isinstance(c_limit, int) or (isinstance(c_limit, str) and (c_limit.isdigit() or c_limit == "all"))):
                settings_data["comment_fetch_limit"] = constants.DEFAULT_COMMENT_FETCH_LIMIT

            # Feature Manager & First Launch validation
            if not isinstance(settings_data.get("favorites"), list):
                settings_data["favorites"] = []
            if not isinstance(settings_data.get("enabled_features"), dict):
                settings_data["enabled_features"] = {}
            if not isinstance(settings_data.get("first_launch_completed"), bool):
                settings_data["first_launch_completed"] = False

            if not isinstance(settings_data.get("spatial_audio_enabled"), bool):
                settings_data["spatial_audio_enabled"] = False
            if not isinstance(settings_data.get("spatial_audio_preset"), str):
                settings_data["spatial_audio_preset"] = constants.DEFAULT_SPATIAL_PRESET
            for bkey, bdef in (
                ("auto_check_updates", True),
                ("lossless_mode", False),
                ("prefer_high_bitrate_audio", True),
                ("vocal_clarity_enabled", False),
                ("night_mode_enabled", False),
                ("nvda_ducking_enabled", False),
            ):
                if not isinstance(settings_data.get(bkey), bool):
                    settings_data[bkey] = bdef
            bb_val = settings_data.get("bass_boost", constants.DEFAULT_BASS_BOOST)
            if isinstance(bb_val, (int, float)):
                settings_data["bass_boost"] = max(constants.BASS_BOOST_MIN, min(constants.BASS_BOOST_MAX, int(bb_val)))
            else:
                settings_data["bass_boost"] = constants.DEFAULT_BASS_BOOST
            for skey, smin, smax, sdef in [
                ("spatial_audio_width", constants.SPATIAL_WIDTH_MIN, constants.SPATIAL_WIDTH_MAX, constants.DEFAULT_SPATIAL_WIDTH),
                ("spatial_audio_room_size", constants.SPATIAL_ROOM_MIN, constants.SPATIAL_ROOM_MAX, constants.DEFAULT_SPATIAL_ROOM),
                ("spatial_audio_depth", constants.SPATIAL_DEPTH_MIN, constants.SPATIAL_DEPTH_MAX, constants.DEFAULT_SPATIAL_DEPTH),
            ]:
                sval = settings_data.get(skey)
                if isinstance(sval, (int, float)):
                    settings_data[skey] = max(smin, min(smax, int(sval)))
                else:
                    settings_data[skey] = sdef

            dir_name = os.path.dirname(settings_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            tmp_path = settings_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(settings_data, f, indent=4, ensure_ascii=False)
            
            replaced = False
            for _ in range(5):
                try:
                    os.replace(tmp_path, settings_path)
                    replaced = True
                    break
                except (PermissionError, OSError):
                    time.sleep(0.02)
            if not replaced:
                with open(settings_path, "w", encoding="utf-8") as f:
                    json.dump(settings_data, f, indent=4, ensure_ascii=False)
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass
        except Exception as e:
            print(f"Error saving settings: {e}")


def get_effective_cookies_path(settings=None):
    """
    Returns a valid cookies file path if configured, or auto-detects
    any existing cookies.txt in the application directory or working directory.
    """
    if settings:
        configured = settings.get("cookies_file_path", "").strip()
        if configured and os.path.exists(configured):
            return configured

    settings_dir = os.path.dirname(get_settings_path())
    candidates = [
        path_utils.get_resource_path("cookies.txt"),
        path_utils.get_resource_path("www.youtube.com_cookies.txt"),
        os.path.join(settings_dir, "cookies.txt"),
        os.path.join(settings_dir, "www.youtube.com_cookies.txt"),
        os.path.join(os.getcwd(), "cookies.txt"),
        os.path.join(os.getcwd(), "www.youtube.com_cookies.txt"),
    ]
    for c in candidates:
        if c and os.path.isfile(c) and os.path.getsize(c) > 0:
            return c
    return ""
