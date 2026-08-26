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
| `0x64E` | 塵 | **麾** | 先王麾下 |
| `0x551` | 舉 | **笨** | 好像一群笨蛋一樣 |
| `0x5C4` | 氣 | **氛** | 沒有王城的氣氛 |

Read the sentence, not the glyph.

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
item, spell, monster and UI tables are a separate corpus and the tests above must
cover them too.

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
> from the 1,686-entry map" means "X appears nowhere in the game" — which makes a
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

Coverage is 98%. The remaining glyphs mostly appear once or twice in the whole game,
and a translator reading in context will resolve them faster than this process will.
