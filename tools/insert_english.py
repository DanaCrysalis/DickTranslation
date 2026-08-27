#!/usr/bin/env python3
"""
insert_english.py - set the translated dialogue into the game

This is the missing half of the pipeline. mkfont.py can paint Latin digraphs into
free glyph slots and script_edit.py can rewrite an entry whose messages changed
length, but nothing turned English prose into a unit list. This does, then drives
both.

    python tools/insert_english.py plan  dialogue.xlsx
    python tools/insert_english.py build dialogue.xlsx out/ out_en/

`plan` measures without writing anything: how many digraph cells the script needs,
how they are allocated, growth per entry, and every message that breaks a ceiling.
Run it first. `build` writes the patched entries and the font.

HOW TEXT IS SET
The box is 12 glyph cells per line and each cell holds two Latin letters, so a
line is 24 characters. Cells are packed greedily in pairs; a pair with no glyph
slot falls back to two single-letter cells, which is why allocation and layout
have to be solved together rather than one after the other (see ALLOCATION).

The engine wraps at 12 cells by itself - the retail script relies on it, which is
why its messages are not multiples of 12. But it wraps mid-cell, and mid-word
breaks look wrong in English, so this pads to the line end with 0x0066 whenever
the next word would straddle the boundary. That padding is the single largest
cost in the whole reinsertion, roughly a sixth of all units.

A newline in the spreadsheet is a HARD break, used where a new speaker starts. It
pads to the line end too. That matches what the retail script does with runs of
full-width spaces before a speaker change.

ALLOCATION
Pair frequencies depend on the layout and the layout depends on which pairs got
slots, so `plan` iterates: count pairs, allocate the most frequent, re-lay, count
again. Two passes are enough - the third changes nothing measurable. Single-letter
cells are reserved first for every character the script actually uses, because
they are the fallback and must always exist.

CEILINGS, in the order they bite
  255 units per message   the count is a u8. Cannot be worked around by padding
                          less; the text has to get shorter. Reported per message.
  65535 bytes per entry   the offset table is u16. Reported per entry.
  12 cells per line       layout only, not a hard limit.

TIGHT MODE
A message over the 255-unit ceiling is re-set with mid-word wrapping, which
recovers the padding. It is used only where it is needed, so the prose stays
word-safe everywhere else. If a message is still over after that, it is listed
and must be shortened - nothing here will silently truncate dialogue.

PRESERVED CELLS
`~~` in the English marks a cell the engine fills at draw time, two characters per
cell, matching uitext.py. Those become 0x0000 and are never packed with a
neighbour.
"""
import collections
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import script_edit  # noqa: E402

COLS = 12
SPACE = 0x0066
FILLED = 0x0000
MARK = "~~"


# ---------------------------------------------------------------- spreadsheet

def read_dialogue(xlsx):
    """-> {entry: {msg: english}}, skipping the over-read rows.

    The Notes column mixes the original over-read marker with annotations added
    later, so this filters on the marker TEXT. Filtering on "notes is non-empty"
    silently drops a good row.
    """
    out = collections.defaultdict(dict)
    for row in script_edit._xlsx_rows(xlsx, "Dialogue"):
        try:
            entry = int(row["A"])
            msg = int(row["B"])
        except (KeyError, ValueError, TypeError):
            continue
        if "over-read" in (row.get("K") or ""):
            continue
        eng = row.get("J")
        if eng:
            out[entry][msg] = eng
    return out


# -------------------------------------------------------------------- layout

def cells_of(text, alloc, tight=False):
    """English -> list of cell strings. '  ' is a blank cell, MARK is engine-filled."""
    cells = []
    col = 0

    def pad():
        nonlocal col
        while col % COLS:
            cells.append("  ")
            col += 1

    def pack(s):
        """Greedy pair packing with single-letter fallback."""
        out, i = [], 0
        while i < len(s):
            if s[i:i + 2] == MARK:
                out.append(MARK)
                i += 2
            elif i + 1 < len(s) and "~" not in s[i:i + 2] and (
                    s[i:i + 2] in alloc or s[i + 1] == " "):
                # "~" never pairs with anything but itself - a run of
                # engine-filled cells must start on a cell boundary
                # right half a space = the single-letter cell, which always
                # exists and consumes both characters
                out.append(s[i:i + 2])
                i += 2
            else:
                out.append(s[i] + " ")
                i += 1
        return out

    for pi, para in enumerate(text.split("\n")):
        if pi:
            pad()
        para = " ".join(para.split())
        if not para:
            continue
        if tight:
            for c in pack(para):
                cells.append(c)
                col += 1
            pad()
            continue
        line = ""
        for word in para.split(" "):
            trial = word if not line else line + " " + word
            if len(pack(trial)) + (col % COLS) > COLS and line:
                for c in pack(line):
                    cells.append(c)
                    col += 1
                pad()
                line = word
            else:
                line = trial
            while len(pack(line)) > COLS:      # a single word longer than a line
                head = line
                while len(pack(head)) > COLS:
                    head = head[:-1]
                for c in pack(head):
                    cells.append(c)
                    col += 1
                pad()
                line = line[len(head):]
        if line:
            for c in pack(line):
                cells.append(c)
                col += 1
            pad()
    return cells


class _All(object):
    """Sentinel for the first allocation pass.

    Seeding with an EMPTY set does not work: with no pairs available every cell
    falls back to a single letter, so no pair is ever counted, so none is ever
    allocated. The fixed point has to be approached from the other side - assume
    every pair is available, see which ones the layout actually asks for, then
    keep the most frequent.
    """

    def __contains__(self, _):
        return True


def allocate(script, slot_count, passes=2):
    """Choose which pairs get glyph slots. Layout and frequency are mutually
    dependent, so iterate."""
    singles = sorted({c for msgs in script.values() for t in msgs.values()
                      for c in t if c != "\n"})
    room = slot_count - len(singles)
    alloc = _All()
    for _ in range(passes):
        freq = collections.Counter()
        for msgs in script.values():
            for t in msgs.values():
                for c in cells_of(t, alloc):
                    if c not in ("  ", MARK) and len(c) == 2 and c[1] != " ":
                        freq[c] += 1
        alloc = {c for c, _ in freq.most_common(room)}
    return singles, alloc, freq


def encode(cells, cellmap):
    out = []
    for c in cells:
        if c == MARK:
            # In dialogue a ~~ cell is a NUMBER slot - the merchant's offer,
            # "I'll pay ~~~~~~ gold" - and FORMATS records that digits arrive in
            # 0x0066 while 0x0000 receives a name. Writing 0x0000 here put the
            # character 一 on screen instead of a price.
            out.append(SPACE)
        elif c == "  ":
            out.append(SPACE)
        else:
            out.append(cellmap[c])
    return out


# --------------------------------------------------------------------- report

def measure(script, alloc):
    rows = []
    for e in sorted(script):
        for m in sorted(script[e]):
            t = script[e][m]
            ws = cells_of(t, alloc)
            rec = {"entry": e, "msg": m, "units": len(ws), "tight": False}
            if len(ws) > script_edit.MAX_UNITS:
                tt = cells_of(t, alloc, tight=True)
                if len(tt) < len(ws):
                    rec = {"entry": e, "msg": m, "units": len(tt), "tight": True}
            rows.append(rec)
    return rows


def cmd_plan(xlsx):
    script = read_dialogue(xlsx)
    slot_count = _slot_count()
    singles, alloc, freq = allocate(script, slot_count)
    covered = sum(v for c, v in freq.items() if c in alloc)
    total = sum(freq.values()) or 1
    print("%d messages in %d entries" % (sum(len(v) for v in script.values()),
                                         len(script)))
    print("%d glyph slots free; %d reserved for single letters, %d for pairs"
          % (slot_count, len(singles), len(alloc)))
    print("pair coverage %.1f%% (the rest fall back to two single-letter cells)"
          % (100.0 * covered / total))
    rows = measure(script, alloc)
    per = collections.Counter()
    for r in rows:
        per[r["entry"]] += r["units"]
    print("\nentry   units   bytes   headroom   tight")
    for e in sorted(per):
        n = len(script[e])
        body = 1 + 2 * n + sum(1 + 2 * r["units"] for r in rows if r["entry"] == e)
        t = sum(1 for r in rows if r["entry"] == e and r["tight"])
        print("%5d  %6d  %6d  %9d  %6d" % (e, per[e], body, 0xFFFF - body, t))
    over = [r for r in rows if r["units"] > script_edit.MAX_UNITS]
    print("\ntotal %d units" % sum(per.values()))
    if over:
        print("\n%d MESSAGES EXCEED THE 255-UNIT CEILING and must be shortened:"
              % len(over))
        for r in sorted(over, key=lambda r: -r["units"]):
            print("   e%-4d m%-4d %3d units (%d over)"
                  % (r["entry"], r["msg"], r["units"],
                     r["units"] - script_edit.MAX_UNITS))
        print("\nNothing is truncated automatically. Shorten these in column J")
        print("and re-run; every other message is ready to build.")
    else:
        print("\nAll messages fit. Ready to build.")
    return over


def _slot_count():
    import mkfont
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return len(mkfont.free_slots(os.path.join(here, "data", "free_slots.txt")))


# ---------------------------------------------------------------------- build

def cmd_build(xlsx, srcdir, outdir):
    import mkfont
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = read_dialogue(xlsx)
    slots = mkfont.free_slots(os.path.join(here, "data", "free_slots.txt"))
    singles, alloc, _ = allocate(script, len(slots))
    rows = measure(script, alloc)
    over = [r for r in rows if r["units"] > script_edit.MAX_UNITS]
    if over:
        print("REFUSING TO BUILD: %d messages exceed the 255-unit ceiling." % len(over))
        print("Run `plan` for the list. Shortening them is an editorial job, and")
        print("truncating dialogue silently is worse than not patching at all.")
        return 1
    os.makedirs(outdir, exist_ok=True)

    plan = [c + " " for c in singles if c != " "] + sorted(alloc)
    cellmap = {}
    glyphs = mkfont.latin_bitmaps()
    fontsrc = os.path.join(srcdir, "0004.bin")
    blob = bytearray(open(fontsrc, "rb").read())
    for cell, slot in zip(plan, slots):
        cellmap[cell] = slot
        blob[mkfont.TAG + slot * mkfont.CELL:
             mkfont.TAG + (slot + 1) * mkfont.CELL] = \
            mkfont.encode_cell(mkfont.compose(glyphs, cell[0], cell[1]))
    for c in singles:
        cellmap.setdefault(c + " ", cellmap.get(c + " "))
    open(os.path.join(outdir, "0004.bin"), "wb").write(bytes(blob))
    json.dump({"cell": "2 letters per 16x16 glyph, left half then right half",
               "pairs": cellmap},
              open(os.path.join(here, "data", "digraphs.json"), "w",
                   encoding="utf-8"), ensure_ascii=False, indent=1)
    print("font: %d cells painted, %d slots spare"
          % (len(cellmap), len(slots) - len(cellmap)))

    tight = {(r["entry"], r["msg"]) for r in rows if r["tight"]}
    for e in sorted(script):
        src = os.path.join(srcdir, "%04d.bin" % e)
        tag, msgs = script_edit.parse(open(src, "rb").read())
        before = len(open(src, "rb").read())
        n = 0
        for m, text in script[e].items():
            if m >= len(msgs):
                print("  e%d: message %d is not in the entry, skipped" % (e, m))
                continue
            msgs[m] = encode(cells_of(text, alloc, (e, m) in tight), cellmap)
            n += 1
        blob = script_edit.build(tag, msgs)
        open(os.path.join(outdir, "%04d.bin" % e), "wb").write(blob)
        print("  entry %-4d %4d messages set, %6d -> %6d bytes (headroom %d)"
              % (e, n, before, len(blob), 0xFFFF - (len(blob) - 1)))

    for name in sorted(os.listdir(srcdir)):
        if name.endswith(".bin") and not os.path.exists(os.path.join(outdir, name)):
            data = open(os.path.join(srcdir, name), "rb").read()
            open(os.path.join(outdir, name), "wb").write(data)
    print("\nwrote %s (unchanged entries copied through)" % outdir)
    print("next: python tools/dickdat.py pack %s DICK.DAT.new" % outdir)
    print("NOTE: entries have moved. patch_poc.py and glyphdump.py hold hardcoded")
    print("absolute offsets and must be re-derived from the new TOC before use.")
    return 0


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    if sys.argv[1] == "plan":
        cmd_plan(sys.argv[2])
        return 0
    if sys.argv[1] == "build" and len(sys.argv) >= 5:
        return cmd_build(sys.argv[2], sys.argv[3], sys.argv[4])
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
