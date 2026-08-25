#!/usr/bin/env python3
"""
mkfont.py - build a Latin digraph font into the game's free glyph slots

The dialogue box is 12 glyphs per line at a 19-pixel advance. English needs
roughly 3x the characters of the Chinese it replaces, so one Latin letter per
16x16 cell does not fit. This packs TWO 8x16 letters into each cell, which costs
about 1.5 cells per original cell and needs no engine changes at all.

    python tools/mkfont.py preview                       letterforms + sample line
    python tools/mkfont.py build 0004.bin 0004.new.bin --text english.txt
    python tools/mkfont.py build 0004.bin 0004.new.bin   (built-in frequencies)

`build` writes a new font entry and a JSON map from character pair -> glyph slot,
which the line-setter needs in order to encode text. Slots not used are left
byte-identical, so the Chinese font is untouched wherever it is still needed.

WHICH SLOTS
Allocation comes from data/free_slots.txt: 351 blank slots at 0x6A1-0x7FF plus
188 drawn-but-unreferenced ones. 0x066 (full-width space) and 0x593 (script
referenced) are excluded even though they are blank.

WHICH PAIRS
Digraph inventory depends on the translated text, which is why --text is the
right way to run this. Measured on real English prose, the 400 most frequent
pairs cover 99.1% of pair slots, so the ~539 available slots are ample: rare
pairs fall back to a single-letter cell (one letter, blank right half), which
wastes a cell but never fails.

PIXEL ROLES
Glyph data is 2 bits per pixel and the value is a palette role, not a colour:
0 transparent, 1 light face, 2 bevel. Letters are drawn entirely in role 1; the
engine's own shadow pass supplies depth, so they sit consistently against the
Chinese glyphs without hand-editing.

THE 19-PIXEL ADVANCE
With the retail advance, a 16-pixel cell leaves a 3-pixel gap, so letters clump
into visible pairs ("Dick: This vil lage"). Patching the advance to 16 makes
spacing even. It is one byte, `add dword [0x26ec], 0x13` -> `0x10`, at three
sites in each code overlay (0x6AD7, 0x6FCE, 0x703B in overlay 13; the third
byte of each is the 0x13). This is cosmetic - the font works either way - and it
must be applied to every overlay copy, so treat it as optional polish.
"""
import json
import os
import sys

CELL = 64
SLOTS = 2048
TAG = 1
CHARS = "".join(chr(c) for c in range(32, 127))

# Most frequent English letter pairs at even offsets in running text, used when
# no --text is supplied. Derived from prose; a real script should override it.
FALLBACK_PAIRS = (
    "e t s a n i o r l d h c u m g p f w y b v k I T A S W H E N O R D L C M B P"
    " th he in er an re on at en nd ti es or te of ed is it al ar st to nt ng se"
    " ha as ou io le ve co me de hi ri ro ic ne ea ra ce li ch ll be ma si om ur"
).split()


def latin_bitmaps(ttf=None, size=12):
    """Trace an 8x16 face from a monospace TTF, baseline-aligned."""
    from PIL import Image, ImageFont, ImageDraw
    import numpy as np
    ttf = ttf or "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
    f = ImageFont.truetype(ttf, size)
    BASE, CELL_BASE = 20, 12
    out = {}
    for ch in CHARS:
        im = Image.new("L", (24, 32), 0)
        ImageDraw.Draw(im).text((6, BASE), ch, font=f, fill=255, anchor="ls")
        a = np.array(im) > 120
        cell = np.zeros((16, 8), dtype=np.uint8)
        xs = np.nonzero(a.any(0))[0]
        if len(xs):
            x0 = xs.min()
            x1 = min(xs.max() + 1, x0 + 7)
            win = a[BASE - CELL_BASE:BASE - CELL_BASE + 16, x0:x1]
            cell[:win.shape[0], :win.shape[1]] = win
        out[ch] = cell
    return out


def encode_cell(px):
    """16x16 of 0/1/2 -> 64 bytes, 4 pixels per byte, MSB pair first."""
    flat = [int(px[y][x]) & 3 for y in range(16) for x in range(16)]
    b = bytearray()
    for i in range(0, 256, 4):
        v = 0
        for k in range(4):
            v |= flat[i + k] << (6 - 2 * k)
        b.append(v)
    return bytes(b)


def compose(glyphs, a, b):
    import numpy as np
    c = np.zeros((16, 16), dtype=np.uint8)
    c[:, 0:8] = glyphs.get(a, glyphs[" "])
    c[:, 8:16] = glyphs.get(b, glyphs[" "])
    return c


def free_slots(path="data/free_slots.txt"):
    """Blank range plus the drawn-but-unreferenced slots listed in the file."""
    blank = list(range(0x6A1, 0x800))
    drawn = []
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            if line.startswith("0x"):
                drawn.append(int(line.split()[0], 16))
    # blank slots first: repainting those destroys nothing
    return blank + [s for s in drawn if s not in (0x066, 0x593)]


def pairs_from_text(path):
    import collections
    txt = open(path, encoding="utf-8", errors="replace").read()
    txt = " ".join(txt.split())
    c = collections.Counter(txt[i:i + 2] for i in range(0, len(txt) - 1, 2))
    return [p for p, _ in c.most_common()]


def cmd_preview(ttf=None):
    from PIL import Image
    import numpy as np
    g = latin_bitmaps(ttf)
    rows = []
    for line in ("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz",
                 "0123456789 .,:;!?'\"-()"):
        img = np.zeros((16, 8 * len(line)), dtype=np.uint8)
        for i, ch in enumerate(line):
            img[:, i * 8:(i + 1) * 8] = g[ch]
        rows.append(img)
    w = max(r.shape[1] for r in rows)
    sheet = np.zeros((sum(r.shape[0] + 3 for r in rows), w), dtype=np.uint8)
    y = 0
    for r in rows:
        sheet[y:y + 16, :r.shape[1]] = r
        y += 19
    im = Image.fromarray((sheet * 235 + 22).astype("uint8"))
    im = im.resize((im.width * 3, im.height * 3), Image.NEAREST)
    im.save("font_preview.png")
    print("wrote font_preview.png")


def cmd_build(src, out, textfile=None, mapfile="data/digraphs.json", ttf=None):
    g = latin_bitmaps(ttf)
    blob = bytearray(open(src, "rb").read())
    if len(blob) != TAG + SLOTS * CELL:
        sys.exit("expected %d bytes, got %d - is that entry 4?"
                 % (TAG + SLOTS * CELL, len(blob)))
    want = pairs_from_text(textfile) if textfile else FALLBACK_PAIRS
    slots = free_slots()
    singles = [c for c in CHARS if c != " "]
    # single-letter cells first: they are the fallback and must always exist
    plan = [(c + " ") for c in singles]
    for p in want:
        if len(p) == 2 and p not in plan and all(c in CHARS for c in p):
            plan.append(p)
    if len(plan) > len(slots):
        print("note: %d cells wanted, %d slots free - keeping the %d most "
              "frequent" % (len(plan), len(slots), len(slots)))
        plan = plan[:len(slots)]
    mapping = {}
    for pair, slot in zip(plan, slots):
        blob[TAG + slot * CELL:TAG + (slot + 1) * CELL] = \
            encode_cell(compose(g, pair[0], pair[1]))
        mapping[pair] = slot
    open(out, "wb").write(bytes(blob))
    json.dump({"cell": "2 letters per 16x16 glyph, left half then right half",
               "pairs": mapping},
              open(mapfile, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_single = sum(1 for p in mapping if p.endswith(" "))
    print("wrote %s: %d slots repainted (%d single-letter, %d digraph)"
          % (out, len(mapping), n_single, len(mapping) - n_single))
    print("wrote %s" % mapfile)
    print("%d free slots remain" % (len(slots) - len(mapping)))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    c = sys.argv[1]
    if c == "preview":
        cmd_preview(sys.argv[2] if len(sys.argv) > 2 else None)
    elif c == "build":
        tf = None
        if "--text" in sys.argv:
            tf = sys.argv[sys.argv.index("--text") + 1]
        cmd_build(sys.argv[2], sys.argv[3], tf)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
