#--- START OF FILE onboarding_dialog.py ---

"""
onboarding_dialog.py

First-Launch Onboarding Wizard for Tunevia.
Provides a friendly, accessible setup process allowing users to
choose between usage presets or customize individual features.
Optimized for NVDA and screen-reader accessibility.
"""

import wx
import nvda
import constants
import utils
import feature_manager
from translation_manager import _


class OnboardingDialog(wx.Dialog):
    """
    Multi-page accessible onboarding dialog shown on first launch of Tunevia.
    """
    def __init__(self, parent, settings):
        super().__init__(
            parent,
            title=_("Welcome to Tunevia | Initial Setup"),
            size=(700, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.settings = settings
        self.current_step = 1 # 1: Welcome, 2: Presets, 3: Custom, 4: Completion
        self.selected_preset = feature_manager.PRESET_RECOMMENDED

        # Working copy of feature states
        self.feature_states = {}
        for fid in feature_manager.FEATURE_REGISTRY:
            self.feature_states[fid] = feature_manager.is_feature_enabled(self.settings, fid)

        # Checkbox widgets reference
        self.feature_checkboxes = {}

        self.InitUI()
        self.CentreOnScreen()
        self.show_page(1)

    def InitUI(self):
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Container for pages
        self.content_panel = wx.Panel(self)
        self.content_sizer = wx.BoxSizer(wx.VERTICAL)
        self.content_panel.SetSizer(self.content_sizer)

        self._create_page_welcome()
        self._create_page_presets()
        self._create_page_custom()
        self._create_page_completion()

        self.main_sizer.Add(self.content_panel, 1, wx.EXPAND | wx.ALL, 15)

        # Bottom navigation bar
        nav_line = wx.StaticLine(self, style=wx.LI_HORIZONTAL)
        self.main_sizer.Add(nav_line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)

        self.nav_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.back_button = wx.Button(self, label=_("&Back"))
        self.back_button.SetName(_("Back"))
        self.back_button.Bind(wx.EVT_BUTTON, self.on_back)
        self.nav_sizer.Add(self.back_button, 0, wx.RIGHT, 10)

        self.continue_button = wx.Button(self, label=_("&Continue"))
        self.continue_button.SetName(_("Continue"))
        self.continue_button.Bind(wx.EVT_BUTTON, self.on_continue)
        self.nav_sizer.Add(self.continue_button, 0, wx.RIGHT, 10)

        self.skip_button = wx.Button(self, label=_("&Use Recommended Settings"))
        self.skip_button.SetName(_("Use Recommended Settings"))
        self.skip_button.Bind(wx.EVT_BUTTON, self.on_use_recommended)
        self.nav_sizer.Add(self.skip_button, 0)

        self.nav_sizer.AddStretchSpacer(1)

        self.main_sizer.Add(self.nav_sizer, 0, wx.EXPAND | wx.ALL, 15)
        self.SetSizer(self.main_sizer)

        self.Bind(wx.EVT_CLOSE, self.on_close)

    # --- Page 1: Welcome ---
    def _create_page_welcome(self):
        self.page_welcome = wx.Panel(self.content_panel)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.welcome_title = wx.StaticText(self.page_welcome, label=_("Welcome to Tunevia!"))
        font = self.welcome_title.GetFont()
        font.SetPointSize(16)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.welcome_title.SetFont(font)
        sizer.Add(self.welcome_title, 0, wx.BOTTOM | wx.ALIGN_LEFT, 15)

        desc_text = _(
            "Pick the features you want to use. You can change these anytime in Settings.\n\n"
            "If you are not sure what to pick, choose 'Use Recommended Settings' below for a fast, balanced setup."
        )
        self.welcome_desc = wx.StaticText(self.page_welcome, label=desc_text)
        self.welcome_desc.Wrap(640)
        sizer.Add(self.welcome_desc, 0, wx.EXPAND | wx.BOTTOM, 15)

        # Sound Effects Prompt Section
        sfx_box = wx.StaticBox(self.page_welcome, label=_("Sound Effects"))
        sfx_box_sizer = wx.StaticBoxSizer(sfx_box, wx.VERTICAL)

        sfx_question = _(
            "Tunevia can play audio cues when moving through lists, opening items, and performing actions."
        )
        self.sfx_desc = wx.StaticText(self.page_welcome, label=sfx_question)
        self.sfx_desc.Wrap(620)
        sfx_box_sizer.Add(self.sfx_desc, 0, wx.ALL | wx.EXPAND, 8)

        self.sfx_checkbox = wx.CheckBox(self.page_welcome, label=_("Enable sound effects"))
        self.sfx_checkbox.SetName(_("Enable sound effects"))
        initial_sfx = self.settings.get("sound_effects_enabled", True)
        self.sfx_checkbox.SetValue(initial_sfx)
        self.feature_states[feature_manager.FEATURE_SOUND_EFFECTS] = initial_sfx

        def on_sfx_toggled(evt):
            is_enabled = self.sfx_checkbox.GetValue()
            self.feature_states[feature_manager.FEATURE_SOUND_EFFECTS] = is_enabled
            if is_enabled:
                nvda.speak(_("Sound effects enabled."))
            else:
                nvda.speak(_("Sound effects disabled."))
        self.sfx_checkbox.Bind(wx.EVT_CHECKBOX, on_sfx_toggled)

        sfx_box_sizer.Add(self.sfx_checkbox, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        sizer.Add(sfx_box_sizer, 0, wx.EXPAND | wx.BOTTOM, 15)

        self.page_welcome.SetSizer(sizer)
        self.content_sizer.Add(self.page_welcome, 1, wx.EXPAND)

    # --- Page 2: Usage Presets ---
    def _create_page_presets(self):
        self.page_presets = wx.Panel(self.content_panel)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.presets_title = wx.StaticText(self.page_presets, label=_("How do you want to use Tunevia?"))
        font = self.presets_title.GetFont()
        font.SetPointSize(14)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.presets_title.SetFont(font)
        sizer.Add(self.presets_title, 0, wx.BOTTOM | wx.ALIGN_LEFT, 15)

        self.presets_desc = wx.StaticText(
            self.page_presets,
            label=_("Choose a preset, or select Custom to toggle individual features.")
        )
        self.presets_desc.Wrap(640)
        sizer.Add(self.presets_desc, 0, wx.EXPAND | wx.BOTTOM, 15)

        # Radio options with descriptions
        self.preset_choices = [
            feature_manager.PRESET_MUSIC_PLAYER,
            feature_manager.PRESET_MUSIC_DISCOVERY,
            feature_manager.PRESET_POWER_USER,
            feature_manager.PRESET_CUSTOM,
        ]

        preset_labels = []
        for pid in self.preset_choices:
            if pid == feature_manager.PRESET_CUSTOM:
                preset_labels.append(f"{_('Custom')}: {_('Pick individual features yourself.')}")
            else:
                name = feature_manager.get_preset_name(pid)
                desc = feature_manager.get_preset_description(pid)
                preset_labels.append(f"{name}: {desc}")

        self.presets_radio = wx.RadioBox(
            self.page_presets,
            label=_("Choose a Preset"),
            choices=preset_labels,
            majorDimension=1,
            style=wx.RA_SPECIFY_COLS
        )
        self.presets_radio.SetName(_("Choose a Preset"))
        self.presets_radio.SetSelection(0)
        self.presets_radio.Bind(wx.EVT_RADIOBOX, self.on_preset_selected)
        sizer.Add(self.presets_radio, 1, wx.EXPAND | wx.BOTTOM, 15)

        self.page_presets.SetSizer(sizer)
        self.content_sizer.Add(self.page_presets, 1, wx.EXPAND)

    # --- Page 3: Custom Feature Selection ---
    def _create_page_custom(self):
        self.page_custom = wx.Panel(self.content_panel)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.custom_title = wx.StaticText(self.page_custom, label=_("Feature Selection"))
        font = self.custom_title.GetFont()
        font.SetPointSize(14)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.custom_title.SetFont(font)
        sizer.Add(self.custom_title, 0, wx.BOTTOM | wx.ALIGN_LEFT, 10)

        self.custom_desc = wx.StaticText(
            self.page_custom,
            label=_("Select the features you want to enable.")
        )
        self.custom_desc.Wrap(640)
        sizer.Add(self.custom_desc, 0, wx.EXPAND | wx.BOTTOM, 10)

        # Scrollable area for categories and checkboxes
        self.scrolled_window = wx.ScrolledWindow(self.page_custom, style=wx.VSCROLL)
        self.scrolled_window.SetScrollRate(0, 20)
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)

        for category in feature_manager.CATEGORIES:
            cat_name = feature_manager.get_category_name(category)
            cat_box = wx.StaticBox(self.scrolled_window, label=cat_name)
            cat_sizer = wx.StaticBoxSizer(cat_box, wx.VERTICAL)

            features = feature_manager.get_features_by_category(category)
            for spec in features:
                fid = spec["id"]
                name = feature_manager.get_feature_name(fid)
                desc = feature_manager.get_feature_description(fid)

                # Label contains full name and description for clear screen reader reading
                cb_label = f"{name} - {desc}"
                cb = wx.CheckBox(self.scrolled_window, label=cb_label)
                cb.SetValue(self.feature_states.get(fid, spec["default"]))
                cb.SetToolTip(desc)

                # Bind toggle event
                cb.Bind(wx.EVT_CHECKBOX, lambda evt, f_id=fid: self.on_feature_checkbox_toggled(evt, f_id))
                self.feature_checkboxes[fid] = cb
                cat_sizer.Add(cb, 0, wx.ALL | wx.EXPAND, 4)

            scroll_sizer.Add(cat_sizer, 0, wx.EXPAND | wx.BOTTOM, 10)

        self.scrolled_window.SetSizer(scroll_sizer)
        sizer.Add(self.scrolled_window, 1, wx.EXPAND | wx.BOTTOM, 10)

        self.page_custom.SetSizer(sizer)
        self.content_sizer.Add(self.page_custom, 1, wx.EXPAND)

    # --- Page 4: Completion ---
    def _create_page_completion(self):
        self.page_completion = wx.Panel(self.content_panel)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.completion_title = wx.StaticText(self.page_completion, label=_("Setup Complete"))
        font = self.completion_title.GetFont()
        font.SetPointSize(16)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.completion_title.SetFont(font)
        sizer.Add(self.completion_title, 0, wx.BOTTOM | wx.ALIGN_LEFT, 15)

        desc_text = _(
            "Tunevia is configured and ready to use.\n\n"
            "You can change any of these options later from Settings, Feature Manager.\n\n"
            "Active features:"
        )
        self.completion_desc = wx.StaticText(self.page_completion, label=desc_text)
        self.completion_desc.Wrap(640)
        sizer.Add(self.completion_desc, 0, wx.EXPAND | wx.BOTTOM, 15)

        self.summary_list = wx.ListBox(self.page_completion, style=wx.LB_SINGLE | wx.LB_HSCROLL)
        self.summary_list.SetName(_("Active features"))
        sizer.Add(self.summary_list, 1, wx.EXPAND | wx.BOTTOM, 15)

        self.page_completion.SetSizer(sizer)
        self.content_sizer.Add(self.page_completion, 1, wx.EXPAND)

    # --- Navigation Logic ---
    def show_page(self, step_number):
        self.current_step = step_number

        self.page_welcome.Hide()
        self.page_presets.Hide()
        self.page_custom.Hide()
        self.page_completion.Hide()

        if step_number == 1:
            self.page_welcome.Show()
            self.back_button.Hide()
            self.continue_button.SetLabel(_("&Continue"))
            self.skip_button.Show()
            self.continue_button.SetFocus()
            nvda.speak(_("Welcome to Tunevia. Select the features you want to use."))

        elif step_number == 2:
            self.page_presets.Show()
            self.back_button.Show()
            self.continue_button.SetLabel(_("&Continue"))
            self.skip_button.Show()
            self.presets_radio.SetFocus()
            nvda.speak(_("Select a setup preset, or choose Custom."))

        elif step_number == 3:
            self.page_custom.Show()
            self.back_button.Show()
            self.continue_button.SetLabel(_("&Continue"))
            self.skip_button.Hide()
            self.scrolled_window.Layout()
            # Focus the first checkbox
            first_fid = list(self.feature_checkboxes.keys())[0]
            self.feature_checkboxes[first_fid].SetFocus()
            nvda.speak(_("Feature selection. Check or uncheck features."))

        elif step_number == 4:
            self.page_completion.Show()
            self.back_button.Show()
            self.continue_button.SetLabel(_("&Start Tunevia"))
            self.skip_button.Hide()
            self.update_summary_list()
            self.continue_button.SetFocus()
            nvda.speak(_("Setup complete. Press Enter to start Tunevia."))

        self.content_panel.Layout()
        self.Layout()

    def update_summary_list(self):
        self.summary_list.Clear()
        for fid, spec in feature_manager.FEATURE_REGISTRY.items():
            if self.feature_states.get(fid):
                cat_name = feature_manager.get_category_name(spec["category"])
                name = feature_manager.get_feature_name(fid)
                self.summary_list.Append(f"[{cat_name}] {name}")

    def on_preset_selected(self, event):
        sel_idx = self.presets_radio.GetSelection()
        self.selected_preset = self.preset_choices[sel_idx]
        preset_name = feature_manager.get_preset_name(self.selected_preset) if self.selected_preset != feature_manager.PRESET_CUSTOM else _("Custom")
        nvda.speak(_("Selected preset: {}").format(preset_name))

    def on_feature_checkbox_toggled(self, event, feature_id):
        cb = event.GetEventObject()
        is_checked = cb.IsChecked()
        self.feature_states[feature_id] = is_checked

        spec = feature_manager.FEATURE_REGISTRY.get(feature_id, {})
        feat_name = feature_manager.get_feature_name(feature_id)

        # Handle dependencies
        if is_checked:
            # Check parents
            for dep_id in spec.get("dependencies", []):
                if not self.feature_states.get(dep_id):
                    self.feature_states[dep_id] = True
                    if dep_id in self.feature_checkboxes:
                        self.feature_checkboxes[dep_id].SetValue(True)
                    parent_name = feature_manager.get_feature_name(dep_id)
                    nvda.speak(_("Enabled {parent} because {child} requires it.").format(parent=parent_name, child=feat_name))
            nvda.speak(_("{feature} enabled.").format(feature=feat_name))
        else:
            # Uncheck children
            for other_id, other_spec in feature_manager.FEATURE_REGISTRY.items():
                if feature_id in other_spec.get("dependencies", []):
                    if self.feature_states.get(other_id):
                        self.feature_states[other_id] = False
                        if other_id in self.feature_checkboxes:
                            self.feature_checkboxes[other_id].SetValue(False)
                        child_name = feature_manager.get_feature_name(other_id)
                        nvda.speak(_("Disabled {child} because it requires {parent}.").format(child=child_name, parent=feat_name))
            nvda.speak(_("{feature} disabled.").format(feature=feat_name))

    def on_continue(self, event):
        if self.current_step == 1:
            self.show_page(2)
        elif self.current_step == 2:
            sel_idx = self.presets_radio.GetSelection()
            self.selected_preset = self.preset_choices[sel_idx]
            if self.selected_preset == feature_manager.PRESET_CUSTOM:
                self.show_page(3)
            else:
                # Apply the selected preset
                preset_config = feature_manager.PRESETS_CONFIG.get(self.selected_preset, {})
                for fid, enabled in preset_config.get("features", {}).items():
                    self.feature_states[fid] = enabled
                    if fid in self.feature_checkboxes:
                        self.feature_checkboxes[fid].SetValue(enabled)
                # Preserve user's explicit sound effect choice from Page 1
                if hasattr(self, 'sfx_checkbox'):
                    sfx_val = self.sfx_checkbox.GetValue()
                    self.feature_states[feature_manager.FEATURE_SOUND_EFFECTS] = sfx_val
                    if feature_manager.FEATURE_SOUND_EFFECTS in self.feature_checkboxes:
                        self.feature_checkboxes[feature_manager.FEATURE_SOUND_EFFECTS].SetValue(sfx_val)
                self.show_page(4)
        elif self.current_step == 3:
            self.show_page(4)
        elif self.current_step == 4:
            self.finish_onboarding()

    def on_back(self, event):
        if self.current_step == 2:
            self.show_page(1)
        elif self.current_step == 3:
            self.show_page(2)
        elif self.current_step == 4:
            if self.selected_preset == feature_manager.PRESET_CUSTOM:
                self.show_page(3)
            else:
                self.show_page(2)

    def on_use_recommended(self, event):
        """Applies recommended default settings immediately and completes onboarding."""
        rec_features = feature_manager.PRESETS_CONFIG[feature_manager.PRESET_RECOMMENDED]["features"]
        for fid, enabled in rec_features.items():
            self.feature_states[fid] = enabled
        if hasattr(self, 'sfx_checkbox'):
            sfx_val = self.sfx_checkbox.GetValue()
            self.feature_states[feature_manager.FEATURE_SOUND_EFFECTS] = sfx_val
            self.settings["sound_effects_enabled"] = sfx_val
        nvda.speak(_("Using recommended settings."))
        self.finish_onboarding()

    def finish_onboarding(self):
        # Save feature states to settings
        if hasattr(self, 'sfx_checkbox'):
            sfx_val = self.sfx_checkbox.GetValue()
            self.feature_states[feature_manager.FEATURE_SOUND_EFFECTS] = sfx_val
            self.settings["sound_effects_enabled"] = sfx_val

        if "enabled_features" not in self.settings:
            self.settings["enabled_features"] = {}
        for fid, state in self.feature_states.items():
            feature_manager.set_feature_enabled(self.settings, fid, state)

        # Mark first launch as completed
        self.settings["first_launch_completed"] = True

        import settings_manager
        settings_manager.save_settings(self.settings)

        nvda.speak(_("Setup complete. Starting Tunevia."))
        if self.IsModal():
            self.EndModal(wx.ID_OK)
        else:
            self.Hide()

    def on_close(self, event):
        # If user closes the window without finishing, apply recommended defaults
        # so Tunevia is left in a safe, fully usable state
        if not self.settings.get("first_launch_completed", False):
            self.on_use_recommended(None)
        if event:
            event.Skip()
