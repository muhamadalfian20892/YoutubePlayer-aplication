import os
import struct
import sys

def get_resource_path(relative_path):
    """
    Resolves the absolute path for a resource file or directory.
    It checks sys._MEIPASS, base directory, '_internal' subdirectories, and
    supports alternative candidate subpaths (e.g., 'libs/plugins' vs 'plugins').
    """
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
        meipass = getattr(sys, '_MEIPASS', None)
        paths_to_check = []
        if meipass:
            paths_to_check.append(meipass)
        paths_to_check.append(base_path)
    else:
        base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        paths_to_check = [base_path]
        try:
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            if current_file_dir not in paths_to_check:
                paths_to_check.append(current_file_dir)
        except NameError:
            pass

    # Build relative candidates (e.g. check both 'plugins' and 'libs/plugins')
    normalized_rel = os.path.normpath(relative_path)
    candidates = [relative_path]
    
    parts = normalized_rel.split(os.sep)
    if parts and parts[0] == 'libs' and len(parts) > 1:
        alt_rel = os.path.join(*parts[1:])
        if alt_rel not in candidates:
            candidates.append(alt_rel)
    elif parts and parts[0] != 'libs':
        alt_rel = os.path.join('libs', normalized_rel)
        if alt_rel not in candidates:
            candidates.append(alt_rel)

    # 1. Try to find candidate in base paths directly.
    for bp in paths_to_check:
        for cand in candidates:
            full_path = os.path.join(bp, cand)
            if os.path.exists(full_path):
                return os.path.abspath(full_path)

    # 2. Try to find candidate in '_internal' subdirectory of each base path.
    for bp in paths_to_check:
        for cand in candidates:
            internal_path = os.path.join(bp, "_internal", cand)
            if os.path.exists(internal_path):
                return os.path.abspath(internal_path)

    # 3. Fallback to the primary base path + original relative path.
    return os.path.abspath(os.path.join(paths_to_check[0], relative_path))

_dll_dir_handles = []
_preloaded_vlccore = None


def sync_vlc_plugins_cache(plugins_dir):
    """
    Syncs recorded plugin DLL mtimes inside VLC's plugins.dat with disk mtimes
    when file sizes match, preventing slow cold rescans after ZIP extraction.
    """
    if not plugins_dir or not os.path.isdir(plugins_dir):
        return (0, 0)
    dat_path = os.path.join(plugins_dir, "plugins.dat")
    if not os.path.isfile(dat_path):
        return (0, 0)

    try:
        with open(dat_path, "rb") as f:
            buf = bytearray(f.read())
    except OSError:
        return (0, 0)

    matched = 0
    patched = 0
    for root, _, files in os.walk(plugins_dir):
        for fn in files:
            if not fn.lower().endswith(".dll"):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, plugins_dir).replace("/", "\\")
            rel_b = rel.encode("utf-8")
            needle = struct.pack("<H", len(rel_b) + 1) + rel_b + b"\x00"
            pos = buf.find(needle)
            if pos == -1:
                continue
            meta_off = pos + len(needle)
            if meta_off + 17 > len(buf) or buf[meta_off] != 1:
                continue
            stored_mtime, stored_size = struct.unpack_from("<qq", buf, meta_off + 1)
            try:
                st = os.stat(full)
            except OSError:
                continue
            if stored_size != st.st_size:
                continue
            matched += 1
            disk_mtime = int(st.st_mtime)
            if stored_mtime != disk_mtime:
                struct.pack_into("<q", buf, meta_off + 1, disk_mtime)
                patched += 1

    if patched > 0:
        tmp_path = dat_path + ".tmp"
        try:
            with open(tmp_path, "wb") as f:
                f.write(buf)
            os.replace(tmp_path, dat_path)
        except OSError:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            return (matched, 0)

    return (matched, patched)


def setup_vlc_environment():
    """
    Configures environment variables and Windows DLL search paths for libvlc.
    Must be called BEFORE `import vlc` so that python-vlc's find_lib() loads
    the bundled libvlc.dll and resolves libvlccore.dll without depending on
    a system-wide VLC installation.
    """
    global _preloaded_vlccore
    import ctypes
    vlc_dll_file = get_resource_path('libvlc.dll')
    if vlc_dll_file and os.path.exists(vlc_dll_file):
        vlc_bin_dir = os.path.dirname(vlc_dll_file)
        if vlc_bin_dir and os.path.exists(vlc_bin_dir):
            if vlc_bin_dir not in sys.path:
                sys.path.insert(0, vlc_bin_dir)

            current_path = os.environ.get('PATH', '')
            if vlc_bin_dir not in current_path:
                os.environ['PATH'] = f"{vlc_bin_dir}{os.pathsep}{current_path}"

            if sys.platform == 'win32':
                if hasattr(os, 'add_dll_directory'):
                    try:
                        # Keep handle alive so Python does not revoke the search directory.
                        _dll_dir_handles.append(os.add_dll_directory(vlc_bin_dir))
                    except Exception as e:
                        print(f"Warning: Could not add VLC DLL directory {vlc_bin_dir}: {e}")

                vlccore_path = os.path.join(vlc_bin_dir, 'libvlccore.dll')
                if os.path.exists(vlccore_path) and _preloaded_vlccore is None:
                    try:
                        _preloaded_vlccore = ctypes.CDLL(vlccore_path)
                    except Exception as e:
                        print(f"Warning: Could not preload libvlccore.dll: {e}")

            os.environ['PYTHON_VLC_LIB_PATH'] = vlc_dll_file

    plugin_path = get_resource_path('plugins')
    if plugin_path and os.path.isdir(plugin_path):
        os.environ['VLC_PLUGIN_PATH'] = plugin_path
        os.environ['PYTHON_VLC_MODULE_PATH'] = plugin_path


