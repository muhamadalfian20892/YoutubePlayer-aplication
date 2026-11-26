import wx
from datetime import datetime, timezone

# Local application imports
import nvda
import constants
import utils
import feature_manager
from translation_manager import _

class HistoryPanel(wx.Panel):
    """
    A wx.Panel that displays the user's playback history, with options
    to search, play, remove, and clear items.
    """
    def __init__(self, parent, main_frame):
        super().__init__(parent)
        self.main_frame = main_frame
        self.full_history_data = []
        self.current_search_query = ""
        self.InitUI()
        self.load_history()

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Search control
        search_hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.search_label = wx.StaticText(self, label="")
        search_hbox.Add(self.search_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        self.search_ctrl = wx.SearchCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.search_ctrl.ShowCancelButton(True)
        search_hbox.Add(self.search_ctrl, proportion=1, flag=wx.EXPAND)
        vbox.Add(search_hbox, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        # History list
        self.history_list = wx.ListBox(self, style=wx.LB_EXTENDED | wx.LB_HSCROLL | wx.WANTS_CHARS)
        vbox.Add(self.history_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        # Buttons
        hbox_buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.play_button = wx.Button(self, label="")
        self.copy_link_button = wx.Button(self, label="")
        self.remove_button = wx.Button(self, label="")
        self.export_button = wx.Button(self, label="")
        self.clear_button = wx.Button(self, label="")

        hbox_buttons.Add(self.play_button, flag=wx.RIGHT, border=10)
        hbox_buttons.Add(self.copy_link_button, flag=wx.RIGHT, border=10)
        hbox_buttons.Add(self.remove_button, flag=wx.RIGHT, border=10)
        hbox_buttons.Add(self.export_button, flag=wx.RIGHT, border=10)
        hbox_buttons.AddStretchSpacer(1)
        hbox_buttons.Add(self.clear_button, flag=wx.LEFT, border=10)
        vbox.Add(hbox_buttons, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        self.SetSizer(vbox)

        # Bind events
        self.search_ctrl.Bind(wx.EVT_TEXT, self.on_history_search_change)
        self.search_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_history_search_change)
        self.search_ctrl.Bind(wx.EVT_SEARCHCTRL_SEARCH_BTN, self.on_history_search_change)
        self.search_ctrl.Bind(wx.EVT_SEARCHCTRL_CANCEL_BTN, self.on_history_search_cancel)
        self.history_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_play_selected)
        self.history_list.Bind(wx.EVT_LISTBOX, self.on_selection_change)
        self.history_list.Bind(wx.EVT_KEY_DOWN, self.on_list_key_down)
        self.history_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
        self.play_button.Bind(wx.EVT_BUTTON, self.on_play_selected)
        self.copy_link_button.Bind(wx.EVT_BUTTON, lambda e: self.on_copy_link())
        self.remove_button.Bind(wx.EVT_BUTTON, self.on_remove_selected)
        self.export_button.Bind(wx.EVT_BUTTON, self.on_export_history)
        self.clear_button.Bind(wx.EVT_BUTTON, self.on_clear_history)

        # Initial button states
        self.play_button.Disable()
        self.copy_link_button.Disable()
        self.remove_button.Disable()
        self.export_button.Disable()
        self.clear_button.Disable()

        # Tab Order
        self.history_list.MoveAfterInTabOrder(self.search_ctrl)
        self.play_button.MoveAfterInTabOrder(self.history_list)
        self.copy_link_button.MoveAfterInTabOrder(self.play_button)
        self.remove_button.MoveAfterInTabOrder(self.copy_link_button)
        self.export_button.MoveAfterInTabOrder(self.remove_button)
        self.clear_button.MoveAfterInTabOrder(self.export_button)

        self.retranslate_ui()

    def retranslate_ui(self):
        """Updates all translatable text on the panel."""
        self.search_label.SetLabel(_("Search History:"))
        self.search_ctrl.SetName(_("Search History"))
        self.search_ctrl.SetToolTip(_("Type to search played videos by title or uploader."))
        self.history_list.SetName(_("History List"))
        self.history_list.SetToolTip(_("List of recently played videos (max {max_items}). Double-click or Enter to play.").format(max_items=constants.MAX_PLAY_HISTORY_ITEMS))

        self.play_button.SetLabel(_("Play Selected"))
        self.play_button.SetName(_("Play Selected"))
        self.play_button.SetToolTip(_("Play the selected video from history"))
        self.copy_link_button.SetLabel(_("Copy Link"))
        self.copy_link_button.SetName(_("Copy Link"))
        self.copy_link_button.SetToolTip(_("Copy the URL of the selected item to clipboard"))
        self.remove_button.SetLabel(_("Remove Selected"))
        self.remove_button.SetName(_("Remove Selected"))
        self.remove_button.SetToolTip(_("Remove the selected video(s) from history"))
        self.export_button.SetLabel(_("Export Playlist"))
        self.export_button.SetName(_("Export Playlist"))
        self.export_button.SetToolTip(_("Export the currently displayed history to a playlist file"))
        self.clear_button.SetLabel(_("Clear All History"))
        self.clear_button.SetName(_("Clear All History"))
        self.clear_button.SetToolTip(_("Clear the entire play history"))

        # We need to redisplay the history to apply translations to timestamps etc.
        self.filter_and_display_history()
        self.Layout()

    def on_history_search_change(self, event):
        query = self.search_ctrl.GetValue().lower().strip()
        if query != self.current_search_query:
            self.current_search_query = query
            self.filter_and_display_history()
        event.Skip()

    def on_history_search_cancel(self, event):
        self.search_ctrl.SetValue("")
        if self.current_search_query:
            self.current_search_query = ""
            self.filter_and_display_history()
        self.history_list.SetFocus()
        event.Skip()

    def load_history(self):
        """Loads full history data from settings and triggers display."""
        self.full_history_data = self.main_frame.settings.get("play_history", [])
        self.filter_and_display_history()

    def filter_and_display_history(self):
        """Filters full history based on the search query and updates the listbox."""
        self.history_list.Clear()
        query = self.current_search_query
        history_to_display = []

        if not query:
            history_to_display = self.full_history_data
        else:
            for entry in self.full_history_data:
                title = entry.get('title', '').lower()
                uploader = entry.get('uploader', '').lower()
                if query in title or query in uploader:
                    history_to_display.append(entry)

        if not history_to_display:
            if query:
                self.history_list.Append(_("No history items match '{}'.").format(query))
            else:
                self.history_list.Append(_("Play history is empty."))
            self.history_list.Disable()
            self.play_button.Disable()
            self.remove_button.Disable()
            self.export_button.Disable()
        else:
            self.history_list.Enable()
            for entry in reversed(history_to_display): # Display newest first
                if isinstance(entry, dict) and 'title' in entry and 'url' in entry:
                    title = entry.get('title', 'N/A')
                    uploader = entry.get('uploader', 'N/A')
                    played_time_str = self._format_timestamp(entry.get('timestamp', ''))
                    duration_str = entry.get('duration_string') or utils.format_duration(entry.get('duration'))
                    
                    list_str = f"{title}. duration: {duration_str} uploaded by {uploader}"
                    
                    upload_date_str = utils.format_upload_date(entry.get('upload_date'))
                    if upload_date_str != _("Unknown Date") and upload_date_str != _("Invalid Date"):
                        list_str += f", {_('uploaded')} {upload_date_str}"
                    
                    list_str += f" ({_('played')} {played_time_str})"
                    
                    self.history_list.Append(list_str, clientData=entry)
                else:
                    print(f"Skipping invalid history entry during display: {entry}")
            self.history_list.SetSelection(wx.NOT_FOUND)
            self.on_selection_change(None)

        self.export_button.Enable(bool(history_to_display))
        self.clear_button.Enable(bool(self.full_history_data))

    def refresh_list(self):
        """Public method to reload history and re-apply the current filter."""
        current_sel_strings = []
        if self.history_list.IsEnabled():
            selected_indices = self.history_list.GetSelections()
            current_sel_strings = [self.history_list.GetString(i) for i in selected_indices]

        self.load_history()

        if current_sel_strings and self.history_list.IsEnabled():
            new_selections = [i for i in range(self.history_list.GetCount()) if self.history_list.GetString(i) in current_sel_strings]
            for idx in new_selections:
                self.history_list.SetSelection(idx, True)
        self.on_selection_change(None)

    def on_copy_link(self, url=None):
        if not url and self.history_list.IsEnabled():
            sel = self.history_list.GetSelections()
            if sel:
                entry = self.history_list.GetClientData(sel[0])
                if entry and isinstance(entry, dict):
                    url = entry.get('url')
        if url:
            utils.copy_text_to_clipboard(url)
            nvda.speak(_("Video link copied to clipboard."))
        else:
            nvda.speak(_("Could not copy link."))

    def on_list_key_down(self, event):
        keyCode = event.GetKeyCode()
        if keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_play_selected(event)
        elif event.ControlDown() and keyCode == ord('C'):
            self.on_copy_link()
        elif keyCode == wx.WXK_DELETE:
            self.on_remove_selected(event)
        elif keyCode == wx.WXK_TAB:
            flags = wx.NavigationKeyEvent.IsBackward if event.ShiftDown() else wx.NavigationKeyEvent.IsForward
            event.GetEventObject().Navigate(flags)
        else:
            event.Skip()

    def on_selection_change(self, event):
        if not self.history_list or not self.history_list.IsEnabled():
            self.play_button.Disable()
            self.copy_link_button.Disable()
            self.remove_button.Disable()
            self.export_button.Disable()
            if event: event.Skip()
            return

        num_sel = len(self.history_list.GetSelections())
        self.play_button.Enable(num_sel == 1)
        self.copy_link_button.Enable(num_sel == 1)
        self.remove_button.Enable(num_sel > 0)

        if num_sel == 1 and event is not None:
            try:
                utils.play_sound(self.main_frame.settings, "list_navigate")
                nvda.speak(self.history_list.GetString(self.history_list.GetSelections()[0]))
                data = self.history_list.GetClientData(self.history_list.GetSelections()[0])
                if data and isinstance(data, dict) and data.get('url') and hasattr(self.main_frame, 'audio_player_panel'):
                    self.main_frame.audio_player_panel.prefetch_stream_url(data['url'])
            except Exception:
                pass

        if event: event.Skip()

    def on_context_menu(self, event):
        if not self.history_list.IsEnabled(): return
        
        sel_indices = self.history_list.GetSelections()
        if not sel_indices: return

        menu = wx.Menu()
        menu_actions = {}

        def add_item(target_menu, label, action):
            item = target_menu.Append(wx.ID_ANY, label)
            menu_actions[item.GetId()] = action
            return item

        if len(sel_indices) == 1:
            entry = self.history_list.GetClientData(sel_indices[0])
            add_item(menu, _("Play Audio"), lambda: self.on_play_selected(None))
            if entry and isinstance(entry, dict) and entry.get('url'):
                add_item(menu, _("Play Next (Add to Queue)"), lambda: self.main_frame.audio_player_panel.add_to_queue(entry, play_next=True))
                add_item(menu, _("Copy Video Link"), lambda: self.on_copy_link(entry['url']))
            if feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_FAVORITES):
                add_item(menu, _("Add to Favorites"), lambda: self.main_frame.add_to_favorites(entry))
            if feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_DOWNLOADER) and entry and isinstance(entry, dict) and entry.get('url'):
                add_item(menu, _("Download with Downloader"), lambda: self.main_frame.show_ytdl_panel(initial_urls=[entry['url']]))
            menu.AppendSeparator()
        
        add_item(menu, _("Remove from History"), lambda: self.on_remove_selected(None))

        menu.Bind(wx.EVT_MENU, lambda e: menu_actions.get(e.GetId(), lambda: None)())
        self.PopupMenu(menu)
        menu.Destroy()

    def _format_timestamp(self, iso_timestamp_str):
        try:
            if isinstance(iso_timestamp_str, str):
                dt_utc = datetime.fromisoformat(iso_timestamp_str.replace('Z', '+00:00'))
                dt_local = dt_utc.astimezone(None)
                return dt_local.strftime("%Y-%m-%d %H:%M")
            return _("Invalid Timestamp")
        except (ValueError, TypeError):
            return _("Unknown Time")

    def on_play_selected(self, event):
        if not self.history_list.IsEnabled():
            nvda.speak(_("Please select an item from the history list."))
            return

        sel = self.history_list.GetSelections()
        if len(sel) == 1:
            try:
                entry = self.history_list.GetClientData(sel[0])
                if entry and isinstance(entry, dict) and 'url' in entry:
                    nvda.speak(_("Playing from history: {}").format(entry.get('title', 'video')))
                    self.main_frame.request_audio_play(entry['url'], entry.get('title'), entry.get('uploader'), index=None)
                else:
                    utils.show_error_dialog(self, _("Error retrieving history item data."), _("History Error"))
            except Exception as e:
                utils.show_error_dialog(self, _("Error playing history item:\n{}").format(e), _("Playback Error"))
        elif len(sel) == 0:
            nvda.speak(_("Please select an item from the history list."))
        else:
            nvda.speak(_("Please select exactly one item to play."))

    def on_remove_selected(self, event):
        if not self.history_list.IsEnabled():
            nvda.speak(_("Please select an item from the history list."))
            return

        sel_indices = self.history_list.GetSelections()
        if not sel_indices:
            nvda.speak(_("Please select an item from the history list."))
            return

        items_to_remove_data = [self.history_list.GetClientData(i) for i in sel_indices if self.history_list.GetClientData(i)]
        if not items_to_remove_data:
            return

        remove_identifiers = set((item.get('url'), item.get('timestamp')) for item in items_to_remove_data)
        current_full_history = self.main_frame.settings.get("play_history", [])
        new_full_history = [e for e in current_full_history if (e.get('url'), e.get('timestamp')) not in remove_identifiers]

        if len(current_full_history) > len(new_full_history):
            self.main_frame.settings["play_history"] = new_full_history
            self.main_frame.save_settings()
            self.refresh_list()
            nvda.speak(_("Removed selected item(s) from history."))
        else:
            self.refresh_list()

    def on_clear_history(self, event):
        if not self.full_history_data:
            nvda.speak(_("Play history is empty."))
            return

        with wx.MessageDialog(self, _("Are you sure you want to clear the entire play history? This cannot be undone."), _("Confirm Clear History"),
                              wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING) as dlg:
            dlg.CentreOnParent()
            utils.play_sound(self.main_frame.settings, "confirm_prompt")
            if dlg.ShowModal() == wx.ID_YES:
                self.main_frame.settings["play_history"] = []
                self.main_frame.save_settings()
                self.refresh_list()
                nvda.speak(_("Play history cleared."))

    def on_export_history(self, event):
        """Exports the currently displayed history items to a playlist file."""
        if not self.history_list.IsEmpty():
            # Get valid export candidates from current filter
            query = self.current_search_query
            history_to_export = []
            
            if not query:
                history_to_export = self.full_history_data
            else:
                 for entry in self.full_history_data:
                    title = entry.get('title', '').lower()
                    uploader = entry.get('uploader', '').lower()
                    if query in title or query in uploader:
                        history_to_export.append(entry)

            if not history_to_export:
                utils.show_message_dialog(self, _("No items to export."), _("Info"))
                return
            
            with wx.FileDialog(self, _("Export Playlist"), wildcard="M3U Playlist (*.m3u)|*.m3u|PLS Playlist (*.pls)|*.pls",
                               style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
                if fileDialog.ShowModal() == wx.ID_CANCEL:
                    return
                pathname = fileDialog.GetPath()

            if utils.save_playlist_file(pathname, history_to_export):
                utils.show_message_dialog(self, _("History exported successfully."), _("Success"))
                nvda.speak(_("History exported successfully."), constants.NVDA_VERBOSITY_DEFAULT)
            else:
                utils.show_error_dialog(self.main_frame, _("Failed to export history."))