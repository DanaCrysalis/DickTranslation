# Byte-level format reference

All offsets are hexadecimal. Multi-byte values are little-endian.

## DICK.DAT — the archive

```
0x00000  u16       entry count (1146 in the retail file)
0x00002  u32,u32   per entry: absolute file offset, size in bytes
                   ascending; entries are contiguous apart from three
                   small padding gaps
0x20002  ...       entry data begins (TOC region padded to 128 KB)
```

The last entry ends at exactly 89,131,843 — the retail file size. Use that as a
sanity check when parsing.

Game code uses **1-based** entry numbers: the loader computes `(N-1)*8 + 2`. Tools
in this repository use 0-based numbering throughout.

### Loading

Confirmed by disassembly of the loader (overlay entry 181, offset `0xFD15`):

1. open `DICK.DAT`
2. seek `(N-1)*8 + 2`, read 8 bytes → offset, size
3. seek offset
4. if a flag is set, read and discard one type byte and decrement size
5. read the remainder into a staging segment in 64 KB chunks
6. `rep movsd` the staging buffer to a fixed flat address

No decompression occurs at any step.

## Script entries

Entries 23, 249, 390, 625 and 794 hold dialogue.

```
+0x0000  u8        type tag (consumed by the loader)
+0x0001  u16 × n   message offsets, ascending
                   these are MEMORY offsets; file offset = ptr + 1
                   the table ends where the first message begins

per message, at (ptr + 1):
  u8              unit count
  u16 × count     units
```

The table's length is not stored; read u16s while they ascend and stay below the
first pointer.

### Units

A unit is either a glyph index or a control code, in one numeric space.

| value | meaning |
|---|---|
| `0x0066` | full-width space (pads message tails, centres short names) |
| others | glyph index into the font table |

Indices observed in the script run from `0x0000` to `0x069b`. The font itself is
larger; slots above the script's range exist but are never referenced.

The renderer word-wraps at **12 units per line, 3 lines per box**. Messages contain
no explicit line or box breaks — an 84-unit message renders as three boxes.

## Rendering

Glyphs are 16×16. The engine draws each one three times at one-pixel offsets —
black, mid-grey, then the light face — producing the bevelled outline. Colour 0 is
transparent. Screen pitch is 320; the dialogue box uses a 19-pixel advance per glyph.

The stored glyph format is **not** a plain bitmap. Searches at 1, 2, 4 and 8 bits per
pixel across row pitches 12–32, matched against a pixel-exact glyph lifted from a
screenshot, all fail. It is most likely RLE-encoded per glyph.

## Character-name table (in RAM)

Three units per entry, centre-padded with `0x0066`:

```
005d 0066 005e   狄 · 克
0066 000f 0066   · 琳 ·
```

## Save files

`HDD-DATA.1` and `HDD-DATA.2`, five records of `0x10040` bytes each. Each record
begins with an 11-byte validity signature; if it doesn't match, the slot is empty and
the menu draws a fixed 64×24 "新冒險" graphic instead of slot text.

## Other entries

| content | where |
|---|---|
| item icons | entry 1098, offset `0x4E20`, 16×16 8bpp, 256 bytes per cell |
| portrait faces | entry 1098, offset `0xA108`, same cell format |
| GUS patch bank | entry 0, and the loose `DATA` file (`GF1PATCH110`) |
| code overlays | ~90 entries, prologue `1E 06 66 50 66 53 66 51 66 52 66 56 66 57 66 55` |

Overlays are copies of one engine with per-scene data; two overlays differ in about
12 KB of scattered data plus a size shift.
