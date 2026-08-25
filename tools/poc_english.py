#!/usr/bin/env python3
"""
poc_english.py - render one line of English in-game, end to end

Proof of concept only. It repaints just the glyph cells this one line needs and
rewrites entry 23 message 0, Lin's opening line:

    Lin: Dick, is this the
    village where you live?
    It's so full of life!

The original is 36 units and so is the replacement, so the message keeps its
exact byte length: no offset table is rebuilt and no later message moves. That
isolates the thing being tested - can the engine draw Latin glyphs at all -
from the entry-resizing work, which is proven separately by script_edit.py.

Lines are hand-set to exactly 24 characters (12 cells of 2 letters) so each one
fills a row of the box and no word is broken across a line. A general
line-setter still has to be written; this sidesteps it for one message.

    python tools/poc_english.py out/
    python tools/dickdat.py pack out/ DICK.DAT.new

Writes out/0004.bin and out/0023.bin in place, after saving .orig copies.
Pass --revert to restore them.
"""
import json
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mkfont          # noqa: E402
import script_edit     # noqa: E402

FONT_ENTRY = "0004.bin"
SCRIPT_ENTRY = "0023.bin"
MSG = 0
LINES = ["Lin: Dick, is this the",
         "village where you live?",
         "It's so full of life!"]


def _check_pristine(spath):
    """Refuse to run against an entry that has already been edited.

    The usual cause is an out/ directory left over from an earlier experiment:
    script_edit.py push pads messages to 255 units, and glyphdump.py overwrites
    a message in place. Neither changes anything this tool would otherwise
    notice until the output is wrong in-game."""
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    xlsx = os.path.join(repo, "dialogue.xlsx")
    tag, msgs = script_edit.parse(open(spath, "rb").read())
    if not os.path.exists(xlsx):
        return tag, msgs
    ref = {}
    for row in script_edit._xlsx_rows(xlsx, "Dialogue"):
        try:
            if int(row.get("A", -1)) != 23:
                continue
            ref[int(row["B"])] = [int(h, 16) for h in row["I"].split()]
        except (ValueError, KeyError, TypeError):
            continue
    if not ref:
        return tag, msgs
    bad = [i for i, u in ref.items() if i < len(msgs) and msgs[i] != u]
    if not bad:
        return tag, msgs
    print("%s does not match dialogue.xlsx: %d of %d messages differ."
          % (os.path.basename(spath), len(bad), len(ref)))
    padded = [i for i in bad if len(msgs[i]) == 255]
    if padded:
        print("  %d of them are exactly 255 units - that is script_edit.py's"
              % len(padded))
        print("  push test, so this extraction came from a modified archive.")
    elif set(bad) & {0, 61, 62}:
        print("  Messages 0/61/62 are glyphdump.py's targets - the archive"
              " still carries a dump pass.")
    print()
    print("  Re-extract from a pristine DICK.DAT, and delete the stale copies")
    print("  so --revert cannot restore them:")
    print("      del %s\\*.orig" % outdir_hint(spath))
    print("      python tools/dickdat.py extract DICK.DAT %s"
          % outdir_hint(spath))
    sys.exit(1)


def outdir_hint(spath):
    return os.path.dirname(spath) or "out"


def build(outdir):
    fpath = os.path.join(outdir, FONT_ENTRY)
    spath = os.path.join(outdir, SCRIPT_ENTRY)
    for p in (fpath, spath):
        if not os.path.exists(p):
            sys.exit("missing %s - run: python tools/dickdat.py extract "
                     "DICK.DAT %s" % (p, outdir))

    _check_pristine(spath)
    # backups are taken only after validation, so a stale extraction can never
    # be captured as the thing --revert restores
    for p in (fpath, spath):
        if not os.path.exists(p + ".orig"):
            shutil.copy2(p, p + ".orig")

    text = "".join(L.ljust(24) for L in LINES)
    if len(text) % 2:
        sys.exit("line lengths must be even")
    pairs = [text[i:i + 2] for i in range(0, len(text), 2)]

    tag, msgs = script_edit.parse(open(spath, "rb").read())
    original = len(msgs[MSG])
    if len(pairs) != original:
        sys.exit("message %d is %d units but the English needs %d. Adjust "
                 "LINES, or use script_edit.py to change the length."
                 % (MSG, original, len(pairs)))

    glyphs = mkfont.latin_bitmaps()
    blob = bytearray(open(fpath, "rb").read())
    if len(blob) != 1 + 2048 * 64:
        sys.exit("%s is %d bytes; expected %d. Wrong entry?"
                 % (fpath, len(blob), 1 + 2048 * 64))
    slots = mkfont.free_slots(os.path.join(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))), "data", "free_slots.txt"))
    need = sorted(set(pairs))
    amap = {p: slots[i] for i, p in enumerate(need)}
    for p, s in amap.items():
        blob[1 + s * 64:1 + (s + 1) * 64] = \
            mkfont.encode_cell(mkfont.compose(glyphs, p[0], p[1]))
    open(fpath, "wb").write(bytes(blob))

    msgs[MSG] = [amap[p] for p in pairs]
    open(spath, "wb").write(script_edit.build(tag, msgs))

    print("repainted %d glyph cells (slots 0x%03x-0x%03x)"
          % (len(amap), min(amap.values()), max(amap.values())))
    print("rewrote entry 23 message 0: %d units, unchanged length"
          % len(pairs))
    print()
    for L in LINES:
        print("    " + L)
    print()
    print("Now: python tools/dickdat.py pack %s DICK.DAT.new" % outdir)
    print("Then load a save in Gulei Village and trigger the opening line.")


def revert(outdir):
    for name in (FONT_ENTRY, SCRIPT_ENTRY):
        p = os.path.join(outdir, name)
        if os.path.exists(p + ".orig"):
            shutil.copy2(p + ".orig", p)
            print("restored %s" % p)
        else:
            print("no backup for %s" % p)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    outdir = sys.argv[1]
    if "--revert" in sys.argv:
        revert(outdir)
    else:
        build(outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
