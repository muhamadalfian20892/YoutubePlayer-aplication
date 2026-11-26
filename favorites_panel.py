import wx
from datetime import datetime, timezone

# Local application imports
import nvda
import constants
import utils
from translation_manager import _

class FavoritesPanel(wx.Panel):
    """
    A wx.Panel that displays the user's favorite songs, with options
    to play, and remove items.
    """
    def __init__(self, parent, main_frame):
        super().__init__(parent)
        self.main_frame = main_frame
        self.InitUI()
        self.load_favorites()

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Favorites list
        self.favorites_list = wx.ListBox(self, style=wx.LB_EXTENDED | wx.LB_HSCROLL | wx.WANTS_CHARS)
        vbox.Add(self.favorites_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        # Buttons
        hbox_buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.play_button = wx.Button(self, label="")
        self.remove_button = wx.Button(self, label="")

        hbox_buttons.Add(self.play_button, flag=wx.RIGHT, border=10)
        hbox_buttons.Add(self.remove_button, flag=wx.RIGHT, border=10)
        vbox.Add(hbox_buttons, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        self.SetSizer(vbox)

        # Bind events
        self.favorites_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_play_selected)
        self.favorites_list.Bind(wx.EVT_LISTBOX, self.on_selection_change)
        self.favorites_list.Bind(wx.EVT_KEY_DOWN, self.on_list_key_down)
        self.favorites_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
        self.play_button.Bind(wx.EVT_BUTTON, self.on_play_selected)
        self.remove_button.Bind(wx.EVT_BUTTON, self.on_remove_selected)

        # Initial button states
        self.play_button.Disable()
        self.remove_button.Disable()

        self.retranslate_ui()

    def retranslate_ui(self):
        """Updates all translatable text on the panel."""
        self.favorites_list.SetName(_("Favorites List"))
        self.favorites_list.SetToolTip(_("List of your favorite songs. Double-click or Enter to play."))
        self.play_button.SetLabel(_("Play Selected"))
        self.play_button.SetName(_("Play Selected"))
        self.play_button.SetToolTip(_("Play the selected song"))
        self.remove_button.SetLabel(_("Remove Selected"))
        self.remove_button.SetName(_("Remove Selected"))
        self.remove_button.SetToolTip(_("Remove the selected song(s) from favorites"))
        self.display_favorites()
        self.Layout()

    def load_favorites(self):
        """Loads favorites data from settings and triggers display."""
        self.display_favorites()

    def display_favorites(self):
        """updates the listbox."""
        self.favorites_list.Clear()
        favorites = self.main_frame.settings.get("favorites", [])

        if not favorites:
            self.favorites_list.Append(_("You have no favorite songs yet."))
            self.favorites_list.Disable()
            self.play_button.Disable()
            self.remove_button.Disable()
        else:
            self.favorites_list.Enable()
            for entry in favorites:
                if isinstance(entry, dict) and 'title' in entry and 'url' in entry:
                    title = entry.get('title', 'N/A')
                    uploader = entry.get('uploader', 'N/A')
                    duration_str = entry.get('duration_string') or utils.format_duration(entry.get('duration'))
                    list_str = f"{title}. duration: {duration_str} uploaded by {uploader}"
                    self.favorites_list.Append(list_str, clientData=entry)
                else:
                    print(f"Skipping invalid favorite entry during display: {entry}")
        
        self.on_selection_change(None)

    def refresh_list(self):
        """Public method to reload favorites and preserve selection if possible."""
        current_selection = self.favorites_list.GetSelections()
        selected_url = None
        if current_selection:
            raw_data = self.favorites_list.GetClientData(current_selection[0])
            if isinstance(raw_data, dict):
                selected_url = raw_data.get('url')

        self.load_favorites()
        
        if selected_url:
            for i in range(self.favorites_list.GetCount()):
                item_data = self.favorites_list.GetClientData(i)
                if item_data and item_data.get('url') == selected_url:
                    self.favorites_list.SetSelection(i)
                    break
            else:
                # If the selected item was removed, select the item at the same index
                if current_selection and self.favorites_list.GetCount() > 0:
                    new_idx = min(current_selection[0], self.favorites_list.GetCount() - 1)
                    self.favorites_list.SetSelection(new_idx)
        
        self.on_selection_change(None)

    def on_list_key_down(self, event):
        keyCode = event.GetKeyCode()
        if keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_play_selected(event)
        elif keyCode == wx.WXK_DELETE:
            self.on_remove_selected(event)
        elif keyCode == wx.WXK_TAB:
            flags = wx.NavigationKeyEvent.IsBackward if event.ShiftDown() else wx.NavigationKeyEvent.IsForward
            event.GetEventObject().Navigate(flags)
        else:
            event.Skip()

    def on_selection_change(self, event):
        if not self.favorites_list or not self.favorites_list.IsEnabled():
            self.play_button.Disable()
            self.remove_button.Disable()
            if event: event.Skip()
            return

        num_sel = len(self.favorites_list.GetSelections())
        self.play_button.Enable(num_sel == 1)
        self.remove_button.Enable(num_sel > 0)

        if num_sel == 1 and event is not None:
            try:
                utils.play_sound(self.main_frame.settings, "list_navigate")
                nvda.speak(self.favorites_list.GetString(self.favorites_list.GetSelections()[0]))
                data = self.favorites_list.GetClientData(self.favorites_list.GetSelections()[0])
                if data and isinstance(data, dict) and data.get('url') and hasattr(self.main_frame, 'audio_player_panel'):
                    self.main_frame.audio_player_panel.prefetch_stream_url(data['url'])
            except Exception:
                pass

        if event: event.Skip()

    def on_play_selected(self, event):
        if not self.favorites_list.IsEnabled():
            nvda.speak(_("Please select a song from the favorites list."))
            return

        sel = self.favorites_list.GetSelections()
        if len(sel) == 1:
            try:
                entry = self.favorites_list.GetClientData(sel[0])
                if entry and isinstance(entry, dict) and 'url' in entry:
                    nvda.speak(_("Playing from favorites: {}").format(entry.get('title', 'song')))
                    self.main_frame.request_audio_play(entry['url'], entry.get('title'), entry.get('uploader'), index=None)
                else:
                    utils.show_error_dialog(self, _("Error retrieving favorite song data."), _("Favorites Error"))
            except Exception as e:
                utils.show_error_dialog(self, _("Error playing favorite song:\n{}").format(e), _("Playback Error"))
        elif len(sel) == 0:
            nvda.speak(_("Please select a song from the favorites list."))
        else:
            nvda.speak(_("Please select exactly one song to play."))

    def on_remove_selected(self, event):
        if not self.favorites_list.IsEnabled():
            nvda.speak(_("Please select a song from the favorites list."))
            return

        sel_indices = self.favorites_list.GetSelections()
        if not sel_indices:
            nvda.speak(_("Please select a song from the favorites list."))
            return

        items_to_remove_data = [self.favorites_list.GetClientData(i) for i in sel_indices if self.favorites_list.GetClientData(i)]
        if not items_to_remove_data:
            return

        for item in items_to_remove_data:
            self.main_frame.remove_from_favorites(item['url'])
        
        nvda.speak(_("Removed selected song(s) from favorites."))

    def on_context_menu(self, event):
        if not self.favorites_list.IsEnabled() or not self.favorites_list.GetSelections():
            return

        menu = wx.Menu()
        play_item = menu.Append(wx.ID_ANY, _("Play"))
        queue_item = menu.Append(wx.ID_ANY, _("Play Next (Add to Queue)"))
        remove_item = menu.Append(wx.ID_ANY, _("Remove from Favorites"))

        def _on_queue(e):
            sel = self.favorites_list.GetSelections()
            if sel:
                entry = self.favorites_list.GetClientData(sel[0])
                self.main_frame.audio_player_panel.add_to_queue(entry, play_next=True)

        menu.Bind(wx.EVT_MENU, self.on_play_selected, play_item)
        menu.Bind(wx.EVT_MENU, _on_queue, queue_item)
        menu.Bind(wx.EVT_MENU, self.on_remove_selected, remove_item)

        self.PopupMenu(menu)
        menu.Destroy()
