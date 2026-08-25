#!/usr/bin/env python3
"""
font.py - decode and repaint the glyph font (archive entry 4)

Format, read out of the renderer in overlay 13 at 0x6ECC-0x6F3D:

    mov ax, fs:[esi]     ; u16 glyph index from the script
    shl eax, 6           ; x 64          -> 64 bytes per glyph
    mov esi, 0x100000    ; font base once loaded
    add esi, eax         ; src = base + index*64
    ...  shr al, cl / and al, 3          -> 2 BITS PER PIXEL

So: 16x16 glyphs, 2bpp, 4 pixels per byte, most-significant pair first,
64 bytes per glyph, 2048 slots, stored raw in entry 4 after a 1-byte type tag.

Pixel classes are palette *roles*, not colours. The renderer maps them per
pass, so a repainted glyph must use the same roles to look native:

    0  transparent   (engine writes 0x45 = skip)
    1  light face    (0x48 -> 0x78 or 0x47)
    2  bevel / edge  (0x4B -> 0x24 or 0x41)
    3  unused by the retail font -- avoid it, its colour is unverified

The engine draws each glyph three times: a shadow pass at the base position
in colour 7, then the glyph proper at base - 0x282, i.e. two pixels up and
two left. Advance between glyphs is 0x13 = 19 pixels; screen pitch is 320.

    python font.py dump  0004.bin sheet.png        # all 2048 slots as an image
    python font.py dump  0004.bin sheet.png 0x4b0 0x6a0
    python font.py export 0004.bin glyphs/         # one PNG per non-blank slot
    python font.py import 0004.bin glyphs/ 0004.new.bin
    python font.py free  0004.bin                  # list repaintable slots

Import reads PNGs named <hex>.png, 16x16, any greyscale/RGB. Pixel values are
snapped to the nearest class by luminance: black -> 0, mid -> 2, bright -> 1.
Everything not supplied is left byte-identical, so a repack is safe.
"""
import os
import sys

CELL = 64
SLOTS = 2048
TAG = 1  # leading type byte, consumed by the loader


def decode(blob, n):
    """Return a 16x16 list of rows of class values 0-3."""
    b = blob[TAG + n * CELL:TAG + (n + 1) * CELL]
    px = [[0] * 16 for _ in range(16)]
    for i, by in enumerate(b):
        for k in range(4):
            p = i * 4 + k
            px[p // 16][p % 16] = (by >> (6 - 2 * k)) & 3
    return px


def encode(px):
    """Inverse of decode. Returns 64 bytes."""
    flat = [px[y][x] for y in range(16) for x in range(16)]
    out = bytearray()
    for i in range(0, 256, 4):
        by = 0
        for k in range(4):
            by |= (flat[i + k] & 3) << (6 - 2 * k)
        out.append(by)
    return bytes(out)


def is_blank(blob, n):
    return not any(blob[TAG + n * CELL:TAG + (n + 1) * CELL])


def load(path):
    blob = open(path, "rb").read()
    want = TAG + SLOTS * CELL
    if len(blob) != want:
        sys.stderr.write("warning: expected %d bytes, got %d\n" % (want, len(blob)))
    return blob


# class -> preview grey. Chosen to look like the in-game bevel, not to match
# the palette exactly, which we cannot read without the VGA palette entry.
PREVIEW = {0: 0, 1: 255, 2: 128, 3: 60}


def cmd_dump(src, out, lo=0, hi=SLOTS - 1):
    from PIL import Image
    blob = load(src)
    n = hi - lo + 1
    cols = 32
    rows = (n + cols - 1) // cols
    img = Image.new("L", (cols * 17 + 1, rows * 17 + 1), 30)
    p = img.load()
    for i in range(n):
        px = decode(blob, lo + i)
        ox, oy = (i % cols) * 17 + 1, (i // cols) * 17 + 1
        for y in range(16):
            for x in range(16):
                p[ox + x, oy + y] = PREVIEW[px[y][x]]
    img = img.resize((img.width * 2, img.height * 2), Image.NEAREST)
    img.save(out)
    print("wrote %s (%d slots, 0x%03x-0x%03x)" % (out, n, lo, hi))


def cmd_export(src, outdir):
    from PIL import Image
    blob = load(src)
    os.makedirs(outdir, exist_ok=True)
    n = 0
    for s in range(SLOTS):
        if is_blank(blob, s):
            continue
        px = decode(blob, s)
        img = Image.new("L", (16, 16))
        q = img.load()
        for y in range(16):
            for x in range(16):
                q[x, y] = PREVIEW[px[y][x]]
        img.save(os.path.join(outdir, "%03x.png" % s))
        n += 1
    print("exported %d non-blank glyphs to %s" % (n, outdir))


def snap(v):
    """Luminance -> class. Mid-greys become bevel, brights become face."""
    if v < 48:
        return 0
    if v < 192:
        return 2
    return 1


def cmd_import(src, indir, out):
    from PIL import Image
    blob = bytearray(load(src))
    n = 0
    for fn in sorted(os.listdir(indir)):
        if not fn.lower().endswith(".png"):
            continue
        try:
            slot = int(os.path.splitext(fn)[0], 16)
        except ValueError:
            print("  skip %s (name is not a hex slot number)" % fn)
            continue
        if not 0 <= slot < SLOTS:
            print("  skip %s (slot out of range)" % fn)
            continue
        img = Image.open(os.path.join(indir, fn)).convert("L")
        if img.size != (16, 16):
            print("  skip %s (%dx%d, need 16x16)" % (fn, *img.size))
            continue
        q = img.load()
        px = [[snap(q[x, y]) for x in range(16)] for y in range(16)]
        blob[TAG + slot * CELL:TAG + (slot + 1) * CELL] = encode(px)
        n += 1
    open(out, "wb").write(bytes(blob))
    print("repainted %d slots -> %s (%d bytes)" % (n, out, len(blob)))


def cmd_free(src):
    blob = load(src)
    blanks = [s for s in range(SLOTS) if is_blank(blob, s)]
    runs, start = [], None
    for s in range(SLOTS + 1):
        b = s < SLOTS and s in set(blanks)
        if b and start is None:
            start = s
        if not b and start is not None:
            runs.append((start, s - 1))
            start = None
    print("%d blank slots of %d" % (len(blanks), SLOTS))
    for a, b in runs:
        print("  0x%03x - 0x%03x  (%d slots)" % (a, b, b - a + 1))
    print("\nNote: 0x066 is the full-width space and 0x593 is referenced by the")
    print("script, so neither is safe to repaint despite being blank.")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == "dump":
        lo = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0
        hi = int(sys.argv[5], 0) if len(sys.argv) > 5 else SLOTS - 1
        cmd_dump(sys.argv[2], sys.argv[3], lo, hi)
    elif cmd == "export":
        cmd_export(sys.argv[2], sys.argv[3])
    elif cmd == "import":
        cmd_import(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "free":
        cmd_free(sys.argv[2])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
