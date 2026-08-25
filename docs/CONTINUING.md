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

## Duplicate and mismatch checks

Merge new readings against `data/charmap.json` and look for:

1. **Mismatches** — an index already mapped to a different character. One of the two
   readings is wrong.
2. **Duplicates** — two indices mapped to the same character.

**Duplicates are no longer conclusive.** The font contains genuine duplicate
characters: `0x353` and `0x524` are both 越, both used, in overlapping chapters. Slot
allocation was not deduplicated. When a duplicate appears, decide it by looking at
how each index is used in the decoded script, not by assuming a misreading.

A duplicate whose second slot the script never references is usually a real
duplicate, and is a good repaint target.

## Bitmaps and readings are separate things

A glyph's pixels and its character label are independent artifacts. The map can be
wrong about what a glyph *means* while the bitmap is exactly right. Keep them
separate when reasoning: 496 screenshot-derived bitmaps matched the decoded font
perfectly at a time when dozens of their character labels were still wrong.

Practically: if you are checking the font or the renderer, use bitmaps. If you are
checking the map, use decoded sentences.

## The game's own mistakes

Not every strange decode is a map error. The retail script contains 氾瀾 for 氾濫,
廣閣 for 廣闊, and 整遍 for 整片. Confirm against the rendered glyph before
"correcting" a reading — and flag them for the translator rather than silently
normalising.

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
`0x286`/`0x287`/`0x288`, which turned out to be the name 艾沙娜; they had never
appeared in a glyphdump pass because those slots sit below 0x4B0.

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
