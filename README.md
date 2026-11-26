# Tunevia

Tunevia is an accessible YouTube and local audio player built with Python, wxPython, LibVLC, and yt-dlp for keyboard-first navigation and NVDA screen reader users on Windows.

## Key Features

- Keyboard-focused interface with Tab traversal, Command Palette (`Ctrl+K`), local shortcuts, and configurable global media hotkeys (`Alt+Shift+...`).
- Native NVDA Controller Client speech feedback with adjustable verbosity and optional Smart NVDA Audio Ducking (`Ctrl+Shift+D`) that lowers music volume while the screen reader speaks.
- 48 kHz Spatial Audio (`Ctrl+Shift+S` / `Ctrl+Shift+E`), 10-band Equalizer (`Ctrl+E`), Bass Boost (`Ctrl+Shift+B`), Vocal Clarity (`Ctrl+Shift+V`), Night Listening compression (`Ctrl+Shift+N`), Mono toggle (`Ctrl+M`), and peak-safe RMS Normalization running on low-memory fixed C-speed audio buffers.
- Local and Lossless audio playback (`Ctrl+O`) supporting FLAC, WAV, AIFF, WavPack, APE, and ALAC with optional Bit-Perfect bypass (`Ctrl+Shift+L`).
- Up-Next Queue (`Ctrl+Shift+Q`), A-B Segment Loop (`Ctrl+Shift+A`), Sleep Timer with gradual fade-out (`Ctrl+Shift+Z`), `0-9` percentage jumps, `I` key track telemetry, Chapters, Bookmarks, Lyrics search, SponsorBlock auto-skip, Downloader (`Ctrl+D`), and built-in app updates (`Help -> Check for Updates`).
- Bilingual English and Indonesian (`Bahasa Indonesia`) UI.

## Running From Source

1. Install Python 3.12 (64-bit) on Windows.
2. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Place the 64-bit Windows `libvlc.dll`, `libvlccore.dll`, `plugins/`, and `ffmpeg.exe` into `libs/` (see `BUILDING.md`).
4. Run:
   ```powershell
   python tunevia.py
   ```

## Testing and Building

Run all automated tests:
```powershell
.\venv\Scripts\python.exe -m unittest test_new_features.py test_small_sections.py test_streamguard_and_gui.py test_feature_manager_system.py test_60_scenarios.py test_spatial_and_bugfixes.py
```

Build the standalone Windows package:
```powershell
.\venv\Scripts\pyinstaller.exe --clean Tunevia.spec --noconfirm
```
The compiled executable and runtime files are placed in `dist/Tunevia/`.
