import wx
import os
import re
import threading
import importlib.util

# Defer importing lyricsgenius (and bs4/requests) until a lyrics search is started.
lyricsgenius = None
LYRICSGENIUS_ENABLED = importlib.util.find_spec("lyricsgenius") is not None

# Local application imports
import nvda
import constants
import utils
import feature_manager
from ui_components import SearchResultsDialog
from translation_manager import _

class LyricsSearchPanel(wx.Panel):
    """
    A wx.Panel that provides a UI for searching and displaying song lyrics.
    """
    def __init__(self, parent, main_frame):
        super().__init__(parent)
        self.main_frame = main_frame
        self.token = os.environ.get("GENIUS_API_TOKEN", "Sw9rbVa7sj1NEP3FB_X7RijVcp11vJhJfrSY1hL5uscyYbt3JmDpNesFVd52xO9d")
        if self.token == "Sw9rbVa7sj1NEP3FB_X7RijVcp11vJhJfrSY1hL5uscyYbt3JmDpNesFVd52xO9d":
            print("Warning: Using default placeholder Genius API token. Please set GENIUS_API_TOKEN environment variable or replace in code.")

        self.genius = None
        self.lyrics_cache = None
        self.search_in_progress = False
        self.current_artist = ""
        self.current_title = ""

        self.InitUI()

    def get_genius(self):
        """Lazily initializes and returns the Genius API client off the startup path."""
        if self.genius is None:
            self._initialize_genius()
        return self.genius

    def _initialize_genius(self):
        """Initializes the lyricsgenius library instance."""
        global lyricsgenius, LYRICSGENIUS_ENABLED
        if not LYRICSGENIUS_ENABLED:
            self.genius = None
            return
        try:
            if lyricsgenius is None:
                import lyricsgenius as _lg
                lyricsgenius = _lg
            self.genius = lyricsgenius.Genius(
                self.token, skip_non_songs=True, excluded_terms=["(Remix)", "(Live)"],
                remove_section_headers=True, timeout=20, retries=2
            )
        except Exception as e:
            print(f"Error initializing LyricsGenius: {e}")
            self.genius = None

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)
        grid_sizer = wx.GridBagSizer(vgap=5, hgap=5)

        # Song Title
        self.label_judul = wx.StaticText(self, label="")
        grid_sizer.Add(self.label_judul, pos=(0, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        self.tc_judul = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.tc_judul.Bind(wx.EVT_TEXT_ENTER, self.OnSearchLyrics)
        grid_sizer.Add(self.tc_judul, pos=(0, 1), flag=wx.EXPAND)

        # Artist Name
        self.label_artis = wx.StaticText(self, label="")
        grid_sizer.Add(self.label_artis, pos=(1, 0), flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=5)
        self.tc_artis = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.tc_artis.Bind(wx.EVT_TEXT_ENTER, self.OnSearchLyrics)
        grid_sizer.Add(self.tc_artis, pos=(1, 1), flag=wx.EXPAND)

        # "No Artist" Checkbox
        self.cb_no_artist = wx.CheckBox(self, label="")
        self.cb_no_artist.Bind(wx.EVT_CHECKBOX, self.OnNoArtistCheck)
        grid_sizer.Add(self.cb_no_artist, pos=(1, 2), flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=5)

        grid_sizer.AddGrowableCol(1)
        vbox.Add(grid_sizer, flag=wx.EXPAND | wx.ALL, border=10)

        # Search Button
        self.button_cari = wx.Button(self, label="")
        self.button_cari.Bind(wx.EVT_BUTTON, self.OnSearchLyrics)
        vbox.Add(self.button_cari, flag=wx.ALIGN_CENTER | wx.BOTTOM, border=10)

        # Lyrics Display Area
        self.display_area = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.VSCROLL)
        vbox.Add(self.display_area, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        # Bottom Buttons (Copy, Save)
        hbox_bottom_buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.button_copy = wx.Button(self, label="")
        self.button_copy.Bind(wx.EVT_BUTTON, self.OnCopy)
        self.button_copy.Disable()
        hbox_bottom_buttons.Add(self.button_copy, flag=wx.RIGHT, border=10)

        self.button_save = wx.Button(self, label="")
        self.button_save.Bind(wx.EVT_BUTTON, self.OnSaveLyrics)
        self.button_save.Disable()
        hbox_bottom_buttons.Add(self.button_save)
        vbox.Add(hbox_bottom_buttons, flag=wx.ALIGN_CENTER | wx.BOTTOM, border=10)

        self.SetSizer(vbox)
        self.retranslate_ui() # Call after UI elements are created

        if LYRICSGENIUS_ENABLED or self.genius:
            self.tc_artis.MoveAfterInTabOrder(self.tc_judul)
            self.cb_no_artist.MoveAfterInTabOrder(self.tc_artis)
            self.button_cari.MoveAfterInTabOrder(self.cb_no_artist)
            self.display_area.MoveAfterInTabOrder(self.button_cari)
            self.button_copy.MoveAfterInTabOrder(self.display_area)
            self.button_save.MoveAfterInTabOrder(self.button_copy)
        else:
            self.button_cari.Disable()
            self.tc_judul.Disable()
            self.tc_artis.Disable()
            self.cb_no_artist.Disable()

    def retranslate_ui(self):
        """Updates all translatable text on the panel."""
        self.label_judul.SetLabel(_("Song Title:"))
        self.tc_judul.SetName(_("Song Title"))
        self.tc_judul.SetToolTip(_("Enter the title of the song. (Ctrl+T to focus)."))
        self.label_artis.SetLabel(_("Artist Name:"))
        self.tc_artis.SetName(_("Artist Name"))
        self.tc_artis.SetToolTip(_("Enter the artist of the song."))
        self.cb_no_artist.SetLabel(_("I don't know artist name"))
        self.cb_no_artist.SetName(_("I don't know artist name"))
        self.cb_no_artist.SetToolTip(_("Check this if you don't know the artist's name."))
        self.button_cari.SetLabel(_("Search Lyrics"))
        self.button_cari.SetName(_("Search Lyrics"))
        self.button_cari.SetToolTip(_("Search for lyrics on Genius.com."))
        self.display_area.SetName(_("Lyrics Display"))
        self.display_area.SetToolTip(_("Displays the found lyrics."))
        self.button_copy.SetLabel(_("Copy Lyrics"))
        self.button_copy.SetName(_("Copy Lyrics"))
        self.button_copy.SetToolTip(_("Copy the displayed lyrics to the clipboard."))
        self.button_save.SetLabel(_("Save Lyrics"))
        self.button_save.SetName(_("Save Lyrics"))
        self.button_save.SetToolTip(_("Save the displayed lyrics to a text file."))
        has_save = feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_SAVE_LYRICS)
        self.button_save.Show(has_save)

        # Retranslate the initial/status message if no actual lyrics are loaded
        current_text = self.display_area.GetValue()
        if not self.lyrics_cache or "..." in current_text:
            if not self.lyrics_cache:
                self.display_lyrics_message()
            elif self.search_in_progress:
                self.display_area.SetValue(_("Searching lyrics..."))

        self.Layout()

    def OnNoArtistCheck(self, event):
        is_checked = self.cb_no_artist.IsChecked()
        self.tc_artis.Enable(not is_checked)
        if is_checked:
            self.tc_artis.SetValue("")
        event.Skip()

    def display_lyrics_message(self, message=None):
        if message is None:
            message = _("No lyrics loaded. Please search for a song.")
        self.display_area.SetValue(message)
        self.button_copy.Disable()
        self.button_save.Disable()
        self.lyrics_cache = None
        self.current_artist = ""
        self.current_title = ""

    def OnCopy(self, event):
        if self.lyrics_cache:
            utils.copy_text_to_clipboard(self.lyrics_cache)
        else:
            nvda.speak(_("Nothing to copy."))

    def OnSaveLyrics(self, event):
        if not self.lyrics_cache:
            utils.show_error_dialog(self, _("No lyrics to save."), _("Save Error"))
            nvda.speak(_("No lyrics to save."))
            return

        artist = self.current_artist or self.tc_artis.GetValue().strip() or _("Unknown Artist")
        title = self.current_title or self.tc_judul.GetValue().strip() or _("Unknown Title")
        default_filename = utils.sanitize_filename(f"{artist} - {title}.txt")

        default_dir = self.main_frame.settings.get("download_dir", os.path.expanduser("~"))
        if not os.path.isdir(default_dir):
            default_dir = os.path.expanduser("~")

        with wx.FileDialog(
            self, message=_("Save Lyrics As"), defaultDir=default_dir,
            defaultFile=default_filename, wildcard=_("Text files (*.txt)|*.txt|All files (*.*)|*.*"),
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as dlg:
            dlg.CentreOnParent()
            if dlg.ShowModal() == wx.ID_OK:
                save_path = dlg.GetPath()
                try:
                    with open(save_path, "w", encoding="utf-8") as f:
                        f.write(self.lyrics_cache)
                    utils.show_message_dialog(self, _("Lyrics saved successfully!"), _("Save Successful"))
                    nvda.speak(_("Lyrics saved successfully!"))
                except Exception as e:
                    error_msg = _("Error saving lyrics: {}").format(e)
                    utils.show_error_dialog(self, error_msg, _("Save Error"))
                    nvda.speak(_("Error saving lyrics."))
                    print(error_msg)

    def OnSearchLyrics(self, event):
        if not LYRICSGENIUS_ENABLED and not self.genius:
            utils.show_error_dialog(self, _("Lyrics component not initialized."), _("Error"))
            return
        if self.search_in_progress:
            utils.show_message_dialog(self, _("A search is already in progress. Please wait."), _("Busy"), wx.OK | wx.ICON_WARNING)
            return

        judul = self.tc_judul.GetValue().strip()
        artis = self.tc_artis.GetValue().strip()
        no_artist = self.cb_no_artist.IsChecked()

        if not judul:
            utils.show_error_dialog(self, _("Please enter a song title."))
            self.tc_judul.SetFocus()
            return
        if not no_artist and not artis:
            utils.show_error_dialog(self, _("Please enter artist name or check 'I don't know artist name'."))
            self.tc_artis.SetFocus()
            return

        self.clear_results()
        self.display_area.SetValue(_("Searching lyrics..."))
        self.button_cari.Disable()
        self.search_in_progress = True
        nvda.speak(_("Searching lyrics..."))
        wx.BeginBusyCursor()
        threading.Thread(target=self.perform_search, args=(artis, judul, no_artist, False), daemon=True).start()

    def search_lyrics_auto(self, title, artist):
        if (not LYRICSGENIUS_ENABLED and not self.genius) or not title or not artist:
            print("Auto-fetch: Genius not ready or missing title/artist.")
            return
        if self.search_in_progress:
            print("Auto-fetch: Search already in progress, skipping.")
            return

        title = utils.clean_title_for_lyrics(title)
        # Artist might also need cleaning if it contains VEVO or similar
        artist = re.sub(r'(?i)VEVO$', '', artist).strip()

        self.tc_judul.SetValue(title)
        self.tc_artis.SetValue(artist)
        self.cb_no_artist.SetValue(False)
        self.tc_artis.Enable(True)
        self.clear_results()
        self.display_area.SetValue(_("Auto-fetching lyrics..."))
        self.button_cari.Disable()
        self.search_in_progress = True
        nvda.speak(_("Auto-fetching lyrics..."))
        threading.Thread(target=self.perform_search, args=(artist, title, False, True), daemon=True).start()

    def perform_search(self, artist, title, no_artist, is_auto=False):
        import requests
        error_message = None
        results = None

        try:
            if not utils.is_internet_available():
                raise requests.exceptions.ConnectionError(_("No internet connection detected."))

            genius = self.get_genius()
            if not genius:
                raise RuntimeError(_("Lyrics component not initialized."))

            if no_artist and not is_auto:
                response = genius.search_songs(title, per_page=15)
                results = response.get('hits', []) if response else []
                results = self._remove_duplicate_results(results)
                if results:
                    wx.CallAfter(self.show_search_results_dialog, results)
                    return
                else:
                    error_message = _("Song lyrics not found.")
            else:
                lyrics = self._fetch_lyrics_direct(artist, title)
                if lyrics:
                    speak_msg = _("Auto-fetch complete.") if is_auto else _("Lyrics search complete.")
                    nvda.speak(speak_msg)
                    wx.CallAfter(self.update_ui, lyrics, artist, title)
                else:
                    error_message = _("Auto-fetch: Lyrics not found.") if is_auto else _("Song lyrics not found.")

            if error_message:
                wx.CallAfter(self.handle_error, error_message)
                if not is_auto:
                    wx.CallAfter(lambda: utils.show_message_dialog(self, error_message, _("Not Found"), wx.OK | wx.ICON_INFORMATION))
                else:
                    nvda.speak(error_message)

        except requests.exceptions.ConnectionError as e:
            error_message = _("Internet connection error: ") + str(e)
            wx.CallAfter(self.handle_error, error_message)
            if not is_auto: wx.CallAfter(lambda: utils.show_error_dialog(self, error_message, _("Connection Error")))
        except requests.exceptions.Timeout:
            error_message = _("Lyrics search timed out.")
            wx.CallAfter(self.handle_error, error_message)
            if not is_auto: wx.CallAfter(lambda: utils.show_error_dialog(self, error_message, _("Timeout")))
        except Exception as e:
            error_message = _("An error occurred: ") + str(e)
            print(f"Unexpected lyrics search error: {e}")
            wx.CallAfter(self.handle_error, error_message)
            if not is_auto: wx.CallAfter(lambda: utils.show_error_dialog(self, error_message, _("Lyrics Search Error")))
        finally:
            if not results:
                wx.CallAfter(self.finalize_search)

    def finalize_search(self):
        if not self:
            return
        self.search_in_progress = False
        if LYRICSGENIUS_ENABLED or self.genius:
            self.button_cari.Enable()
        if wx.IsBusy():
            wx.EndBusyCursor()

    def show_search_results_dialog(self, results):
        top_level_window = wx.GetApp().GetTopWindow()
        with SearchResultsDialog(top_level_window, _("Lyrics Search Results"), results) as dlg:
            result_code = dlg.ShowModal()
            selected_result_data = dlg.GetSelectedResult()

        if result_code == wx.ID_OK and selected_result_data:
            try:
                result_details = selected_result_data.get("result", {})
                artist_details = result_details.get("primary_artist", {})
                artist_name = artist_details.get("name")
                song_title = result_details.get("title")
                if artist_name and song_title:
                    self.tc_judul.SetValue(song_title)
                    self.tc_artis.SetValue(artist_name)
                    self.cb_no_artist.SetValue(False)
                    self.tc_artis.Enable(True)
                    wx.CallAfter(wx.BeginBusyCursor)
                    wx.CallAfter(self.display_area.SetValue, _("Fetching lyrics for '{}'...").format(song_title))
                    nvda.speak(_("Fetching lyrics for '{}'...").format(song_title))
                    threading.Thread(target=self._fetch_selected_lyrics, args=(artist_name, song_title), daemon=True).start()
                    return
                else:
                    raise KeyError(_("Missing artist name or song title in selected result."))
            except KeyError as e:
                wx.CallAfter(self.handle_error, _("Error processing selected result: {}").format(e))
                wx.CallAfter(self.finalize_search)
            except Exception as e:
                wx.CallAfter(self.handle_error, _("An error occurred: ") + str(e))
                wx.CallAfter(self.finalize_search)
        else:
            wx.CallAfter(self.display_lyrics_message)
            wx.CallAfter(self.finalize_search)

    def _fetch_selected_lyrics(self, artist, title):
        import requests
        lyrics = None
        error_message = None
        try:
            if not utils.is_internet_available():
                raise requests.exceptions.ConnectionError(_("No internet connection detected."))
            lyrics = self._fetch_lyrics_direct(artist, title)
            if lyrics:
                nvda.speak(_("Lyrics search complete."))
                wx.CallAfter(self.update_ui, lyrics, artist, title)
            else:
                error_message = _("Song lyrics not found.")
                wx.CallAfter(self.handle_error, error_message)
                wx.CallAfter(lambda: utils.show_message_dialog(self, error_message, _("Not Found"), wx.OK | wx.ICON_INFORMATION))
        except requests.exceptions.ConnectionError as e:
            error_message = _("Internet connection error: ") + str(e)
            wx.CallAfter(self.handle_error, error_message)
            wx.CallAfter(lambda: utils.show_error_dialog(self, error_message, _("Connection Error")))
        except requests.exceptions.Timeout:
            error_message = _("Lyrics fetch timed out.")
            wx.CallAfter(self.handle_error, error_message)
            wx.CallAfter(lambda: utils.show_error_dialog(self, error_message, _("Timeout")))
        except Exception as e:
            error_message = _("An error occurred: ") + str(e)
            print(f"Unexpected lyrics fetch error: {e}")
            wx.CallAfter(self.handle_error, error_message)
            wx.CallAfter(lambda: utils.show_error_dialog(self, error_message, _("Lyrics Fetch Error")))
        finally:
            wx.CallAfter(self.finalize_search)

    def update_ui(self, lyrics, artist, title):
        if not self:
            return
        self.lyrics_cache = lyrics
        self.current_artist = artist
        self.current_title = title
        self.display_area.SetValue(lyrics)
        self.button_copy.Enable()
        has_save = feature_manager.is_feature_enabled(self.main_frame.settings, feature_manager.FEATURE_SAVE_LYRICS)
        self.button_save.Enable(has_save)

    def handle_error(self, error_message):
        if not self:
            return
        self.lyrics_cache = None
        self.current_artist = ""
        self.current_title = ""
        self.display_area.SetValue(f"{_('Error')}:\n{error_message}")
        self.button_copy.Disable()
        self.button_save.Disable()

    def _fetch_lyrics_direct(self, artist, title):
        import requests
        genius = self.get_genius()
        if not genius: return None
        try:
            song = genius.search_song(title=title, artist=artist)
            if song and hasattr(song, 'lyrics'):
                lyrics = self._clean_lyrics(song.lyrics)
                return lyrics.strip() if lyrics else None
            return None
        except requests.exceptions.RequestException as e:
            print(f"Genius API Fetch Request Error: {e}")
            raise e
        except Exception as e:
            print(f"Genius API Fetch Error: {e}")
            raise e

    def _clean_lyrics(self, lyrics):
        if not lyrics: return ""
        import re
        lyrics = re.sub(r"^\d*\s*Contributors?.*? Lyrics", "", lyrics, flags=re.IGNORECASE | re.DOTALL)
        lyrics = re.sub(r"\[.*?\]", "", lyrics)
        lyrics = re.sub(r"\d+Embed$", "", lyrics.strip(), flags=re.IGNORECASE)
        lyrics = re.sub(r"You might also like.*$", "", lyrics.strip(), flags=re.IGNORECASE | re.DOTALL)
        lyrics = "\n".join([line.strip() for line in lyrics.splitlines() if line.strip()])
        return lyrics

    def clear_results(self):
        self.lyrics_cache = None
        self.current_artist = ""
        self.current_title = ""
        self.display_area.Clear()
        self.button_copy.Disable()
        self.button_save.Disable()

    def _remove_duplicate_results(self, hits):
        unique_hits = []
        seen = set()
        for hit in hits:
            try:
                if hit.get('type') == 'song':
                    result_data = hit.get('result', {})
                    artist_data = result_data.get('primary_artist', {})
                    title = result_data.get('title', '').lower().strip()
                    artist = artist_data.get('name', '').lower().strip()
                    if title and artist:
                        identifier = (title, artist)
                        if identifier not in seen:
                            unique_hits.append(hit)
                            seen.add(identifier)
            except Exception as e:
                print(f"Error processing hit for duplicate check: {e}")
        return unique_hits