import wx
import threading
import requests
import constants
from translation_manager import _
import nvda
import utils
import re
import html
import os
import time

# In-memory comments cache for instant reopening
_COMMENTS_CACHE = {}

class VideoCommentsDialog(wx.Dialog):
    """
    Dialog to display comments for a YouTube video.
    """
    def __init__(self, parent, video_url, video_title):
        super().__init__(parent, title=_("Comments: {}").format(video_title), size=(650, 520), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.video_url = video_url
        self.video_title = video_title
        self.comments_data = []
        self.displayed_comments = []
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        self._last_nav_sound_time = 0
        
        self.InitUI()
        self.load_comments()
        
        # Play popup open sound
        utils.play_sound(self._get_app_settings(), "popup_open")

    def _get_app_settings(self):
        app = wx.GetApp()
        top = app.GetTopWindow() if app else None
        return getattr(top, 'settings', {}) if top else {}

    def InitUI(self):
        vbox = wx.BoxSizer(wx.VERTICAL)

        self.status_label = wx.StaticText(self, label=_("Loading comments..."))
        vbox.Add(self.status_label, 0, wx.ALL | wx.EXPAND, 10)

        self.comments_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.WANTS_CHARS)
        self.comments_list.SetName(_("Comments List"))
        self.comments_list.InsertColumn(0, _("Author"), width=150)
        self.comments_list.InsertColumn(1, _("Comment"), width=440)
        vbox.Add(self.comments_list, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)
        
        self.comments_list.Bind(wx.EVT_LIST_ITEM_FOCUSED, self.on_item_focused)
        self.comments_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_item_activated)
        self.comments_list.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
        self.comments_list.Bind(wx.EVT_KEY_DOWN, self.on_list_key_down)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.view_btn = wx.Button(self, label=_("View Full Comment"))
        self.view_btn.SetName(_("View Full Comment"))
        self.view_btn.Bind(wx.EVT_BUTTON, self.on_view_full_comment)
        btn_sizer.Add(self.view_btn, 0, wx.RIGHT, 5)

        self.copy_btn = wx.Button(self, label=_("Copy Comment"))
        self.copy_btn.SetName(_("Copy Comment"))
        self.copy_btn.Bind(wx.EVT_BUTTON, self.on_copy_comment)
        btn_sizer.Add(self.copy_btn, 0, wx.RIGHT, 10)

        btn_sizer.AddStretchSpacer(1)

        close_btn = wx.Button(self, wx.ID_CLOSE, label=_("Close"))
        close_btn.SetName(_("Close"))
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        self.Bind(wx.EVT_CLOSE, lambda e: self.EndModal(wx.ID_CLOSE))
        btn_sizer.Add(close_btn, 0)

        vbox.Add(btn_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

        self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
        self.SetSizer(vbox)
        self.CentreOnParent()

    def on_char_hook(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CLOSE)
        else:
            event.Skip()

    def load_comments(self):
        if self.video_url in _COMMENTS_CACHE:
            self.comments_data = _COMMENTS_CACHE[self.video_url]
            self.update_list()
            return
        threading.Thread(target=self._fetch_comments_thread, daemon=True).start()

    def _fetch_comments_thread(self):
        try:
            app = wx.GetApp()
            comment_limit = constants.DEFAULT_COMMENT_FETCH_LIMIT
            if app and hasattr(app.GetTopWindow(), 'settings'):
                comment_limit = app.GetTopWindow().settings.get("comment_fetch_limit", constants.DEFAULT_COMMENT_FETCH_LIMIT)
            
            str_limit = str(comment_limit)

            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'getcomments': True,
                'playlist_items': '0',
                'no_color': True,
                'nocheckcertificate': True,
                'extract_flat': 'discard',
                'format': 'worst',
                'extractor_args': {
                    'youtube': {
                        'skip': ['dash', 'hls', 'translated_subs', 'formats'],
                        'max_comments': [str_limit, 'all', 'all']
                    }
                }
            }
            if app and hasattr(app.GetTopWindow(), 'settings'):
                import settings_manager
                cookies_path = settings_manager.get_effective_cookies_path(app.GetTopWindow().settings)
                if cookies_path and os.path.exists(cookies_path):
                    ydl_opts['cookiefile'] = cookies_path

            import yt_dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.video_url, download=False)
                if info and 'comments' in info:
                    self.comments_data = info['comments']
                    if len(_COMMENTS_CACHE) >= 10:
                        _COMMENTS_CACHE.pop(next(iter(_COMMENTS_CACHE)))
                    _COMMENTS_CACHE[self.video_url] = self.comments_data
        except Exception as e:
            msg = self.ansi_escape.sub('', str(e))
            wx.CallAfter(lambda m=msg: self.status_label.SetLabel(_("Error fetching comments: {}").format(m)) if self else None)
            return

        wx.CallAfter(self.update_list)

    def update_list(self):
        if not self:
            return
        self.comments_list.Freeze()
        self.displayed_comments = []
        try:
            self.comments_list.DeleteAllItems()
            if not self.comments_data:
                self.status_label.SetLabel(_("No comments found or disabled."))
            else:
                for comment in self.comments_data:
                    author = comment.get('author', _('Unknown'))
                    text = comment.get('text', '')
                    if not text: continue
                    text = html.unescape(text)
                    
                    idx = self.comments_list.InsertItem(self.comments_list.GetItemCount(), author)
                    self.comments_list.SetItem(idx, 1, text)
                    self.displayed_comments.append(comment)
                self.status_label.SetLabel(_("Loaded {} comments.").format(len(self.displayed_comments)))
        finally:
            self.comments_list.Thaw()

        if self.displayed_comments and self.comments_list.GetItemCount() > 0:
            self.comments_list.SetFocus()
            self.comments_list.Select(0)
            self.comments_list.Focus(0)
            nvda.speak(_("Loaded {} comments. Press Enter to view full comment.").format(len(self.displayed_comments)))
        elif not self.displayed_comments:
            nvda.speak(_("No comments found."))

    def _get_selected_comment(self):
        sel = self.comments_list.GetFirstSelected()
        if sel == wx.NOT_FOUND or sel >= len(self.displayed_comments):
            return None
        return self.displayed_comments[sel]

    def on_item_focused(self, event):
        now = time.time()
        if now - self._last_nav_sound_time > 0.08:
            self._last_nav_sound_time = now
            utils.play_sound(self._get_app_settings(), "popup_navigate")
        event.Skip()

    def on_list_key_down(self, event):
        keyCode = event.GetKeyCode()
        if keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.on_view_full_comment(None)
        elif keyCode == wx.WXK_ESCAPE:
            self.Close()
        elif keyCode == wx.WXK_TAB:
            flags = wx.NavigationKeyEvent.IsBackward if event.ShiftDown() else wx.NavigationKeyEvent.IsForward
            event.GetEventObject().Navigate(flags)
        else:
            event.Skip()

    def on_item_activated(self, event):
        self.on_view_full_comment(None)

    def on_view_full_comment(self, event):
        comment = self._get_selected_comment()
        if not comment:
            return
        author = comment.get('author', _('Unknown'))
        raw_text = html.unescape(comment.get('text', ''))
        
        utils.play_sound(self._get_app_settings(), "popup_open")
        with wx.Dialog(self, title=_("Comment by {}").format(author), size=(550, 350), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER) as dlg:
            panel = wx.Panel(dlg)
            sizer = wx.BoxSizer(wx.VERTICAL)
            
            text_ctrl = wx.TextCtrl(panel, value=raw_text, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_AUTO_URL | wx.VSCROLL)
            text_ctrl.SetName(_("Comment Text"))
            sizer.Add(text_ctrl, 1, wx.ALL | wx.EXPAND, 10)
            
            btn_sizer = wx.StdDialogButtonSizer()
            copy_btn = wx.Button(panel, label=_("Copy Comment"))
            copy_btn.SetName(_("Copy Comment"))
            copy_btn.Bind(wx.EVT_BUTTON, lambda e: utils.copy_text_to_clipboard(raw_text))
            btn_sizer.AddButton(copy_btn)

            close_btn = wx.Button(panel, wx.ID_CLOSE, label=_("Close"))
            close_btn.SetName(_("Close"))
            close_btn.Bind(wx.EVT_BUTTON, lambda e: dlg.EndModal(wx.ID_CLOSE))
            dlg.Bind(wx.EVT_CLOSE, lambda e: dlg.EndModal(wx.ID_CLOSE))
            btn_sizer.AddButton(close_btn)
            btn_sizer.Realize()
            sizer.Add(btn_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 10)

            panel.SetSizer(sizer)

            def on_dlg_key(e):
                if e.GetKeyCode() == wx.WXK_ESCAPE:
                    dlg.EndModal(wx.ID_CLOSE)
                else:
                    e.Skip()
            dlg.Bind(wx.EVT_CHAR_HOOK, on_dlg_key)

            dlg.CentreOnParent()
            text_ctrl.SetFocus()
            nvda.speak(_("Viewing comment by {}. Press Escape to close.").format(author))
            dlg.ShowModal()

    def on_copy_comment(self, event):
        comment = self._get_selected_comment()
        if not comment:
            return
        raw_text = html.unescape(comment.get('text', ''))
        utils.copy_text_to_clipboard(raw_text)
        nvda.speak(_("Comment copied to clipboard."))

    def on_context_menu(self, event):
        comment = self._get_selected_comment()
        if not comment:
            return
        
        utils.play_sound(self._get_app_settings(), "popup_open")
        menu = wx.Menu()
        author = comment.get('author', _('Unknown'))
        raw_text = html.unescape(comment.get('text', ''))

        view_item = menu.Append(wx.ID_ANY, _("View Full Comment"))
        copy_text_item = menu.Append(wx.ID_ANY, _("Copy Comment Text"))
        copy_author_item = menu.Append(wx.ID_ANY, _("Copy Author Name"))

        menu.Bind(wx.EVT_MENU, lambda e: self.on_view_full_comment(None), view_item)
        menu.Bind(wx.EVT_MENU, lambda e: (utils.copy_text_to_clipboard(raw_text), nvda.speak(_("Comment copied to clipboard."))), copy_text_item)
        menu.Bind(wx.EVT_MENU, lambda e: (utils.copy_text_to_clipboard(author), nvda.speak(_("Author copied to clipboard."))), copy_author_item)

        self.PopupMenu(menu)
        menu.Destroy()
