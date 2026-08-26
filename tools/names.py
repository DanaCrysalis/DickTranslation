#!/usr/bin/env python3
"""
names.py - item, spell and monster names in archive entry 1098

Entry 1098 is the game's data bank, not just the icon sheet documented in
FORMATS.md. Alongside the icons at 0x4E20 and the portraits at 0xA108 it holds
fixed-width name and description records:

    record stride   0x50 (80 bytes)
    +0x42           name field,        8 units, zero-padded
    +0x52           description field, 14 units, full-width-space padded
    remainder       binary stats

So a name may be up to 16 Latin characters and a description up to 28, at two
letters per glyph cell - much more generous than the menu tables, whose labels
are two or three cells.

    python tools/names.py dump 1098.bin
    python tools/names.py dump 1098.bin --json names.json
    python tools/names.py patch 1098.bin 0004.bin names.json out.bin out.font.bin

The JSON is a list of {offset, kind, chinese, english_name, english_desc}.
Fill in the English fields and patch; blank fields are left untouched. Records
are written in place, so entry 1098 never changes size.

Padding is preserved: a translated name keeps the same 8-unit field, so the
engine's column alignment is unaffected.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STRIDE = 0x50
NAME_OFF, NAME_UNITS = 0x42, 8
DESC_OFF, DESC_UNITS = 0x52, 14
FIRST = 0x145           # first record base
ICONS = 0x4E20          # tables end where the icon sheet begins


def load_charmap():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cm = json.load(open(os.path.join(here, "data", "charmap.json"), encoding="utf-8"))
    return {int(k, 16): v for k, v in cm.items()}


def units(d, o, n):
    return [struct.unpack_from("<H", d, o + 2 * k)[0] for k in range(n)]


def text(u, cm):
    return "".join("" if v in (0, 0x66) else cm.get(v, "[%03x]" % v) for v in u)


def records(d, cm):
    """Yield (offset, name, description) for every populated record."""
    o = FIRST
    while o + STRIDE <= ICONS:
        nm = text(units(d, o + NAME_OFF, NAME_UNITS), cm)
        ds = text(units(d, o + DESC_OFF, DESC_UNITS), cm)
        if nm or ds:
            yield o, nm, ds
        o += STRIDE


def classify(off, name, desc):
    """Rough section label. Boundaries are positional, so this is advisory."""
    if off >= 0x8000:
        return "monster"
    if off >= 0x4500:
        return "spell"
    return "item"


def cmd_dump(path, jsonout=None):
    cm = load_charmap()
    d = open(path, "rb").read()
    rows = []
    for off, nm, ds in records(d, cm):
        rows.append({"offset": "0x%05X" % off, "kind": classify(off, nm, ds),
                     "chinese": nm, "chinese_desc": ds,
                     "english_name": "", "english_desc": ""})
        print("0x%05X  %-8s %-16s  %s" % (off, classify(off, nm, ds), nm, ds))
    print("\n%d records (name <=16 chars, description <=28)" % len(rows))
    if jsonout:
        json.dump(rows, open(jsonout, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("wrote %s" % jsonout)


def cmd_patch(src, fontsrc, jsonin, out, fontout):
    import mkfont
    cm = load_charmap()
    d = bytearray(open(src, "rb").read())
    blob = bytearray(open(fontsrc, "rb").read())
    rows = json.load(open(jsonin, encoding="utf-8"))
    glyphs = mkfont.latin_bitmaps()
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    slots = mkfont.free_slots(os.path.join(here, "data", "free_slots.txt"))

    pairs = set()
    for r in rows:
        for key, w in (("english_name", NAME_UNITS), ("english_desc", DESC_UNITS)):
            s = (r.get(key) or "")
            if not s:
                continue
            s = s.ljust(w * 2)[:w * 2]
            for i in range(0, len(s), 2):
                pairs.add(s[i:i + 2])
    amap = {}
    for p in sorted(pairs):
        if not slots:
            sys.exit("ran out of free glyph slots (%d pairs needed)" % len(pairs))
        amap[p] = slots.pop(0)
    for p, slot in amap.items():
        blob[1 + slot * 64:1 + (slot + 1) * 64] = \
            mkfont.encode_cell(mkfont.compose(glyphs, p[0], p[1]))

    n = 0
    for r in rows:
        off = int(r["offset"], 16)
        for key, foff, w in (("english_name", NAME_OFF, NAME_UNITS),
                             ("english_desc", DESC_OFF, DESC_UNITS)):
            s = (r.get(key) or "")
            if not s:
                continue
            if len(s) > w * 2:
                print("  too long, skipped: %r (max %d)" % (s, w * 2))
                continue
            s = s.ljust(w * 2)
            for k in range(w):
                struct.pack_into("<H", d, off + foff + 2 * k, amap[s[2 * k:2 * k + 2]])
            n += 1
    open(out, "wb").write(bytes(d))
    open(fontout, "wb").write(bytes(blob))
    print("%d fields written, %d glyph cells repainted" % (n, len(amap)))
    print("wrote %s (%d bytes, unchanged) and %s" % (out, len(d), fontout))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    if sys.argv[1] == "dump":
        j = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
        cmd_dump(sys.argv[2], j)
    elif sys.argv[1] == "patch":
        cmd_patch(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
