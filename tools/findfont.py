#!/usr/bin/env python3
"""
findfont.py - locate the glyph bitmaps using 496 known-exact 16x16 glyphs as cribs.

Lives in tools/, reads its cribs from data/known_glyphs.bin, and scans any file
you point it at (paths are taken as given, so targets outside the repo are fine):

    python tools/findfont.py /games/dick/DICK.DAT
    python tools/findfont.py /games/dick/*.EXE /games/dick/*.OVL
    python tools/findfont.py DICK.DAT --table        # offset-table scan only
    python tools/findfont.py DICK.DAT --no-table    # bitmap sweeps only
    python tools/findfont.py DICK.DAT --fast         # skip the shift sweep
    python tools/findfont.py DICK.DAT --cribs other.bin

WHY THE CRIBS MAY NEED SHIFTING
STATUS.md records that each glyph is blitted three times at one-pixel offsets to
make the bevel. The cribs in data/known_glyphs.bin were recovered from the light
face layer of a screenshot, so they are one of those three passes - which means
they may sit one pixel away from the glyph as stored on disk. An exact search
using them would then fail at every offset in the file no matter how many
orientations you try. By default this tool therefore also tries the crib shifted
by -1/0/+1 in x and y, skipping any shift that would clip ink off the edge.

AXES SWEPT
  storage order    row-major, and column-major (glyph rotated 90 degrees, which
                   is what a blitter writing VGA planes column-wise produces)
  bit order        MSB-first / LSB-first within each byte (= horizontal mirror)
  row order        top-down / bottom-up (the BMP and VGA convention)
  word endianness  for 16-bit-per-row storage
  polarity         ink=1 / ink=0
  origin shift     dx,dy in -1..+1 (disable with --fast)
  row stride       1/2/3/4 bytes between glyph rows, searching a single 8x16
                   half -- catches split half-planes and cells wider than 16px
Row pitch is covered by the stride search in the adjacency test.

A hit only counts if glyph N+1 also lands at the predicted stride, so single
coincidental matches cannot mislead you.

numpy is optional: needed only for the bpp>1 and offset-table scans.
"""
import sys, os, glob, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def find_cribs(explicit=None):
    tries = []
    if explicit:
        tries.append(explicit)
    tries += [
        os.path.join(REPO, "data", "known_glyphs.bin"),   # tools/ -> ../data/
        os.path.join(HERE, "data", "known_glyphs.bin"),   # run from repo root
        os.path.join(HERE, "known_glyphs.bin"),           # beside the script
        os.path.join(os.getcwd(), "data", "known_glyphs.bin"),
        os.path.join(os.getcwd(), "known_glyphs.bin"),
    ]
    for p in tries:
        if os.path.isfile(p):
            return p
    sys.stderr.write(
        "error: could not find known_glyphs.bin. Looked in:\n  "
        + "\n  ".join(tries)
        + "\nPass one with --cribs PATH.\n")
    sys.exit(2)


def load_cribs(path):
    d = open(path, "rb").read()
    if d[:4] != b"GLY1":
        sys.exit("error: %s is not a GLY1 crib file" % path)
    n = int.from_bytes(d[4:6], "little")
    out, p = {}, 6
    for _ in range(n):
        idx = int.from_bytes(d[p:p + 2], "little"); p += 2
        out[idx] = [int.from_bytes(d[p + 2 * r:p + 2 * r + 2], "big")
                    for r in range(16)]
        p += 32
    return out


# ---------------------------------------------------------------- transforms

def shift(rows, dy, dx):
    """Shift glyph by (dy,dx). Returns None if that would clip ink."""
    out = []
    for r in range(16):
        sr = r - dy
        v = rows[sr] if 0 <= sr < 16 else 0
        if dx > 0:
            if v & ((1 << dx) - 1):
                return None
            v >>= dx
        elif dx < 0:
            k = -dx
            if v & ~((1 << (16 - k)) - 1):
                return None
            v = (v << k) & 0xFFFF
        out.append(v)
    if dy > 0 and any(rows[16 - dy:]):
        return None
    if dy < 0 and any(rows[:-dy]):
        return None
    return out


def transpose(rows):
    cols = []
    for c in range(16):
        v = 0
        for r in range(16):
            if rows[r] >> (15 - c) & 1:
                v |= 1 << (15 - r)
        cols.append(v)
    return cols


def revbits16(v):
    return int(format(v, "016b")[::-1], 2)


def pack(rows, bitorder, endian, invert):
    out = bytearray()
    for v in rows:
        if invert:
            v ^= 0xFFFF
        if bitorder == "lsb":
            v = revbits16(v)
        out += v.to_bytes(2, endian)
    return bytes(out)


def orient(rows, order, vflip):
    """vflip = bottom-up row order (the BMP/VGA convention). Together with
    'col' (90 deg rotation) and 'lsb' (horizontal mirror) this covers all eight
    dihedral orientations of the glyph."""
    r = rows[::-1] if vflip else rows
    return transpose(r) if order == "col" else r


VARIANTS = [(o, b, e, i, v)
            for o in ("row", "col")
            for b in ("msb", "lsb")
            for e in ("big", "little")
            for i in (False, True)
            for v in (False, True)]

STRIDES = (32, 33, 34, 36, 40, 48, 64)


def ink_count(rows):
    return sum(bin(v).count("1") for v in rows)


def pick_probes(cribs, k):
    ok = [i for i in cribs if i + 1 in cribs]
    ok.sort(key=lambda i: abs(ink_count(cribs[i]) - 110))
    return ok[:k]


# ------------------------------------------------------------------ searches

def sweep_1bpp(data, cribs, name, shifts, nprobe):
    hits, seen = [], set()
    probes = pick_probes(cribs, nprobe)
    for dy, dx in shifts:
        for idx in probes:
            a = shift(cribs[idx], dy, dx)
            b = shift(cribs[idx + 1], dy, dx)
            if a is None or b is None:
                continue
            for order, bo, en, inv, vf in VARIANTS:
                ra = orient(a, order, vf)
                rb = orient(b, order, vf)
                pat, npat = pack(ra, bo, en, inv), pack(rb, bo, en, inv)
                start = 0
                while True:
                    at = data.find(pat, start)
                    if at < 0:
                        break
                    start = at + 1
                    for st in STRIDES:
                        if data[at + st:at + st + 32] == npat:
                            key = (at - idx * st, st, order, bo, en, inv, vf,
                                   dy, dx)
                            if key not in seen:
                                seen.add(key)
                                hits.append((name, at, at - idx * st, st,
                                             order + ("/vflip" if vf else ""),
                                             bo, en, inv, idx, dy, dx))
                            break
    return hits


HALF_STRIDES = (16, 17, 18, 19, 20, 24, 32, 33, 34, 36, 40, 48, 64)


def sweep_halves(data, cribs, name, shifts, nprobe, log=None):
    """Search for ONE 8x16 half of a glyph, allowing an arbitrary byte stride
    between its rows.

    This covers the cases a contiguous 32-byte search cannot see:
      row stride 1  left and right halves kept in separate regions/planes
      row stride 2  ordinary 16-wide rows (redundant with the 1bpp sweep)
      row stride 3  rows wider than 16px -- e.g. a 19 or 24 px cell, which the
                    measured 19px advance makes entirely plausible
      row stride 4  32-bit padded rows
    Anchors on the rarest byte value in the pattern so each probe costs a
    lookup rather than a full scan."""
    try:
        import numpy as np
    except ImportError:
        print("  (numpy missing - skipping half-glyph sweep)")
        return []
    a = np.frombuffer(data, dtype=np.uint8)
    hist = np.bincount(a, minlength=256).astype(np.int64)
    pos_cache = {}

    def positions(v):
        if v not in pos_cache:
            if len(pos_cache) > 24:
                pos_cache.clear()
            pos_cache[v] = np.flatnonzero(a == v)
        return pos_cache[v]

    def halves(rows, bitorder, invert):
        out = []
        for which in (0, 1):
            p = []
            for v in rows:
                if invert:
                    v ^= 0xFFFF
                if bitorder == "lsb":
                    v = revbits16(v)
                p.append((v >> 8) & 0xFF if which == 0 else v & 0xFF)
            out.append(bytes(p))
        return out

    hits, seen = [], set()
    probes = pick_probes(cribs, nprobe)
    for dy, dx in shifts:
        for idx in probes:
            ra, rb = shift(cribs[idx], dy, dx), shift(cribs[idx + 1], dy, dx)
            if ra is None or rb is None:
                continue
            for bo, vf in [(b, v) for b in ("msb", "lsb")
                           for v in (False, True)]:
                for inv in (False, True):
                    ha = halves(ra[::-1] if vf else ra, bo, inv)
                    hb = halves(rb[::-1] if vf else rb, bo, inv)
                    for which in (0, 1):
                        pat, npat = ha[which], hb[which]
                        if len(set(pat)) < 4:
                            continue          # too bland to anchor on
                        k = min(range(16), key=lambda i: hist[pat[i]])
                        if hist[pat[k]] == 0:
                            continue
                        base = positions(pat[k])
                        for S in (1, 2, 3, 4):
                            cand = base - k * S
                            cand = cand[(cand >= 0) &
                                        (cand < len(a) - 16 * S - 1)]
                            if len(cand) == 0:
                                continue
                            for i in range(16):
                                if i == k or len(cand) == 0:
                                    continue
                                cand = cand[a[cand + i * S] == pat[i]]
                            for c in cand[:64]:
                                c = int(c)
                                for gs in HALF_STRIDES:
                                    q = c + gs
                                    if q + 16 * S >= len(a):
                                        continue
                                    if all(a[q + i * S] == npat[i]
                                           for i in range(16)):
                                        key = (c - idx * gs, S, gs, bo, inv,
                                               which, vf, dy, dx)
                                        if key in seen:
                                            break
                                        seen.add(key)
                                        hits.append(
                                            (name, c, c - idx * gs, gs,
                                             "half%d/rowstride%d%s"
                                             % (which, S,
                                                "/vflip" if vf else ""),
                                             bo, "-", inv, idx, dy, dx))
                                        break
    return hits


ATLAS_STRIDES = (16, 17, 18, 19, 20, 24, 32, 38, 40, 48, 64, 76, 80, 96, 128,
                 160, 192, 256, 304, 320, 384, 400, 512, 608, 640, 768, 1024)


def sweep_atlas8(data, cribs, name, shifts, nprobe, log=None):
    """8bpp glyphs with an arbitrary row stride, tolerant of a baked-in bevel.

    Two assumptions in the earlier sweeps were wrong for this case:
      - rows contiguous.  In an atlas the stride is the atlas width.
      - ink == non-zero.  If the 3-pass bevel is pre-rendered into the glyph,
        shadow and mid-grey are non-zero too, so a non-zero test matches a
        dilated blob, never the crib.
    So this tests VALUE EQUALITY instead: every face pixel must share one byte
    value, every true-background pixel another. Background is computed as
    NOT(face OR face shifted by +1,+1), which excludes wherever the shadow pass
    would have landed and leaves the test valid whether or not it is baked in."""
    try:
        import numpy as np
    except ImportError:
        print("  (numpy missing - skipping 8bpp atlas sweep)")
        return []
    a = np.frombuffer(data, dtype=np.uint8)
    n = len(a)
    hits, seen = [], set()
    for dy, dx in shifts:
        for idx in pick_probes(cribs, max(2, nprobe // 2)):
            rows = shift(cribs[idx], dy, dx)
            nxt = shift(cribs[idx + 1], dy, dx)
            if rows is None or nxt is None:
                continue
            face = np.array([[(rows[r] >> (15 - c)) & 1 for c in range(16)]
                             for r in range(16)], dtype=bool)
            shadow = np.zeros_like(face)
            shadow[1:, 1:] = face[:-1, :-1]
            bg = ~(face | shadow)
            fy, fx = np.nonzero(face)
            gy, gx = np.nonzero(bg)
            if len(fy) < 12 or len(gy) < 12:
                continue
            # a spread-out subset keeps the shortlist selective and cheap
            fsel = np.linspace(0, len(fy) - 1, 10).astype(int)
            gsel = np.linspace(0, len(gy) - 1, 10).astype(int)
            for S in ATLAS_STRIDES:
                span = 15 * S + 16
                if span + 1 >= n:
                    continue
                lim = n - span - 1
                f0 = fy[fsel[0]] * S + fx[fsel[0]]
                g0 = gy[gsel[0]] * S + gx[gsel[0]]
                base = a[:lim]
                v1, v0 = a[f0:f0 + lim], a[g0:g0 + lim]
                keep = v1 != v0
                for j in fsel[1:4]:
                    o = fy[j] * S + fx[j]
                    keep &= a[o:o + lim] == v1
                for j in gsel[1:4]:
                    o = gy[j] * S + gx[j]
                    keep &= a[o:o + lim] == v0
                cand = np.flatnonzero(keep)
                if len(cand) == 0 or len(cand) > 5_000_000:
                    continue
                for j in list(fsel[4:]) + list(gsel[4:]):
                    if len(cand) == 0:
                        break
                    if j in fsel:
                        o = fy[j] * S + fx[j]
                        cand = cand[a[cand + o] == a[cand + f0]]
                    else:
                        o = gy[j] * S + gx[j]
                        cand = cand[a[cand + o] == a[cand + g0]]
                for c in cand[:32]:
                    c = int(c)
                    # full verify, then adjacency on glyph N+1
                    ok = (np.all(a[c + fy * S + fx] == a[c + f0]) and
                          np.all(a[c + gy * S + gx] == a[c + g0]))
                    if not ok:
                        continue
                    nf = np.array([[(nxt[r] >> (15 - c2)) & 1
                                    for c2 in range(16)] for r in range(16)],
                                  dtype=bool)
                    ny, nx = np.nonzero(nf)
                    for gs in (16, 17, 18, 19, 20, 24, 32, S, 256, 257, 260,
                               272, 320):
                        q = c + gs
                        if q + span >= n:
                            continue
                        if np.all(a[q + ny * S + nx] == a[c + f0]):
                            key = (c - idx * gs, S, gs, dy, dx)
                            if key in seen:
                                break
                            seen.add(key)
                            hits.append((name, c, c - idx * gs, gs,
                                         "8bpp-atlas/rowstride%d" % S,
                                         "-", "-", False, idx, dy, dx))
                            break
    return hits


def sweep_multibpp(data, cribs, name, shifts, nprobe):
    try:
        import numpy as np
    except ImportError:
        print("  (numpy missing - skipping bpp>1 search)")
        return []
    a = np.frombuffer(data, dtype=np.uint8)
    hits = []
    for dy, dx in shifts:
        for idx in pick_probes(cribs, max(2, nprobe // 2)):
            rows = shift(cribs[idx], dy, dx)
            if rows is None:
                continue
            flat = [(rows[r] >> (15 - c)) & 1 for r in range(16) for c in range(16)]
            ink = [p for p, v in enumerate(flat) if v]
            bg = [p for p, v in enumerate(flat) if not v]
            if len(ink) < 8 or len(bg) < 8:
                continue
            for bpp in (2, 4, 8):
                per, ppb = 16 * 16 * bpp // 8, 8 // bpp
                cand = None
                for px, want in zip(ink[:2] + bg[:2], (1, 1, 0, 0)):
                    byi, sh = px // ppb, (ppb - 1 - px % ppb) * bpp
                    mask = ((1 << bpp) - 1) << sh
                    col = (a[byi:len(a) - per + byi] & mask) != 0
                    c = col == bool(want)
                    cand = c if cand is None else (cand & c)
                for at in np.flatnonzero(cand)[:2000]:
                    at = int(at); blk = a[at:at + per]; ok = True
                    for p, v in enumerate(flat):
                        byi, sh = p // ppb, (ppb - 1 - p % ppb) * bpp
                        if (((blk[byi] >> sh) & ((1 << bpp) - 1)) != 0) != bool(v):
                            ok = False; break
                    if ok:
                        hits.append((name, at, at - idx * per, per,
                                     "row/%dbpp" % bpp, "-", "-", False,
                                     idx, dy, dx))
    return hits


def scan_offset_table(data, cribs, name, top=5, cap=200000, log=None):
    """If glyphs are RLE, a per-glyph offset table must exist. Score plausible
    table positions by correlating deltas against per-glyph run counts.

    Prefilters are vectorised and must reject the degenerate regions that fill
    real archives -- zero runs, 0xFF runs and constant-stride arrays all look
    'non-decreasing' and would otherwise make every offset a candidate."""
    try:
        import numpy as np
    except ImportError:
        print("  (numpy missing - skipping offset-table scan)")
        return []

    def runcount(rows):
        n = 0
        for v in rows:
            prev = 0
            for c in range(16):
                b = (v >> (15 - c)) & 1
                n += b != prev
                prev = b
            n += prev
        return n

    ks = sorted(k for k in cribs if k + 1 in cribs)
    x = np.array([runcount(cribs[k]) for k in ks], dtype=np.float64)
    x -= x.mean()
    xn = np.linalg.norm(x)
    lo = ks[0]
    span = ks[-1] - lo + 2
    rel = np.array([k - lo for k in ks])
    MINAVG = 4          # bytes per glyph, even a trivial packer beats this

    out = []
    for width, dt in ((2, "<u2"), (2, ">u2"), (4, "<u4"), (4, ">u4")):
        for align in range(width):
            buf = data[align:]
            arr = np.frombuffer(buf[:len(buf) - len(buf) % width], dtype=dt)
            if len(arr) < span + 2:
                continue
            arr = arr.astype(np.int64)
            d = np.diff(arr)
            ok = (d >= 0) & (d < 8192)
            n = len(arr) - span
            if n <= 0:
                continue
            # window entirely non-decreasing
            csum = np.concatenate(([0], np.cumsum(ok, dtype=np.int64)))
            idx = np.arange(n)
            good = (csum[idx + span - 1] - csum[idx]) == (span - 1)
            # and genuinely growing: kills zero fill, 0xFF fill, stride-1 arrays
            growth = arr[idx + span - 1] - arr[idx]
            good &= growth >= MINAVG * (span - 1)
            cand = np.flatnonzero(good)
            if len(cand) == 0:
                continue
            if len(cand) > cap:
                if log:
                    log("    %s u%d %s align%d: %d candidates, sampling %d"
                        % (name, width * 8, dt[0], align, len(cand), cap))
                cand = cand[np.linspace(0, len(cand) - 1, cap).astype(np.int64)]
            # vectorised correlation, chunked to bound memory
            dd = np.diff(arr)
            for i in range(0, len(cand), 4096):
                ch = cand[i:i + 4096]
                y = dd[ch[:, None] + rel[None, :]].astype(np.float64)
                ym = y - y.mean(axis=1, keepdims=True)
                nrm = np.linalg.norm(ym, axis=1)
                live = nrm > 0
                if not live.any():
                    continue
                r = (ym[live] @ x) / (nrm[live] * xn)
                for p, rv in zip(ch[live], r):
                    if rv > 0.35:
                        # p indexes the crib window, which starts at glyph `lo`;
                        # report where entry 0 of the table would be
                        base = (int(p) - lo) * width + align
                        out.append((name, base, float(rv), width,
                                    "LE" if dt[0] == "<" else "BE"))
    out.sort(key=lambda t: -t[2])
    return out[:top]


# ------------------------------------------------------------------- reporting

def report(hits, tabs, scanned, shifts):
    if hits:
        print("\n=== GLYPH BITMAP HITS ===")
        for n, at, base, st, order, bo, en, inv, idx, dy, dx in hits:
            print("  %s @0x%X  glyph0=0x%X stride=%d  %s/%s/%s%s  shift=(%+d,%+d)"
                  "  [crib 0x%03x]"
                  % (n, at, base, st, order, bo, en,
                     " INV" if inv else "", dy, dx, idx))
    if tabs:
        print("\n=== OFFSET TABLE CANDIDATES ===")
        for n, at, r, w, en in tabs:
            print("  %s table[0]@0x%X  u%d %s  corr(delta, runcount)=%.3f%s"
                  % (n, at, w * 8, en, r,
                     "   <-- strong" if r > 0.7 else ""))
    if not hits and not tabs:
        print("\nNo match in: %s" % ", ".join(scanned))
        print("Ruled out: plain bitmap storage at 1/2/4/8 bpp in either raster")
        print("order, both bit orders, both endiannesses, both polarities, and")
        print("%d origin shift(s). Also: no monotonic array whose deltas track" % len(shifts))
        print("glyph complexity, so no obvious RLE offset table either.")
        print("\nNext: scan the executables and any overlay/driver files, which")
        print("this tool takes as extra arguments. If those are clean too, the")
        print("font is likely packed per-glyph with a codec that does not")
        print("preserve size ordering, and the practical route is tracing the")
        print("blit in a debugger rather than searching for the data.")


def main():
    argv = sys.argv[1:]
    cribs_path = None
    if "--cribs" in argv:
        i = argv.index("--cribs")
        cribs_path = argv[i + 1]
        del argv[i:i + 2]
    only_table = "--table" in argv
    no_table = "--no-table" in argv
    fast = "--fast" in argv
    targets = []
    for a in argv:
        if a.startswith("--"):
            continue
        targets += sorted(glob.glob(a)) or [a]
    if not targets:
        print(__doc__)
        return 1

    cp = find_cribs(cribs_path)
    cribs = load_cribs(cp)
    print("cribs: %s (%d glyphs, 0x%03x-0x%03x)"
          % (os.path.relpath(cp), len(cribs), min(cribs), max(cribs)))

    shifts = [(0, 0)] if fast else [(dy, dx) for dy in (0, -1, 1)
                                    for dx in (0, -1, 1)]
    nprobe = 6 if fast else 4
    if not fast and not only_table:
        print("sweeping %d origin shifts (--fast for centre only)" % len(shifts))

    hits, tabs, scanned = [], [], []
    for path in targets:
        if not os.path.isfile(path):
            sys.stderr.write("skip (not a file): %s\n" % path)
            continue
        data = open(path, "rb").read()
        nm = os.path.basename(path)
        scanned.append(nm)
        print("scanning %s (%.1f MB)" % (path, len(data) / 1e6))
        if not only_table:
            t = time.time()
            hits += sweep_1bpp(data, cribs, nm, shifts, nprobe)
            print("    1bpp sweep      %5.1fs" % (time.time() - t))
            t = time.time()
            hits += sweep_halves(data, cribs, nm, shifts, nprobe)
            print("    half-glyph      %5.1fs" % (time.time() - t))
            t = time.time()
            hits += sweep_atlas8(data, cribs, nm, shifts, nprobe)
            print("    8bpp atlas      %5.1fs" % (time.time() - t))
            t = time.time()
            hits += sweep_multibpp(data, cribs, nm, shifts, nprobe)
            print("    2/4/8bpp sweep  %5.1fs" % (time.time() - t))
        if not no_table:
            t = time.time()
            tabs += scan_offset_table(data, cribs, nm,
                                      log=lambda m: print(m))
            print("    offset table    %5.1fs" % (time.time() - t))
    report(hits, tabs, scanned, shifts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
