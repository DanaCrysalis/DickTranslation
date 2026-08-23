#!/usr/bin/env python3
"""
glyphdump.py - make the game display a chosen block of glyphs so they can be read

Overwrites entry 23 message 61 with a run of consecutive glyph indices. That
message is the villager in Gulei Village who says

    村人：這裡是古雷村，我們這是常常下雨。下雨天容易使人心情沮喪，唉。。。

so load a save in that town, talk to him, and screenshot - the glyphs shown
are that index range, in order. He repeats on every talk, so each pass is
load, talk, screenshot rather than replaying the unskippable intro.

Pass --intro to target the opening line (entry 23 message 0) instead.

    python glyphdump.py DICK.DAT 0        # shows indices 0x000-0x020
    python glyphdump.py DICK.DAT 33       # shows 0x021-0x041
    python glyphdump.py DICK.DAT --revert # restore the original line

Each pass shows 33 glyphs; the game wraps at twelve per line, so they read as
12 + 12 + 9. Work upward in steps of 33.

The replacement always fills exactly the original 36 units, padded with the
full-width space 0x0066, so message length never changes and neither the
entry's offset table nor the archive TOC needs rebuilding.
"""
import os
import shutil
import sys

ENTRY_BASE = 0x1E5AA6          # entry 23 within DICK.DAT

# both targets are 36 units, so a patch never changes any message length
# (count-byte offset, unit count). All are exact, so a patch never changes a
# message's length and neither the offset table nor the archive TOC moves.
TARGETS = {
    "bridge": (ENTRY_BASE + 0x39C7, 84),  # msg 62, villager by the town entrance
    "rain":   (ENTRY_BASE + 0x397E, 36),  # msg 61, villager who complains about rain
    "intro":  (ENTRY_BASE + 0x0FA1, 36),  # msg 0, Lin's opening line
}
DEFAULT = "bridge"
PER_PASS = 81   # 84 units less three trailing spaces
SPACE = 0x0066

ORIGINAL_BRIDGE = [
    0x0022, 0x0036, 0x0018, 0x0009, 0x000a, 0x00ac, 0x0032, 0x01a4, 0x01a5,
    0x0168, 0x00d3, 0x004a, 0x004b, 0x01a6, 0x01a7, 0x01a8, 0x01a9, 0x0011,
    0x0169, 0x005b, 0x0016, 0x01a8, 0x01a9, 0x01a2, 0x0015, 0x0009, 0x000a,
    0x00af, 0x0004, 0x0030, 0x000d, 0x01aa, 0x0011, 0x01ab, 0x019b, 0x0022,
    0x01ac, 0x01ad, 0x0017, 0x000c, 0x0026, 0x0028, 0x01a4, 0x0087, 0x0088,
    0x0148, 0x01b1, 0x039f, 0x0172, 0x0173, 0x0030, 0x009a, 0x009b, 0x009c,
    0x005a, 0x03a0, 0x0011, 0x022c, 0x019b, 0x022d, 0x0172, 0x0173, 0x000b,
    0x0218, 0x03a1, 0x035e, 0x0016, 0x008e, 0x004b, 0x01f1, 0x01a9, 0x0011,
    0x03a2, 0x03a3, 0x012e, 0x00c7, 0x00ba, 0x008f, 0x0177, 0x00bd, 0x0017,
    0x0066, 0x0066, 0x0066]

ORIGINAL_INTRO = [0x0066, 0x000f, 0x0018, 0x005d, 0x005e, 0x0034, 0x000b, 0x0005,
            0x0067, 0x0068, 0x0011, 0x0022, 0x0069, 0x0064, 0x001a, 0x006a,
            0x0009, 0x0067, 0x0068, 0x0011, 0x006b, 0x006c, 0x0022, 0x000c,
            0x006d, 0x0000, 0x006e, 0x0016, 0x0039, 0x004c, 0x006f, 0x0070,
            0x0071, 0x0072, 0x0017, 0x0066]

ORIGINAL_NPC = [0x0022, 0x0036, 0x0018, 0x0034, 0x0033, 0x000b, 0x006c, 0x019b,
                0x0022, 0x0016, 0x0009, 0x000a, 0x0034, 0x000b, 0x00e9, 0x00e9,
                0x0056, 0x019c, 0x0017, 0x0056, 0x019c, 0x0046, 0x02ac, 0x02ad,
                0x01a2, 0x0036, 0x010a, 0x00f6, 0x039e, 0x037e, 0x0016, 0x022b,
                0x0017, 0x0017, 0x0017, 0x0066]

ORIGINALS = {"bridge": ORIGINAL_BRIDGE, "rain": ORIGINAL_NPC,
             "intro": ORIGINAL_INTRO}


def pack(units):
    out = bytearray()
    for u in units:
        out += bytes([u & 0xFF, u >> 8])
    return bytes(out)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    path = sys.argv[1]
    revert = "--revert" in sys.argv
    which = DEFAULT
    for name in TARGETS:
        if "--" + name in sys.argv:
            which = name
    count_off, unit_count = TARGETS[which]
    units_off = count_off + 1
    original = ORIGINALS[which]
    per_pass = unit_count - 3

    if revert:
        units = original
    else:
        start = int(sys.argv[2], 0)
        idx = list(range(start, start + per_pass))
        units = idx + [SPACE] * (unit_count - len(idx))

    with open(path, "rb") as f:
        f.seek(count_off)
        if f.read(1)[0] != unit_count:
            print(f"unit count at 0x{count_off:X} is not {unit_count} - "
                  f"wrong file or already modified elsewhere, aborting")
            return 1

    backup = path + ".bak"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
        print(f"backup written to {backup}")

    with open(path, "r+b") as f:
        f.seek(units_off)
        f.write(pack(units))

    if revert:
        print(f"original {which} line restored")
        return 0

    print(f"target '{which}' now shows glyph indices "
          f"0x{start:03x}-0x{start + per_pass - 1:03x}")
    for ln in range(0, per_pass, 12):
        box, row = divmod(ln // 12, 3)
        print(f"  box {box + 1} line {row + 1}: "
              + ' '.join(f"{v:03x}" for v in units[ln:ln + 12]))
    print(f"\ntalk to the '{which}' NPC, screenshot every box, then run with "
          f"{start + per_pass} next")
    return 0


if __name__ == "__main__":
    sys.exit(main())
