import wx
import re
import os
import sys
import threading
import importlib.util
from datetime import datetime

# Local application imports
import nvda
import constants
import path_utils
from translation_manager import _

# Suppress pygame welcome banner
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

# Defer importing pygame (SDL/audio DLLs) until sound effects are initialized off the startup path.
_pygame = None
_sound_init_lock = threading.Lock()
SOUNDS_ENABLED = importlib.util.find_spec("pygame") is not None

# Cache for loaded sound objects to avoid disk I/O
_sound_cache = {}
_last_sound_play_time = {}


def init_sound_engine_async(settings=None, on_ready=None):
    """Initializes pygame.mixer and preloads sound assets in a background thread."""
    if not SOUNDS_ENABLED:
        return
    if settings and not settings.get("sound_effects_enabled", True):
        return

    def _invoke_ready():
        if not on_ready:
            return
        if wx.GetApp() is not None and not wx.IsMainThread():
            wx.CallAfter(on_ready)
        else:
            on_ready()

    def _worker():
        global _pygame, SOUNDS_ENABLED
        with _sound_init_lock:
            if _pygame is None:
                try:
                    import pygame as _pg
                    _pygame = _pg
                except ImportError:
                    SOUNDS_ENABLED = False
                    print("Warning: 'pygame' library not found. Install it (`pip install pygame`) to enable application sounds.")
                    return
            try:
                if not _pygame.mixer.get_init():
                    _pygame.mixer.init()
                for ev_info in constants.SOUND_EVENTS.values():
                    fn = ev_info.get('file')
                    if fn and fn not in _sound_cache:
                        sp = path_utils.get_resource_path(os.path.join("sound", fn))
                        if os.path.exists(sp):
                            try:
                                _sound_cache[fn] = _pygame.mixer.Sound(sp)
                            except Exception:
                                pass
            except Exception as e:
                print(f"Could not initialize pygame mixer for sounds: {e}")
                return
        _invoke_ready()

    threading.Thread(target=_worker, daemon=True, name="SoundEngineInitThread").start()


def preload_sounds_async(settings=None):
    """Preloads all defined sound files into _sound_cache in a background thread."""
    init_sound_engine_async(settings=settings)


def clear_sound_cache():
    """Releases cached sound buffers when sound effects are turned off."""
    _sound_cache.clear()

def play_sound(settings, event_key):
    """
    Plays a sound based on an event key and user settings using pygame.mixer.
    Applies both master and individual sound volume settings.
    """
    if not SOUNDS_ENABLED:
        return

    if not settings.get("sound_effects_enabled", True):
        return

    if _pygame is None:
        init_sound_engine_async(settings)
        return

    if not _pygame.mixer.get_init():
        return

    # Throttle identical sound events triggered within 50ms to prevent audio queue lag
    import time
    now = time.time()
    if now - _last_sound_play_time.get(event_key, 0) < 0.05:
        return
    _last_sound_play_time[event_key] = now

    sound_settings = settings.get("sound_settings", {})
    sound_config = sound_settings.get(event_key)

    # Check if the sound is enabled
    if not sound_config or not sound_config.get("enabled", False):
        return

    sound_event_info = constants.SOUND_EVENTS.get(event_key)
    if not sound_event_info or 'file' not in sound_event_info:
        print(f"Warning: Sound event key '{event_key}' not found in constants.SOUND_EVENTS.")
        return
    
    sound_filename = sound_event_info['file']

    try:
        # Check cache first
        if sound_filename in _sound_cache:
            sound = _sound_cache[sound_filename]
        else:
            # --- Sound file loading ---
            sound_file_path = path_utils.get_resource_path(os.path.join("sound", sound_filename))
            
            if not os.path.exists(sound_file_path):
                print(_("Notification sound file not found: {}").format(sound_file_path))
                return
            
            sound = _pygame.mixer.Sound(sound_file_path)
            _sound_cache[sound_filename] = sound

        # Calculate and set volume (check both sound_effects_volume and master_volume for compatibility)
        raw_master = settings.get("sound_effects_volume", settings.get("master_volume", 100))
        master_volume = raw_master / 100.0
        individual_volume = sound_config.get("volume", 100) / 100.0
        final_volume = master_volume * individual_volume
        sound.set_volume(final_volume)
        
        sound.play()

    except _pygame.error as e:
        print(f"Error playing sound '{sound_filename}' with pygame: {e}")


def format_duration(duration_seconds):
    """Formats a duration in seconds into a HH:MM:SS or MM:SS string."""
    if duration_seconds is None or not isinstance(duration_seconds, (int, float)) or duration_seconds < 0:
        return "N/A"
    try:
        seconds = int(duration_seconds)
        mins, secs = divmod(seconds, 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours}:{mins:02}:{secs:02}"
        else:
            return f"{mins:02}:{secs:02}"
    except (TypeError, ValueError):
        return "N/A"

def format_time_ms(milliseconds):
    """Formats a time in milliseconds into a HH:MM:SS or MM:SS string."""
    if milliseconds is None or milliseconds < 0:
        milliseconds = 0
    try:
        total_seconds = int(milliseconds // 1000)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}:{minutes:02}:{seconds:02}"
        else:
            return f"{minutes:02}:{seconds:02}"
    except (TypeError, ValueError):
        return _("Time not available")

def format_upload_date(date_str):
    """Formats a 'YYYYMMDD' date string into a localized, readable format."""
    if not date_str or not isinstance(date_str, str) or len(date_str) != 8:
        return _("Unknown Date")
    try:
        dt = datetime.strptime(date_str, '%Y%m%d')
        # %x is the locale's appropriate date representation (e.g., MM/DD/YY or DD.MM.YYYY)
        return dt.strftime('%x')
    except (ValueError, TypeError):
        return _("Invalid Date")

def format_filesize(size_bytes):
    """Formats a file size in bytes into a human-readable string (KB, MB, GB)."""
    if size_bytes is None or not isinstance(size_bytes, (int, float)) or size_bytes < 0:
        return "N/A"
    try:
        size_bytes = int(size_bytes)
        if size_bytes == 0:
            return "0 B"
        power = 1024
        n = 0
        power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
        while size_bytes >= power and n < len(power_labels) -1 :
            size_bytes /= power
            n += 1
        return f"{size_bytes:.2f} {power_labels[n]}B"
    except (ValueError, TypeError):
        return "N/A"


def is_internet_available():
    """Checks for a basic internet connection."""
    import requests
    try:
        requests.get("https://www.google.com", timeout=5)
        return True
    except requests.exceptions.RequestException:
        return False

def show_message_dialog(parent, message, title, style=wx.OK | wx.ICON_INFORMATION):
    """Thread-safe method to show a wx.MessageBox."""
    wx.CallAfter(wx.MessageBox, message, title, style | wx.CENTRE, parent)

def show_error_dialog(parent, message, title=None):
    """Convenience function to show a standardized error dialog."""
    if title is None:
        title = _("Error")
    
    app = wx.GetApp()
    msg_parent = parent or (app.GetTopWindow() if app else None)
    
    if msg_parent:
        settings = getattr(msg_parent, 'settings', {}) if hasattr(msg_parent, 'settings') else {}
        if not settings and hasattr(msg_parent, 'main_frame'):
            settings = getattr(msg_parent.main_frame, 'settings', {})
        if settings:
            play_sound(settings, "error")
            
    show_message_dialog(parent, message, title, wx.OK | wx.ICON_ERROR)

def copy_text_to_clipboard(text):
    """Copies the given text to the system clipboard."""
    if not wx.TheClipboard.IsOpened():
        if wx.TheClipboard.Open():
            data = wx.TextDataObject()
            data.SetText(text or "")
            try:
                if wx.TheClipboard.SetData(data):
                    nvda.speak(_("Text copied to clipboard!"))
                else:
                    print("Clipboard SetData failed.")
                    error_detail = _("SetData returned false.")
                    show_error_dialog(None, f"{_('Could not access clipboard.')}\n{_('Details')}: {error_detail}")
                    nvda.speak(_('Could not access clipboard.'))
            except Exception as e:
                print(f"Clipboard SetData Error: {e}")
                show_error_dialog(None, f"{_('Could not access clipboard.')}\n{_('Details')}: {e}")
                nvda.speak(_('Could not access clipboard.'))
            finally:
                wx.TheClipboard.Close()
        else:
            nvda.speak(_("Unable to open clipboard."))
            show_error_dialog(None, _("Unable to open clipboard."))
    else:
        nvda.speak(_("Clipboard busy, please try again."))

def sanitize_filename(filename):
    """
    Removes illegal characters from a string to make it a valid filename.
    Also truncates to a reasonable length.
    """
    sanitized = re.sub(r'[\\/*?:"<>|]', '', filename)
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    max_len = 200
    if len(sanitized) > max_len:
        last_space = sanitized[:max_len].rfind(' ')
        sanitized = sanitized[:last_space] if last_space > max_len // 2 else sanitized[:max_len]
    return sanitized or _("lyrics")

def clean_title_for_lyrics(title):
    """
    Cleans up a YouTube video title by removing common tags (e.g. Official Video, Lyrics)
    to improve lyrics search accuracy.
    """
    # Remove content in brackets/parentheses containing typical keywords
    clean_title = re.sub(r'(?i)[\[\(\{].*?(official|music|video|audio|lyrics|visualizer|live|premiere|feat\.?|ft\.?|acoustic).*?[\]\)\}]', '', title)
    # Remove "- Topic" or similar typical suffixes if needed, but the above is usually enough.
    return clean_title.strip()


def parse_playlist_file(file_path):
    """
    Parses a playlist file (M3U or PLS) and returns a list of dictionaries
    containing 'url' and 'title' for each entry.
    """
    results = []
    try:
        ext = os.path.splitext(file_path)[1].lower()
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        if ext == '.m3u' or ext == '.m3u8':
            current_title = "Unknown Title"
            for line in lines:
                line = line.strip()
                if not line: continue
                if line.startswith('#EXTINF:'):
                    # Format: #EXTINF:123,Artist - Title
                    parts = line.split(',', 1)
                    if len(parts) > 1:
                        current_title = parts[1].strip()
                elif not line.startswith('#'):
                    results.append({'url': line, 'title': current_title})
                    current_title = "Unknown Title" # Reset for next entry

        elif ext == '.pls':
            import configparser
            config = configparser.ConfigParser()
            config.read(file_path)
            if 'playlist' in config:
                count = int(config['playlist'].get('NumberOfEntries', 0))
                for i in range(1, count + 1):
                    url = config['playlist'].get(f'File{i}')
                    title = config['playlist'].get(f'Title{i}', 'Unknown Title')
                    if url:
                        results.append({'url': url, 'title': title})
    except Exception as e:
        print(f"Error parsing playlist file: {e}")
        return []

    return results

def save_playlist_file(file_path, items):
    """
    Saves a list of items (dicts with 'url' and 'title') to a playlist file.
    Format is determined by file extension (.m3u or .pls).
    """
    try:
        ext = os.path.splitext(file_path)[1].lower()
        with open(file_path, 'w', encoding='utf-8') as f:
            if ext == '.m3u' or ext == '.m3u8':
                f.write("#EXTM3U\n")
                for item in items:
                    title = item.get('title', 'Unknown Title')
                    url = item.get('url', '')
                    # Duration is unknown, so we use -1
                    f.write(f"#EXTINF:-1,{title}\n")
                    f.write(f"{url}\n")
            
            elif ext == '.pls':
                f.write("[playlist]\n")
                f.write(f"NumberOfEntries={len(items)}\n")
                for i, item in enumerate(items, 1):
                    title = item.get('title', 'Unknown Title')
                    url = item.get('url', '')
                    f.write(f"File{i}={url}\n")
                    f.write(f"Title{i}={title}\n")
                    f.write(f"Length{i}=-1\n")
                f.write("Version=2\n")
        return True
    except Exception as e:
        print(f"Error saving playlist file: {e}")
        return False

_kernel32 = None
_psapi = None

def optimize_memory():
    """
    Trims unused memory pages, evicts expired stream caches, and runs garbage collection.
    Keeps physical RAM usage low when idle.
    """
    global _kernel32, _psapi
    try:
        if 'audio_player_panel' in sys.modules:
            ap = sys.modules['audio_player_panel']
            if hasattr(ap, '_stream_cache_lock') and hasattr(ap, '_stream_url_cache'):
                import time as _time
                now = _time.time()
                with ap._stream_cache_lock:
                    expired = [k for k, v in ap._stream_url_cache.items() if now >= v.get('expires_at', 0)]
                    for k in expired:
                        del ap._stream_url_cache[k]
        import gc
        gc.collect()
        if sys.platform == 'win32':
            import ctypes
            from ctypes import wintypes
            if _kernel32 is None or _psapi is None:
                _kernel32 = ctypes.windll.kernel32
                _psapi = ctypes.windll.psapi
                _kernel32.GetCurrentProcess.restype = wintypes.HANDLE
                _psapi.EmptyWorkingSet.argtypes = [wintypes.HANDLE]
                _psapi.EmptyWorkingSet.restype = wintypes.BOOL
            _psapi.EmptyWorkingSet(_kernel32.GetCurrentProcess())
    except Exception:
        pass

def get_youtube_video_id(url):
    """
    Extracts the 11-character YouTube video ID from a watch, embed, or youtu.be URL.
    Returns None if no valid ID is found.
    """
    if not url or not isinstance(url, str):
        return None
    match = re.search(r'(?:v=|\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', url)
    return match.group(1) if match else None
