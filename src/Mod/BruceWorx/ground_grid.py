# SPDX-License-Identifier: LGPL-2.1-or-later
"""Small toggleable ground grid for the BruceWorx preference pack.

The grid is a Coin overlay on the active 3D view, not a document object, so
it never lands in the FCStd file. It is drawn only while the pack is applied
and ``ShowGroundGrid`` is true. Turning the pack off removes the overlay and
the menu item.
"""

from __future__ import annotations

# 500 mm square, 10 mm minor lines, 100 mm major lines. Small on purpose:
# it sits under a part, it is not a construction grid for a building.
HALF_EXTENT_MM = 250.0
STEP_MM = 10.0
MAJOR_EVERY = 10

MINOR_RGB = (0.62, 0.64, 0.68)
MAJOR_RGB = (0.42, 0.45, 0.50)

_STATE = {
    "separator": None,
    "root": None,
    "observer": None,
    "action": None,
}


def grid_segments(half: float = HALF_EXTENT_MM, step: float = STEP_MM, major_every: int = MAJOR_EVERY):
    """World-space line segments on the XY plane.

    Each item is ``((x1, y1, z1), (x2, y2, z2), major)``.
    """
    if step <= 0 or half < 0:
        raise ValueError("grid extent and step must be positive")
    count = int(round(half / step))
    segments = []
    for index in range(-count, count + 1):
        major = index % major_every == 0
        coord = index * step
        segments.append(((-half, coord, 0.0), (half, coord, 0.0), major))
        segments.append(((coord, -half, 0.0), (coord, half, 0.0), major))
    return segments


def should_show(applied: bool, show_flag: bool) -> bool:
    return bool(applied) and bool(show_flag)


def _prefs():
    import FreeCAD as App

    return App.ParamGet("User parameter:BaseApp/Preferences/BruceWorx")


def prefs_request_grid() -> bool:
    group = _prefs()
    return should_show(group.GetBool("Applied", False), group.GetBool("ShowGroundGrid", False))


def build_grid_node():
    """Coin separator for the grid. Imports pivy only when a view is attached."""
    from pivy import coin

    sep = coin.SoSeparator()
    sep.setName("BruceWorxGroundGrid")
    style = coin.SoDrawStyle()
    style.lineWidth.setValue(1.0)
    sep.addChild(style)

    buckets = {False: [], True: []}
    for start, end, major in grid_segments():
        buckets[major].append((start, end))

    colors = {False: MINOR_RGB, True: MAJOR_RGB}
    for major, pairs in buckets.items():
        if not pairs:
            continue
        points = []
        for start, end in pairs:
            points.append(start)
            points.append(end)
        group = coin.SoSeparator()
        color = coin.SoBaseColor()
        color.rgb = colors[major]
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), points)
        lines = coin.SoLineSet()
        lines.numVertices.setValues([2] * len(pairs))
        group.addChild(color)
        group.addChild(coords)
        group.addChild(lines)
        sep.addChild(group)
    return sep


def _active_scene():
    import FreeCADGui as Gui

    doc = getattr(Gui, "ActiveDocument", None)
    if doc is None:
        return None, None
    view = getattr(doc, "ActiveView", None)
    if view is None or not hasattr(view, "getSceneGraph"):
        return None, None
    return view, view.getSceneGraph()


def _detach():
    sep = _STATE["separator"]
    root = _STATE["root"]
    if sep is not None and root is not None:
        try:
            root.removeChild(sep)
        except Exception:
            pass
    _STATE["separator"] = None
    _STATE["root"] = None


def sync() -> None:
    """Add or remove the overlay so it matches the current preferences."""
    if not prefs_request_grid():
        _detach()
        return
    view, root = _active_scene()
    if root is None:
        _detach()
        return
    if _STATE["separator"] is not None and _STATE["root"] is root:
        return
    _detach()
    sep = build_grid_node()
    root.addChild(sep)
    _STATE["separator"] = sep
    _STATE["root"] = root
    try:
        view.getViewer().getSoRenderManager().scheduleRedraw()
    except Exception:
        pass


def toggle() -> bool:
    """Flip ShowGroundGrid while the pack is applied. Returns the new flag."""
    group = _prefs()
    if not group.GetBool("Applied", False):
        return False
    updated = not group.GetBool("ShowGroundGrid", True)
    group.SetBool("ShowGroundGrid", updated)
    sync()
    _refresh_action()
    return updated


class _Observer:
    def slotActivateDocument(self, doc):  # noqa: ARG002 - FreeCAD observer signature
        sync()

    def slotCreatedDocument(self, doc):  # noqa: ARG002
        sync()

    def slotDeletedDocument(self, doc):  # noqa: ARG002
        _detach()


def _tools_menu():
    import FreeCADGui as Gui

    window = Gui.getMainWindow()
    if window is None:
        return None
    bar = window.menuBar()
    for action in bar.actions():
        menu = action.menu()
        if menu is None:
            continue
        title = menu.title().replace("&", "")
        if title in ("Tools",):
            return menu
    return None


def _refresh_action() -> None:
    action = _STATE["action"]
    if action is None:
        return
    try:
        group = _prefs()
        action.setChecked(group.GetBool("ShowGroundGrid", False))
    except Exception:
        pass


def _bruceworx_menu():
    """The shared BruceWorx menu. The Tools menu is rebuilt on every workbench
    switch (MenuManager::setup clears the menu bar), so an action added there
    from InitGui disappears; the BruceWorx menu is re-attached instead."""
    try:
        import bruceworx_menu

        return bruceworx_menu.get_menu()
    except Exception:
        return _tools_menu()


def _install_menu() -> None:
    if _STATE["action"] is not None:
        _refresh_action()
        return
    menu = _bruceworx_menu()
    if menu is None:
        return
    from PySide import QtGui  # FreeCAD 1.1 ships PySide (Qt6 shims) as PySide

    action = QtGui.QAction(menu)
    action.setText("Ground Grid")
    action.setObjectName("BruceWorxGroundGridAction")
    action.setCheckable(True)
    action.setToolTip("Show or hide the BruceWorx 3D ground grid")
    action.triggered.connect(lambda _checked=False: toggle())
    try:
        import bruceworx_menu

        bruceworx_menu.add_action(action)
    except Exception:
        menu.addAction(action)
    _STATE["action"] = action
    _refresh_action()


def _remove_menu() -> None:
    action = _STATE["action"]
    if action is None:
        return
    menus = [_tools_menu()]
    try:
        import bruceworx_menu

        menus.append(bruceworx_menu.get_menu(create=False))
    except Exception:
        pass
    for menu in menus:
        if menu is not None:
            menu.removeAction(action)
    action.deleteLater()
    _STATE["action"] = None


def activate() -> None:
    """Start showing the grid and add the BruceWorx → Ground Grid toggle."""
    import FreeCADGui as Gui

    if _STATE["observer"] is None:
        observer = _Observer()
        Gui.addDocumentObserver(observer)
        _STATE["observer"] = observer
    _install_menu()
    sync()


def deactivate() -> None:
    """Remove the overlay, the observer and the menu item."""
    _detach()
    observer = _STATE["observer"]
    if observer is not None:
        try:
            import FreeCADGui as Gui

            Gui.removeDocumentObserver(observer)
        except Exception:
            pass
        _STATE["observer"] = None
    _remove_menu()


def startup() -> None:
    """Called from InitGui. Does nothing while the pack is off."""
    try:
        group = _prefs()
    except Exception:
        return
    if group.GetBool("Applied", False):
        activate()
