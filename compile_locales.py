import struct
import re
import os

def compile_po_to_mo(po_path, mo_path):
    with open(po_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    entries = {}
    current_msgid = None
    current_msgstr = None
    state = None

    def unescape(s):
        return s.encode('raw_unicode_escape').decode('unicode_escape')

    for line in lines:
        line_str = line.strip()
        if not line_str or line_str.startswith('#'):
            continue
        if line_str.startswith('msgid '):
            if current_msgid is not None and current_msgstr is not None:
                entries[current_msgid] = current_msgstr
            m = re.match(r'^msgid\s+"(.*)"$', line_str)
            current_msgid = unescape(m.group(1)) if m else ""
            current_msgstr = None
            state = 'msgid'
        elif line_str.startswith('msgstr '):
            m = re.match(r'^msgstr\s+"(.*)"$', line_str)
            current_msgstr = unescape(m.group(1)) if m else ""
            state = 'msgstr'
        elif line_str.startswith('"') and line_str.endswith('"'):
            content = unescape(line_str[1:-1])
            if state == 'msgid':
                current_msgid += content
            elif state == 'msgstr':
                current_msgstr += content

    if current_msgid is not None and current_msgstr is not None:
        entries[current_msgid] = current_msgstr

    items = sorted(entries.items(), key=lambda x: x[0].encode('utf-8'))
    keys = [k.encode('utf-8') for k, v in items]
    vals = [v.encode('utf-8') for k, v in items]
    num_strings = len(items)

    keystart = 28 + 2 * 8 * num_strings
    valstart = keystart + sum(len(k) + 1 for k in keys)

    koffsets = []
    curr = keystart
    for k in keys:
        koffsets.append((len(k), curr))
        curr += len(k) + 1

    voffsets = []
    curr = valstart
    for v in vals:
        voffsets.append((len(v), curr))
        curr += len(v) + 1

    out = bytearray()
    out.extend(struct.pack('Iiiiiii', 0x950412de, 0, num_strings, 28, 28 + 8 * num_strings, 0, 0))
    for l, off in koffsets:
        out.extend(struct.pack('ii', l, off))
    for l, off in voffsets:
        out.extend(struct.pack('ii', l, off))
    for k in keys:
        out.extend(k + b'\x00')
    for v in vals:
        out.extend(v + b'\x00')

    with open(mo_path, 'wb') as f:
        f.write(out)
    print(f"Successfully compiled {num_strings} translations from {po_path} to {mo_path}")

if __name__ == '__main__':
    po_file = os.path.join('locales', 'id', 'LC_MESSAGES', 'messages.po')
    mo_file = os.path.join('locales', 'id', 'LC_MESSAGES', 'messages.mo')
    if os.path.exists(po_file):
        compile_po_to_mo(po_file, mo_file)
