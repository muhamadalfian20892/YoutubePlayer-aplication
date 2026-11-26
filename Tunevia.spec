# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

ytm_datas, ytm_binaries, ytm_hiddenimports = collect_all('ytmusicapi')
cert_datas, cert_binaries, cert_hiddenimports = collect_all('certifi')
ytdlp_datas, ytdlp_binaries, ytdlp_hiddenimports = collect_all('yt_dlp')
genius_datas, genius_binaries, genius_hiddenimports = collect_all('lyricsgenius')
bs4_datas, bs4_binaries, bs4_hiddenimports = collect_all('bs4')
soup_datas, soup_binaries, soup_hiddenimports = collect_all('soupsieve')

hiddenimports = [
    'path_utils', 'constants', 'settings_manager', 'utils', 'nvda',
    'translation_manager', 'youtube_panel', 'discovery_panel', 'radar_panel',
    'audio_player_panel', 'history_panel', 'favorites_panel', 'lyrics_panel',
    'settings_panel', 'downloader_panel', 'help_panel', 'stats_panel',
    'ui_components', 'video_player_frame', 'feature_manager', 'onboarding_dialog',
    'video_comments_dialog', 'playlist_manager', 'yt_dlp_manager', 'spatial_audio',
    'updater', 'pygame', 'pygame.mixer', 'vlc'
] + ytm_hiddenimports + cert_hiddenimports + ytdlp_hiddenimports + genius_hiddenimports + bs4_hiddenimports + soup_hiddenimports

datas = [
    ('docs', 'docs'),
    ('libs', 'libs'),
    ('sound', 'sound'),
    ('locales', 'locales'),
] + ytm_datas + cert_datas + ytdlp_datas + genius_datas + bs4_datas + soup_datas

binaries = ytm_binaries + cert_binaries + ytdlp_binaries + genius_binaries + bs4_binaries + soup_binaries

a = Analysis(
    ['tunevia.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'torch', 'matplotlib'],
    noarchive=False,
    optimize=0,
)

# Drop unused bass DLLs and machine-specific VLC plugins.dat cache so VLC rescans cleanly on any PC.
a.datas = [
    d for d in a.datas
    if not d[0].replace('\\', '/').startswith('libs/bass/')
    and not d[0].replace('\\', '/').endswith('plugins.dat')
]
a.binaries = [
    b for b in a.binaries
    if not b[0].replace('\\', '/').startswith('libs/bass/')
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Tunevia',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='Tunevia',
)
