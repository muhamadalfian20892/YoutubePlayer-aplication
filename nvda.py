import ctypes
import os
import sys

# Local application imports
import constants
import path_utils

# --- Global NVDA Controller Instance ---
nvdaControllerClient = None
_nvda_is_running = False
# Global settings cache to avoid frequent file I/O
_settings_cache = None
_speech_hook = None


def set_speech_hook(hook_fn):
    """Registers an optional callback invoked with spoken text when speech is sent to NVDA."""
    global _speech_hook
    _speech_hook = hook_fn

def load_nvda_dll():
    """
    Attempts to load the NVDA Controller DLL from the 'libs' subfolder.
    Dynamically chooses between 64-bit and 32-bit versions based on Python architecture.
    """
    global nvdaControllerClient, _nvda_is_running
    if nvdaControllerClient:
        return

    try:
        is_64bit = ctypes.sizeof(ctypes.c_void_p) == 8
        dll_name = "nvdaControllerClient64.dll" if is_64bit else "nvdaControllerClient32.dll"
        local_dll_path = path_utils.get_resource_path(os.path.join("libs", dll_name))

        if os.path.exists(local_dll_path):
            dll_path = local_dll_path
        else:
            dll_path = dll_name

        client = ctypes.cdll.LoadLibrary(dll_path)

        # Set explicit ctypes signatures
        if hasattr(client, 'nvdaController_testIfRunning'):
            client.nvdaController_testIfRunning.restype = ctypes.c_long
        if hasattr(client, 'nvdaController_speakText'):
            client.nvdaController_speakText.argtypes = [ctypes.c_wchar_p]
            client.nvdaController_speakText.restype = ctypes.c_long
        if hasattr(client, 'nvdaController_cancelSpeech'):
            client.nvdaController_cancelSpeech.restype = ctypes.c_long

        nvdaControllerClient = client

        # Check if NVDA is actually running
        if hasattr(nvdaControllerClient, 'nvdaController_testIfRunning'):
            _nvda_is_running = (nvdaControllerClient.nvdaController_testIfRunning() == 0)
        else:
            _nvda_is_running = True

        print(f"NVDA Controller DLL loaded successfully from: {dll_path} (Running: {_nvda_is_running})")

    except OSError as e:
        nvdaControllerClient = None
        _nvda_is_running = False
    except Exception as e:
        nvdaControllerClient = None
        _nvda_is_running = False

_last_nvda_check_time = 0

def is_nvda_running():
    """Checks if NVDA is actively running and responding to RPC calls."""
    global _nvda_is_running, _last_nvda_check_time
    if not nvdaControllerClient:
        return False
    import time
    now = time.time()
    if now - _last_nvda_check_time < 2.0:
        return _nvda_is_running
    _last_nvda_check_time = now
    if hasattr(nvdaControllerClient, 'nvdaController_testIfRunning'):
        try:
            _nvda_is_running = (nvdaControllerClient.nvdaController_testIfRunning() == 0)
        except Exception:
            _nvda_is_running = False
    return _nvda_is_running

def _get_verbosity_level():
    """
    Gets the current verbosity level from settings, using a cache.
    This avoids reading the settings file for every speech call.
    """
    global _settings_cache
    if _settings_cache is None:
        try:
            import settings_manager
            _settings_cache = settings_manager.load_settings()
        except Exception:
            _settings_cache = {}
    
    verbosity_str = _settings_cache.get("nvda_verbosity", constants.DEFAULT_NVDA_VERBOSITY)
    return constants.NVDA_VERBOSITY_LEVELS.get(verbosity_str, constants.NVDA_VERBOSITY_LEVELS.get(constants.DEFAULT_NVDA_VERBOSITY, 1))

def refresh_settings_cache(new_settings=None):
    """Forces a reload or direct update of the settings cache."""
    global _settings_cache
    if new_settings is not None and isinstance(new_settings, dict):
        _settings_cache = new_settings
    else:
        try:
            import settings_manager
            _settings_cache = settings_manager.load_settings()
        except Exception:
            _settings_cache = {}

def speak(text, verbosity=constants.NVDA_VERBOSITY_DEFAULT, cancel=True):
    """
    Speaks the given text using the loaded NVDA controller without freezing the GUI.
    
    Args:
        text (str): The text to be spoken.
        verbosity (str): The verbosity level required ('quiet', 'default', 'verbose').
        cancel (bool): If True, cancels any previous speech before speaking.
    """
    if not nvdaControllerClient or not text:
        return
    if not is_nvda_running():
        return

    required_level = constants.NVDA_VERBOSITY_LEVELS.get(verbosity, 1)
    current_level = _get_verbosity_level()
    if current_level < 0:
        return

    if current_level >= required_level:
        try:
            text_str = str(text).strip()
            if not text_str:
                return
            if _speech_hook is not None:
                try:
                    _speech_hook(text_str)
                except Exception:
                    pass
            if cancel:
                nvdaControllerClient.nvdaController_cancelSpeech()
            nvdaControllerClient.nvdaController_speakText(text_str)
        except Exception:
            pass

def beep(freq=440, dur=100):
    """
    Generates an accessible system beep without crashing.
    """
    try:
        import winsound
        winsound.Beep(freq, dur)
    except Exception:
        try:
            ctypes.windll.kernel32.MessageBeep(0)
        except Exception:
            pass

# --- Initial Load Attempt ---
load_nvda_dll()