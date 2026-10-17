# SPDX-License-Identifier: LGPL-2.1-or-later
"""Open the prototype dock inside FreeCAD and save a screenshot.

Headless display::

    xvfb-run -a freecad -M /path/to/HistoryTimeline tests/grab_prototype.py

The picture is written to docs/mock/prototype-freecad.png. This is optional
evidence next to the offscreen design mocks. The data-access proof is
tests/test_timeline_access.py, which does not need a GUI.
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import FreeCAD as App
import FreeCADGui as Gui

OUT = os.path.join(ROOT, "docs", "mock", "prototype-freecad.png")


def _build():
    doc = App.newDocument("TimelinePrototype")
    body = doc.addObject("PartDesign::Body", "Bracket")
    doc.recompute()
    box = doc.addObject("PartDesign::AdditiveBox", "Stock")
    box.Length = 40
    box.Width = 20
    box.Height = 10
    body.addObject(box)
    cylinder = doc.addObject("PartDesign::AdditiveCylinder", "Boss")
    cylinder.Radius = 6
    cylinder.Height = 12
    body.addObject(cylinder)
    sphere = doc.addObject("PartDesign::AdditiveSphere", "Knob")
    sphere.Radius = 8
    body.addObject(sphere)
    doc.recompute()
    return body


def _grab():
    from history_timeline.dock import DOCK_OBJECT_NAME, install, set_enabled
    from history_timeline.qtcompat import load_qt

    _QtCore, QtGui, QtWidgets = load_qt()
    window = Gui.getMainWindow()
    window.resize(1280, 820)
    window.show()
    install()
    set_enabled(True)
    view = Gui.ActiveDocument.ActiveView if Gui.ActiveDocument else None
    body = App.ActiveDocument.getObject("Bracket")
    if view is not None and body is not None:
        try:
            view.setActiveObject("pdbody", body)
        except Exception as exc:
            App.Console.PrintWarning(f"setActiveObject failed: {exc}\n")
    QtWidgets.QApplication.processEvents()
    dock = window.findChild(QtWidgets.QDockWidget, DOCK_OBJECT_NAME)
    if dock is None:
        print("NO_DOCK", flush=True)
        window.grab().save(OUT)
    else:
        # Include a strip of the main window above the dock so the shot shows
        # the bar sitting on the bottom of FreeCAD, not as a loose widget.
        dock_geo = dock.geometry()
        full = window.grab()
        top = max(0, dock_geo.top() - 80)
        crop = full.copy(0, top, full.width(), full.height() - top)
        crop.save(OUT)
        print(f"SAVED_DOCK {OUT} {crop.width()}x{crop.height()}", flush=True)
    os._exit(0)


def main():
    _build()
    from history_timeline.qtcompat import load_qt

    QtCore, _QtGui, _QtWidgets = load_qt()
    # Let InitGui's install() land, then grab.
    QtCore.QTimer.singleShot(1200, _grab)


main()
