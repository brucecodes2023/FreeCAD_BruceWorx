# History Timeline (BruceWorx spike)

Python add-on that reads a PartDesign body's history and shows it as a bottom bar. This is the FCB-P1F-15 / FCB-P1F-16 spike. It is not the full timeline build. Bruce reviews the design (FCB-P1F-17) before that build.

BruceWorx ships it **on by default** (the BruceWorx rule: every feature is on, with an off switch). The normal build copies this folder into `<build>/Mod/HistoryTimeline` (what `pixi run freecad-release` loads) and installs it to `Mod/HistoryTimeline` (`CMakeLists.txt`, wired from `src/Mod/CMakeLists.txt`; build switch `-DBUILD_BW_HISTORY_TIMELINE=OFF`). The dock shows along the bottom of the window on start.

The preference is `User parameter:BaseApp/Preferences/Mod/HistoryTimeline/Enabled` (default `true`).

On stock FreeCAD (no BruceWorx build), copy or symlink this directory into `<user-app-data>/Mod/HistoryTimeline` (`FreeCAD.getUserAppDataDir()` prints that parent), or start with `freecad -M /path/to/HistoryTimeline`.

## Turn it off

Any one of these is enough:

* Uncheck **BruceWorx → History Timeline**, or close the dock (both write `Enabled = false`, so it stays off on later starts).
* Uncheck **History timeline** on **Preferences → BruceWorx**.
* Drop an empty file named `ADDON_DISABLED` in the installed `Mod/HistoryTimeline` directory.
* Start FreeCAD with `--disable-addon HistoryTimeline`.
* Configure the build with `-DBUILD_BW_HISTORY_TIMELINE=OFF`.

The **BruceWorx** menu is kept on the menu bar by `src/Mod/BruceWorx/bruceworx_menu.py`. FreeCAD clears the menu bar on every workbench activation (`MenuManager::setup`), so a menu added once from `InitGui.py` would vanish when the startup workbench loads.

## What the dock does

Read-only order from `Body.Group`, rollback marker after `Body.Tip`.

* Click a solid feature: set the tip (same rule as **Set tip**).
* Double-click: `setEdit` on that object.
* Right-click: edit, roll the tip, suppress / unsuppress.
* **Move earlier** and **Move later** are present and disabled. Reorder is not safe yet. See `docs/SPIKE.md`.

## Headless test

From a source build:

```text
FreeCADCmd package/bruceworx/mods/HistoryTimeline/tests/test_timeline_access.py
```

From the conda package the binary is `freecadcmd`. Exit 0 means every check passed. The test does not load the GUI.

## Docs

* [Spike findings](docs/SPIKE.md) — what Python can and cannot do.
* [UX note](docs/UX.md) — the bar, the mocks, what the prototype actually does.
* [Questions for Bruce](docs/REVIEW.md) — FCB-P1F-17.

Regenerate the mock PNGs with PySide6 and no FreeCAD:

```text
QT_QPA_PLATFORM=offscreen python docs/mock/render_mock.py
```

Optional in-app grab (needs a display or `xvfb-run`):

```text
xvfb-run -a freecad -M /path/to/HistoryTimeline tests/grab_prototype.py
```
