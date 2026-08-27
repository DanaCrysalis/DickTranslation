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
- **The item and spell table.** Entry 1098's field layout is settled and verified
  by probe (name +0x4C, 5 units; description +0x5C, 12 units), and **all 235
  records are translated** in the `Item-Spell-Monster` sheet. Budget is 10 Latin
  characters for a name and 24 for a description.
- **All five battle overlays are dumped**, not just entry 48. The four new ones
  carry the per-chapter world-map destination table, and nothing else that 48
  lacks.

## Numbers

| | |
|---|---|
| messages extracted | 1,064 clean (of 1,108 parsed; 44 over-read) |
| characters of dialogue | ~39,500 |
| distinct glyph indices used | 1,508 |
| characters mapped | 1,686 |
| coverage by text volume | 100% |
| highest index used by script | `0x069B` |
| font slots | 2,048 (353 blank) |
| slots the script never references | 540 |
| messages translated | 1,064 of 1,064 |
| English units | 67,728 (1.41× the source) |
| charmap corrections made while translating | 18 |

## Not solved

- **Menu and title artwork.** The title screen options (開始新遊戲 / 繼續舊冒險)
  are images, proven by the font not being resident in memory at the title. The
  image codec is understood but the 16-byte descriptor table that carries
  dimensions has not been found, so images cannot yet be re-encoded.
- ~~**Item, spell and monster names.**~~ Done — 235 of 235, see Solved above.
- ~~**Monster names: the game appears not to have any.**~~ **Wrong, twice.** A
  screenshot of the status screen showed 犬爪獸, and searching for its bytes found
  it at `0x081C1` — inside entry 1098, above the `0x4E20` limit that `names.py`
  had always stopped at. Two tables live up there: 49 special-attack and summon
  names at `0x07F21` and 29 plot items at `0x08F89`, all now translated. The
  `~0x8000` figure this repository had recorded from the start was correct, and
  the scan limit was what hid it. **The 76 orphan glyphs are explained too** —
  鳳凰 in 鳳凰魔法, 犬 in 犬爪獸, 隕 in 慧星隕石, 砲 in 鬥氣砲, 旋 in 迴旋斬, 煌
  in 星舞烈煌槍, 虎 in 虎之牙, 翡翠 in 翡翠手鐲. The reasoning below is kept
  because the *argument* was sound and the *premise* was not: it is true that
  every battle message calls the enemy generically 怪物 — 怪物脫逃, 怪物生命力增加,
  怪物防禦力增加, 怪物封住___魔法, 怪物使用一擊必殺, 怪物使用偷錢術,
  怪物降低我方守備力. A game that named its monsters would use the name in at
  least one of those seven lines. The "236 item / spell / monster records" figure
  this repository repeated for months was an assumption nobody checked.
- **76 mapped glyph slots that no dumped corpus references.** Their vocabulary
  reads as special-attack names — 鳳凰, 隕, 砲, 旋, 焦, 煌, 鋼, 虎, 犬. The likely
  home is a table stored as a **bare array** with no count prefix, like the class
  skill array at 0x09739, which `uitext.py` cannot see by construction. A
  0x39-stride table sits immediately after the destination table in every overlay
  and is the best candidate. Use `tools/tblprobe.py`.
- **Character names** (狄克 / 琳) and the battle HP/MP plate, which are not in the
  overlay string tables.

- **44 over-read messages.** 4% of the total; the length byte or a table slot
  behaves unexpectedly. Flagged in the spreadsheet, individually identifiable, and
  left untranslated.
- **The item name field width** (see FORMATS.md). Documented as 8 units, but the
  extracted sheet truncates at three characters. This is the difference between a
  16-character and an 8-character item-name budget and blocks writing item English.
- **How script entries reach memory.** No overlay in `loadmap.txt` loads entries
  23/249/390/625/794, so `cmd_loadmap` is missing a code path.


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

1. ~~Locate the menu / item / spell name tables.~~ Done — entry 1098, `names.py`.
   ~~Settle the name field width first.~~ Done — 5 units / 10 characters, verified
   by `names.py layout`.
2. ~~Translate the dialogue.~~ Done — 1,064 of 1,064, 1.41×, nothing over 252 units.
3. ~~Write the item / spell / monster English.~~ Done — 235 of 235.
4. ~~The character-name table.~~ Done — entry 48, 6-byte grid at `0x14C7`, nine
   names. The destination table is done too, all 29 across five chapters.
5. ~~The battle HP/MP plate.~~ Found — entry 48 `0x1509`-`0x154B`, five party
   name slots plus an `HP··MP` header. **Nothing in this repository is now in the
   looked-for-and-not-found state.**
6. ~~The remaining UI strings.~~ Entry 48 is complete: every row is either
   translated or shown not to be text. What is left is the fifteen destination
   names recovered from run-together records, whose offsets are estimated and
   want checking before a patch.
7. **The 16-byte image descriptor table** for the title-screen graphics
   (開始新遊戲 / 繼續舊冒險), which has never been searched for in earnest, and the
   **digraph font and line-setter** work below.
4. Design the digraph font: `font.py export`, draw 8x8 letter pairs into free slots,
   `font.py import`.
5. Write the line-setter: wrap at 24 columns, pad each line to exactly 12 units, and
   start each newline-separated block of column J on a fresh line. Preserve the three
   engine-filled cells at `e390 m2` (marked `~~~~~~`).
6. Resolve the 44 over-read messages.
