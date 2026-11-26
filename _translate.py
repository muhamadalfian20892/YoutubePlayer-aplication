import re
import os
from datetime import datetime

# --- CONFIGURATION ---

# List of Python files to scan for translatable strings
FILES_TO_SCAN = [
    'audio_player_panel.py', 'constants.py', 'discovery_panel.py', 'downloader_panel.py',
    'feature_manager.py', 'help_panel.py', 'history_panel.py', 'lyrics_panel.py', 'nvda.py',
    'onboarding_dialog.py', 'playlist_manager.py', 'radar_panel.py', 'settings_manager.py',
    'settings_panel.py', 'stats_panel.py', 'translation_manager.py', 'tunevia.py',
    'ui_components.py', 'utils.py', 'video_comments_dialog.py', 'video_player_frame.py',
    'youtube_panel.py', 'yt_dlp_manager.py'
]

# The output .po file name
OUTPUT_PO_FILE = 'template.po'

# The function name that marks a string for translation
TRANSLATION_FUNCTION = '_'

# --- SCRIPT LOGIC ---

def escape_po_string(s):
    """Escapes characters in a string for PO file format."""
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n"\n"')

def generate_po_file():
    """Scans files and generates a .po template file."""
    print("Starting scan for translatable strings...")
    
    # A dictionary to hold msgid -> [locations]
    # e.g., {'Hello': ['file1.py:10', 'file2.py:25']}
    extracted_strings = {}

    # This regex finds _("...") or _('...') and handles escaped quotes inside.
    # It has two capturing groups: one for double-quoted strings and one for single-quoted.
    pattern = re.compile(
        r"""{func}\(\s*
        (?:
            "((?:[^"\\]|\\.)*)"  # Group 1: Double-quoted string
            |
            '((?:[^'\\]|\\.)*)'  # Group 2: Single-quoted string
        )
        \s*\)""".format(func=re.escape(TRANSLATION_FUNCTION)),
        re.VERBOSE
    )

    for filename in FILES_TO_SCAN:
        if not os.path.exists(filename):
            print(f"--- WARNING: File not found, skipping: {filename}")
            continue

        print(f"Scanning {filename}...")
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    for match in pattern.finditer(line):
                        # The matched string is in either group 1 or group 2
                        msgid = match.group(1) if match.group(1) is not None else match.group(2)
                        
                        # Unescape characters like \\ and \" to get the raw string
                        msgid = msgid.encode().decode('unicode_escape')

                        if not msgid:
                            continue

                        location = f"{filename}:{line_num}"
                        if msgid not in extracted_strings:
                            extracted_strings[msgid] = []
                        
                        # Avoid duplicate locations for the same string
                        if location not in extracted_strings[msgid]:
                            extracted_strings[msgid].append(location)

        except Exception as e:
            print(f"--- ERROR: Could not process {filename}: {e}")

    if not extracted_strings:
        print("No translatable strings found. No .po file will be generated.")
        return

    print(f"\nFound {len(extracted_strings)} unique strings.")
    print(f"Generating {OUTPUT_PO_FILE}...")

    # Sort strings for consistent output
    sorted_msgids = sorted(extracted_strings.keys())

    try:
        with open(OUTPUT_PO_FILE, 'w', encoding='utf-8') as f:
            # Write PO file header
            now = datetime.now().strftime('%Y-%m-%d %H:%M%z')
            f.write('msgid ""\n')
            f.write('msgstr ""\n')
            f.write('"Project-Id-Version: Tunevia\\n"\n')
            f.write('"Report-Msgid-Bugs-To: \\n"\n')
            f.write(f'"POT-Creation-Date: {now}\\n"\n')
            f.write('"PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE\\n"\n')
            f.write('"Last-Translator: FULL NAME <EMAIL@ADDRESS>\\n"\n')
            f.write('"Language-Team: LANGUAGE <LL@li.org>\\n"\n')
            f.write('"MIME-Version: 1.0\\n"\n')
            f.write('"Content-Type: text/plain; charset=UTF-8\\n"\n')
            f.write('"Content-Transfer-Encoding: 8bit\\n"\n\n')

            # Write string entries
            for msgid in sorted_msgids:
                locations = extracted_strings[msgid]
                
                # Write location comments
                f.write(f"#: {' '.join(locations)}\n")
                
                # Write msgid (handling multiline strings)
                if '\n' in msgid:
                    f.write('msgid ""\n')
                    f.write(f'"{escape_po_string(msgid)}"\n')
                else:
                    f.write(f'msgid "{escape_po_string(msgid)}"\n')

                # Write empty msgstr
                f.write('msgstr ""\n\n')

        print(f"\nSuccessfully created {OUTPUT_PO_FILE}!")
        print("You can now use a tool like Poedit to create translations from this template.")

    except Exception as e:
        print(f"--- ERROR: Could not write to {OUTPUT_PO_FILE}: {e}")

if __name__ == "__main__":
    generate_po_file()