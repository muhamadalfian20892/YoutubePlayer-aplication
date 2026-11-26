import wx
import os
import sys

# local stuff
import path_utils
from translation_manager import _
import constants
import utils
import nvda

class HelpPanel(wx.Panel):
    def __init__(self, parent, main_frame):
        super().__init__(parent)
        self.main_window = main_frame
        
        self.make_the_widgets()
        self.grab_the_text()

    def make_the_widgets(self):
        # basically sets up the ui
        main_box = wx.BoxSizer(wx.VERTICAL)

        self.the_text_box = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.VSCROLL | wx.TE_RICH2)
        main_box.Add(self.the_text_box, 1, wx.EXPAND | wx.ALL, 10)

        self.copypasta_button = wx.Button(self, label="...")
        self.copypasta_button.Bind(wx.EVT_BUTTON, self.do_the_copy_thing)
        main_box.Add(self.copypasta_button, 0, wx.ALIGN_CENTER | wx.BOTTOM, 10)

        self.SetSizer(main_box)
        self.update_labels_and_stuff()

    def update_labels_and_stuff(self):
        self.retranslate_ui()

    def retranslate_ui(self):
        # for when the lang changes
        self.the_text_box.SetName(_("User Guide"))
        self.copypasta_button.SetLabel(_("Copy Guide to Clipboard"))
        self.copypasta_button.SetName(_("Copy Guide to Clipboard"))
        self.copypasta_button.SetToolTip(_("Copies the entire user guide text to the clipboard."))
        self.grab_the_text()
        self.Layout()

    def grab_the_text(self):
        # gotta find the readme file
        lang_code = self.main_window.settings.get("language", constants.DEFAULT_PREFERRED_LANGUAGE)
        
        fname, fext = os.path.splitext(constants.README_FILE_NAME)
        special_readme_name = f"{fname}_{lang_code}{fext}"
        
        # check for the translated version first
        path_to_special_readme = path_utils.get_resource_path(os.path.join("docs", special_readme_name))
        path_to_en_readme = path_utils.get_resource_path(os.path.join("docs", f"{fname}_en{fext}"))
        path_to_normal_readme = path_utils.get_resource_path(os.path.join("docs", constants.README_FILE_NAME))

        # fall back to English readme if the localized one is missing
        if os.path.exists(path_to_special_readme):
            the_file_we_need = path_to_special_readme
        elif os.path.exists(path_to_en_readme):
            the_file_we_need = path_to_en_readme
        else:
            the_file_we_need = path_to_normal_readme
        
        all_the_text = _("Help file not found at: {}").format(the_file_we_need)
        if os.path.exists(the_file_we_need):
            try:
                with open(the_file_we_need, "r", encoding="utf-8") as f:
                    all_the_text = f.read()
            except Exception as e:
                # lol error handling
                all_the_text = _("Error reading help file: {}").format(e)
        
        self.the_text_box.SetValue(all_the_text)

    def do_the_copy_thing(self, event):
        # copy button thing
        some_text = self.the_text_box.GetValue()
        if some_text:
            utils.copy_text_to_clipboard(some_text)
        else:
            nvda.speak(_("Nothing to copy."), constants.NVDA_VERBOSITY_DEFAULT)