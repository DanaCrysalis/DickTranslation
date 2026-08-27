#!/usr/bin/env python3
"""
names.py - item, spell and monster names in archive entry 1098

CORRECTED LAYOUT (2026-08-26). The previous constants (name 8 units at +0x42,
description 14 units at +0x52) were wrong and produced the three-character
truncation seen in dialogue.xlsx. Relative to the record bases this tool uses
(FIRST = 0x145, STRIDE = 0x50) the real fields are:

    +0x4C   name field,        5 units, padded with 0x0066
    +0x56   3 units, ALWAYS 0x0066 in all 245 slots - a fixed gap, not text
    +0x5C   description field, 12 units, padded with 0x0066
    +0x74   4 units, ALWAYS 0x0066 - a fixed gap
    +0x7C   binary stats, 16 units (32 bytes), to the next record's name

The old constants read the last three units of the name as an 8-unit window
starting five units early, which is why every long name lost its tail into the
description column (賢者之|杖受諸神保護的大賢者) and why spell rows picked up
stat bytes as leading junk (功迅風咒, 藍書[2c1f]裝夢之咒).

Budget: a name is 5 cells = 10 Latin characters, a description 12 cells = 24.
NOT the 16 / 28 the old docstring claimed.

0x0000 IS THE CHARACTER 一, never padding. Both fields pad with 0x0066 - the
layout probe finds zero 0x0000 in any of the five name columns. A 0x0000 in
either field decodes as 一, or descriptions read wrong: 一人速度上升 became
"人速度上升" while the old constants were in force.

    python tools/names.py layout 1098.bin      # empirical field probe
    python tools/names.py dump 1098.bin
    python tools/names.py dump 1098.bin --json names.json
    python tools/names.py patch 1098.bin 0004.bin names.json out.bin out.font.bin

The JSON is a list of {offset, kind, chinese, english_name, english_desc}.
Fill in the English fields and patch; blank fields are left untouched. Records
are written in place, so entry 1098 never changes size.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STRIDE = 0x50
NAME_OFF, NAME_UNITS = 0x4C, 5
DESC_OFF, DESC_UNITS = 0x5C, 12
FIRST = 0x145           # first record base
END = 0xEE49            # end of entry 1098

# The old constant was ICONS = 0x4E20, on the belief that the icon sheet began
# there and the tables ended. Entry 1098 CONTINUES past it, and two more tables
# live above: the special-attack and summon names at 0x07F21 (stride 0x2A,
# 5-unit name) and the plot items at 0x08F89 (stride 0x50, 5-unit name at +0x00,
# 12-unit description at +0x10). Scanning only to 0x4E20 is what produced the
# false conclusions that the table held 235 records and that the game did not
# name its monsters.
SKILLS_AT, SKILL_STRIDE = 0x07F21, 0x2A
PLOT_AT, PLOT_STRIDE = 0x08F89, 0x50
SPACE = 0x0066


def load_charmap():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cm = json.load(open(os.path.join(here, "data", "charmap.json"), encoding="utf-8"))
    return {int(k, 16): v for k, v in cm.items()}


def units(d, o, n):
    return [struct.unpack_from("<H", d, o + 2 * k)[0] for k in range(n)]


def text(u, cm):
    """Decode a field. The only pad is 0x0066; 0x0000 is the character 一."""
    out = []
    for v in u:
        if v == SPACE:
            continue
        out.append(cm.get(v, "[%03x]" % v))
    return "".join(out)


def records(d, cm):
    """Yield (offset, name, description) for every populated record."""
    o = FIRST
    while o + DESC_OFF + 2 * DESC_UNITS <= 0x4E20:
        nm = text(units(d, o + NAME_OFF, NAME_UNITS), cm)
        ds = text(units(d, o + DESC_OFF, DESC_UNITS), cm)
        if nm or ds:
            yield o, nm, ds
        o += STRIDE


def extra_tables(d, cm):
    """The two tables above 0x4E20 that the old scan limit hid."""
    for o in range(SKILLS_AT, 0x08F00, SKILL_STRIDE):
        nm = text(units(d, o, 5), cm)
        if nm:
            yield o, "skill", nm, ""
    for o in range(PLOT_AT, 0x0A100, PLOT_STRIDE):
        nm = text(units(d, o, 5), cm)
        ds = text(units(d, o + 0x10, 12), cm)
        if nm or ds:
            yield o, "plot", nm, ds


def classify(off, name, desc):
    """Rough section label for the main table only. Boundaries are positional,
    so this is advisory. Spells begin at 0x3E35, not the 0x4500 in older docs."""
    if off >= 0x3E35:
        return "spell"
    return "item"


def cmd_layout(path):
    """Empirical field probe: for every u16 column in the stride, how often is
    it a mapped glyph, 0x0000, 0x0066 or binary? Text fields stand out as runs
    of high glyph density with a ragged pad tail; stats do not."""
    cm = load_charmap()
    d = open(path, "rb").read()
    cols = STRIDE // 2
    bases = list(range(FIRST, ICONS - STRIDE, STRIDE))
    print("col  off   glyph  zero  space  other   sample")
    for c in range(cols):
        g = z = s = o = 0
        sample = []
        for b in bases:
            v = struct.unpack_from("<H", d, b + 2 * c)[0]
            if v == 0:
                z += 1
            elif v == SPACE:
                s += 1
            elif v in cm:
                g += 1
                if len(sample) < 8:
                    sample.append(cm[v])
            else:
                o += 1
        print("%3d  +%02X   %5d %5d  %5d  %5d   %s"
              % (c, 2 * c, g, z, s, o, "".join(sample)))
    print("\n%d record slots probed. Expect the name field at +%02X (%d units) "
          "and the description at +%02X (%d units)."
          % (len(bases), NAME_OFF, NAME_UNITS, DESC_OFF, DESC_UNITS))


def cmd_dump(path, jsonout=None):
    cm = load_charmap()
    d = open(path, "rb").read()
    rows = []
    allrows = [(o, classify(o, n, s), n, s) for o, n, s in records(d, cm)]
    allrows += [(o, k, n, s) for o, k, n, s in extra_tables(d, cm)]
    for off, kind, nm, ds in allrows:
        rows.append({"offset": "0x%05X" % off, "kind": kind,
                     "chinese": nm, "chinese_desc": ds,
                     "english_name": "", "english_desc": ""})
        print("0x%05X  %-6s %-10s  %s" % (off, kind, nm, ds))
    print("\n%d records (name <=%d chars, description <=%d)"
          % (len(rows), NAME_UNITS * 2, DESC_UNITS * 2))
    if jsonout:
        json.dump(rows, open(jsonout, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("wrote %s" % jsonout)


def cmd_patch(src, fontsrc, jsonin, out, fontout):
    import mkfont
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
    if sys.argv[1] == "layout":
        cmd_layout(sys.argv[2])
    elif sys.argv[1] == "dump":
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
