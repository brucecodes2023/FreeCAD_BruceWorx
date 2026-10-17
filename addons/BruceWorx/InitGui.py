# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI init for the BruceWorx hooks add-on (on by default).

Adds BruceWorx → Assign Part Number… (command ``BruceWorx_PartNumber``).
Does nothing when ``BaseApp/Preferences/BruceWorx/LoadHooks`` is false.
FreeCAD execs this file; the module directory is already on sys.path.
"""


def _bw_hooks_gui():
    import FreeCAD

    group = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/BruceWorx")
    if not group.GetBool("LoadHooks", True):
        FreeCAD.Console.PrintLog("BruceWorx hooks add-on is off (LoadHooks=false)\n")
        return
    from bruceworx import gui

    gui.install()


try:
    _bw_hooks_gui()
except Exception as exc:  # pragma: no cover - FreeCAD console only
    try:
        import FreeCAD

        FreeCAD.Console.PrintWarning(f"BruceWorx hooks add-on GUI was not loaded: {exc}\n")
    except Exception:
        print(f"BruceWorx hooks add-on GUI was not loaded: {exc}")
