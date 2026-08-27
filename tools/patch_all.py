#!/usr/bin/env python3
"""
patch_all.py - build a playable English archive: dialogue, tables and UI in one pass

insert_english.py sets the dialogue and nothing else, and it consumes every slot
in data/free_slots.txt doing it. names.py and uitext.py each allocate from the top
of that same list, independently, so running any two of them repaints each other's
cells and the item names come out spelled in the dialogue's letters. The fix is
not to run them in a careful order - it is to allocate ONCE for every English
string in the project. That is what this does.

    python tools/patch_all.py find  out_clean/ 接受
    python tools/patch_all.py plan  dialogue.xlsx out_clean/
    python tools/patch_all.py build dialogue.xlsx out_clean/ out_en/
    python tools/dickdat.py pack out_en/ DICK.DAT.new

WHAT GETS PATCHED
  entries 23, 249, 390, 625, 794   dialogue, variable length, entry regrows
  entry 1098                       item / spell / skill / plot names and
                                   descriptions, FIXED width, in place
  entry 48                         UI strings marked done, FIXED width, in place
  entry 4                          the font

WHERE THE SLOTS COME FROM
data/free_slots.txt lists 539 slots, which is not enough: the fixed-width strings
alone want 496 distinct pairs before the dialogue asks for anything. But that list
was drawn up when only the battle UI was being translated. Once the dialogue and
the tables are ENGLISH, every glyph that only they used is free as well, and that
is another 1,291 slots.

So the pool is computed rather than read: start from all 2048, subtract every
index still referenced by Chinese this patch does NOT replace - the untranslated
UI rows in all five overlays - and subtract 0x066 and 0x593. About 1,830 slots.

THE RISK IN THAT, STATED PLAINLY: it assumes the UI sheet has found every Chinese
string in the overlays. If some overlay carries text nobody has catalogued, its
glyphs may be repainted and it will render as Latin nonsense. Nothing crashes and
no save is corrupted, but it is why this is a test build. Run with --safe-slots to
use only the original 539 instead; the fixed-width text will then not fit and the
tool will say so.

FIXED WIDTH MEANS FIXED
A table field of n units must receive exactly n units. Text is packed two letters
to a cell, and where a pair has no slot it falls back to a single-letter cell,
which costs an extra cell - so a string can overflow its field even though its
character count fits. Allocation therefore has to guarantee the fixed-width
strings first and give the dialogue what is left; the dialogue can absorb a
fallback anywhere, a table field cannot.

~~ marks a cell the engine fills at draw time and becomes 0x0000.
"""
import collections
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import script_edit  # noqa: E402
import insert_english as ie  # noqa: E402

SPACE = 0x0066
FILLED = 0x0000
DIALOGUE = (23, 249, 390, 625, 794)

# entry 1098 field geometry, see docs/FORMATS.md
# The main table's NAME FIELDS run 0x0001 + n * 0x50. Everything inherited the
# framing "record base 0x145, name at base + 0x4C", which cannot express the
# first record at all - its base would be negative - so record 0, 鐵劍, was
# invisible to every tool and stayed Chinese at the top of every shop list.
# Iterate the fields, not the bases.
MAIN_FIRST, MAIN_STRIDE, MAIN_END = 0x0005, 0x50, 0x4E20
NAME_GRID = 0x0001
NAME_OFF, NAME_UNITS = 0x4C, 5
DESC_OFF, DESC_UNITS = 0x5C, 12
SKILL_AT, SKILL_STRIDE = 0x07F21, 0x2A
PLOT_AT, PLOT_STRIDE = 0x08F89, 0x50


def pack(s, alloc):
    """Greedy two-letters-per-cell packing with single-letter fallback."""
    out, i = [], 0
    while i < len(s):
        if s[i:i + 2] == "~~":
            out.append("~~")
            i += 2
        elif i + 1 < len(s) and "~" not in s[i:i + 2] and (
                s[i:i + 2] in alloc or s[i + 1] == " "):
            # "~" never pairs with anything but itself. A run of engine-filled
            # cells has to START on a cell boundary: pair the space before it
            # with the first tilde and the run slides by one, leaving a lone
            # "~ " cell that maps to nothing and a placeholder in the wrong place.
            # A cell whose right half is a space IS the single-letter cell, so
            # it always exists and consumes BOTH characters. Treating it as a
            # fallback instead wastes one cell per word, which was enough on its
            # own to push most item descriptions out of their fields.
            out.append(s[i:i + 2])
            i += 2
        else:
            out.append(s[i] + " ")
            i += 1
    return out


# ------------------------------------------------------------------ gathering

def gather(xlsx):
    """-> (dialogue, fixed) where fixed is [(where, offset, units, text)]."""
    dialogue = ie.read_dialogue(xlsx)
    fixed = []
    for row in script_edit._xlsx_rows(xlsx, "Item-Spell-Monster"):
        off = row.get("B")
        if not off or not off.startswith("0x"):
            continue
        o = int(off, 16)
        if row.get("F"):
            fixed.append(("1098", o, NAME_UNITS, row["F"]))
        if row.get("G"):
            fixed.append(("1098d", o, DESC_UNITS, row["G"]))
    for row in script_edit._xlsx_rows(xlsx, "UI strings"):
        if row.get("A") != "48" or row.get("G") != "done":
            continue
        off, units, eng = row.get("B"), row.get("C"), row.get("F")
        if not (off and units and eng and off.startswith("0x")):
            continue
        fixed.append(("48", int(off, 16), int(units), eng))
    return dialogue, fixed


def ui_rows(xlsx):
    """Every UI row that has English: (offset_or_None, units, chinese, english)."""
    out = []
    for row in script_edit._xlsx_rows(xlsx, "UI strings"):
        if row.get("G") != "done":
            continue
        ch, units, eng, off = (row.get("E"), row.get("C"),
                               row.get("F"), row.get("B"))
        if ch and units and eng:
            o = int(off, 16) if off and off.startswith("0x") else None
            out.append((o, int(units), ch, eng))
    return out


def source_pattern(ref, o, n, chinese, cmi):
    """The exact unit run to search for, taken from the FILE rather than rebuilt
    from the spreadsheet's Chinese.

    Rebuilding does not work for every row. A menu label spaces its characters
    apart (攻 0x0066 擊) and the character-name table spreads a two-character
    name across three cells (狄 0x0066 克), so the sheet's "狄克" is two units
    while the field is three and the bytes never match. Reading the run out of
    entry 48 sidesteps the whole question - and the offset column is not
    consistent about whether it points at the count word or at the field, so
    both are tried and the one that decodes to the row's own characters wins.
    """
    if o is None or ref is None:
        return None
    want = "".join(c for c in chinese if c not in "\u00b7_")
    loose = None
    for at in (o + 2, o):
        if at < 0 or at + 2 * n > len(ref):
            continue
        u = [struct.unpack_from("<H", ref, at + 2 * k)[0] for k in range(n)]
        txt = "".join(cmi.get(v, "") for v in u if v not in (0, SPACE))
        if txt == want:
            return u          # exact: this is the right interpretation
        if txt and all(c in txt for c in want) and loose is None:
            loose = u
    # Containment alone is not enough. The one-character name 琳 is CONTAINED by
    # the run starting one unit later (琳 法, reaching into the next name's
    # field), so a contains-test picked a pattern that straddled two records and
    # wrote Fran's first cell over Lin's padding. Equality settles it.
    return loose


def header_ok(data, at, n):
    """Is `at` really the start of a drawn string, not a coincidence?

    Content search alone is not safe for short strings, because the low glyph
    indices are also small NUMBERS: 是 is 0x000B and 好 is 0x000E, so a bare byte
    search for the one-unit menu label 是 matched 37 places in entry 48, nearly
    all of them numeric fields. The record header settles it - the two u16s in
    front must be a screen position inside a 320-wide frame and a count equal to
    the string's length, and the string must fit the line at 16 pixels a glyph.
    """
    if at < 4:
        return False
    pos = struct.unpack_from("<H", data, at - 4)[0]
    cnt = struct.unpack_from("<H", data, at - 2)[0]
    if cnt != n or not (0 < pos < 0xFA00):
        return False
    return pos % 320 + n * 16 <= 320


def find_all(data, pat):
    blob = b"".join(struct.pack("<H", v) for v in pat)
    out, i = [], data.find(blob)
    while i >= 0:
        out.append(i)
        i = data.find(blob, i + 2)
    return out


def scan_overlays(srcdir, xlsx, charmap, loose=False, skip_tables=False,
                  min_hits=20):
    """-> (keep, hits): glyphs to preserve, and every place we can write English.

    Matching is by CONTENT, everywhere, with no record detection at all. The
    first build detected records by their screen-position header and translated
    entry 48 only; that missed 姓名： (its y is 7, below the geometry filter's
    floor) and left four other overlay copies of every menu in Chinese, whose
    glyph slots the allocator had already repainted. The menus and the status
    screen came out as Latin nonsense while the dialogue read correctly.

    Everything that is NOT going to be replaced has its glyphs reserved, judged
    from the files rather than from the spreadsheet: a run of two or more
    consecutive mapped glyphs that no replacement covers is assumed to be text
    somebody still has to read.
    """
    cmi = {int(k, 16): v for k, v in charmap.items()}
    rows = ui_rows(xlsx)
    ref = None
    p48 = os.path.join(srcdir, "0048.bin")
    if os.path.exists(p48):
        ref = open(p48, "rb").read()
    # Rows in the character-name table are a BARE array with no record header.
    # They are the only strings allowed to be matched without one, and even then
    # only in an entry that has already produced a header-validated match, so a
    # pure code entry is never written into on the strength of a byte pattern.
    BARE = range(0x014C0, 0x01500)
    pats = []
    for o, n, ch, eng in rows:
        u = source_pattern(ref, o, n, ch, cmi)
        if u is None:
            u = [cmi_inv[c] for c in ch] if False else None
        if u is None:
            inv = {}
            for k, v in charmap.items():
                inv.setdefault(v, int(k, 16))
            if all(c in inv for c in ch) and len(ch) == n:
                u = [inv[c] for c in ch]
        if u is not None and len(u) == n:
            pats.append((u, n, eng, o is not None and o in BARE))

    # 0x0000 is the character 一 AND the engine's placeholder; 0x0066 is the
    # full-width space; 0x0593 is script-referenced. A pool built by subtraction
    # has to name each of them.
    keep = {FILLED, SPACE, 0x593}
    # Reserve every glyph any catalogued Chinese uses, translated or not. Cheap
    # insurance against the failure this keeps producing: a string we did not
    # find, drawn from a copy we did not know about, with its glyphs repainted
    # underneath it. The HP separator "/" was a one-unit record at screen
    # position 0, which no header test will accept, so it was neither replaced
    # nor reserved and rendered as "Ic".
    inv = {}
    for k, v in charmap.items():
        inv.setdefault(v, int(k, 16))
    sheets = [("UI strings", "E")]
    if not skip_tables:
        # Entry 1098 is rewritten field by field at known offsets, so reserving
        # its Chinese is belt-and-braces rather than necessary. It is the first
        # thing to drop if the pool runs short: --no-reserve-tables.
        sheets += [("Item-Spell-Monster", "D"), ("Item-Spell-Monster", "E")]
    for sheet, col in sheets:
        for row in script_edit._xlsx_rows(xlsx, sheet):
            for ch in (row.get(col) or ""):
                if ch in inv:
                    keep.add(inv[ch])
    hits = collections.defaultdict(list)
    for name in sorted(os.listdir(srcdir)):
        if not name.endswith(".bin"):
            continue
        num = name[:-4]
        if not num.isdigit() or int(num) in DIALOGUE or int(num) == 1098:
            continue
        data = open(os.path.join(srcdir, name), "rb").read()
        if data[:2] == b"MZ":
            continue        # never write into an executable on a byte match
        covered = set()
        anchored = False
        for u, n, eng, bare in sorted(pats, key=lambda p: (-p[1], p[3])):
            for at in find_all(data, u):
                # Longest first, and never inside something already claimed:
                # 回復系 is a substring of 現在不可使用非回復系魔法, and 攻擊力 of
                # ___三回合攻擊力上升, so a short pattern will happily match in
                # the middle of a longer string and overwrite six characters of
                # it with an unrelated label.
                if any(b in covered for b in range(at, at + 2 * n)):
                    continue
                # A HEADER IS NOW REQUIRED for everything except the bare
                # character-name array. Trusting a three-unit run on its own let
                # writes land inside larger untranslated strings and inside
                # binary: 身體： matched in the middle of 身體狀況： and turned
                # the status line half Latin, and somewhere in a code entry a
                # match corrupted the battle routine badly enough to lock the
                # game up. The header is what says "this is a string the engine
                # draws" rather than "these bytes happen to look like one".
                if not header_ok(data, at, n):
                    if not (bare and anchored):
                        continue
                else:
                    anchored = True
                hits[num].append((at - 2, n, eng))   # -2: caller writes at at+2
                covered.update(range(at, at + 2 * n))
        # Reserve the glyphs of every string we are NOT replacing. Two earlier
        # rules both failed on the full archive. Reserving any run of three
        # mapped glyphs anywhere took 1,482 indices and left 566 slots, one short
        # of what the fixed-width text alone needed - most of them coincidence,
        # since a mapped glyph index is a common u16 value and an image entry has
        # millions of positions to be lucky in. Demanding a record header
        # immediately before the RUN then reserved almost nothing, because a run
        # breaks at every pad: a record like 現在·不可 starts its second run in
        # the middle of itself, where no header is.
        #
        # So walk the records instead, and reserve the mapped units of any record
        # that no replacement covers.
        i = 0
        while i + 4 < len(data):
            pos = struct.unpack_from("<H", data, i)[0]
            n = struct.unpack_from("<H", data, i + 2)[0]
            if (1 <= n <= 40 and 0 < pos < 0xFA00
                    and pos % 320 + n * 16 <= 320
                    and i + 4 + 2 * n <= len(data)):
                u = [struct.unpack_from("<H", data, i + 4 + 2 * k)[0]
                     for k in range(n)]
                good = [v for v in u if v in cmi and v not in (0, SPACE)]
                if len(good) >= 2 and all(v in cmi or v in (0, SPACE) for v in u):
                    if not any(b in covered
                               for b in range(i + 4, i + 4 + 2 * n)):
                        keep.update(good)
                    i += 4 + 2 * n
                    continue
            i += 2
        if loose:
            i, run = 0, []
            while i + 1 < len(data):
                v = struct.unpack_from("<H", data, i)[0]
                if v in cmi and v not in (0, SPACE) and i not in covered:
                    run.append(v)
                else:
                    if len(run) >= 3:
                        keep.update(run)
                    run = []
                i += 2
    # An entry that carries the UI block matches DOZENS of strings - the
    # standard menu and status set is 94 records, and the battle overlays run to
    # about 150. An entry that matches one or two is almost certainly a
    # coincidence in image or audio data, and writing English into it corrupts
    # whatever those bytes really were. The third build wrote to every entry with
    # a single hit and came back with a battle screen full of noise bands.
    thin = {k: v for k, v in hits.items() if len(v) < min_hits}
    for k, v in thin.items():
        for at, n, eng in v:
            pass
        del hits[k]
    if thin:
        print("skipped %d entries with fewer than %d matches (likely "
              "coincidence): %s" % (len(thin), min_hits,
                                    ", ".join(sorted(thin))))
    return keep, hits


# ---------------------------------------------------------------- allocation

def allocate(dialogue, fixed, pool):
    """Fixed-width strings get their pairs first; the dialogue gets the rest.

    A dialogue line can always fall back to single-letter cells and simply take
    one cell more. A table field cannot - it has n units and that is that - so
    the guarantee has to run in that order.
    """
    chars = {c for _, _, _, t in fixed for c in t}
    for msgs in dialogue.values():
        for t in msgs.values():
            chars |= set(t)
    chars.discard("\n")
    chars.discard("~")
    singles = sorted(chars)

    need = collections.Counter()
    ALL = ie._All()
    for _, _, _, t in fixed:
        for c in pack(t, ALL):
            if len(c) == 2 and c[1] != " " and c != "~~":
                need[c] += 1
    want = collections.Counter()
    for msgs in dialogue.values():
        for t in msgs.values():
            for c in ie.cells_of(t, ALL):
                if c not in ("  ", "~~") and c[1] != " ":
                    want[c] += 1

    room = len(pool) - len(singles)
    if room < len(need):
        print("NOT ENOUGH GLYPH SLOTS: the fixed-width text alone needs %d pairs"
              " and only %d are free after reserving %d singles."
              % (len(need), room, len(singles)))
        print("Every one of those pairs is mandatory - a table field is n units"
              " and cannot grow, so a pair that falls back to two single-letter"
              " cells pushes the string out of its field.")
        print("Either free more slots (see the reservation note in scan_overlays)"
              " or shorten the fixed-width English.")
        return singles, set(list(need)[:room]), need, want
    alloc = set(need)
    for c, _ in want.most_common():
        if len(alloc) >= room:
            break
        alloc.add(c)
    return singles, alloc, need, want


def fits(fixed, alloc):
    return [(w, o, n, t) for w, o, n, t in fixed if len(pack(t, alloc)) > n]


# --------------------------------------------------------------------- output

def encode_fixed(text, units, alloc, cellmap, orig=None):
    """orig is the field's ORIGINAL units, so a ~~ cell can keep what was there.

    A ~~ cell is one the engine overwrites at draw time, and WHICH pad it holds
    matters: 0x0066 receives digits, 0x0000 receives a name. Writing 0x0000
    everywhere put the character 一 - a horizontal bar - into the six cells the
    equipment line reserves for an item name, which is the row of dashes in
    'Head: Bronze-Pin-Attack'. Copying the original unit is both simpler and
    right by construction.
    """
    cells = pack(text, alloc)
    if len(cells) > units:
        raise ValueError("%r needs %d units, field is %d" % (text, len(cells), units))
    out = []
    for i, c in enumerate(cells):
        if c == "~~":
            out.append(orig[i] if orig and i < len(orig) else FILLED)
        elif c == "  ":
            out.append(SPACE)
        else:
            out.append(cellmap[c])
    return out + [SPACE] * (units - len(out))


def describe_tail(tail, used, raw):
    """What is actually sitting after the script block?

    The refusal this replaces was too cautious. "Not a single repeated byte" is
    not the same as "real data": the entries are fixed 65537-byte buffers and the
    space past the script may simply be whatever was in memory when the archive
    was built. This reports enough to tell the difference - how big it is, how
    many distinct byte values, the commonest one, and whether it opens with
    anything that parses as a script header.
    """
    if not tail:
        return "none"
    hist = collections.Counter(tail)
    top, n = hist.most_common(1)[0]
    bits = ["%d bytes" % len(tail),
            "%d distinct values" % len(hist),
            "%.0f%% are 0x%02X" % (100.0 * n / len(tail), top)]
    if len(tail) > 3:
        cnt = struct.unpack_from("<H", tail, 1)[0]
        if 1 <= cnt <= 4000:
            bits.append("opens like a script block of %d messages" % cnt)
    return ", ".join(bits)


def msgs_patched(msgs, texts, alloc, cellmap, tight, e, ie):
    out = list(msgs)
    for m, text in texts.items():
        if m < len(out):
            out[m] = ie.encode(ie.cells_of(text, alloc, (e, m) in tight), cellmap)
    return out


def cmd_find(srcdir, needle, charmap):
    """Where does this Chinese string live, and what is its record?

    Adding a UI row needs the exact unit count, and the string is usually in an
    overlay nobody has dumped. This searches every entry and prints the record
    header, so a row can be written straight into the spreadsheet.
    """
    cmi = {int(k, 16): v for k, v in charmap.items()}
    inv = {}
    for k, v in charmap.items():
        inv.setdefault(v, int(k, 16))
    missing = [c for c in needle if c not in inv]
    if missing:
        print("not in the charmap: %s" % " ".join(missing))
        return 1
    pat = b"".join(struct.pack("<H", inv[c]) for c in needle)
    found = headerless = 0
    for name in sorted(os.listdir(srcdir)):
        if not name.endswith(".bin"):
            continue
        data = open(os.path.join(srcdir, name), "rb").read()
        at = data.find(pat)
        while at >= 0:
            pos = struct.unpack_from("<H", data, at - 4)[0] if at >= 4 else -1
            n = struct.unpack_from("<H", data, at - 2)[0] if at >= 2 else -1
            if 1 <= n <= 40:
                u = [struct.unpack_from("<H", data, at + 2 * k)[0]
                     for k in range(n)]
                txt = "".join("\u00b7" if v == SPACE else "_" if v == 0
                              else cmi.get(v, ".") for v in u)
                print("entry %-5s 0x%05X  pos=0x%04X (x=%d y=%d) n=%-3d %s"
                      % (name[:-4], at - 2, pos, pos % 320, pos // 320, n, txt))
                found += 1
            else:
                # Report headerless hits too. A string can sit in a bare array,
                # or start partway into a record - the shop's price prompt does
                # both, which is why searching for 買下 came back empty while the
                # words are plainly on screen. Show the surrounding units so the
                # real record start is visible.
                lo = max(0, at - 16)
                u = [struct.unpack_from("<H", data, lo + 2 * k)[0]
                     for k in range((at - lo) // 2 + 12)
                     if lo + 2 * k + 1 < len(data)]
                txt = "".join("\u00b7" if v == SPACE else "_" if v == 0
                              else cmi.get(v, ".") for v in u)
                print("entry %-5s 0x%05X  (no header)  ...%s..."
                      % (name[:-4], at, txt))
                headerless += 1
            at = data.find(pat, at + 2)
    if not found and not headerless:
        print("%r does not occur in any entry" % needle)
    elif not found:
        print("\n%d occurrences, none with a record header in front - the string"
              " is inside a\nbare array or starts partway into a record."
              % headerless)
    return 0


def cmd(argv, build):
    xlsx, srcdir = argv[2], argv[3]
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    charmap = json.load(open(os.path.join(here, "data", "charmap.json"),
                             encoding="utf-8"))
    # Bisection switches. The battle crash survived the size fix, so the next
    # question is WHICH of the three write targets causes it. Build with pieces
    # switched off until it stops, then switch the last one back on alone.
    #   --skip-ui           leave every overlay alone (menus stay Chinese)
    #   --skip-tables       leave entry 1098 alone (items stay Chinese)
    #   --entries 48,258    patch only these overlays, by number
    dialogue, fixed = gather(xlsx)
    keep, uihits = scan_overlays(srcdir, xlsx, charmap,
                                 loose="--reserve-loose" in argv,
                                 skip_tables="--no-reserve-tables" in argv,
                                 min_hits=int(argv[argv.index("--min-hits") + 1])
                                 if "--min-hits" in argv else 20)
    fixed = [f for f in fixed if f[0] != "48"]
    if "--skip-tables" in argv:
        fixed = []
        print("--skip-tables: entry 1098 will not be written")
    want = None
    if "--skip-ui" in argv:
        uihits = {}
        want = set()
        print("--skip-ui: no overlay will be written")
    else:
        # Writing every entry that matched by content crashed the game outright -
        # DOS/4GW "Illegal descriptor type 0", i.e. corrupted protected-mode
        # code. About a hundred of those entries are not text overlays at all;
        # they merely contained enough plausible-looking records to pass. The
        # five FORMATS documents are the ones known to hold UI strings, so they
        # are the default. --entries all opts back in, --entries 48,258 narrows.
        # DEFAULT IS auto. It was proven in build E - town UI translated, no
        # crash - and leaving the default at the five documented overlays meant
        # every later build silently reverted the town menus to Chinese, which
        # cost a build cycle to notice. "--entries safe" is the old five.
        arg = (argv[argv.index("--entries") + 1]
               if "--entries" in argv else "auto")
        if arg == "safe":
            arg = "48,258,416,612,790"
        if arg == "all":
            want = None
        elif arg == "auto":
            # Every UI overlay in the archive is EXACTLY 65535 bytes - that is
            # the allocation, the same way the script entries are all 65537. The
            # entries that crashed build D were not that size; they were data
            # blobs with enough coincidental records to pass. Size plus match
            # count is a much better test than match count alone: an entry that
            # is 65535 bytes AND matches twenty strings is an overlay.
            want = {int(k) for k, v in uihits.items()
                    if len(v) >= 20 and
                    os.path.getsize(os.path.join(srcdir, k + ".bin")) == 0xFFFF}
            print("--entries auto: %d entries are 65535 bytes with 20+ matches"
                  % len(want))
        else:
            want = {int(x) for x in arg.split(",")}
    if "--skip-ui" not in argv and want is not None:
        uihits = {k: v for k, v in uihits.items() if int(k) in want}
        print("overlays written: %s"
              % ", ".join(str(x) for x in sorted(want)))
    for num, items in uihits.items():
        for at, n, eng in items:
            fixed.append(("ui:" + num, at, n, eng))
    if "--safe-slots" in argv:
        import mkfont
        pool = mkfont.free_slots(os.path.join(here, "data", "free_slots.txt"))
    else:
        pool = [s for s in range(2048) if s not in keep]
    singles, alloc, need, want = allocate(dialogue, fixed, pool)

    print("%d fixed-width strings, %d dialogue messages"
          % (len(fixed), sum(len(v) for v in dialogue.values())))
    print("UI records matched by content: %s"
          % ", ".join("entry %s: %d" % (k, len(v))
                      for k, v in sorted(uihits.items())))
    print("%d glyph indices reserved for Chinese left untranslated%s"
          % (len(keep), "  (--reserve-loose)" if "--reserve-loose" in argv else ""))
    print("%d slots in the pool: %d single letters, %d pairs"
          % (len(pool), len(singles), len(alloc)))
    print("fixed-width wants %d distinct pairs, dialogue wants %d; %d granted"
          % (len(need), len(want), len(alloc)))
    bad = fits(fixed, alloc)
    if bad:
        print("\n%d FIXED-WIDTH STRINGS DO NOT FIT their field:" % len(bad))
        for w, o, n, t in bad[:20]:
            print("   %-5s 0x%05X  %r needs %d units, field is %d"
                  % (w, o, t, len(pack(t, alloc)), n))
        return 1
    print("all fixed-width strings fit their fields")

    rows = ie.measure(dialogue, alloc)
    over = [r for r in rows if r["units"] > script_edit.MAX_UNITS]
    per = collections.Counter()
    for r in rows:
        per[r["entry"]] += r["units"]
    print("\nentry   units    bytes   headroom  tight")
    for e in sorted(per):
        n = len(dialogue[e])
        body = 1 + 2 * n + sum(1 + 2 * r["units"] for r in rows if r["entry"] == e)
        print("%5d  %6d  %7d  %9d  %5d"
              % (e, per[e], body, 0xFFFF - body,
                 sum(1 for r in rows if r["entry"] == e and r["tight"])))
    if over:
        print("\n%d dialogue messages exceed the 255-unit ceiling:" % len(over))
        for r in over:
            print("   e%-4d m%-4d %d units" % (r["entry"], r["msg"], r["units"]))
        return 1
    if not build:
        print("\nReady to build.")
        return 0

    # ---- font
    import mkfont
    glyphs = mkfont.latin_bitmaps()
    plan = [c + " " for c in singles if c != " "] + sorted(alloc)
    cellmap = {}
    blob = bytearray(open(os.path.join(srcdir, "0004.bin"), "rb").read())
    for cell, slot in zip(plan, pool):
        cellmap[cell] = slot
        blob[mkfont.TAG + slot * mkfont.CELL:
             mkfont.TAG + (slot + 1) * mkfont.CELL] = \
            mkfont.encode_cell(mkfont.compose(glyphs, cell[0], cell[1]))
    outdir = argv[4]
    os.makedirs(outdir, exist_ok=True)
    open(os.path.join(outdir, "0004.bin"), "wb").write(bytes(blob))
    json.dump({"cell": "2 letters per 16x16 glyph, left half then right half",
               "pairs": cellmap},
              open(os.path.join(here, "data", "digraphs.json"), "w",
                   encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\nfont: %d cells painted, %d slots spare"
          % (len(cellmap), len(pool) - len(cellmap)))

    # ---- fixed-width entries, written in place
    import struct
    byentry = collections.defaultdict(list)
    for w, o, n, t in fixed:
        byentry["1098" if w.startswith("1098") else w.split(":")[1]].append(
            (w, o, n, t))
    for name, items in byentry.items():
        src = os.path.join(srcdir, "%04d.bin" % int(name))
        data = bytearray(open(src, "rb").read())
        for w, o, n, t in items:
            # Every entry-1098 row now carries its NAME FIELD offset, with the
            # description a fixed 0x10 after it. The old convention stored a
            # record "base" and added 0x4C, which cannot express record 0 at all
            # - its base would be negative - and that is why the first weapon in
            # every shop stayed Chinese. The base was always a fiction; the name
            # fields are the real grid, at 0x0001 + n * 0x50.
            if w == "1098":
                at = o
            elif w == "1098d":
                at = o + 0x10
            else:
                at = o + 2
            orig = [struct.unpack_from("<H", data, at + 2 * k)[0]
                    for k in range(n)]
            for k, u in enumerate(encode_fixed(t, n, alloc, cellmap, orig)):
                struct.pack_into("<H", data, at + 2 * k, u)
        open(os.path.join(outdir, "%04d.bin" % int(name)), "wb").write(bytes(data))
        print("  entry %-5s %4d fields written in place, %d bytes (unchanged)"
              % (name, len(items), len(data)))

    # ---- the class skill array, a bare 2-unit array with no header
    # FORMATS: the battle menu's third option is stored as 特·技 with units 0
    # and 2 replaced at draw time from this table. Every class must therefore
    # resolve to the SAME English word, since the middle cell is shared. Left
    # unpatched, the menu read 劍il技 - our middle cell between two Chinese ones.
    skill_pat, skill_new = None, None
    ref48 = os.path.join(srcdir, "0048.bin")
    if os.path.exists(ref48):
        r = open(ref48, "rb").read()
        u = [struct.unpack_from("<H", r, 0x09739 + 2 * k) for k in range(22)]
        u = [x[0] for x in u]
        cmi = {int(k, 16): v for k, v in charmap.items()}
        if sum(1 for v in u if v in cmi) >= 18:
            skill_pat = u
            pair = [cellmap.get("Sk"), cellmap.get("l ")]
            if None not in pair:
                skill_new = pair * 11
    if skill_new:
        for name in sorted(os.listdir(outdir)):
            if not name.endswith(".bin") or not name[:-4].isdigit():
                continue
            data = bytearray(open(os.path.join(outdir, name), "rb").read())
            blob = b"".join(struct.pack("<H", v) for v in skill_pat)
            at = data.find(blob)
            n = 0
            while at >= 0:
                for k, v in enumerate(skill_new):
                    struct.pack_into("<H", data, at + 2 * k, v)
                n += 1
                at = data.find(blob, at + 2)
            if n:
                open(os.path.join(outdir, name), "wb").write(bytes(data))
                print("  entry %-5s class skill array written %d time(s)"
                      % (name[:-4], n))

    # ---- dialogue entries, which regrow
    tight = {(r["entry"], r["msg"]) for r in rows if r["tight"]}
    for e in sorted(dialogue):
        src = os.path.join(srcdir, "%04d.bin" % e)
        raw = open(src, "rb").read()
        tag, msgs = script_edit.parse(raw)
        # THE ENTRY IS A FIXED-SIZE BUFFER. All five script entries are exactly
        # 65537 bytes in the retail archive, and the overlays 65535 - these are
        # allocations, not measurements. Writing a shorter entry shrank the
        # archive by 174 KB and broke the game: whatever the engine expects to
        # find after the script block moved or vanished.
        used = len(script_edit.build(tag, msgs))
        tail = raw[used:]
        filler = set(tail)
        blob = script_edit.build(tag, msgs_patched(msgs, dialogue[e], alloc,
                                                  cellmap, tight, e, ie))
        if len(blob) > len(raw):
            print("  entry %-5d TOO BIG: %d bytes into a %d byte entry"
                  % (e, len(blob), len(raw)))
            return 1
        # The tail is whatever sits between the end of the script block and the
        # end of the fixed 65537-byte buffer. Overwriting the part of it the new
        # block reaches is a judgement call, so describe it rather than guess:
        # see describe_tail. Everything BEYOND the new block keeps its original
        # bytes at their original offsets, and the entry keeps its length, which
        # is the part that actually broke the game.
        if len(blob) > used:
            print("  entry %-5d tail: %s" % (e, describe_tail(tail, used, raw)))
            print("        the new script block reaches %d bytes into it"
                  % (len(blob) - used))
        out = blob + raw[len(blob):]
        assert len(out) == len(raw)
        open(os.path.join(outdir, "%04d.bin" % e), "wb").write(out)
        print("  entry %-5d %4d messages, script block %6d -> %6d bytes,"
              " entry stays %d" % (e, len(dialogue[e]), used, len(blob), len(raw)))

    for nm in sorted(os.listdir(srcdir)):
        if nm.endswith(".bin") and not os.path.exists(os.path.join(outdir, nm)):
            open(os.path.join(outdir, nm), "wb").write(
                open(os.path.join(srcdir, nm), "rb").read())
    print("\nwrote %s" % outdir)
    print("next: python tools/dickdat.py pack %s DICK.DAT.new" % outdir)
    print("Entries have moved: patch_poc.py and glyphdump.py hold hardcoded")
    print("absolute offsets and must be re-derived from the new TOC.")
    return 0


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 1
    if sys.argv[1] == "find" and len(sys.argv) >= 4:
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cmp_ = json.load(open(os.path.join(here, "data", "charmap.json"),
                              encoding="utf-8"))
        return cmd_find(sys.argv[2], sys.argv[3], cmp_)
    if sys.argv[1] == "plan":
        return cmd(sys.argv, False)
    if sys.argv[1] == "build" and len(sys.argv) >= 5:
        return cmd(sys.argv, True)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
