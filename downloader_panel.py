import wx
import os
import sys
import threading
import time
import re
from datetime import datetime

# Local application imports
import path_utils
import nvda
import constants
import utils
import feature_manager
from translation_manager import _
import yt_dlp_manager
from ui_components import PlaylistCountDialog, MultiLinkEntryDialog

# --- Download Item Statuses ---
STATUS_QUEUED = "Queued"
STATUS_DOWNLOADING = "Downloading"
STATUS_CONVERTING = "Converting"
STATUS_FINISHED = "Finished"
STATUS_ERROR = "Error"
STATUS_SKIPPED = "Skipped (Exists)"


class YoutubeDLPanel(wx.Panel):
    """
    A wx.Panel that provides a UI for downloading videos using yt-dlp,
    featuring a simple download list, format options, and logging.
    """
    def __init__(self, parent_dialog, main_frame, initial_urls=None):
        super().__init__(parent_dialog)
        self.parent_dialog = parent_dialog
        self.main_frame = main_frame
        
        self.download_list_data = [] # List of dictionaries for each download item
        self.download_thread = None
        self.is_downloading = False
        self.is_busy_fetching_info = False # Flag for info-fetching state
        self.is_destroyed = False # Flag to check if the panel object is destroyed
        self.current_download_idx = -1
        self._last_progress_ui_time = 0
        
        # Regex to strip ANSI escape codes (for colors)
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        self._last_progress_log_time = 0
        
        self.InitUI()
        self.Bind(wx.EVT_WINDOW_DESTROY, self.on_destroy) # Bind destroy event to set a flag
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)

        if initial_urls:
            self.on_add_url(url=initial_urls)

    def on_char_hook(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.on_close(None)
        else:
            event.Skip()

    def on_destroy(self, event):
        """Sets a flag when the panel is being destroyed to prevent calls from worker threads."""
        self.is_destroyed = True
        event.Skip()

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Top Controls (Add, Remove)
        top_controls_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.add_button = wx.Button(self, label="")
        self.remove_button = wx.Button(self, label="")
        self.clear_list_button = wx.Button(self, label="")
        
        top_controls_sizer.Add(self.add_button, 0, wx.RIGHT, 5)
        top_controls_sizer.Add(self.remove_button, 0, wx.RIGHT, 5)
        top_controls_sizer.Add(self.clear_list_button, 0)
        vbox.Add(top_controls_sizer, 0, wx.ALL, 10)

        # Download List (Updating in-place)
        self.url_list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES)
        vbox.Add(self.url_list_ctrl, 3, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Download Options Group
        self.options_group = wx.StaticBox(self, label="")
        options_sizer = wx.StaticBoxSizer(self.options_group, wx.VERTICAL)
        self._create_options_controls(options_sizer)
        vbox.Add(options_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        # Status text below options
        self.status_bar_text = wx.StaticText(self, label="")
        vbox.Add(self.status_bar_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Bottom buttons
        hbox_bottom = wx.BoxSizer(wx.HORIZONTAL)
        self.download_button = wx.Button(self, label="")
        self.update_ytdlp_button = wx.Button(self, label="")
        self.close_button = wx.Button(self, label="")

        hbox_bottom.Add(self.download_button, 0, wx.RIGHT, 10)
        hbox_bottom.Add(self.update_ytdlp_button, 0)
        hbox_bottom.AddStretchSpacer(1)
        hbox_bottom.Add(self.close_button)
        vbox.Add(hbox_bottom, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.SetSizer(vbox)
        self.retranslate_ui()
        self._bind_events()
        self.update_button_states()

    def _bind_events(self):
        self.add_button.Bind(wx.EVT_BUTTON, self.on_add_url)
        self.remove_button.Bind(wx.EVT_BUTTON, self.on_remove_item)
        self.clear_list_button.Bind(wx.EVT_BUTTON, self.on_clear_list)
        self.mp3_checkbox.Bind(wx.EVT_CHECKBOX, self.on_format_checkbox_toggled)
        self.format_choice.Bind(wx.EVT_CHOICE, self.on_format_choice_changed)
        self.browse_button.Bind(wx.EVT_BUTTON, self.on_browse)
        self.download_button.Bind(wx.EVT_BUTTON, self.on_download)
        self.update_ytdlp_button.Bind(wx.EVT_BUTTON, self.on_update_ytdlp)
        self.close_button.Bind(wx.EVT_BUTTON, self.on_close)
        self.url_list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, lambda e: self.update_button_states())
        self.url_list_ctrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, lambda e: self.update_button_states())

    def retranslate_ui(self):
        self.parent_dialog.SetTitle(_("YouTube Downloader"))
        
        # Top buttons
        self.add_button.SetLabel(_("Add Link(s)..."))
        self.add_button.SetName(_("Add Link(s)"))
        self.add_button.SetToolTip(_("Add one or more video/playlist links to the download list"))
        self.remove_button.SetLabel(_("Remove Selected"))
        self.remove_button.SetName(_("Remove Selected"))
        self.remove_button.SetToolTip(_("Remove the selected item from the list"))
        self.clear_list_button.SetLabel(_("Clear List"))
        self.clear_list_button.SetName(_("Clear List"))
        self.clear_list_button.SetToolTip(_("Remove all items from the download list"))
        
        # URL List (Updating in-place)
        self.url_list_ctrl.SetName(_("Download Queue"))
        self.url_list_ctrl.ClearAll()
        self.url_list_ctrl.InsertColumn(0, _("Title"), width=250)
        self.url_list_ctrl.InsertColumn(1, _("Status"), width=100)
        self.url_list_ctrl.InsertColumn(2, _("Progress"), width=75)
        self.url_list_ctrl.InsertColumn(3, _("Speed"), width=90)
        self.url_list_ctrl.InsertColumn(4, _("ETA"), width=65)
        self.url_list_ctrl.InsertColumn(5, _("Size"), width=115)
        self.url_list_ctrl.InsertColumn(6, _("URL"), width=200)
        self.populate_url_list()

        # Options
        if hasattr(self, 'options_group'):
            self.options_group.SetLabel(_("Options"))
        has_mp3 = feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_MP3_CONVERSION)
        self.mp3_checkbox.Enable(has_mp3)
        if not has_mp3:
            self.mp3_checkbox.SetValue(False)
        self.mp3_checkbox.SetLabel(_("Convert to Audio (Music only)"))
        self.mp3_checkbox.SetName(_("Convert to Audio (Music only)"))
        self.mp3_checkbox.SetToolTip(_("If checked, downloads audio only in the selected format. If unchecked, downloads video.") if has_mp3 else _("Audio conversion is disabled in Feature Manager."))

        self.format_label.SetLabel(_("Audio format:"))
        self.format_choice.SetName(_("Audio format"))
        self.format_choice.SetToolTip(_("Choose the audio format to convert to"))
        self.format_choice.Enable(has_mp3 and self.mp3_checkbox.IsChecked())

        self.dir_label.SetLabel(_("Download directory:"))
        self.download_dir_text.SetName(_("Download directory"))
        self.download_dir_text.SetToolTip(_("Directory where files will be downloaded"))
        self.browse_button.SetLabel(_("Browse..."))
        self.browse_button.SetName(_("Browse Download Directory"))
        self.browse_button.SetToolTip(_("Browse for a download directory"))

        # Bottom buttons
        self.download_button.SetLabel(_("Download All"))
        self.download_button.SetName(_("Download All"))
        self.download_button.SetToolTip(_("Start downloading all items in the list"))
        self.update_ytdlp_button.SetLabel(_("Update yt-dlp"))
        self.update_ytdlp_button.SetName(_("Update yt-dlp"))
        self.update_ytdlp_button.SetToolTip(_("Check for and install updates for the yt-dlp library"))
        self.close_button.SetLabel(_("Close"))
        self.close_button.SetName(_("Close Downloader"))
        self.close_button.SetToolTip(_("Close the downloader window"))

        self.Layout()

    def _create_options_controls(self, sizer):
        format_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.mp3_checkbox = wx.CheckBox(self, label="")
        self.mp3_checkbox.SetValue(True)
        format_sizer.Add(self.mp3_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)

        self.format_label = wx.StaticText(self, label="")
        format_sizer.Add(self.format_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.audio_formats = [
            ("mp3", "MP3 (192 kbps)"),
            ("m4a", "M4A / AAC (192 kbps)"),
            ("opus", "OPUS (128 kbps)"),
            ("flac", "FLAC (Lossless)"),
            ("wav", "WAV (Lossless)"),
        ]
        self.format_choice = wx.Choice(self, choices=[name for _, name in self.audio_formats])
        
        saved_format = self.main_frame.settings.get("download_audio_format", "mp3").lower()
        default_idx = 0
        for i, (fmt_key, _) in enumerate(self.audio_formats):
            if fmt_key == saved_format:
                default_idx = i
                break
        self.format_choice.SetSelection(default_idx)
        format_sizer.Add(self.format_choice, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(format_sizer, 0, wx.ALL, 5)

        dir_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.dir_label = wx.StaticText(self, label="")
        dir_sizer.Add(self.dir_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        
        download_dir = self.main_frame.settings.get("download_dir", os.path.expanduser("~"))
        self.download_dir_text = wx.TextCtrl(self, value=download_dir)
        dir_sizer.Add(self.download_dir_text, 1, wx.EXPAND | wx.RIGHT, 5)

        self.browse_button = wx.Button(self, label="")
        dir_sizer.Add(self.browse_button, 0, wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(dir_sizer, 0, wx.EXPAND | wx.ALL, 5)

    def on_format_checkbox_toggled(self, event):
        has_mp3 = feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_MP3_CONVERSION)
        self.format_choice.Enable(has_mp3 and self.mp3_checkbox.IsChecked())
        if event: event.Skip()

    def on_format_choice_changed(self, event):
        sel = self.format_choice.GetSelection()
        if 0 <= sel < len(self.audio_formats):
            self.main_frame.settings["download_audio_format"] = self.audio_formats[sel][0]
        if event: event.Skip()

    def on_add_url(self, event=None, url=None):
        if self.is_downloading or self.is_busy_fetching_info: return
        
        urls_to_add = []
        if url:
            urls_to_add = url if isinstance(url, list) else [url]
        else:
            with MultiLinkEntryDialog(self, title=_("Add Link(s)"), message=_("Enter one or more YouTube links (one per line):")) as dlg:
                if dlg.ShowModal() == wx.ID_OK:
                    raw_text = dlg.get_value()
                    urls_to_add = [line.strip() for line in raw_text.splitlines() if line.strip()]
                else:
                    return # User cancelled

        if urls_to_add:
            self._log(_("Fetching info for {} item(s)...").format(len(urls_to_add)))
            self.is_busy_fetching_info = True
            wx.BeginBusyCursor()
            threading.Thread(target=self._fetch_info_for_list_thread, args=(urls_to_add,), daemon=True).start()

    def _fetch_info_for_list_thread(self, urls):
        """Worker thread to process a list of URLs sequentially."""
        try:
            for url in urls:
                if self.is_destroyed:
                    break
                self._process_single_url_info(url)
        finally:
            self.is_busy_fetching_info = False
            if not self.is_destroyed:
                wx.CallAfter(lambda: wx.EndBusyCursor() if wx.IsBusy() else None)
    
    def _process_single_url_info(self, url):
        """Fetches info for a single URL. Called by the worker thread."""
        import yt_dlp
        try:
            ydl_opts = {
                'skip_download': True,
                'extract_flat': True,
                'no_color': True,
                'nocheckcertificate': True,
            }
            import settings_manager
            cookies_path = settings_manager.get_effective_cookies_path(self.main_frame.settings)
            if cookies_path and os.path.exists(cookies_path):
                ydl_opts['cookiefile'] = cookies_path

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if self.is_destroyed: return

            if 'entries' in info and info.get('entries'): # Playlist or Channel
                wx.CallAfter(self._show_playlist_count_dialog, info)
            else: # Single video
                wx.CallAfter(self._add_item_to_gui, info)
        except Exception as e:
            wx.CallAfter(self._log, _("Error fetching info for '{}': {}").format(url, e))

    def _show_playlist_count_dialog(self, playlist_info):
        if self.is_destroyed: return
        
        entries = [e for e in playlist_info.get('entries', []) if e]
        if not entries:
            self._log(_("Playlist is empty or could not be loaded."))
            return
            
        playlist_type = _("Playlist") if playlist_info.get('_type') == 'playlist' else _("Channel")
        
        with PlaylistCountDialog(self, playlist_type, playlist_info.get('title', 'N/A'), len(entries)) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                count = dlg.get_selection_count()
                if count > 0:
                    videos_to_add = entries[:count]
                    self._log(_("Adding {} videos from {} '{}'").format(len(videos_to_add), playlist_type, playlist_info.get('title')))
                    for video_info in videos_to_add:
                        self._add_item_to_gui(video_info)

    def _add_item_to_gui(self, video_info):
        if self.is_destroyed: return
        
        if not video_info or 'id' not in video_info:
            self._log(_("Skipped adding an invalid item."))
            return
            
        item_data = {
            'title': video_info.get('title', 'N/A'),
            'url': video_info.get('webpage_url') or (f"https://www.youtube.com/watch?v={video_info['id']}" if video_info.get('id') else video_info.get('url')),
            'status': STATUS_QUEUED,
            'progress': '0%',
            'speed': '-',
            'eta': '-',
            'size': '-',
        }
        self.download_list_data.append(item_data)
        
        index = self.url_list_ctrl.GetItemCount()
        self.url_list_ctrl.InsertItem(index, item_data['title'])
        self.url_list_ctrl.SetItem(index, 1, _(item_data['status']))
        self.url_list_ctrl.SetItem(index, 2, item_data['progress'])
        self.url_list_ctrl.SetItem(index, 3, item_data['speed'])
        self.url_list_ctrl.SetItem(index, 4, item_data['eta'])
        self.url_list_ctrl.SetItem(index, 5, item_data['size'])
        self.url_list_ctrl.SetItem(index, 6, item_data['url'])
        self.url_list_ctrl.SetItemData(index, index)
        self.update_button_states()

    def on_download(self, event):
        if self.is_downloading: return
        
        download_dir = self.download_dir_text.GetValue().strip()
        if not download_dir or not os.path.isdir(download_dir):
            utils.show_error_dialog(self, _("Please select a valid download directory."))
            return
        self.main_frame.settings["download_dir"] = download_dir
        
        items_to_download = [item for item in self.download_list_data if item['status'] == STATUS_QUEUED]
        if not items_to_download:
            self._log(_("No items in queue to download."))
            return

        convert_to_audio = self.mp3_checkbox.IsChecked()
        sel_idx = self.format_choice.GetSelection()
        audio_format = self.audio_formats[sel_idx][0] if (hasattr(self, 'audio_formats') and 0 <= sel_idx < len(self.audio_formats)) else "mp3"
        self.main_frame.settings["download_audio_format"] = audio_format

        self.is_downloading = True
        self.update_button_states()
        self._log(_("Starting download process..."))
        self.download_thread = threading.Thread(target=self._download_thread, args=(download_dir, convert_to_audio, audio_format), daemon=True)
        self.download_thread.start()

    def _download_thread(self, download_dir, convert_to_audio, audio_format):
        import yt_dlp
        
        try:
             version = yt_dlp.version.__version__
             wx.CallAfter(self._log, f"yt-dlp version: {version}")
        except Exception:
             pass
        
        out_tmpl = os.path.join(download_dir, '%(title)s.%(ext)s')

        # Resolve bundled FFmpeg directory (in libs/)
        ffmpeg_dir = path_utils.get_resource_path('libs')
        ffmpeg_exe = os.path.join(ffmpeg_dir, 'ffmpeg.exe')
        has_bundled_ffmpeg = os.path.exists(ffmpeg_exe)

        for idx, item in enumerate(self.download_list_data):
            if self.is_destroyed:
                break
            if item['status'] != STATUS_QUEUED:
                continue

            self.current_download_idx = idx
            wx.CallAfter(self._update_item_progress_row, idx, STATUS_DOWNLOADING, '0%', '-', '-', '-')
            wx.CallAfter(self._log, _("Starting download ({}/{}): {}").format(idx + 1, len(self.download_list_data), item['title']))

            ydl_opts = {
                'progress_hooks': [self._yt_dlp_hook],
                'ignoreerrors': True,
                'outtmpl': out_tmpl,
                'download_archive': os.path.join(download_dir, 'downloaded.txt'),
                'retries': 10,
                'fragment_retries': 10,
                'file_access_retries': 3,
                'nocheckcertificate': True,
                'no_color': True,
                # High-speed optimizations:
                'concurrent_fragment_downloads': 8, # Multi-threaded parallel chunk downloads
                'http_chunk_size': 10485760,         # 10MB chunk size prevents YouTube rate-limiting
                'buffersize': 1024 * 1024,           # 1MB buffer reduces disk I/O overhead
                'socket_timeout': 20,
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                    }
                },
            }
            if has_bundled_ffmpeg:
                ydl_opts['ffmpeg_location'] = ffmpeg_dir

            import settings_manager
            cookies_path = settings_manager.get_effective_cookies_path(self.main_frame.settings)
            if cookies_path and os.path.exists(cookies_path):
                ydl_opts['cookiefile'] = cookies_path

            if convert_to_audio:
                ydl_opts['format'] = 'ba/b'
                pp_dict = {'key': 'FFmpegExtractAudio'}
                
                # Format options matching fast BotTeamTalk parameters (-threads 0)
                if audio_format == 'mp3':
                    pp_dict['preferredcodec'] = 'mp3'
                    pp_dict['preferredquality'] = '192'
                    ydl_opts['postprocessor_args'] = {
                        'FFmpegExtractAudio': ['-threads', '0', '-ar', '44100', '-ac', '2', '-b:a', '192k'],
                        'ffmpeg': ['-threads', '0']
                    }
                elif audio_format == 'm4a':
                    pp_dict['preferredcodec'] = 'm4a'
                    pp_dict['preferredquality'] = '192'
                    ydl_opts['postprocessor_args'] = {
                        'FFmpegExtractAudio': ['-threads', '0', '-c:a', 'aac', '-b:a', '192k'],
                        'ffmpeg': ['-threads', '0']
                    }
                elif audio_format == 'flac':
                    pp_dict['preferredcodec'] = 'flac'
                    ydl_opts['postprocessor_args'] = {
                        'FFmpegExtractAudio': ['-threads', '0', '-compression_level', '5'],
                        'ffmpeg': ['-threads', '0']
                    }
                elif audio_format == 'opus':
                    pp_dict['preferredcodec'] = 'opus'
                    pp_dict['preferredquality'] = '128'
                    ydl_opts['postprocessor_args'] = {
                        'FFmpegExtractAudio': ['-threads', '0', '-c:a', 'libopus', '-b:a', '128k'],
                        'ffmpeg': ['-threads', '0']
                    }
                elif audio_format == 'wav':
                    pp_dict['preferredcodec'] = 'wav'
                    ydl_opts['postprocessor_args'] = {
                        'FFmpegExtractAudio': ['-threads', '0'],
                        'ffmpeg': ['-threads', '0']
                    }
                else:
                    pp_dict['preferredcodec'] = 'mp3'
                    pp_dict['preferredquality'] = '192'
                    ydl_opts['postprocessor_args'] = {'ffmpeg': ['-threads', '0']}

                postprocessors = [pp_dict]
                if audio_format in ('mp3', 'm4a', 'opus', 'flac'):
                    ydl_opts['writethumbnail'] = True
                    postprocessors.append({'key': 'EmbedThumbnail'})
                ydl_opts['postprocessors'] = postprocessors
            else:
                ydl_opts['format'] = 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                ydl_opts['postprocessors'] = [{'key': 'FFmpegVideoRemuxer', 'preferedformat': 'mp4'}]
                ydl_opts['postprocessor_args'] = {
                    'ffmpeg': ['-threads', '0', '-c:v', 'copy', '-c:a', 'aac']
                }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([item['url']])
                if not self.is_destroyed and self.download_list_data[idx]['status'] not in (STATUS_FINISHED, STATUS_SKIPPED, STATUS_ERROR):
                    wx.CallAfter(self._update_item_progress_row, idx, STATUS_FINISHED, '100%', '-', '-', None)
            except Exception as e:
                wx.CallAfter(self._update_item_progress_row, idx, STATUS_ERROR, '-', '-', '-', '-')
                wx.CallAfter(self._log, _("Error downloading '{}': {}").format(item['title'], e))
        
        if not self.is_destroyed:
            wx.CallAfter(self._finalize_downloads)

    def _finalize_downloads(self):
        if self.is_destroyed: return
        self.is_downloading = False
        self.current_download_idx = -1
        self.update_button_states()
        self._log(_("Download process finished."))
        if feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_DOWNLOAD_NOTIFICATIONS):
            nvda.speak(_("All downloads are complete."))

    def _yt_dlp_hook(self, d):
        if self.is_destroyed: return
        
        current_item_idx = getattr(self, 'current_download_idx', -1)
        if current_item_idx == -1:
            for i, item in enumerate(self.download_list_data):
                if item['status'] in [STATUS_DOWNLOADING, STATUS_CONVERTING]:
                    current_item_idx = i
                    break
        if current_item_idx == -1: return

        status = d.get('status')
        filename = d.get('filename')
        info_dict = d.get('info_dict', {})

        if status == 'finished':
            if info_dict.get('was_downloaded') is False:
                wx.CallAfter(self._update_item_progress_row, current_item_idx, STATUS_SKIPPED, '100%', '-', '-', '-')
                wx.CallAfter(self._log, _("Skipped (already exists): {}").format(info_dict.get('title') or (os.path.basename(filename) if filename else 'File')))
            else:
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                size_str = utils.format_filesize(total_bytes) if total_bytes > 0 else '-'
                if not d.get('postprocessor'):
                    wx.CallAfter(self._update_item_progress_row, current_item_idx, STATUS_FINISHED, '100%', '-', '-', size_str)
                    wx.CallAfter(self._log, _("Finished downloading: {}").format(os.path.basename(filename) if filename else 'File'))
                    if feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_DOWNLOAD_NOTIFICATIONS):
                        wx.CallAfter(utils.play_sound, self.main_frame.settings, "download_item_complete")
                else:
                    wx.CallAfter(self._update_item_progress_row, current_item_idx, STATUS_CONVERTING, '100%', '-', '-', size_str)
                    wx.CallAfter(self._log, _("Converting: {}").format(os.path.basename(filename) if filename else 'File'))

        elif status == 'downloading':
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            
            pct_raw = self.ansi_escape.sub('', d.get('_percent_str', '')).strip()
            pct_clean = re.sub(r'[^0-9.]', '', pct_raw)
            if pct_clean:
                pct_str = f"{float(pct_clean):.1f}%"
            elif total > 0:
                pct_str = f"{(downloaded / total * 100):.1f}%"
            else:
                pct_str = utils.format_filesize(downloaded)

            speed_raw = self.ansi_escape.sub('', d.get('_speed_str', '')).strip()
            speed_raw = re.sub(r'\[.*?\]', '', speed_raw).strip()
            speed_str = speed_raw if speed_raw else ('-' if not d.get('speed') else utils.format_filesize(d['speed']) + '/s')

            eta_val = d.get('eta')
            if eta_val is not None and eta_val > 0:
                s = int(eta_val)
                if s < 60:
                    eta_str = _("about {s}s left").format(s=s)
                elif s < 3600:
                    m = round(s / 60)
                    eta_str = _("about {m}m left").format(m=m)
                else:
                    h = s // 3600
                    m = (s % 3600) // 60
                    eta_str = _("about {h}h {m}m left").format(h=h, m=m)
            else:
                eta_raw = self.ansi_escape.sub('', d.get('_eta_str', '')).strip()
                eta_raw = re.sub(r'\[.*?\]', '', eta_raw).strip()
                eta_str = eta_raw if eta_raw else '-'

            if total > 0:
                size_str = f"{utils.format_filesize(downloaded)} of {utils.format_filesize(total)}"
            else:
                size_str = utils.format_filesize(downloaded)

            now = time.time()
            if now - getattr(self, '_last_progress_ui_time', 0) >= 0.15:
                self._last_progress_ui_time = now
                human_status = _("Downloading in progress")
                wx.CallAfter(self._update_item_progress_row, current_item_idx, human_status, pct_str, speed_str, eta_str, size_str)

        elif status == 'postprocessing':
            wx.CallAfter(self._update_item_progress_row, current_item_idx, STATUS_CONVERTING, '100%', '-', '-', None)
            wx.CallAfter(self._log, _("Converting: {}").format(os.path.basename(filename) if filename else 'File'))

        elif status == 'error':
            wx.CallAfter(self._update_item_progress_row, current_item_idx, STATUS_ERROR, '-', '-', '-', '-')
            wx.CallAfter(self._log, _("Error during download."))

    def _update_item_progress_row(self, item_index, status=None, progress=None, speed=None, eta=None, size=None):
        if self.is_destroyed: return
        if not (0 <= item_index < len(self.download_list_data)): return
        
        item = self.download_list_data[item_index]
        if status is not None: item['status'] = status
        if progress is not None: item['progress'] = progress
        if speed is not None: item['speed'] = speed
        if eta is not None: item['eta'] = eta
        if size is not None: item['size'] = size
        
        for row in range(self.url_list_ctrl.GetItemCount()):
            if self.url_list_ctrl.GetItemData(row) == item_index:
                if status is not None:
                    self.url_list_ctrl.SetItem(row, 1, _(status))
                if progress is not None:
                    self.url_list_ctrl.SetItem(row, 2, progress)
                if speed is not None:
                    self.url_list_ctrl.SetItem(row, 3, speed)
                if eta is not None:
                    self.url_list_ctrl.SetItem(row, 4, eta)
                if size is not None:
                    self.url_list_ctrl.SetItem(row, 5, size)
                break

    def _update_item_status(self, item_index, new_status):
        self._update_item_progress_row(item_index, status=new_status)

    def _log(self, message):
        if self.is_destroyed or not message: return
        clean_msg = re.sub(r'\[\w+\]\s*', '', str(message)).strip()
        def do_log():
            if not self.is_destroyed and hasattr(self, 'status_bar_text'):
                self.status_bar_text.SetLabel(clean_msg)
        wx.CallAfter(do_log)

    def on_remove_item(self, event):
        selected_index = self.url_list_ctrl.GetFirstSelected()
        if selected_index == -1: return
        
        data_index_to_remove = self.url_list_ctrl.GetItemData(selected_index)
        del self.download_list_data[data_index_to_remove]
        
        self.populate_url_list()
        self.update_button_states()

    def on_clear_list(self, event):
        if not self.download_list_data: return
        
        with wx.MessageDialog(self, _("Are you sure you want to clear all items from the download list?"), _("Confirm Clear"), wx.YES_NO | wx.ICON_QUESTION) as dlg:
            utils.play_sound(self.main_frame.settings, "confirm_prompt")
            if dlg.ShowModal() == wx.ID_YES:
                self.download_list_data.clear()
                self.url_list_ctrl.DeleteAllItems()
                self.update_button_states()

    def populate_url_list(self):
        """Re-populates the URL list from the data list."""
        self.url_list_ctrl.DeleteAllItems()
        for i, item in enumerate(self.download_list_data):
            index = self.url_list_ctrl.InsertItem(i, item['title'])
            self.url_list_ctrl.SetItem(index, 1, _(item.get('status', STATUS_QUEUED)))
            self.url_list_ctrl.SetItem(index, 2, item.get('progress', '0%'))
            self.url_list_ctrl.SetItem(index, 3, item.get('speed', '-'))
            self.url_list_ctrl.SetItem(index, 4, item.get('eta', '-'))
            self.url_list_ctrl.SetItem(index, 5, item.get('size', '-'))
            self.url_list_ctrl.SetItem(index, 6, item.get('url', ''))
            self.url_list_ctrl.SetItemData(index, i)

    def update_button_states(self):
        has_selection = self.url_list_ctrl.GetFirstSelected() != -1
        has_items = len(self.download_list_data) > 0
        has_queued_items = any(item['status'] == STATUS_QUEUED for item in self.download_list_data)
        
        is_busy = self.is_downloading or self.is_busy_fetching_info
        
        self.add_button.Enable(not is_busy)
        self.remove_button.Enable(has_selection and not is_busy)
        self.clear_list_button.Enable(has_items and not is_busy)
        self.download_button.Enable(has_queued_items and not self.is_downloading)
        self.update_ytdlp_button.Enable(not is_busy)
        
        has_mp3 = feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_MP3_CONVERSION)
        self.mp3_checkbox.Enable(has_mp3 and not is_busy)
        if hasattr(self, 'format_choice'):
            self.format_choice.Enable(has_mp3 and self.mp3_checkbox.IsChecked() and not is_busy)
        self.browse_button.Enable(not is_busy)
        self.download_dir_text.Enable(not is_busy)

    def on_browse(self, event):
        with wx.DirDialog(self, _("Choose download directory"), self.download_dir_text.GetValue(), wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self.download_dir_text.SetValue(dlg.GetPath())

    def on_update_ytdlp(self, event):
        if self.is_downloading or self.is_busy_fetching_info: return
        self._log(_("Checking for yt-dlp updates..."))
        wx.BeginBusyCursor()
        threading.Thread(target=self.run_update_ytdlp, daemon=True).start()

    def run_update_ytdlp(self):
        def progress_callback(message):
            self._log(message)

        try:
            success, final_message = yt_dlp_manager.run_update_from_panel(progress_callback)
            nvda.speak(final_message)
        except Exception as e:
            error_msg = _("Update process failed: {}").format(e)
            self._log(error_msg)
            nvda.speak(error_msg)
        finally:
            def _end_busy():
                if wx.IsBusy(): wx.EndBusyCursor()
            wx.CallAfter(_end_busy)

    def on_close(self, event):
        if self.is_downloading:
            utils.show_message_dialog(self, _("A download is in progress. Please wait for it to finish before closing."), _("Download Active"), wx.OK | wx.ICON_WARNING)
            return
        if self.is_busy_fetching_info:
            utils.show_message_dialog(self, _("Fetching information for links. Please wait for it to finish before closing."), _("Operation in Progress"), wx.OK | wx.ICON_WARNING)
            return
        
        self.parent_dialog.Close()