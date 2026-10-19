# SPDX-License-Identifier: LGPL-2.1-or-later
"""Follow the macOS appearance and accent colour (roadmap §13.3, step B).

While the BruceWorx preference pack is applied:

* FollowSystemAppearance (default on): when macOS switches between light and
  dark, the pack's light or dark values are written (theme, viewport, view cube,
  edge colours...). Only the keys that differ between the two modes change.
  FreeCAD reloads the stylesheet itself when the Theme parameter changes.
* FollowSystemAccent (default on): the macOS accent colour becomes FreeCAD's
  accent (Themes/ThemeAccentColor1, which the BruceWorx yaml files use as
  @AccentColor), plus the 3D selection and view-cube highlight colours.

Text and glyphs on the accent are white when white has at least 3:1 contrast
against it (macOS's own rule for buttons), otherwise near-black. They are
written as the tokens AccentTextColor and AccentGlyphColor in
Themes/UserParameters, so they are always present whichever accent is in use.
"""

from __future__ import annotations

import subprocess
import sys

PREFS_PATH = "User parameter:BaseApp/Preferences/BruceWorx"
THEME_PATH = "User parameter:BaseApp/Preferences/MainWindow"
ACCENT_PATH = "User parameter:BaseApp/Preferences/Themes"
TOKENS_PATH = "User parameter:BaseApp/Preferences/Themes/UserParameters"

# macOS accent colours (AppleAccentColor) as (light, dark) hex. Missing key = blue.
MAC_ACCENTS = {
    -1: ("#8E8E93", "#98989D"),  # graphite
    0: ("#FF3B30", "#FF453A"),  # red
    1: ("#FF9500", "#FF9F0A"),  # orange
    2: ("#FFCC00", "#FFD60A"),  # yellow
    3: ("#34C759", "#30D158"),  # green
    4: ("#007AFF", "#0A84FF"),  # blue
    5: ("#AF52DE", "#BF5AF2"),  # purple
    6: ("#FF2D55", "#FF375F"),  # pink
}
DEFAULT_ACCENT = 4
DARK_TEXT = "#1D1D1F"

# Stylesheet tokens this module writes to Themes/UserParameters (not in the yaml files).
RUNTIME_TOKENS = ("AccentTextColor", "AccentGlyphColor")


# ----- pure helpers (unit tested) -------------------------------------------------


def accent_hex(accent_index, dark: bool) -> str:
    light, dark_hex = MAC_ACCENTS.get(accent_index, MAC_ACCENTS[DEFAULT_ACCENT])
    return dark_hex if dark else light


def _channel(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    """WCAG relative luminance of #RRGGBB."""
    r, g, b = (int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def text_on(accent: str) -> tuple[str, str]:
    """(text colour, glyph colour name for images_classic) on an accent."""
    if contrast("#FFFFFF", accent) >= 3.0:
        return "#FFFFFF", "white"
    return DARK_TEXT, "black"


def packed(hex_color: str) -> int:
    """#RRGGBB as FreeCAD's 0xRRGGBBAA."""
    return (int(hex_color[1:], 16) << 8) | 0xFF


def mode_switch_entries(pack, mode: str) -> list[dict]:
    """The pack entries for ``mode`` whose value differs between light and dark."""
    light = {(e["path"], e["name"]): e["value"] for e in pack.pack_entries("light")}
    dark = {(e["path"], e["name"]): e["value"] for e in pack.pack_entries("dark")}
    return [e for e in pack.pack_entries(mode) if light.get((e["path"], e["name"])) != dark.get((e["path"], e["name"]))]


# ----- reading macOS ------------------------------------------------------------


def system_accent_index():
    """AppleAccentColor from the global defaults; None when not on macOS."""
    if sys.platform != "darwin":
        return None
    try:
        out = subprocess.run(
            ["defaults", "read", "-g", "AppleAccentColor"], capture_output=True, text=True, timeout=2
        )
    except Exception:
        return DEFAULT_ACCENT
    if out.returncode != 0:
        return DEFAULT_ACCENT  # key missing: the default blue (multicolour)
    try:
        return int(out.stdout.strip())
    except ValueError:
        return DEFAULT_ACCENT


def system_is_dark():
    """True/False from Qt's colour scheme, None when Qt does not know."""
    try:
        from PySide import QtCore, QtGui

        scheme = QtGui.QGuiApplication.styleHints().colorScheme()
        if scheme == QtCore.Qt.ColorScheme.Dark:
            return True
        if scheme == QtCore.Qt.ColorScheme.Light:
            return False
    except Exception:
        pass
    return None


# ----- applying ------------------------------------------------------------------


def _prefs():
    import FreeCAD

    return FreeCAD.ParamGet(PREFS_PATH)


def _current_dark() -> bool:
    import FreeCAD

    return "Dark" in FreeCAD.ParamGet(THEME_PATH).GetString("Theme", "")


def apply_mode(dark: bool) -> bool:
    """Write the pack's light or dark values. Returns True if anything changed."""
    if dark == _current_dark():
        return False
    import bruceworx_pack

    store = bruceworx_pack.FreeCADStore()
    bruceworx_pack.apply_entries(store, mode_switch_entries(bruceworx_pack, "dark" if dark else "light"))
    return True


def apply_accent(dark: bool) -> None:
    import FreeCAD

    prefs = _prefs()
    if prefs.GetBool("FollowSystemAccent", True):
        index = system_accent_index()
        accent = accent_hex(DEFAULT_ACCENT if index is None else index, dark)
        value = packed(accent)
        themes = FreeCAD.ParamGet(ACCENT_PATH)
        view = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View")
        cube = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/NaviCube")
        if view.GetUnsigned("SelectionColor", 0) != value:
            view.SetUnsigned("SelectionColor", value)
        if cube.GetUnsigned("HiliteColor", 0) != value:
            cube.SetUnsigned("HiliteColor", value)
    else:
        themes = FreeCAD.ParamGet(ACCENT_PATH)
        value = themes.GetUnsigned("ThemeAccentColor1", packed(accent_hex(DEFAULT_ACCENT, dark)))
        accent = "#%06X" % (value >> 8)
    text, glyph = text_on(accent)
    tokens = FreeCAD.ParamGet(TOKENS_PATH)
    # Tokens first: the accent write below is what makes FreeCAD reload the sheet.
    if tokens.GetString("AccentTextColor", "") != text:
        tokens.SetString("AccentTextColor", text)
    if tokens.GetString("AccentGlyphColor", "") != glyph:
        tokens.SetString("AccentGlyphColor", glyph)
    if themes.GetUnsigned("ThemeAccentColor1", 0) != value:
        themes.SetUnsigned("ThemeAccentColor1", value)


def sync(*_args) -> None:
    """Bring theme and accent in line with macOS."""
    prefs = _prefs()
    if not prefs.GetBool("Applied", False):
        return
    dark = _current_dark()
    if prefs.GetBool("FollowSystemAppearance", True):
        system = system_is_dark()
        if system is not None:
            apply_mode(system)
            dark = system
    apply_accent(dark)


# ----- live updates --------------------------------------------------------------

_installed = False
_filter = None
_timer = None


def _schedule():
    if _timer is not None:
        _timer.start()


def install() -> None:
    """Sync now and whenever macOS changes appearance or accent."""
    global _installed, _filter, _timer
    if _installed:
        return
    from PySide import QtCore, QtGui, QtWidgets

    app = QtWidgets.QApplication.instance()
    _timer = QtCore.QTimer()
    _timer.setSingleShot(True)
    _timer.setInterval(200)
    _timer.timeout.connect(sync)
    QtGui.QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _scheme: _schedule())

    class _Filter(QtCore.QObject):
        # The accent has no signal: macOS sends a palette change, and coming back
        # to the app after changing System Settings is an activation.
        def eventFilter(self, obj, event):
            if obj is app and event.type() in (
                QtCore.QEvent.ApplicationPaletteChange,
                QtCore.QEvent.ApplicationActivate,
            ):
                _schedule()
            return False

    _filter = _Filter()
    app.installEventFilter(_filter)
    _installed = True
    sync()
