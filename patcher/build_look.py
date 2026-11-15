"""Assemble the mod folder (romfs layout) from the files the other steps made in assets/:
  look "gear": Dark Link's sword + shield models, black clothes and sheath on Link's own body (skin and eyes kept)
  look "full": the same on Dark Link's body model (his skin and eyes)
  glow "red":   the Master Sword always shines, recoloured deep red / scarlet (Demise style), no glow when sheathed
  glow "stock": always shines in the game's own colours, no glow when sheathed
Every edit checks the stock bytes first and keeps file sizes inside the game's resource size table."""
import os, shutil, struct, sys
from compression import zstd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import game as cm  # noqa: E402
import gamefmt as gf  # noqa: E402
import bntx_astc as bx  # noqa: E402
import rstb  # noqa: E402

ASSETS = os.path.join(HERE, "assets")
LOOK_GEAR = {"Weapon_Shield_Hylian": "Weapon_Shield_Hylian_Dark", "Weapon_Sword_Master": "Weapon_Sword_Master_Dark"}
LOOK_BODY = {"Player_Adult": "Player_Adult_Dark"}
# Every pack holding a copy of a swapped ModelInfo file must get the same edit: the game keeps whichever copy loads
# first in a session. Dm_Sword_Master (the Temple of Time cutscene sword) and Shop_Weapon_Shield_Hylian carry their own
# copies of the sword's and shield's ModelInfo; unpatched, they left the stock sword/shield until a reload (v1.0.1).
WEAPON_PACKS = ["Weapon_Shield_Hylian.pack.zs", "Weapon_Sword_Master.pack.zs",
                "Dm_Sword_Master.pack.zs", "Shop_Weapon_Shield_Hylian.pack.zs"]
LOOK_PACKS = {"gear": WEAPON_PACKS,
              "full": WEAPON_PACKS + ["Player_Adult.pack.zs", "Player_Base.pack.zs", "PouchPlayer_Adult.pack.zs"]}
LOOK_ROWS = {"gear": ["Weapon_Shield_Hylian", "Weapon_Sword_Master"],
             "full": ["Weapon_Shield_Hylian", "Weapon_Sword_Master", "Player_Adult", "PouchPlayer_Adult"]}
# Recoloured textures ship under their own names, so the Dark Link boss, the tunic items and anything else that shares
# the stock textures keeps its normal look. (Exception: the sword texture, because both looks use the boss's sword
# model; and in "full" the body, because Link wears the boss's own body model.)
CLOTHES = ["Tex/Mt_Vest_Player_DkLnk_Alb", "Tex/Mt_Inner_Player_DkLnk_Alb", "Tex/Mt_Leater_Upper_Player_DkLnk_Alb",
           "Tex/Mt_Boots_Player_DkLnk_Alb", "Tex/Mt_Glove_Player_DkLnk_Alb", "Tex/Mt_Angin_Acs_Player_DkLnk_Alb",
           "Tex/Mt_Feather_Player_DkLnk_Alb"]
GEAR_TEX = ["Tex/Mt_Weapon_Sword_Master_Dark_Alb", "Tex/Mt_Weapon_Sheath_DkLink_Alb", "Tex/Mt_Weapon_Sheath_Master_Rgh",
            "Model/Weapon_Sheath_Master.Weapon_Sheath_Master.bfres.zs",
            "UI/Tex/Icon/Weapon_Sword_Master", "UI/Tex/Icon/Weapon_Shield_Hylian", "UI/Tex/Icon/Armor_Adult_Normal"]
LOOK_TEXTURES = {"gear": GEAR_TEX + CLOTHES + ["Model/Player_Adult.Player_Adult.bfres.zs", "Tex/Angin_Tile_D_Alb"],
                 "full": GEAR_TEX + CLOTHES + ["Model/Player_Adult_Dark.Player_Adult_Dark.bfres.zs"]}
RSDB_ACTORINFO = "RSDB/ActorInfo.Product.111.rstbl.byml.zs"
RED_GLOW = "Effect/Weapon_Sword_Master.Nin_Ounce_NVN2.vsetb.byml.zs"
GLOW_PACK = "Weapon_Sword_Master.pack.zs"
GLOW_AINB = "AI/Weapon_Sword_Master.root.ainb"
# Effect link table: the always-on SHEATHED glow entry -> the game's own empty effect name "Dummy_Onetime"
ELINK = "ELink2/elink2.Product.110.belnk.zs"
ELINK_NT = 0x1f5840
ELINK_EDITS = {0x5891c: (0x01049adb, 0x0101a6c1)}
_RSTB = None


def zs_load(rel):
    raw = zstd.decompress(open(os.path.join(cm.ROMFS, "Pack", "ZsDic.pack.zs"), "rb").read())
    dicts = {nm: zstd.ZstdDict(raw[s:t]) for nm, (s, t) in cm.sarc_entries(raw).items()}
    src = open(os.path.join(cm.ROMFS, *rel.split("/")), "rb").read()
    for nm, d in [(None, None)] + list(dicts.items()):
        try:
            return (zstd.decompress(src, zstd_dict=d) if d else zstd.decompress(src)), nm, dicts
        except Exception:
            continue
    raise ValueError(f"can't decompress {rel}")


def rsdb_look(look, log):
    b, dname, dicts = zs_load(RSDB_ACTORINFO)
    data = bytearray(b)
    y = cm.Byml(b)
    stab = struct.unpack_from("<I", b, 8)[0]
    n = int.from_bytes(b[stab + 1:stab + 4], "little")
    offs = struct.unpack_from(f"<{n}I", b, stab + 4)
    strs = [b[stab + o:b.index(b"\0", stab + o)].decode() for o in offs]
    sidx = {s: i for i, s in enumerate(strs)}
    swap = dict(LOOK_GEAR, **(LOOK_BODY if look == "full" else {}))
    rows = set(LOOK_ROWS[look])
    assert b[y.root] == 0xC0
    done = set()
    for vat, t in y.array_at(y.root):
        if t != 0xC1:
            continue
        row = y.u32(vat)
        tt, rid = y.child(row, "__RowId")
        if tt != 0xA0 or strs[y.u32(rid)] not in rows:
            continue
        rid_s = strs[y.u32(rid)]
        for key in ("FmdbName", "ModelProjectName"):
            tt, at = y.child(row, key)
            assert tt == 0xA0, (rid_s, key)
            old = strs[y.u32(at)]
            new = swap.get(old)
            assert new and new in sidx, (rid_s, key, old)
            struct.pack_into("<I", data, at, sidx[new])
            log.append(f"  {RSDB_ACTORINFO}: row {rid_s}.{key}: {old} -> {new}")
        done.add(rid_s)
    assert done == rows, rows - done
    return zstd.compress(bytes(data), level=9, zstd_dict=dicts[dname]) if dname else zstd.compress(bytes(data), 9)


def rstb_table():
    global _RSTB
    if _RSTB is None:
        _RSTB = rstb.load_rstb(os.path.join(cm.ROMFS, *rstb.RSTB_REL.split("/")))
    return _RSTB


def look_replacements(orig, look):
    swap = dict(LOOK_GEAR, **(LOOK_BODY if look == "full" else {}))
    out = {}
    for nm, (s, t) in cm.sarc_entries(orig).items():
        if not nm.startswith("Component/ModelInfo/"):
            continue
        ver, tree = gf.byml_read(orig[s:t])
        fm = tree.get("FmdbName", ("", ""))[1]
        if fm in swap:
            tree["FmdbName"] = ("str", swap[fm])
            tree["ModelProjectName"] = ("str", swap[fm])
            out[nm] = gf.byml_write(ver, tree)
    return out


def glow_edit(data, s, log):
    """The Master Sword's AI picks its shine from a game flag: TrueValue 1 / FalseValue 0. FalseValue -> 1."""
    end = s + 0x10000
    b = bytes(data[s:end])
    assert b[:4] == b"AIB "
    pool = struct.unpack_from("<I", b, 0x24)[0]

    def name_off(n):
        i = b.find(b"\0" + n + b"\0", pool)
        assert i >= 0, n
        return i + 1 - pool

    def record(name):
        key = struct.pack("<I", name_off(name))
        hits = [i for i in range(0, pool - 16, 4) if b[i:i + 4] == key and b[i + 4:i + 8] == b"\xff\xff\x00\x00"]
        assert len(hits) == 1, (name, hits)
        return hits[0] + 12

    fv, tv = record(b"FalseValue"), record(b"TrueValue")
    assert struct.unpack_from("<i", b, fv)[0] == 0 and struct.unpack_from("<i", b, tv)[0] == 1
    struct.pack_into("<i", data, s + fv, 1)
    log.append("MasterSwordShine selector FalseValue 0 -> 1 (always shine)")
    return 1


def glow_elink(target, log):
    b, dname, dicts = bx.load(ELINK)
    assert b[:4] == b"XLNK" and struct.unpack_from("<I", b, 8)[0] == 0x24
    data = bytearray(b)

    def name(w):
        o = ELINK_NT + (w & 0xFFFFFF)
        return b[o:b.index(b"\0", o)].decode()
    for off, (old, new) in ELINK_EDITS.items():
        assert struct.unpack_from("<I", b, off)[0] == old, hex(off)
        struct.pack_into("<I", data, off, new)
        log.append(f"  {ELINK}: {off:#x} {name(old)} -> {name(new)} (no glow while sheathed)")
    dst = os.path.join(target, "romfs", *ELINK.split("/"))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, "wb").write(zstd.compress(bytes(data), level=19, zstd_dict=dicts[dname]))


def build(target, look, glow):
    """Write the mod folder `target` (target/romfs/...). look: none|gear|full; glow: off|stock|red."""
    pdict = cm.load_dict()
    shutil.rmtree(target, ignore_errors=True)
    log = []
    packs = list(LOOK_PACKS.get(look, []))
    if glow != "off" and GLOW_PACK not in packs:
        packs.append(GLOW_PACK)
    out_dir = os.path.join(target, "romfs", "Pack", "Actor")
    os.makedirs(out_dir)
    for pack in packs:
        orig = zstd.decompress(open(os.path.join(cm.actor_dir(), pack), "rb").read(), zstd_dict=pdict)
        data, done = bytearray(orig), 0
        if glow != "off" and pack == GLOW_PACK:
            s, _ = cm.sarc_entries(orig)[GLOW_AINB]
            sub = []
            done += glow_edit(data, s, sub)
            log.append(f"  {pack}: {GLOW_AINB.split('/')[-1]}: {'; '.join(sub)}")
        repl = look_replacements(bytes(data), look) if pack in LOOK_PACKS.get(look, []) else {}
        if repl:
            new = bytes(data)
            for nm, blob in repl.items():
                new = gf.sarc_shift_replace(new, nm, blob)
            table = rstb.lookup(rstb_table(), "Pack/Actor/" + pack[:-3])
            assert table and len(new) <= table, f"{pack}: {len(new)} B would exceed its size-table entry {table}"
            for nm in repl:
                log.append(f"  {pack}: {nm.split('/')[-1]}: model -> {gf.byml_read(repl[nm])[1]['FmdbName'][1]}")
            data, done = bytearray(new), done + len(repl)
        if done:
            packed = zstd.compress(bytes(data), level=9, zstd_dict=pdict)
            assert zstd.decompress(packed, zstd_dict=pdict) == bytes(data)
            open(os.path.join(out_dir, pack), "wb").write(packed)
    if look != "none":
        rel = RSDB_ACTORINFO.split("/")
        os.makedirs(os.path.join(target, "romfs", *rel[:-1]), exist_ok=True)
        open(os.path.join(target, "romfs", *rel), "wb").write(rsdb_look(look, log))
        for t in LOOK_TEXTURES[look]:
            parts = (t if t.endswith(".zs") else t + ".bntx.zs").split("/")
            dst = os.path.join(target, "romfs", *parts)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copyfile(os.path.join(ASSETS, *parts), dst)
            log.append(f"  {'/'.join(parts)}")
    if glow == "red":
        dst = os.path.join(target, "romfs", *RED_GLOW.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(ASSETS, *RED_GLOW.split("/")), dst)
        log.append(f"  {RED_GLOW}: red glow")
    if glow != "off":
        glow_elink(target, log)
    return log
