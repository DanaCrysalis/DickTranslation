# 英雄戰記：德亞斯的邪念 — translation toolkit

Reverse-engineering notes and tools for **Hero War Chronicle: The Evil Thought of Dias**
(新科技軸心 / 富國科技, 1997), a Taiwanese DOS RPG.

The game ships its text as indices into a private glyph table rather than as Big5,
which is why ordinary text-extraction tools find nothing in its 87 MB archive. This
repository documents the formats, provides tools to extract and reinsert the script,
and contains the recovered index-to-character map.

**Status: the script is fully extractable and reinsertable.** 1,064 dialogue
messages (~39,500 characters) can be dumped and patched back. The character map is
96% complete by text volume.

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
```

`script/_index.txt` lists which entries hold dialogue and how many messages each has.

To prove reinsertion works on your own copy, `tools/patch_poc.py DICK.DAT` rewrites
the game's first spoken line and `--revert` puts it back.

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

**Nothing in the archive is compressed.** The loader optionally consumes a single
leading type byte and copies the remainder verbatim. Assets are raw.

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

Glyphs are 16×16, drawn three times at one-pixel offsets (black, mid-grey, light
face) to produce the bevelled look.

### Why indices instead of Big5

Not a space saving — an index is two bytes and so is a Big5 code. The saving is in
the **font**: a full Big5 face is ~13,000 glyphs, this game needs about 1,700. It
also lets the game run on plain English DOS with no Chinese system (倚天 etc.)
installed, and `base + index × cell` is a shift and an add on a 386.

Glyph slots were allocated **in order of first use while the script was written**.
That's why 狄/克 are `0x5d`/`0x5e` and 知/道 are `0x62`/`0x63` — pairs typed together
got consecutive slots. Frequent characters cluster low: 的 at `0x11`, punctuation
，。：！？ at `0x16`–`0x1a`.

### Where things live

- **Dialogue**: entries 23, 249, 390, 625, 794 — one block per chapter, matching the
  overlay groupings in `data/loadmap.txt`.
- **Code**: ~90 overlay entries, each a copy of the same engine with per-scene data.
- **Icons and portraits**: entry 1098, 16×16 8bpp cells, item icons at `0x4E20` and
  portrait faces at `0xA108`.
- **Saves**: `HDD-DATA.1` / `.2`, five slots of `0x10040` bytes, an 11-byte validity
  signature at the head of each.
- **Audio**: `DATA` is a Gravis Ultrasound patch bank (`GF1PATCH110`).

### Not found

- **The font bitmaps.** Searched at 1, 2, 4 and 8 bits per pixel across every
  plausible row pitch, against a pixel-exact glyph taken from a screenshot. No match.
  It is almost certainly RLE-encoded per glyph and expanded during the blit.
  Recovering it means disassembling the blitter's inner loop.
- **Menu, item and spell name tables.** They use the same glyph indices but are not
  length-prefixed message blocks, so the script parser skips them. The character map
  now covers their vocabulary (裝備, 咒文, 狀態, 鐵劍, 匕首 …), which should make
  them findable by searching for known index sequences.

---

## Repository layout

```
tools/
  dickdat.py      archive: list, extract, pack, find, render, loadmap, text, script, learn
  glyphdump.py    display a chosen glyph range in-game so it can be read
  patch_poc.py    minimal proof that message reinsertion works
data/
  charmap.json    1,120 verified index → character mappings
  unmapped.txt    482 indices the script uses that are not yet identified
  free_slots.txt  94 known slots the script never uses — repaintable for Latin
  loadmap.txt     which archive entries each code overlay loads, and where
docs/
  FORMATS.md      byte-level format reference
  CONTINUING.md   how to extend the character map
  STATUS.md       what is done, what is not, and known weaknesses
```

Game data is **not** committed — see `.gitignore`. Extract it from your own copy.

---

## Method note

The character map was not recovered by finding the font. It was recovered by using
the game as its own renderer: `glyphdump.py` writes a run of consecutive indices into
a message, the game draws them, and the screenshot is read back. Each pass recovers
81 glyphs. Every pass overlaps known indices, so misalignment is detectable, and
mapping two indices to the same character raises a duplicate that flags a misreading.

That check is not exhaustive: a wrong reading of a character not otherwise used stays
invisible. Several errors were caught this way (萊→禁, 兒→兇, 野→夥, 蠻癟→繼續) but
a residue probably remains among rare glyphs. Treat the map as reliable for common
characters and provisional in the tail.

## Credits and legal

Game © 1997 新科技軸心 / 富國科技 / 大嘉出版. This repository contains no game
assets — only format documentation and tools. The copy protection is documented at
[chiuinan.github.io](https://chiuinan.github.io/), which also notes the game needs
PCem or a similarly accurate emulator; it switches to protected mode itself with
`lgdt`/`mov cr0` rather than using DPMI, which DOSBox handles poorly.
