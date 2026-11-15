"""Game paths and the small container readers the patcher needs (SARC archives, BYML documents, zstd dictionaries).
install.py sets ROMFS before anything reads a file."""
import os, struct
from compression import zstd

ROMFS = None   # the game's romfs folder (set by install.py)


def actor_dir():
    return os.path.join(ROMFS, "Pack", "Actor")


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


class Byml:
    """Just enough BYML ('YB', little-endian) to find values: items(off) -> (key, type, value offset)."""

    def __init__(self, b):
        assert b[:2] == b"YB"
        self.b = b
        _, ktab, _, self.root = struct.unpack_from("<HIII", b, 2)
        n = int.from_bytes(b[ktab + 1:ktab + 4], "little")
        offs = struct.unpack_from(f"<{n}I", b, ktab + 4)
        self.keys = [b[ktab + o:b.index(b"\0", ktab + o)].decode() for o in offs]

    def items(self, off):
        b = self.b
        assert b[off] == 0xC1, hex(b[off])
        for i in range(int.from_bytes(b[off + 1:off + 4], "little")):
            e = off + 4 + i * 8
            yield self.keys[int.from_bytes(b[e:e + 3], "little")], b[e + 3], e + 4

    def child(self, off, key):
        for k, t, at in self.items(off):
            if k == key:
                return t, at
        return None, None

    def u32(self, at):
        return struct.unpack_from("<I", self.b, at)[0]

    def array_at(self, arr):
        assert self.b[arr] == 0xC0
        n = int.from_bytes(self.b[arr + 1:arr + 4], "little")
        vo = arr + 4 + ((n + 3) & ~3)
        return [(vo + i * 4, self.b[arr + 4 + i]) for i in range(n)]


def load_dict():
    raw = zstd.decompress(open(os.path.join(ROMFS, "Pack", "ZsDic.pack.zs"), "rb").read())
    s, t = sarc_entries(raw)["pack.zsdic"]
    return zstd.ZstdDict(raw[s:t])
