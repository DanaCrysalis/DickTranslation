#!/usr/bin/env python3
"""
uitext.py - dump and translate the UI / battle string tables in the code overlays

Menus, battle messages, status labels and prompts are NOT in a data entry: they
live inside the ~90 code overlays, each of which carries a copy. Records are

    u16 count
    u16 * count   glyph indices (0x0066 = full-width space, 0x0000 = placeholder)
    u16 trailer   purpose unknown; preserved verbatim

Note that menu labels space their characters out - the battle menu stores
"attack" as three units, 攻 · 擊, not two. That is why searching for adjacent
character pairs never finds them.

Copies are NOT byte-identical across overlays: entry 48 has the menu at 0x12E8
while entry 47 has it at 0x12D6. So records are located by CONTENT SIGNATURE,
never by fixed offset.

    python tools/uitext.py dump 0048.bin
    python tools/uitext.py dump 0048.bin --json strings.json
    python tools/uitext.py patchall out/ --preset battle_full   # all overlays, in place
    python tools/uitext.py patch 0048.bin 0004.bin out.bin out.font.bin --preset battle

`patch` rewrites records in place. Unit counts are preserved exactly, so the
overlay's byte length never changes and nothing downstream can shift - the same
conservative choice poc_english.py makes for dialogue. English is encoded two
letters per glyph cell, repainting free font slots as needed.

Because the same records appear in every overlay, a full translation must apply
to all of them. Run patch once per overlay file; the signature search will find
the right offsets in each.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SPACE = 0x0066

# label -> English. Unit counts must match the original exactly.
PRESETS = {
    "battle": {
        "攻·擊": "Attack",
        "咒·文": "Spell",
        "特·技": "Skil ",   # only the middle cell ("il") survives; see patch_skill_table
        "道·具": "Item",
        "防·禦": "Defend",
        "撤·退": "Flee",
    },
    "system": {
        "存檔": "Save",
        "讀檔": "Load",
        "對話速度": "Text Speed",
        "視窗速度": "Window Spd",
        "遊戲速度": "Game Speed",
        "音樂聲量": "Music Vol",
        "音效聲量": "Sound Vol",
    },
    "prompt": {
        "好": "OK", "不好": "No", "是": "Y", "不是": "No",
        "休息": "Rest", "不休息": "Don't", "買": "Go", "不買": "No",
        "賣": "Se", "使用": "Use", "丟棄": "Drop",
    },
}


# The battle menu's third option is a TEMPLATE: the record at "特·技" has its
# first and third units overwritten at runtime with the character's class skill
# name, taken from a bare 2-unit array elsewhere in the overlay. Only the middle
# unit is static. So the label renders as
#     [class unit 0][static middle][class unit 1]
# and the only way to get one clean English word is to make the middle carry the
# letters that bridge the two halves: "Sk" + "il" + "l " = "Skill".
# Per-class English names are impossible without engine changes, because every
# class shares that one middle cell.
SKILL_TABLE_SIG = bytes.fromhex("7300e2019a02e20192 02e301".replace(" ", ""))
SKILL_ENTRIES = 11


def patch_skill_table(d, glyphs, blob, slots, amap, log=print):
    i = d.find(SKILL_TABLE_SIG)
    if i < 0:
        log("  skill table not found - third menu option left in Chinese")
        return 0
    def cell(pair):
        if pair not in amap:
            amap[pair] = slots.pop(0)
        return amap[pair]
    a, b = cell("Sk"), cell("l ")
    for k in range(SKILL_ENTRIES):
        struct.pack_into("<HH", d, i + 4 * k, a, b)
    log("  0x%05x  class skill table (%d entries) -> 'Sk'+'l '" % (i, SKILL_ENTRIES))
    return 1


# Full battle sequence. "~~" = leave that unit untouched (runtime-filled).
PRESETS["battle_full"] = {
    # battle menu (3 units; units 0 and 2 of 特·技 are runtime-replaced)
    "攻·擊": "Attack", "咒·文": "Spell", "特·技": "Skil ",
    "道·具": "Item", "防·禦": "Defend", "撤·退": "Flee",
    # spell selection screen
    "火·系": "Fire  ", "風·系": "Wind  ", "冰·系": "Ice   ",
    "光·系": "Light ", "雷·系": "Bolt  ",
    "魔法說明：": "Spell info",
    "回復系": "Heal  ", "爆裂系": "Blast ",
    "頁數": "Page",
    "魔法力": "MP ",
    # spell / item sub-menus
    "道具說明：": "Item info:",
    "現在不可使用非回復系魔法": "Only healing magic now! ",
    "魔法力不夠！": "Low MP!     ",
    "體力不支，現在無法使用": "Too weak to use that! ",
    "此物品不能使用。": "Can't use that! ",
    "道具袋已滿。": "Bag is full!",
    "重要物品，不可丟棄！！": "Key item - can't drop!",
    "每種道具最多只能五個！！": "Only five of each item! ",
    # combat results
    "獲得經驗值": "EXP gained",
    "獲得金·錢": "Gold found",
    "獲得·····": "Got ~~~~~~~~~~",
    "等級··升至··": "Lev.~~~~->  ~~~~",
    "HP··升至··": "HP  ~~~~->  ~~~~",
    "MP··升至··": "MP  ~~~~->  ~~~~",
    "臂力··升至··": "Str ~~~~->  ~~~~",
    "速度··升至··": "Spd ~~~~->  ~~~~",
    "智慧··升至··": "Int ~~~~->  ~~~~",
    "魔防··升至··": "MDef~~~~->  ~~~~",
    "守備··升至··": "Def ~~~~->  ~~~~",
    "技術··升至··": "Skil~~~~->  ~~~~",
    "幸運··升至··": "Luck~~~~->  ~~~~",
    # retreat
    "___帶領全員撤退。。。": "~~~~~~ leads a retreat!",
    "撤退成功": "Escaped!", "撤退失敗": "Blocked!",
    # monster and party actions
    "___·使用咒文·__": "~~~~~~ casts spell~~~~",
    "___·使用道具": "~~~~~~ uses item",
    "怪物脫逃。。。": "Monster flees!",
    "怪物生命力增加。。。": "Monster HP rises... ",
    "怪物防禦力增加。。。": "Monster DEF up...   ",
    "怪物封住___魔法。。。": "Seal on ~~~~~~magic... ",
    "怪物降低___命中率。。。": "Aim of  ~~~~~~lowered... ",
    "怪物使用_擊必殺。。。": "Monster ~~ crit hit!!",
    "怪物使用偷錢術": "Monster steals",
    "怪物降低我方守備力。。。": "Party defense lowered!  ",
    "___暫時麻痺。。。": "~~~~~~ is stunned!!",
    "魔法失敗。。。。": "Spell failed... ",
    "全體生命力回復": "Party healed! ",
    "頭部": "Head",
    # status panel
    "臂力": "Str ", "速度": "Spd ", "智慧": "Int ", "魔防": "MDef",
    "技術": "Skil", "守備": "Def ", "幸運": "Luck",
    "攻擊力": "Attack", "防禦力": "Defend",
    "身體狀況：": "Condition:", "次回": "Next", "全體金錢": "Gold:   ",
    "姓名：": "Name: ", "年齡：": "Age:  ", "身高：": "Hght: ", "等級：": "Levl: ",
    "武器：": "Weap: ", "身體：": "Body: ", "其它：": "Misc: ",
    "頭部：······攻擊力": "Head: ~~~~~~~~~~~~Attack",
    "防具：······防禦力": "Armor:~~~~~~~~~~~~Defend",
    # field / system menus
    "道具": "Item", "咒文": "Cast", "裝備": "Gear", "狀態": "Stat", "系統": "Sys ",
    "戰鬥排列": "Line-up ", "基本狀態": "Status  ",
    "存檔": "Save", "讀檔": "Load",
    "對話速度": "Text Spd", "視窗速度": "Wind Spd", "遊戲速度": "Game Spd",
    "音樂聲量": "Music Vl", "音效聲量": "SFX  Vol",
    "現在不能存檔": "Cannot save!", "現在不能讀檔": "Cannot load!",
    "抱歉，你的錢不夠。": "Sorry, too costly!",
    "錢不夠，無法提供住宿！！": "Not enough gold to stay!",
    # prompts
    "好": "OK", "不好": "No  ", "是": "Y ", "不是": "No  ",
    "休息": "Rest", "不休息": "Leave ", "使用": "Use ", "丟棄": "Drop",
    "買": "Bu", "不買": "No  ", "賣": "Se",
    "沒有道具": "No items",
}


def build_glyph_map(table, glyphs, blob, slots):
    """Assign a font slot to every letter pair the preset needs, in SORTED order.

    Allocation must not depend on the order records happen to be encountered:
    the same pair has to land in the same slot in every overlay, or one font
    cannot serve them all. Sorting the pair set makes the assignment a pure
    function of the preset."""
    import mkfont
    pairs = set()
    for eng in table.values():
        t = eng
        if len(t) % 2:
            t += " "
        for i in range(0, len(t), 2):
            p = t[i:i + 2]
            if p != "~~":
                pairs.add(p)
    pairs.add("Sk")
    pairs.add("l ")
    amap = {}
    for p in sorted(pairs):
        if not slots:
            raise SystemExit("not enough free glyph slots for this preset")
        amap[p] = slots.pop(0)
    for p, slot in amap.items():
        blob[1 + slot * 64:1 + (slot + 1) * 64] = \
            mkfont.encode_cell(mkfont.compose(glyphs, p[0], p[1]))
    return amap


def load_charmap():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(here, "data", "charmap.json")
    cm = json.load(open(p, encoding="utf-8"))
    return {int(k, 16): v for k, v in cm.items()}


def read_rec(d, i, cm):
    if i + 4 > len(d):
        return None
    c = struct.unpack_from("<H", d, i)[0]
    if not (1 <= c <= 40) or i + 2 + 2 * c + 2 > len(d):
        return None
    u = [struct.unpack_from("<H", d, i + 2 + 2 * k)[0] for k in range(c)]
    if not all(v < 0x800 for v in u):
        return None
    if not all(v in cm or v in (SPACE, 0) for v in u):
        return None
    if not any(v not in (SPACE, 0) for v in u):
        return None
    return c, u, i + 2 + 2 * c + 2


def scan(d, cm, minlen=1):
    """Return every chain of >=minlen contiguous records.

    minlen defaults to 1 because tables are not always contiguous: the spell
    schools sit 12 bytes apart with a 2-byte gap, and the retreat messages form
    a chain of only three. Requiring longer chains silently skipped both. Exact
    text matching is what keeps patching safe, not the chain length."""
    out = []
    i = 0
    while i < len(d) - 6:
        r = read_rec(d, i, cm)
        if not r:
            i += 1
            continue
        ch = []
        p = i
        while True:
            r = read_rec(d, p, cm)
            if not r:
                break
            ch.append((p, r[1]))
            p = r[2]
        if len(ch) >= minlen:
            out.append(ch)
            i = p
        else:
            i += 1
    return out


def text_of(units, cm):
    return "".join("·" if v == SPACE else ("_" if v == 0 else cm.get(v, "[%03x]" % v))
                   for v in units)


def cmd_dump(path, jsonout=None):
    cm = load_charmap()
    d = open(path, "rb").read()
    chains = scan(d, cm)
    n = sum(len(c) for c in chains)
    print("%s: %d chains, %d records" % (os.path.basename(path), len(chains), n))
    rows = []
    for ch in chains:
        print("\n=== chain @0x%05x (%d records) ===" % (ch[0][0], len(ch)))
        for off, u in ch:
            t = text_of(u, cm)
            print("   0x%05x  %2d  %s" % (off, len(u), t))
            rows.append({"offset": off, "units": len(u), "text": t})
    if jsonout:
        json.dump(rows, open(jsonout, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("\nwrote %s" % jsonout)


def encode_english(s, orig, glyphs, blob, slots, amap):
    """Pack s into exactly len(orig) cells, two letters per cell.

    A "~~" pair means LEAVE THIS UNIT ALONE. Many strings carry slots the engine
    fills at runtime - "·" units that receive numbers, "_" units that receive a
    character name - and overwriting those breaks the message. Mark them "~~"
    and the original unit is preserved."""
    nunits = len(orig)
    need = nunits * 2
    if len(s) > need:
        raise ValueError("%r needs %d cells, only %d available"
                         % (s, (len(s) + 1) // 2, nunits))
    s = s.ljust(need)
    out = []
    for i in range(0, need, 2):
        pair = s[i:i + 2]
        if pair == "~~":
            out.append(orig[i // 2])
            continue
        if pair not in amap:
            if not slots:
                raise ValueError("no free glyph slots left")
            amap[pair] = slots.pop(0)
        out.append(amap[pair])
    return out


def cmd_patch(src, fontsrc, out, fontout, preset):
    import mkfont
    cm = load_charmap()
    d = bytearray(open(src, "rb").read())
    blob = bytearray(open(fontsrc, "rb").read())
    if len(blob) != 1 + 2048 * 64:
        sys.exit("%s is not the font entry" % fontsrc)
    table = {}
    for name in preset.split(","):
        if name not in PRESETS:
            sys.exit("unknown preset %r; have %s" % (name, ", ".join(PRESETS)))
        table.update(PRESETS[name])
    glyphs = mkfont.latin_bitmaps()
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    slots = mkfont.free_slots(os.path.join(here, "data", "free_slots.txt"))
    amap = build_glyph_map(table, glyphs, blob, slots)
    done = 0
    for ch in scan(d, cm, minlen=1):
        for off, u in ch:
            t = text_of(u, cm)
            if t not in table:
                continue
            eng = table[t]
            try:
                units = encode_english(eng, u, glyphs, blob, slots, amap)
            except ValueError as e:
                print("  skip %s: %s" % (t, e))
                continue
            for k, v in enumerate(units):
                struct.pack_into("<H", d, off + 2 + 2 * k, v)
            print("  0x%05x  %-12s -> %-12s (%d units, unchanged)"
                  % (off, t, eng, len(u)))
            done += 1
    if "battle" in preset:
        done += patch_skill_table(d, glyphs, blob, slots, amap)
    open(out, "wb").write(bytes(d))
    open(fontout, "wb").write(bytes(blob))
    print("\n%d records rewritten, %d glyph cells repainted" % (done, len(amap)))
    print("wrote %s (%d bytes, unchanged) and %s" % (out, len(d), fontout))


def cmd_patchall(outdir, preset):
    """Patch every code-overlay chunk in a directory, in place.

    The string tables are duplicated across ~90 overlays, so translating one is
    not enough - the field and system menus appear in all of them, and battle
    strings in five. Overlay chunks are identifiable by size: they are all
    exactly 65535 bytes. Anything else in the directory is left alone."""
    font_path = os.path.join(outdir, "0004.bin")
    if not os.path.exists(font_path):
        sys.exit("no 0004.bin (the font) in %s" % outdir)
    names = sorted(n for n in os.listdir(outdir)
                   if n.endswith(".bin") and n != "0004.bin"
                   and os.path.getsize(os.path.join(outdir, n)) == 65535)
    if not names:
        sys.exit("no 65535-byte overlay chunks found in %s" % outdir)
    print("%d overlay chunks to scan\n" % len(names))
    total = touched = 0
    for i, n in enumerate(names):
        p = os.path.join(outdir, n)
        before = open(p, "rb").read()
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_patch(p, font_path, p, font_path, preset)
        out = buf.getvalue()
        m = [l for l in out.splitlines() if "records rewritten" in l]
        cnt = int(m[0].split()[0]) if m else 0
        after = open(p, "rb").read()
        assert len(before) == len(after), "%s changed size!" % n
        if cnt:
            touched += 1
            total += cnt
            print("  %-12s %3d records" % (n, cnt))
    print("\n%d records rewritten across %d overlays" % (total, touched))
    print("font written to %s" % font_path)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    if sys.argv[1] == "dump":
        j = None
        if "--json" in sys.argv:
            j = sys.argv[sys.argv.index("--json") + 1]
        cmd_dump(sys.argv[2], j)
    elif sys.argv[1] == "patchall":
        preset = "battle_full"
        if "--preset" in sys.argv:
            preset = sys.argv[sys.argv.index("--preset") + 1]
        cmd_patchall(sys.argv[2], preset)
    elif sys.argv[1] == "patch":
        preset = "battle"
        if "--preset" in sys.argv:
            preset = sys.argv[sys.argv.index("--preset") + 1]
        cmd_patch(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], preset)
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
