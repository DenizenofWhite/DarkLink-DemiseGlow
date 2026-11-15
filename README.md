# Dark Link & Demise Glow

A mod for **The Legend of Zelda: Ocarina of Time** (Switch 2), for **Longshot**, **Hookshot** and Switch
emulators.

- **Dark Link Gear:** Dark Link's black Master Sword (ruby jewel) and shield, black tunic, undercoat, boots, gloves and
  hat, silver buckles and earrings, black-and-silver sheath, with Link's normal face.
- **Full Dark Link:** the same, with Dark Link's skin and eyes.
- **Demise Glow:** the Master Sword always shines with its final-battle aura, swing swoop and lens flare, recoloured
  to a deep red with hot scarlet-orange glints, like a corrupted blade heating up. It goes dark when sheathed.

**No game files are included.** The patcher builds every file from **your own** copy of the game on your PC, checks
first that your game files are the version it was made for, and refuses to run otherwise. Only code is published here.

## You need

1. Your own game files (the `romfs` folder). Longshot and Hookshot users already have it in their game folder.
2. **Python 3.14 or newer** (python.org; Hookshot's builder also ships one in its `tools\python` folder).
3. **ARM astcenc 5.7.1** (free, open source, Apache 2.0) for the texture recolours:
   https://github.com/ARM-software/astc-encoder/releases/tag/5.7.1 . Download the zip for your system; the installer
   window unpacks it for you (command line: unzip it into a folder named `astcenc` next to `install.py`).

## Install (the easy way)

1. Unzip this mod anywhere.
2. Double-click **`Install.bat`**. A window opens.
3. **Prerequisites:** if Python or astcenc shows **Missing**, click **Install Prerequisite** next to it (it asks
   first). Python is installed with winget, Windows' own installer; astcenc is downloaded from ARM's GitHub page and
   checked against ARM's published fingerprint before use. If that can't work (offline, or no winget), the
   **Install by Hand** window opens the right download page: install it yourself, then click **Check Again** (for
   astcenc, just leave `astcenc-5.7.1-windows-x64.zip` in your Downloads folder).
4. Pick your game: your **Longshot / Hookshot** folder, or for an emulator your game's `romfs` folder plus the
   emulator's `load` folder.
5. Pick a **look** and a **glow**, then click **Install / Change**. It takes a few minutes.

**Something went wrong?** Your game only changes when an install finishes, so a failed install leaves it as it was.
Click **Report a Problem**: it opens a bug report on this mod's GitHub page with the details filled in (your user name and folders are hidden; you review it and click
submit yourself; you need a free GitHub account). The full log is also copied to your clipboard.

**To switch options:** run `Install.bat` again, pick the new look or glow, click **Install / Change**.
**To go back to stock:** run `Install.bat` again and click **Uninstall**.
Close the game first: the installer refuses while it's running.

## Install from the command line

Longshot (installs into `<Longshot>\mods\DarkLink-DemiseGlow`):

    python install.py --longshot "C:\Games\Longshot"

Hookshot: the same with `--hookshot "C:\Games\Hookshot"`. (If you moved your mods folder with `HOS_MODS`, use
`--romfs <game>\romfs --out <your mods folder>`.)

Emulator (installs into `<load folder>\0400486024DEC000\DarkLink-DemiseGlow`):

    python install.py --romfs "D:\dump\romfs" --emulator-load "C:\path\to\emulator\load"

Anywhere else: `--romfs <romfs> --out <folder>`.

Options:

| Option | Values | Default |
|---|---|---|
| `--look` | `gear` (Dark Link's Gear, Link's Normal Face), `full` (Full Dark Link, Dark Link's Skin and Eyes), `none` | `gear` |
| `--glow` | `red` (Demise glow), `stock` (always-on glow in the game's own colours), `off` | `red` |

Building takes a few minutes (texture recolouring). Run it with the game closed, then start the game.

**Uninstall:** `--uninstall` (or delete the `DarkLink-DemiseGlow` folder). **Change options:** run `install.py` again.

## Notes

- Only Link changes. The recoloured textures are given their own names, so the Dark Link boss, the tunic items and
  anything else that shares the game's textures keep their normal look. Two exceptions by design: both looks use Dark
  Link's own sword model, so his sword shares the ruby jewel; and in `full` Link wears Dark Link's own body model, so
  the boss matches you.
- The glow option makes the Master Sword shine all the time (the game normally only does this in the final battle);
  with it on, the sheathed glow is switched off everywhere, the final battle included.
- Made for game build e0f3ccfa (program 0400486024DEC000), the build Longshot and Hookshot support. Tested on
  Hookshot v2.0.14. Longshot and emulators: reports welcome.
- Unofficial fan project. Use your own legally obtained copy of the game.

Made by DenizenofWhite. Built with AI assistance.
