#!/usr/bin/env python3
"""
tblprobe.py - identify the record structure of a glyph-index table in any entry

names.py's `layout` probe works because the record stride was already known.
This one derives the stride instead, so it can be pointed at an entry whose
format has not been worked out - which is what entries 6 and 463 need.

Method, in order:

1. PARITY. Script and data entries carry a leading type byte, so their u16s sit
   at ODD file offsets. Both parities are scored and the better one is used.
   Getting this wrong turns a clean table into noise, which is the single
   easiest way to misread one of these entries.

2. STRIDE. Classify every u16 as a mapped glyph index, 0x0066, 0x0000 or
   binary, then for each candidate stride ask how concentrated the glyph
   positions are modulo that stride. A real fixed-width table puts its text
   fields in the same columns of every record and scores near 1.0; unstructured
   data scores near the glyph density itself.

3. COLUMNS. With the stride fixed, report per-column statistics and a decoded
   sample, exactly like names.py layout, so the text fields can be read off.

    python tools/tblprobe.py out/0006.bin
    python tools/tblprobe.py out/0463.bin --from 0x2905 --to 0x3400
    python tools/tblprobe.py out/0006.bin --stride 4 --rows 40
    python tools/tblprobe.py out/0048.bin --from 0x9730 --to 0x9790 \
        --stride 4 --parity 1          # forced: read a region as a hexdump

A caution learned the hard way on entry 1098: a field can straddle the nominal
record boundary, so a text run that starts mid-record is normal. Read the
columns, not the record numbering.
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPACE = 0x0066


def load_charmap():
    p = os.path.join(HERE, "data", "charmap.json")
    return {int(k, 16): v for k, v in json.load(open(p, encoding="utf-8")).items()}


def classify(v, cm):
    if v == 0:
        return "z"
    if v == SPACE:
        return "s"
    if v in cm:
        return "g"
    return "b"


def score_stride(tags, stride):
    """How much a fixed-width table of this stride explains the glyph layout.

    Two things mark a real record grid: the glyphs concentrate in a few columns,
    AND some columns are DEAD (binary stats never decode as glyphs). Scoring
    concentration alone always prefers stride 2, because any alternating
    pattern satisfies it - the dead-column term is what separates a genuine
    record from a coincidence. Multiples of the true stride score similarly, so
    the smallest high scorer is usually the record, and the ranked list is
    printed rather than just the winner.
    """
    cols = [0] * stride
    total = 0
    for i, t in enumerate(tags):
        if t == "g":
            cols[i % stride] += 1
            total += 1
    rows = len(tags) / stride
    if total < stride * 3 or rows < 8:
        return 0.0
    hot = sum(c for c in cols if c > rows * 0.30)
    dead = sum(1 for c in cols if c < rows * 0.05)
    return (hot / total) * (0.15 + dead / stride)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]

    def opt(name, default=None):
        return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default

    cm = load_charmap()
    data = open(path, "rb").read()
    lo = int(opt("--from", "0"), 0)
    hi = int(opt("--to", str(len(data))), 0)
    hi = min(hi, len(data))
    rows_wanted = int(opt("--rows", "24"), 0)

    forced = opt("--parity")
    best = None
    for parity in ((int(forced),) if forced is not None else (0, 1)):
        start = lo + ((parity - lo) % 2)
        vals = [struct.unpack_from("<H", data, o)[0]
                for o in range(start, hi - 1, 2)]
        tags = [classify(v, cm) for v in vals]
        dens = tags.count("g") / max(1, len(tags))
        if best is None or dens > best[0] or forced is not None:
            best = (dens, parity, start, vals, tags)
    dens, parity, start, vals, tags = best
    other = 1 - parity
    print("%s: 0x%x..0x%x, parity %s (u16s at %s offsets), glyph density %.3f"
          % (os.path.basename(path), lo, hi, parity,
             "odd" if parity else "even", dens))
    if dens < 0.35:
        print("  NOTE: parity was chosen on glyph density and this region is "
              "mostly binary,\n  so the choice is weak. Script entries carry a "
              "leading type byte and put\n  their u16s at ODD offsets; if that "
              "disagrees with the line above, trust it\n  and re-run the region "
              "you care about with a narrower --from.")

    if dens < 0.02:
        print("\nAlmost no mapped glyph indices here - this region is not a "
              "text table, or the charmap does not cover it.")
        return 0

    ranked = sorted(((score_stride(tags, s), s) for s in range(2, 65)),
                    key=lambda t: -t[0])
    print("\nbest strides (u16 units / bytes):")
    for sc, s in ranked[:6]:
        print("   %2d units = %3d bytes   score %.3f" % (s, s * 2, sc))

    # A region with no fixed-width structure still produces a ranked list, and
    # picking its top entry invents a table that is not there. Require a real
    # score before auto-selecting; the synthetic reference table scores 0.65 and
    # a genuine record grid scores well above 0.25.
    FLOOR = 0.25
    if ranked[0][0] < FLOOR and "--stride" not in sys.argv:
        print("\nNO FIXED-WIDTH STRUCTURE DETECTED (best score %.3f, floor %.2f)."
              "\nThis region is not a record table, or its records are not "
              "uniform.\nRe-run with an explicit --stride to look anyway."
              % (ranked[0][0], FLOOR))
        stride = 8
        print("\nfalling back to a plain 8-unit listing for reading by eye.\n")
    else:
        # Multiples of the true stride score as well as the stride itself, so
        # take the SMALLEST stride within 75% of the best rather than the top.
        # Strides of 2 and 3 are excluded from the automatic choice: a two-column
        # alternation satisfies the concentration test almost for free, so they
        # score high on nearly any table and have won this selection three times
        # while the real record was 8 or 16. They are still listed above and can
        # be forced with --stride.
        thresh = ranked[0][0] * 0.75
        auto = min((s for sc, s in ranked if sc >= thresh and s >= 4),
                   default=ranked[0][1])
        stride = int(opt("--stride", str(auto)), 0)
        print("\nusing stride %d units (%d bytes), score %.3f"
              % (stride, stride * 2,
                 dict((b, a) for a, b in ranked).get(stride, float("nan"))))

    print("col  +off   glyph  zero  space  binary   sample")
    nrec = len(vals) // stride
    for c in range(stride):
        col = [vals[r * stride + c] for r in range(nrec)]
        g = sum(1 for v in col if classify(v, cm) == "g")
        z = sum(1 for v in col if v == 0)
        s = sum(1 for v in col if v == SPACE)
        b = len(col) - g - z - s
        sample = "".join(cm[v] for v in col[:10] if v in cm)
        print("%3d  +%03X   %5d %5d  %5d  %6d   %s"
              % (c, 2 * c, g, z, s, b, sample))

    print("\nfirst %d records decoded (_ = 0x0066 or 0x0000, . = binary):" % rows_wanted)
    for r in range(min(rows_wanted, nrec)):
        chunk = vals[r * stride:(r + 1) * stride]
        txt = "".join("_" if v in (0, SPACE) else cm.get(v, ".") for v in chunk)
        raw = " ".join("%04x" % v for v in chunk[:8])
        print("  0x%06x  %-24s  %s" % (start + r * stride * 2, txt, raw))
    return 0


if __name__ == "__main__":
    sys.exit(main())
