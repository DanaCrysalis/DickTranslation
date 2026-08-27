# Extending and verifying the character map

The font is decoded, so glyphs no longer have to be read off a screenshot. Render
the slot you want and read it:

```bash
python tools/font.py dump out/0004.bin sheet.png 0x4b0 0x6a0
python tools/font.py export out/0004.bin glyphs/     # one 16x16 PNG per slot
```

`glyphdump.py` still works and is documented below, but it is now only needed to
confirm how something looks *in situ*, not to recover shapes.

## Verifying by context — do this first

The single most productive check is decoding the script and reading it as Chinese:

```bash
python tools/dickdat.py text DICK.DAT script/ data/charmap.json
```

`dialogue.xlsx` carries per-message glyph indices in its own column, so a candidate
map can be applied and read back without touching `DICK.DAT` at all.

This is the only check that catches a wrong reading of a character that collides
with nothing. In one pass over the `0x4B0`–`0x6A0` range it corrected 46 readings,
including several that were pixel-plausible and had survived every other check:

| index | read as | actually | evidence |
|---|---|---|---|
| `0x546` | 靈 | **麗** | 華麗的場景 / 美麗的島 |
| `0x515` | 鬧 | **聞** | 傳聞說 |
| `0x64E` | 塵 | ~~麾~~ | **both wrong — `0x64E` is 役 (戰役). See STATUS.md** |
| `0x551` | 舉 | **笨** | 好像一群笨蛋一樣 |
| `0x5C4` | 氣 | **氛** | 沒有王城的氣氛 |

### Check the scan limit before concluding something is absent

`names.py` stopped at `0x4E20` for years on the belief that the icon sheet began
there. Two tables sat above it. That one constant supported two confident false
conclusions — that entry 1098 holds 235 records, and that the game does not name
its monsters — and both survived because every dump agreed with every other dump,
all of them reading the same truncated window.

**An absence is only evidence if the search covered the space.** Before writing
"not found", state what range was actually read. When a doc gives a figure that
your tooling cannot reproduce (here, `~0x8000`), suspect the tooling first: the
doc was written by someone looking at the game.

### Two geometry tests that settle a doubtful record

Overlay records carry a screen position (see FORMATS.md), and that makes the
question "is this text?" answerable rather than a matter of taste:

1. **Position.** `pos % 320` and `pos // 320` must give a sane x and y. A phantom
   record usually has `pos = 0x0000`, or a y of 0 with x near 260.
2. **Screen fit.** Glyphs are 16 pixels wide, so `x + 16 * n` must be at most 320.
   This alone kills every long phantom: a 38-unit "string" would need 608 pixels
   of a 320-pixel line.

Calibrated against the 152 records already translated in entry 48, the pair
resolved all 84 remaining doubtful rows without a single judgement call — 65 fail
outright, 8 are the item-menu grid, 9 are round low values, and 2 stay ambiguous.

**They only apply to position-headed records.** The destination table and the
character-name table are bare arrays with no position word, so they fail these
tests while being perfectly real. Check which kind of table you are in first.

### Low glyph index means small number

Before anything else, check whether the "text" is text. Slots were allocated on
**first use**, so the first characters the writers typed hold the lowest indices —
and any 16-bit numeric field with a small value decodes as one of them:

```
 0 一   1 裝   2 備   3 魔   4 法   5 你   6 妳   7 他
 8 她   9 我  10 們  11 是  12 不  13 對  14 好  15 琳
16 長  17 的  18 真  19 漂  20 亮  21 得  22 ，  23 。
24 ：  25 ！  26 ？  27 （  28 ）  29 〔  30 〕  31 ；
32 那  33 都  34 村  35 風  36 總  37 小  38 過  39 倒
40 也  41 挺  42 舒  43 服  44 只  45 剩  46 婦  47 女
```

So a record reading `也倒（〕男人這` is a run of small integers, and `的的的的的的的的`
is the byte pattern `11 11`. This produced four separate false readings in one pass:
a "0x39-stride table" that was `FF`-fill (丑 = 0x01FF, 妻 = 0x02FF); a "class skill
array" whose 法 was the value 4; two "character-name rows" whose 琳 was the unit
count 15; and a "numeric table" at 0x5A00 whose 敵 衛 城 were the ids 802, 401, 403.

It also cuts the other way, usefully. Inside a record that the scanner ran
together, the character between two strings is the next record's unit **count** —
`那都村魔古雷村備森林備` is 那都村, count 3, 古雷村, count 2, 森林, count 2. That
recovered every destination name without a re-dump.

**The test:** look up the indices. If most are below about `0x40` and the reading is
incoherent, it is numeric. Real text mixes high indices freely — the character-name
record at `0x014DB` has ten of eleven units above `0x9C`.

Read the sentence, not the glyph. And read it in **every** corpus — the three
most recent corrections (`0x2cb` 屠, `0x2e8` 燄, `0x5ea` 節) all came out of the
item table, which has no dialogue uses at all.

### Make every edit assert that it matched

A find-and-replace that silently does nothing is the most expensive kind of
mistake in this repository, because the file still looks edited. A stale line
survived a full documentation pass this way — the README went on claiming the item
names and the line-setter were outstanding after both were finished, because the
text being replaced had been reworded upstream and the replacement quietly no-op'd.
Assert on the match, or diff afterwards.

### Patching is a separate discipline from decoding

Reading the data right does not mean writing it back right. The reinsertion pass
broke the game five times, and not once because a translation was wrong:

- **Write back the same entry length.** Entry sizes are allocations, not
  measurements. See FORMATS.md.
- **Never write on a byte match alone.** Require the record header. Content
  matching without it puts English inside longer strings and inside code.
- **Verify from the other side.** A field-by-field decode check cannot see a write
  that landed where it was never aimed, which is exactly the failure that hangs the
  game. `tools/verify_patch.py` diffs the packed archive against a clean one and
  reports which entries changed and by how much; anything outside the expected list
  is a bug.
- **Compare file sizes first.** One command found the cause of a crash that four
  rounds of reasoning had missed.
- **Bisect rather than theorise.** `patch_all.py` has `--skip-ui`, `--skip-tables`
  and `--entries` for exactly this. Four builds isolated a crash that five guesses
  had not.

## UI strings are a separate job from dialogue

Menus, battle messages and status labels live in the code overlays, not in a
script entry, and use a different record format (see FORMATS.md). Work on them
with `tools/uitext.py`:

```bash
python tools/uitext.py dump out/0048.bin            # inventory one overlay
python tools/uitext.py patchall out --preset battle_full
```

Three traps, each of which cost a test cycle:

1. **Menu vocabulary is not in the dialogue charmap.** A record containing an
   unmapped index cannot be decoded and is skipped, which looks exactly like the
   record not existing. If something stays Chinese, dump the bytes and read the
   unknown glyph out of the font before assuming the string is missing.
2. **Tables are not always contiguous.** Requiring long chains of adjacent
   records silently skipped the spell schools and the whole retreat block.
3. **Some units are filled at runtime.** `·` receives digits and `_` receives a
   name; overwrite them and the substitution breaks. Mark them `~~` in a preset
   to preserve them, and start such strings with a space or the name will run
   straight into the text.

## The zero-good-use test

The sharpest check available, and the one that separates a **map error** from a
**retail typo**. Take the suspect glyph's *index* and look at every other place it
appears:

- A retail typo is a correct glyph used in one wrong place, so the index reads
  correctly everywhere else. 太 has 114 good uses and one 太家. 遭 has 9 good and two
  遭糕. 的 has 1,249 good and one 使的.
- A misread glyph reads wrongly **everywhere**, because the reading itself is wrong.

Applied to 38 suspicious decodes found while translating, 27 passed and 11 failed.
Every one of the failures was confirmed by render. Corroborate with two things:
whether the proposed correct character is absent from the whole map (see the
occupancy test below), and whether adjacent slots come from the same phrase — slots
were allocated in order of first use, so `0x1bb`=豈 `0x1bc`=更 `0x1bd`=糟 is
豈不是更糟 typed in one go.

## The bigram profile

The zero-good-use test fails if you test the wrong bigrams. `0x2a6` passed an early
pass with "40 good uses" because only 亙浪 and 亙大 were checked as suspect and
亙樹/亙弓/亙繩 were assumed good. All six of its bigrams were wrong: it is **巨**,
44 uses, and 巨樹/巨弓/巨繩 are the central nouns of chapter 4.

So don't hand-pick suspect bigrams. **List every two-character sequence the glyph
takes part in and ask whether any of them is a real word.**
`data/glyph_bigram_audit.csv` carries this for every glyph used 20 times or fewer —
1,167 of them, which is where essentially all the remaining risk lives.

## Check every corpus, not just the dialogue

`0x556` and `0x559` were once filed as "zero uses, can never be checked". Both were
wrong: they have zero *dialogue* uses but appear in item descriptions, where both
readings check out (青睞 "favour", 蠶絲 "silk"). The dialogue is 1,064 messages; the
item, spell and UI tables are a separate corpus and the tests above must cover them
too.

This is now the highest-yield check there is. Running the zero-good-use test over
the **item table** produced three corrections in one pass — `0x2cb` 屑→屠 (three
uses, all 屠龍, zero dialogue uses), `0x2e8` 餞→燄 (one use, 火燄頭盔), `0x5ea`
筋→節 — and, on the same day, one firm **non**-correction: `0x5c3` reads 早晨
correctly in its single dialogue use and wrongly as 星晨 three times in the item
table, which is a retail typo rather than a map error. Same test, opposite verdicts,
and only the second corpus makes the difference visible.

Also note what a slot-ordered table does to this reasoning. Entries 6 and 463 pair
glyph indices with a small number in ascending slot order (see FORMATS.md), so a
slot can be *referenced* without ever having been typed into text. "Referenced
nowhere" is weaker evidence of an undumped corpus than it looks.

## Duplicate and mismatch checks

Merge new readings against `data/charmap.json` and look for:

1. **Mismatches** — an index already mapped to a different character. One of the two
   readings is wrong.
2. **Duplicates** — two indices mapped to the same character.

**Duplicates are NOT conclusive, and this file previously said they were.**
A confirmed duplicate exists: `0x2f9` and `0x660` are both 鱗, both correct.
`0x2f9` has zero dialogue uses and appears only in item names (龍鱗甲, 龍鱗盾),
with neighbours 冑 護 盾 腕 — allocated inside the armour-name block. `0x660` has one
dialogue use and no item uses. **Allocation did not deduplicate across corpora.**

So a duplicate is evidence to check, not proof of error. Ask which corpus each slot
serves: if both are dialogue-resident, one reading is almost certainly wrong; if they
sit in different corpora, both may be right.

This does not weaken the *occupancy test*, which is the most useful consequence of
allocation-on-first-use:

> The font holds exactly the characters the writers typed. So "character X is absent
> from the 1,688-entry map" means "X appears nowhere in the game" — which makes a
> proposed reading being absent *consistent*, and a reading already held by another
> dialogue slot *impossible*.

That is what settled `0x1bd` (the render read 相, but 相 is `0x51` with 34 dialogue
uses) and `0x41f` (the render read 書, but 書 is `0x102` with 7 dialogue uses).

`0x353`/`0x524` are recorded here as 越 and 愈. Given duplicates are now known to be
real, that pair is worth re-rendering — the original claim in `PASS_NOTES.md` may
have been right.

## Bitmaps and readings are separate things

A glyph's pixels and its character label are independent artifacts. The map can be
wrong about what a glyph *means* while the bitmap is exactly right. Keep them
separate when reasoning: 496 screenshot-derived bitmaps matched the decoded font
perfectly at a time when dozens of their character labels were still wrong.

Practically: if you are checking the font or the renderer, use bitmaps. If you are
checking the map, use decoded sentences.

## The game's own mistakes

Not every strange decode is a map error. The retail script contains 氾瀾 for 氾濫,
廣閣 for 廣闊, and 整遍 for 整片, and roughly seventy more found while translating —
all logged in the `Issues` sheet of `dialogue.xlsx`. Confirm against the rendered
glyph before "correcting" a reading, and flag them for the translator rather than
silently normalising.

**But do not reach for "retail typo" on sight.** Of 38 odd decodes met while
translating, 11 were the map's fault, not the writers'. Run the zero-good-use test
above first — a script that never once uses 費, 價, 蠻, 糟 or 漠 is not a script with
charming typos, it is a map with five wrong readings.

## Reading a glyphdump pass (legacy method)

`glyphdump.py` overwrites a message with a run of consecutive glyph indices. Talk to
the NPC, screenshot, read the characters in order. **81 glyphs per pass**, drawn as
12 + 12 + 9 across three boxes. (The tool's own docstring says 33 in places; the code
uses 81 for the default `--bridge` target.)

```bash
python tools/glyphdump.py DICK.DAT 1200     # shows 0x4b0 onward
python tools/glyphdump.py DICK.DAT --revert # restore the real line
```

Targets, all 36 or 84 units so no message length ever changes:

| flag | who | units |
|---|---|---|
| `--bridge` (default) | villager at the town entrance in Gulei Village | 84 |
| `--rain` | villager who complains about the rain | 36 |
| `--intro` | Lin's opening line | 36 |

**Always restore `DICK.DAT.bak` before starting a fresh run** rather than relying on
`--revert` alone, and **verify the archive afterwards**:

```bash
python tools/script_edit.py verify out/0023.bin dialogue.xlsx 23
```

A dump pass leaves the message the same *length*, so nothing downstream notices it
until something unrelated fails and gets blamed. This has already cost one wasted
test cycle: a `push` experiment appeared to corrupt the bridge villager when in fact
the archive still carried the final `0x696` pass from a dump session.

If you do read from screenshots, note that the light face layer is drawn at
`-0x282` from the shadow, so an extracted bitmap sits two pixels up and two left of
the glyph as stored. That offset is why byte-level searches for the font failed for
so long.

## What's left (nothing, for dialogue)

Every glyph index the dialogue uses is now identified. The last 65 were resolved
by rendering them straight out of the font and reading them - no dumping, no
context inference. Among them were the three highest-frequency unknowns,
`0x286`/`0x287`/`0x288`; they had never appeared in a glyphdump pass because those
slots sit below 0x4B0.

**An earlier revision of this file called those three "the name 艾沙娜". They are
not a name.** They are three ordinary characters — 艾, 沙, 娜 — and the string 艾沙娜
occurs **zero** times in the script. The apparent frequency was 艾 alone (113 uses).
What they actually spell is three separate characters: 艾薩克 Isaac (53), 娜迪亞
Nadia (51) and 沙卡修 Sakashu (32). Decode before naming.

If a new unknown appears (menus and item tables use vocabulary the dialogue does
not), read it the same way:

```bash
python tools/font.py export out/0004.bin glyphs/   # then open glyphs/<index>.png
```

## Historical: what was left

`data/unmapped.txt` lists every index the script uses that isn't identified. 13
indices were deliberately left unmapped rather than guessed; each has an ambiguous
single use recorded in the notes from the last pass.

Coverage is 100% by text volume for the dialogue and complete for the item table.
**Three** indices remain unmapped, not thirteen — and one of them, `0x2be`, has
been rendered and is not a character at all (an empty box with a single grey line).
`data/unmapped.txt` is stale on two counts: it still lists `0x2c3` and `0x2c8`,
both settled, and its header still argues that the font contains no duplicate
bitmaps, which `STATUS.md` and `README.md` both retract.
