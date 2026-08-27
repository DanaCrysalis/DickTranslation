#!/usr/bin/env python3
"""
uidiff.py - dump ALL FIVE battle overlays and report what overlay 48 does not have

Every row of the UI strings sheet came from entry 48. FORMATS.md records that
battle strings live in entries 48, 258, 416, 612 and 790 - one per chapter - so
four of the five have never been read. Monsters and their attacks differ by
chapter, which makes those four the most likely home of the monster names.

This writes files rather than printing, because a full dump of five overlays is
thousands of records. What you want is the DIFFERENCE, and that is what lands in
ui_new.txt: every record found in 258 / 416 / 612 / 790 whose text does not
appear anywhere in 48.

    python tools/uidiff.py out/
    python tools/uidiff.py out/ --outdir report/

Writes, into the current directory unless --outdir is given:

    ui_new.txt    the readable report - new records per overlay, then a
                  combined unique list, ORPHAN-flagged records first
    ui_new.json   the same records as data, ready to paste into the sheet
    ui_all.json   every record from all five overlays, if the diff misses
                  something and the raw dump is wanted

Records containing one of the 76 ORPHAN glyph slots are marked [ORPHAN] and
sorted to the top. Those are slots that no dumped corpus references, and if the
monster table is here they are the characters it will be built from - 鳳凰 虎 犬
隕 砲 旋 焦 煌 鋼 翡翠.

No spreadsheet library is needed and dialogue.xlsx is not read: overlay 48 is
dumped directly and used as the baseline, which is the same thing the sheet is.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uitext  # noqa: E402

BATTLE = [48, 258, 416, 612, 790]

ORPHANS = {
    0x00BC, 0x0143, 0x0145, 0x017F, 0x01CC, 0x0208, 0x0209, 0x0214, 0x0215,
    0x0216, 0x0263, 0x0291, 0x0305, 0x0306, 0x0307, 0x0308, 0x030A, 0x030D,
    0x0310, 0x0315, 0x0319, 0x031C, 0x031E, 0x0336, 0x0453, 0x0454, 0x0458,
    0x045B, 0x045D, 0x045E, 0x0463, 0x0481, 0x0484, 0x0485, 0x057F, 0x05A4,
    0x05A6, 0x05A8, 0x05A9, 0x05BA, 0x05C8, 0x05C9, 0x05CA, 0x05CB, 0x05CC,
    0x05CF, 0x05D0, 0x05D1, 0x05D2, 0x05D4, 0x05D5, 0x05D6, 0x05D9, 0x05DA,
    0x05DD, 0x05DE, 0x05E0, 0x05E1, 0x05E2, 0x05E6, 0x05E9, 0x05EA, 0x05EB,
    0x05EC, 0x0633, 0x0634, 0x0635, 0x063B, 0x063C, 0x0644, 0x0647, 0x0648,
    0x064B, 0x0656, 0x0683, 0x0692,
}
# These turn up in any binary and mean nothing on their own.
WEAK = {0x0143, 0x0145, 0x0263, 0x0291}


def dump_one(path, cm):
    d = open(path, "rb").read()
    out = []
    for ch in uitext.scan(d, cm):
        for off, u in ch:
            out.append({"offset": "0x%05X" % off, "units": len(u),
                        "text": uitext.text_of(u, cm),
                        "orphans": sorted({v for v in u
                                           if v in ORPHANS and v not in WEAK})})
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    outdir = (sys.argv[sys.argv.index("--outdir") + 1]
              if "--outdir" in sys.argv else ".")
    os.makedirs(outdir, exist_ok=True)
    src = sys.argv[1]
    cm = uitext.load_charmap()

    dumps, missing = {}, []
    for n in BATTLE:
        for name in ("%04d.bin" % n, "%d.bin" % n):
            p = os.path.join(src, name)
            if os.path.exists(p):
                dumps[n] = dump_one(p, cm)
                print("entry %-4d %-12s %5d records" % (n, name, len(dumps[n])))
                break
        else:
            missing.append(n)
    if missing:
        print("MISSING: %s - run dickdat.py extract first" % missing)
    if 48 not in dumps:
        print("entry 48 is the baseline and is required.")
        return 1

    base = {r["text"] for r in dumps[48]}
    new, seen = [], set()
    for n in BATTLE:
        if n == 48:
            continue
        for r in dumps.get(n, []):
            if r["text"] in base:
                continue
            key = (r["text"], r["units"])
            if key in seen:
                continue
            seen.add(key)
            r = dict(r, overlay=n)
            new.append(r)

    new.sort(key=lambda r: (not r["orphans"], -len(r["orphans"]), r["offset"]))

    tpath = os.path.join(outdir, "ui_new.txt")
    with open(tpath, "w", encoding="utf-8") as f:
        f.write("Battle overlays 258 / 416 / 612 / 790 vs the 48 baseline\n")
        f.write("%d records in 48; %d records elsewhere that 48 does not have\n"
                % (len(dumps[48]), len(new)))
        f.write("%d of them contain an orphan glyph slot\n\n"
                % sum(1 for r in new if r["orphans"]))
        f.write("%-6s %-9s %5s  %s\n" % ("entry", "offset", "units", "text"))
        for r in new:
            mark = " [ORPHAN %s]" % " ".join("%03x" % o for o in r["orphans"]) \
                if r["orphans"] else ""
            f.write("%-6d %-9s %5d  %s%s\n"
                    % (r["overlay"], r["offset"], r["units"], r["text"], mark))
    json.dump(new, open(os.path.join(outdir, "ui_new.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(dumps, open(os.path.join(outdir, "ui_all.json"), "w",
                          encoding="utf-8"), ensure_ascii=False, indent=1)

    print("\n%d new records, %d with orphan slots"
          % (len(new), sum(1 for r in new if r["orphans"])))
    print("wrote %s, ui_new.json, ui_all.json" % tpath)
    return 0


if __name__ == "__main__":
    sys.exit(main())
