# Glyph passes 0x4B0–0x6A0 — results

483 new index→character mappings, verified against the decoded script.
Coverage by text volume: **96.0% → 98.0%**. Merged map: 1,603 entries.

Files: `charmap_additions.json` (new only), `charmap.json` (merged, drop-in
replacement for `data/charmap.json`).

## Three findings that change the method

**1. The glyph table ends at 0x6A0 (1696).** Screens for 1697+ render blank, and
0x593 (1427) is a second blank slot inside the range. `STATUS.md` says "the font is
larger than the script's index range, so more slots exist above 0x69b that are
certainly unused" — there is no such headroom. An English patch has ~95 repaintable
slots plus the unused duplicates below, not an open tail.

**2. Duplicate glyphs are real, so duplicate-detection has false positives.**
`CONTINUING.md` treats two indices mapping to one character as "almost always a
misreading." But 0x353 and 0x524 are both 越, both used, in overlapping chapters
(0x353 in entries 23/249/390/625; 0x524 in 249/390). The allocator did not dedupe.
Five further pairs are duplicates whose second slot the script never references:
0x55A 鏡, 0x5CD 禁, 0x5D3 藝, 0x5EA 箭, 0x64B 慣, 0x66D 祭. These are the best
repaint targets available — the glyph exists, nothing points at it.

**3. Context decoding beats duplicate-detection, and needs no `DICK.DAT`.**
Column I of `dialogue.xlsx` carries per-message glyph indices, so a candidate map can
be applied and read back offline. This caught 46 errors in my own readings, including
the class `STATUS.md` calls invisible — wrong readings that collide with nothing.
Examples: 0x546 read as 靈 from its bitmap (雨 + three 口 + 巫) is 麗, from 華麗的場景
and 美麗的島; 0x515 read as 鬧 is 聞, from 傳聞說; 0x64E read as 塵 is 麾, from
先王麾下. Recommend adding this step to `CONTINUING.md` ahead of the duplicate check.

## Corrections to the existing map

- **0x123 is 閒, not 間** — 0x4EE is the real 間 (閒聊時他不小心說漏了嘴). Same shape
  class as the four errors already listed in `STATUS.md`.

## Your 1361 call

1361 is **笨**, not 舉: *好像一群笨蛋一樣* (e249 m227). 笨蛋 leaves 蛋 at 1362
accounted for; 舉 strands it. The template matcher independently returned 竿/竽/笚/苹
for that glyph — a 竹-radical cluster, i.e. 竹 over 本.

## The game's own typos

Not every odd decode is a map error. 氾瀾 for 氾濫 (e390 m141, 0x5BF is genuinely 瀾),
廣閣 for 廣闊 (e625, 0x60A is genuinely 閣), 整遍 for 整片. Worth flagging in the
spreadsheet so a translator doesn't chase them.

## Left unmapped (13)

Deliberately, per your rule about not guessing:

| index | evidence | note |
|---|---|---|
| 0x54E | 「X錫尼」place name, 4 uses | reads as 金+真 = 鎮, but 0x3DC is 鎮 (城下鎮/鎮守) and the same continent is 美錫尼 elsewhere |
| 0x584 | 山賊已經被X除 | 剿/剷 — bitmap is ?+刂, can't separate |
| 0x58B | 一個山賊X守在門口 | 駐/把/看 |
| 0x5C5 | 希望能早點X回皇城 | 遷, but 還 (0x146) also fits and shapes are close |
| 0x660 | 撿到〔297〕色的X片 | 金-radical, 鑽 taken |
| 0x505 0x556 0x559 0x5B2 0x5E3 0x5FF 0x643 0x658 | unused or single ambiguous use | |

0x556 (一臉X喪), 0x5FF (老闆：X！真煩), 0x643 (卡X, a name) each have one use that
doesn't pin the character.

## Method note

Glyph geometry: 38px cell pitch, 2× scale, ink origin (88, 242). Isolating the light
bevel layer alone recovers the exact 16×16 bitmap, which is what made pixel-level
adjudication possible. A Noto-CJK template matcher over all 13,452 Big5 characters
was too weak to drive transcription (~20% top-1) but reliable at radical level, and
useful as a tiebreaker — it was what confirmed 竹 for 笨.
