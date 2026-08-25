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

No decompression occurs at any step. The byte-count figures in `loadmap.txt` are
**destination buffer sizes** requested by the calling code, not expanded sizes —
they routinely exceed the stored entry size and do not imply compression.

Assets may still be *encoded* internally: picture entries carry a skip/run stream
(below). That is decoded by the drawing code, not by the loader.

## The font — entry 4

Loaded raw to flat `0x100000`. After the leading type byte, 2048 fixed-size cells:

```
16 x 16 pixels, 2 bits per pixel
4 pixels per byte, most significant pair first (shifts 6, 4, 2, 0)
64 bytes per glyph
glyph N at  base + N*64
```

Read out of the renderer in overlay 13 at `0x6ECC`:

```
mov  ax, fs:[esi]        ; u16 glyph index from the script stream
shl  eax, 6              ; x 64
mov  esi, 0x100000       ; font base
add  esi, eax            ; src = base + index*64
lea  edi, [0x423c]       ; 256-byte staging buffer, one byte per pixel
mov  cx, 0x40            ; 64 source bytes
  mov cl, 4              ; 4 pixels per byte
  mov dl, 6              ; shift 6, 4, 2, 0
    mov al, fs:[esi]
    shr al, cl
    and al, 3            ; 2 bits per pixel
```

### Pixel roles

The two-bit value is a palette role, expanded into the staging buffer as a byte:

| value | staging byte | meaning |
|---|---|---|
| 0 | `0x45` | transparent — every pass skips it |
| 1 | `0x48` | light face |
| 2 | `0x4B` | bevel / edge |
| 3 | `0x21` | unused by the retail font; colour unverified |

Role 3 does not occur in any of the 2048 retail glyphs. Avoid it when repainting.

### Slot inventory

| | |
|---|---|
| total slots | 2048 |
| highest slot with ink | `0x6A0` |
| blank slots | 353 — `0x066`, `0x593`, and `0x6A1`–`0x7FF` |
| highest slot the script uses | `0x69B` |

`0x066` is the full-width space and is drawn constantly despite being blank; `0x593`
is referenced by the script. Neither is safe to repaint.

## Rendering

Screen is mode 13h, 320×200, 8bpp. Screen pitch 320; the dialogue box advances
**19 pixels** per glyph (`add dword [0x26ec], 0x13`).

Each glyph is expanded into the staging buffer, then blitted three times. Contrary
to earlier notes in this file, the passes are **not** one-pixel offsets of one
bitmap — they differ by position *and* palette:

| pass | destination | writes |
|---|---|---|
| shadow | `edi` | constant colour 7 wherever the source is not `0x45` |
| main A | `edi - 0x282` | `0x48`→`0x78`, `0x4B`→`0x24` |
| main B | `edi - 0x282` | `0x48`→`0x47`, `0x4B`→`0x41` (or `0x16`) |

`-0x282` is `-(2*320 + 2)`: two pixels up and two left. A and B are alternatives
selected by a flag at `[0x1372]`, not both drawn.

Colour 0 is transparent for **icon** cells; for **font** cells the transparent
staging value is `0x45`, because the font is 2bpp and 0 is a role, not a colour.

### Icon and portrait blitter

Entry 1098, 16×16 8bpp cells, 256 bytes each, colour 0 transparent. From overlay 13
at `0xB42F`:

```
shl  eax, 8                      ; index * 256
mov  bl, fs:[eax + 0x284E20]     ; 0x280000 (entry 1098) + 0x4E20 (icons)
cmp  bl, 0 / je                  ; colour 0 transparent
add  edi, 0x130                  ; 304 = 320 - 16, next row
```

Portraits use the same loop at `+0xA108`.

## Picture entries — skip/run codec

Entries whose first bytes are `01 ff ff` or `02 ff ff` (and entry 21, tagged `03`)
carry a run-length stream:

```
repeat:
  u16 skip      transparent pixels to advance
  u16 len       literal pixel count
  u8 * len      literal 8bpp pixels
until:
  ff ff         end of image
```

Multiple images follow one another in a single entry. On entry 21 this decodes 24
images and accounts for 98.1% of the entry. Row width is implicit: within one image
`skip + len` sums to the row width for rows containing a single run.

Entry 21 is UI artwork, not a glyph sheet — its largest image is 34,908 pixels.

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

Indices observed in clean messages run from `0x0000` to `0x069B`.

The renderer word-wraps at **12 units per line, 3 lines per box**. Messages contain
no explicit line or box breaks — an 84-unit message renders as three boxes.

### Container limits

The unit count is a **u8**, so 255 units is a hard ceiling per message. The longest
retail message is 252 units — 99% of the way there. Message offsets are u16 and
memory-relative, so an entry's payload cannot exceed 64 KB; the largest is entry 23
at 29,874 bytes.

Both limits bind before any font or width work does. Expanding text past them means
splitting messages, which adds offset-table entries and moves every message after
the insertion point.

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
| font | entry 4, 2048 × 64 bytes, loaded to `0x100000` |
| UI artwork | entry 21, skip/run images, loaded to `0x040000` by 81 of 90 overlays |
| item icons | entry 1098, offset `0x4E20`, 16×16 8bpp, 256 bytes per cell |
| portrait faces | entry 1098, offset `0xA108`, same cell format |
| raw screens | 64000-byte entries (320×200); 768-byte entries are VGA palettes |
| GUS patch bank | entry 0, and the loose `DATA` file (`GF1PATCH110`) |
| code overlays | ~90 entries, prologue `1E 06 66 50 66 53 66 51 66 52 66 56 66 57 66 55` |

Overlays are copies of one engine with per-scene data; two overlays differ in about
12 KB of scattered data plus a size shift. Overlay code addresses quoted in this file
(`0x6ECC`, `0xB42F`, `0xFD15`) are consistent across copies.
