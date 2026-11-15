"""Dark Link & Demise Glow: builds the mod from YOUR OWN copy of The Legend of Zelda: Ocarina of Time (Switch 2)
and installs it. No game files ship with this patcher; everything is made from your files on your PC.

  Longshot:  python install.py --longshot "C:/Games/Longshot"           (uses <folder>/romfs, installs to <folder>/mods)
  Hookshot:  python install.py --hookshot "C:/Games/Hookshot"           (same layout)
  Emulator:  python install.py --romfs "D:/dump/romfs" --emulator-load "C:/Users/me/AppData/Roaming/<emulator>/load"
  Folder:    python install.py --romfs "D:/dump/romfs" --out "D:/mods-out"
Options:   --look gear|full|none (default gear)   --glow red|stock|off (default red)   --astcenc <path to astcenc>
Needs Python 3.14+ (Hookshot's builder ships one) and ARM's astcenc (see README). Uninstall: delete the mod folder."""
import argparse, glob, hashlib, json, os, shutil, subprocess, sys

if sys.version_info < (3, 14):
    sys.exit("Python 3.14 or newer is needed (it has compression.zstd). Hookshot users: use the Python inside "
             "HookshotBuilder's tools/python folder.")
HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "patcher")
sys.path.insert(0, LIB)
import game  # noqa: E402

MOD_NAME = "DarkLink-DemiseGlow"
VERSION = "1.0.0"
TITLE_ID = "0400486024DEC000"
ASTC_SETS = ["weapons", "clothes", "darksword", "icons"]


def find_astcenc(given):
    if given:
        return given
    for name in ("astcenc-avx2", "astcenc-sse4.1", "astcenc-sse2", "astcenc-neon", "astcenc"):
        for ext in (".exe", ""):
            hits = glob.glob(os.path.join(HERE, "astcenc", "**", name + ext), recursive=True)
            if hits:
                return hits[0]
        p = shutil.which(name)
        if p:
            return p
    sys.exit("astcenc not found: download ARM astcenc 5.7.1 (see README) and unzip it into the 'astcenc' folder next "
             "to install.py, or pass --astcenc <path>.")


def run_jobs(work, exe):
    """Run every astcenc job line of work/jobs.txt (paths are relative to `work`)."""
    for line in open(os.path.join(work, "jobs.txt")):
        args = line.split()
        if not args:
            continue
        r = subprocess.run([exe] + args, cwd=work, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"astcenc failed: {' '.join(args)}\n{r.stdout[-800:]}{r.stderr[-800:]}")


def check_game(romfs):
    """Every game file the patcher reads must match the version it was made for."""
    want = json.load(open(os.path.join(LIB, "game_files.json")))
    bad = []
    for rel, sha in want["sha256"].items():
        p = os.path.join(romfs, *rel.split("/"))
        if not os.path.exists(p):
            bad.append(f"missing {rel}")
        elif hashlib.sha256(open(p, "rb").read()).hexdigest() != sha:
            bad.append(f"different {rel}")
    if bad:
        sys.exit(f"This game version doesn't match the one the patcher was made for ({want['version']}):\n  "
                 + "\n  ".join(bad[:10]))


def make_assets(exe, look, glow):
    import bc_recolor, recolor_gear, model_patch, make_glow
    shutil.rmtree(os.path.join(LIB, "assets"), ignore_errors=True)
    shutil.rmtree(os.path.join(LIB, "work"), ignore_errors=True)
    if look != "none":
        print("BC textures ...")
        bc_recolor.process("Tex/Mt_Weapon_Sheath_Master_Rgh.bntx.zs", bc_recolor.rough,
                           "Tex/Mt_Weapon_Sheath_Master_Mtl.bntx.zs")
        bc_recolor.process("Tex/Mt_Angin_Acs_Player_Adult_Alb.bntx.zs", bc_recolor.darken)
        bc_recolor.process_bc3("Tex/Angin_Tile_A_Alb.bntx.zs", bc_recolor.darken, "Tex/Angin_Tile_D_Alb.bntx.zs")
        bc_recolor.process("Tex/Mt_Feather_Player_Adult_Alb.bntx.zs", bc_recolor.darken)
        for s in ASTC_SETS:
            print(f"ASTC textures: {s} ...")
            recolor_gear.use_set(s)
            recolor_gear.export()
            run_jobs(recolor_gear.WORK, exe)
            recolor_gear.recolor()
            run_jobs(recolor_gear.WORK, exe)
            recolor_gear.do_import()
        print("models ...")
        model_patch.main()
    if glow == "red":
        print("glow effect ...")
        make_glow.main()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hookshot", help="Hookshot folder (has romfs and mods)")
    ap.add_argument("--longshot", help="Longshot folder (Hookshot's successor: same romfs and mods layout)")
    ap.add_argument("--romfs", help="romfs folder of your own game dump")
    ap.add_argument("--emulator-load", help="the emulator's 'load' folder (mods go to load/<title id>/<mod>)")
    ap.add_argument("--out", help="write the mod folder here instead")
    ap.add_argument("--look", choices=["gear", "full", "none"], default="gear")
    ap.add_argument("--glow", choices=["red", "stock", "off"], default="red")
    ap.add_argument("--astcenc", help="path to astcenc (default: ./astcenc folder or PATH)")
    ap.add_argument("--uninstall", action="store_true", help="remove the mod folder (back to stock)")
    a = ap.parse_args()
    a.hookshot = a.hookshot or a.longshot
    if a.hookshot:
        romfs = a.romfs or os.path.join(a.hookshot, "romfs")
        dest = os.path.join(a.hookshot, "mods", MOD_NAME)
    elif a.romfs and (a.emulator_load or a.out):
        romfs = a.romfs
        dest = os.path.join(a.emulator_load, TITLE_ID, MOD_NAME) if a.emulator_load else os.path.join(a.out, MOD_NAME)
    elif a.uninstall and a.emulator_load:
        romfs, dest = None, os.path.join(a.emulator_load, TITLE_ID, MOD_NAME)
    elif a.uninstall and a.out:
        romfs, dest = None, os.path.join(a.out, MOD_NAME)
    else:
        ap.error("give --longshot or --hookshot, or --romfs with --emulator-load or --out")
    assert os.path.basename(dest) == MOD_NAME     # this tool only ever writes or deletes its own folder
    if a.uninstall:
        if os.path.isdir(dest):
            shutil.rmtree(dest)
            print(f"Uninstalled: removed {dest}. The game is back to stock.")
        else:
            print(f"Not installed (no {dest}). Nothing to remove.")
        return
    if a.look == "none" and a.glow == "off":
        ap.error("nothing to do")
    game.ROMFS = romfs
    check_game(romfs)
    exe = find_astcenc(a.astcenc) if a.look != "none" else None
    make_assets(exe, a.look, a.glow)
    import build_look
    # Build next to the target under a disabled name (a leading "-" makes Longshot/Hookshot skip it), then swap, so a
    # failed or interrupted build never leaves a half-made mod that the game would load.
    tmp = os.path.join(os.path.dirname(dest), "-" + MOD_NAME + "-building")
    log = build_look.build(tmp, a.look, a.glow)
    open(os.path.join(tmp, "README.txt"), "w").write(
        f"{MOD_NAME} {VERSION}: look {a.look}, glow {a.glow}. Made by install.py from your own game files. "
        "Run the installer again to change or uninstall, or delete this folder.\n")
    json.dump({"mod": MOD_NAME, "version": VERSION, "look": a.look, "glow": a.glow},
              open(os.path.join(tmp, "install.json"), "w"))
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    os.rename(tmp, dest)
    print("\n".join(log))
    print(f"\nInstalled: {dest}\nStart the game. Run the installer again to change or uninstall.")


if __name__ == "__main__":
    main()
