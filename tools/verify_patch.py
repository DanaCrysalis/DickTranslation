#!/usr/bin/env python3
"""
verify_patch.py - compare a patched archive against a clean one

The decode check inside patch_all.py can only see the fields it wrote. It cannot
see a write that landed somewhere it never meant to go, which is exactly what
broke the battle screen: content matching without a record header put English
into image and code entries, and the field check passed while the game filled
with noise.

This checks the other direction. It reads both archives' tables of contents and
asks, entry by entry, WHAT CHANGED AND WHY.

    python tools/verify_patch.py DICK.DAT.clean DICK.DAT.new
    python tools/verify_patch.py DICK.DAT.clean DICK.DAT.new --expect 23,249,390,625,794,1098,48

Expect exactly three kinds of change and nothing else:

  the five dialogue entries   grew, because English is longer than Chinese
  entry 1098                  identical size, fields rewritten in place
  entry 4 and the UI overlays identical size, glyph cells and strings rewritten

Any entry that changed size other than the dialogue five, or any entry that
changed at all without being on the expected list, is a bug - and on a 1,100
entry archive it is the only practical way to find one. The file size difference
should equal the sum of the dialogue growth exactly; if it does not, the packer
is doing something to the archive beyond replacing entries.
"""
import struct
import sys


def read_toc(path):
    with open(path, "rb") as f:
        n = struct.unpack("<H", f.read(2))[0]
        raw = f.read(n * 8)
    return [struct.unpack_from("<II", raw, i * 8) for i in range(n)]


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    a, b = sys.argv[1], sys.argv[2]
    expect = set()
    if "--expect" in sys.argv:
        expect = {int(x) for x in sys.argv[sys.argv.index("--expect") + 1].split(",")}

    ta, tb = read_toc(a), read_toc(b)
    da, db = open(a, "rb").read(), open(b, "rb").read()
    print("%s: %d entries, %d bytes" % (a, len(ta), len(da)))
    print("%s: %d entries, %d bytes  (%+d)" % (b, len(tb), len(db), len(db) - len(da)))
    if len(ta) != len(tb):
        print("\nENTRY COUNT DIFFERS - the packer added or dropped entries.")
        return 1

    grew, changed, same = [], [], 0
    for i, ((oa, sa), (ob, sb)) in enumerate(zip(ta, tb)):
        A, B = da[oa:oa + sa], db[ob:ob + sb]
        if sa != sb:
            grew.append((i, sa, sb))
        elif A != B:
            n = sum(1 for x, y in zip(A, B) if x != y)
            changed.append((i, sa, n))
        else:
            same += 1

    print("\n%d entries identical" % same)
    print("\n%d entries CHANGED SIZE:" % len(grew))
    total = 0
    for i, sa, sb in grew:
        total += sb - sa
        flag = "" if i in expect or not expect else "   <-- UNEXPECTED"
        print("  entry %-5d %8d -> %8d  %+7d%s" % (i, sa, sb, sb - sa, flag))
    print("  sum of growth: %+d" % total)
    if total != len(db) - len(da):
        print("  MISMATCH: the archive grew by %+d but its entries grew by %+d."
              % (len(db) - len(da), total))
        print("  The difference is header, padding or alignment the packer is")
        print("  handling differently from the original - worth understanding")
        print("  before trusting the build, since anything that reads this file")
        print("  by absolute offset rather than through the table will break.")
    else:
        print("  matches the file size difference exactly.")

    print("\n%d entries changed IN PLACE:" % len(changed))
    for i, sz, n in sorted(changed, key=lambda t: -t[2])[:40]:
        flag = "" if i in expect or not expect else "   <-- UNEXPECTED"
        print("  entry %-5d %8d bytes, %6d differ (%.2f%%)%s"
              % (i, sz, n, 100.0 * n / max(sz, 1), flag))
    if len(changed) > 40:
        print("  ... and %d more" % (len(changed) - 40))

    if expect:
        bad = [i for i, _, _ in grew if i not in expect]
        bad += [i for i, _, _ in changed if i not in expect]
        if bad:
            print("\n%d UNEXPECTED ENTRIES were modified: %s"
                  % (len(bad), ", ".join(str(i) for i in sorted(set(bad)))))
            print("Each one is a write that went somewhere it was not aimed.")
            return 1
        print("\nOnly the expected entries were modified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
