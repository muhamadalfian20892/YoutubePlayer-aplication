# Building Tunevia for Windows

This document explains how VLC and application assets are bundled into a standalone Windows executable using PyInstaller.

## Prerequisites

- Python 3.8+ (64-bit)
- Dependencies installed: `pip install -r requirements.txt`
- PyInstaller installed: `pip install pyinstaller`

## VLC Bundling Architecture

Tunevia relies on `python-vlc` which binds to standard VLC binaries (`libvlc.dll` and `libvlccore.dll`) along with VLC module plugins (`plugins/` directory).

1. **Bundled Binaries**:
   - `libs/libvlc.dll`
   - `libs/libvlccore.dll`
   - `libs/plugins/`

2. **Runtime Path Resolution**:
   - `path_utils.get_resource_path()` automatically detects whether the app is running from Python source or a PyInstaller bundle (`sys._MEIPASS` or `_internal`).
   - `audio_player_panel.py` configures Windows DLL search paths (`os.add_dll_directory`, `PATH`, `PYTHON_VLC_LIB_PATH`) so `ctypes` loads the bundled `libvlc.dll` and `libvlccore.dll`.
   - `--plugin-path=<resolved_path>` is passed directly to `vlc.Instance(...)` to ensure plugin modules (decoders, demuxers, audio outputs) initialize correctly.

3. **`ytmusicapi` Translation Data**:
   - `collect_all('ytmusicapi')` is invoked in `Tunevia.spec` to bundle translation catalog domain (`base`) `.mo` files, resolving `No translation file found for domain: 'base'`.

## Building the Release Executable

Generate a clean release build with a single command:

```powershell
pyinstaller --clean Tunevia.spec
```

The output standalone folder will be located at:
`dist/Tunevia/`

Run the compiled app:
```powershell
.\dist\Tunevia\Tunevia.exe
```

## Troubleshooting

- **Diagnostic Logs**: When running `Tunevia.exe` from command prompt, initialization details (resolved paths, exists checks, VLC instance creation) are printed under `[VLC Log]`.
- **Degraded Mode**: If VLC binaries are missing, Tunevia will display an actionable error message and continue running in degraded mode rather than crashing.
