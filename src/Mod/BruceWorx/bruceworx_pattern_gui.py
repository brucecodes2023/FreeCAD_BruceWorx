# SPDX-License-Identifier: LGPL-2.1-or-later
"""Rectangular / Circular Pattern commands and task panel (BW-MOD-01).

* PartDesign features selected: hand over to PartDesign_LinearPattern or
  PartDesign_PolarPattern (their own dialogs).
* Bodies, Part solids or assembly components selected: this task panel. It
  creates one linked pattern per selected object (see bruceworx_pattern) and
  updates it live; Cancel aborts the transaction, so nothing is left behind.
* An existing BruceWorx pattern selected: the same panel, editing it.

Off switch: Preferences > BruceWorx > "Rectangular and Circular Pattern
commands" (BaseApp/Preferences/BruceWorx/PatternCommands).
"""

import os

import FreeCAD as App

import bruceworx_pattern as bp

PREFS_PATH = "User parameter:BaseApp/Preferences/BruceWorx"
ENABLED_KEY = "PatternCommands"
HERE = os.path.dirname(os.path.abspath(__file__))
USER_ROLE = 256  # Qt.UserRole
COMMANDS = {
    bp.RECTANGULAR: "BruceWorx_RectangularPattern",
    bp.CIRCULAR: "BruceWorx_CircularPattern",
}
PARTDESIGN = {
    bp.RECTANGULAR: "PartDesign_LinearPattern",
    bp.CIRCULAR: "PartDesign_PolarPattern",
}

_state = {"installed": False, "manipulator": None, "observer": None, "pending": set()}


def _qt():
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide import QtCore, QtGui

        QtWidgets = QtGui
    return QtCore, QtGui, QtWidgets


def enabled():
    return bool(App.ParamGet(PREFS_PATH).GetBool(ENABLED_KEY, True))


def _warn(message):
    App.Console.PrintWarning(f"BruceWorx pattern: {message}\n")


# ---------------------------------------------------------------------------
# Selection helpers.


def _axis_from_selection():
    """``(point, direction)`` in global coordinates from the selected edge,
    circular edge (its centre and normal) or datum line; None if nothing fits."""
    import FreeCADGui as Gui

    for sel in Gui.Selection.getSelectionEx():
        for sub in sel.SubObjects:
            if sub.ShapeType != "Edge":
                continue
            curve = sub.Curve
            name = type(curve).__name__
            if name in ("Line", "LineSegment"):
                return sub.Vertexes[0].Point, App.Vector(curve.Direction)
            if name == "Circle":
                return App.Vector(curve.Center), App.Vector(curve.Axis)
        obj = sel.Object
        if obj.isDerivedFrom("App::Line") or obj.isDerivedFrom("PartDesign::Line"):
            placement = obj.getGlobalPlacement()
            if obj.isDerivedFrom("App::Line"):
                # App::Line runs along its local X axis.
                return placement.Base, placement.Rotation.multVec(App.Vector(1, 0, 0))
            edge = obj.Shape.Edges[0]
            return edge.Vertexes[0].Point, App.Vector(edge.Curve.Direction)
    return None


def _to_parent(point, direction, seed):
    """Global point/direction into the seed's parent coordinates."""
    parent = bp.parent_of(seed)
    if parent is None:
        return point, direction
    inverse = parent.getGlobalPlacement().inverse()
    return inverse.multVec(point), inverse.Rotation.multVec(direction)


# ---------------------------------------------------------------------------
# Task panel.


class PatternTaskPanel:
    """Live-preview dialog for linked body/component patterns."""

    def __init__(self, kind, seeds=None, arrays=None):
        QtCore, _QtGui, QtWidgets = _qt()
        self.QtWidgets = QtWidgets
        self.doc = App.ActiveDocument
        self.editing = bool(arrays)
        title = f"{kind} Pattern"
        self.doc.openTransaction(title)
        if arrays:
            self.arrays = list(arrays)
            params = bp.read_params(self.arrays[0])
            # Restored on Cancel even when the document has undo turned off.
            self._original = [(a.Name, bp.read_params(a)) for a in self.arrays]
        else:
            params = bp.default_params(kind)
            if kind == bp.CIRCULAR:
                params["axis_base"], params["axis_direction"] = self._default_axis(seeds[0])
            self.arrays = [bp.create_linked(seed, params, self.doc) for seed in seeds]
            self._original = []
        self.params = params
        self.custom = {"direction1": None, "direction2": None, "axis": None}
        self._building = True
        self.form = self._build(QtWidgets, title)
        self._load(params)
        self._building = False
        self._refresh_suppress_list()
        self.doc.recompute()

    # ----- construction ----------------------------------------------------

    def _default_axis(self, seed):
        """Z axis through the parent origin; the seed sits off-axis already."""
        return App.Vector(0, 0, 0), App.Vector(0, 0, 1)

    def _build(self, QtWidgets, title):
        form = QtWidgets.QWidget()
        form.setWindowTitle(title)
        layout = QtWidgets.QVBoxLayout(form)

        seeds = ", ".join(a.PatternSeed.Label for a in self.arrays if a.PatternSeed is not None)
        objects = QtWidgets.QLabel(f"<b>Objects:</b> {seeds}")
        objects.setWordWrap(True)
        layout.addWidget(objects)

        type_row = QtWidgets.QHBoxLayout()
        type_row.addWidget(QtWidgets.QLabel("Type"))
        self.kind = QtWidgets.QComboBox()
        self.kind.addItems([bp.RECTANGULAR, bp.CIRCULAR])
        type_row.addWidget(self.kind, 1)
        layout.addLayout(type_row)

        # Rectangular.
        self.rect_box = QtWidgets.QWidget()
        rect = QtWidgets.QVBoxLayout(self.rect_box)
        rect.setContentsMargins(0, 0, 0, 0)
        self.dir1 = self._direction_group(QtWidgets, "Direction 1", checkable=False)
        self.dir2 = self._direction_group(QtWidgets, "Direction 2", checkable=True)
        rect.addWidget(self.dir1["box"])
        rect.addWidget(self.dir2["box"])
        layout.addWidget(self.rect_box)

        # Circular.
        self.circ_box = QtWidgets.QGroupBox("Axis")
        grid = QtWidgets.QGridLayout(self.circ_box)
        self.axis = QtWidgets.QComboBox()
        self.axis.addItems(["Z axis", "X axis", "Y axis", "Selected edge / axis"])
        self.axis_pick = QtWidgets.QPushButton("Use selection")
        self.axis_pick.setToolTip("Select a straight edge, a circular edge (its centre), or a datum axis, then press.")
        self.circ_type = QtWidgets.QComboBox()
        self.circ_type.addItems(bp.CIRCULAR_TYPES)
        self.angle = QtWidgets.QDoubleSpinBox()
        self.angle.setRange(-3600.0, 3600.0)
        self.angle.setDecimals(3)
        self.angle.setSuffix(" °")
        self.circ_count = QtWidgets.QSpinBox()
        self.circ_count.setRange(1, 10000)
        grid.addWidget(QtWidgets.QLabel("Axis"), 0, 0)
        grid.addWidget(self.axis, 0, 1)
        grid.addWidget(self.axis_pick, 0, 2)
        grid.addWidget(QtWidgets.QLabel("Type"), 1, 0)
        grid.addWidget(self.circ_type, 1, 1, 1, 2)
        grid.addWidget(QtWidgets.QLabel("Angle"), 2, 0)
        grid.addWidget(self.angle, 2, 1, 1, 2)
        grid.addWidget(QtWidgets.QLabel("Quantity"), 3, 0)
        grid.addWidget(self.circ_count, 3, 1, 1, 2)
        layout.addWidget(self.circ_box)

        # Copies.
        copies_row = QtWidgets.QHBoxLayout()
        copies_row.addWidget(QtWidgets.QLabel("Copies"))
        self.copies = QtWidgets.QComboBox()
        self.copies.addItems(["Linked", "Independent"])
        self.copies.setToolTip(
            "Linked: one App::Link array; instances follow the source and can be edited later.\n"
            "Independent: separate solids (bodies) or separate links (components), made on OK."
        )
        copies_row.addWidget(self.copies, 1)
        layout.addLayout(copies_row)

        # Suppress.
        suppress_box = QtWidgets.QGroupBox("Instances (uncheck to suppress)")
        suppress_layout = QtWidgets.QVBoxLayout(suppress_box)
        self.instances = QtWidgets.QListWidget()
        self.instances.setMaximumHeight(160)
        suppress_layout.addWidget(self.instances)
        layout.addWidget(suppress_box)

        self.status = QtWidgets.QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch(1)

        # Signals.
        self.kind.currentIndexChanged.connect(self._changed)
        for group in (self.dir1, self.dir2):
            group["direction"].currentIndexChanged.connect(self._changed)
            group["pick"].clicked.connect(lambda _c=False, g=group: self._pick_direction(g))
            group["reverse"].toggled.connect(self._changed)
            group["type"].currentIndexChanged.connect(self._changed)
            group["distance"].valueChanged.connect(self._changed)
            group["count"].valueChanged.connect(self._changed)
            group["symmetric"].toggled.connect(self._changed)
        self.dir2["box"].toggled.connect(self._changed)
        self.axis.currentIndexChanged.connect(self._changed)
        self.axis_pick.clicked.connect(self._pick_axis)
        self.circ_type.currentIndexChanged.connect(self._changed)
        self.angle.valueChanged.connect(self._changed)
        self.circ_count.valueChanged.connect(self._changed)
        self.instances.itemChanged.connect(self._list_changed)
        return form

    def _direction_group(self, QtWidgets, title, checkable):
        box = QtWidgets.QGroupBox(title)
        box.setCheckable(checkable)
        grid = QtWidgets.QGridLayout(box)
        direction = QtWidgets.QComboBox()
        direction.addItems(["X axis", "Y axis", "Z axis", "Selected edge"])
        pick = QtWidgets.QPushButton("Use selection")
        pick.setToolTip("Select a straight edge or a datum axis, then press.")
        reverse = QtWidgets.QCheckBox("Reverse")
        kind = QtWidgets.QComboBox()
        kind.addItems(bp.DISTANCE_TYPES)
        distance = QtWidgets.QDoubleSpinBox()
        distance.setRange(0.0, 1e6)
        distance.setDecimals(3)
        distance.setSuffix(" mm")
        count = QtWidgets.QSpinBox()
        count.setRange(1, 10000)
        symmetric = QtWidgets.QCheckBox("Symmetric")
        symmetric.setToolTip("Spread the instances on both sides of the original.")
        grid.addWidget(QtWidgets.QLabel("Direction"), 0, 0)
        grid.addWidget(direction, 0, 1)
        grid.addWidget(pick, 0, 2)
        grid.addWidget(QtWidgets.QLabel("Distance type"), 1, 0)
        grid.addWidget(kind, 1, 1, 1, 2)
        grid.addWidget(QtWidgets.QLabel("Distance"), 2, 0)
        grid.addWidget(distance, 2, 1, 1, 2)
        grid.addWidget(QtWidgets.QLabel("Quantity"), 3, 0)
        grid.addWidget(count, 3, 1, 1, 2)
        grid.addWidget(reverse, 4, 1)
        grid.addWidget(symmetric, 4, 2)
        return {"box": box, "direction": direction, "pick": pick, "reverse": reverse, "type": kind,
                "distance": distance, "count": count, "symmetric": symmetric}

    # ----- params <-> widgets ---------------------------------------------

    _AXES = [App.Vector(1, 0, 0), App.Vector(0, 1, 0), App.Vector(0, 0, 1)]

    def _vector_index(self, vector):
        for index, axis in enumerate(self._AXES):
            if abs(abs(App.Vector(vector).normalize().dot(axis)) - 1.0) < 1e-9:
                return index, App.Vector(vector).dot(axis) < 0
        return 3, False

    def _load(self, params):
        self.kind.setCurrentText(params["kind"])
        for n, group in ((1, self.dir1), (2, self.dir2)):
            vector = App.Vector(params[f"direction{n}"])
            index, reverse = self._vector_index(vector)
            if index == 3:
                self.custom[f"direction{n}"] = vector
            group["direction"].setCurrentIndex(index)
            group["reverse"].setChecked(reverse)
            group["type"].setCurrentText(params[f"type{n}"])
            group["distance"].setValue(float(params[f"distance{n}"]))
            group["count"].setValue(int(params[f"count{n}"]) if n == 1 or params["count2"] > 1 else 2)
            group["symmetric"].setChecked(bool(params[f"symmetric{n}"]))
        self.dir2["box"].setChecked(params["count2"] > 1)
        vector_index, reversed_axis = self._vector_index(params["axis_direction"])
        axis_index = {0: 1, 1: 2, 2: 0, 3: 3}[vector_index]
        if axis_index == 3 or reversed_axis or App.Vector(params["axis_base"]).Length > 1e-12:
            self.custom["axis"] = (App.Vector(params["axis_base"]), App.Vector(params["axis_direction"]))
            axis_index = 3
        self.axis.setCurrentIndex(axis_index)
        self.circ_type.setCurrentText(params["circular_type"])
        self.angle.setValue(float(params["angle"]))
        self.circ_count.setValue(int(params["count1"]) if params["kind"] == bp.CIRCULAR else 6)
        self.copies.setEnabled(True)
        self._suppressed = {tuple(k) for k in params["suppressed"]}
        self._show_kind()

    def _direction(self, n, group):
        index = group["direction"].currentIndex()
        if index == 3:
            vector = self.custom[f"direction{n}"] or App.Vector(1, 0, 0)
        else:
            vector = App.Vector(self._AXES[index])
        vector = App.Vector(vector)
        if group["reverse"].isChecked():
            vector = vector * -1
        return vector

    def _gather(self):
        params = dict(self.params)
        kind = self.kind.currentText()
        params["kind"] = kind
        params["direction1"] = self._direction(1, self.dir1)
        params["direction2"] = self._direction(2, self.dir2)
        for n, group in ((1, self.dir1), (2, self.dir2)):
            params[f"type{n}"] = group["type"].currentText()
            params[f"distance{n}"] = group["distance"].value()
            params[f"symmetric{n}"] = group["symmetric"].isChecked()
        if kind == bp.RECTANGULAR:
            params["count1"] = self.dir1["count"].value()
            params["count2"] = self.dir2["count"].value() if self.dir2["box"].isChecked() else 1
        else:
            params["count1"] = self.circ_count.value()
            params["count2"] = 1
        axis_index = self.axis.currentIndex()
        if axis_index == 3 and self.custom["axis"]:
            params["axis_base"], params["axis_direction"] = self.custom["axis"]
        else:
            params["axis_base"] = App.Vector(0, 0, 0)
            params["axis_direction"] = App.Vector([self._AXES[2], self._AXES[0], self._AXES[1], self._AXES[2]][axis_index])
        params["circular_type"] = self.circ_type.currentText()
        params["angle"] = self.angle.value()
        params["suppressed"] = sorted(self._suppressed)
        return params

    def _show_kind(self):
        circular = self.kind.currentText() == bp.CIRCULAR
        self.rect_box.setVisible(not circular)
        self.circ_box.setVisible(circular)
        self.angle.setEnabled(self.circ_type.currentText() != "Full")

    # ----- live update -------------------------------------------------------

    def _changed(self, *_args):
        if self._building:
            return
        if self.sender_is_list():
            self._suppressed = set()
            for row in range(self.instances.count()):
                item = self.instances.item(row)
                if not self._is_checked(item):
                    self._suppressed.add(bp.text_to_key(item.data(USER_ROLE)))
        self._show_kind()
        params = self._gather()
        try:
            bp.transforms(params)
        except ValueError as exc:
            self.status.setText(f"<span style='color:#c0392b'>{exc}</span>")
            return
        self.status.setText("")
        self.params = params
        for array in self.arrays:
            bp.write_params(array, params)
            bp.apply(array)
        self.doc.recompute()
        if not self.sender_is_list():
            self._refresh_suppress_list()

    def sender_is_list(self):
        return getattr(self, "_from_list", False)

    @staticmethod
    def _is_checked(item):
        state = item.checkState()
        return getattr(state, "value", state) != 0

    def _refresh_suppress_list(self):
        QtCore, _QtGui, _QtWidgets = _qt()
        self.instances.blockSignals(True)
        self.instances.clear()
        params = self._gather()
        skip = bp.seed_key(params["kind"])
        keys = [k for k, _g in bp.transforms(params) if k != skip] if self._valid(params) else []
        self._suppressed = {k for k in self._suppressed if k in set(keys)}
        for key in keys:
            item = self.QtWidgets.QListWidgetItem(bp.describe_key(params, key))
            item.setData(USER_ROLE, bp.key_to_text(key))
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Unchecked if key in self._suppressed else QtCore.Qt.Checked)
            self.instances.addItem(item)
        self.instances.blockSignals(False)

    def _list_changed(self, _item):
        self._from_list = True
        try:
            self._changed()
        finally:
            self._from_list = False

    @staticmethod
    def _valid(params):
        try:
            bp.transforms(params)
            return True
        except ValueError:
            return False

    def _pick_direction(self, group):
        found = _axis_from_selection()
        if found is None:
            self.status.setText("Select a straight edge or a datum axis first.")
            return
        _point, direction = _to_parent(found[0], found[1], self.arrays[0].PatternSeed)
        n = 1 if group is self.dir1 else 2
        self.custom[f"direction{n}"] = direction
        group["direction"].setCurrentIndex(3)
        self._changed()

    def _pick_axis(self):
        found = _axis_from_selection()
        if found is None:
            self.status.setText("Select a straight edge, a circular edge or a datum axis first.")
            return
        self.custom["axis"] = _to_parent(found[0], found[1], self.arrays[0].PatternSeed)
        self.axis.setCurrentIndex(3)
        self._changed()

    # ----- task dialog API -----------------------------------------------

    def getStandardButtons(self):
        _QtCore, _QtGui, QtWidgets = _qt()
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel

    def accept(self):
        import FreeCADGui as Gui

        try:
            if self.copies.currentText() == "Independent":
                for array in list(self.arrays):
                    bp.make_independent(array)
            self.doc.commitTransaction()
        except Exception as exc:
            _warn(str(exc))
            self.doc.abortTransaction()
        Gui.Control.closeDialog()
        self.doc.recompute()
        return True

    def reject(self):
        import FreeCADGui as Gui

        self.cancel()
        Gui.Control.closeDialog()
        return True

    def cancel(self):
        """Undo everything the panel did, with or without document undo."""
        self.doc.abortTransaction()
        if self.editing:
            for name, params in self._original:
                array = self.doc.getObject(name)
                if array is not None:
                    bp.write_params(array, params)
                    bp.apply(array)
        else:
            for array in self.arrays:
                try:
                    name = array.Name
                except Exception:  # already removed by the undo
                    continue
                if self.doc.getObject(name) is not None:
                    self.doc.removeObject(name)
        self.doc.recompute()


# ---------------------------------------------------------------------------
# Commands.


class _PatternCommand:
    def __init__(self, kind):
        self.kind = kind

    def GetResources(self):
        name = COMMANDS[self.kind]
        tip = (
            f"{self.kind} Pattern. Features: uses PartDesign's {self.kind.lower()} pattern. "
            "Bodies, solids and assembly components: linked or independent copies, "
            "with symmetric directions and suppressed instances. "
            "Select an existing BruceWorx pattern to edit it."
        )
        return {
            "Pixmap": os.path.join(HERE, name + ".svg"),
            "MenuText": f"{self.kind} Pattern",
            "ToolTip": tip,
        }

    def IsActive(self):
        return App.ActiveDocument is not None and enabled()

    def Activated(self):
        import FreeCADGui as Gui

        selection = Gui.Selection.getSelection()
        patterns = [o for o in selection if bp.is_pattern(o)]
        if patterns and len(patterns) == len(selection):
            Gui.Control.showDialog(PatternTaskPanel(patterns[0].PatternType, arrays=patterns))
            return
        kind = bp.classify_selection(selection)
        if kind == "features":
            Gui.runCommand(PARTDESIGN[self.kind])
            return
        if kind == "empty":
            _message("Select a feature, a body, a solid or an assembly component first.")
            return
        if kind == "mixed":
            _message("Select either PartDesign features, or bodies / components, not both.")
            return
        unusable = [o.Label for o in selection if not _patternable(o)]
        if unusable:
            _message("These cannot be patterned: " + ", ".join(unusable))
            return
        Gui.Control.showDialog(PatternTaskPanel(self.kind, seeds=selection))


def _patternable(obj):
    if obj.isDerivedFrom("App::Link"):
        return obj.ElementCount == 0 and not bp.is_pattern(obj)
    return obj.isDerivedFrom("Part::Feature") or obj.isDerivedFrom("App::Part")


def _message(text):
    _QtCore, _QtGui, QtWidgets = _qt()
    import FreeCADGui as Gui

    QtWidgets.QMessageBox.information(Gui.getMainWindow(), "Pattern", text)


class _Manipulator:
    """Put the commands next to PartDesign's patterns and on the Assembly toolbar."""

    def modifyToolBars(self):
        if not enabled():
            return []
        items = []
        for command in COMMANDS.values():
            items.append({"insert": command, "toolItem": "PartDesign_MultiTransform"})
            items.append({"append": command, "toolBar": "Assembly"})
        return items


class _SeedObserver:
    """Re-place linked patterns when their seed moves or a pattern property is
    edited in the property view. Deferred to the event loop, outside recompute."""

    def slotChangedObject(self, obj, prop):
        try:
            if prop == "Placement" and not obj.isDerivedFrom("App::LinkElement"):
                for array in bp.patterns_of(obj):
                    _schedule(array)
            elif bp.is_pattern(obj) and prop not in ("InstanceKeys", "ElementCount", "ElementList",
                                                     "Placement", "Label", "Visibility"):
                if obj.getGroupOfProperty(prop) == bp.GROUP:
                    _schedule(obj)
        except Exception:
            pass


def _schedule(array):
    QtCore, _QtGui, _QtWidgets = _qt()
    key = (array.Document.Name, array.Name)
    if key in _state["pending"]:
        return
    _state["pending"].add(key)

    def run():
        _state["pending"].discard(key)
        doc = App.getDocument(key[0]) if key[0] in App.listDocuments() else None
        obj = doc.getObject(key[1]) if doc else None
        if obj is None or not bp.is_pattern(obj):
            return
        try:
            bp.apply(obj)
        except Exception as exc:
            _warn(f"{obj.Label}: {exc}")

    QtCore.QTimer.singleShot(0, run)


def install():
    """Register commands, toolbar placement, menu entries and the observer."""
    if _state["installed"]:
        return
    import FreeCADGui as Gui

    for kind, name in COMMANDS.items():
        Gui.addCommand(name, _PatternCommand(kind))
    manipulator = _Manipulator()
    Gui.addWorkbenchManipulator(manipulator)
    _state["manipulator"] = manipulator
    observer = _SeedObserver()
    App.addDocumentObserver(observer)
    _state["observer"] = observer
    _state["installed"] = True
    _add_menu_entries()


def _add_menu_entries():
    try:
        import FreeCADGui as Gui
        import bruceworx_menu

        _QtCore, QtGui, _QtWidgets = _qt()
        window = Gui.getMainWindow()
        for kind, name in COMMANDS.items():
            action = QtGui.QAction(QtGui.QIcon(os.path.join(HERE, name + ".svg")), f"{kind} Pattern…", window)
            action.triggered.connect(lambda _c=False, n=name: Gui.runCommand(n))
            bruceworx_menu.add_action(action, f"BruceWorxMenu_{name}")
    except Exception as exc:
        _warn(f"menu entries not added: {exc}")
