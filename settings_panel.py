# --- settings_panel.py ---

import wx
import os

# Local application imports
import nvda
import constants
import utils
import feature_manager
from translation_manager import _
from ui_components import SoundSettingsDialog, LanguageSelectionDialog, KeyboardShortcutsDialog, EqualizerDialog, SpatialAudioDialog

class SettingsPanel(wx.Panel):
    """
    A wx.Panel with a modern Category Sidebar and Simplebook pages
    for cleanly organized application configuration.
    """
    def __init__(self, parent, main_frame):
        super().__init__(parent)
        self.main_frame = main_frame

        # Data for the seek interval choice
        self.seek_interval_options = [
            (_("3 Seconds"), 3),
            (_("5 Seconds"), 5),
            (_("10 Seconds"), 10),
            (_("15 Seconds"), 15),
            (_("30 Seconds"), 30),
            (_("1 Minute"), 60),
            (_("5 Minutes"), 300),
            (_("10 Minutes"), 600),
            (_("15 Minutes"), 900),
            (_("30 Minutes"), 1800),
            (_("1 Hour"), 3600),
        ]
        
        # Data for verbosity choice
        self.verbosity_options = [
            (constants.NVDA_VERBOSITY_OFF, _("Off")),
            (constants.NVDA_VERBOSITY_QUIET, _("Quiet")),
            (constants.NVDA_VERBOSITY_DEFAULT, _("Default")),
            (constants.NVDA_VERBOSITY_VERBOSE, _("Verbose")),
        ]

        # References to UI elements
        self.sidebar_list = None
        self.content_book = None
        self.search_group = None
        self.playback_group = None
        self.appearance_group = None
        self.general_group = None
        self.accessibility_group = None
        self.custom_group = None
        self.theme_label = None
        self.seek_interval_label = None
        self.seek_interval_choice = None
        self.tab_management_group = None
        self.tabs_list_box = None
        self.tab_move_up_button = None
        self.tab_move_down_button = None
        self.tab_reset_button = None

        self.InitUI()
        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        self.load_settings_to_ui()

    def InitUI(self):
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 1. Left Sidebar
        self.sidebar_list = wx.ListBox(self, choices=[], style=wx.LB_SINGLE | wx.WANTS_CHARS)
        self.sidebar_list.SetName(_("Settings Categories"))
        self.sidebar_list.SetMinSize((190, -1))
        self.sidebar_list.Bind(wx.EVT_LISTBOX, self.on_sidebar_select)
        self.sidebar_list.Bind(wx.EVT_KEY_DOWN, self.on_sidebar_key_down)
        main_sizer.Add(self.sidebar_list, 0, wx.EXPAND | wx.ALL, 5)

        # 2. Right Content Simplebook
        self.content_book = wx.Simplebook(self)
        main_sizer.Add(self.content_book, 1, wx.EXPAND | wx.ALL, 5)

        # Page 0: Feature Manager
        page_fm = wx.ScrolledWindow(self.content_book)
        page_fm.SetScrollRate(0, 20)
        page_fm_sizer = wx.BoxSizer(wx.VERTICAL)

        self.feature_manager_group = wx.StaticBox(page_fm, label="")
        fm_box_sizer = wx.StaticBoxSizer(self.feature_manager_group, wx.VERTICAL)

        self.fm_desc = wx.StaticText(page_fm, label="")
        self.fm_desc.Wrap(650)
        fm_box_sizer.Add(self.fm_desc, 0, wx.ALL | wx.EXPAND, 5)

        # Preset toolbar
        preset_bar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.preset_lbl = wx.StaticText(page_fm, label="")
        preset_bar_sizer.Add(self.preset_lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        self.btn_preset_mp = wx.Button(page_fm, label="")
        self.btn_preset_mp.Bind(wx.EVT_BUTTON, lambda e: self.on_apply_preset(feature_manager.PRESET_MUSIC_PLAYER))
        preset_bar_sizer.Add(self.btn_preset_mp, 0, wx.RIGHT, 5)

        self.btn_preset_disc = wx.Button(page_fm, label="")
        self.btn_preset_disc.Bind(wx.EVT_BUTTON, lambda e: self.on_apply_preset(feature_manager.PRESET_MUSIC_DISCOVERY))
        preset_bar_sizer.Add(self.btn_preset_disc, 0, wx.RIGHT, 5)

        self.btn_preset_power = wx.Button(page_fm, label="")
        self.btn_preset_power.Bind(wx.EVT_BUTTON, lambda e: self.on_apply_preset(feature_manager.PRESET_POWER_USER))
        preset_bar_sizer.Add(self.btn_preset_power, 0, wx.RIGHT, 5)

        self.btn_preset_rec = wx.Button(page_fm, label="")
        self.btn_preset_rec.Bind(wx.EVT_BUTTON, lambda e: self.on_apply_preset(feature_manager.PRESET_RECOMMENDED))
        preset_bar_sizer.Add(self.btn_preset_rec, 0)

        fm_box_sizer.Add(preset_bar_sizer, 0, wx.ALL | wx.EXPAND, 5)

        # Categories & Checkboxes
        self.fm_checkboxes = {}
        self.fm_cat_boxes = {}
        for category in feature_manager.CATEGORIES:
            cat_box = wx.StaticBox(page_fm, label="")
            self.fm_cat_boxes[category] = cat_box
            cat_sizer = wx.StaticBoxSizer(cat_box, wx.VERTICAL)

            features = feature_manager.get_features_by_category(category)
            for spec in features:
                fid = spec["id"]
                cb = wx.CheckBox(page_fm, label="")
                cb.Bind(wx.EVT_CHECKBOX, lambda evt, f_id=fid: self.on_feature_manager_toggle(evt, f_id))
                self.fm_checkboxes[fid] = cb
                cat_sizer.Add(cb, 0, wx.ALL | wx.EXPAND, 3)

            fm_box_sizer.Add(cat_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.fm_restart_note = wx.StaticText(page_fm, label="")
        self.fm_restart_note.Wrap(650)
        fm_box_sizer.Add(self.fm_restart_note, 0, wx.ALL | wx.EXPAND, 5)

        page_fm_sizer.Add(fm_box_sizer, 0, wx.EXPAND | wx.ALL, 10)
        page_fm.SetSizer(page_fm_sizer)
        self.content_book.AddPage(page_fm, "")

        # Page 1: Search Settings
        page_search = wx.ScrolledWindow(self.content_book)
        page_search.SetScrollRate(0, 20)
        page_search_sizer = wx.BoxSizer(wx.VERTICAL)

        self.search_group = wx.StaticBox(page_search, label="")
        search_sizer = wx.StaticBoxSizer(self.search_group, wx.VERTICAL)

        search_modes = ["", ""]
        self.search_mode_radio = wx.RadioBox(page_search, label="", choices=search_modes, majorDimension=1, style=wx.RA_SPECIFY_COLS)
        search_sizer.Add(self.search_mode_radio, 0, wx.EXPAND | wx.ALL, 5)

        comment_limit_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.comment_limit_label = wx.StaticText(page_search, label="")
        comment_limit_sizer.Add(self.comment_limit_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.comment_limit_choice = wx.ComboBox(page_search, choices=constants.COMMENT_FETCH_LIMIT_OPTIONS, style=wx.CB_DROPDOWN)
        comment_limit_sizer.Add(self.comment_limit_choice, 1, wx.EXPAND)
        search_sizer.Add(comment_limit_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.clear_cache_button = wx.Button(page_search, label="")
        search_sizer.Add(self.clear_cache_button, 0, wx.TOP | wx.BOTTOM | wx.ALIGN_CENTER_HORIZONTAL, 5)

        page_search_sizer.Add(search_sizer, 0, wx.EXPAND | wx.ALL, 10)
        page_search.SetSizer(page_search_sizer)
        self.content_book.AddPage(page_search, "")

        # Page 2: Playback Settings
        page_playback = wx.ScrolledWindow(self.content_book)
        page_playback.SetScrollRate(0, 20)
        page_playback_sizer = wx.BoxSizer(wx.VERTICAL)

        self.playback_group = wx.StaticBox(page_playback, label="")
        playback_sizer = wx.StaticBoxSizer(self.playback_group, wx.VERTICAL)
        
        seek_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.seek_interval_label = wx.StaticText(page_playback, label="")
        seek_sizer.Add(self.seek_interval_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.seek_interval_choice = wx.Choice(page_playback, choices=[])
        seek_sizer.Add(self.seek_interval_choice, 1, wx.EXPAND)
        playback_sizer.Add(seek_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.autoplay_check = wx.CheckBox(page_playback, label="")
        playback_sizer.Add(self.autoplay_check, 0, wx.ALL, 5)

        self.remember_position_check = wx.CheckBox(page_playback, label="")
        playback_sizer.Add(self.remember_position_check, 0, wx.ALL, 5)

        self.sponsorblock_check = wx.CheckBox(page_playback, label="")
        playback_sizer.Add(self.sponsorblock_check, 0, wx.ALL, 5)

        page_playback_sizer.Add(playback_sizer, 0, wx.EXPAND | wx.ALL, 10)
        page_playback.SetSizer(page_playback_sizer)
        self.content_book.AddPage(page_playback, "")

        # Page 3: Appearance & Behavior
        page_appearance = wx.ScrolledWindow(self.content_book)
        page_appearance.SetScrollRate(0, 20)
        page_appearance_sizer = wx.BoxSizer(wx.VERTICAL)

        self.appearance_group = wx.StaticBox(page_appearance, label="")
        appearance_sizer = wx.StaticBoxSizer(self.appearance_group, wx.VERTICAL)
        
        theme_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.theme_label = wx.StaticText(page_appearance, label="")
        theme_sizer.Add(self.theme_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.theme_choice = wx.Choice(page_appearance, choices=[])
        theme_sizer.Add(self.theme_choice, 1, wx.EXPAND)
        appearance_sizer.Add(theme_sizer, 0, wx.EXPAND | wx.ALL, 5)

        self.always_on_top_check = wx.CheckBox(page_appearance, label="")
        appearance_sizer.Add(self.always_on_top_check, 0, wx.ALL, 5)

        page_appearance_sizer.Add(appearance_sizer, 0, wx.EXPAND | wx.ALL, 10)
        page_appearance.SetSizer(page_appearance_sizer)
        self.content_book.AddPage(page_appearance, "")

        # Page 4: Accessibility
        page_accessibility = wx.ScrolledWindow(self.content_book)
        page_accessibility.SetScrollRate(0, 20)
        page_accessibility_sizer = wx.BoxSizer(wx.VERTICAL)

        self.general_group = wx.StaticBox(page_accessibility, label="")
        general_sizer = wx.StaticBoxSizer(self.general_group, wx.VERTICAL)
        
        self.accessibility_group = wx.StaticBox(page_accessibility, label="")
        accessibility_sizer = wx.StaticBoxSizer(self.accessibility_group, wx.VERTICAL)
        verbosity_labels = [label for key, label in self.verbosity_options]
        self.nvda_verbosity_radio = wx.RadioBox(page_accessibility, label="", choices=verbosity_labels, majorDimension=1, style=wx.RA_SPECIFY_COLS)
        accessibility_sizer.Add(self.nvda_verbosity_radio, 0, wx.EXPAND | wx.ALL, 5)
        general_sizer.Add(accessibility_sizer, 0, wx.EXPAND | wx.ALL, 5)

        page_accessibility_sizer.Add(general_sizer, 0, wx.EXPAND | wx.ALL, 10)
        page_accessibility.SetSizer(page_accessibility_sizer)
        self.content_book.AddPage(page_accessibility, "")

        # Page 5: Authentication & Cookies
        page_cookies = wx.ScrolledWindow(self.content_book)
        page_cookies.SetScrollRate(0, 20)
        page_cookies_sizer = wx.BoxSizer(wx.VERTICAL)

        self.cookies_group = wx.StaticBox(page_cookies, label="")
        cookies_box_sizer = wx.StaticBoxSizer(self.cookies_group, wx.VERTICAL)
        self.cookies_path_label = wx.StaticText(page_cookies, label="")
        cookies_box_sizer.Add(self.cookies_path_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
        cookies_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.cookies_path_text = wx.TextCtrl(page_cookies, style=wx.TE_READONLY)
        self.cookies_browse_button = wx.Button(page_cookies, label="")
        self.cookies_clear_button = wx.Button(page_cookies, label="")
        cookies_sizer.Add(self.cookies_path_text, 1, wx.EXPAND | wx.RIGHT, 5)
        cookies_sizer.Add(self.cookies_browse_button, 0, wx.RIGHT, 5)
        cookies_sizer.Add(self.cookies_clear_button, 0)
        cookies_box_sizer.Add(cookies_sizer, 1, wx.EXPAND | wx.ALL, 5)

        page_cookies_sizer.Add(cookies_box_sizer, 0, wx.EXPAND | wx.ALL, 10)
        page_cookies.SetSizer(page_cookies_sizer)
        self.content_book.AddPage(page_cookies, "")

        # Page 6: Customization
        page_custom = wx.ScrolledWindow(self.content_book)
        page_custom.SetScrollRate(0, 20)
        page_custom_sizer = wx.BoxSizer(wx.VERTICAL)

        self.custom_group = wx.StaticBox(page_custom, label="")
        custom_sizer = wx.GridBagSizer(5, 5)

        self.equalizer_button = wx.Button(page_custom, label="")
        self.spatial_audio_button = wx.Button(page_custom, label="")
        self.pref_lang_button = wx.Button(page_custom, label="")
        self.change_lang_button = wx.Button(page_custom, label="")
        self.sound_settings_button = wx.Button(page_custom, label="")
        self.shortcuts_button = wx.Button(page_custom, label="")

        custom_sizer.Add(self.equalizer_button, pos=(0, 0), flag=wx.EXPAND)
        custom_sizer.Add(self.spatial_audio_button, pos=(0, 1), flag=wx.EXPAND)
        custom_sizer.Add(self.pref_lang_button, pos=(1, 0), flag=wx.EXPAND)
        custom_sizer.Add(self.change_lang_button, pos=(1, 1), flag=wx.EXPAND)
        custom_sizer.Add(self.sound_settings_button, pos=(2, 0), flag=wx.EXPAND)
        custom_sizer.Add(self.shortcuts_button, pos=(2, 1), flag=wx.EXPAND)
        
        custom_sizer.AddGrowableCol(0)
        custom_sizer.AddGrowableCol(1)

        custom_box_sizer = wx.StaticBoxSizer(self.custom_group, wx.VERTICAL)
        custom_box_sizer.Add(custom_sizer, 1, wx.EXPAND | wx.ALL, 5)

        page_custom_sizer.Add(custom_box_sizer, 0, wx.EXPAND | wx.ALL, 10)
        page_custom.SetSizer(page_custom_sizer)
        self.content_book.AddPage(page_custom, "")

        # Page 7: Tab Management
        page_tabs = wx.ScrolledWindow(self.content_book)
        page_tabs.SetScrollRate(0, 20)
        page_tabs_sizer = wx.BoxSizer(wx.VERTICAL)

        self.tab_management_group = wx.StaticBox(page_tabs, label="")
        tab_management_sizer = wx.StaticBoxSizer(self.tab_management_group, wx.VERTICAL)
        
        tabs_list_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.tabs_list_box = wx.CheckListBox(page_tabs, choices=[])
        tabs_list_sizer.Add(self.tabs_list_box, 1, wx.EXPAND | wx.ALL, 5)
        
        tabs_buttons_sizer = wx.BoxSizer(wx.VERTICAL)
        self.tab_move_up_button = wx.Button(page_tabs, label=_("Move Up"))
        self.tab_move_down_button = wx.Button(page_tabs, label=_("Move Down"))
        self.tab_reset_button = wx.Button(page_tabs, label=_("Reset"))
        tabs_buttons_sizer.Add(self.tab_move_up_button, 0, wx.EXPAND | wx.BOTTOM, 5)
        tabs_buttons_sizer.Add(self.tab_move_down_button, 0, wx.EXPAND | wx.BOTTOM, 5)
        tabs_buttons_sizer.AddStretchSpacer(1)
        tabs_buttons_sizer.Add(self.tab_reset_button, 0, wx.EXPAND)
        tabs_list_sizer.Add(tabs_buttons_sizer, 0, wx.ALL, 5)
        
        tab_management_sizer.Add(tabs_list_sizer, 1, wx.EXPAND | wx.ALL, 5)
        page_tabs_sizer.Add(tab_management_sizer, 1, wx.EXPAND | wx.ALL, 10)
        page_tabs.SetSizer(page_tabs_sizer)
        self.content_book.AddPage(page_tabs, "")

        self.SetSizer(main_sizer)

        # Bind events
        self.search_mode_radio.Bind(wx.EVT_RADIOBOX, self.on_search_mode_change)
        self.comment_limit_choice.Bind(wx.EVT_TEXT, self.on_comment_limit_change)
        self.clear_cache_button.Bind(wx.EVT_BUTTON, self.on_clear_search_cache)
        self.seek_interval_choice.Bind(wx.EVT_CHOICE, self.on_seek_interval_change)
        self.autoplay_check.Bind(wx.EVT_CHECKBOX, self.on_toggle_autoplay)
        self.remember_position_check.Bind(wx.EVT_CHECKBOX, self.on_toggle_remember_position)
        self.sponsorblock_check.Bind(wx.EVT_CHECKBOX, self.on_toggle_sponsorblock)
        self.theme_choice.Bind(wx.EVT_CHOICE, self.on_theme_change)
        self.always_on_top_check.Bind(wx.EVT_CHECKBOX, self.on_toggle_always_on_top)
        self.nvda_verbosity_radio.Bind(wx.EVT_RADIOBOX, self.on_verbosity_change)
        self.cookies_path_text.Bind(wx.EVT_TEXT, self.on_cookies_text_change)
        self.cookies_browse_button.Bind(wx.EVT_BUTTON, self.on_browse_cookies)
        self.cookies_clear_button.Bind(wx.EVT_BUTTON, self.on_clear_cookies)
        self.equalizer_button.Bind(wx.EVT_BUTTON, self.on_open_equalizer)
        self.spatial_audio_button.Bind(wx.EVT_BUTTON, self.on_open_spatial_audio)
        self.pref_lang_button.Bind(wx.EVT_BUTTON, self.on_set_preferred_language)
        self.change_lang_button.Bind(wx.EVT_BUTTON, self.main_frame.on_change_language)
        self.sound_settings_button.Bind(wx.EVT_BUTTON, self.main_frame.on_sound_settings)
        self.shortcuts_button.Bind(wx.EVT_BUTTON, self.main_frame.on_customize_shortcuts)
        self.tab_move_up_button.Bind(wx.EVT_BUTTON, lambda event: self.on_tab_move('up'))
        self.tab_move_down_button.Bind(wx.EVT_BUTTON, lambda event: self.on_tab_move('down'))
        self.tab_reset_button.Bind(wx.EVT_BUTTON, self.on_tab_reset)
        self.tabs_list_box.Bind(wx.EVT_CHECKLISTBOX, self.on_tab_toggled)

        self.retranslate_ui()

    def on_sidebar_select(self, event):
        idx = self.sidebar_list.GetSelection()
        if idx != wx.NOT_FOUND:
            self.content_book.SetSelection(idx)
            # Retain focus in sidebar list so Up/Down arrow navigation does not steal focus
            self.sidebar_list.SetFocus()
            utils.play_sound(self.main_frame.settings, "list_navigate")
            nvda.speak(self.sidebar_list.GetString(idx), constants.NVDA_VERBOSITY_QUIET)

    def get_page_controls(self, page_idx=None):
        """Returns the list of navigable interactive controls for the current or specified page."""
        if page_idx is None:
            if not self.content_book:
                return []
            page_idx = self.content_book.GetSelection()
        if page_idx == 0:
            ctrls = [self.btn_preset_mp, self.btn_preset_disc, self.btn_preset_power, self.btn_preset_rec]
            if hasattr(self, 'fm_checkboxes') and self.fm_checkboxes:
                ctrls.extend(self.fm_checkboxes.values())
            return ctrls
        elif page_idx == 1:
            return [self.search_mode_radio, self.comment_limit_choice, self.clear_cache_button]
        elif page_idx == 2:
            return [self.seek_interval_choice, self.autoplay_check, self.remember_position_check, self.sponsorblock_check]
        elif page_idx == 3:
            return [self.theme_choice, self.always_on_top_check]
        elif page_idx == 4:
            return [self.nvda_verbosity_radio]
        elif page_idx == 5:
            return [self.cookies_path_text, self.cookies_browse_button, self.cookies_clear_button]
        elif page_idx == 6:
            return [self.equalizer_button, self.spatial_audio_button, self.pref_lang_button, self.change_lang_button, self.sound_settings_button, self.shortcuts_button]
        elif page_idx == 7:
            return [self.tabs_list_box, self.tab_move_up_button, self.tab_move_down_button, self.tab_reset_button]
        return []

    def focus_first_page_control(self):
        """Focuses the first available interactive control on the active page."""
        ctrls = [c for c in self.get_page_controls() if c and c.IsShown() and c.IsEnabled() and c.CanAcceptFocusFromKeyboard()]
        if ctrls:
            ctrls[0].SetFocus()
        else:
            current_page = self.content_book.GetCurrentPage()
            if current_page:
                current_page.SetFocus()

    def on_sidebar_key_down(self, event):
        keyCode = event.GetKeyCode()
        if keyCode == wx.WXK_TAB:
            if event.ShiftDown():
                self.sidebar_list.Navigate(wx.NavigationKeyEvent.IsBackward)
            else:
                self.focus_first_page_control()
        elif keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.focus_first_page_control()
        else:
            event.Skip()

    def on_char_hook(self, event):
        keyCode = event.GetKeyCode()
        if keyCode == wx.WXK_TAB:
            focus = wx.Window.FindFocus()
            ctrls = [c for c in self.get_page_controls() if c and c.IsShown() and c.IsEnabled() and c.CanAcceptFocusFromKeyboard()]
            if ctrls:
                first_ctrl = ctrls[0]
                last_ctrl = ctrls[-1]
                if event.ShiftDown():
                    if focus == first_ctrl or (hasattr(first_ctrl, 'HasChild') and first_ctrl.HasChild(focus)):
                        self.sidebar_list.SetFocus()
                        return
                else:
                    if focus == last_ctrl or (hasattr(last_ctrl, 'HasChild') and last_ctrl.HasChild(focus)):
                        self.sidebar_list.SetFocus()
                        return
        event.Skip()


    def retranslate_ui(self):
        """Updates all translatable text on the panel."""
        categories = [
            _("Feature Manager"),
            _("Search Settings"),
            _("Playback Settings"),
            _("Appearance & Behavior"),
            _("Accessibility"),
            _("Authentication"),
            _("Customization"),
            _("Tab Management"),
        ]
        if self.sidebar_list:
            sel = self.sidebar_list.GetSelection()
            if sel == wx.NOT_FOUND: sel = 0
            self.sidebar_list.SetItems(categories)
            self.sidebar_list.SetSelection(sel)
            if self.content_book:
                self.content_book.SetSelection(sel)

        # Feature Manager labels
        self.feature_manager_group.SetLabel(_("Feature Manager"))
        self.fm_desc.SetLabel(_("Turn off features you do not need to speed up startup and save memory."))
        self.preset_lbl.SetLabel(_("Presets:"))
        self.btn_preset_mp.SetLabel(_("Music Player"))
        self.btn_preset_mp.SetName(_("Apply Music Player preset"))
        self.btn_preset_disc.SetLabel(_("Music + Discovery"))
        self.btn_preset_disc.SetName(_("Apply Music + Discovery preset"))
        self.btn_preset_power.SetLabel(_("Power User"))
        self.btn_preset_power.SetName(_("Apply Power User preset"))
        self.btn_preset_rec.SetLabel(_("Recommended"))
        self.btn_preset_rec.SetName(_("Apply Recommended Settings preset"))
        self.fm_restart_note.SetLabel(_("Note: Changes to tabs or core modules take effect after restarting Tunevia."))

        for category in feature_manager.CATEGORIES:
            cat_name = feature_manager.get_category_name(category)
            if category in self.fm_cat_boxes:
                self.fm_cat_boxes[category].SetLabel(cat_name)

        for fid, cb in self.fm_checkboxes.items():
            name = feature_manager.get_feature_name(fid)
            desc = feature_manager.get_feature_description(fid)
            cb.SetLabel(f"{name} - {desc}")
            cb.SetName(f"{name} - {desc}")
            cb.SetToolTip(desc)

        self.search_group.SetLabel(_("Search Settings"))
        self.playback_group.SetLabel(_("Playback Settings"))
        self.appearance_group.SetLabel(_("Appearance & Behavior"))
        self.general_group.SetLabel(_("General & Accessibility"))
        self.cookies_group.SetLabel(_("Authentication"))
        self.custom_group.SetLabel(_("Customization"))
        self.tab_management_group.SetLabel(_("Tab Management"))
        self.tab_move_up_button.SetLabel(_("Move Up"))
        self.tab_move_up_button.SetName(_("Move Tab Up"))
        self.tab_move_down_button.SetLabel(_("Move Down"))
        self.tab_move_down_button.SetName(_("Move Tab Down"))
        self.tab_reset_button.SetLabel(_("Reset"))
        self.tab_reset_button.SetName(_("Reset Tab Order"))
        self.tabs_list_box.SetName(_("Tabs List"))
        self._populate_tabs_list()

        self.search_mode_radio.SetLabel(_("Search Source"))
        self.search_mode_radio.SetName(_("Search Source"))
        self.search_mode_radio.SetString(0, _("Standard YouTube"))
        self.search_mode_radio.SetString(1, _("YouTube Music"))
        self.search_mode_radio.SetToolTip(_("Switch between standard YouTube and YouTube Music catalogs."))

        self.comment_limit_label.SetLabel(_("Comment Fetch Limit:"))
        self.comment_limit_choice.SetName(_("Comment Fetch Limit"))
        self.comment_limit_choice.SetToolTip(_("Number of comments to fetch per video. 'all' loads every comment, which can take longer."))

        self.clear_cache_button.SetName(_("Clear Search Cache"))

        self.seek_interval_label.SetLabel(_("Seek Interval:"))
        self.seek_interval_choice.SetName(_("Seek Interval"))
        self.seek_interval_choice.SetToolTip(_("How far Rewind and Fast Forward jump in the track."))
        self._populate_seek_intervals()

        self.autoplay_check.SetLabel(_("Autoplay Next Track"))
        self.autoplay_check.SetName(_("Autoplay Next Track"))
        self.autoplay_check.SetToolTip(_("Play the next track automatically when the current one ends. Ignored during Radio Mode."))
        self.remember_position_check.SetLabel(_("Remember Playback Position"))
        self.remember_position_check.SetName(_("Remember Playback Position"))
        self.remember_position_check.SetToolTip(_("Save where you stopped a track and ask to resume next time you play it."))
        self.sponsorblock_check.SetLabel(_("Skip sponsor segments (SponsorBlock)"))
        self.sponsorblock_check.SetName(_("Skip sponsor segments (SponsorBlock)"))
        self.sponsorblock_check.SetToolTip(_("Skip sponsored segments, intros, and promos using SponsorBlock."))

        self.theme_label.SetLabel(_("Theme:"))
        current_theme_sel = self.theme_choice.GetSelection()
        self.theme_choice.SetItems([_("Light"), _("Dark")])
        if current_theme_sel != wx.NOT_FOUND: self.theme_choice.SetSelection(current_theme_sel)
        self.theme_choice.SetName(_("Theme"))
        self.theme_choice.SetToolTip(_("Switch between light and dark themes."))

        self.always_on_top_check.SetLabel(_("Always on Top"))
        self.always_on_top_check.SetName(_("Always on Top"))
        self.always_on_top_check.SetToolTip(_("Keep Tunevia floating on top of other windows."))

        self.accessibility_group.SetLabel(_("Accessibility"))
        self.nvda_verbosity_radio.SetLabel(_("NVDA Verbosity Level"))
        self.nvda_verbosity_radio.SetName(_("NVDA Verbosity Level"))
        for i, (key, label) in enumerate(self.verbosity_options):
            self.nvda_verbosity_radio.SetString(i, label)
        self.nvda_verbosity_radio.SetToolTip(_("How much NVDA announces in Tunevia.\nOff: No speech.\nQuiet: Alerts and errors only.\nDefault: Standard actions and status.\nVerbose: Detailed navigation and list items."))

        self.cookies_path_label.SetLabel(_("Cookies file path:"))
        self.cookies_path_text.SetName(_("Cookies File Path"))
        self.cookies_path_text.SetToolTip(_("Path to your exported cookies.txt file. Required for age-restricted or members-only videos."))
        self.cookies_browse_button.SetLabel(_("Browse..."))
        self.cookies_browse_button.SetName(_("Browse Cookies File"))
        self.cookies_clear_button.SetLabel(_("Clear"))
        self.cookies_clear_button.SetName(_("Clear Cookies File"))

        self.equalizer_button.SetLabel(_("Audio Equalizer..."))
        self.equalizer_button.SetName(_("Audio Equalizer"))
        self.equalizer_button.SetToolTip(_("Adjust frequencies, pre-amplification, and sound presets."))
        self.spatial_audio_button.SetLabel(_("Spatial Audio..."))
        self.spatial_audio_button.SetName(_("Spatial Audio"))
        self.spatial_audio_button.SetToolTip(_("Adjust stereo soundstage width, room size, and 3D depth."))
        self.pref_lang_button.SetLabel(_("Set Preferred Audio Language..."))
        self.pref_lang_button.SetName(_("Set Preferred Audio Language"))
        self.pref_lang_button.SetToolTip(_("Language code (such as en, ja, id) used to auto-select audio tracks on multi-language videos."))
        self.change_lang_button.SetLabel(_("Change Application Language..."))
        self.change_lang_button.SetName(_("Change Application Language"))
        self.change_lang_button.SetToolTip(_("Choose the display language for Tunevia."))
        self.sound_settings_button.SetLabel(_("Sound Settings..."))
        self.sound_settings_button.SetName(_("Sound Settings"))
        self.sound_settings_button.SetToolTip(_("Configure startup sounds, alerts, and navigation audio cues."))
        self.shortcuts_button.SetLabel(_("Keyboard Shortcuts..."))
        self.shortcuts_button.SetName(_("Keyboard Shortcuts"))
        self.shortcuts_button.SetToolTip(_("Customize global and in-app keyboard shortcuts."))

        self._update_clear_cache_button_label()
        self.Layout()

    def _populate_seek_intervals(self):
        """Populates the seek interval choice with translated strings."""
        current_sel = self.seek_interval_choice.GetSelection()
        choices = [label for label, val in self.seek_interval_options]
        self.seek_interval_choice.SetItems(choices)
        if current_sel != wx.NOT_FOUND:
            self.seek_interval_choice.SetSelection(current_sel)

    def load_settings_to_ui(self):
        """Loads current settings from the main frame and applies them to the UI controls."""
        settings = self.main_frame.settings

        search_mode = settings.get("search_mode", "youtube")
        self.search_mode_radio.SetSelection(1 if search_mode == "ytmusic" else 0)

        c_limit = str(settings.get("comment_fetch_limit", constants.DEFAULT_COMMENT_FETCH_LIMIT))
        self.comment_limit_choice.SetValue(c_limit)

        seek_val = settings.get("seek_interval", constants.DEFAULT_SEEK_INTERVAL_SECONDS)
        seek_index = next((i for i, (_, val) in enumerate(self.seek_interval_options) if val == seek_val), -1)
        if seek_index != -1:
            self.seek_interval_choice.SetSelection(seek_index)
        else:
            self.seek_interval_choice.SetSelection(2)

        self.autoplay_check.SetValue(settings.get("autoplay_enabled", False))
        self.remember_position_check.SetValue(settings.get("remember_playback_position", False))
        self.sponsorblock_check.SetValue(settings.get("enable_sponsorblock", True))
        
        theme = settings.get("theme", constants.DEFAULT_THEME)
        self.theme_choice.SetSelection(1 if theme == constants.THEME_DARK else 0)
        self.always_on_top_check.SetValue(settings.get("always_on_top", False))

        verbosity = settings.get("nvda_verbosity", constants.DEFAULT_NVDA_VERBOSITY)
        verbosity_keys = [key for key, label in self.verbosity_options]
        try:
            sel_index = verbosity_keys.index(verbosity)
            self.nvda_verbosity_radio.SetSelection(sel_index)
        except ValueError:
            self.nvda_verbosity_radio.SetSelection(2) # Default

        cookies_path = settings.get("cookies_file_path", "")
        if not cookies_path:
            import settings_manager
            detected = settings_manager.get_effective_cookies_path(settings)
            if detected:
                cookies_path = detected
                settings["cookies_file_path"] = detected
                self.main_frame.save_settings()
        self.cookies_path_text.SetValue(cookies_path)

        # Feature Manager checkboxes
        if hasattr(self, 'fm_checkboxes'):
            for fid, cb in self.fm_checkboxes.items():
                cb.SetValue(feature_manager.is_feature_enabled(settings, fid))

        self._update_clear_cache_button_label()
        self._populate_tabs_list()

    def on_feature_manager_toggle(self, event, feature_id):
        cb = event.GetEventObject()
        is_checked = cb.IsChecked()

        feature_manager.set_feature_enabled(self.main_frame.settings, feature_id, is_checked)
        self.main_frame.save_settings()

        # Update all checkboxes to reflect any dependency changes
        for fid, cbox in self.fm_checkboxes.items():
            cbox.SetValue(feature_manager.is_feature_enabled(self.main_frame.settings, fid))

        spec = feature_manager.FEATURE_REGISTRY.get(feature_id, {})
        feat_name = feature_manager.get_feature_name(feature_id)

        # Sync existing duplicate controls in SettingsPanel
        self.load_settings_to_ui()

        # Apply dynamic features directly if main_frame is available
        self._apply_dynamic_feature_change(feature_id, is_checked)

        if spec.get("requires_restart", False):
            msg = _("{feature} updated. Restart Tunevia to apply this change.").format(feature=feat_name)
            nvda.speak(msg)
        else:
            msg = (_("{feature} enabled.") if is_checked else _("{feature} disabled.")).format(feature=feat_name)
            nvda.speak(msg)

    def ensure_data_loaded(self):
        """Refreshes dynamic UI counters such as search cache size when switching to Settings."""
        self.load_settings_to_ui()

    def on_apply_preset(self, preset_id):
        feature_manager.apply_preset(self.main_frame.settings, preset_id)
        self.main_frame.save_settings()
        self.load_settings_to_ui()
        for fid in feature_manager.FEATURE_REGISTRY:
            self._apply_dynamic_feature_change(fid, feature_manager.is_feature_enabled(self.main_frame.settings, fid))
        pname = feature_manager.get_preset_name(preset_id)
        nvda.speak(_("Applied preset: {preset}. Restart Tunevia to apply tab changes.").format(preset=pname))

    def _apply_dynamic_feature_change(self, feature_id, enabled):
        if not self.main_frame:
            return
        if feature_id == feature_manager.FEATURE_SEARCH_SUGGESTIONS:
            if hasattr(self.main_frame, 'youtube_panel'):
                if not enabled and hasattr(self.main_frame.youtube_panel, 'suggestion_timer'):
                    self.main_frame.youtube_panel.suggestion_timer.Stop()
        elif feature_id == feature_manager.FEATURE_PLAYLISTS:
            if hasattr(self.main_frame, 'youtube_panel') and self.main_frame.youtube_panel:
                self.main_frame.youtube_panel.retranslate_ui()
        elif feature_id == feature_manager.FEATURE_DOWNLOADER:
            if hasattr(self.main_frame, 'youtube_panel') and self.main_frame.youtube_panel:
                self.main_frame.youtube_panel.retranslate_ui()
        elif feature_id == feature_manager.FEATURE_CLIPBOARD_DETECTION:
            if hasattr(self.main_frame, 'clipboard_timer'):
                if enabled:
                    self.main_frame.clipboard_timer.Start(2000)
                else:
                    self.main_frame.clipboard_timer.Stop()
        elif feature_id == feature_manager.FEATURE_SYSTEM_TRAY:
            tb_icon = getattr(self.main_frame, 'taskbar_icon', None)
            if not enabled and tb_icon:
                tb_icon.Destroy()
                self.main_frame.taskbar_icon = None
            elif enabled and not tb_icon and hasattr(self.main_frame, 'setup_taskbar_icon'):
                self.main_frame.setup_taskbar_icon()
        elif feature_id == feature_manager.FEATURE_GLOBAL_HOTKEYS:
            if hasattr(self.main_frame, 'rebuild_accelerators_and_hotkeys'):
                self.main_frame.rebuild_accelerators_and_hotkeys()
        elif feature_id == feature_manager.FEATURE_SOUND_EFFECTS:
            if not enabled:
                utils.clear_sound_cache()
            else:
                utils.preload_sounds_async(self.main_frame.settings)
        elif feature_id in (feature_manager.FEATURE_MONO_AUDIO, feature_manager.FEATURE_SPATIAL_AUDIO, feature_manager.FEATURE_AUDIO_NORMALIZATION, feature_manager.FEATURE_EQUALIZER, feature_manager.FEATURE_BOOKMARKS, feature_manager.FEATURE_VIDEO_PLAYER, feature_manager.FEATURE_FAVORITES):
            if hasattr(self.main_frame, 'audio_player_panel') and self.main_frame.audio_player_panel:
                self.main_frame.audio_player_panel.retranslate_ui()
                if hasattr(self.main_frame.audio_player_panel, '_apply_dsp_backend_transition'):
                    self.main_frame.audio_player_panel._apply_dsp_backend_transition()


    def on_search_mode_change(self, event):
        selection = self.search_mode_radio.GetSelection()
        new_mode = "ytmusic" if selection == 1 else "youtube"
        self.main_frame.settings["search_mode"] = new_mode
        self.main_frame.save_settings()
        nvda.speak(_("Search mode set to {}").format(self.search_mode_radio.GetString(selection)))

    def on_toggle_search_suggestions(self, event):
        is_checked = event.IsChecked()
        self.main_frame.settings["enable_search_suggestions"] = is_checked
        self.main_frame.save_settings()
        nvda.speak(_("Search suggestions enabled.") if is_checked else _("Search suggestions disabled."))

    def on_comment_limit_change(self, event):
        value = self.comment_limit_choice.GetValue().strip()
        if value:
            self.main_frame.settings["comment_fetch_limit"] = value
            self.main_frame.save_settings()
            nvda.speak(_("Comment fetch limit set to {}").format(value))

    def on_seek_interval_change(self, event):
        selection = self.seek_interval_choice.GetSelection()
        if selection != wx.NOT_FOUND:
            label, value = self.seek_interval_options[selection]
            self.main_frame.settings["seek_interval"] = value
            self.main_frame.save_settings()
            nvda.speak(_("Seek interval set to {}").format(label))

    def on_toggle_autoplay(self, event):
        is_checked = event.IsChecked()
        self.main_frame.settings["autoplay_enabled"] = is_checked
        self.main_frame.save_settings()
        nvda.speak(_("Autoplay enabled.") if is_checked else _("Autoplay disabled."))

    def on_toggle_remember_position(self, event):
        is_checked = event.IsChecked()
        self.main_frame.settings["remember_playback_position"] = is_checked
        self.main_frame.save_settings()
        nvda.speak(_("Remember playback position enabled.") if is_checked else _("Remember playback position disabled."))

    def on_toggle_sponsorblock(self, event):
        is_checked = event.IsChecked()
        self.main_frame.settings["enable_sponsorblock"] = is_checked
        self.main_frame.save_settings()
        msg = _("SponsorBlock enabled.") if is_checked else _("SponsorBlock disabled.")
        nvda.speak(msg, constants.NVDA_VERBOSITY_DEFAULT)

    def on_toggle_normalization(self, event):
        is_checked = event.IsChecked()
        self.main_frame.settings["audio_normalization"] = is_checked
        self.main_frame.save_settings()
        self.main_frame.audio_player_panel.apply_normalization(is_checked)
        nvda.speak(_("Audio normalization enabled.") if is_checked else _("Audio normalization disabled."))

    def on_theme_change(self, event):
        selection = self.theme_choice.GetSelection()
        theme = constants.THEME_DARK if selection == 1 else constants.THEME_LIGHT
        self.main_frame.on_set_theme(theme)

    def on_toggle_always_on_top(self, event):
        self.main_frame.on_toggle_always_on_top(event)

    def on_toggle_minimize_to_tray(self, event):
        self.main_frame.on_toggle_minimize_to_tray(event)

    def on_toggle_auto_fetch_lyrics(self, event):
        is_checked = event.IsChecked()
        self.main_frame.settings["auto_fetch_lyrics"] = is_checked
        self.main_frame.save_settings()
        nvda.speak(_("Auto fetch lyrics enabled") if is_checked else _("Auto fetch lyrics disabled"))

    def on_toggle_monitor_clipboard(self, event):
        is_checked = event.IsChecked()
        self.main_frame.settings["monitor_clipboard_for_urls"] = is_checked
        self.main_frame.save_settings()
        nvda.speak(_("Clipboard monitoring enabled") if is_checked else _("Clipboard monitoring disabled"))

    def on_toggle_player_shortcuts(self, event):
        is_checked = event.IsChecked()
        self.main_frame.settings["enable_player_shortcuts"] = is_checked
        self.main_frame.save_settings()
        nvda.speak(_("Player keyboard shortcuts enabled.") if is_checked else _("Player keyboard shortcuts disabled."))

    def on_verbosity_change(self, event):
        selection = self.nvda_verbosity_radio.GetSelection()
        new_verbosity_key = self.verbosity_options[selection][0]
        self.main_frame.settings["nvda_verbosity"] = new_verbosity_key
        self.main_frame.save_settings()
        nvda.refresh_settings_cache(self.main_frame.settings)
        if new_verbosity_key != constants.NVDA_VERBOSITY_OFF:
            nvda.speak(_("NVDA verbosity set to {}").format(self.nvda_verbosity_radio.GetString(selection)), constants.NVDA_VERBOSITY_DEFAULT)

    def on_clear_search_cache(self, event):
        search_cache = self.main_frame.settings.get("search_results_cache", {})
        if not search_cache:
            nvda.speak(_("Search cache is already empty."))
            return

        confirm_msg = _("Are you sure you want to clear the search results cache? This will remove {count} cached searches.").format(count=len(search_cache))
        with wx.MessageDialog(self, confirm_msg, _("Confirm Clear Cache"), wx.YES_NO | wx.ICON_QUESTION | wx.CENTRE) as dlg:
            utils.play_sound(self.main_frame.settings, "confirm_prompt")
            if dlg.ShowModal() == wx.ID_YES:
                self.main_frame.settings["search_results_cache"] = {}
                self.main_frame.save_settings()
                self._update_clear_cache_button_label()
                nvda.speak(_("Search cache cleared."))

    def _update_clear_cache_button_label(self):
        search_cache = self.main_frame.settings.get("search_results_cache", {})
        count = len(search_cache)

        base_text = _("Clear Search Cache")
        if count > 0:
            label = f"{base_text} ({_('{count} items').format(count=count)})"
        else:
            label = base_text

        self.clear_cache_button.SetLabel(label)
        self.clear_cache_button.SetName(label)
        self.clear_cache_button.Enable(count > 0)
        self.clear_cache_button.SetToolTip(_("Delete cached search results to refresh queries and free up disk space."))

    def on_browse_cookies(self, event):
        with wx.FileDialog(
            self, _("Select your cookies.txt file"),
            wildcard=_("Text files (*.txt)|*.txt|All files (*.*)|*.*"),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
        ) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_OK:
                path = fileDialog.GetPath()
                self.cookies_path_text.ChangeValue(path)
                self.main_frame.settings["cookies_file_path"] = path
                self.main_frame.save_settings()
                nvda.speak(_("Cookies file path set and saved."))
    
    def on_clear_cookies(self, event):
        self.cookies_path_text.ChangeValue("")
        self.main_frame.settings["cookies_file_path"] = ""
        self.main_frame.save_settings()
        nvda.speak(_("Cookies file path cleared."))

    def on_cookies_text_change(self, event):
        path = self.cookies_path_text.GetValue().strip()
        if os.path.exists(path) or path == "":
            self.main_frame.settings["cookies_file_path"] = path
            self.main_frame.save_settings()

    def on_set_preferred_language(self, event):
        current_lang = self.main_frame.settings.get("preferred_audio_language", constants.DEFAULT_PREFERRED_LANGUAGE)
        prompt_msg = _("Enter preferred language code (e.g., en, ja, es, id) or leave blank for none:")
        with wx.TextEntryDialog(self, prompt_msg, _("Set Preferred Language"), value=current_lang) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                new_lang = dlg.GetValue().strip().lower()
                self.main_frame.settings["preferred_audio_language"] = new_lang
                self.main_frame.save_settings()
                nvda.speak(_("Preferred audio language set to: {}").format(new_lang if new_lang else _("None")))

    def on_open_equalizer(self, event):
        eq_settings = {
            "enabled": self.main_frame.settings.get("equalizer_enabled", False),
            "preamp": self.main_frame.settings.get("equalizer_preamp", constants.DEFAULT_PREAMP_PERCENT),
            "bands": self.main_frame.settings.get("equalizer_bands", constants.EQUALIZER_PRESETS["Flat"]),
            "custom_presets": self.main_frame.settings.get("equalizer_presets", {}),
            "preset_name": self.main_frame.settings.get("equalizer_preset_name", "Flat")
        }
        
        with EqualizerDialog(self.main_frame, eq_settings) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                new_settings = dlg.get_new_settings()
                self.main_frame.settings["equalizer_enabled"] = new_settings["enabled"]
                self.main_frame.settings["equalizer_preamp"] = new_settings["preamp"]
                self.main_frame.settings["equalizer_bands"] = new_settings["bands"]
                self.main_frame.settings["equalizer_presets"] = new_settings.get("custom_presets", {})
                self.main_frame.settings["equalizer_preset_name"] = new_settings.get("preset_name", "Flat")
                if hasattr(self.main_frame, 'audio_player_panel'):
                    self.main_frame.audio_player_panel.apply_equalizer_settings(new_settings)
                self.main_frame.save_settings()
                nvda.speak(_("Equalizer settings applied."))
            else:
                if hasattr(self.main_frame, 'audio_player_panel'):
                    self.main_frame.audio_player_panel.apply_equalizer_settings({
                        "enabled": self.main_frame.settings.get("equalizer_enabled", False),
                        "preamp": self.main_frame.settings.get("equalizer_preamp", constants.DEFAULT_PREAMP_PERCENT),
                        "bands": self.main_frame.settings.get("equalizer_bands", constants.EQUALIZER_PRESETS["Flat"]),
                    })

    def on_open_spatial_audio(self, event):
        spatial_cfg = {
            "enabled": self.main_frame.settings.get("spatial_audio_enabled", False),
            "preset": self.main_frame.settings.get("spatial_audio_preset", constants.DEFAULT_SPATIAL_PRESET),
            "width": self.main_frame.settings.get("spatial_audio_width", constants.DEFAULT_SPATIAL_WIDTH),
            "room_size": self.main_frame.settings.get("spatial_audio_room_size", constants.DEFAULT_SPATIAL_ROOM),
            "depth": self.main_frame.settings.get("spatial_audio_depth", constants.DEFAULT_SPATIAL_DEPTH),
        }
        with SpatialAudioDialog(self.main_frame, spatial_cfg) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                new_cfg = dlg.get_new_settings()
                if hasattr(self.main_frame, 'audio_player_panel'):
                    self.main_frame.audio_player_panel.apply_spatial_audio_settings(new_cfg)
                self.main_frame.save_settings()
                nvda.speak(_("Spatial Audio settings applied."))
            else:
                if hasattr(self.main_frame, 'audio_player_panel'):
                    self.main_frame.audio_player_panel.apply_spatial_audio_settings(spatial_cfg)

    def _populate_tabs_list(self):
        self.tabs_list_box.Clear()
        
        tab_order = self.main_frame.settings.get("tab_order", constants.DEFAULT_TAB_ORDER)
        visible_tabs = self.main_frame.settings.get("visible_tabs", constants.DEFAULT_TAB_ORDER)

        TAB_TO_FEATURE = {
            "discovery": feature_manager.FEATURE_DISCOVER,
            "radar": feature_manager.FEATURE_RADAR,
            "history": feature_manager.FEATURE_HISTORY,
            "favorites": feature_manager.FEATURE_FAVORITES,
            "lyrics": feature_manager.FEATURE_LYRICS_SEARCH,
            "stats": feature_manager.FEATURE_STATS,
        }

        for tab_key in tab_order:
            if tab_key in constants.TABS_CONFIG:
                # Filter out tabs whose associated feature is disabled
                if tab_key in TAB_TO_FEATURE:
                    feat_id = TAB_TO_FEATURE[tab_key]
                    if not feature_manager.is_feature_enabled(self.main_frame.settings, feat_id):
                        continue

                tab_name = _(constants.TABS_CONFIG[tab_key]["name"])
                self.tabs_list_box.Append(tab_name)
                
                # Store the key in the item's client data
                item_index = self.tabs_list_box.GetCount() - 1
                self.tabs_list_box.SetClientData(item_index, tab_key)
                
                if tab_key in visible_tabs:
                    self.tabs_list_box.Check(item_index)

    def on_tab_toggled(self, event):
        self._save_tab_config()

    def on_tab_move(self, direction):
        sel_index = self.tabs_list_box.GetSelection()
        if sel_index == wx.NOT_FOUND:
            return

        if direction == 'up' and sel_index > 0:
            new_index = sel_index - 1
        elif direction == 'down' and sel_index < self.tabs_list_box.GetCount() - 1:
            new_index = sel_index + 1
        else:
            return

        # Swap items
        label = self.tabs_list_box.GetString(sel_index)
        client_data = self.tabs_list_box.GetClientData(sel_index)
        is_checked = self.tabs_list_box.IsChecked(sel_index)

        self.tabs_list_box.Delete(sel_index)
        self.tabs_list_box.Insert(label, new_index)
        self.tabs_list_box.SetClientData(new_index, client_data)
        self.tabs_list_box.Check(new_index, is_checked)
        self.tabs_list_box.SetSelection(new_index)

        self._save_tab_config()

    def on_tab_reset(self, event):
        self.main_frame.settings["tab_order"] = constants.DEFAULT_TAB_ORDER
        self.main_frame.settings["visible_tabs"] = constants.DEFAULT_TAB_ORDER
        self._populate_tabs_list()
        self._save_tab_config()
        self.main_frame.save_settings()
        nvda.speak(_("Tab order and visibility have been reset to default."))

    def _save_tab_config(self):
        new_order = []
        new_visible = []
        for i in range(self.tabs_list_box.GetCount()):
            key = self.tabs_list_box.GetClientData(i)
            new_order.append(key)
            if key == "settings":
                if not self.tabs_list_box.IsChecked(i):
                    self.tabs_list_box.Check(i, True)
                    nvda.speak(_("Settings tab cannot be hidden."))
                new_visible.append(key)
            elif self.tabs_list_box.IsChecked(i):
                new_visible.append(key)

        # Preserve tabs that are in current tab_order but were hidden due to disabled features
        current_order = self.main_frame.settings.get("tab_order", constants.DEFAULT_TAB_ORDER)
        for old_key in current_order:
            if old_key not in new_order:
                new_order.append(old_key)

        self.main_frame.settings["tab_order"] = new_order
        self.main_frame.settings["visible_tabs"] = new_visible
        self.main_frame.save_settings()
        
        # Trigger a rebuild of the notebook
        self.main_frame.rebuild_notebook()
        nvda.speak(_("Tab settings updated."))