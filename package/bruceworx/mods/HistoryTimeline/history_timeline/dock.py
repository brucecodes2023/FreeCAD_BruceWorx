# SPDX-License-Identifier: LGPL-2.1-or-later
"""FreeCAD dock that shows ``read_timeline`` and rolls ``Body.Tip``.

BruceWorx ships this on by default: ``Mod/HistoryTimeline/Enabled`` defaults to
true, so the dock shows on a normal start. The off switches are the
BruceWorx → History Timeline menu item, the "History timeline" box on
Preferences → BruceWorx, or closing the dock. All three write the preference
back to false; the dock then stays hidden on later starts.
"""

from __future__ import annotations

import FreeCAD

from history_timeline import model
from history_timeline.bar import TimelineBar
from history_timeline.qtcompat import load_qt, qt_enum

QtCore, QtGui, QtWidgets = load_qt()

PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/HistoryTimeline"
DOCK_OBJECT_NAME = "HistoryTimelineDock"
COMMAND_NAME = "HistoryTimeline_Toggle"

_state = {
    "dock": None,
    "action": None,
    "observer": None,
    "pref_observer": None,
    "pref_group": None,
    "syncing": False,
    "installed": False,
}


def prefs():
    return FreeCAD.ParamGet(PARAM_PATH)


ENABLED_DEFAULT = True


def is_enabled() -> bool:
    return bool(prefs().GetBool("Enabled", ENABLED_DEFAULT))


def _bottom_area():
    return qt_enum(
        QtCore.Qt,
        ("DockWidgetArea", "BottomDockWidgetArea"),
        ("BottomDockWidgetArea",),
    )


def _view_icon(obj):
    if not FreeCAD.GuiUp:
        return None
    view = getattr(obj, "ViewObject", None)
    if view is None:
        return None
    icon = getattr(view, "Icon", None)
    return icon


def active_body():
    """Active PartDesign body (``pdbody``), else the first body in the document.

    Returns ``(body, source)`` where source is ``"active"``, ``"first"``, or ``"none"``.
    """
    doc = FreeCAD.ActiveDocument
    if doc is None:
        return None, "none"
    if FreeCAD.GuiUp:
        import FreeCADGui

        gui_doc = FreeCADGui.ActiveDocument
        view = getattr(gui_doc, "ActiveView", None) if gui_doc is not None else None
        getter = getattr(view, "getActiveObject", None)
        if getter is not None:
            try:
                body = getter("pdbody")
            except (RuntimeError, TypeError):
                body = None
            if isinstance(body, tuple):
                body = body[0] if body else None
            if body is not None and getattr(body, "TypeId", "") == "PartDesign::Body":
                return body, "active"
    for obj in doc.Objects:
        if getattr(obj, "TypeId", "") == "PartDesign::Body":
            return obj, "first"
    return None, "none"


class _DocumentObserver:
    def __init__(self, dock):
        self._dock = dock

    def slotChangedObject(self, _obj, _prop):
        self._dock.schedule_refresh()

    def slotCreatedObject(self, _obj):
        self._dock.schedule_refresh()

    def slotDeletedObject(self, _obj):
        self._dock.schedule_refresh()

    def slotActivateDocument(self, _doc):
        self._dock.schedule_refresh()

    def slotDeleteDocument(self, _doc):
        self._dock.schedule_refresh()

    def slotUndoDocument(self, _doc):
        self._dock.schedule_refresh()

    def slotRedoDocument(self, _doc):
        self._dock.schedule_refresh()


class HistoryTimelineDock(QtWidgets.QDockWidget):
    def __init__(self, parent):
        super().__init__("History Timeline", parent)
        self.setObjectName(DOCK_OBJECT_NAME)
        self.setAllowedAreas(_bottom_area())
        self._bar = TimelineBar(self)
        self._bar.tipRequested.connect(self._roll_to)
        self._bar.editRequested.connect(self._edit)
        self._bar.contextMenuRequested.connect(self._popup)
        self.setWidget(self._bar)
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(0)
        self._refresh_timer.timeout.connect(self.refresh)
        self._suspend = False

    def schedule_refresh(self):
        if not self._suspend:
            self._refresh_timer.start()

    def refresh(self):
        if self._suspend:
            return
        body, source = active_body()
        if body is None:
            self._bar.set_timeline(
                None,
                [],
                "No PartDesign body. Create one, or activate a body, to see its history.",
            )
            return
        timeline = model.read_timeline(body)
        for entry in timeline.entries:
            entry.icon = _view_icon(entry.obj)
        if source == "first":
            label = f"{timeline.body_label}  (first body — none active)"
        else:
            label = timeline.body_label
        self._bar.set_timeline(label, timeline.entries)

    def _feature(self, name):
        body, _source = active_body()
        if body is None:
            return None, None
        for obj in body.Group:
            if obj.Name == name:
                return body, obj
        return body, None

    def _transaction(self, title, fn):
        body, _source = active_body()
        doc = body.Document if body is not None else FreeCAD.ActiveDocument
        if doc is None:
            return
        self._suspend = True
        doc.openTransaction(title)
        try:
            fn(doc, body)
        except Exception:
            doc.abortTransaction()
            self._suspend = False
            raise
        else:
            doc.commitTransaction()
            self._suspend = False
            doc.recompute()
            self.refresh()

    def _roll_to(self, name):
        body, feature = self._feature(name)
        if feature is None:
            return
        ok, reason = model.can_be_tip(body, feature)
        if not ok:
            FreeCAD.Console.PrintWarning(reason + "\n")
            return

        def apply(doc, _body):
            model.set_tip(body, feature)
            # Match PartDesign_MoveTip: show the feature. The view provider
            # hides the other solids when the GUI is up.
            if FreeCAD.GuiUp:
                feature.Visibility = True

        self._transaction("Roll history tip", apply)

    def _edit(self, name):
        _body, feature = self._feature(name)
        if feature is None or not FreeCAD.GuiUp:
            return
        import FreeCADGui

        try:
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(feature)
            FreeCADGui.ActiveDocument.setEdit(feature)
        except Exception as exc:
            FreeCAD.Console.PrintError(f"History timeline: cannot edit {name}: {exc}\n")

    def _set_suppressed(self, feature, value):
        def apply(_doc, _body):
            model.set_suppressed(feature, value)

        title = "Suppress feature" if value else "Unsuppress feature"
        self._transaction(title, apply)

    def _popup(self, name, global_pos):
        body, feature = self._feature(name)
        if feature is None:
            return
        menu = QtWidgets.QMenu(self)
        edit_action = menu.addAction("Edit feature")
        edit_action.triggered.connect(lambda _checked=False, n=name: self._edit(n))

        roll_action = menu.addAction("Roll history to here")
        ok, reason = model.can_be_tip(body, feature)
        roll_action.setEnabled(ok)
        if not ok:
            roll_action.setToolTip(reason)
        roll_action.triggered.connect(lambda _checked=False, n=name: self._roll_to(n))

        if hasattr(feature, "Suppressed"):
            suppressed = model.is_suppressed(feature)
            label = "Unsuppress feature" if suppressed else "Suppress feature"
            suppress_action = menu.addAction(label)
            suppress_action.triggered.connect(
                lambda _checked=False, feat=feature, flag=not suppressed: self._set_suppressed(
                    feat, flag
                )
            )
        else:
            missing = menu.addAction("Suppress feature")
            missing.setEnabled(False)
            missing.setToolTip("This object has no Suppressed property.")

        menu.addSeparator()
        earlier = menu.addAction("Move earlier")
        later = menu.addAction("Move later")
        for action in (earlier, later):
            action.setEnabled(False)
            action.setToolTip(
                "Not in this spike. Assigning Body.Group does not rewrite BaseFeature."
            )
        if hasattr(menu, "exec"):
            menu.exec(global_pos)
        else:
            menu.exec_(global_pos)

    def closeEvent(self, event):
        # Closing the dock is the disable gesture. Preference goes back to false.
        set_enabled(False, hide_widget=False)
        super().closeEvent(event)


class _ToggleCommand:
    def GetResources(self):
        return {
            "CmdType": "ForEdit",
            "MenuText": "Toggle history timeline",
            "ToolTip": (
                "Show or hide the PartDesign history timeline. "
                "On by default. Preference: Mod/HistoryTimeline/Enabled."
            ),
        }

    def Activated(self, *_args):
        set_enabled(not is_enabled())

    def IsActive(self):
        return True


def _ensure_dock():
    import FreeCADGui

    dock = _state["dock"]
    if dock is not None:
        return dock
    window = FreeCADGui.getMainWindow()
    dock = HistoryTimelineDock(window)
    window.addDockWidget(_bottom_area(), dock)
    _state["dock"] = dock
    return dock


def _ensure_observer(dock):
    if _state["observer"] is None:
        observer = _DocumentObserver(dock)
        FreeCAD.addDocumentObserver(observer)
        _state["observer"] = observer


def _drop_observer():
    observer = _state["observer"]
    if observer is not None:
        try:
            FreeCAD.removeDocumentObserver(observer)
        except (AttributeError, RuntimeError, TypeError):
            pass
        _state["observer"] = None


def set_enabled(enabled: bool, hide_widget: bool = True):
    """Persist the preference and show or hide the dock."""
    _state["syncing"] = True
    try:
        prefs().SetBool("Enabled", bool(enabled))
    finally:
        _state["syncing"] = False
    action = _state["action"]
    if action is not None:
        action.blockSignals(True)
        action.setChecked(bool(enabled))
        action.blockSignals(False)
    if not FreeCAD.GuiUp:
        return
    if enabled:
        dock = _ensure_dock()
        _ensure_observer(dock)
        dock.show()
        dock.raise_()
        dock.refresh()
    else:
        _drop_observer()
        dock = _state["dock"]
        if hide_widget and dock is not None:
            dock.hide()


class _PrefObserver:
    """Follows ``Enabled`` when it is changed elsewhere (the preference page)."""

    def onChange(self, _group, name):
        if name != "Enabled" or _state["syncing"]:
            return
        QtCore.QTimer.singleShot(0, _follow_pref)


def _follow_pref():
    enabled = is_enabled()
    dock = _state["dock"]
    visible = dock is not None and dock.isVisible()
    if enabled != visible:
        set_enabled(enabled)


def _menu_fallback(window):
    """Same object name and re-attach rule as BruceWorx's bruceworx_menu, for
    running this add-on on a FreeCAD without the BruceWorx module."""
    menu = window.findChild(QtWidgets.QMenu, "BruceWorxMenu")
    if menu is None:
        menu = QtWidgets.QMenu("BruceWorx", window)
        menu.setObjectName("BruceWorxMenu")

    def attach(*_args):
        bar = window.menuBar()
        if menu.menuAction() not in bar.actions():
            bar.addMenu(menu)

    try:
        window.workbenchActivated.connect(lambda _name: QtCore.QTimer.singleShot(0, attach))
    except Exception:
        pass
    attach()
    return menu


def install():
    """Register the menu command and show the dock unless the preference is off."""
    if _state["installed"]:
        return
    if not FreeCAD.GuiUp:
        return
    import FreeCADGui

    FreeCADGui.addCommand(COMMAND_NAME, _ToggleCommand())

    window = FreeCADGui.getMainWindow()
    action = QtGui.QAction("History Timeline", window)
    action.setObjectName("HistoryTimelineAction")
    action.setCheckable(True)
    action.setChecked(is_enabled())
    action.setToolTip(
        "Bottom PartDesign history bar. On by default. "
        "Uncheck, close the dock, or turn it off on Preferences → BruceWorx."
    )
    action.toggled.connect(set_enabled)
    try:
        # The menu bar is rebuilt on every workbench switch; bruceworx_menu
        # keeps the BruceWorx menu on it.
        import bruceworx_menu

        bruceworx_menu.add_action(action)
    except ImportError:
        _menu_fallback(window).addAction(action)
    _state["action"] = action

    if _state["pref_observer"] is None:
        observer = _PrefObserver()
        # Keep the group handle: the Python wrapper returned by ParamGet
        # detaches its observers when it is garbage collected.
        group = prefs()
        group.Attach(observer)
        _state["pref_observer"] = observer
        _state["pref_group"] = group

    if is_enabled():
        set_enabled(True)
    _state["installed"] = True
