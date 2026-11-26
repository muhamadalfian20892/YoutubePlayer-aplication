import os
import sys
import requests
import zipfile
import shutil
import wx
import time
import re

try:
    from translation_manager import _
except Exception:
    def _(s):
        return s

def get_app_data_path():
    """Gets the path to the application's data directory in %APPDATA%."""
    base = os.getenv('APPDATA') or os.getenv('LOCALAPPDATA') or os.getenv('USERPROFILE')
    if base:
        return os.path.abspath(os.path.join(base, 'tunevia'))
    home = os.path.expanduser('~')
    if home and home != '~':
        return os.path.abspath(os.path.join(home, '.tunevia'))
    return os.path.abspath(os.path.join(os.getcwd(), '.tunevia'))

def get_yt_dlp_path():
    """Gets the path to the external yt-dlp module directory."""
    return os.path.join(get_app_data_path(), 'yt_dlp')

import importlib.machinery

class YTDLPOverrideFinder:
    def __init__(self, app_data_path):
        self.app_data_path = app_data_path

    def find_spec(self, fullname, path, target=None):
        if fullname == "yt_dlp" or fullname.startswith("yt_dlp."):
            spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
            if spec and spec.origin and isinstance(spec.origin, str) and self.app_data_path in spec.origin:
                return spec
        return None

def setup_sys_path():
    """Adds the app's data directory to the Python path to make yt_dlp importable."""
    app_data_path = get_app_data_path()
    if app_data_path not in sys.path:
        # Insert at index 1 to avoid displacing the primary bundle/script directory at index 0
        if len(sys.path) > 0:
            sys.path.insert(1, app_data_path)
        else:
            sys.path.append(app_data_path)
        print(f"Added '{app_data_path}' to sys.path at index 1")
    
    if not any(isinstance(finder, YTDLPOverrideFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, YTDLPOverrideFinder(app_data_path))
        print("Injected YTDLPOverrideFinder into sys.meta_path")

def _show_progress_dialog(title, message):
    """Shows a simple, non-blocking progress dialog."""
    if wx.GetApp() is None or not wx.IsMainThread():
        return None
    dialog = wx.ProgressDialog(
        title,
        message,
        maximum=100,
        parent=None,
        style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_ELAPSED_TIME
    )
    dialog.Pulse()
    return dialog

def _perform_download_and_install(progress_callback=None):
    """
    Handles the full process of downloading and extracting the latest yt-dlp source.
    Uses a progress_callback if provided, otherwise shows a wx.ProgressDialog.
    Returns (True, success_message) or (False, error_message).
    """
    app_data_path = get_app_data_path()
    api_url = 'https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest'
    headers = {'User-Agent': 'Tunevia/1.0 (https://github.com/Technokers/Tunevia)'}
    zip_path = os.path.join(app_data_path, 'yt-dlp-latest.zip')
    temp_extract_path = os.path.join(app_data_path, 'yt-dlp-temp')
    progress_dialog = None

    def update_progress(message):
        if progress_callback:
            wx.CallAfter(progress_callback, message)
        elif progress_dialog:
            progress_dialog.Pulse(message)

    try:
        if not progress_callback:
            progress_dialog = _show_progress_dialog(
                _("Initializing Tunevia"),
                _("Setting up required components (yt-dlp)... Please wait.")
            )

        # 1. Create necessary directories
        os.makedirs(app_data_path, exist_ok=True)
        if os.path.exists(temp_extract_path):
            shutil.rmtree(temp_extract_path)

        # 2. Fetch latest release info
        update_progress(_("Checking for component updates..."))
        response = requests.get(api_url, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        version_tag = data.get('tag_name')
        if not version_tag:
            raise RuntimeError("Could not determine the latest version tag.")
        zip_url = f"https://github.com/yt-dlp/yt-dlp/archive/refs/tags/{version_tag}.zip"

        # 3. Download the zip file
        update_progress(_("Downloading yt-dlp v{}...").format(version_tag))
        with requests.get(zip_url, stream=True, headers=headers, timeout=60) as r:
            r.raise_for_status()
            with open(zip_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

        # 4. Extract the zip file
        update_progress(_("Extracting files..."))
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract_path)

        # 5. Find the 'yt_dlp' source folder
        source_module_path = None
        for root, dirs, files in os.walk(temp_extract_path):
            if 'yt_dlp' in dirs and os.path.exists(os.path.join(root, 'yt_dlp', 'YoutubeDL.py')):
                source_module_path = os.path.join(root, 'yt_dlp')
                break
        if not source_module_path:
            raise RuntimeError("Could not find 'yt_dlp' module in extracted files.")

        # 6. Move the 'yt_dlp' folder to its final destination
        update_progress(_("Finalizing installation..."))
        final_path = get_yt_dlp_path()
        if os.path.exists(final_path):
            shutil.rmtree(final_path)
        shutil.move(source_module_path, final_path)

        # 7. Manually write the version file to ensure it matches the tag, but safely (preserve CHANNEL)
        version_file_path = os.path.join(final_path, 'version.py')
        try:
            clean_version = version_tag.lstrip('v')
            with open(version_file_path, 'r', encoding='utf-8') as vf:
                content = vf.read()
            
            # Regex to replace __version__ = '...' with new version
            new_content = re.sub(r"__version__\s*=\s*['\"].*?['\"]", f"__version__ = '{clean_version}'", content)
            
            with open(version_file_path, 'w', encoding='utf-8') as vf:
                vf.write(new_content)
            update_progress(_("Updated version info to {}").format(clean_version))
        except Exception as ve:
            print(f"Warning: Could not write version file: {ve}")

        success_msg = _("yt-dlp updated successfully to v{}!\nPlease restart the application to apply the update.").format(version_tag)
        update_progress(success_msg)
        if progress_dialog:
            time.sleep(1.5)
        
        return (True, success_msg)

    except Exception as e:
        print(f"yt-dlp setup internal error: {e}")
        error_msg = _("Could not complete the component update right now. Please check your internet connection and try again.")
        update_progress(error_msg)
        if not progress_callback and wx.GetApp() is not None and wx.IsMainThread():
            wx.MessageBox(
                error_msg,
                _("Component Setup Error"), wx.OK | wx.ICON_ERROR
            )
        return (False, error_msg)
    finally:
        if os.path.exists(zip_path): os.remove(zip_path)
        if os.path.exists(temp_extract_path): shutil.rmtree(temp_extract_path)
        if progress_dialog: progress_dialog.Destroy()

def run_update_from_panel(progress_callback):
    """
    Public function to be called from the downloader panel to run an update.
    """
    # Check current version first to avoid unnecessary downloads
    try:
        import yt_dlp
        from packaging import version
        current = version.parse(yt_dlp.version.__version__)
        response = requests.get('https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest', timeout=10)
        response.raise_for_status()
        latest = version.parse(response.json()['tag_name'])
        

        
        if latest <= current:
            msg = _("yt-dlp is already up-to-date (v{}).").format(current)
            wx.CallAfter(progress_callback, msg)
            return (True, msg)
    except Exception as e:
        print(f"Could not pre-check yt-dlp version, proceeding with update anyway. Error: {e}")

    # If newer version available or check failed, perform the full update
    return _perform_download_and_install(progress_callback)

def ensure_yt_dlp():
    """
    Checks if yt-dlp is installed. If not, triggers the installation.
    Adds the correct path to sys.path for importing.
    """
    # 1. First, check if custom yt-dlp exists in AppData
    yt_dlp_path = get_yt_dlp_path()
    if os.path.isdir(yt_dlp_path):
        setup_sys_path()
        try:
            import yt_dlp
            print("Found existing yt-dlp installation in AppData.")
            return True
        except Exception as e:
            print(f"Warning: Failed importing yt_dlp from AppData: {e}")

    # 2. Check if yt_dlp is already bundled in the environment / PyInstaller bundle
    try:
        import yt_dlp
        print("Using bundled/environment yt-dlp.")
        return True
    except ImportError:
        pass

    # 3. Fallback to download only if not available anywhere
    print("yt-dlp not found. Starting automatic installation process.")
    success, _ = _perform_download_and_install()
    if not success:
        return False

    setup_sys_path()
    return True