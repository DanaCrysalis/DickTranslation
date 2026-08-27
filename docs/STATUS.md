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
- **UI / menu / battle strings.** Located inside the code overlays, format
  documented, and translatable in place with `tools/uitext.py`. 118 records per
  battle overlay rewritten to English and confirmed in-game: battle menu, spell
  and item sub-menus, level-up lines, retreat, monster actions, status panel,
  field and system menus.
- **Latin font generation.** `tools/mkfont.py` packs two 8x16 letters into each
  16x16 cell, so English costs roughly 1.5 cells per original cell and needs no
  engine change.
- **Overlay/asset map**, **save format**, **icon and portrait banks**, **audio**.
- **The dialogue translation.** All 1,064 clean messages are in English in column J
  of `dialogue.xlsx`, with a `Glossary` sheet (~170 terms) and an `Issues` sheet
  (~180 rows). Growth 48,108 → 67,728 units, **1.41×**. See `docs/TRANSLATION.md`.
- **All the fixed-width text.** Entry 1098's three tables are settled and
  verified against retail bytes: 239 items and spells, 49 special attacks and
  summons, 29 plot items — **317 records, all translated**. There is no
  monster-name table; see FORMATS.md. The `Item-Spell-Monster` sheet is misnamed
  for historical reasons. Budget is 10 Latin
  characters for a name and 24 for a description.
- **All five battle overlays are dumped**, not just entry 48. The four new ones
  carry the per-chapter world-map destination table.
- **The UI.** Entry 48 is complete — every row either translated or shown not to
  be text — and the strings are written into every overlay copy by content match.
- **The character-name table**, at entry 48 `0x14C7`: Darrel, Dick, Isaac, Lin,
  Fran, Noron, Nadia, Ronto, Sakash.
- **The battle HP/MP plate**, at entry 48 `0x1509`–`0x154B`: five 3-unit party
  name slots at x=95, an `HP··MP` header at x=190 y=68, and a separator.
- **Reinsertion.** `tools/patch_all.py` builds a playable English archive —
  dialogue, both entry-1098 tables, the UI and the font in one allocation pass.
  See the reinsertion section of `docs/FORMATS.md`.

## Not solved

- **Menu and title artwork.** The title screen options (開始新遊戲 / 繼續舊冒險)
  are images, proven by the font not being resident in memory at the title. The
  image codec is understood but the 16-byte descriptor table that carries
  dimensions has not been found, so images cannot yet be re-encoded. This is now
  the only category of in-game text with no route to English.
- **無裝備 and the equipment dash filler.** The status screen writes "nothing
  equipped" from code or from an entry not yet scanned — a byte search for 無裝
  finds it in neither entry 48 nor 1098. Cosmetic: two Chinese strings on an
  otherwise English screen.
- **Entries 190, 208, 367, 831, 881, 893, 933.** Four or five "messages" each that
  decode as junk under the script parser, so either they are not script entries or
  they use a format nobody has read. The new-game text crawl is the likely
  occupant of at least one.
- **44 over-read messages.** 4% of the total; the length byte or a table slot
  behaves unexpectedly. Flagged in the spreadsheet, individually identifiable, and
  left untranslated.
- **How script entries reach memory.** No overlay in `loadmap.txt` loads entries
  23/249/390/625/794, so `cmd_loadmap` is missing a code path.
- **One-unit fields cannot hold English words.** The shop's 買 and 賣 are single
  units, i.e. two Latin characters. Not a gap in knowledge — a limit of the
  digraph approach, and the only fix is a draw-routine change or a word glyph.

## What the reinsertion pass taught

Every one of these cost at least one broken build. They are listed because the
pattern is the same each time: an inherited constant or a convenient assumption
that nothing had ever checked.

- **Entry lengths are fixed allocations.** Rebuilding a script entry to fit its
  contents shrank the archive by 174 KB and broke the battle system. Write back
  the same length.
- **Record 0 could not be addressed.** The sheet stored a record "base" and added
  `0x4C`; record 0's base would be negative, so the first weapon in every shop
  stayed Chinese. Address name fields, not bases.
- **Content matching needs a record header.** Without one, writes land inside
  longer untranslated strings and inside code — the latter locks the game up with
  DOS/4GW `Illegal descriptor type 0`.
- **Match count and entry size identify an overlay.** ~130 entries matched by
  content; the ones that crashed the game matched a handful and were not 65535
  bytes.
- **`0x0000` is 一, and 一 is a horizontal bar.** Writing it into engine-filled
  cells drew a row of dashes across the equipment screen. A preserved cell should
  copy whatever the original held.
- **Low glyph indices are small numbers.** 是 is `0x000B`; a one-unit search for it
  matched 37 numeric fields.
- **The archive size is a diagnostic.** Comparing two file sizes found the cause
  of a crash that four rounds of reasoning had missed. `tools/verify_patch.py`
  now does it automatically.

## Known weaknesses

- The character map was read by eye. The reliable check is decoding the script and
  reading it for sense; that caught 46 errors in one pass, including many that
  collide with nothing and are invisible to duplicate detection.
- **Duplicate detection is NOT reliable, and this file previously claimed it was.**
  A confirmed duplicate exists: `0x2f9` and `0x660` are both 鱗, and both are right.
  `0x2f9` is item-table vocabulary (龍鱗甲, 龍鱗盾, neighbours 冑 護 盾 腕) with zero
  dialogue uses; `0x660` has one dialogue use and no item uses. Allocation did not
  deduplicate **across corpora**. `README.md` and `PASS_NOTES.md` said so all along;
  this file and `CONTINUING.md` were wrong to overrule them.
  A duplicate is evidence to check, not proof of error — ask which corpus each slot
  serves. The related pairs `0x524` 愈, `0x55A` 鑲, `0x5EA` 筋, `0x66D` 脊 are worth
  re-rendering in that light.
- Three glyphs remain unmapped, not thirteen: `0x2be` (rendered — an empty box
  with one grey line, **not a character**), `0x5cd` and `0x5d3`. `data/unmapped.txt`
  and the `Unmapped` sheet are stale: they still list `0x2c3` and `0x2c8`, both of
  which are settled in `charmap.json` and corroborated by the item table (`0x2c3`
  is 鷹 from 飛鷹拳套 and 飛鷹頭帶, not 塵; `0x2c8` is 撤 against `0x645` 撒). That
  file also still argues from "the font contains no duplicate bitmaps", the
  reasoning this file retracts below.
- Coverage percentages are by text volume, so they overstate how much of the *rare*
  vocabulary is known.
- Some oddities in the decoded script are the **game's own typos**, not map errors:
  氾瀾 for 氾濫, 廣閣 for 廣闊, 整遍 for 整片, and roughly seventy more logged in the
  `Issues` sheet. Verify against the glyph before "fixing" a reading.
- **The reverse error is just as common.** Of 38 odd decodes met while translating,
  11 were map errors wearing a typo's clothes. Low-frequency glyphs are the weak
  layer: 339 indices occur exactly *once* in the clean dialogue, where context cannot
  reach them at all. Use the zero-good-use test and the bigram profile in
  `CONTINUING.md`, and `data/glyph_bigram_audit.csv`.

## Corrections made to earlier findings

- ~~`0x123` is **閒**, not 間. The real 間 is `0x4EE`.~~ **Both halves of this are
  wrong.** `0x123` is 間 (突然間, 房間, 一段時間, 之間) and `0x4EE` is 食 (飲食).
  Confirmed by context in every occurrence. The same correction in `PASS_NOTES.md`
  is wrong for the same reason.
- ~~`0x64E` is **麾** (先王麾下).~~ Wrong: `0x64E` is 役 (戰役).
- FORMATS previously described the bevel as three draws at one-pixel offsets. It is
  three draws at `-0x282` (two up, two left) differing by **palette**, with the
  bevel encoded in the glyph's own 2-bit roles.
- `data/free_slots.txt` said "the font is larger than the script's index range, so
  more slots exist above `0x69b`". Confirmed: 351 blank slots at `0x6A1`–`0x7FF`.

## Charmap corrections made while translating

18 readings were wrong and are now fixed in `data/charmap.json`. 16 were confirmed by
rendering the glyph; two (`0x2a6`, `0x366`) by the bigram profile and then rendered.

| slot | was | is | how it was caught |
|---|---|---|---|
| `0x2a6` | 亙 | **巨** | 44 uses, every bigram wrong — 巨樹, 巨弓, 巨繩 are chapter 4's core nouns |
| `0x41f` | 晝 | **費** | 7 uses, all cost contexts; 書 and 畫 already occupied |
| `0x41e` | 僵 | **價** | 5 uses, all price contexts; adjacent to 費 |
| `0x40c` | 螢 | **蠻** | 6 uses, all the adverb 蠻 |
| `0x1bd` | 槽 | **糟** | 6 uses; render read 相, but 相 is `0x51` with 34 uses |
| `0x44d` | 滇 | **漠** | 10 uses — makes 沙漠之翼 "Wings of the Desert" readable |
| `0x230` | 檻 | **權** | 2 uses, both 政權 |
| `0x2cd` | 簧 | **驚** | 驚訝, and 驚人/驚天/驚動 in entry 1098 |
| `0x35a` | 訂 | **訝** | slot order 躲 藏 [訝] 史 課 哼 = e23 m13's vocabulary |
| `0x404` | 遮 | **遞** | 傳遞訊息; `0x405` is 訊 |
| `0x474` | 賭 | **睹** | 慘不忍睹; `0x472`=慘 `0x473`=忍 |
| `0x341` | 葡 | **徹** | 很徹底 |
| `0x699` | 蟑 | **螞** | 螞蟻; `0x69a`=蟻 |
| `0x467` | 闊 | **闢** | 闢了一條小路; 開 occupied |
| `0x58b` | 仿 | **仍** | 仍守在門口 — not a 守-compound at all |
| `0x660` | 鎌 | **鱗** | 金色的鱗片 — 魚 radical, not 金 |
| `0x366` | 詩 | **誇** | 誇獎 / 誇張; `0x367`=獎 |
| `0x17a` | 乙 | **Ｚ** | fullwidth Latin — the sleeping SFX Ｚ。。。Ｚ。。 |

### Three further corrections, from the item corpus (2026-08-26)

Found by running the zero-good-use test over the **item table** rather than the
dialogue — the corpus that CONTINUING.md's "check every corpus" note exists for.

| slot | was | is | how it was caught |
|---|---|---|---|
| `0x2cb` | 屑 | **屠** | zero dialogue uses; three item uses and all are 屑龍. 屠龍劍 Dragonbane, 屠龍槍, and 斬龍斧's 勇者屠龍時所用的巨斧. 屠 was absent from the map. Rendered |
| `0x2e8` | 餞 | **燄** | one use in the whole game, 火餞頭盔 described as 以烈火鍛造的. 焰 is `0x2b1` with three correct item uses in the same corpus, so occupancy forced the variant 燄. Rendered |
| `0x5ea` | 筋 | **節** | rendered. Duplicates `0x5be` 節, which is dialogue-resident; `0x5ea` has zero uses in any dumped corpus, so the two serve different corpora |

Contrast `0x5c3`, which was NOT corrected: it has one dialogue use, 早晨 "morning",
which is right, and three item uses that are all 星晨 for 星辰. Right glyph, wrong
place — a **retail typo**, and 辰 being absent from the map confirms the writers
never typed it. The two verdicts came out of the same test on the same day and are
worth reading together.

### Two long-standing open questions, closed

- `0x505` is **垂**, confirmed by render. So 一臉垂喪 is the writers' own
  contraction of 垂頭喪氣, not a map error. Open since the 0x4B0-0x6A0 pass.
- `0x524` is **愈**, confirmed by render. The `PASS_NOTES.md` claim that `0x353`
  and `0x524` are both 越 is wrong. Context could not settle it — all five uses are
  the frame X來X, and 愈來愈 and 越來越 are equally idiomatic — but the corpus
  argument pointed the right way: `0x353` is certainly 越 and writes 越來越 31
  times across the same entries, so a same-corpus duplicate would have been
  anomalous.

Still unresolved, none blocking: `0x505` (一臉X喪 — 垂 may be right, as a contraction
of 垂頭喪氣) and `0x5e3` (a snort of contempt, X！真煩 — any dismissive reading works,
so it does not need identifying).

## For an English patch

Latin letters exist in the font but only where the developers needed them — D, O,
S, M, P, H, X, fullwidth Ａ Ｂ Ｃ Ｚ, and digits. English text needs slots repainted.

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

**This turned out not to bind.** The completed translation grew 1.41×, not 1.5×, and
**no message needed splitting**. The 37-message estimate assumed uniform growth; in
practice short NPC barks grow far less than the average and the long expository
messages were tightened to fit. Note also that the true ceiling is **252 units, not
255**, because every message is padded to a whole 12-unit line.

Entry growth is proven to 32,105 bytes deep in entry 23. A full translation needs
that entry at roughly 45,127 bytes, so a ~13 KB window is untested — the technique
cannot probe further because the messages ahead of the reachable one are already at
the 255-unit ceiling. The risk is low (the loader takes its size from the TOC, and a
buffer sized to the retail 30,626 bytes would already have failed at 32,105), and
translating chapter 1 first exercises that region as a by-product.

### Order of work

1. ~~Locate the item / spell tables and settle the field widths.~~ Done — name 5
   units / 10 characters, description 12 / 24, verified by `names.py layout` and
   again against retail bytes.
2. ~~Translate the dialogue.~~ Done — 1,064 of 1,064.
3. ~~Write the fixed-width English.~~ Done — 317 records across all three tables.
4. ~~The character-name table.~~ Done — entry 48, 6-byte grid at `0x14C7`.
5. ~~The battle HP/MP plate.~~ Done — entry 48 `0x1509`–`0x154B`.
6. ~~The remaining UI strings.~~ Entry 48 complete; written into every overlay
   copy by content match.
7. ~~The digraph font and line-setter.~~ Done — `tools/patch_all.py`, one
   allocation pass over every English string in the project.
8. **Remaining work**, in the order it is worth doing:
   - the 16-byte image descriptor table, for the title-screen graphics;
   - entries 190, 208, 367, 831, 881, 893, 933, one of which is likely the
     new-game text crawl;
   - 無裝備 and the equipment dash filler, wherever they are written from;
   - the 44 over-read messages;
   - the 15 destination names whose offsets are still estimated;
   - a draw-routine change, if `Bu` / `Se` in the shop is worth a code patch.
