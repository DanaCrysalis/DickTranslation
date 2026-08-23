# Status

## Solved

- **Archive format** — parsed and verified against the game's own loader code.
- **No compression** — every asset is stored raw.
- **Script format** — 1,064 messages extractable and reinsertable.
- **Text encoding** — 16-bit glyph indices, frequency-ordered, `0x0066` = space.
- **Reinsertion** — proven in-game. Rewriting a message and seeing it on screen
  confirms the whole chain: TOC, entry location, offset table, message structure,
  glyph indices.
- **Overlay/asset map** — which entries each of ~90 overlays loads, and where.
- **Save format**, **icon and portrait banks**, **audio format**.

## Numbers

| | |
|---|---|
| messages extracted | 1,064 clean (of 1,108 parsed; 44 over-read) |
| characters of dialogue | ~39,500 |
| distinct glyph indices used | 1,508 |
| characters mapped | 1,120 |
| coverage by text volume | 96.0% |
| messages fully decoded | 427 / 1,064 |
| highest index used by script | `0x069b` |

## Not solved

- **Font bitmaps.** Not stored as a plain bitmap at any bit depth or row pitch.
  Almost certainly RLE per glyph. Needs the blitter disassembled.
- **Menu / item / spell name tables.** Same encoding, different container — no
  length-prefixed message structure, so the script parser skips them.
- **44 over-read messages.** 4% of the total; the length byte or a table slot
  behaves unexpectedly. Flagged in the spreadsheet, individually identifiable.
- **The remaining 482 indices** the script uses but that aren't yet identified.
  See `data/unmapped.txt`; recover with more `glyphdump.py` passes.

## Known weaknesses

- The character map was read by eye from screenshots. Duplicate detection catches
  misreadings only when two indices collide on one character. Errors that produce a
  character not otherwise used are invisible. Four such errors were caught and fixed
  (萊→禁, 兒→兇, 野→夥, 蠻癟→繼續); more probably remain among rare glyphs.
- Several glyphs were deliberately left unmapped rather than guessed, where the
  script never uses them and the reading was uncertain.
- Coverage percentages are by text volume, so they overstate how much of the *rare*
  vocabulary is known.

## For an English patch

Latin letters do exist in the font but only where the developers needed them — D, O,
S (from the DOS menu option), M, P, H, X, and digits 0–5. There is no full alphabet,
so English text will need glyph slots repainted.

`data/free_slots.txt` lists 94 identified slots the script never references. Those
are safe to overwrite. The font is larger than the script's index range, so more
slots exist above `0x069b` that are certainly unused.

Repainting requires the font format, which is the outstanding blocker. Until then,
insertion is limited to text built from glyphs the game already has.
