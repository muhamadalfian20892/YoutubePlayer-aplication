#--- START OF FILE radar_panel.py ---

import wx
import threading
import random
import time
import os

# local stuff
import nvda
import constants
import utils
import feature_manager
from translation_manager import _

# try to get the yt music api, w/e if it fails
try:
    from ytmusicapi import YTMusic
    YTMUSIC_WORKS = True
except ImportError:
    YTMUSIC_WORKS = False
    print("Warning: ytmusicapi is not installed. Radar recommendations are unavailable.")

class RadarPanel(wx.Panel):
    """
    A wx.Panel that provides music recommendations based on the user's play history.
    """
    def __init__(self, parent, main_frame):
        super().__init__(parent)
        self.main_frame = main_frame
        self.is_scanning = False
        self.recommendations = []
        self.ytm = None # YouTube Music API client

        self.InitUI()

    def get_ytm(self):
        """Lazily initialize YTMusic off the UI thread."""
        global YTMUSIC_WORKS
        if not YTMUSIC_WORKS:
            return None
        if self.ytm is None:
            try:
                self.ytm = YTMusic()
            except Exception as e:
                print(f"YouTube Music API initialization failed: {e}")
                YTMUSIC_WORKS = False
                return None
        return self.ytm

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Instruction and Scan Button
        top_sizer = wx.BoxSizer(wx.VERTICAL)
        self.instruction_text = wx.StaticText(self, label="")
        top_sizer.Add(self.instruction_text, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        self.scan_button = wx.Button(self, label="")
        self.scan_button.SetFont(self.scan_button.GetFont().MakeLarger())
        top_sizer.Add(self.scan_button, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        
        vbox.Add(top_sizer, 0, wx.EXPAND)

        # Separator
        separator = wx.StaticLine(self, style=wx.LI_HORIZONTAL)
        vbox.Add(separator, 0, wx.EXPAND | wx.ALL, 10)

        # Results area
        results_sizer = wx.BoxSizer(wx.VERTICAL)
        self.status_label = wx.StaticText(self, label="")
        results_sizer.Add(self.status_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        self.results_list = wx.ListBox(self, style=wx.LB_SINGLE | wx.LB_HSCROLL | wx.WANTS_CHARS)
        results_sizer.Add(self.results_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        vbox.Add(results_sizer, 1, wx.EXPAND)

        self.SetSizer(vbox)

        # Event Bindings
        self.scan_button.Bind(wx.EVT_BUTTON, self.on_scan)
        self.results_list.Bind(wx.EVT_LISTBOX, self.on_selection_change)
        self.results_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_item_dclick)
        self.results_list.Bind(wx.EVT_KEY_DOWN, self.on_list_key_down)
        self.results_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
        
        self.retranslate_ui()
    
    def on_context_menu(self, event):
        idx = self.results_list.GetSelection()
        if idx == wx.NOT_FOUND: return

        track_data = self.results_list.GetClientData(idx)
        if not track_data: return

        menu = wx.Menu()
        play_item = menu.Append(wx.ID_ANY, _("Play Audio"))
        queue_item = menu.Append(wx.ID_ANY, _("Play Next (Add to Queue)"))
        fav_item = None
        if feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_FAVORITES):
            fav_item = menu.Append(wx.ID_ANY, _("Add to Favorites"))
        
        def on_play(e):
            self.on_item_dclick(None)
        
        def on_queue(e):
            self.main_frame.audio_player_panel.add_to_queue(track_data, play_next=True)

        def on_fav(e):
            self.main_frame.add_to_favorites(track_data)

        menu.Bind(wx.EVT_MENU, on_play, play_item)
        menu.Bind(wx.EVT_MENU, on_queue, queue_item)
        if fav_item:
            menu.Bind(wx.EVT_MENU, on_fav, fav_item)

        self.PopupMenu(menu)
        menu.Destroy()
    
    def on_selection_change(self, event):
        idx = self.results_list.GetSelection()
        if idx != wx.NOT_FOUND:
            item_text = self.results_list.GetString(idx)
            nvda.speak(item_text, constants.NVDA_VERBOSITY_DEFAULT)
            utils.play_sound(self.main_frame.settings, "list_navigate")
        event.Skip()
    
    def retranslate_ui(self):
        """Updates translatable text on the panel."""
        self.instruction_text.SetLabel(_("Click the button to scan your recent listening history and discover top songs from artists you like."))
        self.scan_button.SetLabel(_("Scan for Recommendations"))
        self.scan_button.SetName(_("Scan for Recommendations"))
        self.results_list.SetName(_("Recommendations List"))
        
        if not YTMUSIC_WORKS:
            self.status_label.SetLabel(_("Radar feature disabled. Please install 'ytmusicapi' library."))
            self.scan_button.Disable()
        elif not self.recommendations:
            self.status_label.SetLabel(_("Scan history to find new tracks."))
        
        self.Layout()

    def on_scan(self, event):
        if self.is_scanning or not YTMUSIC_WORKS:
            return

        play_history = self.main_frame.settings.get("play_history", [])
        if len(play_history) < 5:
            utils.show_message_dialog(self, _("Your play history is too short. Listen to at least 5 different songs to get recommendations."), _("Not Enough Data"))
            return

        self.is_scanning = True
        self.scan_button.Disable()
        self.results_list.Clear()
        self.status_label.SetLabel(_("Analyzing your listening habits..."))
        nvda.speak(_("Scanning for recommendations..."))
        wx.BeginBusyCursor()

        # Perform the scan in a background thread to keep the UI responsive
        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        history = self.main_frame.settings.get("play_history", [])
        seen_urls = {item.get('url') for item in history if item.get('url')}

        # Identify unique artists from the last 20 played songs
        recent_history = history[-20:]
        artists = sorted(list({item.get('uploader') for item in recent_history if item.get('uploader')}))
        
        if not artists:
            wx.CallAfter(self.finish_scan, [], _("Could not identify any artists from your recent history."))
            return

        ytm = self.get_ytm()
        if not ytm:
            wx.CallAfter(self.finish_scan, [], _("YouTube Music API is not available."))
            return

        all_recommendations = []
        num_artists = len(artists)

        for i, artist in enumerate(artists):
            wx.CallAfter(self.status_label.SetLabel, _("Finding top songs for {artist} ({i}/{total})...").format(artist=artist, i=i+1, total=num_artists))
            try:
                # Search for the artist to get their browseId
                search_results = ytm.search(artist, filter="artists", limit=1)
                if not search_results or 'browseId' not in search_results[0]:
                    continue
                
                artist_id = search_results[0]['browseId']
                artist_data = ytm.get_artist(artist_id)
                
                # Fetch top songs for this artist
                if 'songs' in artist_data and 'results' in artist_data['songs']:
                    top_songs = artist_data['songs']['results']
                    for song in top_songs[:5]: # Take top 5 songs per artist
                        if song and 'videoId' in song:
                            all_recommendations.append(song)
                time.sleep(0.5) # Avoid rate limiting
            except Exception as e:
                print(f"Failed to fetch data for artist '{artist}': {e}")

        # Filter out duplicates and tracks already in the play history
        final_results = []
        processed_ids = set()
        
        for rec in all_recommendations:
            video_id = rec.get('videoId')
            if not video_id or video_id in processed_ids:
                continue
            
            yt_url = f"https://www.youtube.com/watch?v={video_id}"
            if yt_url not in seen_urls:
                artists_str = ", ".join([a['name'] for a in rec.get('artists', []) if a.get('name')])
                final_results.append({
                    'id': video_id,
                    'url': yt_url,
                    'title': rec.get('title', 'N/A'),
                    'uploader': artists_str or 'Unknown Artist',
                    'duration': rec.get('duration_seconds'),
                })
                processed_ids.add(video_id)

        random.shuffle(final_results)
        wx.CallAfter(self.finish_scan, final_results[:50]) # Limit to 50 results

    def finish_scan(self, results, error=None):
        if not self:
            return
        self.recommendations = results
        self.results_list.Clear()

        if error:
            self.status_label.SetLabel(error)
            nvda.speak(error)
        elif not self.recommendations:
            self.status_label.SetLabel(_("Scan complete. Couldn't find any new recommendations."))
            nvda.speak(_("No new recommendations found."))
        else:
            self.status_label.SetLabel(_("Scan complete! Found {count} new tracks you might like.").format(count=len(self.recommendations)))
            nvda.speak(_("Found {count} new recommendations.").format(count=len(self.recommendations)))
            for track in self.recommendations:
                display_str = f"{track.get('title', 'N/A')}. duration: {utils.format_duration(track.get('duration'))} uploaded by {track.get('uploader', 'N/A')}"
                self.results_list.Append(display_str, clientData=track)

        self.is_scanning = False
        self.scan_button.Enable(YTMUSIC_WORKS)
        if wx.IsBusy():
            wx.EndBusyCursor()

    def on_list_key_down(self, event):
        keyCode = event.GetKeyCode()
        if keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_item_dclick(event)
        elif keyCode == wx.WXK_TAB:
            flags = wx.NavigationKeyEvent.IsBackward if event.ShiftDown() else wx.NavigationKeyEvent.IsForward
            event.GetEventObject().Navigate(flags)
        else:
            event.Skip()

    def on_item_dclick(self, event):
        selection = self.results_list.GetSelection()
        if selection == wx.NOT_FOUND: return
        track_data = self.results_list.GetClientData(selection)
        if not track_data: return
        
        nvda.speak(_("Loading recommended track..."))
        self.main_frame.request_audio_play(
            track_data['url'], track_data['title'], track_data['uploader'], index=None
        )