import wx
import sys
import os

# Local application imports
from translation_manager import _

# Safely import the vlc library
try:
    import vlc
    VLC_ENABLED = True
except ImportError:
    VLC_ENABLED = False
    print("FATAL: VLC library not found. Video player functionality is disabled.")

class VideoPlayerFrame(wx.Frame):
    """
    A separate frame for displaying video playback using VLC.
    """
    def __init__(self, parent, title):
        super().__init__(parent, title=title, size=(640, 480))
        self.main_frame = parent
        self.player = None
        self.error_label = None

        self.panel = wx.Panel(self)
        self.panel.SetBackgroundColour(wx.BLACK)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.panel, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self.Bind(wx.EVT_CLOSE, self.on_close)

        if VLC_ENABLED:
            if self.main_frame and hasattr(self.main_frame, 'audio_player_panel'):
                self.player = self.main_frame.audio_player_panel.player
        else:
            self.error_label = wx.StaticText(self.panel, label="")
            error_sizer = wx.BoxSizer(wx.VERTICAL)
            error_sizer.Add(self.error_label, 0, wx.CENTER)
            self.panel.SetSizer(error_sizer)

        self.retranslate_ui()

    def retranslate_ui(self):
        """Retranslates UI elements in the video frame."""
        if self.main_frame and self.main_frame.audio_player_panel.is_loaded:
            current_title = self.main_frame.audio_player_panel.video_title
            self.SetTitle(f"{current_title} - {_('Tunevia Video Player')}")
        else:
            self.SetTitle(_("Tunevia Video Player"))

        if self.error_label:
            self.error_label.SetLabel(_("VLC is not installed. Video playback is disabled."))
        
        self.Layout()

    def play_video(self, video_url, start_time_ms=0):
        """
        Attaches the video output to this frame's panel.
        Crucially, it handles re-attaching if a video is already playing.
        """
        if not VLC_ENABLED or not self.player:
            return

        # The key to fixing the black screen: if a video is already playing,
        # we must stop it, attach the window, and restart from the same position.
        if self.player.is_playing():
            current_media = self.player.get_media()
            if not current_media:
                return 
            
            current_time = self.player.get_time()

            # 1. Attach the panel to the player instance
            if sys.platform == 'win32':
                self.player.set_hwnd(self.panel.GetHandle())
            else:
                self.player.set_xwindow(self.panel.GetHandle())

            # 2. Stop, re-set the media, and play again to re-initialize video output
            self.player.stop()
            self.player.set_media(current_media)
            current_media.release()
            self.player.play()

            # 3. Schedule a seek to the previous time after a short delay
            def seek_to_previous_time():
                if self.player:
                    self.player.set_time(current_time)
            
            wx.CallLater(150, seek_to_previous_time)

        else:
            # If nothing is playing, just attach the window. The next track will use it.
            if sys.platform == 'win32':
                self.player.set_hwnd(self.panel.GetHandle())
            else:
                self.player.set_xwindow(self.panel.GetHandle())

        video_title = self.main_frame.audio_player_panel.video_title or ""
        self.SetTitle(f"{video_title} - {_('Tunevia Video Player')}")

    def on_playback_finished(self):
        """Called by the main audio player when playback stops or finishes."""
        self.SetTitle(_("Tunevia Video Player"))

    def on_close(self, event):
        """
        When the video frame is closed, detach the video output from the player
        and re-route it back to the hidden video panel.
        """
        if self.player:
            hidden_hwnd = getattr(self.main_frame.audio_player_panel, 'hidden_video_panel', None)
            hwnd_val = hidden_hwnd.GetHandle() if hidden_hwnd else 0
            if sys.platform == 'win32':
                self.player.set_hwnd(hwnd_val)
            else:
                self.player.set_xwindow(hwnd_val)

        if self.main_frame:
            self.main_frame.video_frame = None
            if hasattr(self.main_frame, 'audio_player_panel'):
                self.main_frame.audio_player_panel.update_video_button_label()

        self.Destroy()