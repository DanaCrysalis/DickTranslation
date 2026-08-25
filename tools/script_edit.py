#!/usr/bin/env python3
"""
script_edit.py - rewrite a dialogue entry with messages of different lengths

Every reinsertion tool in this repository so far has been deliberately
length-preserving, to avoid touching the offset table. A translation cannot be:
English needs roughly 1.5x the units even packed two letters per glyph, and only
17.8% of the retail script is recoverable full-width padding. Entries must grow,
which means rebuilding the offset table and letting every later message move.

Entry layout (see docs/FORMATS.md):

    u8        type tag
    u16 * n   message offsets, ascending, MEMORY-relative: file = ptr + 1
              the table ends where the first message begins
    per message:
      u8      unit count      <-- HARD CEILING 255
      u16 * n units

Commands:

    python tools/script_edit.py dump 0023.bin
    python tools/script_edit.py grow 0023.bin 3 20 0023.new.bin
    python tools/script_edit.py set  0023.bin 3 "0011 0066 0012" 0023.new.bin
    python tools/script_edit.py push 0023.bin 62 0023.new.bin
    python tools/script_edit.py verify 0023.bin dialogue.xlsx 23
    python tools/script_edit.py selftest

`grow` appends N full-width spaces (0x0066) to one message. It is the safest
possible length change: the text still renders identically, so if anything breaks
it is the container, not the content.

After writing, repack and run:

    python tools/dickdat.py pack out/ DICK.DAT.new

WARNING: patch_poc.py and glyphdump.py hold hardcoded absolute file offsets. Once
any entry changes size every later entry shifts, and those constants are wrong.
Re-derive them from the TOC before using either tool on a repacked archive.
"""
import struct
import sys

SPACE = 0x0066
MAX_UNITS = 255


def parse(blob):
    """-> (tag, [ [unit,...], ... ]).  Mirrors dickdat.cmd_script."""
    tag = blob[0]
    first = struct.unpack_from("<H", blob, 1)[0]
    ptrs = []
    p = 1
    while p + 2 <= len(blob):
        v = struct.unpack_from("<H", blob, p)[0]
        if ptrs and (v < ptrs[-1] or v >= first + 1 and p >= first):
            break
        if p - 1 >= first:
            break
        ptrs.append(v)
        p += 2
    msgs = []
    for ptr in ptrs:
        off = ptr + 1
        if off >= len(blob):
            msgs.append([])
            continue
        n = blob[off]
        units = list(struct.unpack_from("<%dH" % n, blob, off + 1)) \
            if off + 1 + 2 * n <= len(blob) else []
        msgs.append(units)
    return tag, msgs


def build(tag, msgs):
    """Inverse of parse. Offsets are recomputed, so messages may change length."""
    for i, m in enumerate(msgs):
        if len(m) > MAX_UNITS:
            raise ValueError("message %d has %d units; the count is a u8 "
                             "(max %d). Split it." % (i, len(m), MAX_UNITS))
    table = 2 * len(msgs)
    body, ptrs = bytearray(), []
    for m in msgs:
        # ptr is memory-relative: file offset = ptr + 1
        ptrs.append(1 + table + len(body) - 1)
        body.append(len(m))
        for u in m:
            body += struct.pack("<H", u)
    out = bytearray([tag])
    for p in ptrs:
        out += struct.pack("<H", p)
    out += body
    if ptrs and ptrs[0] + 1 != 1 + table:
        raise AssertionError("pointer/table mismatch")
    if len(out) - 1 > 0xFFFF:
        raise ValueError("entry payload %d bytes exceeds the u16 offset ceiling"
                         % (len(out) - 1))
    return bytes(out)


def cmd_dump(path):
    tag, msgs = parse(open(path, "rb").read())
    total = sum(len(m) for m in msgs)
    print("tag=0x%02x  %d messages, %d units" % (tag, len(msgs), total))
    print("payload %d bytes of 65535 (headroom %d)"
          % (1 + 2 * len(msgs) + sum(1 + 2 * len(m) for m in msgs),
             65535 - (1 + 2 * len(msgs) + sum(1 + 2 * len(m) for m in msgs))))
    near = [i for i, m in enumerate(msgs) if len(m) > 200]
    print("messages over 200 units (near the 255 ceiling): %s" % (near or "none"))
    for i, m in enumerate(msgs[:12]):
        print("  %3d  %3d units  %s" % (i, len(m),
                                        " ".join("%04x" % u for u in m[:10])))
    if len(msgs) > 12:
        print("  ... %d more" % (len(msgs) - 12))


def cmd_grow(path, idx, n, out):
    tag, msgs = parse(open(path, "rb").read())
    before = len(msgs[idx])
    msgs[idx] = msgs[idx] + [SPACE] * n
    blob = build(tag, msgs)
    open(out, "wb").write(blob)
    print("message %d: %d -> %d units; entry now %d bytes"
          % (idx, before, len(msgs[idx]), len(blob)))
    print("wrote %s" % out)


def cmd_set(path, idx, spec, out):
    tag, msgs = parse(open(path, "rb").read())
    units = [int(t, 16) for t in spec.split()]
    before = len(msgs[idx])
    msgs[idx] = units
    blob = build(tag, msgs)
    open(out, "wb").write(blob)
    print("message %d: %d -> %d units; entry now %d bytes"
          % (idx, before, len(units), len(blob)))
    print("wrote %s" % out)


def cmd_push(path, idx, out, target=None):
    """Pad every message BEFORE idx with full-width spaces, up to the 255-unit
    ceiling, so that message idx is driven as deep into the entry as possible.

    This is the only way to probe for a fixed read-size cap when the only
    reachable dialogue sits near the front of the entry: instead of growing the
    tail (which you cannot see), push a message you CAN reach out past the
    suspect boundary. If it still renders, the entry really is that big in
    memory."""
    tag, msgs = parse(open(path, "rb").read())
    if idx >= len(msgs):
        raise SystemExit("entry has only %d messages" % len(msgs))
    for i in range(idx):
        room = MAX_UNITS - len(msgs[i])
        if room > 0:
            msgs[i] = msgs[i] + [SPACE] * room
    blob = build(tag, msgs)
    # where does idx now start?
    off = 1 + 2 * len(msgs) + sum(1 + 2 * len(m) for m in msgs[:idx])
    open(out, "wb").write(blob)
    print("padded messages 0-%d to the %d-unit ceiling" % (idx - 1, MAX_UNITS))
    print("message %d now begins at byte %d of %d" % (idx, off, len(blob)))
    print("wrote %s" % out)
    print()
    print("In game: talk to that NPC. If the line renders normally, the entry")
    print("is fully resident at %d bytes. If it is blank or garbled, the read" % len(blob))
    print("is capped somewhere below byte %d." % off)


def _xlsx_rows(path, sheet_name):
    """Minimal .xlsx reader: stdlib only, so this tool keeps dickdat.py's
    zero-dependency rule. Yields dicts of column-letter -> string."""
    import zipfile
    import xml.etree.ElementTree as ET
    NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    RS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    PK = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(NS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(NS + "t")))
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = {r.get("Id"): r.get("Target") for r in rels.findall(PK + "Relationship")}
        path_in_zip = None
        for sh in wb.iter(NS + "sheet"):
            if sh.get("name") == sheet_name:
                t = target[sh.get(RS + "id")]
                path_in_zip = "xl/" + t.lstrip("/").replace("xl/", "", 1)
        if path_in_zip is None:
            raise SystemExit("sheet %r not found in %s" % (sheet_name, path))
        ws = ET.fromstring(z.read(path_in_zip))
        for row in ws.iter(NS + "row"):
            out = {}
            for c in row.findall(NS + "c"):
                ref = c.get("r") or ""
                col = "".join(ch for ch in ref if ch.isalpha())
                v = c.find(NS + "v")
                if c.get("t") == "s" and v is not None:
                    out[col] = shared[int(v.text)]
                elif c.get("t") == "inlineStr":
                    out[col] = "".join(t.text or "" for t in c.iter(NS + "t"))
                elif v is not None:
                    out[col] = v.text
            if out:
                yield out


def cmd_verify(path, xlsx, entry):
    """Cross-check parse() against dialogue.xlsx.

    selftest only round-trips this tool's own output, so it cannot catch a
    misparse of a real entry. This can: the spreadsheet holds an independently
    extracted unit list for every message."""
    tag, msgs = parse(open(path, "rb").read())
    ref = {}
    for row in _xlsx_rows(xlsx, "Dialogue"):
        try:
            if int(row.get("A", -1)) != entry:
                continue
            ref[int(row["B"])] = [int(h, 16) for h in row["I"].split()]
        except (ValueError, KeyError, TypeError):
            continue
    if not ref:
        raise SystemExit("no rows for entry %d found in %s" % (entry, xlsx))
    print("parsed %d messages; spreadsheet has %d (max index %d)"
          % (len(msgs), len(ref), max(ref)))
    if len(msgs) != max(ref) + 1:
        print("!! MESSAGE COUNT MISMATCH - the pointer table was misdetected.")
        print("   Everything this tool writes would be wrong. Stop here.")
        return
    bad = [i for i, u in ref.items() if i < len(msgs) and msgs[i] != u]
    if not bad:
        print("OK: all %d messages match the spreadsheet unit-for-unit." % len(ref))
        return
    print("!! %d messages differ: %s" % (len(bad), bad[:12]))
    for i in bad[:3]:
        print("   msg %d  file: %s" % (i, " ".join("%04x" % v for v in msgs[i][:10])))
        print("          xlsx: %s" % " ".join("%04x" % v for v in ref[i][:10]))
    if set(bad) & {0, 61, 62}:
        print("   Messages 0/61/62 are glyphdump's targets - the archive still")
        print("   carries a dump pass and is not pristine.")


def cmd_selftest():
    """Round-trip against a synthetic entry built to the documented layout."""
    msgs = [[0x11, 0x66, 0x12], [0x5D, 0x5E], list(range(0x20, 0x20 + 200)), []]
    blob = build(0x01, msgs)
    tag, back = parse(blob)
    assert tag == 0x01, tag
    assert back == msgs, (back[:2], msgs[:2])
    # a length change must round-trip too
    msgs[0] = msgs[0] + [SPACE] * 40
    blob2 = build(0x01, msgs)
    _, back2 = parse(blob2)
    assert back2 == msgs
    assert len(blob2) == len(blob) + 80, (len(blob2), len(blob))
    try:
        build(0x01, [[0] * 256])
    except ValueError as e:
        assert "u8" in str(e)
    else:
        raise AssertionError("u8 ceiling not enforced")
    print("selftest OK: parse/build round-trip, +40 units grew entry by 80 bytes,")
    print("             255-unit ceiling enforced")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    c = sys.argv[1]
    if c == "selftest":
        cmd_selftest()
    elif c == "dump":
        cmd_dump(sys.argv[2])
    elif c == "grow":
        cmd_grow(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5])
    elif c == "verify":
        cmd_verify(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    elif c == "push":
        cmd_push(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    elif c == "set":
        cmd_set(sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5])
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
