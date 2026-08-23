# Extending the character map

The font itself hasn't been located, so the map is built by making the game render
glyphs and reading them off screen.

## How it works

`glyphdump.py` overwrites a message with a run of consecutive glyph indices. Talk to
the NPC, screenshot, read the characters in order. 81 glyphs per pass, drawn as
12 + 12 + 9 across three boxes.

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

The bridge NPC is the best target: three boxes per talk, and re-talkable, so a pass
is load, walk, talk, screenshot.

**Always restore `DICK.DAT.bak` before starting a fresh run** rather than relying on
`--revert` alone.

## Reading a pass

The tool prints the expected layout box by box. Check it against the screenshot
before recording anything — if a known character doesn't land where predicted, the
pass is misaligned and the whole block would be wrong.

Then merge the 81 characters against `data/charmap.json`, in order, and check:

1. **Mismatches** — an index already mapped to a different character. Means one of
   the two readings is wrong.
2. **Duplicates** — two indices mapped to the same character. Almost always a
   misreading of a visually similar glyph; resolve by looking at how each index is
   used in the decoded script.

Both checks have caught real errors. Neither catches a wrong reading of a character
that appears nowhere else, so where a glyph is unused and the reading is uncertain,
leave it out.

## Verifying by context

The most reliable check is whether the decoded script reads as Chinese. `蠻癟` in
`計劃可以蠻癟進行了` was obviously wrong; the sentence demands `繼續`. Run:

```bash
python tools/dickdat.py text DICK.DAT script/ data/charmap.json
```

and read messages that use the new indices.

## What's left

`data/unmapped.txt` lists every index the script uses that isn't identified,
ranked by how often it appears. The script's highest index is `0x069b`.

Coverage is 96%; the remaining passes buy roughly 0.5% each, and the glyphs there
mostly appear once or twice in the whole game. A translator reading in context will
resolve those faster than this process will.
