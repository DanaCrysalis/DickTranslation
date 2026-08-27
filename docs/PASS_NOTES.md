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

---

# Resolution (after the full dialogue translation)

## Your finding 2 was right, and later docs overruled it wrongly

This file said duplicate glyphs are real and duplicate-detection has false
positives. `STATUS.md` and `CONTINUING.md` later asserted the opposite. **This file
was right.** `0x2f9` and `0x660` are both 鱗 and both correct — `0x2f9` is item-table
vocabulary (龍鱗甲, 龍鱗盾, neighbours 冑 護 盾 腕) with zero dialogue uses, `0x660`
has one dialogue use and no item uses. Allocation did not deduplicate across corpora.

The specific pair cited here, `0x353`/`0x524`, is currently mapped 越/愈 and is worth
re-rendering in that light. Same for `0x55A` 鑲, `0x5EA` 筋, `0x66D` 脊.

## Your finding 3 became the main working method

Context decoding did indeed beat duplicate detection. Translating the whole script
sharpened it into two tests, now in `CONTINUING.md`: the **zero-good-use test**
(does the index read correctly *anywhere* else?) and the **bigram profile** (list
every bigram the glyph takes part in; is any of them a real word?). Together they
found 18 more wrong readings. `data/glyph_bigram_audit.csv` carries the profile.

## The 0x123 correction here is wrong

> **0x123 is 閒, not 間** — 0x4EE is the real 間

Both halves are wrong. `0x123` is 間 (突然間, 房間, 一段時間, 之間) and `0x4EE` is
食 (飲食). `STATUS.md` carried the same error.

## The 13 left unmapped — all now have readings

| index | then | now | how |
|---|---|---|---|
| `0x54E` | 「X錫尼」 | 鎂 | correct — the retail script spells the continent both 美錫尼 (15) and 鎂錫尼 (4) |
| `0x584` | 剿/剷 | 剷 | correct — 山賊已經被剷除 |
| `0x58B` | 駐/把/看 | **仍** | none of the three: 駐, 把, 看 are all occupied. Not a 守-compound — 還有一個山賊仍守在門口. Rendered |
| `0x5C5` | 遷/還 | 遷 | correct — 早點遷回隆恩內爾皇城 |
| `0x660` | 金-radical, 鑽 taken | **鱗** | 魚 radical, not 金 — 撿到金色的鱗片. Rendered |
| `0x505` | 一臉X喪 | 垂 | **still open.** 沮 is occupied; 頹 and 懊 are absent and fit; 垂 may be right as a contraction of 垂頭喪氣. No translation impact |
| `0x556` | unused | 睞 | **correct after all** — zero *dialogue* uses, but two item descriptions: 受女士青睞, 武鬥家青睞的硬水晶 |
| `0x559` | unused | 蠶 | **correct after all** — 輕薄的蠶絲製成的長衣 |
| `0x5B2` | single use | 龐 | correct — 龐德隆利山, 8 uses |
| `0x5E3` | 老闆：X！真煩 | 噴 | **still open**, and does not need solving. Both uses are a snort of contempt; any dismissive English reading is correct |
| `0x5FF` | (attributed here) | 吼 | correct — 聽到吼叫聲. The 老闆：X！真煩 context actually belongs to `0x5E3` |
| `0x643` | 卡X, a name | 席 | correct — 卡席, General of Sal in entry 794 |
| `0x658` | single use | 攏 | **retail typo, not a map error** — 攏爾 for 撒爾 at e794 m26. Provable: m90 is the same speech and spells it 撒爾 |

## One more note on 0x556 and 0x559

They were filed as unverifiable on the strength of zero dialogue uses. That was a
method error: the dialogue is one corpus, the item / spell / monster and UI tables
are another. Check both before calling a glyph uncheckable.


---

## Later corrections to this file

Three more map errors were found after this pass, all in the ITEM corpus, which
this pass could not see — it only ever read the dialogue.

| slot | this file / charmap said | is |
|---|---|---|
| `0x2cb` | 屑 | **屠** — 屠龍劍, 屠龍槍, 勇者屠龍時所用 |
| `0x2e8` | 餞 | **燄** — 火燄頭盔 |
| `0x5ea` | 箭 / 筋 | **節** — duplicates `0x5be`, zero uses in any dumped corpus |
| `0x28c` | *(unmapped)* | **狂** — 狂亂擊, 狂猛擊 |
| `0x317` | *(unmapped)* | **X** — a Latin letter. X字斬 is named with the letter |

`0x317` is worth dwelling on. The bigrams said 十字斬, 十 is a real word, and the
reading was obvious — and wrong. It is a duplicate of `0x0263` X, the third
cross-corpus duplicate found in this project. Render before believing a reading,
however plausible the context makes it.

The map is now 1,688 entries.
