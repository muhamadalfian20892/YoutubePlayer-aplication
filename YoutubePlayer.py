import wx
import yt_dlp
import ctypes
import webbrowser
import os
import sys
import threading
import re
from datetime import datetime
from plyer import notification
import json
import wx.media
from playsound import playsound
import lyricsgenius
import requests
import gc  # Garbage collection

dllName = "nvdaControllerClient32.dll"
dllPath = os.path.abspath(dllName)

try:
   nvdaControllerClient = ctypes.cdll.LoadLibrary(dllPath)
except OSError as e:
    print("Error loading the NVDA Controller DLL:", e)
    sys.exit(1)

def speak(text):
    nvdaControllerClient.nvdaController_speakText(text)

def NVDA_beep():
    nvdaControllerClient.nvdaController_beep(0)

class SearchResultsDialog(wx.Dialog):
    """A dialog to display search results and allow selection."""

    def __init__(self, parent, title, results):
        super(SearchResultsDialog, self).__init__(parent, title=title, size=(600, 400))
        self.results = results
        self.selected_result = None
        self.selected_index = wx.NOT_FOUND # Initialize selected_index
        self.InitUI()

    def InitUI(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        instructions = wx.StaticText(panel, label="Matching results found. Use up/down arrows to navigate and Enter to select:")
        vbox.Add(instructions, flag=wx.ALL, border=10)
        self.result_list = wx.ListBox(panel, style=wx.LB_SINGLE)
        for hit in self.results:
            # Corrected line to handle potential NoneType for release_date_components
            result_str = f"{hit['result']['title']} - {hit['result']['primary_artist']['name']} ({(hit['result'].get('release_date_components') or {}).get('year', 'N/A')})"
            self.result_list.Append(result_str)
        vbox.Add(self.result_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        self.result_list.Bind(wx.EVT_LISTBOX, self.OnListSelect)
        self.result_list.Bind(wx.EVT_LISTBOX_DCLICK, self.OnOK)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        ok_button = wx.Button(panel, label="OK")
        ok_button.Bind(wx.EVT_BUTTON, self.OnOK)
        cancel_button = wx.Button(panel, label="Cancel")
        cancel_button.Bind(wx.EVT_BUTTON, self.OnCancel)
        hbox.Add(ok_button, flag=wx.RIGHT, border=10)
        hbox.Add(cancel_button)
        vbox.Add(hbox, flag=wx.ALIGN_CENTER | wx.ALL, border=10)
        panel.SetSizer(vbox)
        self.Centre()

    def OnListSelect(self, event):
        self.selected_index = self.result_list.GetSelection()
        if self.selected_index != wx.NOT_FOUND:
            self.selected_result = self.results[self.selected_index]

    def OnOK(self, event):
        if self.result_list.GetSelection() == wx.NOT_FOUND:
            wx.MessageBox("Please select a search result.", "Warning", wx.OK | wx.ICON_WARNING)
            return
        self.selected_index = self.result_list.GetSelection()
        self.selected_result = self.results[self.selected_index]
        self.EndModal(wx.ID_OK)

    def OnCancel(self, event):
        self.selected_result = None
        self.EndModal(wx.ID_CANCEL)

    def GetSelectedResult(self):
        return self.selected_result

class LyricsSearchPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.token = "Sw9rbVa7sj1NEP3FB_X7RijVcp11vJhJfrSY1hL5uscyYbt3JmDpNesFVd52xO9d" # Make sure to replace with your actual token
        self.genius = lyricsgenius.Genius(self.token, skip_non_songs=True, excluded_terms=["(Remix)", "(Live)"], remove_section_headers=True)
        self.lyrics_cache = None
        self.InitUI()

    def InitUI(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        hbox_input = wx.BoxSizer(wx.HORIZONTAL)
        label_judul = wx.StaticText(self, label="Song Title:")
        hbox_input.Add(label_judul, flag=wx.RIGHT, border=8)
        self.tc_judul = wx.TextCtrl(self)
        hbox_input.Add(self.tc_judul, proportion=1, flag=wx.EXPAND)
        label_artis = wx.StaticText(self, label="Artist Name:")
        hbox_input.Add(label_artis, flag=wx.RIGHT, border=8)
        self.tc_artis = wx.TextCtrl(self)
        hbox_input.Add(self.tc_artis, proportion=1, flag=wx.EXPAND)
        self.cb_no_artist = wx.CheckBox(self, label="I don't know artist name")
        hbox_input.Add(self.cb_no_artist, flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=10)
        button_cari = wx.Button(self, label="Search Lyrics")
        button_cari.Bind(wx.EVT_BUTTON, self.OnSearchLyrics)
        hbox_input.Add(button_cari, flag=wx.LEFT, border=10)
        vbox.Add(hbox_input, flag=wx.EXPAND | wx.ALL, border=10)

        self.display_area = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
        vbox.Add(self.display_area, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        hbox_buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.button_copy = wx.Button(self, label="Copy")
        self.button_copy.Bind(wx.EVT_BUTTON, self.OnCopy)
        hbox_buttons.Add(self.button_copy)
        vbox.Add(hbox_buttons, flag=wx.ALIGN_CENTER | wx.BOTTOM, border=10)

        self.SetSizer(vbox)
        self.display_lyrics_message()

    def display_lyrics_message(self):
        self.display_area.SetValue("No lyrics loaded. Please search for a song.")

    def OnCopy(self, event):
        data = wx.TextDataObject()
        data.SetText(self.display_area.GetValue())
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(data)
            wx.TheClipboard.Close()
            speak("text copyed to clipboard!")
        else:
            wx.MessageBox("Could not access clipboard.", "Error", wx.OK | wx.ICON_ERROR)

    def OnSearchLyrics(self, event):
        self.clear_results()
        judul = self.tc_judul.GetValue()
        artis = self.tc_artis.GetValue()
        no_artist = self.cb_no_artist.IsChecked()

        if not judul:
            wx.MessageBox("Please enter a song title.", "Error", wx.OK | wx.ICON_ERROR)
            return

        if not no_artist and not artis:
            wx.MessageBox("Please enter artist name or check 'I don't know artist name'.", "Error", wx.OK | wx.ICON_ERROR)
            return

        speak("searching...")
        thread = threading.Thread(target=self.perform_search, args=(artis, judul, no_artist))
        thread.daemon = True
        thread.start()
        wx.BeginBusyCursor()

    def perform_search(self, artis, judul, no_artist):
        try:
            if no_artist:
                results = self.search_without_artist(judul)
                if results:
                    wx.CallAfter(self.show_search_results_dialog, results)
                else:
                    wx.CallAfter(self.display_lyrics_message)
            else:
                lyrics = self.fetch_lyrics(artis, judul)
                speak("search complete.")
                wx.CallAfter(self.update_ui, lyrics, artis, judul)

        except requests.exceptions.ConnectionError as e:
            error_message = f"Internet connection error: {str(e)}"
            wx.CallAfter(self.handle_error, error_message)
            wx.CallAfter(lambda: wx.MessageBox(error_message, "Connection Error", wx.OK | wx.ICON_ERROR))
        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            wx.CallAfter(self.handle_error, error_message)
        finally:
            wx.CallAfter(wx.EndBusyCursor)
            wx.CallAfter(gc.collect)

    def show_search_results_dialog(self, results):
        dlg = SearchResultsDialog(self, "Search Results", results)
        if dlg.ShowModal() == wx.ID_OK:
            selected_result = dlg.GetSelectedResult()
            if selected_result:
                lyrics = self.fetch_lyrics(
                    selected_result["result"]["primary_artist"]["name"],
                    selected_result["result"]["title"]
                )
                artis = selected_result["result"]["primary_artist"]["name"]
                self.update_ui(lyrics, artis, selected_result["result"]["title"])
        else:
            self.clear_results()
            self.display_lyrics_message()
        dlg.Destroy()

    def update_ui(self, lyrics, artis, judul):
        if lyrics:
            self.lyrics_cache = lyrics
            self.display_area.SetValue(lyrics) # Removed unnecessary encoding/decoding that could cause issues
        else:
            self.display_lyrics_message()
            if self.is_online():
                wx.MessageBox("Song lyrics not found.", "Info", wx.OK | wx.ICON_INFORMATION)

    def handle_error(self, error_message):
        self.lyrics_cache = error_message
        self.display_area.SetValue(error_message)

    def search_without_artist(self, title):
        base_url = "https://api.genius.com"
        search_url = f"{base_url}/search?q={title}"
        headers = {"Authorization": "Bearer " + self.token}
        try:
            response = requests.get(search_url, headers=headers)
            response.raise_for_status()
            data = response.json()
            hits = data["response"]["hits"]
            return self.remove_duplicate_results(hits)
        except requests.exceptions.RequestException as e:
            print(f"Requests Error: {e}")
            return None

    def fetch_lyrics(self, artist, title):
        try:
            song = self.genius.search_song(title=title, artist=artist) # removed verbose=False
            if song:
                lyrics = self.clean_lyrics(song.lyrics)
                return lyrics
            return None
        except Exception as e:
            print(f"Genius API Error: {e}") # More specific error logging
            return None

    def clean_lyrics(self, lyrics):
        lyrics = re.sub(r"^.*?\[.*?\]\n", "", lyrics, flags=re.MULTILINE)
        lyrics = re.sub(r"\n\[.*?\]", "", lyrics)
        lyrics = re.sub(r"[\(\[].*?[\)\]]", "", lyrics)
        lyrics = re.sub(r"\d*Embed$", "", lyrics)
        lyrics = re.sub(r"[^\w\s\n'-]", "", lyrics)
        return lyrics

    def clear_results(self):
        self.lyrics_cache = None
        self.display_area.Clear()

    def is_online(self):
        try:
            requests.get("https://8.8.8.8", timeout=5)
            return True
        except requests.exceptions.ConnectionError:
            return False

    def remove_duplicate_results(self, hits):
        unique_hits = []
        seen = set()
        for hit in hits:
            title = hit['result']['title'].lower()
            artist = hit['result']['primary_artist']['name'].lower()
            if (title, artist) not in seen:
                unique_hits.append(hit)
                seen.add((title, artist))
        return unique_hits


class YoutubeSearchPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.history = []
        self.current_search_query = ""
        self.current_search_results = []
        self.next_page_token = None
        self.results_per_page = 20
        self.search_thread = None # To prevent multiple search threads running

        vbox = wx.BoxSizer(wx.VERTICAL)

        hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        self.search_text = wx.TextCtrl(self, style=wx.TE_PROCESS_ENTER)
        self.search_text.Bind(wx.EVT_TEXT_ENTER, self.on_search)
        hbox1.Add(self.search_text, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        vbox.Add(hbox1, flag=wx.EXPAND)

        self.results_list = wx.ListBox(self, style=wx.LB_SINGLE)
        self.results_list.Bind(wx.EVT_LISTBOX, self.on_item_selected)
        self.results_list.Bind(wx.EVT_CONTEXT_MENU, self.show_context_menu)
        vbox.Add(self.results_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        self.load_more_button = wx.Button(self, label="Load More")
        self.load_more_button.Bind(wx.EVT_BUTTON, self.on_load_more)
        self.load_more_button.Hide()
        vbox.Add(self.load_more_button, flag=wx.ALIGN_CENTER | wx.ALL, border=5)

        self.run_ytdl_button = wx.Button(self, label="Run Youtube DL")
        self.run_ytdl_button.Bind(wx.EVT_BUTTON, self.on_run_ytdl)
        vbox.Add(self.run_ytdl_button, flag=wx.ALIGN_CENTER | wx.ALL, border=5)

        self.exit_button = wx.Button(self, label="Exit")
        self.exit_button.Bind(wx.EVT_BUTTON, self.on_exit)
        vbox.Add(self.exit_button, flag=wx.ALIGN_CENTER | wx.ALL, border=5)

        self.SetSizer(vbox)
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

    def on_exit(self, event):
        self.parent.GetParent().Close() # Changed to get MainFrame and Close

    def on_key_down(self, event):
        if event.AltDown() and event.GetKeyCode() == wx.WXK_LEFT:
            self.go_back()
        else:
            event.Skip()

    def on_search(self, event):
        query = self.search_text.GetValue()
        if not query:
            return

        if self.search_thread and self.search_thread.is_alive(): # Prevent overlapping searches
            wx.MessageBox("A search is already in progress. Please wait.", "Warning", wx.OK | wx.ICON_WARNING)
            return

        self.current_search_query = query
        self.current_search_results = []
        self.next_page_token = None
        self.results_list.Clear()
        self.history.append(('search', query))
        self.load_more_button.Hide()
        self.search_thread = threading.Thread(target=self.run_search, args=(query,), daemon=True) # Assign thread to self.search_thread
        self.search_thread.start()
        speak("searching...")

    def run_search(self, query, page_token=None):
        ydl_opts = {
            'quiet': True,
            'extract_flat': 'in_playlist',
            'playlistend': self.results_per_page,
            'noprogress': True,
            'skip_download': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_string = f"ytsearch{self.results_per_page}:{query}"
                result = ydl.extract_info(search_string, download=False)

                if 'entries' in result:
                    new_results = [entry for entry in result['entries'] if entry]
                    self.current_search_results.extend(new_results)
                    self.next_page_token = result.get('nextpagetoken')

                    def append_to_list():
                        for entry in new_results:
                            self.results_list.Append(
                                f"{entry.get('title', 'No Title')} - {entry.get('uploader', 'No Uploader')}",
                                clientData=entry)
                        if 'entries' in result and len(result['entries']) >= self.results_per_page :
                            self.load_more_button.Show()
                        else:
                             self.load_more_button.Hide()
                    wx.CallAfter(append_to_list)
        except yt_dlp.utils.DownloadError as e:

            wx.CallAfter(wx.MessageBox, f"Error during search: {e}", "Search Error", wx.OK | wx.ICON_ERROR)
        finally:
            self.search_thread = None # Reset search_thread after completion or error
            speak("search complete.")

    def on_load_more(self, event):
        if len(self.current_search_results) >= 10000:
             wx.MessageBox("Reached maximum search results (10000).", "Info", wx.OK | wx.ICON_INFORMATION)
             self.load_more_button.Hide()
             return
        self.results_per_page += 20
        threading.Thread(target=self.run_search, args=(self.current_search_query,), daemon=True).start()

    def on_item_selected(self, event):
        event.Skip()

    def show_context_menu(self, event):
        pos = event.GetPosition()
        if pos != wx.DefaultPosition:
            pos = self.results_list.ScreenToClient(pos)
            item_index = self.results_list.HitTest(pos)
        else:
            item_index = self.results_list.GetSelection()

        if item_index == wx.NOT_FOUND:
            return

        selected_item = self.results_list.GetClientData(item_index)
        if not selected_item:
            return
        self.history.append(('item', selected_item))

        menu = wx.Menu()
        open_browser_item = menu.Append(wx.ID_ANY, "Open in Browser")
        view_channel_item = menu.Append(wx.ID_ANY, "View Channel")
        view_description_item = menu.Append(wx.ID_ANY, "View Description")
        view_details_item = menu.Append(wx.ID_ANY, "View Video Details")
        download_item = menu.Append(wx.ID_ANY, "Download with Youtube DL")
        play_item = menu.Append(wx.ID_ANY, "Play Audio") # Changed label to be more specific

        copy_menu = wx.Menu()
        copy_video_link_item = copy_menu.Append(wx.ID_ANY, "Copy Video Link")
        copy_channel_link_item = copy_menu.Append(wx.ID_ANY, "Copy Channel Link")
        copy_title_item = copy_menu.Append(wx.ID_ANY, "Copy Title")
        menu.AppendSubMenu(copy_menu, "Copy")

        self.Bind(wx.EVT_MENU, lambda evt, url=selected_item['url']: self.open_in_browser(url), open_browser_item)
        self.Bind(wx.EVT_MENU, lambda evt, uploader_url=selected_item.get('channel_url', selected_item.get('uploader_url', '')) : self.view_channel(uploader_url), view_channel_item)
        self.Bind(wx.EVT_MENU, lambda evt, url=selected_item['url']: self.view_description(url), view_description_item)
        self.Bind(wx.EVT_MENU, lambda evt, url=selected_item['url']: self.view_video_details(url), view_details_item)
        self.Bind(wx.EVT_MENU, lambda evt, url=selected_item['url']: self.run_ytdl_with_link(url), download_item)
        self.Bind(wx.EVT_MENU, lambda evt, url=selected_item['url'], title=selected_item.get('title', 'Video'), uploader=selected_item.get('uploader', 'Uploader'): self.play_audio(url, title, uploader), play_item) # Pass title and uploader

        self.Bind(wx.EVT_MENU, lambda evt, url=selected_item['url']: self.copy_to_clipboard(url), copy_video_link_item)
        self.Bind(wx.EVT_MENU, lambda evt, url=selected_item.get('channel_url', selected_item.get('uploader_url', '')): self.copy_to_clipboard(url), copy_channel_link_item)
        self.Bind(wx.EVT_MENU, lambda evt, title=selected_item.get('title', ''): self.copy_to_clipboard(title), copy_title_item)

        self.PopupMenu(menu)
        menu.Destroy()

    def copy_to_clipboard(self, text):
        if text:
            data = wx.TextDataObject()
            data.SetText(text)
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(data)
                wx.TheClipboard.Close()
            else:
                wx.MessageBox("Unable to open clipboard.", "Error", wx.OK | wx.ICON_ERROR)

    def open_in_browser(self, url):
        webbrowser.open(url)

    def view_channel(self, channel_url):
        if channel_url:
            webbrowser.open(channel_url)
        else:
            wx.MessageBox("No channel URL available.", "Info", wx.OK | wx.ICON_INFORMATION)

    def view_description(self, video_url):
        threading.Thread(target=self.fetch_description, args=(video_url,), daemon=True).start()
        speak("getting description, please wait...")

    def fetch_description(self, video_url):
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'noprogress': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                description = info.get('description', 'No description available.')
                def show_desc_dialog():
                    dlg = wx.Dialog(self, title="Video Description", size=(500, 300))
                    text = wx.TextCtrl(dlg, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
                    text.SetValue(description)
                    sizer = wx.BoxSizer(wx.VERTICAL)
                    sizer.Add(text, 1, wx.EXPAND | wx.ALL, 10)
                    close_button = wx.Button(dlg, label="Close")
                    close_button.Bind(wx.EVT_BUTTON, lambda evt: dlg.Close())
                    sizer.Add(close_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)
                    dlg.SetSizer(sizer)
                    dlg.ShowModal()
                    dlg.Destroy()
                wx.CallAfter(show_desc_dialog)
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Error fetching description: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def view_video_details(self, video_url):
        threading.Thread(target=self.fetch_video_details, args=(video_url,), daemon=True).start()
        speak("Getting video detail...")

    def calculate_time_ago(self, date_str):
        try:
            upload_date = datetime.strptime(date_str, "%Y-%m-%d")
            now = datetime.now()
            difference = now - upload_date
            days = difference.days
            years, remainder = divmod(days, 365)
            months = remainder // 30
            if years > 0:
                return f"{years} year{'s' if years > 1 else ''} ago"
            elif months > 0:
                return f"{months} month{'s' if months > 1 else ''} ago"
            elif days > 0:
                return f"{days} day{'s' if days > 1 else ''} ago"
            else:
                return "Today"
        except (ValueError, TypeError):
            return "Invalid date"

    def fetch_video_details(self, video_url):
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'noprogress': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                title = info.get('title', 'N/A')
                uploader = info.get('uploader', 'N/A')
                duration = info.get('duration_string', 'N/A')
                views = info.get('view_count', 'N/A')
                upload_date = info.get('upload_date', 'N/A')
                if upload_date != 'N/A':
                     upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
                likes = info.get('like_count', 'N/A')
                dislikes = info.get('dislike_count', 'N/A') # Added dislike count

                time_ago = self.calculate_time_ago(upload_date)
                upload_date_display = f"{upload_date} ({time_ago})" if upload_date != 'N/A' else 'N/A'

                details_str = (
                    f"Title: {title}\n"
                    f"Uploader: {uploader}\n"
                    f"Duration: {duration}\n"
                    f"Views: {views}\n"
                    f"Upload Date: {upload_date_display}\n"
                    f"Likes: {likes}\n"
                    f"Dislikes: {dislikes}\n" # Added Dislikes to details
                )
                def show_detail_dialog():
                    dlg = wx.Dialog(self, title="Video Details", size=(500, 300))
                    text = wx.TextCtrl(dlg, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL)
                    text.SetValue(details_str)
                    sizer = wx.BoxSizer(wx.VERTICAL)
                    sizer.Add(text, 1, flag=wx.EXPAND | wx.ALL, border=10)
                    close_button = wx.Button(dlg, label="Close")
                    close_button.Bind(wx.EVT_BUTTON, lambda evt: dlg.Close())
                    sizer.Add(close_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)
                    dlg.SetSizer(sizer)
                    dlg.ShowModal()
                    dlg.Destroy()
                wx.CallAfter(show_detail_dialog)
        except Exception as e:
            wx.CallAfter(wx.MessageBox, f"Error fetching video details: {e}", "Error", wx.OK | wx.ICON_ERROR)


    def run_ytdl_with_link(self, url):
        self.parent.GetParent().show_ytdl_panel(url) # Changed to get MainFrame

    def on_run_ytdl(self, event):
        wx.CallAfter(self.show_ytdl_dialog)

    def show_ytdl_dialog(self):
        dlg = wx.Dialog(self, title="Youtube DL", size=(600, 400))
        panel = YoutubeDLPanel(dlg)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(panel, 1, wx.EXPAND)
        dlg.SetSizer(sizer)
        dlg.ShowModal()
        dlg.Destroy()

    def play_audio(self, video_url, video_title, video_uploader): # Added title and uploader parameters
        AudioPlayerDialog(self, video_url, video_title, video_uploader).ShowModal() # Pass title and uploader

    def go_back(self):
        if len(self.history) > 1:
            self.history.pop()
            previous_state = self.history.pop()

            if previous_state[0] == 'search':
                self.search_text.SetValue(previous_state[1])
                self.on_search(None)
            elif previous_state[0] == 'item':
                pass

class AudioPlayerDialog(wx.Dialog):
    def __init__(self, parent, video_url, video_title, video_uploader, auto_play=True): # Added video_title and video_uploader
        super().__init__(parent, title="Audio Player", size=(400, 300))
        self.video_url = video_url
        self.video_title = video_title # Store video title
        self.video_uploader = video_uploader # Store video uploader
        self.media_ctrl = None
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
        self.playback_thread = None
        self.is_playing = False
        self.audio_url = None
        self.error_text_value = ""
        self.auto_play = auto_play
        self.notification_sound_played = False

        self.init_ui()
        self.fetch_audio_url()

    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)

        title_text = wx.StaticText(panel, label=f"{self.video_title} - {self.video_uploader}") # Display title and uploader
        vbox.Add(title_text, flag=wx.EXPAND | wx.ALL, border=10)

        self.time_text = wx.TextCtrl(panel, style=wx.TE_READONLY)
        vbox.Add(self.time_text, flag=wx.EXPAND | wx.ALL, border=10)

        hbox_buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.rewind_button = wx.Button(panel, label="Rewind")
        self.ffwd_button = wx.Button(panel, label="Fast Forward")
        self.play_pause_button = wx.Button(panel, label="Play")
        self.close_button = wx.Button(panel, label="Close")
        self.error_text = wx.TextCtrl(panel, style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_NO_VSCROLL)
        self.error_text.SetMinSize((150, -1))

        hbox_buttons.Add(self.rewind_button, flag=wx.ALL, border=5)
        hbox_buttons.Add(self.play_pause_button, flag=wx.ALL, border=5)
        hbox_buttons.Add(self.ffwd_button, flag=wx.ALL, border=5)
        hbox_buttons.Add(self.close_button, flag=wx.ALL, border=5)
        hbox_buttons.Add(self.error_text, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)

        vbox.Add(hbox_buttons, flag=wx.EXPAND | wx.BOTTOM, border=10)

        panel.SetSizer(vbox)

        self.rewind_button.Bind(wx.EVT_BUTTON, self.on_rewind)
        self.ffwd_button.Bind(wx.EVT_BUTTON, self.on_ffwd)
        self.play_pause_button.Bind(wx.EVT_BUTTON, self.on_play_pause)
        self.close_button.Bind(wx.EVT_BUTTON, self.on_close_dialog)

    def fetch_audio_url(self):
        threading.Thread(target=self._fetch_audio_url_thread, daemon=True).start()
        speak("loading audio, please wait...")
    def _fetch_audio_url_thread(self):
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'noprogress': True,
            'format': 'bestaudio/best',
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.video_url, download=False)
                self.audio_url = info['url']
                wx.CallAfter(self.init_media_player)
        except Exception as e:
            wx.CallAfter(self.display_error, str(e))
            wx.CallAfter(self.init_media_player_failed)

    def init_media_player_failed(self):
        self.play_pause_button.Disable()

    def init_media_player(self):
        self.media_ctrl = wx.media.MediaCtrl()
        if not self.media_ctrl.Create(self, style=wx.SIMPLE_BORDER):
            wx.MessageBox("Sorry, could not create media player object.", "Error", wx.OK | wx.ICON_ERROR)
            return False

        if not self.media_ctrl.LoadURI(self.audio_url):
            wx.MessageBox(f"Sorry, could not load URI: {self.audio_url}", "Error", wx.OK | wx.ICON_ERROR)
            return False

        self.timer.Start(100)
        self.play_notification_sound()
        if self.auto_play:
            wx.CallAfter(self.auto_play_audio)

    def play_notification_sound(self):
        if self.notification_sound_played:
            return

        sound_file_path = os.path.join(os.path.dirname(__file__), "sound", "notification_complete_Load.mp3")
        if os.path.exists(sound_file_path):
            try:
                playsound(sound_file_path, block=False)
                self.notification_sound_played = True
            except Exception as e:
                print(f"Error playing notification sound: {e}")
        else:
            print(f"Notification sound file not found: {sound_file_path}")


    def auto_play_audio(self):
        if self.media_ctrl and not self.is_playing:
            self.media_ctrl.Play()
            self.play_pause_button.SetLabel("Pause")
            self.is_playing = True
            self.timer.Start(100)


    def on_timer(self, event):
        if self.media_ctrl:
            current_pos = self.media_ctrl.Tell()
            length = self.media_ctrl.Length()
            self.time_text.SetValue(f"{self.format_time(current_pos)} / {self.format_time(length)}")
            if self.is_playing and current_pos >= length - 500: # Check if near end and playing
                self.on_media_end()

    def on_media_end(self):
        self.media_ctrl.Stop()
        self.play_pause_button.SetLabel("Play")
        self.is_playing = False
        self.timer.Stop()


    def format_time(self, milliseconds):
        seconds = milliseconds // 1000
        minutes = seconds // 60
        seconds %= 60
        return f"{minutes}:{seconds:02}"

    def on_play_pause(self, event):
        if not self.media_ctrl:
            return
        if self.is_playing:
            self.media_ctrl.Pause()
            self.play_pause_button.SetLabel("Play")
            self.is_playing = False
            self.timer.Stop()
        else:
            self.media_ctrl.Play()
            self.play_pause_button.SetLabel("Pause")
            self.is_playing = True
            self.timer.Start(100)

    def on_rewind(self, event):
        if self.media_ctrl:
            current_pos = self.media_ctrl.Tell()
            new_pos = max(0, current_pos - 10000)
            self.media_ctrl.Seek(new_pos)

    def on_ffwd(self, event):
        if self.media_ctrl:
            current_pos = self.media_ctrl.Tell()
            length = self.media_ctrl.Length()
            new_pos = min(length, current_pos + 10000)
            self.media_ctrl.Seek(new_pos)

    def on_close_dialog(self, event):
        if self.media_ctrl:
            self.media_ctrl.Stop()
            self.timer.Stop()
            self.media_ctrl.Destroy() # Explicitly destroy media control
            self.media_ctrl = None # Set to None to avoid potential double destroy
        self.Destroy()

    def display_error(self, error_message):
        self.error_text_value = error_message
        wx.CallAfter(self._set_error_text)

    def _set_error_text(self):
        self.error_text.SetValue(self.error_text_value)


class YoutubeDLPanel(wx.Panel):
    def __init__(self, parent, initial_url=None):
        super().__init__(parent)
        self.parent = parent
        self.link_progress_items = {}
        self.download_thread = None # To prevent multiple download threads

        vbox = wx.BoxSizer(wx.VERTICAL)

        hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        label1 = wx.StaticText(self, label="Links to download (one per line):")
        hbox1.Add(label1, flag=wx.RIGHT, border=8)
        self.links_text = wx.TextCtrl(self, style=wx.TE_MULTILINE)
        if initial_url:
            self.links_text.SetValue(initial_url)
        hbox1.Add(self.links_text, proportion=1, flag=wx.EXPAND)
        vbox.Add(hbox1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        self.subtitles_check = wx.CheckBox(self, label="Download subtitles")
        vbox.Add(self.subtitles_check, flag=wx.LEFT | wx.TOP, border=10)

        self.description_check = wx.CheckBox(self, label="Download description")
        vbox.Add(self.description_check, flag=wx.LEFT | wx.TOP, border=10)

        self.convert_mp3_check = wx.CheckBox(self, label="Convert to MP3")
        vbox.Add(self.convert_mp3_check, flag=wx.LEFT | wx.TOP, border=10)

        hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        label2 = wx.StaticText(self, label="Download directory:")
        hbox2.Add(label2, flag=wx.RIGHT, border=8)
        self.download_dir_text = wx.TextCtrl(self)
        hbox2.Add(self.download_dir_text, proportion=1, flag=wx.EXPAND)
        self.browse_button = wx.Button(self, label="Browse")
        self.browse_button.Bind(wx.EVT_BUTTON, self.on_browse)
        hbox2.Add(self.browse_button, flag=wx.LEFT, border=5)
        vbox.Add(hbox2, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

        self.download_button = wx.Button(self, label="Download")
        self.download_button.Bind(wx.EVT_BUTTON, self.on_download)
        vbox.Add(self.download_button, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=10)

        self.progress_list = wx.ListBox(self, style=wx.LB_SINGLE | wx.LB_HSCROLL)
        vbox.Add(self.progress_list, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        self.close_button = wx.Button(self, label="Close")
        self.close_button.Bind(wx.EVT_BUTTON, self.on_close)
        vbox.Add(self.close_button, flag=wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, border=10)

        self.SetSizer(vbox)

    def on_browse(self, event):
        main_frame = self.parent.GetParent() # Adjusted to get MainFrame
        dlg = wx.DirDialog(self.parent, "Choose a download directory:",
                           style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
                           defaultPath=main_frame.settings.get("download_dir", ""))
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self.download_dir_text.SetValue(path)
            main_frame.settings["download_dir"] = path
            main_frame.save_settings()
        dlg.Destroy()

    def on_download(self, event):
        links = self.links_text.GetValue().splitlines()
        links = [link.strip() for link in links if link.strip()]
        download_dir = self.download_dir_text.GetValue()
        if not links:
            wx.MessageBox("Please enter at least one link.", "Error", wx.OK | wx.ICON_ERROR)
            return
        if not os.path.isdir(download_dir):
            wx.MessageBox("Please enter a valid download directory.", "Error", wx.OK | wx.ICON_ERROR)
            return

        if self.download_thread and self.download_thread.is_alive(): # Prevent overlapping downloads
            wx.MessageBox("A download is already in progress. Please wait.", "Warning", wx.OK | wx.ICON_WARNING)
            return

        main_frame = self.parent.GetParent() # Adjusted to get MainFrame
        main_frame.settings["download_dir"] = download_dir
        main_frame.save_settings()

        self.progress_list.Clear()
        self.link_progress_items.clear()
        for link in links:
            list_index = self.progress_list.Append(f"Preprocessing: {link}")
            self.link_progress_items[link] = list_index
        self.download_thread = threading.Thread(target=self.run_download, args=(links, download_dir), daemon=True) # Assign thread to self.download_thread
        self.download_thread.start()

    def run_download(self, links, download_dir):
        ydl_opts = {
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
            'writesubtitles': self.subtitles_check.GetValue(),
            'writedescription': self.description_check.GetValue(),
            'format': 'bestaudio/best',
            'progress_hooks': [self.download_hook],
            'restrictfilenames': True,
        }
        if self.convert_mp3_check.GetValue():
            ydl_opts['format'] = 'bestaudio[ext=m4a]/bestaudio'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
             }]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                for link in links:
                    try:
                        ydl.download([link])
                    except yt_dlp.utils.DownloadError as download_error:
                        wx.CallAfter(self.progress_list.SetString, self.link_progress_items[link], f"Error: {link}\n{download_error}")
                        wx.CallAfter(self.show_notification, "Download Error", f"Error downloading {link}: {download_error}")
                    except Exception as unexpected_error:
                        wx.CallAfter(self.progress_list.SetString, self.link_progress_items[link], f"Unexpected Error: {link}\n{unexpected_error}")
                        wx.CallAfter(self.show_notification, "Download Error", f"Unexpected error downloading {link}: {unexpected_error}")


        except yt_dlp.utils.DownloadError as e:
           wx.CallAfter(self.progress_list.Append, f"Error: {links[0] if links else 'Link'}\n{e}")
           wx.CallAfter(self.show_notification, "Download Error", f"Error downloading {links[0] if links else 'link'}")

        except Exception as e:
            wx.CallAfter(self.progress_list.Append, f"Unexpected Error: {links[0] if links else 'Link'}\n{e}")
            wx.CallAfter(self.show_notification, "Download Error", f"An unexpected error occurred with {links[0] if links else 'link'}")
        finally:
            self.download_thread = None # Reset download_thread after completion or error


    def download_hook(self, d):
      if d['status'] == 'downloading':
          percentage = d.get('_percent_str', '0.00%')
          video_url = d.get('info_dict', {}).get('webpage_url') or d.get('info_dict', {}).get('url')
          if video_url and video_url in self.link_progress_items:
              list_index = self.link_progress_items[video_url]
              filename = os.path.basename(d.get('filename', ''))
              wx.CallAfter(self.progress_list.SetString, list_index, f"Downloading {filename}: {percentage}")

      elif d['status'] == 'finished':
          video_url = d.get('info_dict', {}).get('webpage_url') or d.get('info_dict', {}).get('url')
          if video_url and video_url in self.link_progress_items:
              list_index = self.link_progress_items[video_url]
              filename = os.path.basename(d.get('filename', ''))
              wx.CallAfter(self.progress_list.SetString, list_index, f"Complete: {filename}")
              wx.CallAfter(self.show_notification, "Download Complete", f"{filename} downloaded successfully!")

      elif d['status'] == 'error':
          video_url = d.get('info_dict', {}).get('webpage_url') or d.get('info_dict', {}).get('url')
          if video_url and video_url in self.link_progress_items:
              list_index = self.link_progress_items[video_url]
              filename = os.path.basename(d.get('filename', ''))
              wx.CallAfter(self.progress_list.SetString, list_index, f"Error downloading: {filename}")
              wx.CallAfter(self.show_notification, "Download Error", f"Error downloading {filename}")


    def show_notification(self, title, message):
        try:
            notification.notify(
                title=title,
                message=message,
                app_icon=None,
                timeout=10,
            )
        except Exception as e:
            print(f"Error displaying notification: {e}")


    def on_close(self, event):
        self.parent.Destroy() # Changed to Destroy instead of Close


class MainFrame(wx.Frame):
    VERSION = "1.3.1"
    SETTINGS_FILE = "youtube_player_settings.json"

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.settings = self.load_settings()
        self.notebook = wx.Notebook(self)
        self.youtube_panel = YoutubeSearchPanel(self.notebook)
        self.lyrics_panel = LyricsSearchPanel(self.notebook) # Create Lyrics Panel
        self.notebook.AddPage(self.youtube_panel, "YouTube")
        self.notebook.AddPage(self.lyrics_panel, "Lyrics") # Add Lyrics Tab
        self.ytdl_panel = None
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.notebook, 1, wx.EXPAND) # Use notebook in sizer
        self.SetSizer(self.sizer)
        self.SetSize((800, 600))
        self.SetTitle(f"YouTube Player - v{MainFrame.VERSION}, by Technokers Lab")
        self.Centre()
        self.Bind(wx.EVT_CLOSE, self.on_close)


    def load_settings(self):
        try:
            with open(MainFrame.SETTINGS_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"download_dir": os.path.expanduser("~")}

    def save_settings(self):
        try:
            with open(MainFrame.SETTINGS_FILE, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def on_close(self, event):
        self.save_settings()
        if self.youtube_panel:
             self.youtube_panel.Destroy()
        if self.lyrics_panel:
            self.lyrics_panel.Destroy()
        self.Destroy()


    def show_ytdl_panel(self, initial_url=None):
        dlg = wx.Dialog(self, title="Youtube DL", size=(600, 400))
        panel = YoutubeDLPanel(dlg, initial_url)

        panel.download_dir_text.SetValue(self.settings.get("download_dir", ""))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(panel, 1, wx.EXPAND)
        dlg.SetSizer(sizer)
        dlg.ShowModal()
        dlg.Destroy()


if __name__ == '__main__':
    sound_dir = os.path.join(os.path.dirname(__file__), "sound")
    if not os.path.exists(sound_dir):
        os.makedirs(sound_dir)
    sound_file = os.path.join(sound_dir, "notification_complete_Load.mp3")
    if not os.path.exists(sound_file):
        with open(sound_file, 'w') as f:
            f.write('')

    app = wx.App()
    frame = MainFrame(None)
    frame.Show()
    app.MainLoop()