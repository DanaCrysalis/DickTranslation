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

### Latin glyphs already present

The font carries Latin in two sets, which matters when adjudicating a doubtful
reading — "it looks like a letter" is a live hypothesis, not a stretch.

| set | slots | dialogue uses |
|---|---|---|
| halfwidth `D O S` | `0x143`–`0x145` (contiguous — "DOS") | 0 |
| halfwidth `M P H` | `0x1d7`–`0x1d9` (MP / HP) | 0 |
| halfwidth `X` | `0x263` | 0 |
| fullwidth `Ａ Ｂ Ｃ` | `0x55b`, `0x55d`, `0x57b` | 6 / 6 / 4 — NPC labels 商人Ａ, 村人Ｂ, 村人Ｃ |
| fullwidth `Ｚ` | `0x17a` | 2 — the sleeping sound effect at e23 m47 |

Also present: halfwidth digits `0`–`5`, fullwidth `８ ９`, `/ + %`, a fullwidth
hyphen and a box-drawing dash.

`0x17a` sits one pixel lower than Ａ Ｂ Ｃ. It was allocated in entry 23 while the
letters were allocated in entry 390, so it was drawn first, in a different pass, and
never quite matched the later baseline.

### Slot inventory

| | |
|---|---|
| total slots | 2048 |
| highest slot with ink | `0x6A0` |
| blank slots | 353 — `0x066`, `0x593`, and `0x6A1`–`0x7FF` |
| highest slot the script uses | `0x69B` |

`0x066` is the full-width space and is drawn constantly despite being blank; `0x593`
is referenced by the script. Neither is safe to repaint.

**A third category exists: slots with ink that are not characters.** `0x2be`
renders as an empty box with one grey line along the top edge. It is not blank, so
it is not in the 353 count above, and it carries no reading - but it *is*
referenced, as the entire "description" of 聖光槍 and 冰盾 in entry 1098, both of
which should be read as having no description. `0x2bf` is also unmapped and may be
its pair. Do not assume "has ink" means "is a character".

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

## UI, menu and battle strings

These are **not** in a data entry. They live inside the code overlays, and every
overlay carries a copy: the field and system menus appear in all 89, battle
strings only in entries 48, 258, 416, 612 and 790.

```
u16 count
u16 * count   glyph indices
u16 trailer   purpose unknown; preserved verbatim when patching
```

Records usually sit back to back, but not always: the spell schools are 12 bytes
apart with a 2-byte gap, and the retreat block is a run of only three. Any
scanner that requires long contiguous chains will silently miss whole tables.

Copies are **not** byte-identical. Entry 48 holds the field menu at `0x12E8`,
entry 47 at `0x12D6`, and entry 47 has 46 records where most overlays have 58.
Locate records by content, never by offset.

### Spaced labels

Menu labels space their characters apart, so the two halves are never adjacent
in memory:

```
0x0A172   3 units   攻 · 擊      (0x0108, 0x0066, 0x0109)
```

The middle unit is the full-width space. Searching for the character pair
`0108 0109` will not find the battle menu.

### Runtime-filled units

Two kinds of unit are written by the engine while drawing and must be preserved:

| unit | meaning |
|---|---|
| `0x0066` | full-width space; in `等級··升至··` these receive digits |
| `0x0000` | placeholder; receives a character name |

`等級··升至··` renders as `等級 12 升至 13`. Overwriting the `·` units breaks the
substitution, so a translation must leave them alone.

**This also happens in dialogue**, in exactly one place. `e390 m2` reads
`商人Ａ：...我出價　　　元！！` — three `0x0066` cells between 價 and 元 receive the
merchant's offer price at draw time. A sweep of all five script entries found no
other case; the other 17 mid-sentence gaps are layout spacing. Note that `0x0000` is
**not** a placeholder inside dialogue: there it is the character 一.

### Templates rewritten at runtime

The battle menu's third option is a template. The stored record is `特·技`, but
units 0 and 2 are replaced at draw time with the character's class skill name,
taken from a bare 2-unit array at `0x09739` in entry 48:

> **Location CONFIRMED (2026-08-26).** `0x09739` is right, and each entry is
> 4 bytes. An archive-wide byte search puts 弓術 (`92 02 e3 01`) at entry 48
> +`0x9741` and 斧擊 (`1a 02 09 01`) at +`0x974D` — exactly `0x9739 + 2x4` and
> `0x9739 + 5x4`, the third and sixth entries of the list below. Eleven entries,
> 44 bytes, `0x9739`-`0x9764`.
>
> This also explains the `0x0975B` row in `dialogue.xlsx` that reads 槍技神法:
> entry 9 of the array is 刀法, whose second unit 法 is `0x0004`, and `uitext.py`
> read that 4 as a record length and took the next four units — 槍技神法, which
> are entries 10 and 11. The bare array is invisible to the scanner by design,
> and was found here only because one of its own units happens to be the number 4.
>
> **Why the extracted copy looked empty.** `out/0048.bin` is not a clean
> extraction — it is the **patch output**, with the `battle_full` preset already
> applied in place. Diffing it against a fresh extraction shows that *every*
> changed `u16` has a high byte of `06` or `07`, i.e. lies in the free/blank slot
> range `0x6A1`-`0x7FF` that `mkfont.py` repaints with Latin digraphs. Nothing is
> stale and nothing is corrupt; the Chinese has simply been replaced with English
> where the preset covers.
>
> At `0x9739` the patched file holds `06EA 072D` repeated eleven times. That is
> not fill: it is the same repainted pair written into all eleven class entries,
> which is exactly what this table's design forces — every class shares the middle
> cell, so every class must resolve to the same English word. The constraint
> described below is already implemented in the proof-of-concept patch.
>
> **Two earlier notes in this file were wrong, and both came from probing the
> patched file as though it were retail data.** When reading raw bytes, extract
> from a clean `DICK.DAT` to a separate directory.


```
特技 劍技 弓術 精神 特技 斧擊 無· 武技 刀法 槍技 神法
```

Only the middle unit is static. The label therefore renders as

```
[class unit 0][static middle][class unit 1]
```

so a single English word has to be split across all three — "Sk" + "il" + "l ".
Because every class shares one middle cell, per-class English names are
impossible without a code change.

### Overlay record header — [position][count], not [count][trailer]

`uitext.py` models an overlay string as `u16 count`, units, `u16 trailer`. The
real shape is:

```
u16  screen position   byte offset into a 320-wide screen
u16  unit count
n x u16  units
```

What the tool calls a trailer is the **next record's position word**. Walking the
correct shape from `0x1509` in entry 48 yields five 3-unit records at `0x6E5F`,
`0x861F`, `0x9DDF`, `0xB59F`, `0xCD5F` — x=95 with y=88, 107, 126, 145, 164, five
party rows exactly 19 pixels apart — then `HP··MP` and `/`. The same walk over
`0x1600` gives 頁數, `/`, `MP：`, five more party rows on the identical `0x17C0`
vertical stride, then the six element tabs 火·系 風·系 冰·系 光·系 雷·系 回復系, all
sharing position `0x2452` because they are tabs drawn in one place.

`pos % 320` and `pos // 320` give x and y, which makes this a **test**: a genuine
record has a position below `0xFA00` (64000); a phantom one usually has `0x0000`.
It also explains why every offset in `dialogue.xlsx` is the count field with the
content at +2.

### The battle HP/MP plate

Found, and it needs no image work — the labels are ordinary full-width glyphs
(H `0x01D9`, P `0x01D8`, M `0x01D7`).

```
0x01509  pos 6E5F  n=3   ___     party row 1   x=95  y=88
0x01513  pos 861F  n=3   ___     party row 2         y=107
0x0151D  pos 9DDF  n=3   ___     party row 3         y=126
0x01527  pos B59F  n=3   ___     party row 4         y=145
0x01531  pos CD5F  n=3   ___     party row 5         y=164
0x0153B  pos 55BE  n=6   HP··MP  header       x=190  y=68
0x0154B  pos 0000  n=1   /       placed by code
```

The five name slots are three units each and are filled at draw time from the
character-name table. It stayed hidden because those slots hold nothing but
`0x0000` and the header is only six units, so nothing in the old record model had
a plausible count to latch onto.

The item menu grid sits just above, eight 8-unit records at `0x016BD` through
`0x01749`, positions forming a 2 x 4 grid at x=18 and x=178, y=99/117/135/153.
Their `的的的的的的的的` content is the byte pattern `11 11` repeated (的 is
`0x0011`) — a placeholder overwritten at draw time.

### Bare arrays: the scanner's blind spot

`uitext.py` finds a record by requiring `u16 count`, that many units, then a
`u16` trailer. **Not every table has that shape.** The class skill array at
`0x09739` in entry 48 (documented below) is a bare run of 2-unit entries with no
count and no trailer, and no dump has ever found it automatically - it is known
only because it was read out of the code. Any other table stored the same way is
invisible to every scan run so far.

This is the leading explanation for the 76 mapped glyph slots that no dumped
corpus references. Their vocabulary - 鳳凰, 隕, 砲, 旋, 焦, 煌, 鋼, 虎, 犬 - reads
as special-attack names (鳳凰旋, 隕石砲) rather than dialogue. `tools/tblprobe.py`
derives stride and parity for a table of unknown format and is the tool for
finding them.

### The destination table

Each battle overlay carries the world-map destination list for its own chapter,
in the `0x0940`-`0x0965` region:

| overlay | chapter | names |
|---|---|---|
| 48 | 1 | 那都村 古雷村 森林 礦坑 奧丁城下鎮 小村莊 峽谷 |
| 258 | 2 | 格倫村 達蓮王城 穆古村 神殿 德茲村 科林港 哈樂德村 |
| 416 | 3 | 哈路利村 貝德村 克魯達村 愛斯那村 沙利安村 布德村 |
| 612 | 4 | 拉賽倫王城 羅蘭村 文森村 托夫村 康泰村 |
| 790 | 5 | 摩里斯城 尼斯卡城 伊克城 薩爾城 |

Some entries are read as one long record by `uitext.py`'s scanner and need
`tblprobe.py` to separate. Immediately after this table, every overlay has a
**0x39-byte-stride table** whose columns decode as the nonsense `丑妻` at exact
57-byte intervals (48 at `0x0971B`; 612 at `0x09736`, `0x0976F`, `0x097A8`; 790 at
`0x095A1`, `0x095DA`, `0x09613`). A nonsense string repeating on a fixed stride is
not a string - it is two columns of a fixed-width record table. Not yet decoded.

### Vocabulary outside the dialogue

Menus use characters the script never does, so they are absent from
`charmap.json` until read out of the font. `0x282` 頁 and `0x291` `/` were found
this way. A record containing an unmapped index cannot be decoded and will be
skipped entirely, which looks identical to the record not existing.


## Item, spell and monster names — entry 1098

Entry 1098 is the game's data bank, not only an icon sheet. Before the icons it
holds fixed-width name/description records:

```
record stride  0x50 (80 bytes), first record at 0x145
+0x4C          name field,        5 units, padded with 0x0066
+0x56          3 units, ALWAYS 0x0066 in all 245 slots - a fixed gap
+0x5C          description field, 12 units, padded with 0x0066
+0x74          4 units, ALWAYS 0x0066 - a fixed gap
+0x7C          binary stats, 16 units (32 bytes)
```

5 + 3 + 12 + 4 + 16 = 40 units = 0x50 exactly. Note that the name/description
block starts at +0x4C and therefore runs past the nominal record end into the
next stride slot; the offsets above are relative to the record bases `names.py`
uses (`FIRST = 0x145`), not to a natural record boundary. Read the columns, not
the record numbering.

**These offsets were wrong until 2026-08-26.** This file said name 8 units at
+0x42 and description 14 units at +0x52, and `names.py` was coded to match. That
window starts five units early and ends three units into the name, which is why
`dialogue.xlsx` truncated every name at three characters, spilled the fourth into
the description (`賢者之|杖受諸神保護的大賢者`), and made the spell rows look
garbled with a junk prefix (`功迅風咒`, `藍書[2c1f]裝夢之咒`) - the prefix was the
previous record's stat bytes decoding as glyphs. Verified empirically with
`names.py layout`, which probes every u16 column of the stride.

**0x0000 is the character 一 here, not padding.** Both fields pad with 0x0066.
The old `text()` dropped 0x0000 as padding, which silently deleted 一 from
descriptions: 一人速度上升 read as 人速度上升, 同伴免死一次 as 同伴免死次.

235 populated records, all items and spells. Sections are positional rather than tagged: items first,
spells from roughly 0x4500, monsters from roughly 0x8000, with unpopulated gaps
between. The icon sheet at 0x4E20 and portraits at 0xA108 sit inside the same
entry.

Field widths translate to **10 Latin characters for a name and 24 for a
description** at two letters per cell. That is tighter than the 16/28 this file
used to claim, and tight enough to shape the English: most two-word item names
have to close up the space (`SilverHelm`, `FlameAegis`, `BoltMirror`).

Section boundaries are positional. **Spells begin at 0x3E35**, not the 0x4500
quoted in earlier revisions. The main table's populated run ends at 0x04AB5.

**Entry 1098 does not end there.** Two further tables sit above what was long
assumed to be an icon boundary at `0x4E20`:

| table | at | stride | layout | entries |
|---|---|---|---|---|
| special attacks and summons | `0x07F21` | `0x2A` | name 5 units at +0x00 | 49 |
| plot items | `0x08F89` | `0x50` | name 5 units at +0x00, description 12 at +0x10 | 29 |

The plot table's record is the **same `[name 5][gap 3][desc 12]` block** as the
main item table, sitting at offset 0 instead of +0x4C — independent confirmation
of that layout.

`names.py`'s `records()` used to stop at `0x4E20`, so nothing ever read these.
That single constant produced two false conclusions that stood for a long time:
that the table holds 235 records, and that the game does not name its monsters.
The `~0x8000` figure in `README.md` was right all along.

`tools/names.py` dumps these to JSON, and patches translations back in place.

## Picture entries — skip/run codec

Entries whose first bytes are `01 ff ff` or `02 ff ff` (and entry 21, tagged `03`)
carry a run-length stream:

```
u8            mode: 0 = stream begins with a skip, non-zero = begins with a run
repeat:
  u16 skip    transparent pixels to advance (0xFFFF ends the image)
  u16 len     literal pixel count           (0xFFFF also ends)
  u8 * len    literal 8bpp pixels
```

Read from the decoder in overlay 13 at `0x25DA`. The leading mode byte is easy
to miss; omitting it puts every image one byte out of phase and decodes to
noise. Image dimensions are **not** in the stream - the decode loop walks a
table of 16-byte descriptors at `[ebx+0x7DD6]`, which has not yet been located.
Without it, widths can only be guessed.

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

**Every clean message's unit count is a multiple of 12** — all 1,064 of them.
Messages are padded to whole lines with `0x0066`.

**Speaker turns start on a fresh line.** Within a message, a new speaker generally
begins at a 12-unit boundary, padded out to reach it: 399 of ~464 internal turn
breaks land exactly on one. The rest pack two short turns onto a shared line, which
the retail script does when space is tight. Turns cross *box* boundaries freely — the
alignment is to the line, not the box.

A one-character speaker name is padded to two cells with a leading `0x0066`
(`　琳：`), which is why some turn starts sit one unit past a boundary.

### Container limits

The unit count is a **u8**, so 255 units is the raw ceiling — but because messages
are padded to whole 12-unit lines, the **effective ceiling is 252 units** (21 lines,
504 Latin characters at two per cell). The longest retail message is exactly 252,
which is the ceiling rather than a near miss. Message offsets are u16 and
memory-relative, so an entry's payload cannot exceed 64 KB; the largest is entry 23
at 29,874 bytes.

Both limits bind before any font or width work does. Expanding text past them means
splitting messages, which adds offset-table entries and moves every message after
the insertion point.

## Character-name table

Three units per entry, centre-padded with `0x0066`:

```
005d 0066 005e   狄 · 克
0066 000f 0066   · 琳 ·
```

**It is not only in RAM.** A static copy sits in entry 48 on a 6-byte grid based
at `0x14D9`, which is what makes it patchable without touching code:

| offset | units | name | English |
|---|---|---|---|
| `0x14B5` | `0000 0000 0000` | — | empty |
| `0x14BB` | `0000 0000 0000` | — | empty |
| `0x14C1` | `0000 0000 0000` | — | empty |
| `0x14C7` | `01b0 00c4 01b1` | 德瑞爾 | Darrel |
| `0x14CD` | `005d 0066 005e` | 狄克 | Dick |
| `0x14D3` | `0286 009a 005e` | 艾薩克 | Isaac |
| `0x14D9` | `0066 000f 0066` | 琳 | Lin |
| `0x14DF` | `0004 0066 0147` | 法蘭 | Fran |
| `0x14E5` | `00bf 0066 01f0` | 諾隆 | Noron |
| `0x14EB` | `0288 00be 009c` | 娜迪亞 | Nadia |
| `0x14F1` | `0285 0066 0073` | 龍特 | Ronto |
| `0x14F7` | `0287 025b 01a6` | 沙卡修 | Sakash |

The 狄克 row is `005d 0066 005e` byte for byte — the same bytes this file already
gives as the RAM example — so the static copy and the RAM copy share a layout.

Two names exceed six characters and are shortened on screen only: **Darrell**
becomes `Darrel` and **Sakashu** becomes `Sakash`. The dialogue keeps both in
full.

Three cells is **6 Latin characters**, and the English does not have to reproduce
the centring — write it left-aligned and space-padded.

Two cautions this table earned. First, `uitext.py` reports a bogus 15-unit
"record" at `0x14DB`, because 琳 is glyph `0x000F` and the scanner read the
character *Lin* as a unit count. Second, and usefully, that is the second bare
array to surface this way — the class skill array appeared because its 法 is
`0x0004`. **A bare array can be hunted deliberately by looking for records whose
declared length equals a low-index glyph sitting where a name should be.**

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
| slot-ordered glyph tables | entries 6 and 463, 4 bytes per record - see below |
| code overlays | ~90 entries, prologue `1E 06 66 50 66 53 66 51 66 52 66 56 66 57 66 55` |

### Entries 6 and 463 — slot-ordered glyph tables

Neither had been catalogued. Both hold 4-byte records that walk the font in
**ascending slot order**, each glyph index paired with a small, nearly constant
second `u16` (`0x001a` throughout entry 463; a different low value in entry 6):

```
entry 463 +0x30C5   欲參傑帝佔剷投魯額佩膽輩仍     slots 0x57F-0x58B, consecutive
entry 463 +0x3199   萄景央季節瀾素端穩晨氛遷財駕淮察悍抵雜   0x5BA-0x5CC
entry 6   +0x250E   淮察悍俊贏熟逝泡呆揚迫握隔唔跳扎   ascending, but a SUBSET
```

Entry 6 skips slots entry 463 includes, so they are two different lists rather
than copies. `loadmap.txt` shows entry 6 is loaded by overlay 181 — the loader —
to flat `0x2C0000` in the same pass as entry 4 (the font), entry 1098 (the data
bank) and entries 2, 3 and 178, which makes it a global boot-time asset sitting
beside the font. Entry 463 is scene-local, loaded by overlay 454 to `0x1A0000`.
Purpose unknown; `tools/tblprobe.py` will derive their record layout.

Consequence for the map work: **a slot-ordered table references a glyph without
anyone having typed it into text.** "Referenced nowhere" therefore does not imply
"belongs to an undumped text corpus" as strongly as it seems to.

Overlays are copies of one engine with per-scene data; two overlays differ in about
12 KB of scattered data plus a size shift. Overlay code addresses quoted in this file
(`0x6ECC`, `0xB42F`, `0xFD15`) are consistent across copies.
