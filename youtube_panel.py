import wx
import re
import threading
import webbrowser
import requests
import traceback
import time
import random
import os

# Local application imports
import nvda
import constants
import utils
import feature_manager
from translation_manager import _



# Import YouTube Music API library safely
try:
    from ytmusicapi import YTMusic
    YTMUSIC_ENABLED = True
except ImportError:
    YTMUSIC_ENABLED = False
    print("Warning: YouTube Music API not found. Please run 'pip install ytmusicapi' to enable YouTube Music search.")
from video_comments_dialog import VideoCommentsDialog

class YoutubeSearchPanel(wx.Panel):
    """
    A wx.Panel for searching YouTube, displaying results and related videos,
    and initiating playback or other actions.
    """
    def __init__(self, parent, main_frame):
        super().__init__(parent)
        self.main_frame = main_frame
        self.current_search_query = ""
        self.current_search_results = []
        self.shuffled_search_results = []
        self.total_results_displayed = 0
        self.results_per_page = constants.INITIAL_RESULTS_PER_PAGE
        self.next_playlist_item_to_load = 1 # For paginating playlists/channels
        self.search_thread = None
        self.youtube_link_pattern = re.compile(r'(https?://)?(www\.|m\.|music\.)?(youtube\.com/(watch\?v=|shorts/|live/|embed/|playlist\?list=)|youtu\.be/)([a-zA-Z0-9_-]+)')
        self.search_in_progress = False
        self.current_search_type = 'search'  # Can be 'search', 'playlist', 'channel', or 'ytmusic'
        self.related_videos_data = []
        self.radio_mode_queue = []
        
        # Search Suggestions
        self.suggestion_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_suggestion_timer, self.suggestion_timer)
        self.ignore_text_change = False

        # TurboStream: Prefetch debounce timer for instant playback on Enter
        self.prefetch_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_prefetch_timer, self.prefetch_timer)
        self._pending_prefetch_url = None

        # Persistent HTTP session and in-memory caches for blazingly fast queries
        self.http_session = requests.Session()
        self._video_details_cache = {}
        self._continuation_tokens = {}

        # --- YouTube Music API ---
        self.ytmusic = None

        self.InitUI()
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroy)

    def _on_destroy(self, event):
        if hasattr(self, 'http_session') and self.http_session:
            try:
                self.http_session.close()
            except Exception:
                pass
        event.Skip()

    def get_ytmusic(self):
        """Lazily initialize YTMusic instance off the UI thread."""
        global YTMUSIC_ENABLED
        if not YTMUSIC_ENABLED:
            return None
        if self.ytmusic is None:
            try:
                self.ytmusic = YTMusic()
            except Exception as e:
                print(f"Failed to initialize YTMusic API: {e}")
                YTMUSIC_ENABLED = False
                return None
        return self.ytmusic

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Search Input Area
        hbox_search = wx.BoxSizer(wx.HORIZONTAL)
        self.search_label = wx.StaticText(self, label="")
        hbox_search.Add(self.search_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        self.search_input = wx.ComboBox(self, style=wx.CB_DROPDOWN | wx.TE_PROCESS_ENTER, choices=[])
        hbox_search.Add(self.search_input, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=5)

        # Playlist Button
        self.playlist_button = wx.Button(self, label="")
        self.playlist_button.Bind(wx.EVT_BUTTON, self.on_playlist_button)
        hbox_search.Add(self.playlist_button, flag=wx.LEFT, border=5)

        vbox.Add(hbox_search, flag=wx.EXPAND | wx.ALL, border=10)

        # Status Text
        self.status_text = wx.StaticText(self, label="")
        vbox.Add(self.status_text, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        # Results and Related Videos Area
        hbox_results_area = wx.BoxSizer(wx.HORIZONTAL)

        results_list_sizer = wx.BoxSizer(wx.VERTICAL)
        self.results_list = wx.ListBox(self, style=wx.LB_SINGLE | wx.LB_HSCROLL | wx.WANTS_CHARS)
        # Bind events
        self.results_list.Bind(wx.EVT_LISTBOX, self.on_item_selected)
        self.results_list.Bind(wx.EVT_CONTEXT_MENU, self.show_context_menu)
        self.results_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_item_dclick)
        self.results_list.Bind(wx.EVT_KEY_DOWN, self.on_list_key_down)
        self.results_list.Bind(wx.EVT_SET_FOCUS, self.on_results_list_focus)
        results_list_sizer.Add(self.results_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        hbox_results_area.Add(results_list_sizer, proportion=3, flag=wx.EXPAND | wx.RIGHT, border=5)

        related_sizer = wx.BoxSizer(wx.VERTICAL)
        self.related_videos_list = wx.ListBox(self, style=wx.LB_SINGLE | wx.LB_HSCROLL | wx.WANTS_CHARS)
        self.related_videos_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_play_related_video)
        self.related_videos_list.Bind(wx.EVT_KEY_DOWN, self.on_related_list_key_down)
        self.related_videos_list.Bind(wx.EVT_LISTBOX, self.on_related_selection_change)
        self.related_videos_list.Bind(wx.EVT_CONTEXT_MENU, self.show_related_context_menu)
        self.related_videos_list.Bind(wx.EVT_SET_FOCUS, self.on_related_list_focus)
        related_sizer.Add(self.related_videos_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        hbox_results_area.Add(related_sizer, proportion=2, flag=wx.EXPAND | wx.LEFT, border=5)

        vbox.Add(hbox_results_area, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        hbox_buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.load_more_button = wx.Button(self, label="")
        self.load_more_button.Bind(wx.EVT_BUTTON, self.on_load_more)
        self.load_more_button.Hide()
        hbox_buttons.Add(self.load_more_button, flag=wx.RIGHT, border=10)

        self.run_ytdl_button = wx.Button(self, label="")
        self.run_ytdl_button.Bind(wx.EVT_BUTTON, self.on_run_ytdl)
        hbox_buttons.Add(self.run_ytdl_button, flag=wx.RIGHT, border=10)

        hbox_buttons.AddStretchSpacer(prop=1)

        self.exit_button = wx.Button(self, label="")
        self.exit_button.Bind(wx.EVT_BUTTON, self.on_exit)
        hbox_buttons.Add(self.exit_button, flag=wx.LEFT, border=10)

        vbox.Add(hbox_buttons, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        self.SetSizer(vbox)

        self.update_tab_order()
        self.retranslate_ui()
        self.search_input.Bind(wx.EVT_TEXT, self.on_search_text_change)
        self.search_input.Bind(wx.EVT_TEXT_ENTER, self.on_search)
        self.load_search_history_to_combobox()
        self.search_input.SetFocus()

    def update_tab_order(self):
        """Chains visible controls cleanly to ensure smooth keyboard and screen reader traversal."""
        try:
            controls = [self.search_input]
            if hasattr(self, 'playlist_button') and self.playlist_button.IsShown():
                controls.append(self.playlist_button)
            if hasattr(self, 'results_list') and self.results_list.IsShown():
                controls.append(self.results_list)
            if hasattr(self, 'related_videos_list') and self.related_videos_list.IsShown():
                controls.append(self.related_videos_list)
            if hasattr(self, 'load_more_button') and self.load_more_button.IsShown():
                controls.append(self.load_more_button)
            if hasattr(self, 'run_ytdl_button') and self.run_ytdl_button.IsShown():
                controls.append(self.run_ytdl_button)
            if hasattr(self, 'exit_button') and self.exit_button.IsShown():
                controls.append(self.exit_button)

            for i in range(1, len(controls)):
                controls[i].MoveAfterInTabOrder(controls[i - 1])
        except Exception as e:
            print(f"Tab order update warning: {e}")

    def retranslate_ui(self):
        """Updates all translatable text on the panel."""
        self.search_label.SetLabel(_("Search YouTube:"))
        self.search_input.SetName(_("Search YouTube"))
        self.search_input.SetToolTip(_("Enter search terms, a YouTube URL, or select from previous searches (up to {max_items}). Press Enter to search. (Ctrl+F to focus).").format(max_items=constants.MAX_YT_SEARCH_HISTORY_ITEMS))

        has_playlists = feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_PLAYLISTS)
        self.playlist_button.Show(has_playlists)
        self.playlist_button.SetLabel(_("Playlist"))
        self.playlist_button.SetName(_("Playlist"))
        self.playlist_button.SetToolTip(_("Import or Export playlists (M3U, PLS)."))

        self.results_list.SetName(_("Search Results"))
        self.results_list.SetToolTip(_("List of YouTube search results or playlist items. Right-click for options. Double-click or Enter to play."))

        is_radio = bool(getattr(self.main_frame, 'audio_player_panel', None) and self.main_frame.audio_player_panel.is_radio_mode)
        self.related_videos_list.SetName(_("Radio Queue") if is_radio else _("Related Videos"))
        self.related_videos_list.SetToolTip(_("List of related videos or the current radio queue. Double-click or Enter to play."))

        if not self.related_videos_data:
             self.related_videos_list.Clear()
             self.related_videos_list.Append(_("Play a video to see related items."), clientData=None)

        if not self.current_search_results:
             self.results_list.Clear()
             self.results_list.Append(_("No search results yet. Type a query above and press Enter to search."), clientData=None)

        self.load_more_button.SetLabel(_("Load More Results"))
        self.load_more_button.SetName(_("Load More Results"))
        self.load_more_button.SetToolTip(_("Load the next batch of results."))

        has_downloader = feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_DOWNLOADER)
        self.run_ytdl_button.Show(has_downloader)
        self.run_ytdl_button.SetLabel(_("Open YouTube Downloader"))
        self.run_ytdl_button.SetName(_("Open YouTube Downloader"))
        self.run_ytdl_button.SetToolTip(_("Open the YouTube Downloader window."))

        self.exit_button.SetLabel(_("Exit Application"))
        self.exit_button.SetName(_("Exit Application"))
        self.exit_button.SetToolTip(_("Exit the application."))

        current_status = self.status_text.GetLabel()
        if not self.current_search_results:
             if "Loading" in current_status or "Searching" in current_status:
                  pass
             elif self.current_search_query:
                  self.status_text.SetLabel(_("No results found for '{query}'.").format(query=self.current_search_query))
             else:
                  self.status_text.SetLabel(_("Search YouTube by typing a query above."))

        self.update_tab_order()
        self.Layout()

    def on_search(self, event):
        query = self.search_input.GetValue().strip()
        if not query: return
        if self.search_in_progress:
            utils.show_message_dialog(self, _("A search is already in progress. Please wait."), _("Busy"), wx.OK | wx.ICON_WARNING)
            return

        self._reset_search_state(query)

        search_mode = self.main_frame.settings.get("search_mode", "youtube")
        if search_mode == "ytmusic":
            self._start_ytmusic_search(query)
        else:
            self._start_youtube_search(query)

    def on_search_text_change(self, event):
        """Handles text changes for live suggestions."""
        if self.ignore_text_change: return
        if not feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_SEARCH_SUGGESTIONS):
            event.Skip()
            return
        
        # Debounce: Restart timer on every keystroke
        self.suggestion_timer.Stop()
        self.suggestion_timer.Start(2000, wx.TIMER_ONE_SHOT)
        event.Skip()

    def on_suggestion_timer(self, event):
        """Called when debounce timer expires."""
        if not feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_SEARCH_SUGGESTIONS):
            return

        query = self.search_input.GetValue().strip()
        if not query or len(query) < 3: return # Don't suggest for short queries
        
        # Check setting
        if not self.main_frame.settings.get("enable_search_suggestions", True): return

        # Don't suggest if it looks like a URL
        if self.youtube_link_pattern.match(query) or query.startswith('http'): return

        threading.Thread(target=self._fetch_suggestions_thread, args=(query,), daemon=True).start()

    def _fetch_suggestions_thread(self, query):
        try:
            url = f"https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q={requests.utils.quote(query)}"
            response = self.http_session.get(url, timeout=2)
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 1:
                    suggestions = data[1]
                    wx.CallAfter(self.update_suggestions_ui, suggestions, query)
        except Exception:
            pass

    def update_suggestions_ui(self, suggestions, original_query):
        """Updates the combobox items without messing up typing."""
        if not self or not suggestions or self.search_in_progress:
            return
        
        # Check if user has typed significantly more since search started
        current_val = self.search_input.GetValue()
        if not current_val.startswith(original_query[:2]): return
        
        # limit to 10 suggestions
        suggestions = suggestions[:10]
        
        self.ignore_text_change = True
        current_insertion = self.search_input.GetInsertionPoint()
        
        # Update list but keep text
        self.search_input.SetItems(suggestions)
        self.search_input.SetValue(current_val)
        self.search_input.SetInsertionPoint(current_insertion)
        
        # Explicitly clear selection to prevent overwriting next typed char
        # Some wxWidgets versions select all on SetValue
        self.search_input.SetSelection(current_insertion, current_insertion)
        
        # Show dropdown if not empty (Windows specific behavior might vary)
        if hasattr(self.search_input, 'Popup'):
            self.search_input.Popup()
            
        self.ignore_text_change = False

    def _reset_search_state(self, query):
        """Resets the UI and internal state for a new search."""
        self.current_search_query = query
        self.current_search_results = []
        self.shuffled_search_results = []
        self.total_results_displayed = 0
        self.next_playlist_item_to_load = 1
        self.results_list.Clear()
        self.results_list.Append(_("Searching... Please wait."), clientData=None)
        self.load_more_button.Hide()
        if hasattr(self, 'related_videos_list'):
            self.related_videos_list.Clear()
            self.related_videos_list.Append(_("Search/load new video to see related items."), clientData=None)
            self.related_videos_data = []

    def _set_ui_busy(self, is_busy, status_message=""):
        """Sets the UI to a busy or idle state."""
        self.search_in_progress = is_busy
        self.search_input.Enable(not is_busy)
        self.playlist_button.Enable(not is_busy)
        self.results_list.Enable(not is_busy)
        
        if is_busy:
            self.status_text.SetLabel(status_message)
            nvda.speak(status_message, constants.NVDA_VERBOSITY_DEFAULT)
            wx.BeginBusyCursor()
        else:
            if wx.IsBusy():
                wx.EndBusyCursor()

    def _start_youtube_search(self, query, is_load_more=False):
        """Handles the logic for starting a standard YouTube search."""
        if not is_load_more:
            normalized_query = query.lower().strip()
            search_cache = self.main_frame.settings.get('search_results_cache', {})

            is_playlist = 'playlist?list=' in query
            is_channel = '/channel/' in query or '/c/' in query or '/user/' in query or (query.startswith('https://www.youtube.com/@'))
            is_single_video = self.youtube_link_pattern.match(query) and not is_playlist and not is_channel
            is_search_term = not is_playlist and not is_channel and not is_single_video

            search_type = 'search'
            if is_playlist: search_type = 'playlist'
            elif is_channel: search_type = 'channel'
            self.current_search_type = search_type

            if is_search_term:
                self.add_query_to_search_history(query)
                if normalized_query in search_cache:
                    cached_results = search_cache[normalized_query]
                    nvda.speak(_("Loading from cache..."), constants.NVDA_VERBOSITY_VERBOSE)
                    self.finalize_search_ui(cached_results, None, 'search', None, from_cache=True)
                    return

            if is_single_video:
                self.status_text.SetLabel(_("Playing direct video link..."))
                nvda.speak(_("Playing direct link."), constants.NVDA_VERBOSITY_DEFAULT)
                wx.CallAfter(self.main_frame.request_audio_play_direct_link, query)
                return
        
        status_msg_map = {
            'playlist': _("Loading playlist items..."),
            'channel': _("Loading channel videos..."),
            'search': _("Searching videos...")
        }
        status_msg = status_msg_map.get(self.current_search_type)
        if is_load_more:
            status_msg = _("Loading more...")

        self._set_ui_busy(True, status_msg)
        self.search_thread = threading.Thread(target=self.run_youtube_search, args=(query, self.current_search_type, is_load_more), daemon=True)
        self.search_thread.start()
        
    def _start_ytmusic_search(self, query):
        """Handles the logic for starting a YouTube Music search."""
        if not YTMUSIC_ENABLED:
            utils.show_error_dialog(self.main_frame, _("YouTube Music search is unavailable. Please install the 'ytmusicapi' library."), _("Component Missing"))
            return

        self.current_search_type = 'ytmusic'
        self.add_query_to_search_history(query)
        self._set_ui_busy(True, _("Searching YouTube Music..."))
        self.search_thread = threading.Thread(target=self.run_ytmusic_search, args=(query,), daemon=True)
        self.search_thread.start()

    def _get_base_ydl_opts(self):
        """Returns a base dictionary of yt-dlp options, including cookie settings."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'skip_download': True,
            'ignoreerrors': True,
            'check_formats': False,
            'forcejson': True,
            'nocheckcertificate': True,
            'socket_timeout': 6,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'player_skip': ['configs', 'webpage']
                }
            },
        }
        import settings_manager
        cookies_path = settings_manager.get_effective_cookies_path(self.main_frame.settings)
        if cookies_path and os.path.exists(cookies_path):
            ydl_opts['cookiefile'] = cookies_path
        return ydl_opts

    def _on_prefetch_timer(self, event):
        if self._pending_prefetch_url and hasattr(self.main_frame, 'audio_player_panel'):
            target_url = self._pending_prefetch_url
            self._pending_prefetch_url = None
            self.main_frame.audio_player_panel.prefetch_stream_url(target_url)

    def _trigger_prefetch_for_url(self, url):
        if not url:
            return
        self._pending_prefetch_url = url
        if self.prefetch_timer.IsRunning():
            self.prefetch_timer.Stop()
        self.prefetch_timer.StartOnce(300)

    def _search_youtube_innertube(self, query, continuation=None):
        """
        Ultra-fast direct YouTube InnerTube search API request.
        Bypasses heavy yt-dlp initialization, executing in ~0.3-0.5s.
        Returns (results_list, next_continuation_token).
        """
        url = "https://www.youtube.com/youtubei/v1/search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
        data = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20240101.00.00",
                    "hl": "en",
                    "gl": "US"
                }
            }
        }
        if continuation:
            data["continuation"] = continuation
        else:
            data["query"] = query

        resp = self.http_session.post(url, headers=headers, json=data, timeout=6)
        if resp.status_code != 200:
            return [], None

        j = resp.json()
        results = []
        next_continuation = None

        try:
            section_list = j.get('contents', {}).get('twoColumnSearchResultsRenderer', {}).get('primaryContents', {}).get('sectionListRenderer', {}).get('contents', [])
            if not section_list:
                for act in j.get('onResponseReceivedCommands', []):
                    items = act.get('appendContinuationItemsAction', {}).get('continuationItems', [])
                    section_list.append({'itemSectionRenderer': {'contents': items}})

            for sec in section_list:
                item_sec = sec.get('itemSectionRenderer', {}).get('contents', [])
                for item in item_sec:
                    if 'continuationItemRenderer' in item:
                        next_continuation = item['continuationItemRenderer']['continuationEndpoint']['continuationCommand']['token']
                        continue
                    vr = item.get('videoRenderer')
                    if not vr: continue
                    vid = vr.get('videoId')
                    if not vid: continue
                    title = ''.join(r.get('text', '') for r in vr.get('title', {}).get('runs', []))
                    uploader = ''.join(r.get('text', '') for r in vr.get('ownerText', {}).get('runs', []))
                    duration_str = vr.get('lengthText', {}).get('simpleText', '')
                    channel_url = ''
                    channel_id = ''
                    owner_runs = vr.get('ownerText', {}).get('runs', [])
                    if owner_runs:
                        nav_endpoint = owner_runs[0].get('navigationEndpoint', {})
                        channel_id = nav_endpoint.get('browseEndpoint', {}).get('browseId', '')
                        nav_meta = nav_endpoint.get('commandMetadata', {}).get('webCommandMetadata', {})
                        channel_path = nav_meta.get('url', '')
                        if channel_path:
                            channel_url = f'https://www.youtube.com{channel_path}'
                    results.append({
                        'id': vid,
                        'url': f'https://www.youtube.com/watch?v={vid}',
                        'title': title or 'Unknown Title',
                        'uploader': uploader or 'Unknown Artist',
                        'duration_string': duration_str,
                        'channel_url': channel_url,
                        'channel_id': channel_id,
                        'source': 'youtube'
                    })
        except Exception as e:
            print(f"InnerTube search parse error: {e}")

        return results, next_continuation

    def _fetch_channel_videos_innertube(self, channel_identifier):
        """
        Ultra-fast direct InnerTube channel browse endpoint fetcher.
        Bypasses yt-dlp, retrieving 30+ channel videos directly in ~1s.
        Returns (results_list, channel_title).
        """
        browse_id = None
        if isinstance(channel_identifier, str):
            if channel_identifier.startswith('UC') and len(channel_identifier) >= 22:
                browse_id = channel_identifier
            elif '/channel/' in channel_identifier:
                m = re.search(r'/channel/(UC[a-zA-Z0-9_-]+)', channel_identifier)
                if m:
                    browse_id = m.group(1)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json"
        }

        # If browse_id is not yet known (e.g. @handle was passed), resolve it via quick lightweight request
        if not browse_id and isinstance(channel_identifier, str):
            handle_url = channel_identifier
            if not handle_url.startswith('http'):
                handle_url = f"https://www.youtube.com/{channel_identifier.lstrip('/')}"
            try:
                resp = self.http_session.get(handle_url, headers={"User-Agent": headers["User-Agent"]}, timeout=3, stream=True)
                html_chunk = resp.raw.read(150000, decode_content=True).decode('utf-8', errors='ignore')
                resp.close()
                m = re.search(r'browseId[\":\s]+(UC[a-zA-Z0-9_-]+)', html_chunk)
                if m:
                    browse_id = m.group(1)
            except Exception:
                pass

        if not browse_id:
            return [], None

        url = "https://www.youtube.com/youtubei/v1/browse"
        payload = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20240101.00.00",
                    "hl": "en",
                    "gl": "US"
                }
            },
            "browseId": browse_id,
            "params": "EgZ2aWRlb3PyBgQKAjoA"
        }
        cookies_path = None
        try:
            import settings_manager
            cookies_path = settings_manager.get_effective_cookies_path(self.main_frame.settings)
        except Exception:
            pass

        req_headers = dict(headers)
        if cookies_path and os.path.exists(cookies_path):
            try:
                import http.cookiejar
                cj = http.cookiejar.MozillaCookieJar(cookies_path)
                cj.load(ignore_discard=True, ignore_expires=True)
                cookie_str = "; ".join(f"{c.name}={c.value}" for c in cj if "youtube.com" in c.domain)
                if cookie_str:
                    req_headers["Cookie"] = cookie_str
            except Exception:
                pass

        resp = self.http_session.post(url, json=payload, headers=req_headers, timeout=6)
        if resp.status_code != 200:
            return [], None

        data = resp.json()
        results = []
        channel_title = data.get('header', {}).get('c4TabbedHeaderRenderer', {}).get('title', '')
        if not channel_title:
            channel_title = data.get('metadata', {}).get('channelMetadataRenderer', {}).get('title', '')

        tabs = data.get('contents', {}).get('twoColumnBrowseResultsRenderer', {}).get('tabs', [])
        for tab in tabs:
            tr = tab.get('tabRenderer', {})
            if tr.get('selected') or tr.get('title') in ['Videos', 'Uploads']:
                content = tr.get('content', {})
                rich_grid = content.get('richGridRenderer', {})
                for it in rich_grid.get('contents', []):
                    fc = it.get('richItemRenderer', {}).get('content', {})
                    # Format 1: lockupViewModel
                    lvm = fc.get('lockupViewModel')
                    if lvm and lvm.get('contentId'):
                        vid = lvm.get('contentId')
                        meta = lvm.get('metadata', {}).get('lockupMetadataViewModel', {})
                        title = meta.get('title', {}).get('content', '')
                        results.append({
                            'id': vid,
                            'url': f'https://www.youtube.com/watch?v={vid}',
                            'title': title or 'Unknown Title',
                            'uploader': channel_title or 'Unknown Channel',
                            'duration_string': '',
                            'channel_id': browse_id,
                            'source': 'youtube'
                        })
                        continue

                    # Format 2: videoRenderer
                    vr = fc.get('videoRenderer')
                    if vr and vr.get('videoId'):
                        vid = vr.get('videoId')
                        title = ''.join(r.get('text', '') for r in vr.get('title', {}).get('runs', []))
                        uploader = ''.join(r.get('text', '') for r in vr.get('ownerText', {}).get('runs', [])) or channel_title
                        duration_str = vr.get('lengthText', {}).get('simpleText', '')
                        results.append({
                            'id': vid,
                            'url': f'https://www.youtube.com/watch?v={vid}',
                            'title': title or 'Unknown Title',
                            'uploader': uploader or channel_title or 'Unknown Channel',
                            'duration_string': duration_str,
                            'channel_id': browse_id,
                            'source': 'youtube'
                        })
        return results, channel_title

    def run_youtube_search(self, query, search_type, is_load_more=False):
        fetched_results, error_msg, list_title = [], None, None
        try:
            if not utils.is_internet_available():
                raise requests.exceptions.ConnectionError(_("No internet connection detected."))

            # Fast-path 1: Direct InnerTube search for standard keyword queries
            if search_type == 'search':
                cont_token = self._continuation_tokens.get(query) if is_load_more else None
                try:
                    innertube_results, next_cont = self._search_youtube_innertube(query, continuation=cont_token)
                    if innertube_results:
                        fetched_results = innertube_results
                        if len(self._continuation_tokens) >= 20:
                            self._continuation_tokens.pop(next(iter(self._continuation_tokens)))
                        self._continuation_tokens[query] = next_cont
                except Exception as it_err:
                    print(f"InnerTube search fast-path failed, falling back to yt-dlp: {it_err}")

            # Fast-path 2: Direct InnerTube browse for Channel exploration
            if search_type == 'channel' and not is_load_more and not fetched_results:
                try:
                    ch_results, ch_title = self._fetch_channel_videos_innertube(query)
                    if ch_results:
                        fetched_results = ch_results
                        if ch_title:
                            list_title = ch_title
                except Exception as ch_err:
                    print(f"InnerTube channel fast-path failed, falling back to yt-dlp: {ch_err}")

            # Fallback or Playlist/Channel search via yt-dlp
            if not fetched_results and (search_type in ['playlist', 'channel'] or not is_load_more):
                import yt_dlp
                ydl_opts = self._get_base_ydl_opts()
                ydl_opts['extract_flat'] = 'in_playlist' # Much faster for searches and playlists
                if search_type == 'channel':
                    # Remove player_skip and android player_client for channels so yt-dlp extracts properly
                    ydl_opts.pop('extractor_args', None)

                search_target = query
                if search_type in ['playlist', 'channel']:
                    if search_type == 'channel' and not query.rstrip('/').endswith('/videos'):
                        search_target = query.rstrip('/') + '/videos'
                    ydl_opts['playliststart'] = self.next_playlist_item_to_load
                    ydl_opts['playlistend'] = self.next_playlist_item_to_load + self.results_per_page - 1
                else: # Standard search fallback
                    search_target = f"ytsearch{self.results_per_page}:{query}"

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    result = ydl.extract_info(search_target, download=False)
                    if result:
                        entries = result.get('entries')
                        if entries is not None:
                            fetched_results = [e for e in entries if e and isinstance(e, dict) and e.get('id') and e.get('title')]
                            if search_type in ['playlist', 'channel']:
                                list_title = result.get('title', 'Playlist/Channel')
                        elif 'id' in result and result.get('title'):
                            fetched_results = [result]

        except Exception as e:
            error_msg = _("An error occurred: ") + str(e)
            traceback.print_exc()
        finally:
            for entry in fetched_results:
                if entry and not entry.get('url'):
                    entry['url'] = f"https://www.youtube.com/watch?v={entry['id']}"
            
            if search_type in ['playlist', 'channel']:
                self.next_playlist_item_to_load += len(fetched_results)
                
            wx.CallAfter(self.finalize_search_ui, fetched_results, error_msg, search_type, list_title)

    def run_ytmusic_search(self, query):
        fetched_results, error_msg = [], None
        try:
            if not utils.is_internet_available():
                raise requests.exceptions.ConnectionError(_("No internet connection detected."))

            ytm = self.get_ytmusic()
            if not ytm:
                raise RuntimeError(_("YouTube Music API is not available."))
            raw_results = ytm.search(query, filter="songs", limit=50)
            fetched_results = self._parse_ytmusic_results(raw_results)

        except Exception as e:
            error_msg = _("An error occurred during YouTube Music search: ") + str(e)
            traceback.print_exc()
        finally:
            wx.CallAfter(self.finalize_search_ui, fetched_results, error_msg, 'ytmusic', None)

    def _parse_ytmusic_results(self, raw_results):
        parsed = []
        for item in raw_results:
            if not item or item.get('videoId') is None:
                continue

            artists = ", ".join([artist['name'] for artist in item.get('artists', []) if artist.get('name')])
            channel_id = item.get('artists')[0].get('id') if item.get('artists') and item['artists'][0].get('id') else None

            parsed.append({
                'id': item['videoId'],
                'url': f"https://www.youtube.com/watch?v={item['videoId']}",
                'title': item.get('title', 'No Title'),
                'uploader': artists or 'Unknown Artist',
                'duration': item.get('duration_seconds'),
                'duration_string': item.get('duration'),
                'channel_url': f"https://music.youtube.com/channel/{channel_id}" if channel_id else "",
                'source': 'ytmusic'
            })
        return parsed

    def finalize_search_ui(self, fetched_results, error_msg, search_type, list_title=None, from_cache=False):
        self._set_ui_busy(False)

        if error_msg:
            fail_msg = _("Search failed.")
            self.status_text.SetLabel(fail_msg)
            nvda.speak(fail_msg, constants.NVDA_VERBOSITY_QUIET)
            self.results_list.Clear()
            self.results_list.Append(_("Search failed. Please try again."), clientData=None)
            utils.show_error_dialog(self.main_frame, error_msg, _("Search/Load Error"))
            self.load_more_button.Hide()
        else:
            if not from_cache and search_type == 'search' and fetched_results and not self.current_search_results:
                cache = self.main_frame.settings.setdefault('search_results_cache', {})
                cache[self.current_search_query.lower().strip()] = fetched_results
                while len(cache) > 20:
                    oldest_key = next(iter(cache))
                    del cache[oldest_key]

            existing_ids = {entry.get('id') for entry in self.current_search_results}
            new_results_to_add = [e for e in fetched_results if e and e.get('id') not in existing_ids and e.get('title')]

            if not self.current_search_results:
                self.results_list.Clear()

            for entry in new_results_to_add:
                self.current_search_results.append(entry)
                
                title = entry.get('title', 'No Title')
                uploader = entry.get('uploader', 'No Uploader')
                duration_str = entry.get('duration_string') or utils.format_duration(entry.get('duration'))
                upload_date_str = utils.format_upload_date(entry.get('upload_date'))
                
                list_string = f"{title}. duration: {duration_str} uploaded by {uploader}"
                if upload_date_str != _("Unknown Date") and upload_date_str != _("Invalid Date"):
                    list_string += f", {_('uploaded')} {upload_date_str}"
                
                self.results_list.Append(list_string, clientData=entry)

            self.total_results_displayed = len(self.current_search_results)

            if self.total_results_displayed == 0:
                self.results_list.Clear()
                self.results_list.Append(_("No results found for '{query}'.").format(query=self.current_search_query), clientData=None)

            if self.main_frame.settings.get("shuffle_mode", False):
                self.generate_shuffled_list()

            num_fetched_for_status = len(fetched_results)
            self._update_status_and_load_more_button(search_type, list_title, len(new_results_to_add), num_fetched_for_status, from_cache)

        if self.total_results_displayed > 0:
            self.results_list.SetFocus()
            # Predictive TurboStream: Pre-cache top result so hitting Enter immediately is instant
            if self.current_search_results:
                first_url = self.current_search_results[0].get('url')
                if first_url:
                    if hasattr(self.main_frame, 'audio_player_panel'):
                        self.main_frame.audio_player_panel.prefetch_stream_url(first_url)
                    # Automatically fetch related videos for the top search result so Related Items is populated
                    self.start_related_videos_fetch(first_url)
        else:
            self.search_input.SetFocus()

    def _update_status_and_load_more_button(self, search_type, list_title, num_new_added, num_fetched, from_cache=False):
        num_total = self.total_results_displayed
        status_label = ""

        if num_total == 0:
            status_label = _("No results found for '{query}'.").format(query=self.current_search_query)
            nvda.speak(_("No results found."), constants.NVDA_VERBOSITY_DEFAULT)
        else:
            if from_cache:
                status_label = _("Displaying {num_total} cached results for '{query}'.").format(num_total=num_total, query=self.current_search_query)
                nvda.speak(_("Loaded {num_total} results from cache.").format(num_total=num_total), constants.NVDA_VERBOSITY_DEFAULT)
            elif search_type == 'ytmusic':
                status_label = _("Displaying {num_total} results from YouTube Music.").format(num_total=num_total)
                nvda.speak(_("Found {num_total} results from YouTube Music.").format(num_total=num_total), constants.NVDA_VERBOSITY_DEFAULT)
            else: # Covers search, playlist, and channel
                status_label = _("Displaying {num_total} results (added {num_new_added}).").format(num_total=num_total, num_new_added=num_new_added)
                nvda.speak(_("Added {num_new_added} results. Total {num_total}.").format(num_new_added=num_new_added, num_total=num_total), constants.NVDA_VERBOSITY_DEFAULT)

        self.status_text.SetLabel(status_label)

        can_load_more = search_type != 'ytmusic' and num_fetched >= self.results_per_page
        self.load_more_button.Show(can_load_more)
        self.update_tab_order()
        self.Layout()

    def on_load_more(self, event):
        if self.search_in_progress: return
        
        if self.current_search_type == 'search':
            self.results_per_page += constants.RESULTS_PER_PAGE_INCREMENT
            self._start_youtube_search(self.current_search_query, is_load_more=True)
        elif self.current_search_type in ['playlist', 'channel']:
            self._start_youtube_search(self.current_search_query, is_load_more=True)

    def start_related_videos_fetch(self, video_url):
        if not video_url or not hasattr(self, 'related_videos_list'): return
        self.related_videos_list.Clear()
        self.related_videos_list.Append(_("Loading related videos..."), clientData=None)
        self.related_videos_data = []
        threading.Thread(target=self._fetch_related_videos_thread, args=(video_url,), daemon=True).start()

    def _fetch_innertube_related(self, video_id):
        url = "https://www.youtube.com/youtubei/v1/next"
        payload = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20240101.00.00",
                    "hl": "en",
                    "gl": "US"
                }
            },
            "videoId": video_id
        }
        resp = self.http_session.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            timeout=8
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        
        results = data.get("contents", {}).get("twoColumnWatchNextResults", {}).get("secondaryResults", {}).get("secondaryResults", {}).get("results", [])
        items = []
        seen_ids = {video_id}
        for r in results:
            lockup = r.get("lockupViewModel")
            compact = r.get("compactVideoRenderer")
            if lockup:
                cid = lockup.get("contentId")
                if not cid or cid in seen_ids:
                    continue
                meta = lockup.get("metadata", {}).get("lockupMetadataViewModel", {})
                title = meta.get("title", {}).get("content", "Unknown Title")
                
                uploader = "Unknown Uploader"
                rows = meta.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
                if rows:
                    parts = rows[0].get("metadataParts", [])
                    if parts and "text" in parts[0]:
                        uploader = parts[0]["text"].get("content", uploader)
                if uploader == "Unknown Uploader":
                    a11y = meta.get("image", {}).get("decoratedAvatarViewModel", {}).get("a11yLabel", "")
                    if a11y.startswith("Go to channel "):
                        uploader = a11y[len("Go to channel "):]
                
                duration = ""
                overlays = lockup.get("contentImage", {}).get("thumbnailViewModel", {}).get("overlays", [])
                for ov in overlays:
                    bottom = ov.get("thumbnailBottomOverlayViewModel", {})
                    for b in bottom.get("badges", []):
                        t = b.get("thumbnailBadgeViewModel", {}).get("text")
                        if t:
                            duration = t
                            break
                    if duration: break

                items.append({
                    "id": cid,
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={cid}",
                    "uploader": uploader,
                    "duration_string": duration
                })
                seen_ids.add(cid)
            elif compact:
                cid = compact.get("videoId")
                if not cid or cid in seen_ids:
                    continue
                title_runs = compact.get("title", {}).get("runs", [])
                title = "".join(run.get("text", "") for run in title_runs) or "Unknown Title"
                uploader_runs = compact.get("shortBylineText", {}).get("runs", [])
                uploader = "".join(run.get("text", "") for run in uploader_runs) or "Unknown Uploader"
                duration = compact.get("lengthText", {}).get("simpleText", "")
                items.append({
                    "id": cid,
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={cid}",
                    "uploader": uploader,
                    "duration_string": duration
                })
                seen_ids.add(cid)
        return items

    def _fetch_related_videos_thread(self, video_url):
        related_items, error_msg = [], None
        video_id = None
        if video_url:
            match = re.search(r'(?:v=|\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', video_url)
            if match:
                video_id = match.group(1)
        
        # 1. Primary: High-speed InnerTube next endpoint
        if video_id:
            try:
                related_items = self._fetch_innertube_related(video_id)
            except Exception as e:
                print(f"InnerTube related fetch error: {e}")

        # 2. Secondary: If search mode is ytmusic and empty, try YTMusic
        if not related_items and video_id and self.main_frame.settings.get("search_mode") == "ytmusic" and YTMUSIC_ENABLED:
            try:
                ytm = self.get_ytmusic()
                raw_related = ytm.get_watch_playlist(video_id, limit=50) if ytm else None
                if raw_related and 'tracks' in raw_related:
                    seen_ids = {video_id}
                    for item in raw_related['tracks']:
                        if item and item.get('videoId') and item['videoId'] not in seen_ids:
                            artists = ", ".join([artist['name'] for artist in item.get('artists', []) if artist.get('name')])
                            vid_id = item['videoId']
                            related_items.append({
                                'id': vid_id, 'title': item.get('title', 'Unknown Title'),
                                'url': f"https://www.youtube.com/watch?v={vid_id}",
                                'uploader': artists or 'Unknown Artist', 'duration_string': item.get('length')
                            })
                            seen_ids.add(vid_id)
            except Exception as e:
                print(f"YTMusic related fetch error: {e}")

        # 3. Tertiary: Try YouTube Radio playlist RD{video_id} via yt-dlp
        if not related_items and video_id:
            try:
                import yt_dlp
                rd_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
                ydl_opts = self._get_base_ydl_opts()
                ydl_opts['extract_flat'] = True
                ydl_opts['playlist_items'] = '1-30'
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(rd_url, download=False)
                    raw_entries = info.get('entries') if info else None
                    if isinstance(raw_entries, list):
                        seen_ids = {video_id}
                        for item in raw_entries:
                            if isinstance(item, dict):
                                vid_id = item.get('id')
                                if vid_id and vid_id not in seen_ids:
                                    related_items.append({
                                        'id': vid_id, 'title': item.get('title', 'Unknown Title'),
                                        'url': item.get('url') or f"https://www.youtube.com/watch?v={vid_id}",
                                        'uploader': item.get('uploader') or item.get('channel') or 'Unknown Uploader',
                                        'duration_string': utils.format_duration(item.get('duration'))
                                    })
                                    seen_ids.add(vid_id)
            except Exception as e:
                print(f"yt-dlp RD related fetch error: {e}")

        if not related_items:
            error_msg = _("No related videos found.")

        wx.CallAfter(self.update_related_videos_list, related_items, None if related_items else error_msg)

    def load_channel_videos(self, channel_url, channel_id=None):
        if not channel_url and not channel_id:
            utils.show_message_dialog(self.main_frame, _("No channel URL available for this item."), _("Info"))
            return

        target = channel_id if channel_id else channel_url
        if channel_url and "music.youtube.com" in channel_url and not channel_id:
            selected_index = self.results_list.GetSelection()
            if selected_index != wx.NOT_FOUND:
                data = self.results_list.GetClientData(selected_index)
                artist_name = data.get('uploader')
                if artist_name:
                    self.search_input.SetValue(artist_name)
                    self.on_search(None)
                    return

        self.search_input.SetValue(target)
        self.on_search(None)

    def on_playlist_button(self, event):
        menu = wx.Menu()
        import_item = menu.Append(wx.ID_ANY, _("Import Playlist..."))
        export_item = menu.Append(wx.ID_ANY, _("Export Playlist..."))

        menu.Bind(wx.EVT_MENU, self.import_playlist, import_item)
        menu.Bind(wx.EVT_MENU, self.export_playlist, export_item)

        self.PopupMenu(menu)
        menu.Destroy()

    def import_playlist(self, event):
        with wx.FileDialog(self, _("Import Playlist"), wildcard="Playlist Files (*.m3u;*.m3u8;*.pls)|*.m3u;*.m3u8;*.pls",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            pathname = fileDialog.GetPath()
            
        items = utils.parse_playlist_file(pathname)
        if not items:
            utils.show_error_dialog(self.main_frame, _("Failed to parse playlist or playlist is empty."))
            return

        self._reset_search_state("Playlist Import")
        self.current_search_type = 'playlist'
        self.results_list.Clear()
        
        for item in items:
            self.current_search_results.append(item)
            title = item.get('title', 'Unknown Title')
            self.results_list.Append(title, clientData=item)
        
        self.total_results_displayed = len(self.current_search_results)
        self._update_status_and_load_more_button('playlist', os.path.basename(pathname), len(items), len(items))
        nvda.speak(_("Imported {} items from playlist.").format(len(items)), constants.NVDA_VERBOSITY_DEFAULT)

    def export_playlist(self, event):
        if not self.current_search_results:
            utils.show_message_dialog(self, _("No items to export."), _("Info"))
            return

        with wx.FileDialog(self, _("Export Playlist"), wildcard="M3U Playlist (*.m3u)|*.m3u|PLS Playlist (*.pls)|*.pls",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            pathname = fileDialog.GetPath()

        if utils.save_playlist_file(pathname, self.current_search_results):
            utils.show_message_dialog(self, _("Playlist exported successfully."), _("Success"))
            nvda.speak(_("Playlist exported successfully."), constants.NVDA_VERBOSITY_DEFAULT)
        else:
            utils.show_error_dialog(self.main_frame, _("Failed to export playlist."))

    def on_item_selected(self, event):
        selected_index = self.results_list.GetSelection()
        if selected_index != wx.NOT_FOUND:
            utils.play_sound(self.main_frame.settings, "list_navigate")
            nvda.speak(self.results_list.GetString(selected_index), constants.NVDA_VERBOSITY_VERBOSE)
            data = self.results_list.GetClientData(selected_index)
            if data and isinstance(data, dict) and data.get('url'):
                self._trigger_prefetch_for_url(data['url'])
        event.Skip()

    def on_related_selection_change(self, event):
        selected_index = self.related_videos_list.GetSelection()
        if selected_index != wx.NOT_FOUND:
            utils.play_sound(self.main_frame.settings, "list_navigate")
            nvda.speak(self.related_videos_list.GetString(selected_index), constants.NVDA_VERBOSITY_VERBOSE)
            data = self.related_videos_list.GetClientData(selected_index)
            if data and isinstance(data, dict) and data.get('url'):
                self._trigger_prefetch_for_url(data['url'])
        event.Skip()

    def show_text_dialog(self, title, text_content):
        utils.play_sound(self.main_frame.settings, "popup_open")
        with wx.Dialog(self.main_frame, title=title, size=(600, 420), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER) as dlg:
            panel = wx.Panel(dlg)
            sizer = wx.BoxSizer(wx.VERTICAL)
            text_ctrl = wx.TextCtrl(panel, value=text_content or "", style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_AUTO_URL | wx.VSCROLL)
            text_ctrl.SetName(title)
            sizer.Add(text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

            btn_sizer = wx.StdDialogButtonSizer()

            copy_btn = wx.Button(panel, label=_("Copy Content"))
            copy_btn.SetName(_("Copy Content"))
            copy_btn.Bind(wx.EVT_BUTTON, lambda e: utils.copy_text_to_clipboard(text_content))
            btn_sizer.AddButton(copy_btn)

            close_button = wx.Button(panel, wx.ID_CLOSE, label=_("Close"))
            close_button.SetName(_("Close"))
            close_button.Bind(wx.EVT_BUTTON, lambda e: dlg.EndModal(wx.ID_CLOSE))
            dlg.Bind(wx.EVT_CLOSE, lambda e: dlg.EndModal(wx.ID_CLOSE))
            btn_sizer.AddButton(close_button)

            btn_sizer.Realize()
            sizer.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

            panel.SetSizer(sizer)

            def on_dialog_key(e):
                if e.GetKeyCode() == wx.WXK_ESCAPE:
                    dlg.EndModal(wx.ID_CLOSE)
                else:
                    e.Skip()
            dlg.Bind(wx.EVT_CHAR_HOOK, on_dialog_key)

            dlg.CentreOnParent()
            text_ctrl.SetFocus()
            nvda.speak(f"{title}. {_('Press Escape or Close button to dismiss.')}", constants.NVDA_VERBOSITY_DEFAULT)
            dlg.ShowModal()

    def show_context_menu(self, event):
        list_ctrl = event.GetEventObject()
        pos = event.GetPosition()
        if pos != wx.DefaultPosition:
            client_pos = list_ctrl.ScreenToClient(pos)
            item_index = list_ctrl.HitTest(client_pos)
        else:
            item_index = list_ctrl.GetSelection()
        if item_index == wx.NOT_FOUND: return
        if item_index != list_ctrl.GetSelection():
            list_ctrl.SetSelection(item_index)

        try:
            selected_item_data = list_ctrl.GetClientData(item_index)
        except Exception:
            selected_item_data = None
        if not selected_item_data or not isinstance(selected_item_data, dict) or 'url' not in selected_item_data: return

        video_url, video_title, video_uploader = selected_item_data['url'], selected_item_data.get('title', 'Video'), selected_item_data.get('uploader', '')
        channel_url = selected_item_data.get('channel_url', '')

        utils.play_sound(self.main_frame.settings, "popup_open")
        menu = wx.Menu()
        menu_actions = {}

        def add_item(target_menu, label, action):
            item = target_menu.Append(wx.ID_ANY, label)
            menu_actions[item.GetId()] = action
            return item

        add_item(menu, _("Play Audio"), lambda: self.play_audio_item(video_url, video_title, video_uploader, item_index, selected_item_data.get('source', 'youtube')))
        add_item(menu, _("Play Next (Add to Queue)"), lambda: self.main_frame.audio_player_panel.add_to_queue(selected_item_data, play_next=True))
        if feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_RADIO_MODE):
            add_item(menu, _("Start Radio"), lambda: self.start_radio_mode(video_url, video_title, video_uploader))
        if feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_FAVORITES):
            add_item(menu, _("Add to Favorites"), lambda: self.main_frame.add_to_favorites(selected_item_data))
        if feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_DOWNLOADER):
            add_item(menu, _("Download with Downloader"), lambda: self.run_ytdl_with_link(video_url))
        menu.AppendSeparator()

        has_channel_browser = feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_CHANNEL_BROWSER)
        if has_channel_browser:
            view_channel_item = add_item(menu, _("View Videos from Channel/Artist"), lambda: self.load_channel_videos(channel_url, selected_item_data.get('channel_id')))
            if not channel_url:
                view_channel_item.Enable(False)

        add_item(menu, _("Open Video in Browser"), lambda: self.open_in_browser(video_url))

        if has_channel_browser:
            open_channel_item = add_item(menu, _("Open Channel/Artist in Browser"), lambda: self.open_in_browser(channel_url))
            if not channel_url:
                open_channel_item.Enable(False)

        menu.AppendSeparator()
        add_item(menu, _("View Video Details"), lambda: self.view_video_details(video_url))
        add_item(menu, _("View Description"), lambda: self.view_description(video_url))
        if feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_VIDEO_COMMENTS):
            add_item(menu, _("View Comments"), lambda: self.view_comments(video_url))
        menu.AppendSeparator()

        copy_menu = wx.Menu()
        add_item(copy_menu, _("Copy Video Link"), lambda: utils.copy_text_to_clipboard(video_url))
        if has_channel_browser:
            copy_channel_item = add_item(copy_menu, _("Copy Channel/Artist Link"), lambda: utils.copy_text_to_clipboard(channel_url))
            if not channel_url:
                copy_channel_item.Enable(False)
        add_item(copy_menu, _("Copy Title"), lambda: utils.copy_text_to_clipboard(video_title))
        add_item(copy_menu, _("Copy Share Text"), lambda: self.copy_share_text_item(video_title, video_uploader, video_url))
        menu.AppendSubMenu(copy_menu, _("Copy"))

        menu.Bind(wx.EVT_MENU, lambda e: menu_actions.get(e.GetId(), lambda: None)())
        list_ctrl.PopupMenu(menu)
        menu.Destroy()

    def show_related_context_menu(self, event):
        list_ctrl = event.GetEventObject()
        if event.GetPosition() == wx.DefaultPosition:
            item_index = list_ctrl.GetSelection()
        else:
            item_index = list_ctrl.HitTest(list_ctrl.ScreenToClient(event.GetPosition()))
        if item_index == wx.NOT_FOUND: return
        if item_index != list_ctrl.GetSelection():
            list_ctrl.SetSelection(item_index)

        try:
            selected_item_data = list_ctrl.GetClientData(item_index)
        except Exception:
            selected_item_data = None
        if not selected_item_data or not isinstance(selected_item_data, dict) or 'url' not in selected_item_data: return

        utils.play_sound(self.main_frame.settings, "popup_open")
        menu = wx.Menu()
        menu_actions = {}

        def add_menu_item(parent_menu, label, action):
            item = parent_menu.Append(wx.ID_ANY, label)
            menu_actions[item.GetId()] = action
            return item

        add_menu_item(menu, _("Play Related Video"), lambda: self.on_play_related_video(event))
        if feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_DOWNLOADER):
            add_menu_item(menu, _("Download with Downloader"), lambda: self.run_ytdl_with_link(selected_item_data['url']))
        menu.AppendSeparator()
        add_menu_item(menu, _("Copy Video Link"), lambda: utils.copy_text_to_clipboard(selected_item_data['url']))

        def on_menu_select(e):
            action_to_run = menu_actions.get(e.GetId())
            if callable(action_to_run):
                action_to_run()

        menu.Bind(wx.EVT_MENU, on_menu_select)

        list_ctrl.PopupMenu(menu)
        menu.Destroy()

    def load_search_history_to_combobox(self):
        history = self.main_frame.settings.get("youtube_search_history", [])
        current_value = self.search_input.GetValue()
        self.search_input.Clear()
        self.search_input.AppendItems(list(reversed(history)))
        self.search_input.SetValue(current_value)

    def add_query_to_search_history(self, query):
        history = self.main_frame.settings.get("youtube_search_history", [])
        if query in history: history.remove(query)
        history.append(query)
        self.main_frame.settings["youtube_search_history"] = history[-constants.MAX_YT_SEARCH_HISTORY_ITEMS:]
        self.load_search_history_to_combobox()

    def on_item_dclick(self, event):
        selected_index = self.results_list.GetSelection()
        if selected_index != wx.NOT_FOUND:
            data = self.results_list.GetClientData(selected_index)
            if data and isinstance(data, dict) and 'url' in data:
                self.play_audio_item(data['url'], data.get('title'), data.get('uploader'), selected_index, data.get('source', 'youtube'))

    def play_audio_item(self, url, title, uploader, index, media_source='youtube'):
        if self.main_frame.settings.get("shuffle_mode", False):
            self.generate_shuffled_list()
            if self.shuffled_search_results:
                try:
                    item_to_remove = next(item for item in self.shuffled_search_results if item['url'] == url)
                    self.shuffled_search_results.remove(item_to_remove)
                except (ValueError, StopIteration):
                    print(f"Could not find {url} in shuffled list to remove it.")

        nvda.speak(_("Playing: {}").format(title), constants.NVDA_VERBOSITY_DEFAULT)
        wx.CallAfter(self.main_frame.request_audio_play, url, title, uploader, index=index, is_radio=False, media_source=media_source)
        wx.CallAfter(self.start_related_videos_fetch, url)

    def update_related_videos_list(self, data, error_msg=None, is_radio_queue=False):
        if not hasattr(self, 'related_videos_list'): return
        self.related_videos_list.SetName(_("Radio Queue") if is_radio_queue else _("Related Videos"))
        self.related_videos_list.Clear()
        self.related_videos_data = []
        if error_msg:
            self.related_videos_list.Append(error_msg, clientData=None)
        elif not data:
            self.related_videos_list.Append(_("Radio queue is empty.") if is_radio_queue else _("No related videos found."), clientData=None)
        else:
            self.related_videos_data = data
            for item in data:
                display_title = f"{item.get('title', 'N/A')} - {item.get('uploader', 'N/A')}"
                if item.get('duration_string'): display_title += f" [{item['duration_string']}]"
                self.related_videos_list.Append(display_title, clientData=item)
            if not is_radio_queue: nvda.speak(_("Loaded {} related videos.").format(len(data)), constants.NVDA_VERBOSITY_DEFAULT)

    def on_play_related_video(self, event):
        selected_index = self.related_videos_list.GetSelection()
        if selected_index != wx.NOT_FOUND and self.related_videos_data:
            try:
                item_data = self.related_videos_list.GetClientData(selected_index)
            except Exception:
                item_data = None
            if item_data and isinstance(item_data, dict) and 'url' in item_data:
                is_radio = self.main_frame.audio_player_panel.is_radio_mode
                nvda.speak(_("Playing..."), constants.NVDA_VERBOSITY_DEFAULT)
                if is_radio:
                    remaining_queue = self.related_videos_data[selected_index:]
                    song_to_play = remaining_queue.pop(0)
                    random.shuffle(remaining_queue)
                    self.radio_mode_queue = remaining_queue

                    self.main_frame.request_audio_play(song_to_play['url'], song_to_play['title'], song_to_play['uploader'], is_radio=True, media_source=song_to_play.get('source', 'youtube'))
                    self.update_related_videos_list(self.radio_mode_queue, is_radio_queue=True)
                else:
                    self.main_frame.request_audio_play(item_data['url'], item_data['title'], item_data['uploader'], is_radio=False, media_source=item_data.get('source', 'youtube'))
                    self.start_related_videos_fetch(item_data['url'])

    def on_related_list_focus(self, event):
        """Announces related videos list context for screen reader users on focus."""
        is_radio = bool(getattr(self.main_frame, 'audio_player_panel', None) and self.main_frame.audio_player_panel.is_radio_mode)
        name = _("Radio Queue") if is_radio else _("Related Videos")
        count = len(self.related_videos_data)
        if count > 0:
            nvda.speak(f"{name}, {count} {_('items')}", constants.NVDA_VERBOSITY_VERBOSE)
        else:
            nvda.speak(name, constants.NVDA_VERBOSITY_VERBOSE)
        event.Skip()

    def on_results_list_focus(self, event):
        """Announces search results list context for screen reader users on focus."""
        count = len(self.current_search_results)
        if count > 0:
            nvda.speak(f"{_('Search Results')}, {count} {_('items')}", constants.NVDA_VERBOSITY_VERBOSE)
        else:
            nvda.speak(_("Search Results"), constants.NVDA_VERBOSITY_VERBOSE)
        event.Skip()

    def on_related_list_key_down(self, event):
        keyCode = event.GetKeyCode()
        if keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_play_related_video(event)
        elif keyCode == wx.WXK_TAB:
            flags = wx.NavigationKeyEvent.IsBackward if event.ShiftDown() else wx.NavigationKeyEvent.IsForward
            event.GetEventObject().Navigate(flags)
        else:
            event.Skip()

    def on_exit(self, event):
        self.main_frame.Close()

    def on_list_key_down(self, event):
        keyCode = event.GetKeyCode()
        if keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_item_dclick(event)
        elif keyCode == wx.WXK_TAB:
            flags = wx.NavigationKeyEvent.IsBackward if event.ShiftDown() else wx.NavigationKeyEvent.IsForward
            event.GetEventObject().Navigate(flags)
        else:
            event.Skip()

    def copy_share_text_item(self, title, uploader, url):
        share_string = _("Listening to: {title} - {uploader} via Tunevia {url}").format(title=title, uploader=uploader or _("Unknown"), url=url)
        utils.copy_text_to_clipboard(share_string)

    def open_in_browser(self, url):
        if url:
            try: webbrowser.open(url)
            except Exception as e: utils.show_error_dialog(self.main_frame, _("Could not open URL: {}").format(e))

    def view_description(self, video_url):
        if not video_url: return
        nvda.speak(_("Getting video description..."), constants.NVDA_VERBOSITY_DEFAULT)
        wx.BeginBusyCursor()
        threading.Thread(target=self._fetch_and_show_text_dialog, args=(video_url, 'description', _("Video Description")), daemon=True).start()

    def view_video_details(self, video_url):
        if not video_url: return
        nvda.speak(_("Getting video details..."), constants.NVDA_VERBOSITY_DEFAULT)
        wx.BeginBusyCursor()
        threading.Thread(target=self._fetch_and_show_text_dialog, args=(video_url, 'details', _("Video Details")), daemon=True).start()

    def view_comments(self, video_url):
        if not video_url: return
        dlg = VideoCommentsDialog(self.main_frame, video_url, _("Video Comments"))
        dlg.ShowModal()
        dlg.Destroy()

    def _fetch_and_show_text_dialog(self, video_url, mode, title):
        content, error_msg = None, None
        info = None
        try:
            # Extract video ID
            video_id = None
            match = self.youtube_link_pattern.search(video_url)
            if match:
                video_id = match.groups()[-1]

            # Fast-path 1: Check memory cache
            if video_id and video_id in self._video_details_cache:
                info = self._video_details_cache[video_id]

            # Fast-path 2: Direct InnerTube player request (returns in ~0.3-0.5s)
            if not info and video_id:
                try:
                    url = "https://www.youtube.com/youtubei/v1/player"
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Content-Type": "application/json"
                    }
                    data = {
                        "context": {"client": {"clientName": "WEB", "clientVersion": "2.20240101.00.00", "hl": "en", "gl": "US"}},
                        "videoId": video_id
                    }
                    resp = self.http_session.post(url, headers=headers, json=data, timeout=5)
                    if resp.status_code == 200:
                        j = resp.json()
                        vd = j.get('videoDetails', {})
                        if vd and vd.get('title'):
                            dur = int(vd.get('lengthSeconds', 0)) if vd.get('lengthSeconds') else None
                            vc = int(vd.get('viewCount', 0)) if vd.get('viewCount') else None
                            mf = j.get('microformat', {}).get('playerMicroformatRenderer', {})
                            upload_date_raw = mf.get('uploadDate') or mf.get('publishDate')
                            upload_date_val = upload_date_raw.split('T')[0].replace('-', '') if upload_date_raw else None
                            info = {
                                'title': vd.get('title'),
                                'uploader': vd.get('author'),
                                'duration': dur,
                                'view_count': vc,
                                'like_count': None,
                                'upload_date': upload_date_val,
                                'description': vd.get('shortDescription', '')
                            }
                            if len(self._video_details_cache) >= 30:
                                self._video_details_cache.pop(next(iter(self._video_details_cache)))
                            self._video_details_cache[video_id] = info
                except Exception as it_err:
                    print(f"InnerTube details fast-path failed: {it_err}")

            # Fallback: yt-dlp if InnerTube did not provide info
            if not info:
                import yt_dlp
                ydl_opts = self._get_base_ydl_opts()
                ydl_opts['extract_flat'] = False # Need full details for this
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=False)
                    if info and video_id:
                        if len(self._video_details_cache) >= 30:
                            self._video_details_cache.pop(next(iter(self._video_details_cache)))
                        self._video_details_cache[video_id] = info

            if info:
                if mode == 'description': content = info.get('description', _('No description available.'))
                elif mode == 'details': content = self._format_video_details(info)
            else:
                error_msg = _("Failed to extract video information.")
        except Exception as e:
            error_msg = _("Error fetching data: {}").format(e)
        finally:
            wx.CallAfter(lambda: wx.EndBusyCursor() if wx.IsBusy() else None)
            if error_msg: wx.CallAfter(utils.show_error_dialog, self.main_frame, error_msg)
            else: wx.CallAfter(self.show_text_dialog, title, content)

    def _format_video_details(self, info):
        def f(num): return f"{int(num):,}" if num is not None else 'N/A'
        ud = info.get('upload_date')
        return (_("Title: {title}\nUploader: {uploader}\n\n"
                "Duration: {duration}\nViews: {views}\nLikes: {likes}\n"
                "Uploaded: {uploaded_date}\n").format(
                    title=info.get('title', 'N/A'), uploader=info.get('uploader', 'N/A'),
                    duration=utils.format_duration(info.get('duration')),
                    views=f(info.get('view_count')), likes=f(info.get('like_count')),
                    uploaded_date=utils.format_upload_date(ud) if ud else 'N/A'
                ))

    def run_ytdl_with_link(self, url):
        self.main_frame.show_ytdl_panel(initial_urls=[url])

    def on_run_ytdl(self, event):
        self.main_frame.show_ytdl_panel()



    def get_previous_track_info(self, current_index):
        if current_index is None or current_index <= 0: return None
        prev_index = current_index - 1
        return self.get_track_info_at_index(prev_index)

    def get_next_track_info(self, current_index):
        if current_index is None or current_index < 0: return None
        next_index = current_index + 1
        return self.get_track_info_at_index(next_index)

    def get_track_info_at_index(self, index):
        if index is None or not (0 <= index < self.results_list.GetCount()):
            return None
        
        data = self.results_list.GetClientData(index)
        if data and 'url' in data:
            return {
                'url': data['url'],
                'title': data.get('title'),
                'uploader': data.get('uploader'),
                'index': index
            }
        return None

    def is_last_track(self, index):
        if index is None:
            return True
        return index >= self.results_list.GetCount() - 1

    def generate_shuffled_list(self):
        if not self.current_search_results:
            self.shuffled_search_results = []
            return
            
        self.shuffled_search_results = self.current_search_results[:]
        random.shuffle(self.shuffled_search_results)
        print(f"Generated a new shuffled playlist with {len(self.shuffled_search_results)} items.")

    def get_shuffled_track_info(self):
        if not self.shuffled_search_results:
            if self.current_search_results:
                self.generate_shuffled_list()
                if not self.shuffled_search_results: return None
            else:
                return None
        
        track_data = self.shuffled_search_results.pop(0)
        
        original_index = -1
        try:
            original_index = self.current_search_results.index(track_data)
        except ValueError:
            pass 

        return {
            'url': track_data['url'],
            'title': track_data.get('title'),
            'uploader': track_data.get('uploader'),
            'index': original_index
        }
    
    def reshuffle_related_if_needed(self):
        """Re-shuffles the related videos list if shuffle mode is on."""
        if self.main_frame.settings.get("shuffle_mode", False) and self.related_videos_data:
            random.shuffle(self.related_videos_data)
            print("Re-shuffled related videos list.")

    def start_radio_mode(self, video_url, video_title, video_uploader):
        nvda.speak(_("Starting radio with: {}").format(video_title), constants.NVDA_VERBOSITY_DEFAULT)
        utils.play_sound(self.main_frame.settings, "radio_start")

        self.main_frame.request_audio_play(video_url, video_title, video_uploader, is_radio=True)

        self.related_videos_list.Clear()
        self.related_videos_list.Append(_("Finding radio station..."), clientData=None)
        self.radio_mode_queue = []

        threading.Thread(target=self._initialize_radio_queue_thread, args=(video_url,), daemon=True).start()

    def _initialize_radio_queue_thread(self, seed_video_url):
        import yt_dlp
        try:
            ydl_opts = self._get_base_ydl_opts()
            ydl_opts['extract_flat'] = True
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(seed_video_url, download=False)
            if not info or not info.get('title'): raise ValueError("Could not get seed title.")

            search_mode = self.main_frame.settings.get("search_mode", "youtube")
            radio_items = []
            video_id_match = self.youtube_link_pattern.search(seed_video_url)
            video_id = video_id_match.groups()[-1] if video_id_match else None

            if search_mode == "ytmusic" and YTMUSIC_ENABLED and video_id:
                try:
                    ytm = self.get_ytmusic()
                    raw_results = ytm.get_watch_playlist(video_id, limit=50) if ytm else None
                    if raw_results and 'tracks' in raw_results:
                        radio_items = self._parse_ytmusic_results(raw_results['tracks'])
                except Exception as e:
                    print(f"YTMusic radio fetch error: {e}. Falling back to search.")

            if not radio_items and video_id:
                # Try RD (Radio) playlist via yt-dlp as secondary source
                try:
                    rd_url = f"https://www.youtube.com/watch?v={video_id}&list=RD{video_id}"
                    search_opts = self._get_base_ydl_opts()
                    search_opts['extract_flat'] = True
                    search_opts['playlist_items'] = '1-50'
                    with yt_dlp.YoutubeDL(search_opts) as ydl_search:
                         result = ydl_search.extract_info(rd_url, download=False)
                         if result and 'entries' in result:
                             radio_items = result['entries']
                except Exception as e:
                    print(f"RD playlist fetch error: {e}. Falling back to search.")

            if not radio_items:
                # Tertiary: extract related_videos from the video itself
                try:
                    search_opts = self._get_base_ydl_opts()
                    search_opts['extract_flat'] = False # Need related_videos
                    with yt_dlp.YoutubeDL(search_opts) as ydl_search:
                        result = ydl_search.extract_info(seed_video_url, download=False)
                        if result and 'related_videos' in result:
                            radio_items = result['related_videos']
                except Exception as e:
                    print(f"Related videos fetch error: {e}. Falling back to search.")

            if not radio_items:
                # Fallback: title search (existing logic, but as last resort)
                search_opts = self._get_base_ydl_opts()
                search_opts['extract_flat'] = True
                with yt_dlp.YoutubeDL(search_opts) as ydl_search:
                    result = ydl_search.extract_info(f"ytsearch50:{info['title']}", download=False)
                if result and 'entries' in result:
                    radio_items = result['entries']

            if not radio_items: raise ValueError("No radio tracks found.")

            radio_items = [i for i in radio_items if i.get('id') != info.get('id')]
            for item in radio_items:
                if not item.get('url'): item['url'] = f"https://www.youtube.com/watch?v={item['id']}"

            random.shuffle(radio_items)

            wx.CallAfter(self.handle_radio_fetch_result, radio_items, None)
        except Exception as e:
            wx.CallAfter(self.handle_radio_fetch_result, [], _("Could not start radio: {}").format(e))

    def handle_radio_fetch_result(self, radio_items, error_msg):
        if error_msg:
            nvda.speak(error_msg, constants.NVDA_VERBOSITY_QUIET)
            self.related_videos_list.Clear()
            self.related_videos_list.Append(error_msg, clientData=None)
            return
        if not radio_items:
            nvda.speak(_("Could not find any songs for the radio queue."), constants.NVDA_VERBOSITY_DEFAULT)
            self.related_videos_list.Clear()
            self.related_videos_list.Append(_("No related songs found."), clientData=None)
            return

        self.radio_mode_queue = radio_items
        self.update_related_videos_list(self.radio_mode_queue, is_radio_queue=True)
        nvda.speak(_("Radio queue updated."), constants.NVDA_VERBOSITY_VERBOSE)

    def get_next_radio_track(self, last_played_url):
        if not self.radio_mode_queue:
            nvda.speak(_("Radio queue empty, finding more songs..."), constants.NVDA_VERBOSITY_DEFAULT)
            self.start_radio_mode(last_played_url, _("Last Played Song"), "")
            return None
        next_song = self.radio_mode_queue.pop(0)
        self.update_related_videos_list(self.radio_mode_queue, is_radio_queue=True)
        return next_song