# SPDX-License-Identifier: LGPL-2.1-or-later
"""Load the BruceWorx ground grid only when the preference pack is applied."""

try:
    import ground_grid

    ground_grid.startup()
except Exception as exc:  # pragma: no cover - FreeCAD console only
    try:
        import FreeCAD

        FreeCAD.Console.PrintWarning(f"BruceWorx ground grid was not started: {exc}\n")
    except Exception:
        print(f"BruceWorx ground grid was not started: {exc}")
