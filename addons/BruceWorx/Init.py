# SPDX-License-Identifier: LGPL-2.1-or-later
"""Loaded when this folder is on FreeCAD's Mod path.

BruceWorx installs this add-on with the normal build as ``Mod/BruceWorxHooks``
(see CMakeLists.txt), so ``import bruceworx``, the part-number macro and
BruceWorx → Assign Part Number… are available by default.

Off switch: ``BaseApp/Preferences/BruceWorx/LoadHooks`` (the "Hooks add-on"
box on Preferences → BruceWorx). Off takes effect on the next start: the
folder is taken back off ``sys.path`` and InitGui.py adds nothing.
``--disable-addon BruceWorxHooks`` also works.

Headless use does not need any of this. Run hooks.py under FreeCADCmd; see
README.md.
"""

# FreeCAD execs this file inside its loader: names defined at the top of this
# file are not visible inside functions defined here, so everything lives in
# one function that imports what it uses. __file__ is not relied on; the
# loader has just put this folder on sys.path.


def _bw_hooks_init():
    import os
    import sys

    here = None
    for entry in sys.path:
        if os.path.isfile(os.path.join(entry, "bruceworx", "numbering.py")) and os.path.isfile(
            os.path.join(entry, "Init.py")
        ):
            here = entry
            break
    if here is None:
        return
    enabled = True
    try:
        import FreeCAD

        enabled = bool(
            FreeCAD.ParamGet("User parameter:BaseApp/Preferences/BruceWorx").GetBool(
                "LoadHooks", True
            )
        )
    except Exception:
        pass
    if enabled:
        if here not in sys.path:
            sys.path.insert(0, here)
    else:
        while here in sys.path:
            sys.path.remove(here)


_bw_hooks_init()
