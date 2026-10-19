# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketch grid strength: one number for how visible the sketch grid is.

Preferences/BruceWorx/SketchGridStrength (percent, default 10) sets the
Sketcher's grid colours: white lines on the dark theme, black on the light one,
at that opacity, with the major lines a little stronger. The colours are
translucent, so the lines stay equally faint over the whole viewport gradient
(this needs the [BW] alpha change in Part/Gui/ViewProviderGridExtension.cpp).

Change it on Preferences > BruceWorx, or from the Python console:

    import bruceworx_grid
    bruceworx_grid.set_strength(14)

Open sketches update at once. Only applies while the BruceWorx preference pack
is applied, so a user's own grid colours are left alone otherwise.
"""

from __future__ import annotations

PREFS_PATH = "User parameter:BaseApp/Preferences/BruceWorx"
SKETCHER_PATH = "User parameter:BaseApp/Preferences/Mod/Sketcher/General"
THEME_PATH = "User parameter:BaseApp/Preferences/MainWindow"
PREF_NAME = "SketchGridStrength"
DEFAULT_STRENGTH = 10
MIN_STRENGTH = 2
MAX_STRENGTH = 40

# Black lines read stronger on the light viewport than white ones on the dark.
LIGHT_SCALE = 0.8
MAJOR_SCALE = 1.8


def clamp(strength) -> int:
    return max(MIN_STRENGTH, min(MAX_STRENGTH, int(round(strength))))


def colors(strength, dark: bool) -> tuple[int, int]:
    """Packed 0xRRGGBBAA colours (minor, major) for a strength in percent."""
    strength = clamp(strength)
    base = 0xFFFFFF if dark else 0x000000
    minor = strength * (1.0 if dark else LIGHT_SCALE) * 2.55
    major = min(255.0, minor * MAJOR_SCALE)
    return (base << 8) | int(round(minor)), (base << 8) | int(round(major))


def _is_dark() -> bool:
    import FreeCAD

    return "Dark" in FreeCAD.ParamGet(THEME_PATH).GetString("Theme", "")


def apply() -> None:
    """Write the grid colours for the current strength and theme."""
    import FreeCAD

    prefs = FreeCAD.ParamGet(PREFS_PATH)
    if not prefs.GetBool("Applied", False):
        return
    minor, major = colors(prefs.GetInt(PREF_NAME, DEFAULT_STRENGTH), _is_dark())
    sketcher = FreeCAD.ParamGet(SKETCHER_PATH)
    if sketcher.GetUnsigned("GridLineColor", 0) != minor:
        sketcher.SetUnsigned("GridLineColor", minor)
    if sketcher.GetUnsigned("GridDivLineColor", 0) != major:
        sketcher.SetUnsigned("GridDivLineColor", major)


def set_strength(percent) -> int:
    """Set the grid strength (2-40 %) and apply it. Returns the value stored."""
    import FreeCAD

    value = clamp(percent)
    FreeCAD.ParamGet(PREFS_PATH).SetInt(PREF_NAME, value)
    apply()
    return value


class _Observer:
    def onChange(self, _group, name):
        if name in (PREF_NAME, "Theme", "Applied"):
            apply()


_observer = None
_groups = []


def install() -> None:
    """Apply now, and again whenever the strength or the theme changes."""
    global _observer
    if _observer is not None:
        return
    import FreeCAD

    _observer = _Observer()
    for path in (PREFS_PATH, THEME_PATH):
        # Keep the handles: a collected wrapper detaches its observer.
        group = FreeCAD.ParamGet(path)
        group.Attach(_observer)
        _groups.append(group)
    apply()
