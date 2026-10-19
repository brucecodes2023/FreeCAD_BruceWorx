"""Capture the real build's window on the four mock screens (run inside FreeCAD by capture.sh).

Writes <OUT>/<screen>.png (window grab) and <screen>-3d.png (the 3D view, which a
window grab leaves blank) plus <screen>.json with where the 3D view sits, so
capture.sh can paste one into the other.
"""

import json
import os
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

OUT = os.environ["BW_CAPTURE_OUT"]
log = open(os.path.join(OUT, "capture.log"), "w")
V = App.Vector


def say(*a):
    log.write(" ".join(str(x) for x in a) + "\n")
    log.flush()


mw = Gui.getMainWindow()


def view_widget():
    best = None
    for w in mw.findChildren(QtWidgets.QWidget):
        name = w.metaObject().className()
        if ("Quarter" in name or "OpenGL" in name) and w.isVisible():
            if best is None or w.width() * w.height() > best.width() * best.height():
                best = w
    return best


def grab(name):
    QtWidgets.QApplication.processEvents()
    mw.grab().save(os.path.join(OUT, name + ".png"))
    geo = None
    w = view_widget()
    if w is not None and Gui.ActiveDocument is not None:
        p = w.mapTo(mw, QtCore.QPoint(0, 0))
        dpr = w.devicePixelRatioF()
        Gui.ActiveDocument.ActiveView.saveImage(
            os.path.join(OUT, name + "-3d.png"), int(w.width() * dpr), int(w.height() * dpr), "Transparent")
        # Also with the real background: translucent things (grid lines) only look
        # right against it.
        Gui.ActiveDocument.ActiveView.saveImage(
            os.path.join(OUT, name + "-3dbg.png"), int(w.width() * dpr), int(w.height() * dpr), "Current")
        geo = {"x": p.x() * dpr, "y": p.y() * dpr, "w": w.width() * dpr, "h": w.height() * dpr}
    # Panels floating over the 3D view (overlay cards) stay on top when the
    # 3D render is pasted in, so record where they are.
    panels = []
    for w in mw.findChildren(QtWidgets.QWidget):
        if w.metaObject().className() == "Gui::OverlayTabWidget" and w.isVisible():
            p = w.mapTo(mw, QtCore.QPoint(0, 0))
            dpr = w.devicePixelRatioF()
            panels.append([p.x() * dpr, p.y() * dpr, w.width() * dpr, w.height() * dpr])
    with open(os.path.join(OUT, name + ".json"), "w") as f:
        json.dump({"view": geo, "panels": panels}, f)
    say("grab", name, geo)


def sketch_outline(sk):
    import Part
    import Sketcher
    pts = [V(0, 0, 0), V(90, 0, 0), V(90, 60, 0), V(0, 60, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]), False)
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    sk.addConstraint(Sketcher.Constraint("Horizontal", 0))
    sk.addConstraint(Sketcher.Constraint("Horizontal", 2))
    sk.addConstraint(Sketcher.Constraint("Vertical", 1))
    sk.addConstraint(Sketcher.Constraint("Vertical", 3))
    sk.addConstraint(Sketcher.Constraint("Coincident", 0, 1, -1, 1))
    sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 90))
    sk.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, 60))
    first = None
    for x, y in ((24, 16), (66, 16), (24, 38), (66, 38)):
        g = sk.addGeometry(Part.Circle(V(x, y, 0), V(0, 0, 1), 4.5), False)
        if first is None:
            first = g
            sk.addConstraint(Sketcher.Constraint("Diameter", g, 9))
            sk.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, g, 3, x))
            sk.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, g, 3, y))
        else:
            sk.addConstraint(Sketcher.Constraint("Equal", first, g))


def make_bracket():
    doc = App.newDocument("Bracket")
    body = doc.addObject("PartDesign::Body", "Body")
    xy = [f for f in body.Origin.OriginFeatures if f.Role == "XY_Plane"][0]
    sk = body.newObject("Sketcher::SketchObject", "Sketch")
    sk.Label = "Base outline"
    sk.AttachmentSupport = [(xy, "")]
    sk.MapMode = "FlatFace"
    sketch_outline(sk)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Label = "Base plate"
    pad.Profile = sk
    pad.Length = 8
    doc.recompute()
    up = body.newObject("PartDesign::AdditiveBox", "Box")
    up.Label = "Upright"
    up.Length, up.Width, up.Height = 90, 8, 52
    up.Placement = App.Placement(V(0, 52, 0), App.Rotation())
    doc.recompute()
    corners = []
    for i, e in enumerate(up.Shape.Edges):
        d = e.Vertexes[-1].Point - e.Vertexes[0].Point
        if abs(e.Length - 8) < 1e-6 and abs(abs(d.z) - 8) < 1e-6 and e.Vertexes[0].Point.y < 1e-6:
            corners.append("Edge%d" % (i + 1))
    fil = body.newObject("PartDesign::Fillet", "Fillet")
    fil.Label = "Corner fillet"
    fil.Base = (up, corners)
    fil.Radius = 5
    doc.recompute()
    say("bracket", body.Shape.isValid(), corners)
    return doc, body, sk, fil


state = {"step": 0}


def step():
    try:
        s = state["step"]
        state["step"] += 1
        if s == 0:
            mw.resize(1600, 1000)
            mw.show()
        elif s == 1:
            grab("start")
        elif s == 2:
            Gui.activateWorkbench("PartDesignWorkbench")
            doc, body, sk, fil = make_bracket()
            state.update(doc=doc, sk=sk, fil=fil)
            v = Gui.ActiveDocument.ActiveView
            v.viewIsometric()
            Gui.SendMsgToActiveView("ViewFit")
            Gui.ActiveDocument.setEdit(fil)
        elif s == 3:
            grab("part")
            Gui.Control.closeDialog()
            Gui.ActiveDocument.resetEdit()
        elif s == 4:
            Gui.ActiveDocument.setEdit(state["sk"])
        elif s == 5:
            grab("sketch")
            Gui.ActiveDocument.resetEdit()
        elif s == 6:
            import JointObject
            Gui.activateWorkbench("AssemblyWorkbench")
            doc = App.newDocument("Hinge")
            asm = doc.addObject("Assembly::AssemblyObject", "Assembly")
            jg = asm.newObject("Assembly::JointGroup", "Joints")
            base = asm.newObject("Part::Box", "Frame")
            base.Length, base.Width, base.Height = 60, 10, 80
            door = asm.newObject("Part::Box", "Door")
            door.Length, door.Width, door.Height = 50, 4, 70
            door.Placement = App.Placement(V(80, 30, 5), App.Rotation(30, 0, 0))
            doc.recompute()
            g = jg.newObject("App::FeaturePython", "GroundedJoint")
            JointObject.GroundedJoint(g, base)
            JointObject.ViewProviderGroundedJoint(g.ViewObject)
            Gui.activeDocument().activeView().viewIsometric()
            Gui.ActiveDocument.setEdit(asm)
            state.update(base=base, door=door)
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection("Hinge", "Assembly", "Frame.Edge7")
            Gui.Selection.addSelection("Hinge", "Assembly", "Door.Edge1")
            panel = JointObject.TaskAssemblyCreateJoint(1)
            Gui.Control.showDialog(panel)
            panel.jForm.limitCheckbox3.setChecked(True)
            panel.jForm.limitCheckbox4.setChecked(True)
            panel.jForm.limitRotMaxSpinbox.setProperty("rawValue", 110.0)
            j = panel.joint
            j.LimitDatum1 = [base, ["Face4", "Face4"]]
            j.LimitDatum2 = [door, ["Face4", "Face4"]]
            import UtilsAssembly
            plc1 = UtilsAssembly.getJcsGlobalPlc(j.Placement1, j.Reference1)
            axis = plc1.Rotation.multVec(V(0, 0, 1))
            reading = JointObject.limitReading(j)[0]
            door.Placement = App.Placement(V(), App.Rotation(axis, 35 - reading), plc1.Base) * door.Placement
            panel.assembly.solve()
            panel.updateLimitDatumInfo()
            Gui.SendMsgToActiveView("ViewFit")
        elif s == 7:
            grab("asm")
        else:
            timer.stop()
            try:
                Gui.Control.closeDialog()
            except Exception:
                pass
            for name in list(App.listDocuments()):
                App.closeDocument(name)
            say("done")
            QtWidgets.QApplication.quit()
    except Exception:
        say(traceback.format_exc())
        timer.stop()
        QtWidgets.QApplication.quit()


timer = QtCore.QTimer()
timer.timeout.connect(step)
timer.start(2500)
