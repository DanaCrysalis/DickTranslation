# The translation

All 1,064 clean dialogue messages are translated. The English lives in column J
(`English translation`) of `dialogue.xlsx`; the Chinese in column G is untouched
except for re-decoding, and column I (glyph indices) is the source of truth for
both.

| | |
|---|---|
| messages translated | 1,064 of 1,064 clean |
| source units | 48,108 |
| English units | 67,728 |
| growth | **1.41×** |
| messages over the 252-unit ceiling | 0 |

Per entry: 23 → 210, 249 → 294, 390 → 162, 625 → 244, 794 → 154.

The 1.41× figure is well under the 1.5× planning estimate in STATUS.md, and
**no message needed splitting.** The u8 unit count is therefore no longer the
binding constraint it was expected to be — see "The real ceiling" below.

## Sheets

| sheet | what it holds |
|---|---|
| `Dialogue` | column J is the English, one line per speaker block |
| `Glossary` | ~170 terms: people, places, items, spells, plus the naming rules |
| `Issues` | ~180 rows: map corrections, retail typos, open questions, tooling risks |
| `Item-Spell-Monster` | 235 records, all translated |
| `UI strings` | all five battle overlays, not just entry 48 |

`Glossary` is terminology only. Anything that is a *defect* — a bad glyph
reading, a writers' typo, a scanner artefact — is in `Issues`, sorted map
corrections → open questions → notes → typos.

## The real ceiling: 252 units, not 255

**Every clean message's unit count is a multiple of 12.** All 1,064 of them.
Messages are padded to whole lines, so the effective ceiling is not the u8's 255
but the largest multiple of 12 below it:

```
252 units = 21 lines = 504 Latin characters
```

That is exactly the length of the longest retail message, which is not a
coincidence — it is the ceiling, not a near miss.

## Speaker turns start on a fresh line

Within a message, a new speaker generally begins at a 12-unit boundary, padded
with `0x0066`. 399 of ~464 internal turn breaks land exactly on one. The
remainder pack two short turns onto a shared line, which the retail script does
when it is running out of room.

The English mirrors this. In column J, **each newline-separated block starts a
fresh 12-unit line**; blocks may contain two short turns packed together. A
line-setter should wrap each block at 24 characters and pad to a multiple of 24.

Budget arithmetic, per message:

```
units = sum over blocks of ceil(len(block) / 24) * 12     must be <= 252
```

Short one-line NPC barks are the expensive case: a 12-unit source line costs 12
units in English too even if the English is three words, because of the rounding.
Dense exposition is the other expensive case, for the opposite reason.

## ASCII only

`mkfont.py` builds Latin cells from `chr(32..126)`. The English therefore uses
straight quotes and `--`, never curly quotes or en/em dashes. Verified: zero
non-ASCII characters across all 1,064 translations.

## Runtime-filled cells in dialogue

FORMATS.md documents engine-filled units for the *UI tables*. They occur in
dialogue too, in exactly one place:

```
e390 m2   商人Ａ：...我出價　　　元！！
```

Three `0x0066` cells between 價 and 元 receive the merchant's offer price at
draw time. They are written as `~~~~~~` in column J — two characters per
preserved cell, matching `uitext.py`'s convention — and flagged in column K.
Overwriting them breaks the substitution.

A sweep of all five entries found no other case. The other 17 mid-sentence gaps
are layout spacing: the advertisement at e23 m210, "Obtained ___" separators, and
琳's one-character name being centre-padded.

## Lines shared with the UI tables

Several dialogue messages are the *same strings* as records `uitext.py` already
translates, so the wording must match or the game will say two different things
for one condition:

| message | English |
|---|---|
| e23 m83, 此物品不能使用 | `Can't use that!` |
| e23 m199, 重要物品，不可丟棄 | `Key item - can't drop!` |
| e23 m80, e249 m51, 全員體力恢復 | `Party healed!` |
| e23 m81/m82, e249 m52/m53 | the "not enough gold" family |
| e23 m84, 道具袋已滿 | the "bag is full" family |

## Naming rules

Recorded in full in the `Glossary` sheet; in summary:

- A transliteration of a name that has an English original takes that form —
  奧丁 → Odin, 薩摩亞 → Samoa, 美錫尼 → Mycenae, 艾薩克 → Isaac, 摩里斯 → Morris,
  羅蘭 → Roland, 哈樂德 → Harold.
- An invented name gets a plain romanisation — 那都 → Nadu, 蘭特馬里奧 → Lantomario,
  那塔迪斯特 → Natadist.
- Epithets stay epithets rather than becoming transliterations: 牙王 → Fang King,
  炎鬼 → Flame Demon.
- Ranks that are distinct in the source stay distinct in English. The four
  clerical ranks 神官 / 神父 / 修士 / 司祭 are Priest / Father / Monk / Cleric.
  侍衛長 is Captain of the Guard and 禁衛隊長 is Captain of the Palace Guard —
  both appear in one sentence at e23 m139.
- Mycenae is an **empire** (皇帝, 皇城), where Lantomario, Samoa and Bosa are
  kingdoms (國王, 王城). So 陛下 is "Your Imperial Majesty" for Gerard and "Your
  Majesty" elsewhere, and 皇城 is "imperial capital" against 王城 "royal capital".

### Two necklaces

The one distinction that will break the plot if it blurs:

- **沙淚項鍊 — the Sand Tear Necklace** is *Dick's*. The Chief's gift in chapter 1;
  it proves his birth as Prince of Ayafalen (e390 m66). Shortened once to
  淚項鍊 at e390 m62.
- **星水晶項鍊 — the Star Crystal Necklace** is *Lin's*. It wakes her sealed soul
  when the Sacred Stones break (e249 m244). The source calls it 手鐲 "bracelet"
  once at e249 m18, treated as a slip.

## Register

Mid-90s console JRPG, as specified. Villagers plain and chatty; royalty and
generals formal. Some characters carry a fixed register that the English holds
throughout:

| character | register |
|---|---|
| Ryan | sneering, needling — calls Dick 小鬼 "brat" throughout; it cracks only over Fran's death (e249 m152, m158) |
| Noron | rough and teasing — "lad", "girl", "Ha! Ha!" |
| Sakashu | near-silent. `......` and `...Yes, Your Highness` are most of his lines. e794 m47 says outright he is 不太愛講話，有點孤僻. The sparseness *is* the character |
| Isaac | polite, faintly formal — he spends chapter 4 asking for help and knows it |
| Fuzi Lorweid | contemptuous and thin-skinned; refuses counsel out of wounded pride |

## Narrative order vs file order

**Entry 249 is not only chapter 2.** It carries endgame scenes too, in a
different order from the file:

| messages | scene |
|---|---|
| m274–295 | the *first* Dias encounter and Fran's death — early game |
| m0–234 | the Samoa arc |
| m235–273 | the ending: final battle, Lin's revelation, her departure |

Translated in file order; read in narrative order.

## Not dialogue

`e23 m210` is an advertisement for the game's own June release, crediting
新科技軸心, sitting at the end of the script entry. Translated literally. It may
be better left in Chinese or repurposed as a patch credit.

## The item and spell table

All 235 records are translated. The field budget is **10 Latin characters for a
name and 24 for a description** — 5 and 12 cells at two letters each, verified
with `names.py layout` after the documented offsets turned out to be wrong.

### Abbreviation rule

Ten characters is tight enough that most two-word names do not fit. In order:

1. If the full form is exactly 11, **delete the space**: `SilverHelm`,
   `RoyalCrown`, `BronzeMail`, `FlameAegis`, `MagicStaff`, `DeepFreeze`,
   `BoltMirror`. This is period-correct for a mid-90s JRPG item list and keeps
   both words readable.
2. If it is 12 or more, **clip the modifier, never the type word** — the type is
   what a player scans a shop list for: `Silv Sword`, `Pala Crown`, `Sapph Cuff`.

Type words are fixed: Sword / Sabre / Dirk / Spear / Bow / Axe / Claws / Staff /
Fist; Helm / Pin / Band / Sash / Crown / Hat; Mail / Plate / Armor / Robe / Vest /
Veil / Gi; Aegis and Cuff. Aegis is forced — "Iron Shield" is eleven characters
and no abbreviation of "Iron" rescues it.

### Names that could not keep their Glossary form

The dialogue keeps the full form; only the table shortens.

| Glossary | table |
|---|---|
| Holy Cross Staff | `Holy Cross` |
| Lamp of Guidance | `Guide Lamp` |
| Wings of the Desert | `DesertWing` |

Neither necklace appears in the table at all, so 沙淚項鍊 and 星水晶項鍊 cannot
blur through this route.

### Collisions resolved

- 解毒草 keeps **Antidote**; the spell 解毒咒 becomes **Detox**.
- 勇者 keeps **Hero** (Hero Sword, Hero Aegis); 英雄盾 becomes **BraveAegis**.
- 稻妻護腕 becomes **Levin Cuff** so it stays distinct from 雷電頭帶 Bolt Band —
  the source uses two different words for lightning.
- 冥王 is **Hades** throughout the descriptions; "the Underworld King" cannot fit.
- 幻滅聖咒 in the table and 幻滅聖炎 in dialogue are treated as one spell: 咒 is
  the generic suffix every spell here carries. Table `Holy Flame`, dialogue
  "Phantom Holy Flame".

### Duplicate records are real

極凍烈風 and 皇極破 each appear twice with identical descriptions, and 絕殺斷宙斬 /
絕殺斷宙閃 differ only in the fifth character. Almost certainly per-character
variants of one ultimate. Translated identically — nothing in the data
distinguishes them and inventing a difference would be inventing content.

## What is left

1. **UI strings.** ~125 rows still `todo` in the sheet, plus the destination
   table's exact field widths, which need `tblprobe.py` over `0x9390`-`0x9760`.
2. ~~The character-name table~~ — found and translated. Entry 48, 6-byte grid
   based at `0x14C7`, nine names: Darrel, Dick, Isaac, Lin, Fran, Noron, Nadia,
   Ronto, Sakash. Three cells is six Latin characters, which shortens Darrell and
   Sakashu on screen; the dialogue keeps both in full. The **battle HP/MP plate**
   is still unfound and is now the only located-nothing item left.
3. **The 0x39-stride table** after the destination list in every battle overlay,
   and whatever bare array holds the 76 orphan glyphs.
4. **The eleven over-read messages** — e23 m196, e249 m17/m99, e625 m197/m216,
   e794 m10/m16/m18/m24/m25/m94. (An earlier revision of this file called them
   "the eight"; the list has always had eleven entries, and the sheet flags 44
   over-read messages in total, of which these are the ones called out
   individually.)
5. **The digraph font and the line-setter**, per STATUS.md.
