"""Add-ons for DenizenofWhite's mods. An add-on is a small set of byte patches to game files, written down in a note:

  {"addon": "<folder name>", "title": "<shown to players>", "version": "...", "options": {...},
   "patches": [{"file": "<romfs path>", "inner": "<file inside a .pack, or null>", "offset": n,
                "old": "<hex>", "new": "<hex>"}]}

Used on its own, an add-on applies its patches to stock files in its own mod folder and keeps its note there as
addon.json. When Dark Link & Demise Glow (v1.1+) is installed next to it, the add-on applies its patches to Dark Link &
Demise Glow's own files instead and keeps its note in that folder's addons/ folder; Dark Link & Demise Glow re-applies
every note whenever it rebuilds. Every patch checks the bytes it replaces first, so nothing is applied blind."""
import glob, json, os, struct
from compression import zstd

NOTE = "addon.json"         # an add-on's note in its own folder
HOST_NOTES = "addons"        # notes of add-ons merged into Dark Link & Demise Glow


def sarc_entries(b):
    assert b[:4] == b"SARC"
    data_off = struct.unpack_from("<I", b, 0x0C)[0]
    n = struct.unpack_from("<H", b, 0x14 + 6)[0]
    nodes = [struct.unpack_from("<IIII", b, 0x14 + 12 + i * 16) for i in range(n)]
    names_at = 0x14 + 12 + n * 16 + 8
    out = {}
    for _, attr, s, t in nodes:
        p = names_at + (attr & 0xFFFF) * 4
        out[b[p:b.index(b"\0", p)].decode()] = (data_off + s, data_off + t)
    return out


def zs_dicts(romfs):
    raw = zstd.decompress(open(os.path.join(romfs, "Pack", "ZsDic.pack.zs"), "rb").read())
    return [zstd.ZstdDict(raw[s:t]) for nm, (s, t) in sorted(sarc_entries(raw).items())]


def unpack(blob, dicts):
    """(decompressed bytes, the dictionary it needed or None)."""
    for d in [None] + dicts:
        try:
            return (zstd.decompress(blob, zstd_dict=d) if d else zstd.decompress(blob)), d
        except Exception:
            continue
    raise ValueError("can't decompress")


def apply(folder, romfs, patches, reverse=False, dicts=None):
    """Apply (or take back) patches to the files in folder/romfs, starting from the stock game file where the folder
    has none yet. Returns the romfs paths written."""
    dicts = dicts if dicts is not None else zs_dicts(romfs)
    by_file = {}
    for p in patches:
        by_file.setdefault(p["file"], []).append(p)
    written = []
    for rel, ps in sorted(by_file.items()):
        mine = os.path.join(folder, "romfs", *rel.split("/"))
        src = mine if os.path.exists(mine) else os.path.join(romfs, *rel.split("/"))
        raw, d = unpack(open(src, "rb").read(), dicts)
        data = bytearray(raw)
        inner = sarc_entries(raw) if rel.endswith(".pack.zs") else {}
        for p in ps:
            base = inner[p["inner"]][0] if p.get("inner") else 0
            old, new = bytes.fromhex(p["old"]), bytes.fromhex(p["new"])
            if reverse:
                old, new = new, old
            at = base + p["offset"]
            cur = bytes(data[at:at + len(old)])
            if cur == new:
                continue                                    # already applied
            assert cur == old, f"{rel} {p.get('inner') or ''} @{p['offset']}: found {cur.hex()}, expected {old.hex()}"
            data[at:at + len(new)] = new
        os.makedirs(os.path.dirname(mine), exist_ok=True)
        packed = zstd.compress(bytes(data), level=9, zstd_dict=d) if d else zstd.compress(bytes(data), 9)
        open(mine, "wb").write(packed)
        written.append(rel)
    return written


def host_notes(host):
    """Notes of the add-ons merged into a Dark Link & Demise Glow folder."""
    return [json.load(open(p)) for p in sorted(glob.glob(os.path.join(host, HOST_NOTES, "*.json")))]


def sibling_notes(parent, skip):
    """Notes of add-ons installed in their own folders next to it (folder names starting with '-' are disabled)."""
    out = []
    for n in sorted(os.listdir(parent)) if os.path.isdir(parent) else []:
        p = os.path.join(parent, n, NOTE)
        if n != skip and not n.startswith("-") and os.path.isfile(p):
            out.append(json.load(open(p)))
    return out
