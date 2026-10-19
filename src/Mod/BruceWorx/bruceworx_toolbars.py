# SPDX-License-Identifier: LGPL-2.1-or-later
"""Two toolbar rows: app-wide toolbars on the first, the workbench's tools on the second.

FreeCAD restores toolbar line breaks from the saved window state, so tools can
end up spread over three or four rows (add-ons that rebuild the toolbar area
leave breaks behind). With Preferences/BruceWorx/CompactToolbars on (default),
BruceWorx re-lays the top toolbars after every workbench switch: File, the
workbench tabs and View share row 1, and every workbench toolbar follows on
row 2 with no further breaks (roadmap §13.3, step A).
"""

from __future__ import annotations

PREFS_PATH = "User parameter:BaseApp/Preferences/BruceWorx"
PREF_NAME = "CompactToolbars"

# Toolbars that belong to the application, not to a workbench.
APP_TOOLBARS = ("File", "Workbench", "View", "Edit", "Clipboard", "Macro", "Help", "Individual Views")


def plan_breaks(names, app_toolbars=APP_TOOLBARS):
    """Names, in row order, that should start a new row.

    App toolbars stay together on the first row. The first workbench toolbar
    starts the second row and the rest follow it. App toolbars that come after a
    workbench toolbar are not moved; they simply get no break.
    """
    for name in names:
        if name not in app_toolbars:
            return {name}
    return set()


def _enabled():
    import FreeCAD

    return FreeCAD.ParamGet(PREFS_PATH).GetBool(PREF_NAME, True)


def relayout():
    """Apply ``plan_breaks`` to the visible top toolbars of the main window."""
    if not _enabled():
        return
    import FreeCADGui
    from PySide import QtCore, QtWidgets

    mw = FreeCADGui.getMainWindow()
    top = QtCore.Qt.ToolBarArea.TopToolBarArea
    bars = [
        tb
        for tb in mw.findChildren(QtWidgets.QToolBar)
        if tb.parent() is mw and tb.isVisible() and mw.toolBarArea(tb) == top
    ]
    # Row order as laid out: breaks are positional, so sort by where they sit.
    bars.sort(key=lambda tb: (tb.geometry().y(), tb.geometry().x()))
    app = [tb for tb in bars if tb.objectName() in APP_TOOLBARS]
    rest = [tb for tb in bars if tb.objectName() not in APP_TOOLBARS]
    wanted = plan_breaks([tb.objectName() for tb in app + rest])
    for tb in app + rest:
        if mw.toolBarBreak(tb):
            mw.removeToolBarBreak(tb)
    # Re-adding moves each toolbar to the end of the top area, in this order.
    for tb in app + rest:
        if tb.objectName() in wanted:
            mw.addToolBarBreak(top)
        mw.addToolBar(top, tb)
        tb.show()


_installed = False


def install():
    """Re-lay the toolbars after every workbench switch."""
    global _installed
    if _installed:
        return
    import FreeCADGui
    from PySide import QtCore

    mw = FreeCADGui.getMainWindow()
    mw.workbenchActivated.connect(lambda _name: QtCore.QTimer.singleShot(0, relayout))
    _installed = True
