#!/usr/bin/env python3
"""
patch_poc.py - proof of concept: replace one line of dialogue in DICK.DAT

Rewrites the game's first spoken line, entry 23 message 0, from

    琳：狄克這是你居住的村莊嗎？跟我居住的穆古村不太一樣，到處充滿活力。
    "Lin: Dick, is this the village you live in? It's quite different from
     Mugu Village where I live - this place is full of life."

to

    琳：狄克，這村莊不太一樣！
    "Lin: Dick, this village is quite different!"

Only verified glyph indices are used, and the replacement is padded with the
full-width space (0x0066) to the original unit count. That keeps the message
byte length identical, so neither the entry's offset table nor the archive
TOC needs rebuilding - the patch is a straight overwrite of 72 bytes.

    python patch_poc.py DICK.DAT          # writes DICK.DAT.bak first
    python patch_poc.py DICK.DAT --revert # put the original line back

Verifying by hand: entry 23 begins at file offset 0x1E5AA6, message 0's unit
count byte sits at +0x0FA1, and its 36 units run from +0x0FA2.
"""
import os
import shutil
import sys

# WARNING: absolute file offset, valid only for the RETAIL archive layout.
# Once any entry changes size (see tools/script_edit.py) every later entry
# shifts and this constant is wrong. Re-derive it from the TOC first.
ENTRY_BASE = 0x1E5AA6          # entry 23's offset within DICK.DAT
COUNT_OFF = ENTRY_BASE + 0x0FA1
UNITS_OFF = ENTRY_BASE + 0x0FA2
UNIT_COUNT = 36

# 琳：狄克，這村莊不太一樣！ padded with full-width spaces
NEW_UNITS = ([0x0066, 0x000f, 0x0018, 0x005d, 0x005e, 0x0016, 0x0034,
              0x0022, 0x0069, 0x000c, 0x006d, 0x0000, 0x006e, 0x0019]
             + [0x0066] * 22)

ORIGINAL = [0x0066, 0x000f, 0x0018, 0x005d, 0x005e, 0x0034, 0x000b, 0x0005,
            0x0067, 0x0068, 0x0011, 0x0022, 0x0069, 0x0064, 0x001a, 0x006a,
            0x0009, 0x0067, 0x0068, 0x0011, 0x006b, 0x006c, 0x0022, 0x000c,
            0x006d, 0x0000, 0x006e, 0x0016, 0x0039, 0x004c, 0x006f, 0x0070,
            0x0071, 0x0072, 0x0017, 0x0066]


def pack(units):
    out = bytearray()
    for u in units:
        out += bytes([u & 0xFF, u >> 8])
    return bytes(out)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    revert = "--revert" in sys.argv
    want = ORIGINAL if revert else NEW_UNITS

    size = os.path.getsize(path)
    if size != 89131843:
        print(f"warning: expected an 89,131,843-byte DICK.DAT, got {size}")

    with open(path, "rb") as f:
        f.seek(COUNT_OFF)
        count = f.read(1)[0]
        current = f.read(UNIT_COUNT * 2)

    if count != UNIT_COUNT:
        print(f"unit count at 0x{COUNT_OFF:X} is {count}, expected {UNIT_COUNT} "
              f"- wrong file or wrong offset, aborting")
        return 1
    if current not in (pack(ORIGINAL), pack(NEW_UNITS)):
        print("the bytes there are neither the original line nor the patched "
              "one - aborting rather than overwrite something unexpected")
        return 1
    if current == pack(want):
        print("already in that state, nothing to do")
        return 0

    backup = path + ".bak"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
        print(f"backup written to {backup}")

    with open(path, "r+b") as f:
        f.seek(UNITS_OFF)
        f.write(pack(want))

    print("reverted to the original line" if revert
          else "patched: entry 23 message 0 now reads 琳：狄克，這村莊不太一樣！")
    print("start a new game and talk through the opening scene to see it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
