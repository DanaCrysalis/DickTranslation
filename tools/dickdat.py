#!/usr/bin/env python3
"""
dickdat.py - extractor / repacker for DICK.DAT (CosmoTech Game-0001, DOS)

Container format (verified against the 87,043 KB retail file):
    0x0000  u16   entry count            (1146)
    0x0002  n x 8 [u32 offset][u32 size]  absolute file offsets, ascending
    0x20002 ...   entry data              (TOC region padded out to 128 KB)
  Entries are contiguous apart from three small padding gaps; the last
  entry ends at exactly the file length.

Usage:
    python dickdat.py list    DICK.DAT
    python dickdat.py extract DICK.DAT outdir
    python dickdat.py tables  DICK.DAT [outdir] [charmap.json]  # UNVALIDATED
    python dickdat.py learn   script/ "<text you can read>" [charmap.json]
    python dickdat.py text    DICK.DAT [outdir] [charmap.json]  # dump the script
    python dickdat.py script  DICK.DAT [report.txt]  # find text (string chains)
    python dickdat.py loadmap DICK.DAT [report.txt]  # overlay -> resource map
    python dickdat.py find    DICK.DAT "0F 85 4E 01"  # locate bytes -> entry no.
    python dickdat.py render  DICK.DAT pngdir [width]  # dump raw screens as PNG
    python dickdat.py pack    outdir DICK.NEW   # rebuild from extracted dir
"""
import collections, json, math, os, re, struct, sys

TOC_BASE = 0x20002

# The ~250 most frequent traditional-Chinese characters, plus the punctuation a
# game script actually uses. Graphics data decodes into Big5-valid but *rare*
# glyphs (豕, 壯, 牧, 圾, ㄒ...), so requiring a share of genuinely common
# characters is what separates real dialogue from pixel noise.
COMMON = set(
    "的一是不了在人有我他這你們中來上個到說國和地也子時道出而要於就下得可你年生"
    "自會那後能對著事其裡所去行過家十用發天如然作方成者多日都三小軍二無同么經法"
    "當起與好看學進種將還分此心前面又定見只主沒公從他她它是很想知很問話說道找給"
    "王大將軍師父兄弟姊妹姑娘公子少爺老爺夫人娘子英雄武功劍刀掌拳氣力身體手腳眼"
    "口耳頭心神魂命死活殺打救幸苦樂笑哭怒喜怕驚急慢快走跑飛坐立站臥睡吃喝買賣錢"
    "銀金玉寶物件東西南北左右內外遠近高低長短新舊真假是非對錯輸贏勝敗攻守進退"
    "什麼怎樣為何因所以但是可能已經現在剛才將要不過還有沒有一個這個那個我們你們"
    "他們請你謝謝再見對不起沒關係哈哈嗯呢吧啊呀喔咦哼"
    "，。！？、；：「」『』…—～（）"
)


def common_ratio(s):
    return sum(1 for c in s if c in COMMON) / len(s) if s else 0.0


def read_toc(path):
    with open(path, "rb") as f:
        n = struct.unpack("<H", f.read(2))[0]
        raw = f.read(n * 8)
    return [struct.unpack_from("<II", raw, i * 8) for i in range(n)]


def kind(b):
    """Best-effort content sniff for an entry's first bytes."""
    if b[:8] == b"GF1PATCH":
        return "gus-patch"
    if b[:2] == b"MZ":
        return "dos-exe"
    if b[:1] in (b"\x01", b"\x02") and b[1:3] == b"\xff\xff":
        return "rle-image?"
    return "binary"


def cmd_list(path):
    ent = read_toc(path)
    total = os.path.getsize(path)
    print(f"{len(ent)} entries, file {total} bytes")
    with open(path, "rb") as f:
        for i, (off, size) in enumerate(ent):
            f.seek(off)
            head = f.read(16)
            print(f"{i:5d}  off=0x{off:08x}  size={size:8d}  {kind(head)}  {head[:12].hex(' ')}")
    end = ent[-1][0] + ent[-1][1]
    print(f"last entry ends at {end} ({'OK' if end == total else 'MISMATCH vs ' + str(total)})")


def cmd_extract(path, outdir):
    ent = read_toc(path)
    os.makedirs(outdir, exist_ok=True)
    with open(path, "rb") as f:
        for i, (off, size) in enumerate(ent):
            f.seek(off)
            open(os.path.join(outdir, f"{i:04d}.bin"), "wb").write(f.read(size))
        # preserve the padding gaps so a repack is byte-exact
        gaps = {}
        for i in range(len(ent) - 1):
            gap = ent[i + 1][0] - (ent[i][0] + ent[i][1])
            if gap:
                f.seek(ent[i][0] + ent[i][1])
                gaps[i] = f.read(gap)
    with open(os.path.join(outdir, "_gaps.bin"), "wb") as g:
        g.write(struct.pack("<H", len(gaps)))
        for i, data in sorted(gaps.items()):
            g.write(struct.pack("<IH", i, len(data)) + data)
    print(f"extracted {len(ent)} entries to {outdir} ({len(gaps)} padding gaps preserved)")


def big5_runs(data, minchars=3):
    """Runs of >=minchars Big5 chars that are mostly level-1 hanzi or punctuation."""
    out, i, n = [], 0, len(data)
    while i < n - 1:
        a, b = data[i], data[i + 1]
        if not (0xA1 <= a <= 0xF9 and (0x40 <= b <= 0x7E or 0xA1 <= b <= 0xFE)):
            i += 1
            continue
        j, buf, good = i, bytearray(), 0
        while j < n - 1:
            a2, b2 = data[j], data[j + 1]
            if 0xA1 <= a2 <= 0xF9 and (0x40 <= b2 <= 0x7E or 0xA1 <= b2 <= 0xFE):
                v = (a2 << 8) | b2
                if 0xA440 <= v <= 0xC67E or 0xA140 <= v <= 0xA3BF:
                    good += 1
                buf += bytes([a2, b2])
                j += 2
            else:
                break
        nc = len(buf) // 2
        if nc >= minchars and good >= nc * 0.8:
            try:
                s = buf.decode("big5")
            except UnicodeDecodeError:
                s = None
            # Graphics data decodes into long runs of one or two repeated
            # glyphs (豕豕豕..., 壯壯壯...). Real prose is diverse: demand
            # plenty of distinct characters and no single dominant one.
            if s:
                uniq = len(set(s))
                top = max(collections.Counter(s).values())
                if (uniq >= max(3, len(s) * 0.45)
                        and top <= len(s) * 0.35
                        and common_ratio(s) >= 0.25):
                    out.append((i, s))
        i = max(j, i + 1)
    return out


def cmd_scan(path, report="scan_report.txt"):
    ent = read_toc(path)
    hits = 0
    with open(path, "rb") as f, open(report, "w", encoding="utf-8") as r:
        r.write(f"DICK.DAT Big5 scan - {len(ent)} entries, {os.path.getsize(path)} bytes\n")
        for i, (off, size) in enumerate(ent):
            if i % 50 == 0:
                print(f"  scanning {i}/{len(ent)}...", flush=True)
            f.seek(off)
            data = f.read(size)
            runs = big5_runs(data, minchars=5)
            if len(runs) < 3:
                continue
            counts = collections.Counter(data)
            H = -sum((v / size) * math.log2(v / size) for v in counts.values())
            longest = max(len(s) for _, s in runs)
            # real script has long runs; graphics noise produces short scattered ones
            if longest < 8:
                continue
            hits += 1
            r.write(f"\n=== entry {i} off=0x{off:08x} size={size} H={H:.2f} "
                    f"runs={len(runs)} longest={longest}\n")
            for o, s in runs[:40]:
                r.write(f"    +{o:06x}  {s}\n")
        if not hits:
            r.write("\nNO ENTRY CONTAINS PLAUSIBLE BIG5 TEXT - "
                    "dialogue is probably bitmap-rendered or stored elsewhere\n")
    print(f"{hits} candidate entries; report written to {report}")


def cmd_render(path, outdir, width=320):
    """Dump every plausibly-image entry as a PNG so text screens can be eyeballed.

    Entries tagged 0x01/0x02 are compressed (see notes in README); those are
    skipped. Untagged raw entries of 64000/64001 bytes are mode 13h screens and
    render correctly. Palettes are the 768-byte entries; the nearest preceding
    one is used, which is right often enough for triage.
    """
    try:
        from PIL import Image
    except ImportError:
        print("needs Pillow:  pip install pillow")
        return
    ent = read_toc(path)
    os.makedirs(outdir, exist_ok=True)
    pal, n = None, 0
    with open(path, "rb") as f:
        for i, (off, size) in enumerate(ent):
            f.seek(off)
            data = f.read(size)
            if size == 768:                       # VGA palette, 6 bits per gun
                pal = [c * 4 for c in data]
                continue
            if size not in (64000, 64001):
                continue
            raw = data[1:] if size == 64001 else data
            if len(raw) < width * 200:
                continue
            img = Image.frombytes("P", (width, len(raw) // width), raw[:width * (len(raw) // width)])
            img.putpalette(pal if pal else [v for k in range(256) for v in (k, k, k)])
            img.convert("RGB").save(os.path.join(outdir, f"{i:04d}.png"))
            n += 1
    print(f"rendered {n} raw screens to {outdir}")


def cmd_find(path, hexpat):
    """Locate a byte pattern and report which archive entry it falls in.
    '--' or '??' in the pattern means wildcard, e.g. the published crack bytes.
    """
    toks = hexpat.replace(",", " ").split()
    pat = [None if t in ("--", "??", "**") else int(t, 16) for t in toks]
    ent = read_toc(path)
    data = open(path, "rb").read()
    first = pat[0]
    hits = 0
    for i in range(len(data) - len(pat)):
        if data[i] != first:
            continue
        if all(p is None or data[i + k] == p for k, p in enumerate(pat)):
            e = next((j for j, (o, s) in enumerate(ent) if o <= i < o + s), None)
            rel = i - ent[e][0] if e is not None else 0
            print(f"match at file 0x{i:08x} -> entry {e} + 0x{rel:x} "
                  f"(entry size {ent[e][1] if e is not None else '?'})")
            hits += 1
            if hits >= 20:
                print("...stopping at 20 matches")
                return
    if not hits:
        print("no match")


def _cell_grid_score(data, base, ncell=64):
    """How strongly `data` at `base` looks like a grid of 256-byte, row-major
    16x16 glyph cells.

    The engine's blitter reads 16 consecutive bytes per screen row and advances
    the source pointer linearly, so a glyph is exactly 256 bytes with no
    padding. Glyphs leave their cell edges blank; picture data has no such
    alignment, and unlike ink-density or run-length tests this one cannot be
    satisfied by an image that merely happens to contain strokes.

    Returns (edge_blankness, ink_fraction). A real sheet scores above ~0.9.
    """
    if base + 256 * ncell > len(data):
        return 0.0, 0.0
    edge = edge_total = ink = live = 0
    for g in range(ncell):
        c = data[base + g * 256:base + (g + 1) * 256]
        if not any(c):
            continue
        live += 1
        ink += 256 - c.count(0)
        for x in range(16):
            edge_total += 4
            edge += ((c[x] == 0) + (c[240 + x] == 0)
                     + (c[x * 16] == 0) + (c[x * 16 + 15] == 0))
    if live < 24:
        return 0.0, 0.0
    return edge / edge_total, ink / (live * 256)


def cmd_font(path, outdir=None, threshold=0.80):
    """Sweep every entry at every offset for a glyph grid, and dump the hits.

    Validated: a synthetic glyph sheet scores 1.00; the known icon sheet in
    entry 1098 is found at offset 0x4E20, matching the address derived from
    the disassembly; entries 19 and 21 (pictures) peak at 0.16 and 0.11.
    """
    ent = read_toc(path)
    hits = []
    with open(path, "rb") as f:
        for i, (off, size) in enumerate(ent):
            if size < 256 * 64:
                continue
            f.seek(off)
            data = f.read(size)
            best = (0.0, 0, 0.0)
            for b in range(0, size - 256 * 64, 16):
                sc, ink = _cell_grid_score(data, b)
                # sparse cells satisfy the edge test trivially; a glyph sheet
                # must also carry real ink
                if ink >= 0.12 and sc > best[0]:
                    best = (sc, b, ink)
            if best[0] >= threshold and best[2] >= 0.12:
                hits.append((best[0], i, best[1], best[2], size))
            if i % 100 == 0:
                print(f"  scanning {i}/{len(ent)}...", flush=True)
    hits.sort(reverse=True)
    if not hits:
        print("no glyph grid found in any entry")
        return
    for sc, i, b, ink, size in hits[:25]:
        print(f"entry {i:5d} size={size:8d} offset=0x{b:06x} "
              f"edge-blank={sc:.0%} ink={ink:.0%}")
    if outdir:
        try:
            from PIL import Image
        except ImportError:
            print("(install Pillow to dump sheets)")
            return
        os.makedirs(outdir, exist_ok=True)
        with open(path, "rb") as f:
            for sc, i, b, ink, size in hits[:8]:
                f.seek(ent[i][0])
                data = f.read(size)
                ng = min((size - b) // 256, 16 * 24)
                img = Image.new("L", (16 * 16, ((ng + 15) // 16) * 16))
                px = img.load()
                for g in range(ng):
                    gx, gy = (g % 16) * 16, (g // 16) * 16
                    for y in range(16):
                        for x in range(16):
                            v = data[b + g * 256 + y * 16 + x]
                            px[gx + x, gy + y] = 0 if v == 0 else min(255, 60 + v * 2)
                img = img.resize((img.width * 3, img.height * 3), Image.NEAREST)
                img.save(os.path.join(outdir, f"glyphs_{i:04d}_{b:06x}.png"))
        print(f"sheets written to {outdir}")


def _string_chain(data, base, wide=False, minlen=2, maxlen=80):
    """Walk length-prefixed records from `base`.

    The engine renders text by reading a length byte then that many glyph
    indices, so a script region is a self-validating chain: each length must
    land exactly on the next length. Random data breaks within a few records.
    Returns (record_count, index_bytes, end_offset).
    """
    p = base
    n = total = 0
    lengths = []
    hdr = 2 if wide else 1
    while p < len(data) - hdr:
        L = (data[p] | (data[p + 1] << 8)) if wide else data[p]
        if L < minlen or L > maxlen or p + hdr + L > len(data):
            break
        body = data[p + hdr:p + hdr + L]
        # glyph indices, not arbitrary bytes: index 0 is never drawn, and
        # values below 0x12 are control codes that cannot fill a whole string
        if 0 in body:
            break
        if sum(1 for v in body if v >= 0x12) < L * 0.8:
            break
        p += hdr + L
        n += 1
        total += L
        lengths.append(L)
    # a run of identical short lengths is alignment noise, not dialogue:
    # real text lines vary in length and average more than a few characters
    if n and (len(set(lengths)) < 5 or total / n < 5):
        return 0, 0, base + 1
    return n, total, p


def cmd_script(path, report="script_report.txt", minrec=40):
    """Find candidate script regions: long runs of length-prefixed records."""
    ent = read_toc(path)
    found = []
    with open(path, "rb") as f:
        for i, (off, size) in enumerate(ent):
            if size < 512:
                continue
            f.seek(off)
            data = f.read(size)
            for wide in (False, True):
                b = 0
                while b < size - 4:
                    n, tot, end = _string_chain(data, b, wide)
                    if n >= minrec:
                        found.append((n, i, b, tot, wide, size))
                        b = end
                    else:
                        b += 1
            if i % 100 == 0:
                print(f"  scanning {i}/{len(ent)}...", flush=True)
    found.sort(reverse=True)
    with open(report, "w") as r:
        r.write(f"script chain scan: {len(found)} candidate regions\n")
        for n, i, b, tot, wide, size in found[:200]:
            r.write(f"entry {i:5d} size={size:8d} offset=0x{b:06x} "
                    f"{'u16' if wide else 'u8'}-len  {n} records, "
                    f"{tot} index bytes\n")
    if found:
        for n, i, b, tot, wide, size in found[:15]:
            print(f"entry {i:5d} offset=0x{b:06x} {'u16' if wide else 'u8'} "
                  f"{n} records, {tot} bytes")
    else:
        print("no length-prefixed string chains found")
    print(f"report written to {report}")


def parse_text_entry(data):
    """Parse a script entry into messages, or return None if it isn't one.

    Layout (verified against entry 23 and the live RAM of a running game):
        u8              type tag, consumed by the loader
        u16 * n         message offsets, ascending, memory-relative
                        (file offset = pointer + 1, since the tag is skipped)
        per message:    u8 unit count, then that many u16 units
    Units are glyph indices interleaved with control codes; 0x0066 brackets
    and pads messages.
    """
    if len(data) < 8:
        return None
    table, p = [], 1
    while p < len(data) - 2:
        v = struct.unpack_from("<H", data, p)[0]
        if table and v <= table[-1]:
            break
        table.append(v)
        p += 2
    if len(table) < 4 or table[0] + 1 <= p or table[0] + 1 >= len(data):
        return None
    msgs = []
    for i, ptr in enumerate(table):
        off = ptr + 1
        if off >= len(data):
            break
        count = data[off]
        body = data[off + 1:off + 1 + count * 2]
        if len(body) < count * 2:
            break
        units = [body[k] | (body[k + 1] << 8) for k in range(0, len(body), 2)]
        msgs.append((i, off, units))
    # a real script entry parses most of its table cleanly
    if len(msgs) < max(4, len(table) * 0.8):
        return None
    return msgs


def cmd_text(path, outdir="script", charmap=None):
    """Extract every script entry in the archive as decoded text."""
    cm = {}
    if charmap and os.path.exists(charmap):
        with open(charmap, encoding="utf-8") as fh:
            cm = {int(k, 16): v for k, v in json.load(fh).items()}
    ent = read_toc(path)
    os.makedirs(outdir, exist_ok=True)
    total_e = total_m = 0
    index = []
    with open(path, "rb") as f:
        for i, (off, size) in enumerate(ent):
            if size < 64 or size > 1 << 20:
                continue
            f.seek(off)
            data = f.read(size)
            msgs = parse_text_entry(data)
            if not msgs:
                continue
            total_e += 1
            total_m += len(msgs)
            index.append((i, len(msgs)))
            with open(os.path.join(outdir, f"{i:04d}.txt"), "w",
                      encoding="utf-8") as out:
                out.write(f"# entry {i} (game {i + 1}), {len(msgs)} messages\n")
                for n, moff, units in msgs:
                    out.write(f"\n[{n:04d}] @0x{moff:04x} {len(units)} units\n")
                    out.write("  idx: " + ' '.join(f"{u:04x}" for u in units) + "\n")
                    out.write("  txt: " + ''.join(
                        cm.get(u, f"[{u:03x}]") for u in units) + "\n")
    with open(os.path.join(outdir, "_index.txt"), "w") as out:
        out.write(f"{total_e} script entries, {total_m} messages\n")
        for i, n in index:
            out.write(f"entry {i:5d}  {n:5d} messages\n")
    print(f"{total_e} script entries, {total_m} messages -> {outdir}")


def cmd_learn(scriptdir, text, charmap="charmap_seed.json"):
    """Match transcribed on-screen text to a script message and learn its glyphs.

    Give it the Chinese you can read in a screenshot. It finds the message
    whose index sequence has the same repetition pattern and length, then
    records index -> character for every position at once. Ambiguity is
    reported rather than guessed: if more than one message fits, nothing is
    written.
    """
    text = ''.join(text.split())
    if len(text) < 6:
        print("give at least ~6 characters so the pattern is unique")
        return
    # repetition signature of the transcription
    want = [[j for j in range(len(text)) if text[j] == c][0] for c in text]
    msgs = []
    for fn in sorted(os.listdir(scriptdir)):
        if not fn.endswith(".txt") or fn.startswith("_"):
            continue
        entry = int(fn[:-4])
        n = None
        for line in open(os.path.join(scriptdir, fn), encoding="utf-8"):
            if line.startswith("["):
                n = int(line[1:5])
            elif line.startswith("  idx:"):
                msgs.append((entry, n,
                             [int(x, 16) for x in line.split(":", 1)[1].split()]))
    SPACE = 0x66
    hits = []
    for entry, n, units in msgs:
        u = [v for v in units if v != SPACE]      # spaces aren't transcribed
        if len(u) != len(text):
            continue
        sig = [[j for j in range(len(u)) if u[j] == v][0] for v in u]
        if sig == want:
            hits.append((entry, n, u))
    if not hits:
        print("no message matches that transcription")
        return
    if len(hits) > 1:
        print(f"{len(hits)} messages match - ambiguous, transcribe more text:")
        for e, n, _ in hits[:5]:
            print(f"   entry {e} message {n}")
        return
    entry, n, u = hits[0]
    cm = {}
    if os.path.exists(charmap):
        with open(charmap, encoding="utf-8") as fh:
            cm = {int(k, 16): v for k, v in json.load(fh).items()}
    new = conflict = 0
    for v, c in zip(u, text):
        if v in cm:
            if cm[v] != c:
                print(f"  CONFLICT 0x{v:04x}: had {cm[v]}, now {c}")
                conflict += 1
        else:
            cm[v] = c
            new += 1
    cm[SPACE] = "\u3000"
    with open(charmap, "w", encoding="utf-8") as fh:
        json.dump({f"0x{k:04x}": v for k, v in sorted(cm.items())}, fh,
                  ensure_ascii=False, indent=1)
    print(f"matched entry {entry} message {n}: "
          f"{new} new, {conflict} conflicts, {len(cm)} mapped total")


def find_index_arrays(data, minunits=24, ceiling=0x800):
    """Find flat arrays of glyph indices that have no offset table.

    Item names, menu labels and character names are stored as fixed-width
    records padded with the full-width space 0x0066, with no header, so the
    message parser skips them entirely. They show up as long aligned runs of
    small u16 values containing spaces.
    """
    runs = []
    n = len(data) // 2
    u = [data[2 * i] | (data[2 * i + 1] << 8) for i in range(n)]
    i = 0
    while i < n:
        if u[i] >= ceiling:
            i += 1
            continue
        j = i
        while j < n and u[j] < ceiling:
            j += 1
        seg = u[i:j]
        if len(seg) >= minunits and 0x66 in seg:
            uniq = len(set(seg))
            top = max(collections.Counter(seg).values())
            # real text is varied; padding and counters are not
            if uniq >= len(seg) * 0.35 and top <= len(seg) * 0.4:
                runs.append((i * 2, seg))
        i = max(j, i + 1)
    return runs


def cmd_tables(path, outdir="tables", charmap="charmap_seed.json"):
    """Extract flat index arrays (menu, item, spell and character names).

    UNVALIDATED. This finds nothing on a RAM region known to contain the
    character-name table, so the heuristic is wrong somewhere. Kept as a
    starting point, not as a working tool - see docs/STATUS.md.
    """
    cm = {}
    if os.path.exists(charmap):
        with open(charmap, encoding="utf-8") as fh:
            cm = {int(k, 16): v for k, v in json.load(fh).items()}
    ent = read_toc(path)
    os.makedirs(outdir, exist_ok=True)
    found = units = 0
    with open(path, "rb") as f:
        for i, (off, size) in enumerate(ent):
            if size < 128 or size > 1 << 20:
                continue
            f.seek(off)
            runs = find_index_arrays(f.read(size))
            if not runs:
                continue
            found += 1
            units += sum(len(s) for _, s in runs)
            with open(os.path.join(outdir, f"{i:04d}.txt"), "w",
                      encoding="utf-8") as out:
                out.write(f"# entry {i}: {len(runs)} index arrays\n")
                for o, seg in runs:
                    out.write(f"\n@0x{o:05x}  {len(seg)} units\n")
                    out.write("  idx: " + ' '.join(f"{v:04x}" for v in seg) + "\n")
                    out.write("  txt: " + ''.join(
                        cm.get(v, f"[{v:03x}]") for v in seg) + "\n")
            if i % 200 == 0:
                print(f"  scanning {i}/{len(ent)}...", flush=True)
    print(f"{found} entries contain index arrays, {units} units -> {outdir}")


def cmd_pack(indir, outpath):
    files = sorted(f for f in os.listdir(indir)
                   if f.endswith(".bin") and f[0].isdigit())
    gaps = {}
    gp = os.path.join(indir, "_gaps.bin")
    if os.path.exists(gp):
        raw = open(gp, "rb").read()
        cnt = struct.unpack_from("<H", raw, 0)[0]
        p = 2
        for _ in range(cnt):
            idx, ln = struct.unpack_from("<IH", raw, p)
            p += 6
            gaps[idx] = raw[p:p + ln]
            p += ln
    blobs = [open(os.path.join(indir, f), "rb").read() for f in files]
    toc, off = [], TOC_BASE
    for i, b in enumerate(blobs):
        toc.append((off, len(b)))
        off += len(b) + len(gaps.get(i, b""))
    with open(outpath, "wb") as f:
        f.write(struct.pack("<H", len(blobs)))
        for o, s in toc:
            f.write(struct.pack("<II", o, s))
        f.write(b"\x00" * (TOC_BASE - f.tell()))
        for i, b in enumerate(blobs):
            f.write(b)
            if i in gaps:
                f.write(gaps[i])
    print(f"wrote {outpath} ({os.path.getsize(outpath)} bytes, {len(blobs)} entries)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "list":
        cmd_list(sys.argv[2])
    elif cmd == "extract":
        cmd_extract(sys.argv[2], sys.argv[3])
    elif cmd == "scan":
        cmd_scan(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "scan_report.txt")
    elif cmd == "tables":
        cmd_tables(sys.argv[2],
                   sys.argv[3] if len(sys.argv) > 3 else "tables",
                   sys.argv[4] if len(sys.argv) > 4 else "charmap_seed.json")
    elif cmd == "learn":
        cmd_learn(sys.argv[2], sys.argv[3],
                  sys.argv[4] if len(sys.argv) > 4 else "charmap_seed.json")
    elif cmd == "text":
        cmd_text(sys.argv[2],
                 sys.argv[3] if len(sys.argv) > 3 else "script",
                 sys.argv[4] if len(sys.argv) > 4 else "charmap_seed.json")
    elif cmd == "script":
        cmd_script(path=sys.argv[2],
                   report=sys.argv[3] if len(sys.argv) > 3 else "script_report.txt")
    elif cmd == "loadmap":
        cmd_loadmap(sys.argv[2],
                    sys.argv[3] if len(sys.argv) > 3 else "loadmap.txt")
    elif cmd == "find":
        cmd_find(sys.argv[2], " ".join(sys.argv[3:]))
    elif cmd == "render":
        cmd_render(sys.argv[2], sys.argv[3],
                   int(sys.argv[4]) if len(sys.argv) > 4 else 320)
    elif cmd == "pack":
        cmd_pack(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
