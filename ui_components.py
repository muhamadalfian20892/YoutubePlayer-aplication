import copy
import wx

# Local application imports
import nvda
import constants
import utils
from translation_manager import _

class LanguageSelectionDialog(wx.Dialog):
    """
    A dialog for selecting the application's display language.
    """
    def __init__(self, parent, current_lang_code):
        super().__init__(parent, style=wx.DEFAULT_DIALOG_STYLE)

        self.languages = constants.AVAILABLE_LANGUAGES
        self.lang_codes = list(self.languages.keys())
        self.selected_lang_code = current_lang_code
        
        self.panel = wx.Panel(self)
        self.prompt_label = wx.StaticText(self.panel, label="")
        self.lang_choice = wx.Choice(self.panel, choices=[])
        
        self.InitUI()
        self.retranslate_ui()
        self.CentreOnParent()
        
        # Play popup open sound
        app = wx.GetApp()
        if app and hasattr(app.GetTopWindow(), 'settings'):
            utils.play_sound(app.GetTopWindow().settings, "popup_open")

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.prompt_label, flag=wx.ALL, border=10)
        vbox.Add(self.lang_choice, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        btn_sizer = wx.StdDialogButtonSizer()
        self.ok_button = wx.Button(self.panel, wx.ID_OK)
        self.cancel_button = wx.Button(self.panel, wx.ID_CANCEL)
        btn_sizer.AddButton(self.ok_button)
        btn_sizer.AddButton(self.cancel_button)
        btn_sizer.Realize()

        vbox.Add(btn_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        self.panel.SetSizerAndFit(vbox)
        self.Fit()
        
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)

    def retranslate_ui(self):
        self.SetTitle(_("Change Application Language"))
        self.prompt_label.SetLabel(_("Please select your desired language."))
        
        lang_names = [self.languages[code] for code in self.lang_codes]
        current_selection = self.lang_choice.GetSelection()
        self.lang_choice.Set(lang_names)
        
        if current_selection != wx.NOT_FOUND:
            self.lang_choice.SetSelection(current_selection)
        else:
            try:
                current_index = self.lang_codes.index(self.selected_lang_code)
                self.lang_choice.SetSelection(current_index)
            except ValueError:
                self.lang_choice.SetSelection(0)
        
        self.lang_choice.SetName(_("Application Language"))
        self.ok_button.SetLabel(_("OK"))
        self.ok_button.SetName(_("OK"))
        self.cancel_button.SetLabel(_("Cancel"))
        self.cancel_button.SetName(_("Cancel"))
        self.panel.Layout()
        
    def on_ok(self, event):
        selected_index = self.lang_choice.GetSelection()
        if selected_index != wx.NOT_FOUND:
            self.selected_lang_code = self.lang_codes[selected_index]
        self.EndModal(wx.ID_OK)

    def get_selected_language_code(self):
        return self.selected_lang_code


class SoundSettingsDialog(wx.Dialog):
    """
    A dialog for enabling or disabling individual application sounds and adjusting their volumes.
    """
    def __init__(self, parent, sound_settings, master_volume, sound_effects_enabled=True):
        super().__init__(parent, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.sound_settings = sound_settings
        self.master_volume = master_volume
        self.sound_effects_enabled = sound_effects_enabled
        self.new_settings = None
        self.new_master_volume = None
        self.new_sound_effects_enabled = sound_effects_enabled
        
        self.sound_event_keys = list(constants.SOUND_EVENTS.keys())
        self.controls = {} # To hold {'check': checkbox, 'slider': slider}

        self.panel = wx.Panel(self)
        
        self.InitUI()
        self.retranslate_ui()
        self.load_initial_settings()
        self.CentreOnParent()
        self.SetInitialSize((550, 500))

        # Play popup open sound
        app = wx.GetApp()
        if app and hasattr(app.GetTopWindow(), 'settings'):
            utils.play_sound(app.GetTopWindow().settings, "popup_open")


    def InitUI(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Master SFX Toggle ---
        self.master_sfx_checkbox = wx.CheckBox(self.panel, label=_("Enable Sound Effects (SFX)"))
        self.master_sfx_checkbox.SetName(_("Enable Sound Effects (SFX)"))
        self.master_sfx_checkbox.SetValue(self.sound_effects_enabled)
        self.master_sfx_checkbox.Bind(wx.EVT_CHECKBOX, self.on_toggle_master_sfx)
        main_sizer.Add(self.master_sfx_checkbox, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        # --- Master Volume ---
        self.master_box = wx.StaticBox(self.panel, label="")
        master_sizer = wx.StaticBoxSizer(self.master_box, wx.VERTICAL)
        
        master_grid = wx.FlexGridSizer(cols=2, hgap=10, vgap=10)
        self.master_volume_label = wx.StaticText(self.panel, label="")
        self.master_volume_slider = wx.Slider(self.panel, value=self.master_volume, minValue=0, maxValue=100, style=wx.SL_HORIZONTAL | wx.SL_LABELS)
        self.master_volume_slider.SetName(_("Master Sound Effects Volume"))
        
        master_grid.Add(self.master_volume_label, 0, wx.ALIGN_CENTER_VERTICAL)
        master_grid.Add(self.master_volume_slider, 1, wx.EXPAND)
        master_grid.AddGrowableCol(1, 1)
        master_sizer.Add(master_grid, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(master_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # --- Individual Sound Settings ---
        self.sounds_box = wx.StaticBox(self.panel, label="")
        sounds_box_sizer = wx.StaticBoxSizer(self.sounds_box, wx.VERTICAL)

        scroll_win = wx.ScrolledWindow(self.panel, style=wx.VSCROLL)
        scroll_win.SetScrollRate(0, 5)
        
        self.grid_sizer = wx.FlexGridSizer(cols=2, hgap=10, vgap=15)
        self.grid_sizer.AddGrowableCol(0, 1) # Checkbox label column
        self.grid_sizer.AddGrowableCol(1, 1) # Slider column

        for key in self.sound_event_keys:
            description = _(constants.SOUND_EVENTS[key]["description"])
            
            checkbox = wx.CheckBox(scroll_win, label=description)
            checkbox.SetName(description)
            slider = wx.Slider(scroll_win, value=100, minValue=0, maxValue=100, style=wx.SL_HORIZONTAL)
            slider.SetName(_("{event} Volume").format(event=description))
            
            self.grid_sizer.Add(checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)
            self.grid_sizer.Add(slider, 0, wx.EXPAND)
            
            self.controls[key] = {'check': checkbox, 'slider': slider}
            checkbox.Bind(wx.EVT_CHECKBOX, lambda event, k=key: self.on_toggle_sound(event, k))

        scroll_win.SetSizer(self.grid_sizer)
        sounds_box_sizer.Add(scroll_win, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(sounds_box_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # --- Dialog Buttons ---
        btn_sizer = wx.StdDialogButtonSizer()
        self.ok_button = wx.Button(self.panel, wx.ID_OK)
        self.cancel_button = wx.Button(self.panel, wx.ID_CANCEL)
        btn_sizer.AddButton(self.ok_button)
        btn_sizer.AddButton(self.cancel_button)
        btn_sizer.Realize()
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.panel.SetSizer(main_sizer)

        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)

    def retranslate_ui(self):
        self.SetTitle(_("Sound Settings"))
        self.master_sfx_checkbox.SetLabel(_("Enable Sound Effects (SFX)"))
        self.master_box.SetLabel(_("Master Sound Effects Volume"))
        self.master_volume_label.SetLabel(_("Master Volume"))
        self.sounds_box.SetLabel(_("Individual Sound Volumes"))
        
        for key, control_dict in self.controls.items():
            description = _(constants.SOUND_EVENTS[key]["description"])
            control_dict['check'].SetLabel(description)
            control_dict['check'].SetName(description)
            control_dict['slider'].SetName(_("{event} Volume").format(event=description))

        self.ok_button.SetLabel(_("OK"))
        self.cancel_button.SetLabel(_("Cancel"))
        self.panel.Layout()

    def load_initial_settings(self):
        """Loads the current settings into the UI controls."""
        self.master_sfx_checkbox.SetValue(self.sound_effects_enabled)
        self.master_volume_slider.SetValue(self.master_volume)
        
        master_enabled = self.sound_effects_enabled
        self.master_volume_slider.Enable(master_enabled)

        for key, settings in self.sound_settings.items():
            if key in self.controls:
                is_enabled = settings.get("enabled", True)
                volume = settings.get("volume", 100)
                
                self.controls[key]['check'].SetValue(is_enabled)
                self.controls[key]['slider'].SetValue(volume)
                self.controls[key]['check'].Enable(master_enabled)
                self.controls[key]['slider'].Enable(master_enabled and is_enabled)

    def on_toggle_master_sfx(self, event):
        enabled = self.master_sfx_checkbox.IsChecked()
        self.master_volume_slider.Enable(enabled)
        for key, control_dict in self.controls.items():
            check_enabled = control_dict['check'].IsChecked()
            control_dict['check'].Enable(enabled)
            control_dict['slider'].Enable(enabled and check_enabled)
        state_text = _("enabled") if enabled else _("disabled")
        nvda.speak(f"{_('Sound Effects')} {state_text}")

    def on_toggle_sound(self, event, key):
        checkbox = event.GetEventObject()
        is_checked = checkbox.IsChecked()
        self.controls[key]['slider'].Enable(is_checked and self.master_sfx_checkbox.IsChecked())
        
        label = _(constants.SOUND_EVENTS[key]["description"])
        state_text = _("enabled") if is_checked else _("disabled")
        nvda.speak(f"{label} {state_text}", constants.NVDA_VERBOSITY_VERBOSE)

    def on_ok(self, event):
        self.new_sound_effects_enabled = self.master_sfx_checkbox.IsChecked()
        self.new_master_volume = self.master_volume_slider.GetValue()
        self.new_settings = {}
        for key, control_dict in self.controls.items():
            self.new_settings[key] = {
                "enabled": control_dict['check'].IsChecked(),
                "volume": control_dict['slider'].GetValue()
            }
        self.EndModal(wx.ID_OK)

    def get_new_settings(self):
        return self.new_settings, self.new_master_volume, self.new_sound_effects_enabled


class SearchResultsDialog(wx.Dialog):
    def __init__(self, parent, title, results):
        super().__init__(parent, title=title, size=(650, 450), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.results = results
        self.selected_result = None
        self.selected_index = wx.NOT_FOUND
        
        self.panel = wx.Panel(self)
        self.instructions = wx.StaticText(self.panel, label="")
        self.result_list = wx.ListBox(self.panel, style=wx.LB_SINGLE | wx.LB_HSCROLL | wx.WANTS_CHARS)
        self.result_list.SetName(_("Lyrics Search Results"))
        self.ok_button = wx.Button(self.panel, wx.ID_OK)
        self.cancel_button = wx.Button(self.panel, wx.ID_CANCEL)
        
        self.InitUI()
        self.retranslate_ui()
        self.CentreOnParent()

        # Play popup open sound
        app = wx.GetApp()
        if app and hasattr(app.GetTopWindow(), 'settings'):
            utils.play_sound(app.GetTopWindow().settings, "popup_open")

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.instructions, flag=wx.ALL, border=10)
        vbox.Add(self.result_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        self.result_list.Bind(wx.EVT_LISTBOX, self.OnListSelect)
        self.result_list.Bind(wx.EVT_LISTBOX_DCLICK, self.OnOK)
        self.result_list.Bind(wx.EVT_KEY_DOWN, self.OnListKeyDown)

        hbox = wx.StdDialogButtonSizer()
        hbox.AddButton(self.ok_button)
        hbox.AddButton(self.cancel_button)
        hbox.Realize()
        vbox.Add(hbox, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        self.panel.SetSizer(vbox)
        self.ok_button.MoveAfterInTabOrder(self.result_list)
        self.cancel_button.MoveAfterInTabOrder(self.ok_button)
        self.result_list.SetFocus()
        
        self.Bind(wx.EVT_BUTTON, self.OnOK, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.OnCancel, id=wx.ID_CANCEL)
        
    def retranslate_ui(self):
        self.SetTitle(_("Lyrics Search Results"))
        self.instructions.SetLabel(_("Matching results found. Use up/down arrows to navigate and Enter to select:"))
        self.result_list.SetToolTip(_("List of lyrics search results"))
        self.ok_button.SetLabel(_("OK"))
        self.ok_button.SetToolTip(_("Select the highlighted lyrics and close"))
        self.cancel_button.SetLabel(_("Cancel"))
        self.cancel_button.SetToolTip(_("Close without selecting lyrics"))

        self.result_list.Clear()
        for hit in self.results:
            try:
                result_data = hit.get('result', {})
                release_year_components = result_data.get('release_date_components')
                primary_artist = result_data.get('primary_artist', {})
                title = result_data.get('title', _('Unknown Title'))
                artist_name = primary_artist.get('name', _('Unknown Artist'))
                
                release_year = 'N/A'
                if release_year_components and isinstance(release_year_components, dict):
                    release_year = release_year_components.get('year', 'N/A')
                
                result_str = f"{title} - {artist_name} ({release_year})"
                self.result_list.Append(result_str)
            except Exception as e:
                print(f"Error processing lyrics result: {e}. Data: {hit}")
                self.result_list.Append(f"{hit.get('full_title', _('Unknown Result (Format Error)'))}")
        self.panel.Layout()
        
    def OnListKeyDown(self, event):
        keyCode = event.GetKeyCode()
        if keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER): self.OnOK(event)
        elif keyCode == wx.WXK_TAB:
            flags = wx.NavigationKeyEvent.IsBackward if event.ShiftDown() else wx.NavigationKeyEvent.IsForward
            event.GetEventObject().Navigate(flags)
        else: event.Skip()

    def OnListSelect(self, event):
        self.selected_index = self.result_list.GetSelection()
        if self.selected_index != wx.NOT_FOUND:
            if 0 <= self.selected_index < len(self.results):
                self.selected_result = self.results[self.selected_index]
                nvda.speak(self.result_list.GetString(self.selected_index), constants.NVDA_VERBOSITY_VERBOSE)
                
                # Play popup navigate sound
                app = wx.GetApp()
                if app and hasattr(app.GetTopWindow(), 'settings'):
                    utils.play_sound(app.GetTopWindow().settings, "popup_navigate")
            else:
                self.selected_result = None
        event.Skip()

    def OnOK(self, event):
        selected_index = self.result_list.GetSelection()
        if selected_index == wx.NOT_FOUND:
            utils.show_message_dialog(self, _("Please select a search result."), _("Warning"), wx.OK | wx.ICON_WARNING)
            return
        if 0 <= selected_index < len(self.results):
            self.selected_result = self.results[selected_index]
            self.EndModal(wx.ID_OK)
        else:
            self.EndModal(wx.ID_CANCEL)

    def OnCancel(self, event):
        self.selected_result = None
        self.EndModal(wx.ID_CANCEL)

    def GetSelectedResult(self):
        return self.selected_result


class KeyCaptureDialog(wx.Dialog):
    def __init__(self, parent, action_type):
        super().__init__(parent, style=wx.DEFAULT_DIALOG_STYLE)
        self.action_type = action_type
        self.new_key_combo = None

        self.panel = wx.Panel(self)
        self.label = wx.StaticText(self.panel, label="")
        
        self.InitUI()
        self.retranslate_ui()
        self.CentreOnParent()

        # Play popup open sound
        app = wx.GetApp()
        if app and hasattr(app.GetTopWindow(), 'settings'):
            utils.play_sound(app.GetTopWindow().settings, "popup_open")

        nvda.speak(_("Press the desired key combination now. Press Escape to cancel."))

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.label, flag=wx.ALL | wx.ALIGN_CENTER, border=20)
        self.panel.SetSizerAndFit(vbox)
        self.panel.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.panel.SetFocus()

    def retranslate_ui(self):
        self.SetTitle(_("Set New Shortcut"))
        self.label.SetLabel(_("Press the desired key combination now...\n(Press Escape to cancel)"))
        self.panel.Layout()

    def on_key_down(self, event):
        key_code = event.GetKeyCode()
        mods = event.GetModifiers()
        
        if key_code in (wx.WXK_CONTROL, wx.WXK_ALT, wx.WXK_SHIFT, wx.WXK_WINDOWS_LEFT, wx.WXK_WINDOWS_RIGHT):
            return

        if key_code == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return

        if self.action_type == 'global':
            win_mods = 0
            if mods & wx.ACCEL_ALT: win_mods |= constants.MOD_ALT
            if mods & wx.ACCEL_CTRL: win_mods |= constants.MOD_CONTROL
            if mods & wx.ACCEL_SHIFT: win_mods |= constants.MOD_SHIFT
            
            # Map common wx keys to VK codes for Windows API
            wx_to_vk = {
                wx.WXK_LEFT: constants.VK_LEFT,
                wx.WXK_RIGHT: constants.VK_RIGHT,
                wx.WXK_UP: constants.VK_UP,
                wx.WXK_DOWN: constants.VK_DOWN,
            }
            vk_code = wx_to_vk.get(key_code, key_code)
            
            self.new_key_combo = (win_mods, vk_code)
        else:
            wx_mods = wx.ACCEL_NORMAL
            if mods & wx.ACCEL_ALT: wx_mods |= wx.ACCEL_ALT
            if mods & wx.ACCEL_CTRL: wx_mods |= wx.ACCEL_CTRL
            if mods & wx.ACCEL_SHIFT: wx_mods |= wx.ACCEL_SHIFT
            self.new_key_combo = (wx_mods, key_code)
            
        self.EndModal(wx.ID_OK)

    def get_key_combo(self):
        return self.new_key_combo


class KeyboardShortcutsDialog(wx.Dialog):
    def __init__(self, parent, current_config):
        super().__init__(parent, size=(600, 500), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main_frame = parent
        self.config = {k: v for k, v in current_config.items()}
        
        self.panel = wx.Panel(self)
        self.instructions = wx.StaticText(self.panel, label="")
        self.list_ctrl = wx.ListCtrl(self.panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.list_ctrl.SetName(_("Keyboard Shortcuts"))
        self.change_btn = wx.Button(self.panel, label="")
        self.reset_btn = wx.Button(self.panel, label="")
        self.reset_all_btn = wx.Button(self.panel, label="")
        self.ok_button = wx.Button(self.panel, wx.ID_OK)
        self.cancel_button = wx.Button(self.panel, wx.ID_CANCEL)

        self.InitUI()
        self.retranslate_ui()
        self.CentreOnParent()

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.instructions, flag=wx.ALL, border=10)
        vbox.Add(self.list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        hbox_buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.change_btn.Disable()
        self.reset_btn.Disable()
        hbox_buttons.Add(self.change_btn, 0, wx.RIGHT, 5)
        hbox_buttons.Add(self.reset_btn, 0, wx.RIGHT, 15)
        hbox_buttons.Add(self.reset_all_btn, 0)
        vbox.Add(hbox_buttons, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        btn_sizer = wx.StdDialogButtonSizer()
        btn_sizer.AddButton(self.ok_button)
        btn_sizer.AddButton(self.cancel_button)
        btn_sizer.Realize()
        vbox.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.panel.SetSizer(vbox)

        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_item_select)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.on_item_deselect)
        self.change_btn.Bind(wx.EVT_BUTTON, self.on_change_shortcut)
        self.reset_btn.Bind(wx.EVT_BUTTON, self.on_reset_shortcut)
        self.reset_all_btn.Bind(wx.EVT_BUTTON, self.on_reset_all)
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)
        
    def retranslate_ui(self):
        self.SetTitle(_("Keyboard Shortcuts"))
        self.instructions.SetLabel(_("Select an action and change its shortcut. Global shortcuts work even when the app is not focused."))
        self.change_btn.SetLabel(_("Change Shortcut..."))
        self.reset_btn.SetLabel(_("Reset to Default"))
        self.reset_all_btn.SetLabel(_("Reset All"))
        self.ok_button.SetLabel(_("OK"))
        self.cancel_button.SetLabel(_("Cancel"))
        
        if self.list_ctrl.GetColumnCount() > 0:
            col0 = wx.ListItem()
            col0.SetText(_("Action"))
            col0.SetWidth(300)
            self.list_ctrl.SetColumn(0, col0)
            col1 = wx.ListItem()
            col1.SetText(_("Shortcut"))
            col1.SetWidth(200)
            self.list_ctrl.SetColumn(1, col1)
        self.populate_list()
        self.panel.Layout()

    def populate_list(self):
        selected_index = self.list_ctrl.GetFirstSelected()
        self.list_ctrl.DeleteAllItems()
        self.action_keys_in_order = []
        
        if self.list_ctrl.GetColumnCount() == 0:
            self.list_ctrl.InsertColumn(0, _("Action"), width=300)
            self.list_ctrl.InsertColumn(1, _("Shortcut"), width=200)

        for action_key, details in constants.CUSTOMIZABLE_ACTIONS.items():
            mods, key = self.config.get(action_key, details["default"])
            shortcut_str = self.format_shortcut(mods, key, details["type"])
            
            index = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), _(details["description"]))
            self.list_ctrl.SetItem(index, 1, shortcut_str)
            self.list_ctrl.SetItemData(index, len(self.action_keys_in_order))
            self.action_keys_in_order.append(action_key)

        if selected_index != -1 and selected_index < self.list_ctrl.GetItemCount():
            self.list_ctrl.Select(selected_index)
            self.list_ctrl.Focus(selected_index)

    def format_shortcut(self, mods, key, action_type):
        parts = []
        is_global = action_type == 'global'
        
        if is_global:
            if mods & constants.MOD_CONTROL: parts.append("Ctrl")
            if mods & constants.MOD_ALT: parts.append("Alt")
            if mods & constants.MOD_SHIFT: parts.append("Shift")
        else:
            if mods & wx.ACCEL_CTRL: parts.append("Ctrl")
            if mods & wx.ACCEL_ALT: parts.append("Alt")
            if mods & wx.ACCEL_SHIFT: parts.append("Shift")
        
        key_map = {
            wx.WXK_LEFT: "Left", wx.WXK_RIGHT: "Right", wx.WXK_UP: "Up", wx.WXK_DOWN: "Down",
            wx.WXK_RETURN: "Enter", wx.WXK_TAB: "Tab", wx.WXK_BACK: "Backspace",
            wx.WXK_DELETE: "Delete", wx.WXK_ESCAPE: "Escape", wx.WXK_SPACE: "Space"
        }
        
        if is_global:
            vk_map = {
                constants.VK_LEFT: "Left", constants.VK_RIGHT: "Right",
                constants.VK_UP: "Up", constants.VK_DOWN: "Down"
            }
            key_map.update(vk_map)

        if key in key_map:
            parts.append(key_map[key])
        elif wx.WXK_F1 <= key <= wx.WXK_F24:
            parts.append(f"F{key - wx.WXK_F1 + 1}")
        elif 32 < key < 127 and chr(key).isprintable():
            parts.append(chr(key).upper())
        else:
            parts.append(f"Keycode {key}")
            
        return "+".join(parts)

    def on_item_select(self, event):
        self.change_btn.Enable(True)
        self.reset_btn.Enable(True)
        
        # Play popup navigate sound
        app = wx.GetApp()
        if app and hasattr(app.GetTopWindow(), 'settings'):
            utils.play_sound(app.GetTopWindow().settings, "popup_navigate")
        
    def on_item_deselect(self, event):
        self.change_btn.Enable(False)
        self.reset_btn.Enable(False)

    def on_change_shortcut(self, event):
        selected_index = self.list_ctrl.GetFirstSelected()
        if selected_index == -1: return
        
        item_data_idx = self.list_ctrl.GetItemData(selected_index)
        action_key = self.action_keys_in_order[item_data_idx]
        action_type = constants.CUSTOMIZABLE_ACTIONS[action_key]["type"]

        with KeyCaptureDialog(self, action_type) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                new_combo = dlg.get_key_combo()
                if new_combo:
                    self.config[action_key] = new_combo
                    self.populate_list()
                    nvda.speak(_("Shortcut changed."), constants.NVDA_VERBOSITY_DEFAULT)

    def on_reset_shortcut(self, event):
        selected_index = self.list_ctrl.GetFirstSelected()
        if selected_index == -1: return
        
        item_data_idx = self.list_ctrl.GetItemData(selected_index)
        action_key = self.action_keys_in_order[item_data_idx]

        if action_key in self.config:
            del self.config[action_key]
            self.populate_list()
            nvda.speak(_("Shortcut reset to default."), constants.NVDA_VERBOSITY_DEFAULT)

    def on_reset_all(self, event):
        with wx.MessageDialog(self, _("Are you sure you want to reset all shortcuts to their default values?"), _("Confirm Reset"), wx.YES_NO | wx.ICON_WARNING) as dlg:
            st = getattr(self.main_frame, 'settings', {}) if hasattr(self, 'main_frame') and self.main_frame else {}
            if not st:
                app = wx.GetApp()
                if app and hasattr(app.GetTopWindow(), 'settings'):
                    st = app.GetTopWindow().settings
            utils.play_sound(st, "confirm_prompt")
            if dlg.ShowModal() == wx.ID_YES:
                self.config.clear()
                self.populate_list()
                nvda.speak(_("All shortcuts reset to default."), constants.NVDA_VERBOSITY_DEFAULT)

    def on_ok(self, event):
        self.EndModal(wx.ID_OK)

    def get_new_config(self):
        return self.config


class EqualizerDialog(wx.Dialog):
    """
    A dialog for adjusting audio equalizer settings.
    """
    def __init__(self, parent, eq_settings):
        super().__init__(parent, title=_("Audio Equalizer"), size=(750, 450), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main_frame = parent
        self.settings = copy.deepcopy(eq_settings)
        self.band_sliders = []

        self.panel = wx.Panel(self)
        self.InitUI()
        self.load_settings()
        self.CentreOnParent()

        # Play popup open sound
        app = wx.GetApp()
        if app and hasattr(app.GetTopWindow(), 'settings'):
            utils.play_sound(app.GetTopWindow().settings, "popup_open")

    def InitUI(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.enable_check = wx.CheckBox(self.panel, label=_("Enable Equalizer"))
        top_sizer.Add(self.enable_check, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)
        
        preset_label = wx.StaticText(self.panel, label=_("Preset:"))
        top_sizer.Add(preset_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.preset_choice = wx.Choice(self.panel)
        top_sizer.Add(self.preset_choice, 1, wx.ALIGN_CENTER_VERTICAL)
        main_sizer.Add(top_sizer, 0, wx.EXPAND | wx.ALL, 10)

        slider_area_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        preamp_box = wx.StaticBox(self.panel, label=_("Pre-Amp"))
        preamp_sizer = wx.StaticBoxSizer(preamp_box, wx.VERTICAL)
        self.preamp_slider = wx.Slider(self.panel, style=wx.SL_VERTICAL | wx.SL_INVERSE, 
                                       minValue=constants.PREAMP_MIN_PERCENT, maxValue=constants.PREAMP_MAX_PERCENT)
        self.preamp_slider.SetName(_("Pre-Amp Gain"))
        preamp_sizer.Add(self.preamp_slider, 1, wx.EXPAND | wx.ALL, 5)
        slider_area_sizer.Add(preamp_sizer, 0, wx.EXPAND | wx.RIGHT, 10)

        bands_box = wx.StaticBox(self.panel, label=_("Frequency Bands (dB)"))
        bands_sizer = wx.StaticBoxSizer(bands_box, wx.HORIZONTAL)
        
        for i, freq in enumerate(constants.EQUALIZER_FREQUENCIES):
            band_vbox = wx.BoxSizer(wx.VERTICAL)
            label_text = f"{freq/1000:.1f}k" if freq >= 1000 else str(freq)
            freq_label = wx.StaticText(self.panel, label=label_text)
            band_vbox.Add(freq_label, 0, wx.ALIGN_CENTER | wx.BOTTOM, 5)
            
            slider = wx.Slider(self.panel, value=0, minValue=int(constants.EQUALIZER_MIN_GAIN * 10), 
                               maxValue=int(constants.EQUALIZER_MAX_GAIN * 10), style=wx.SL_VERTICAL | wx.SL_INVERSE)
            slider.SetName(_("{freq} Band Gain").format(freq=label_text))
            slider.Bind(wx.EVT_SLIDER, self.on_band_change)
            self.band_sliders.append(slider)
            band_vbox.Add(slider, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
            bands_sizer.Add(band_vbox, 1, wx.EXPAND)
            
        slider_area_sizer.Add(bands_sizer, 1, wx.EXPAND)
        main_sizer.Add(slider_area_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        bottom_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.save_preset_btn = wx.Button(self.panel, label=_("Save Preset..."))
        self.delete_preset_btn = wx.Button(self.panel, label=_("Delete Preset"))
        self.reset_btn = wx.Button(self.panel, label=_("Reset Bands"))
        bottom_btn_sizer.Add(self.save_preset_btn, 0, wx.RIGHT, 5)
        bottom_btn_sizer.Add(self.delete_preset_btn, 0, wx.RIGHT, 5)
        bottom_btn_sizer.Add(self.reset_btn, 0)
        bottom_btn_sizer.AddStretchSpacer(1)
        
        std_btn_sizer = wx.StdDialogButtonSizer()
        self.ok_button = wx.Button(self.panel, wx.ID_OK)
        self.cancel_button = wx.Button(self.panel, wx.ID_CANCEL)
        std_btn_sizer.AddButton(self.ok_button)
        std_btn_sizer.AddButton(self.cancel_button)
        std_btn_sizer.Realize()
        bottom_btn_sizer.Add(std_btn_sizer)
        
        main_sizer.Add(bottom_btn_sizer, 0, wx.EXPAND | wx.ALL, 10)
        self.panel.SetSizer(main_sizer)

        self.enable_check.Bind(wx.EVT_CHECKBOX, self.on_enable_toggle)
        self.preset_choice.Bind(wx.EVT_CHOICE, self.on_preset_select)
        self.preamp_slider.Bind(wx.EVT_SLIDER, self.on_preamp_change)
        self.save_preset_btn.Bind(wx.EVT_BUTTON, self.on_save_preset)
        self.delete_preset_btn.Bind(wx.EVT_BUTTON, self.on_delete_preset)
        self.reset_btn.Bind(wx.EVT_BUTTON, self.on_reset)
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)

    def load_settings(self):
        self.enable_check.SetValue(self.settings.get("enabled", False))
        self.preamp_slider.SetValue(self.settings.get("preamp", constants.DEFAULT_PREAMP_PERCENT))
        
        bands = self.settings.get("bands", constants.EQUALIZER_PRESETS["Flat"])
        for i, slider in enumerate(self.band_sliders):
            slider.SetValue(int(bands[i] * 10))

        self.populate_presets()
        self.on_enable_toggle(None)

    def populate_presets(self, selected_name=None):
        self.preset_choice.Clear()
        self.preset_choice.Append(_("<Custom>"))
        self.preset_choice.AppendItems(sorted(constants.EQUALIZER_PRESETS.keys()))
        
        custom_presets = self.settings.get("custom_presets", {})
        if custom_presets:
            self.preset_choice.Append("---")
            self.preset_choice.AppendItems(sorted(custom_presets.keys()))
        
        target = selected_name or self.settings.get("preset_name")
        if target and self.preset_choice.FindString(target) != wx.NOT_FOUND:
            self.preset_choice.SetStringSelection(target)
        else:
            current_bands = self.settings.get("bands")
            matched = False
            all_presets = constants.EQUALIZER_PRESETS.copy()
            all_presets.update(custom_presets)
            for pname, pbands in all_presets.items():
                if current_bands == pbands:
                    self.preset_choice.SetStringSelection(pname)
                    self.settings["preset_name"] = pname
                    matched = True
                    break
            if not matched:
                self.preset_choice.SetSelection(0)

    def on_enable_toggle(self, event):
        is_enabled = self.enable_check.IsChecked()
        self.settings["enabled"] = is_enabled
        for ctrl in [self.preset_choice, self.preamp_slider, self.save_preset_btn, self.delete_preset_btn, self.reset_btn] + self.band_sliders:
            ctrl.Enable(is_enabled)
        if self.main_frame:
            self.main_frame.audio_player_panel.apply_equalizer_settings(self.settings)

    def on_preset_select(self, event):
        selection_str = self.preset_choice.GetStringSelection()
        
        all_presets = constants.EQUALIZER_PRESETS.copy()
        all_presets.update(self.settings.get("custom_presets", {}))

        if selection_str in all_presets:
            bands = all_presets[selection_str]
            self.settings["bands"] = bands
            self.settings["preset_name"] = selection_str
            for i, slider in enumerate(self.band_sliders):
                slider.SetValue(int(bands[i] * 10))
            self.apply_and_speak_changes()
        elif selection_str == _("<Custom>"):
            self.settings["preset_name"] = _("<Custom>")
            self.delete_preset_btn.Disable()
        
        can_delete = selection_str in self.settings.get("custom_presets", {})
        self.delete_preset_btn.Enable(can_delete and self.enable_check.IsChecked())

    def on_preamp_change(self, event):
        val = self.preamp_slider.GetValue()
        self.settings["preamp"] = val
        self.settings["preset_name"] = _("<Custom>")
        self.apply_and_speak_changes(speak_text=_("Pre-amp {} percent").format(val))
        self.preset_choice.SetSelection(0)
        
    def on_band_change(self, event):
        bands = [s.GetValue() / 10.0 for s in self.band_sliders]
        self.settings["bands"] = bands
        self.settings["preset_name"] = _("<Custom>")
        self.apply_and_speak_changes()
        self.preset_choice.SetSelection(0)

    def on_save_preset(self, event):
        with wx.TextEntryDialog(self, _("Enter a name for the new preset:"), _("Save Preset")) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                name = dlg.GetValue().strip()
                if not name:
                    utils.show_error_dialog(self, _("Preset name cannot be empty."))
                    return
                if name == _("<Custom>") or name in constants.EQUALIZER_PRESETS:
                    utils.show_error_dialog(self, _("Cannot overwrite a built-in preset name."))
                    return
                
                if "custom_presets" not in self.settings:
                    self.settings["custom_presets"] = {}
                self.settings["custom_presets"][name] = self.settings["bands"]
                self.settings["preset_name"] = name
                self.populate_presets(selected_name=name)
                self.preset_choice.SetStringSelection(name)
                nvda.speak(_("Preset '{}' saved.").format(name), constants.NVDA_VERBOSITY_DEFAULT)

    def on_delete_preset(self, event):
        selection_str = self.preset_choice.GetStringSelection()
        custom_presets = self.settings.get("custom_presets", {})
        if selection_str in custom_presets:
            with wx.MessageDialog(self, _("Are you sure you want to delete the preset '{}'?").format(selection_str), _("Confirm Delete"), wx.YES_NO | wx.ICON_WARNING) as dlg:
                utils.play_sound(self.main_frame.settings, "confirm_prompt")
                if dlg.ShowModal() == wx.ID_YES:
                    del custom_presets[selection_str]
                    self.populate_presets()
                    nvda.speak(_("Preset '{}' deleted.").format(selection_str), constants.NVDA_VERBOSITY_DEFAULT)

    def on_reset(self, event):
        flat_bands = constants.EQUALIZER_PRESETS["Flat"]
        self.settings["bands"] = flat_bands
        self.settings["preset_name"] = "Flat"
        for i, slider in enumerate(self.band_sliders):
            slider.SetValue(int(flat_bands[i] * 10))
        self.preset_choice.SetStringSelection("Flat")
        self.apply_and_speak_changes(speak_text=_("Equalizer reset to flat."))

    def apply_and_speak_changes(self, speak_text=None):
        if self.main_frame:
            self.main_frame.audio_player_panel.apply_equalizer_settings(self.settings)
        if speak_text:
            nvda.speak(speak_text, constants.NVDA_VERBOSITY_VERBOSE)

    def on_ok(self, event):
        self.EndModal(wx.ID_OK)

    def get_new_settings(self):
        return self.settings


class SpatialAudioDialog(wx.Dialog):
    """Dialog for configuring wide spatial audio soundstage, room size, and 3D depth."""

    def __init__(self, parent, spatial_settings):
        super().__init__(parent, title=_("Spatial Audio"), size=(540, 420), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main_frame = parent
        self.settings = copy.deepcopy(spatial_settings)
        self._original_settings = copy.deepcopy(spatial_settings)

        self.panel = wx.Panel(self)
        self.InitUI()
        self.load_settings()
        self.CentreOnParent()

        app = wx.GetApp()
        if app and hasattr(app.GetTopWindow(), 'settings'):
            utils.play_sound(app.GetTopWindow().settings, "popup_open")

    def InitUI(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.enable_check = wx.CheckBox(self.panel, label=_("Enable Spatial Audio"))
        self.enable_check.SetName(_("Enable Spatial Audio"))
        top_sizer.Add(self.enable_check, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)

        preset_lbl = wx.StaticText(self.panel, label=_("Preset:"))
        top_sizer.Add(preset_lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.preset_choice = wx.Choice(self.panel)
        self.preset_choice.SetName(_("Spatial Audio Preset"))
        top_sizer.Add(self.preset_choice, 1, wx.ALIGN_CENTER_VERTICAL)
        main_sizer.Add(top_sizer, 0, wx.EXPAND | wx.ALL, 12)

        sliders_box = wx.StaticBox(self.panel, label=_("Soundstage Controls"))
        sliders_sizer = wx.StaticBoxSizer(sliders_box, wx.VERTICAL)

        self.width_label = wx.StaticText(self.panel, label="")
        self.width_slider = wx.Slider(
            self.panel,
            value=constants.DEFAULT_SPATIAL_WIDTH,
            minValue=constants.SPATIAL_WIDTH_MIN,
            maxValue=constants.SPATIAL_WIDTH_MAX,
            style=wx.SL_HORIZONTAL,
        )
        self.width_slider.SetName(_("Soundstage Width"))
        sliders_sizer.Add(self.width_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        sliders_sizer.Add(self.width_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.room_label = wx.StaticText(self.panel, label="")
        self.room_slider = wx.Slider(
            self.panel,
            value=constants.DEFAULT_SPATIAL_ROOM,
            minValue=constants.SPATIAL_ROOM_MIN,
            maxValue=constants.SPATIAL_ROOM_MAX,
            style=wx.SL_HORIZONTAL,
        )
        self.room_slider.SetName(_("Room Size"))
        sliders_sizer.Add(self.room_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        sliders_sizer.Add(self.room_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.depth_label = wx.StaticText(self.panel, label="")
        self.depth_slider = wx.Slider(
            self.panel,
            value=constants.DEFAULT_SPATIAL_DEPTH,
            minValue=constants.SPATIAL_DEPTH_MIN,
            maxValue=constants.SPATIAL_DEPTH_MAX,
            style=wx.SL_HORIZONTAL,
        )
        self.depth_slider.SetName(_("3D Depth"))
        sliders_sizer.Add(self.depth_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        sliders_sizer.Add(self.depth_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        main_sizer.Add(sliders_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.reset_btn = wx.Button(self.panel, label=_("Reset to Default"))
        self.reset_btn.SetName(_("Reset to Default"))
        btn_row.Add(self.reset_btn, 0)
        btn_row.AddStretchSpacer(1)

        std_btns = wx.StdDialogButtonSizer()
        self.ok_button = wx.Button(self.panel, wx.ID_OK, label=_("OK"))
        self.ok_button.SetName(_("OK"))
        self.cancel_button = wx.Button(self.panel, wx.ID_CANCEL, label=_("Cancel"))
        self.cancel_button.SetName(_("Cancel"))
        std_btns.AddButton(self.ok_button)
        std_btns.AddButton(self.cancel_button)
        std_btns.Realize()
        btn_row.Add(std_btns, 0)
        main_sizer.Add(btn_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.panel.SetSizer(main_sizer)

        self.enable_check.Bind(wx.EVT_CHECKBOX, self.on_enable_toggle)
        self.preset_choice.Bind(wx.EVT_CHOICE, self.on_preset_select)
        self.width_slider.Bind(wx.EVT_SLIDER, self.on_slider_change)
        self.room_slider.Bind(wx.EVT_SLIDER, self.on_slider_change)
        self.depth_slider.Bind(wx.EVT_SLIDER, self.on_slider_change)
        self.reset_btn.Bind(wx.EVT_BUTTON, self.on_reset)
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self.on_cancel, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_CLOSE, self.on_cancel)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)

    def load_settings(self):
        self.enable_check.SetValue(bool(self.settings.get("enabled", False)))
        self.width_slider.SetValue(int(self.settings.get("width", constants.DEFAULT_SPATIAL_WIDTH)))
        self.room_slider.SetValue(int(self.settings.get("room_size", constants.DEFAULT_SPATIAL_ROOM)))
        self.depth_slider.SetValue(int(self.settings.get("depth", constants.DEFAULT_SPATIAL_DEPTH)))
        self._populate_presets()
        self._update_value_labels()
        self._update_control_states()

    def _populate_presets(self):
        self.preset_choice.Clear()
        self.preset_choice.Append(_("<Custom>"))
        self.preset_choice.AppendItems(sorted(constants.SPATIAL_AUDIO_PRESETS.keys()))
        preset = self.settings.get("preset", constants.DEFAULT_SPATIAL_PRESET)
        if preset and self.preset_choice.FindString(preset) != wx.NOT_FOUND:
            self.preset_choice.SetStringSelection(preset)
        else:
            self.preset_choice.SetSelection(0)

    def _update_value_labels(self):
        self.width_label.SetLabel(_("Soundstage Width: {}%").format(self.width_slider.GetValue()))
        self.room_label.SetLabel(_("Room Size: {}%").format(self.room_slider.GetValue()))
        self.depth_label.SetLabel(_("3D Depth: {}%").format(self.depth_slider.GetValue()))

    def _update_control_states(self):
        enabled = self.enable_check.IsChecked()
        for ctrl in (self.preset_choice, self.width_slider, self.room_slider, self.depth_slider, self.reset_btn):
            ctrl.Enable(enabled)

    def _apply_preview(self):
        if self.main_frame and hasattr(self.main_frame, 'audio_player_panel') and hasattr(self.main_frame.audio_player_panel, 'apply_spatial_audio_settings'):
            self.main_frame.audio_player_panel.apply_spatial_audio_settings(self.settings)

    def on_enable_toggle(self, event):
        self.settings["enabled"] = self.enable_check.IsChecked()
        self._update_control_states()
        self._apply_preview()

    def on_preset_select(self, event):
        sel = self.preset_choice.GetStringSelection()
        if sel in constants.SPATIAL_AUDIO_PRESETS:
            vals = constants.SPATIAL_AUDIO_PRESETS[sel]
            self.settings["preset"] = sel
            self.settings["width"] = vals["width"]
            self.settings["room_size"] = vals["room_size"]
            self.settings["depth"] = vals["depth"]
            self.width_slider.SetValue(vals["width"])
            self.room_slider.SetValue(vals["room_size"])
            self.depth_slider.SetValue(vals["depth"])
            self._update_value_labels()
            self._apply_preview()
            nvda.speak(_("Spatial preset: {}").format(sel), constants.NVDA_VERBOSITY_DEFAULT)

    def on_slider_change(self, event):
        self.settings["width"] = self.width_slider.GetValue()
        self.settings["room_size"] = self.room_slider.GetValue()
        self.settings["depth"] = self.depth_slider.GetValue()
        self.settings["preset"] = _("<Custom>")
        self.preset_choice.SetSelection(0)
        self._update_value_labels()
        self._apply_preview()

    def on_reset(self, event):
        preset = constants.DEFAULT_SPATIAL_PRESET
        vals = constants.SPATIAL_AUDIO_PRESETS[preset]
        self.settings["preset"] = preset
        self.settings["width"] = vals["width"]
        self.settings["room_size"] = vals["room_size"]
        self.settings["depth"] = vals["depth"]
        self.width_slider.SetValue(vals["width"])
        self.room_slider.SetValue(vals["room_size"])
        self.depth_slider.SetValue(vals["depth"])
        self.preset_choice.SetStringSelection(preset)
        self._update_value_labels()
        self._apply_preview()
        nvda.speak(_("Spatial Audio reset to {}.").format(preset), constants.NVDA_VERBOSITY_DEFAULT)

    def on_char_hook(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.on_cancel(None)
        else:
            event.Skip()

    def on_ok(self, event):
        if self.IsModal():
            self.EndModal(wx.ID_OK)
        else:
            self.Hide()

    def on_cancel(self, event):
        self.settings = copy.deepcopy(self._original_settings)
        self._apply_preview()
        if self.IsModal():
            self.EndModal(wx.ID_CANCEL)
        else:
            self.Hide()

    def get_new_settings(self):
        return self.settings


class BookmarksDialog(wx.Dialog):
    """
    A dialog for managing playback bookmarks for a video.
    """
    def __init__(self, parent, main_frame, video_url):
        super().__init__(parent, title=_("Playback Bookmarks"), size=(500, 400), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.main_frame = main_frame
        self.audio_player = main_frame.audio_player_panel
        self.video_url = video_url
        
        self.panel = wx.Panel(self)
        self.InitUI()
        self.populate_bookmarks()
        self.CentreOnParent()

        # Play popup open sound
        app = wx.GetApp()
        if app and hasattr(app.GetTopWindow(), 'settings'):
            utils.play_sound(app.GetTopWindow().settings, "popup_open")

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.bookmark_list = wx.ListBox(self.panel, style=wx.LB_SINGLE | wx.LB_HSCROLL | wx.WANTS_CHARS)
        self.bookmark_list.SetName(_("Bookmarks List"))
        vbox.Add(self.bookmark_list, 1, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.goto_btn = wx.Button(self.panel, label=_("Go To"))
        self.goto_btn.SetName(_("Go To"))
        self.add_btn = wx.Button(self.panel, label=_("Add New..."))
        self.add_btn.SetName(_("Add New Bookmark"))
        self.edit_btn = wx.Button(self.panel, label=_("Edit..."))
        self.edit_btn.SetName(_("Edit Bookmark"))
        self.delete_btn = wx.Button(self.panel, label=_("Delete"))
        self.delete_btn.SetName(_("Delete Bookmark"))
        
        btn_sizer.Add(self.goto_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(self.add_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(self.edit_btn, 0, wx.RIGHT, 5)
        btn_sizer.Add(self.delete_btn, 0)
        vbox.Add(btn_sizer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        close_btn = wx.Button(self.panel, wx.ID_CLOSE)
        close_btn.SetName(_("Close"))
        vbox.Add(close_btn, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        self.panel.SetSizer(vbox)

        self.bookmark_list.Bind(wx.EVT_LISTBOX, self.on_selection_change)
        self.bookmark_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_goto)
        self.bookmark_list.Bind(wx.EVT_KEY_DOWN, self.on_list_key_down)
        self.goto_btn.Bind(wx.EVT_BUTTON, self.on_goto)
        self.add_btn.Bind(wx.EVT_BUTTON, self.on_add)
        self.edit_btn.Bind(wx.EVT_BUTTON, self.on_edit)
        self.delete_btn.Bind(wx.EVT_BUTTON, self.on_delete)
        close_btn.Bind(wx.EVT_BUTTON, self.on_close)
        self.Bind(wx.EVT_CLOSE, self.on_close)

    def on_list_key_down(self, event):
        keyCode = event.GetKeyCode()
        if keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_goto(event)
        elif keyCode == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CLOSE)
        elif keyCode == wx.WXK_TAB:
            flags = wx.NavigationKeyEvent.IsBackward if event.ShiftDown() else wx.NavigationKeyEvent.IsForward
            event.GetEventObject().Navigate(flags)
        else:
            event.Skip()

    def on_close(self, event):
        self.EndModal(wx.ID_CLOSE)

    def populate_bookmarks(self):
        self.bookmark_list.Clear()
        bookmarks = self.main_frame.settings.get("playback_bookmarks", {}).get(self.video_url, [])
        
        if not bookmarks:
            self.bookmark_list.Append(_("No bookmarks for this track."))
            self.bookmark_list.Disable()
        else:
            bookmarks.sort(key=lambda b: b.get('time', 0))
            for bm in bookmarks:
                time_str = utils.format_time_ms(bm.get('time', 0))
                desc = bm.get('desc', _('No description'))
                self.bookmark_list.Append(f"{time_str} - {desc}", clientData=bm)
            self.bookmark_list.Enable()
        
        self.on_selection_change(None)

    def on_selection_change(self, event):
        is_selected = self.bookmark_list.GetSelection() != wx.NOT_FOUND and self.bookmark_list.IsEnabled()
        self.goto_btn.Enable(is_selected)
        self.edit_btn.Enable(is_selected)
        self.delete_btn.Enable(is_selected)
        
        # Play popup navigate sound
        if event: # Avoid playing during initial populate
            app = wx.GetApp()
            if app and hasattr(app.GetTopWindow(), 'settings'):
                utils.play_sound(app.GetTopWindow().settings, "popup_navigate")

    def on_goto(self, event):
        sel = self.bookmark_list.GetSelection()
        if sel == wx.NOT_FOUND: return
        
        bm_data = self.bookmark_list.GetClientData(sel)
        if bm_data and 'time' in bm_data:
            self.audio_player.seek_to(bm_data['time'])
            self.EndModal(wx.ID_OK)

    def on_add(self, event):
        current_time = self.audio_player.get_current_time()
        time_str = utils.format_time_ms(current_time)
        
        with wx.TextEntryDialog(self, _("Enter a description for the bookmark at {}:").format(time_str), _("Add Bookmark")) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                desc = dlg.GetValue().strip()
                if not desc:
                    utils.show_error_dialog(self, _("Description cannot be empty."))
                    return
                
                self.audio_player.add_bookmark(desc, current_time)
                self.populate_bookmarks()

    def on_edit(self, event):
        sel = self.bookmark_list.GetSelection()
        if sel == wx.NOT_FOUND: return
        
        bm_data = self.bookmark_list.GetClientData(sel)
        if not bm_data: return

        with wx.TextEntryDialog(self, _("Edit bookmark description:"), _("Edit Bookmark"), value=bm_data.get('desc', '')) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                new_desc = dlg.GetValue().strip()
                if not new_desc:
                    utils.show_error_dialog(self, _("Description cannot be empty."))
                    return
                
                bm_data['desc'] = new_desc
                self.main_frame.save_settings()
                self.populate_bookmarks()
                nvda.speak(_("Bookmark updated."), constants.NVDA_VERBOSITY_DEFAULT)

    def on_delete(self, event):
        sel = self.bookmark_list.GetSelection()
        if sel == wx.NOT_FOUND: return
        
        bm_data = self.bookmark_list.GetClientData(sel)
        if not bm_data: return

        bookmarks = self.main_frame.settings.get("playback_bookmarks", {}).get(self.video_url, [])
        
        bookmarks[:] = [b for b in bookmarks if b is not bm_data]

        self.main_frame.save_settings()
        self.populate_bookmarks()
        nvda.speak(_("Bookmark deleted."), constants.NVDA_VERBOSITY_DEFAULT)


class PlaylistCountDialog(wx.Dialog):
    """
    A dialog for asking how many items to download from a playlist or channel.
    """
    def __init__(self, parent, playlist_type, playlist_title, total_videos):
        super().__init__(parent, title=_("Add Multiple Items"), style=wx.DEFAULT_DIALOG_STYLE)
        self.playlist_type = playlist_type
        self.playlist_title = playlist_title
        self.total_videos = total_videos
        self.selected_count = 0
        
        self.choices = [1, 10, 30, 50, 100]
        self.filtered_choices = [c for c in self.choices if c < self.total_videos]
        self.filtered_choices.append(self.total_videos)
        self.filtered_choices = sorted(list(set(self.filtered_choices)))

        self.panel = wx.Panel(self)
        self.InitUI()
        self.retranslate_ui()
        self.CentreOnParent()

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.info_label = wx.StaticText(self.panel, label="")
        vbox.Add(self.info_label, 0, wx.ALL, 10)

        choice_labels = [str(c) for c in self.filtered_choices]
        choice_labels.append(_("Enter manually..."))
        self.radio_box = wx.RadioBox(self.panel, label=_("How many videos to add?"), choices=choice_labels, majorDimension=1, style=wx.RA_SPECIFY_COLS)
        self.radio_box.SetSelection(len(self.filtered_choices) -1)
        vbox.Add(self.radio_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        manual_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.manual_spin = wx.SpinCtrl(self.panel, min=1, max=self.total_videos, initial=self.total_videos)
        self.manual_spin.Disable()
        manual_sizer.Add(wx.StaticText(self.panel, label=""), 1, wx.EXPAND)
        manual_sizer.Add(self.manual_spin, 0, wx.ALIGN_CENTER_VERTICAL)
        vbox.Add(manual_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btn_sizer = wx.StdDialogButtonSizer()
        self.ok_button = wx.Button(self.panel, wx.ID_OK)
        self.cancel_button = wx.Button(self.panel, wx.ID_CANCEL)
        btn_sizer.AddButton(self.ok_button)
        btn_sizer.AddButton(self.cancel_button)
        btn_sizer.Realize()
        vbox.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        self.panel.SetSizer(vbox)
        self.Fit()

        self.radio_box.Bind(wx.EVT_RADIOBOX, self.on_radio_change)
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)

    def retranslate_ui(self):
        self.SetTitle(_("Add Multiple Items"))
        info_text = _("This is a {type} ('{title}') with {count} videos.").format(
            type=self.playlist_type, title=self.playlist_title, count=self.total_videos
        )
        self.info_label.SetLabel(info_text)
        self.radio_box.SetLabel(_("How many videos to add?"))
        self.radio_box.SetName(_("How many videos to add?"))
        self.manual_spin.SetName(_("Manual video count"))
        
        choice_labels = [str(c) for c in self.filtered_choices]
        choice_labels.append(_("Enter manually..."))
        for i, label in enumerate(choice_labels):
            self.radio_box.SetString(i, label)
        
        self.ok_button.SetLabel(_("OK"))
        self.ok_button.SetName(_("OK"))
        self.cancel_button.SetLabel(_("Cancel"))
        self.cancel_button.SetName(_("Cancel"))
        self.panel.Layout()

    def on_radio_change(self, event):
        is_manual = self.radio_box.GetSelection() == self.radio_box.GetCount() - 1
        self.manual_spin.Enable(is_manual)
        if is_manual:
            self.manual_spin.SetFocus()

    def on_ok(self, event):
        selection = self.radio_box.GetSelection()
        
        if selection == self.radio_box.GetCount() - 1:
            self.selected_count = self.manual_spin.GetValue()
        else:
            self.selected_count = self.filtered_choices[selection]
            
        self.EndModal(wx.ID_OK)

    def get_selection_count(self):
        return self.selected_count


class MultiLinkEntryDialog(wx.Dialog):
    """
    An accessible, full-featured dialog for batch URL and playlist link entry.
    Supports clipboard paste, importing URLs directly from .txt files, and live link counting.
    """
    def __init__(self, parent, title, message):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        message_label = wx.StaticText(panel, label=message)
        main_sizer.Add(message_label, 0, wx.EXPAND | wx.ALL, 10)

        self.text_ctrl = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.HSCROLL | wx.VSCROLL)
        self.text_ctrl.SetName(message)
        main_sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Batch actions row
        action_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.paste_button = wx.Button(panel, label=_("Paste from Clipboard"))
        self.paste_button.SetName(_("Paste from Clipboard"))
        self.paste_button.SetToolTip(_("Paste text from the system clipboard into the link entry area."))
        action_sizer.Add(self.paste_button, 0, wx.RIGHT, 5)

        self.import_file_button = wx.Button(panel, label=_("Import from File (.txt)..."))
        self.import_file_button.SetName(_("Import from File (.txt)..."))
        self.import_file_button.SetToolTip(_("Import URLs from an external text file."))
        action_sizer.Add(self.import_file_button, 0, wx.RIGHT, 5)

        self.clear_button = wx.Button(panel, label=_("Clear"))
        self.clear_button.SetName(_("Clear Links"))
        self.clear_button.SetToolTip(_("Clear all entered links."))
        action_sizer.Add(self.clear_button, 0, wx.RIGHT, 10)

        self.count_label = wx.StaticText(panel, label=_("0 link(s) detected"))
        action_sizer.Add(self.count_label, 1, wx.ALIGN_CENTER_VERTICAL)

        main_sizer.Add(action_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btn_sizer = wx.StdDialogButtonSizer()
        ok_button = wx.Button(panel, wx.ID_OK)
        ok_button.SetName(_("OK"))
        ok_button.SetDefault()
        cancel_button = wx.Button(panel, wx.ID_CANCEL)
        cancel_button.SetName(_("Cancel"))
        btn_sizer.AddButton(ok_button)
        btn_sizer.AddButton(cancel_button)
        btn_sizer.Realize()
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(main_sizer)
        
        self.SetInitialSize((560, 320))
        self.CentreOnParent()
        
        # Bind batch action events
        self.text_ctrl.Bind(wx.EVT_TEXT, self.on_text_change)
        self.paste_button.Bind(wx.EVT_BUTTON, self.on_paste)
        self.import_file_button.Bind(wx.EVT_BUTTON, self.on_import_file)
        self.clear_button.Bind(wx.EVT_BUTTON, self.on_clear)

        # Play popup open sound
        app = wx.GetApp()
        if app and hasattr(app.GetTopWindow(), 'settings'):
            utils.play_sound(app.GetTopWindow().settings, "popup_open")
        
        self.text_ctrl.MoveAfterInTabOrder(message_label)
        self.paste_button.MoveAfterInTabOrder(self.text_ctrl)
        self.import_file_button.MoveAfterInTabOrder(self.paste_button)
        self.clear_button.MoveAfterInTabOrder(self.import_file_button)
        ok_button.MoveAfterInTabOrder(self.clear_button)

    def on_text_change(self, event=None):
        text = self.text_ctrl.GetValue()
        urls = [l.strip() for l in text.splitlines() if l.strip()]
        self.count_label.SetLabel(_("{count} link(s) detected").format(count=len(urls)))

    def on_paste(self, event=None):
        if wx.TheClipboard.Open():
            if wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_TEXT)):
                data = wx.TextDataObject()
                wx.TheClipboard.GetData(data)
                clip_text = data.GetText()
                if clip_text:
                    curr = self.text_ctrl.GetValue()
                    new_val = (curr + "\n" + clip_text).strip() if curr.strip() else clip_text.strip()
                    self.text_ctrl.SetValue(new_val)
                    self.on_text_change()
            wx.TheClipboard.Close()

    def on_import_file(self, event=None):
        with wx.FileDialog(self, _("Import URLs from Text File"), wildcard="Text Files (*.txt)|*.txt|All Files (*.*)|*.*", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                file_path = dlg.GetPath()
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        file_text = f.read()
                    curr = self.text_ctrl.GetValue()
                    new_val = (curr + "\n" + file_text).strip() if curr.strip() else file_text.strip()
                    self.text_ctrl.SetValue(new_val)
                    self.on_text_change()
                    nvda.speak(_("Imported URLs from file."), constants.NVDA_VERBOSITY_DEFAULT)
                except Exception as e:
                    utils.show_error_dialog(self, _("Could not read file: {}").format(e))

    def on_clear(self, event=None):
        self.text_ctrl.Clear()
        self.on_text_change()

    def get_value(self):
        return self.text_ctrl.GetValue()

# --- New in 1.5.8 ---

class CommandPaletteDialog(wx.Dialog):
    """
    A searchable command palette for quick access to application functions.
    """
    def __init__(self, parent, commands):
        super().__init__(parent, title=_("Command Palette"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.all_commands = commands
        self.filtered_commands = []
        self.selected_command_id = None

        self.panel = wx.Panel(self)
        self.search_ctrl = wx.SearchCtrl(self.panel, style=wx.TE_PROCESS_ENTER)
        self.search_ctrl.SetName(_("Search Commands"))
        self.results_list = wx.ListBox(self.panel, style=wx.LB_SINGLE | wx.LB_HSCROLL | wx.WANTS_CHARS)
        self.results_list.SetName(_("Commands List"))
        
        self.InitUI()
        self.populate_list()
        self.CentreOnParent()
        self.SetInitialSize((500, 350))
        wx.CallAfter(self.search_ctrl.SetFocus)

        # Play popup open sound
        app = wx.GetApp()
        if app and hasattr(app.GetTopWindow(), 'settings'):
            utils.play_sound(app.GetTopWindow().settings, "popup_open")

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(self.search_ctrl, 0, wx.EXPAND | wx.ALL, 10)
        vbox.Add(self.results_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.panel.SetSizer(vbox)

        self.search_ctrl.Bind(wx.EVT_TEXT, self.on_search)
        self.search_ctrl.Bind(wx.EVT_TEXT_ENTER, self.on_execute)
        self.search_ctrl.Bind(wx.EVT_KEY_DOWN, self.on_search_key)
        self.results_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_execute)
        self.results_list.Bind(wx.EVT_KEY_DOWN, self.on_list_key)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)

    def on_search_key(self, event):
        if event.GetKeyCode() == wx.WXK_DOWN and self.results_list.GetCount() > 0:
            if self.results_list.GetSelection() == wx.NOT_FOUND:
                self.results_list.SetSelection(0)
            self.results_list.SetFocus()
        else:
            event.Skip()

    def on_char_hook(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()

    def populate_list(self, query=""):
        self.results_list.Clear()
        self.filtered_commands.clear()
        
        query = query.lower().strip()
        for cmd in self.all_commands:
            if query in cmd['label'].lower():
                self.results_list.Append(cmd['label'])
                self.filtered_commands.append(cmd)
        
        if self.results_list.GetCount() > 0:
            self.results_list.SetSelection(0)
            
        # Play popup navigate sound
        if query: # Only when filtering
            app = wx.GetApp()
            if app and hasattr(app.GetTopWindow(), 'settings'):
                utils.play_sound(app.GetTopWindow().settings, "popup_navigate")

    def on_search(self, event):
        self.populate_list(self.search_ctrl.GetValue())

    def on_list_key(self, event):
        keyCode = event.GetKeyCode()
        if keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_execute(event)
        elif keyCode == wx.WXK_TAB:
            flags = wx.NavigationKeyEvent.IsBackward if event.ShiftDown() else wx.NavigationKeyEvent.IsForward
            event.GetEventObject().Navigate(flags)
        else:
            event.Skip()

    def on_execute(self, event):
        selection = self.results_list.GetSelection()
        if selection != wx.NOT_FOUND and selection < len(self.filtered_commands):
            self.selected_command_id = self.filtered_commands[selection]['id']
            self.EndModal(wx.ID_OK)
        else:
            nvda.speak(_("No matching commands."))

    def get_selected_command_id(self):
        return self.selected_command_id


class WhatsNewDialog(wx.Dialog):
    """
    A dialog to show the "What's New" information from the changelog.
    """
    def __init__(self, parent, changelog_content):
        super().__init__(parent, title=_("What's New in Tunevia"), size=(600, 450), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        title_font = self.GetFont().Bold()
        title_font.SetPointSize(self.GetFont().GetPointSize() + 2)
        
        title_label = wx.StaticText(panel, label=_("Welcome to Tunevia Version {}!").format(constants.APP_VERSION))
        title_label.SetFont(title_font)
        vbox.Add(title_label, 0, wx.ALL | wx.ALIGN_CENTER, 15)

        text_ctrl = wx.TextCtrl(panel, value=changelog_content, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        text_ctrl.SetName(_("What's New Changelog"))
        vbox.Add(text_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        close_button = wx.Button(panel, wx.ID_OK, _("OK"))
        close_button.SetDefault()
        vbox.Add(close_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(vbox)
        wx.CallAfter(text_ctrl.SetFocus)
        self.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_OK), id=wx.ID_OK)
        self.Bind(wx.EVT_CLOSE, lambda e: self.EndModal(wx.ID_CANCEL))
        def on_key(e):
            if e.GetKeyCode() == wx.WXK_ESCAPE:
                self.EndModal(wx.ID_CANCEL)
            else:
                e.Skip()
        self.Bind(wx.EVT_CHAR_HOOK, on_key)
        self.CentreOnParent()


class SleepTimerDialog(wx.Dialog):
    """Accessible dialog for choosing a playback sleep timer duration."""

    def __init__(self, parent, current_minutes=0):
        super().__init__(parent, title=_("Sleep Timer"), size=(400, 300), style=wx.DEFAULT_DIALOG_STYLE)
        self.selected_minutes = current_minutes
        self._preset_values = list(constants.SLEEP_TIMER_PRESETS)

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        prompt = wx.StaticText(panel, label=_("Pause playback automatically after:"))
        vbox.Add(prompt, 0, wx.ALL, 12)

        labels = []
        for mins in self._preset_values:
            if mins == 0:
                labels.append(_("Off"))
            elif mins == -1:
                labels.append(_("End of current track"))
            else:
                labels.append(_("{} minutes").format(mins))

        self.choice_list = wx.ListBox(panel, choices=labels, style=wx.LB_SINGLE | wx.WANTS_CHARS)
        self.choice_list.SetName(_("Sleep Timer Duration"))
        if current_minutes in self._preset_values:
            self.choice_list.SetSelection(self._preset_values.index(current_minutes))
        else:
            self.choice_list.SetSelection(0)
        vbox.Add(self.choice_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        btns = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, label=_("OK"))
        ok_btn.SetName(_("OK"))
        ok_btn.SetDefault()
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label=_("Cancel"))
        cancel_btn.SetName(_("Cancel"))
        btns.AddButton(ok_btn)
        btns.AddButton(cancel_btn)
        btns.Realize()
        vbox.Add(btns, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        panel.SetSizer(vbox)
        self.CentreOnParent()
        wx.CallAfter(self.choice_list.SetFocus)

        self.choice_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_confirm)
        self.choice_list.Bind(wx.EVT_KEY_DOWN, self.on_list_key)
        self.Bind(wx.EVT_BUTTON, self.on_confirm, id=wx.ID_OK)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)

    def on_list_key(self, event):
        code = event.GetKeyCode()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_confirm(None)
        elif code == wx.WXK_TAB:
            flags = wx.NavigationKeyEvent.IsBackward if event.ShiftDown() else wx.NavigationKeyEvent.IsForward
            event.GetEventObject().Navigate(flags)
        else:
            event.Skip()

    def on_char_hook(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()

    def on_confirm(self, event):
        idx = self.choice_list.GetSelection()
        if 0 <= idx < len(self._preset_values):
            self.selected_minutes = self._preset_values[idx]
        self.EndModal(wx.ID_OK)

    def get_selected_minutes(self):
        return self.selected_minutes


class UpNextQueueDialog(wx.Dialog):
    """Accessible Up-Next queue manager for reordering or playing queued tracks."""

    def __init__(self, parent, audio_player):
        super().__init__(parent, title=_("Up-Next Queue"), size=(560, 420), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.audio_player = audio_player

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.status_label = wx.StaticText(panel, label="")
        vbox.Add(self.status_label, 0, wx.ALL, 10)

        self.queue_list = wx.ListBox(panel, style=wx.LB_SINGLE | wx.WANTS_CHARS)
        self.queue_list.SetName(_("Up-Next Queue List"))
        vbox.Add(self.queue_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.play_btn = wx.Button(panel, label=_("Play Selected"))
        self.play_btn.SetName(_("Play Selected"))
        self.up_btn = wx.Button(panel, label=_("Move Up"))
        self.up_btn.SetName(_("Move Up"))
        self.down_btn = wx.Button(panel, label=_("Move Down"))
        self.down_btn.SetName(_("Move Down"))
        self.remove_btn = wx.Button(panel, label=_("Remove"))
        self.remove_btn.SetName(_("Remove"))
        self.clear_btn = wx.Button(panel, label=_("Clear Queue"))
        self.clear_btn.SetName(_("Clear Queue"))
        self.close_btn = wx.Button(panel, wx.ID_CLOSE, label=_("Close"))
        self.close_btn.SetName(_("Close"))

        for b in (self.play_btn, self.up_btn, self.down_btn, self.remove_btn, self.clear_btn):
            btn_row.Add(b, 0, wx.RIGHT, 5)
        btn_row.AddStretchSpacer(1)
        btn_row.Add(self.close_btn, 0)
        vbox.Add(btn_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        panel.SetSizer(vbox)
        self.CentreOnParent()
        self.refresh_queue()
        wx.CallAfter(self.queue_list.SetFocus)

        self.queue_list.Bind(wx.EVT_LISTBOX_DCLICK, self.on_play_selected)
        self.queue_list.Bind(wx.EVT_KEY_DOWN, self.on_list_key)
        self.play_btn.Bind(wx.EVT_BUTTON, self.on_play_selected)
        self.up_btn.Bind(wx.EVT_BUTTON, lambda e: self._move_item(-1))
        self.down_btn.Bind(wx.EVT_BUTTON, lambda e: self._move_item(1))
        self.remove_btn.Bind(wx.EVT_BUTTON, self.on_remove)
        self.clear_btn.Bind(wx.EVT_BUTTON, self.on_clear)
        self.close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        self.Bind(wx.EVT_CLOSE, lambda e: self.EndModal(wx.ID_CLOSE))
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)

    def refresh_queue(self, select_idx=None):
        queue = getattr(self.audio_player, "up_next_queue", [])
        self.queue_list.Clear()
        if not queue:
            self.queue_list.Append(_("Up-Next queue is empty."))
            self.queue_list.Disable()
            self.status_label.SetLabel(_("No queued tracks."))
            for b in (self.play_btn, self.up_btn, self.down_btn, self.remove_btn, self.clear_btn):
                b.Disable()
            return
        self.queue_list.Enable()
        self.status_label.SetLabel(_("{} track(s) in queue:").format(len(queue)))
        for idx, item in enumerate(queue, 1):
            title = item.get("title") or _("Untitled")
            uploader = item.get("uploader") or _("Unknown")
            self.queue_list.Append(f"{idx}. {title} - {uploader}")
        target = 0 if select_idx is None else max(0, min(len(queue) - 1, select_idx))
        self.queue_list.SetSelection(target)
        for b in (self.play_btn, self.up_btn, self.down_btn, self.remove_btn, self.clear_btn):
            b.Enable()

    def _move_item(self, delta):
        queue = getattr(self.audio_player, "up_next_queue", [])
        idx = self.queue_list.GetSelection()
        if idx == wx.NOT_FOUND or not queue:
            return
        new_idx = idx + delta
        if 0 <= new_idx < len(queue):
            queue[idx], queue[new_idx] = queue[new_idx], queue[idx]
            self.refresh_queue(select_idx=new_idx)
            nvda.speak(_("Moved item to position {}").format(new_idx + 1))

    def on_play_selected(self, event):
        queue = getattr(self.audio_player, "up_next_queue", [])
        idx = self.queue_list.GetSelection()
        if 0 <= idx < len(queue):
            item = queue.pop(idx)
            self.EndModal(wx.ID_OK)
            self.audio_player.play_queue_entry(item)

    def on_remove(self, event):
        queue = getattr(self.audio_player, "up_next_queue", [])
        idx = self.queue_list.GetSelection()
        if 0 <= idx < len(queue):
            removed = queue.pop(idx)
            self.refresh_queue(select_idx=idx)
            nvda.speak(_("Removed {} from queue.").format(removed.get("title") or _("track")))

    def on_clear(self, event):
        self.audio_player.up_next_queue.clear()
        self.refresh_queue()
        nvda.speak(_("Queue cleared."))

    def on_list_key(self, event):
        code = event.GetKeyCode()
        if code in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_play_selected(None)
        elif code == wx.WXK_DELETE:
            self.on_remove(None)
        elif code == wx.WXK_TAB:
            flags = wx.NavigationKeyEvent.IsBackward if event.ShiftDown() else wx.NavigationKeyEvent.IsForward
            event.GetEventObject().Navigate(flags)
        else:
            event.Skip()

    def on_char_hook(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CLOSE)
        else:
            event.Skip()


class UpdateDownloadDialog(wx.Dialog):
    """Accessible update download progress dialog with zero backend exposure."""

    def __init__(self, parent, version_label):
        super().__init__(parent, title=_("Updating Tunevia"), size=(430, 190), style=wx.DEFAULT_DIALOG_STYLE)
        self.cancel_event = None
        self._last_spoken_milestone = -1

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.status_label = wx.StaticText(panel, label=_("Downloading Tunevia {version}...").format(version=version_label))
        vbox.Add(self.status_label, 0, wx.ALL | wx.EXPAND, 12)

        self.gauge = wx.Gauge(panel, range=100, style=wx.GA_HORIZONTAL)
        self.gauge.SetName(_("Update download progress"))
        vbox.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.pct_label = wx.StaticText(panel, label=_("Getting updates..."))
        vbox.Add(self.pct_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)

        self.cancel_btn = wx.Button(panel, wx.ID_CANCEL, label=_("Cancel"))
        self.cancel_btn.SetName(_("Cancel"))
        vbox.Add(self.cancel_btn, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 12)

        panel.SetSizer(vbox)
        self.CentreOnParent()
        self.cancel_btn.Bind(wx.EVT_BUTTON, self.on_cancel)
        self.Bind(wx.EVT_CLOSE, self.on_cancel)

    def update_progress(self, percent):
        if not self:
            return
        pct = max(0, min(100, int(percent)))
        self.gauge.SetValue(pct)
        self.pct_label.SetLabel(_("{}% complete").format(pct))
        milestone = (pct // 25) * 25
        if milestone in (25, 50, 75, 100) and milestone > self._last_spoken_milestone:
            self._last_spoken_milestone = milestone
            nvda.speak(_("Downloading update, {} percent").format(milestone), constants.NVDA_VERBOSITY_DEFAULT)

    def on_cancel(self, event):
        if self.cancel_event is not None:
            self.cancel_event.set()
        self.cancel_btn.Disable()
        self.pct_label.SetLabel(_("Cancelling..."))
