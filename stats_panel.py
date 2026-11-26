import wx
from collections import Counter
import utils
import constants
from translation_manager import _
import nvda

class StatsPanel(wx.Panel):
    """
    Panel that displays listening statistics: Top Artists, Top Tracks, Total Time, etc.
    "Tunevia Wrapped" style.
    """
    def __init__(self, parent, main_frame):
        super().__init__(parent)
        self.main_frame = main_frame
        self.InitUI()

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.headline = wx.StaticText(self, label=_("Your Tunevia Insights"))
        font = self.headline.GetFont()
        font.SetPointSize(14)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.headline.SetFont(font)
        vbox.Add(self.headline, 0, wx.ALL | wx.ALIGN_CENTER, 15)

        # Stats Containers
        stats_sizer = wx.GridBagSizer(10, 10)

        # 1. Total Listening Time & Split
        self.total_time_box = wx.StaticBox(self, label=_("Time Spent"))
        tt_sizer = wx.StaticBoxSizer(self.total_time_box, wx.VERTICAL)
        self.stats_text_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        tt_sizer.Add(self.stats_text_ctrl, 1, wx.ALL | wx.EXPAND, 5)
        stats_sizer.Add(tt_sizer, pos=(0, 0), span=(1, 2), flag=wx.EXPAND)

        # 2. Top Artists
        self.top_artists_box = wx.StaticBox(self, label=_("Top Artists"))
        ta_sizer = wx.StaticBoxSizer(self.top_artists_box, wx.VERTICAL)
        self.top_artists_list = wx.ListBox(self, style=wx.LB_SINGLE)
        ta_sizer.Add(self.top_artists_list, 1, wx.ALL | wx.EXPAND, 5)
        stats_sizer.Add(ta_sizer, pos=(1, 0), flag=wx.EXPAND)

        # 3. Top Tracks
        self.top_tracks_box = wx.StaticBox(self, label=_("Top Tracks"))
        tt_list_sizer = wx.StaticBoxSizer(self.top_tracks_box, wx.VERTICAL)
        self.top_tracks_list = wx.ListBox(self, style=wx.LB_SINGLE)
        tt_list_sizer.Add(self.top_tracks_list, 1, wx.ALL | wx.EXPAND, 5)
        stats_sizer.Add(tt_list_sizer, pos=(1, 1), flag=wx.EXPAND)

        # 4. Habits / Insights
        self.habits_box = wx.StaticBox(self, label=_("Listening Habits"))
        habits_sizer = wx.StaticBoxSizer(self.habits_box, wx.VERTICAL)
        self.habits_label = wx.StaticText(self, label=_("Not enough data yet."))
        habits_sizer.Add(self.habits_label, 1, wx.ALL | wx.EXPAND, 10)
        stats_sizer.Add(habits_sizer, pos=(2, 0), span=(1, 2), flag=wx.EXPAND)

        stats_sizer.AddGrowableCol(0)
        stats_sizer.AddGrowableCol(1)
        stats_sizer.AddGrowableRow(1)
        
        # Add grid to main vbox
        vbox.Add(stats_sizer, 1, wx.ALL | wx.EXPAND, 10)

        # Refresh Button
        self.refresh_btn = wx.Button(self, label=_("Refresh Stats"))
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        vbox.Add(self.refresh_btn, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        self.SetSizer(vbox)
        self.retranslate_ui()

    def retranslate_ui(self):
        self.headline.SetLabel(_("Your Tunevia Insights"))
        self.total_time_box.SetLabel(_("Time Spent"))
        self.stats_text_ctrl.SetName(_("Listening Time and Statistics"))
        self.top_artists_box.SetLabel(_("Top Artists"))
        self.top_artists_list.SetName(_("Top Artists"))
        self.top_tracks_box.SetLabel(_("Top Tracks"))
        self.top_tracks_list.SetName(_("Top Tracks"))
        self.habits_box.SetLabel(_("Listening Habits"))
        self.refresh_btn.SetLabel(_("Refresh Stats"))
        self.refresh_btn.SetName(_("Refresh Stats"))
        self.calculate_stats()
        self.Layout()

    def ensure_data_loaded(self):
        self.calculate_stats()

    def on_refresh(self, event):
        self.calculate_stats()
        nvda.speak(_("Statistics refreshed."))

    def calculate_stats(self):
        history = self.main_frame.settings.get("play_history", [])
        if not history:
            self.stats_text_ctrl.SetValue(_("No history yet."))
            self.top_artists_list.Clear()
            self.top_tracks_list.Clear()
            self.habits_label.SetLabel(_("Not enough data yet."))
            return

        # 2. Stats
        artists = []
        tracks = []
        total_seconds = 0
        music_seconds = 0
        video_seconds = 0
        
        for item in history:
            if not isinstance(item, dict): continue
            
            # Artist
            uploader = item.get('uploader')
            if not uploader: uploader = _('Unknown Artist')
            artists.append(uploader)
            
            # Track
            title = item.get('title')
            if not title: title = _('Unknown Track')
            tracks.append(f"{title} - {uploader}")
            
            # Time
            dur = item.get('duration')
            if dur and isinstance(dur, (int, float)):
                item_dur = dur
            else:
                 item_dur = 210 # fallback 3.5 mins
            
            total_seconds += item_dur
            
            # Classify as Music or Video
            source = item.get('source', 'youtube')
            is_music = False
            
            if source == 'ytmusic':
                is_music = True
            else:
                # Heuristics for standard YouTube items
                # If short, or has keywords -> Music. Else -> Video (Regular)
                lower_title = title.lower()
                lower_uploader = uploader.lower()
                keywords = ['audio', 'lyrics', 'official', 'mv', 'music', 'album', 'soundtrack', 'ost', 'topic', 'vevo']
                
                if item_dur < 600 and (any(k in lower_title for k in keywords) or any(k in lower_uploader for k in keywords)):
                    is_music = True
                elif item_dur < 300: # Very short items likely songs
                    is_music = True
            
            if is_music:
                music_seconds += item_dur
            else:
                video_seconds += item_dur
        
        # Helper to format time
        def get_time_str(secs):
             h = int(secs // 3600)
             m = int((secs % 3600) // 60)
             return _("{h}h {m}m").format(h=h, m=m)

        stats_text = _("Total: {}\n").format(get_time_str(total_seconds))
        stats_text += _("Listening to Music: {}\n").format(get_time_str(music_seconds))
        stats_text += _("Watching Videos: {}").format(get_time_str(video_seconds))
        
        self.stats_text_ctrl.SetValue(stats_text)
        
        # Top 5 Artists
        self.top_artists_list.Clear()
        for artist, count in Counter(artists).most_common(5):
             self.top_artists_list.Append(f"{artist} ({count})")
             
        # Top 5 Tracks
        self.top_tracks_list.Clear()
        for track, count in Counter(tracks).most_common(5):
             self.top_tracks_list.Append(f"{track} ({count})")

        # Insights
        total_hours = int(total_seconds // 3600)
        msg = ""
        if total_hours > 50:
            msg = _("You keep the music playing all day long!")
        elif total_hours > 10:
             msg = _("You're building up a nice collection.")
        else:
             msg = _("Just getting started!")
             
        self.habits_label.SetLabel(msg)
