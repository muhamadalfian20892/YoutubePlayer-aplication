# discovery_panel.py

import wx
import threading
import os

# my local stuff
import nvda
import utils
import constants
import settings_manager
import feature_manager
from translation_manager import _

class DiscoveryPanel(wx.Panel):
    """
    A wx.Panel that displays trending music and new releases from YouTube.
    """
    def __init__(self, parent, main_frame):
        super().__init__(parent)
        self.main_frame = main_frame
        self.is_loading = False
        self.has_loaded = False

        self.InitUI()

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.status_label = wx.StaticText(self, label="...")
        vbox.Add(self.status_label, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        # Holds the two lists
        list_area_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # --- Trending List ---
        self.charts_box = wx.StaticBox(self, label="")
        charts_sizer = wx.StaticBoxSizer(self.charts_box, wx.VERTICAL)
        self.charts_list = wx.ListBox(self, style=wx.LB_SINGLE | wx.LB_HSCROLL | wx.WANTS_CHARS)
        charts_sizer.Add(self.charts_list, 1, wx.EXPAND | wx.ALL, 5)
        list_area_sizer.Add(charts_sizer, 1, wx.EXPAND | wx.RIGHT, 5)

        # --- New Releases List ---
        self.new_stuff_box = wx.StaticBox(self, label="")
        new_stuff_sizer = wx.StaticBoxSizer(self.new_stuff_box, wx.VERTICAL)
        self.new_releases_list = wx.ListBox(self, style=wx.LB_SINGLE | wx.LB_HSCROLL | wx.WANTS_CHARS)
        new_stuff_sizer.Add(self.new_releases_list, 1, wx.EXPAND | wx.ALL, 5)
        list_area_sizer.Add(new_stuff_sizer, 1, wx.EXPAND | wx.LEFT, 5)

        vbox.Add(list_area_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.SetSizer(vbox)
        
        # Event Bindings
        self.charts_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_double_click)
        self.new_releases_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_double_click)
        self.charts_list.Bind(wx.EVT_KEY_DOWN, self.on_list_key_down)
        self.new_releases_list.Bind(wx.EVT_KEY_DOWN, self.on_list_key_down)
        self.charts_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
        self.new_releases_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)

        self.retranslate_ui()

    def on_context_menu(self, event):
        list_ctrl = event.GetEventObject()
        pos = event.GetPosition()
        if pos != wx.DefaultPosition:
            item_index = list_ctrl.HitTest(list_ctrl.ScreenToClient(pos))
        else:
            item_index = list_ctrl.GetSelection()
        if item_index == wx.NOT_FOUND: return
        if item_index != list_ctrl.GetSelection():
            list_ctrl.SetSelection(item_index)

        selected_item_data = list_ctrl.GetClientData(item_index)
        if not selected_item_data: return

        menu = wx.Menu()
        play_item = menu.Append(wx.ID_ANY, _("Play Audio"))
        queue_item = menu.Append(wx.ID_ANY, _("Play Next (Add to Queue)"))
        fav_item = None
        if feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_FAVORITES):
            fav_item = menu.Append(wx.ID_ANY, _("Add to Favorites"))
        
        def on_play(e):
            self.on_double_click(event)
        
        def on_queue(e):
            self.main_frame.audio_player_panel.add_to_queue(selected_item_data, play_next=True)

        def on_fav(e):
            self.main_frame.add_to_favorites(selected_item_data)

        menu.Bind(wx.EVT_MENU, on_play, play_item)
        menu.Bind(wx.EVT_MENU, on_queue, queue_item)
        if fav_item:
            menu.Bind(wx.EVT_MENU, on_fav, fav_item)

        list_ctrl.PopupMenu(menu)
        menu.Destroy()
    
    def retranslate_ui(self):
        """Updates translatable text and layout."""
        self.charts_box.SetLabel(_("Trending Songs (Global)"))
        self.charts_list.SetName(_("Trending Songs (Global)"))
        self.new_stuff_box.SetLabel(_("New Releases"))
        self.new_releases_list.SetName(_("New Releases"))

        if self.charts_list.GetCount() == 0:
            self.charts_list.Append(_("Loading charts..."))
        if self.new_releases_list.GetCount() == 0:
            self.new_releases_list.Append(_("Loading new releases..."))

        self.Layout()

    def ensure_data_loaded(self):
        """Called when the tab is focused or accessed to lazily load data."""
        if not self.has_loaded and not self.is_loading:
            self.load_discovery_data()

    def load_discovery_data(self):
        """Fetches trending and new releases in background threads."""
        if self.is_loading:
            return
        
        self.has_loaded = True
        self.is_loading = True
        self.charts_list.Clear()
        self.new_releases_list.Clear()
        self.charts_list.Append(_("Loading charts..."))
        self.new_releases_list.Append(_("Loading new releases..."))
        self.status_label.SetLabel(_("Scraping YouTube Playlists..."))
        
        threading.Thread(target=self._scrape_playlist_thread, args=(constants.DISCOVERY_CHARTS_URL, self.charts_list), daemon=True).start()
        threading.Thread(target=self._scrape_playlist_thread, args=(constants.DISCOVERY_NEW_RELEASES_URL, self.new_releases_list), daemon=True).start()

    def get_ytdl_opts(self):
        opts = {
            'quiet': True,
            'skip_download': True,
            'extract_flat': 'in_playlist',
            'playlistend': 50
        }
        cookie_file = settings_manager.get_effective_cookies_path(self.main_frame.settings)
        if cookie_file and os.path.exists(cookie_file):
            opts['cookiefile'] = cookie_file
        return opts

    def _scrape_playlist_thread(self, url, list_box):
        entries = []
        error = None
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL(self.get_ytdl_opts()) as ydl:
                info = ydl.extract_info(url, download=False)
                if info and 'entries' in info:
                    entries = [item for item in info['entries'] if item]
        except Exception as e:
            print(f"yt-dlp error on {url}: {e}")
            error = str(e)

        wx.CallAfter(self._update_list, list_box, entries, error)

    def _update_list(self, list_box, entries, error):
        if not self or not list_box:
            return
        list_box.Clear()

        if error:
            list_box.Append(_("Error loading playlist."))
            self.status_label.SetLabel(_("An error occurred during playlist loading."))
        elif entries:
            for entry in entries:
                if 'url' not in entry and entry.get('id'):
                    entry['url'] = f"https://www.youtube.com/watch?v={entry['id']}"
                if not entry.get('url'):
                    continue

                title = entry.get('title', 'N/A')
                uploader = entry.get('uploader', 'Unknown')
                duration = utils.format_duration(entry.get('duration'))
                
                display_str = f"{title}. duration: {duration} uploaded by {uploader}"
                list_box.Append(display_str, clientData=entry)
        else:
            list_box.Append(_("No items found in playlist."))

        if not self.is_loading:
             return
        
        charts_done = (self.charts_list.GetCount() > 0 and self.charts_list.GetString(0) != _("Loading charts..."))
        new_releases_done = (self.new_releases_list.GetCount() > 0 and self.new_releases_list.GetString(0) != _("Loading new releases..."))
        
        if charts_done and new_releases_done:
            self.is_loading = False
            self.status_label.SetLabel(_("Discovery playlists loaded."))

    def on_list_key_down(self, event):
        keyCode = event.GetKeyCode()
        if keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_double_click(event)
        elif keyCode == wx.WXK_TAB:
            flags = wx.NavigationKeyEvent.IsBackward if event.ShiftDown() else wx.NavigationKeyEvent.IsForward
            event.GetEventObject().Navigate(flags)
        else:
            event.Skip()

    def on_double_click(self, event):
        clicked_list = event.GetEventObject() if event else None
        if not isinstance(clicked_list, wx.ListBox):
            clicked_list = self.FindFocus()
            if not isinstance(clicked_list, wx.ListBox):
                clicked_list = self.charts_list if self.charts_list.GetSelection() != wx.NOT_FOUND else self.new_releases_list
        selected_idx = clicked_list.GetSelection() if clicked_list else wx.NOT_FOUND
        if selected_idx == wx.NOT_FOUND:
            return
            
        vid_data = clicked_list.GetClientData(selected_idx)
        if not vid_data or 'url' not in vid_data:
            return

        nvda.speak(_("Loading track..."))
        # Tell the main window to play it.
        self.main_frame.request_audio_play(
            vid_data['url'],
            vid_data.get('title', _('Unknown Title')),
            vid_data.get('uploader', _('Unknown Artist')),
            index=None
        )