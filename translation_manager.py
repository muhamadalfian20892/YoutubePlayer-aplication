import gettext
import os
import sys
import wx

# local imports
import path_utils

APP_NAME_DOMAIN = "messages"
_current_trans = None
_wx_locale = None
_active_lang_code = None

def get_locale_dir():
    """Determines the path to the 'locales' directory."""
    return path_utils.get_resource_path('locales')

def set_language(lang_code=None, settings=None):
    """
    Initializes the gettext system. This part is safe to call before wx.App exists.
    """
    global _current_trans, _active_lang_code
    import constants

    if lang_code is None:
        if settings is not None and isinstance(settings, dict):
            lang_code = settings.get("language", constants.DEFAULT_PREFERRED_LANGUAGE)
        elif _active_lang_code is not None:
            lang_code = _active_lang_code
        else:
            try:
                import settings_manager
                st = settings_manager.load_settings()
                lang_code = st.get("language", constants.DEFAULT_PREFERRED_LANGUAGE)
            except Exception:
                lang_code = constants.DEFAULT_PREFERRED_LANGUAGE

    if _current_trans is not None and _active_lang_code == lang_code:
        return

    _active_lang_code = lang_code
    print(f"Attempting to set language to: {lang_code}")
    locale_dir = get_locale_dir()

    try:
        _current_trans = gettext.translation(
            domain=APP_NAME_DOMAIN,
            localedir=locale_dir,
            languages=[lang_code],
            fallback=True
        )
        print(f"Translation for language '{lang_code}' loaded.")
    except (FileNotFoundError, Exception) as e:
        print(f"Warning: Translation file for '{lang_code}' not found ({e}). Falling back to NullTranslations.")
        _current_trans = gettext.NullTranslations()
    
    _current_trans.install()

def set_wx_locale(lang_code=None, settings=None):
    """
    Configures wxPython's internal locale. This MUST be called after wx.App is created.
    """
    global _wx_locale, _active_lang_code
    import constants
    
    locale_dir = get_locale_dir()

    if lang_code is None:
        if settings is not None and isinstance(settings, dict):
            lang_code = settings.get("language", constants.DEFAULT_PREFERRED_LANGUAGE)
        elif _active_lang_code is not None:
            lang_code = _active_lang_code
        else:
            try:
                import settings_manager
                st = settings_manager.load_settings()
                lang_code = st.get("language", constants.DEFAULT_PREFERRED_LANGUAGE)
            except Exception:
                lang_code = constants.DEFAULT_PREFERRED_LANGUAGE

    try:
        if lang_code:
            lang_info = wx.Locale.FindLanguageInfo(lang_code)
            if lang_info:
                _wx_locale = wx.Locale(lang_info.Language)
                if _wx_locale.IsOk():
                    _wx_locale.AddCatalogLookupPathPrefix(locale_dir)
                    _wx_locale.AddCatalog(APP_NAME_DOMAIN) 
                    print(f"wx.Locale configured for '{lang_code}'.")
                else:
                    print(f"Warning: Could not initialize wx.Locale for '{lang_code}'.")
            else:
                print(f"Warning: wxPython does not have info for language code '{lang_code}'.")
    except Exception as e:
        print(f"Error setting wx.Locale: {e}")

def _(text):
    """
    Main translation function. Lazily initializes the language on first call.
    """
    global _current_trans
    if _current_trans is None:
        set_language()
    return _current_trans.gettext(text)