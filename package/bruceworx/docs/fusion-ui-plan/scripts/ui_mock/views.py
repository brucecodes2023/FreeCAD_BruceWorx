"""Render the 3D content for the UI mock: a bracket and a hinge, transparent background."""
import os, traceback
import FreeCAD as App, FreeCADGui as Gui
import Part
from PySide import QtCore, QtWidgets

OUT = os.environ["BW_MOCK_OUT"]  # set by render.sh
log = open(os.path.join(OUT, "views.log"), "w")


def say(*a):
    log.write(" ".join(str(x) for x in a) + "\n")
    log.flush()


V = App.Vector


def bracket():
    base = Part.makeBox(90, 60, 8)
    up = Part.makeBox(90, 8, 52, V(0, 52, 0))
    gusset_pts = [V(0, 52, 8), V(0, 22, 8), V(0, 52, 38), V(0, 52, 8)]
    gw = Part.Face(Part.makePolygon(gusset_pts)).extrude(V(6, 0, 0))
    g1 = gw.copy(); g1.translate(V(4, 0, 0))
    g2 = gw.copy(); g2.translate(V(80, 0, 0))
    s = base.fuse([up, g1, g2]).removeSplitter()
    holes = [Part.makeCylinder(4.5, 20, V(x, y, -5)) for x in (24, 66) for y in (16, 38)]
    holes += [Part.makeCylinder(5, 20, V(x, 45, 32), V(0, 1, 0)) for x in (30, 60)]
    s = s.cut(holes)
    # round the four vertical corners of the base plate
    corners = [e for e in s.Edges
               if abs(e.Length - 8) < 1e-6 and abs(abs(e.tangentAt(e.FirstParameter).z) - 1) < 1e-6
               and e.Vertexes[0].Point.y < 1e-6]
    if corners:
        s = s.makeFillet(5, corners)
    return s


def style(obj, color=(0.78, 0.80, 0.83)):
    vo = obj.ViewObject
    vo.ShapeAppearance = [App.Material(DiffuseColor=color)]
    vo.LineColor = (0.12, 0.12, 0.14)
    vo.LineWidth = 1.5


def save(name, w=2400, h=1500):
    v = Gui.ActiveDocument.ActiveView
    v.saveImage(os.path.join(OUT, name), w, h, "Transparent")
    say("saved", name)


state = {"step": 0}


def step():
    try:
        s = state["step"]
        state["step"] += 1
        if s == 0:
            doc = App.newDocument("Bracket")
            o = doc.addObject("Part::Feature", "Bracket")
            o.Shape = bracket()
            doc.recompute()
            style(o)
            v = Gui.ActiveDocument.ActiveView
            v.viewIsometric()
            v.setCameraType("Perspective")
            Gui.SendMsgToActiveView("ViewFit")
            cam = v.getCameraNode()
            # Leave room: zoom out a little so the part sits in the middle of the viewport
            cam.scaleHeight(1.35) if hasattr(cam, "scaleHeight") else None
            save("view-part.png")
            # The same part with one face highlighted (the fillet preview in the mock)
            Gui.Selection.addSelection("Bracket", "Bracket", "Face1")
            save("view-part-sel.png")
            Gui.Selection.clearSelection()
        elif s == 1:
            doc = App.newDocument("Hinge")
            frame = doc.addObject("Part::Feature", "Frame")
            frame.Shape = Part.makeBox(60, 10, 80)
            door = doc.addObject("Part::Feature", "Door")
            d = Part.makeBox(50, 4, 70)
            d.Placement = App.Placement(V(0, -4, 5), App.Rotation())
            d.rotate(V(0, 0, 0), V(0, 0, 1), 35)
            d.translate(V(60, 10, 0))
            door.Shape = d
            doc.recompute()
            style(frame, (0.62, 0.66, 0.72))
            style(door, (0.80, 0.82, 0.85))
            v = Gui.ActiveDocument.ActiveView
            v.viewIsometric()
            v.setCameraType("Perspective")
            Gui.SendMsgToActiveView("ViewFit")
            save("view-hinge.png")
        else:
            timer.stop()
            for name in list(App.listDocuments()):
                App.closeDocument(name)
            QtWidgets.QApplication.quit()
    except Exception:
        say(traceback.format_exc())
        timer.stop()
        QtWidgets.QApplication.quit()


timer = QtCore.QTimer()
timer.timeout.connect(step)
timer.start(3000)
