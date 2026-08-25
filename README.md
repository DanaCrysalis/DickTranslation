# 英雄戰記：德亞斯的邪念 — translation toolkit

Reverse-engineering notes and tools for **Hero War Chronicle: The Evil Thought of Dias**
(新科技軸心 / 富國科技, 1997), a Taiwanese DOS RPG.

The game ships its text as indices into a private glyph table rather than as Big5,
which is why ordinary text-extraction tools find nothing in its 87 MB archive. This
repository documents the formats, provides tools to extract and reinsert the script,
and contains the recovered index-to-character map.

**Status: research complete.** 1,064 dialogue messages (~39,500 characters) can be
dumped and patched back, at **changed lengths** — the offset table can be rebuilt and
the archive repacked, verified in-game. The character map is 98% complete by text
volume. The glyph font has been located and decoded, so glyphs can be read directly
and repainted. Nothing about an English patch is blocked on format work any more.

---

## Quick start

You need your own copy of the game. `DICK.DAT` should be 89,131,843 bytes.

```bash
# what's in the archive
python tools/dickdat.py list DICK.DAT

# pull every asset out as a separate file
python tools/dickdat.py extract DICK.DAT out/

# dump the dialogue, decoded with the character map
python tools/dickdat.py text DICK.DAT script/ data/charmap.json

# render the font (entry 4) so glyphs can be read or edited
python tools/font.py dump out/0004.bin sheet.png
```

`script/_index.txt` lists which entries hold dialogue and how many messages each has.

To prove reinsertion works on your own copy, `tools/patch_poc.py DICK.DAT` rewrites
the game's first spoken line and `--revert` puts it back.

To edit messages at a *different* length — which any translation requires — use
`tools/script_edit.py`, which rebuilds the entry's offset table. Always run its
`verify` first: it cross-checks the parsed entry against `dialogue.xlsx` and catches
both a misparse and an archive left dirty by a `glyphdump` pass.

---

## What was found

### The archive

`DICK.DAT` is a flat archive with a table of contents at the front:

| offset | size | meaning |
|---|---|---|
| `0x0000` | 2 | entry count (1146) |
| `0x0002` | n×8 | `u32 offset`, `u32 size` per entry, ascending |
| `0x20002` | … | entry data (the TOC region is padded to 128 KB) |

Entry numbers are **1-based in the game's own code** and 0-based in these tools, so
game entry 1099 is `out/1098.bin`. The loader seeks to `(N-1)*8 + 2`, reads the
offset and size, then reads the data — confirmed by disassembling it, not just
inferred from the bytes.

**The container applies no compression.** The loader consumes a single leading type
byte and copies the remainder verbatim to a fixed flat address. Individual *assets*
may still be encoded — picture entries use a skip/run codec internally (see
FORMATS.md) — but nothing is packed at the archive level.

### How text is stored

Text is **16-bit little-endian indices into a glyph table**, not Big5. A script
entry looks like:

```
u8          type tag (consumed by the loader)
u16 × n     message offsets, ascending, memory-relative (file offset = ptr + 1)
per message:
  u8        unit count
  u16 × n   units
```

Units are glyph indices mixed with control codes. `0x0066` is the full-width space,
used to pad messages. The engine word-wraps at draw time at 12 characters per line,
three lines per box, so messages contain no line breaks.

### The font

**Archive entry 4**, loaded raw to flat address `0x100000`. 2048 slots of 64 bytes:
16×16 pixels at **2 bits per pixel**, four pixels per byte, most significant pair
first. Glyph *N* is at `base + N*64`.

The two-bit value is a palette **role**, not a colour: `0` transparent, `1` light
face, `2` bevel. Role `3` is unused across the whole retail font. The bevelled look
is baked into the glyph data — the renderer draws the glyph three times, recolouring
those roles per pass, rather than shifting one bitmap.

This was read out of the renderer in overlay 13, not guessed, and verified by
decoding all 2048 slots and matching them against 496 glyphs independently recovered
from screenshots: **496 of 496 exact, to the pixel**.

### Why indices instead of Big5

Not a space saving — an index is two bytes and so is a Big5 code. The saving is in
the **font**: a full Big5 face is ~13,000 glyphs, this game needs about 1,700. It
also lets the game run on plain English DOS with no Chinese system (倚天 etc.)
installed, and `base + index × 64` is a shift and an add on a 386.

Glyph slots were allocated **in order of first use while the script was written**.
That's why 狄/克 are `0x5d`/`0x5e` and 知/道 are `0x62`/`0x63` — pairs typed together
got consecutive slots. Frequent characters cluster low: 的 at `0x11`, punctuation
，。：！？ at `0x16`–`0x1a`.

Allocation was not deduplicated: some characters own **two** slots. `0x353` and
`0x524` are both 越 and both used in overlapping chapters. Treat a duplicate as
evidence to check, not proof of error.

### Where things live

- **Dialogue**: entries 23, 249, 390, 625, 794 — one block per chapter.
- **Font**: entry 4.
- **Code**: ~90 overlay entries, each a copy of the same engine with per-scene data.
- **UI artwork**: entry 21, 24 skip/run images, loaded by 81 of 90 overlays.
- **Icons and portraits**: entry 1098, 16×16 8bpp cells, item icons at `0x4E20` and
  portrait faces at `0xA108`.
- **Saves**: `HDD-DATA.1` / `.2`, five slots of `0x10040` bytes, an 11-byte validity
  signature at the head of each.
- **Audio**: `DATA` is a Gravis Ultrasound patch bank (`GF1PATCH110`).

### Not found

- **Menu, item and spell name tables.** They use the same glyph indices but are not
  length-prefixed message blocks, so the script parser skips them. The character map
  now covers their vocabulary (裝備, 咒文, 狀態, 鐵劍, 匕首 …), which should make
  them findable by searching for known index sequences.
- **How script entries are loaded.** `loadmap.txt` records no overlay loading entries
  23/249/390/625/794, so dialogue reaches memory by a path `cmd_loadmap` doesn't
  trace. Not blocking anything, but the resource map is incomplete.

---

## Repository layout

```
tools/
  dickdat.py      archive: list, extract, pack, find, render, loadmap, text, script, learn
  font.py         font: dump, export, import, free  (entry 4)
  glyphdump.py    display a chosen glyph range in-game so it can be read
  patch_poc.py    minimal proof that message reinsertion works
data/
  charmap.json    1,603 verified index → character mappings
  unmapped.txt    indices the script uses that are not yet identified
  free_slots.txt  slots the script never references — repaintable for Latin
  loadmap.txt     which archive entries each code overlay loads, and where
docs/
  FORMATS.md      byte-level format reference
  CONTINUING.md   how to extend and verify the character map
  STATUS.md       what is done, what is not, and known weaknesses
```

Game data is **not** committed — see `.gitignore`. Extract it from your own copy.

---

## Method note

The character map was first built by using the game as its own renderer:
`glyphdump.py` writes a run of consecutive indices into a message, the game draws
them, and the screenshot is read back. That is no longer necessary — with the font
decoded, `font.py` renders any slot directly.

Readings are verified by **decoding the script and checking it reads as Chinese**.
This is the only check that catches a wrong reading of a character that collides with
nothing, and it found 46 such errors in a single pass. Duplicate and mismatch
detection remain useful but are secondary, and duplicates now carry false positives
because the font itself contains duplicate characters.

Note that a glyph's **bitmap** and its **character reading** are independent
artifacts. The map can be wrong about what a glyph means while the bitmap is exactly
right; that distinction is what let the font search be validated against screenshot
data whose character labels were still being corrected.

## Credits and legal

Game © 1997 新科技軸心 / 富國科技 / 大嘉出版. This repository contains no game
assets — only format documentation and tools. The copy protection is documented at
[chiuinan.github.io](https://chiuinan.github.io/), which also notes the game needs
PCem or a similarly accurate emulator; it switches to protected mode itself with
`lgdt`/`mov cr0` rather than using DPMI, which DOSBox handles poorly.
