#!/usr/bin/env python3
"""
orphan_scan.py - locate the corpus that the ORPHAN glyph indices belong to

Slots were allocated on first use, so a font slot that carries a real character
cannot be unreferenced. Cross-referencing the three dumped corpora (dialogue by
glyph index, the entry-1098 name table and the overlay UI tables by character)
leaves 76 mapped slots that nothing points at. Their vocabulary reads as monster
and special-attack naming - 鳳凰 虎 犬 隕 砲 旋 焦 煌 鋼 翡翠 璽 鎗 牌 筒 - and they
fall in consecutive runs, which is what a contiguous name table produces.

This scans the whole archive for those indices as little-endian u16s and reports
CLUSTERS: places where several different orphan indices occur close together.
One stray match is noise; six orphan indices inside 64 bytes is a name table.

Why not dickdat.py find: menu labels space their characters apart (攻 · 擊), so a
bigram like 鳳凰 need not be adjacent, and a fixed-pattern search misses it. This
searches by content and lets the clustering find the layout.

    python tools/orphan_scan.py DICK.DAT
    python tools/orphan_scan.py DICK.DAT --window 96 --min 3
    python tools/orphan_scan.py DICK.DAT --all      # every hit, not just clusters

Note: matches are reported at BOTH even and odd byte offsets. Script entries put
their u16s at odd file offsets (there is a leading type byte), so an even-only
scan would miss them.
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_toc(path):
    with open(path, "rb") as f:
        n = struct.unpack("<H", f.read(2))[0]
        raw = f.read(n * 8)
    return [struct.unpack_from("<II", raw, i * 8) for i in range(n)]


def load_charmap():
    p = os.path.join(HERE, "data", "charmap.json")
    return {int(k, 16): v for k, v in json.load(open(p, encoding="utf-8")).items()}


# The 76 slots no dumped corpus references. Regenerate with --recompute if the
# dialogue / item / UI dumps change.
ORPHANS = [
    0x00BC, 0x0143, 0x0145, 0x017F, 0x01CC, 0x0208, 0x0209, 0x0214, 0x0215,
    0x0216, 0x0263, 0x0291, 0x0305, 0x0306, 0x0307, 0x0308, 0x030A, 0x030D,
    0x0310, 0x0315, 0x0319, 0x031C, 0x031E, 0x0336, 0x0453, 0x0454, 0x0458,
    0x045B, 0x045D, 0x045E, 0x0463, 0x0481, 0x0484, 0x0485, 0x057F, 0x05A4,
    0x05A6, 0x05A8, 0x05A9, 0x05BA, 0x05C8, 0x05C9, 0x05CA, 0x05CB, 0x05CC,
    0x05CF, 0x05D0, 0x05D1, 0x05D2, 0x05D4, 0x05D5, 0x05D6, 0x05D9, 0x05DA,
    0x05DD, 0x05DE, 0x05E0, 0x05E1, 0x05E2, 0x05E6, 0x05E9, 0x05EA, 0x05EB,
    0x05EC, 0x0633, 0x0634, 0x0635, 0x063B, 0x063C, 0x0644, 0x0647, 0x0648,
    0x064B, 0x0656, 0x0683, 0x0692,
]

# Latin and punctuation slots are weak evidence - they turn up in any binary.
WEAK = {0x0143, 0x0145, 0x0263, 0x0291}


def entry_of(toc, off):
    lo, hi = 0, len(toc) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        o, s = toc[mid]
        if off < o:
            hi = mid - 1
        elif off >= o + s:
            lo = mid + 1
        else:
            return mid, off - o
    return None, off


def scan(path, window, minimum, show_all):
    cm = load_charmap()
    data = open(path, "rb").read()
    toc = read_toc(path)
    print("%d bytes, %d entries, hunting %d orphan indices\n"
          % (len(data), len(toc), len(ORPHANS)))

    hits = []
    for idx in ORPHANS:
        pat = struct.pack("<H", idx)
        start = 0
        while True:
            i = data.find(pat, start)
            if i < 0:
                break
            hits.append((i, idx))
            start = i + 1
    hits.sort()
    print("%d raw hits\n" % len(hits))

    if show_all:
        for off, idx in hits:
            e, rel = entry_of(toc, off)
            print("0x%08x  entry %-5s +0x%-8x  0x%03x %s"
                  % (off, e, rel, idx, cm.get(idx, "?")))
        return

    groups, cur = [], []
    for h in hits:
        if cur and h[0] - cur[-1][0] <= window:
            cur.append(h)
        else:
            groups.append(cur)
            cur = [h]
    groups.append(cur)

    ranked = []
    for g in groups:
        strong = {i for _, i in g if i not in WEAK}
        if len(strong) >= minimum:
            ranked.append((len(strong), g))
    ranked.sort(key=lambda t: -t[0])

    if not ranked:
        print("no cluster reached %d distinct strong indices within %d bytes.\n"
              "Try --window 128 --min 2, or --all and read the hits by hand."
              % (minimum, window))
        return

    for n, g in ranked[:40]:
        e, rel = entry_of(toc, g[0][0])
        span = g[-1][0] - g[0][0]
        print("=== %d distinct indices in %d bytes - file 0x%08x, entry %s +0x%x"
              % (n, span, g[0][0], e, rel))
        print("    " + " ".join("%03x:%s" % (i, cm.get(i, "?")) for _, i in g))
        a = max(0, g[0][0] - 32)
        b = min(len(data), g[-1][0] + 34)
        run = [struct.unpack_from("<H", data, o)[0]
               for o in range(g[0][0] & ~1, b - 1, 2)]
        print("    as u16 from the first hit: "
              + "".join("_" if v in (0, 0x66) else cm.get(v, ".") for v in run[:48]))
        print()
    print("Read the decoded run: if it says monster names, that is the table.\n"
          "Then note the stride between records and hand it back.")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    window = int(sys.argv[sys.argv.index("--window") + 1]) if "--window" in sys.argv else 64
    minimum = int(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else 4
    scan(path, window, minimum, "--all" in sys.argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
