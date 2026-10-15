# History Timeline (BruceWorx spike)

Python add-on that reads a PartDesign body's history and shows it as a bottom bar. This is the FCB-P1F-15 / FCB-P1F-16 spike. It is not the full timeline build. Bruce reviews the design (FCB-P1F-17) before that build.

The folder is **not** under `src/Mod`, so a normal BruceWorx build does not load it.

## Turn it on

Copy or symlink this directory into FreeCAD's user Mod folder:

```text
<user-app-data>/Mod/HistoryTimeline
```

`FreeCAD.getUserAppDataDir()` prints that parent. Or pass the folder that contains `Init.py`:

```text
freecad -M /path/to/HistoryTimeline
```

Then use **BruceWorx → History Timeline**. The dock stays hidden until that item is checked. The preference is `User parameter:BaseApp/Preferences/Mod/HistoryTimeline/Enabled` (default `false`).

## Turn it off

Any one of these is enough:

* Uncheck **BruceWorx → History Timeline**, or close the dock (both clear the preference).
* Drop an empty file named `ADDON_DISABLED` in this directory.
* Start FreeCAD with `--disable-addon HistoryTimeline`.
* Remove the folder from the module path. That is the default for this fork.

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
