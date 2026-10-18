# SPDX-License-Identifier: LGPL-2.1-or-later
"""BruceWorx GUI init. Loaded for every session.

BruceWorx rule: everything ships on by default, each with an off switch on
Preferences → BruceWorx. This file:

* applies the BruceWorx preference pack on first start (bruceworx_defaults),
* installs the preference page and the overlay model tree (default on),
* starts the ground grid, which shows only while the preference pack is applied,
* creates the shared top-level BruceWorx menu (bruceworx_menu).

It runs before the startup workbench is activated, so the first-run pack's
startup workbench (PartDesign) is already used on that first start.
"""


def _bw_warn(message):
    try:
        import FreeCAD

        FreeCAD.Console.PrintWarning(message + "\n")
    except Exception:
        print(message)


try:
    import bruceworx_defaults

    bruceworx_defaults.startup()
except Exception as exc:  # pragma: no cover - FreeCAD console only
    _bw_warn(f"BruceWorx defaults were not applied: {exc}")

import BruceWorx

BruceWorx.install()

try:
    import bruceworx_menu

    bruceworx_menu.get_menu()
    bruceworx_menu.install_preferences_entry()
except Exception as exc:  # pragma: no cover - FreeCAD console only
    _bw_warn(f"BruceWorx menu was not created: {exc}")

try:
    import ground_grid

    ground_grid.startup()
except Exception as exc:  # pragma: no cover - FreeCAD console only
    _bw_warn(f"BruceWorx ground grid was not started: {exc}")
