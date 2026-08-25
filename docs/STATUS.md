# Status

## Solved

- **Archive format** — parsed and verified against the game's own loader code.
- **No container compression** — the loader strips one type byte and copies verbatim.
- **Script format** — 1,064 messages extractable and reinsertable.
- **Text encoding** — 16-bit glyph indices, frequency-ordered, `0x0066` = space.
- **Reinsertion** — proven in-game.
- **Font bitmaps** — entry 4, 2048 slots, 16×16 at 2bpp, 64 bytes per glyph, loaded
  to `0x100000`. Format read out of the renderer and verified against 496
  independently recovered glyphs: 496/496 exact. `tools/font.py` decodes, exports
  and repaints it.
- **Text renderer** — three-pass draw, palette roles, 19-pixel advance, all read
  from the overlay code rather than inferred.
- **Picture codec** — skip/run stream used by artwork entries.
- **Variable-length reinsertion.** A message can grow, the offset table can be
  rebuilt and the archive repacked. Verified in-game: entry 23 was inflated from
  30,626 to 51,566 bytes (+68%) and a message pushed from byte 11,165 to 32,105
  still rendered correctly.
- **Overlay/asset map**, **save format**, **icon and portrait banks**, **audio**.

## Numbers

| | |
|---|---|
| messages extracted | 1,064 clean (of 1,108 parsed; 44 over-read) |
| characters of dialogue | ~39,500 |
| distinct glyph indices used | 1,508 |
| characters mapped | 1,668 |
| coverage by text volume | 100% |
| highest index used by script | `0x069B` |
| font slots | 2,048 (353 blank) |
| slots the script never references | 540 |

## Not solved

- **Menu / item / spell name tables.** Same encoding, different container — no
  length-prefixed message structure, so the script parser skips them.
- **44 over-read messages.** 4% of the total; the length byte or a table slot
  behaves unexpectedly. Flagged in the spreadsheet, individually identifiable.
- **How script entries reach memory.** No overlay in `loadmap.txt` loads entries
  23/249/390/625/794, so `cmd_loadmap` is missing a code path.


## Known weaknesses

- The character map was read by eye. The reliable check is decoding the script and
  reading it for sense; that caught 46 errors in one pass, including many that
  collide with nothing and are invisible to duplicate detection.
- **Duplicate detection produces false positives.** The font contains duplicate
  characters — `0x353` and `0x524` are both 越, both used, in overlapping chapters.
  A duplicate is a prompt to check, not proof of a misreading.
- Several glyphs were deliberately left unmapped rather than guessed. 13 remain,
  listed in the notes accompanying the last mapping pass.
- Coverage percentages are by text volume, so they overstate how much of the *rare*
  vocabulary is known.
- Some oddities in the decoded script are the **game's own typos**, not map errors:
  氾瀾 for 氾濫, 廣閣 for 廣闊, 整遍 for 整片. Verify against the glyph before
  "fixing" a reading.

## Corrections made to earlier findings

- `0x123` is **閒**, not 間. The real 間 is `0x4EE`.
- FORMATS previously described the bevel as three draws at one-pixel offsets. It is
  three draws at `-0x282` (two up, two left) differing by **palette**, with the
  bevel encoded in the glyph's own 2-bit roles.
- `data/free_slots.txt` said "the font is larger than the script's index range, so
  more slots exist above `0x69b`". Confirmed: 351 blank slots at `0x6A1`–`0x7FF`.

## For an English patch

Latin letters exist in the font but only where the developers needed them — D, O,
S, M, P, H, X, and digits 0–5. English text needs slots repainted.

**540 slots are never referenced by clean dialogue**: 352 blank and 188 already
carrying a Chinese glyph. `data/free_slots.txt` lists 94 of the drawn ones and all
94 check out against the font. Repainting is `font.py export` → edit 16×16 PNGs →
`font.py import`; untouched slots stay byte-identical, so the result repacks safely.

Two entries that look free are not: `0x066` is the full-width space and `0x593` is
script-referenced. Both are blank but drawn.

### Fitting English into the box

The dialogue box is 12 glyphs per line at a 19-pixel advance, 3 lines per box.
Chinese→English runs roughly 3× in character count, so per original glyph cell:

| approach | screen cost | engine changes |
|---|---|---|
| two 8×8 letters per existing cell (digraphs) | ×1.50 | none |
| true half-width, 8px advance | ×1.26 | advance constant + wrap counter |
| proportional | ×1.03 | advance, plus word-aware wrapping |

Digraphs need no code change at all: a line-setter can wrap at 24 columns and pad
each line to exactly 12 units, which is what the game already does with `0x0066`.
Roughly 1,000–1,200 distinct letter pairs cover a full script, which fits the
available slots once translated Chinese glyphs are freed.

None of this avoids the **u8 unit count**: at 1.5× unit growth, 37 messages exceed
255 units and must be split. That is the real remaining constraint, not the font.

Entry growth is proven to 32,105 bytes deep in entry 23. A full translation needs
that entry at roughly 45,127 bytes, so a ~13 KB window is untested — the technique
cannot probe further because the messages ahead of the reachable one are already at
the 255-unit ceiling. The risk is low (the loader takes its size from the TOC, and a
buffer sized to the retail 30,626 bytes would already have failed at 32,105), and
translating chapter 1 first exercises that region as a by-product.

### Order of work

1. Locate the menu / item / spell name tables — the only shippable-patch blocker.
   Now tractable: search entries for known index sequences from `charmap.json`.
2. Design the digraph font: `font.py export`, draw 8x8 letter pairs into free slots,
   `font.py import`.
3. Write the line-setter: wrap at 24 columns, pad each line to exactly 12 units.
4. Translate, splitting the 37 messages that breach 255 units.
