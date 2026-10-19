"""Build pattern examples in headless FreeCAD and render them to ../fig.

    build/release/bin/FreeCADCmd package/bruceworx/docs/fusion-ui-plan/scripts/render_patterns.py
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import FreeCAD as App
import Part

from bwrender import COL_BASE, COL_GHOST, COL_INST, COL_SEED, V, render  # noqa: E402


def solid_of(doc, obj):
    doc.recompute()
    return obj.Shape


# --------------------------------------------------------------------------
# 1. Feature rectangular pattern: PartDesign LinearPattern with Direction2.
def rect_feature(doc):
    body = doc.addObject("PartDesign::Body", "Plate")
    box = body.newObject("PartDesign::AdditiveBox", "Stock")
    box.Length, box.Width, box.Height = 120, 80, 8
    hole = body.newObject("PartDesign::SubtractiveCylinder", "Hole")
    hole.Radius, hole.Height = 5, 30
    hole.Placement = App.Placement(V(15, 15, -10), App.Rotation())
    pat = body.newObject("PartDesign::LinearPattern", "RectPattern")
    pat.Originals = [hole]
    pat.Direction = (body.Origin.OriginFeatures[0], [""])
    pat.Direction2 = (body.Origin.OriginFeatures[1], [""])
    pat.Mode = "Spacing"
    pat.Offset = 30
    pat.Occurrences = 4
    pat.Mode2 = "Spacing"
    pat.Offset2 = 25
    pat.Occurrences2 = 3
    # Work around Spacings2 defaulting to [0.0] (see plan, Phase 0).
    pat.Spacings2 = [-1.0, -1.0]
    body.Tip = pat
    doc.recompute()
    if not pat.Shape.isValid() or pat.Shape.isNull():
        raise RuntimeError("LinearPattern failed")
    shp = pat.Shape
    # Highlight seed and instance bores as thin rings on top for readability.
    rings = []
    for i in range(4):
        for j in range(3):
            c = V(15 + 30 * i, 15 + 25 * j, 8.01)
            ring = Part.Face(Part.Wire(Part.makeCircle(7.5, c))).cut(
                Part.Face(Part.Wire(Part.makeCircle(5, c))))
            rings.append((ring, COL_SEED if (i, j) == (0, 0) else COL_INST, 1.0, False))
    render("rect_feature", [(shp, COL_BASE, 1.0, True)] + rings)
    return pat


# 2. Feature circular pattern: flange with 8 bolt holes (PolarPattern).
def circ_feature(doc):
    body = doc.addObject("PartDesign::Body", "Flange")
    disc = body.newObject("PartDesign::AdditiveCylinder", "Disc")
    disc.Radius, disc.Height = 60, 10
    boss = body.newObject("PartDesign::AdditiveCylinder", "Hub")
    boss.Radius, boss.Height = 25, 30
    bore = body.newObject("PartDesign::SubtractiveCylinder", "Bore")
    bore.Radius, bore.Height = 15, 80
    bore.Placement = App.Placement(V(0, 0, -20), App.Rotation())
    hole = body.newObject("PartDesign::SubtractiveCylinder", "BoltHole")
    hole.Radius, hole.Height = 5, 40
    hole.Placement = App.Placement(V(45, 0, -10), App.Rotation())
    pat = body.newObject("PartDesign::PolarPattern", "CircPattern")
    pat.Originals = [hole]
    pat.Axis = (body.Origin.OriginFeatures[2], [""])
    pat.Angle = 360
    pat.Occurrences = 8
    body.Tip = pat
    doc.recompute()
    rings = []
    for k in range(8):
        t = 2 * math.pi * k / 8
        c = V(45 * math.cos(t), 45 * math.sin(t), 10.01)
        ring = Part.Face(Part.Wire(Part.makeCircle(7.5, c))).cut(
            Part.Face(Part.Wire(Part.makeCircle(5, c))))
        rings.append((ring, COL_SEED if k == 0 else COL_INST, 1.0, False))
    render("circ_feature", [(pat.Shape, COL_BASE, 1.0, True)] + rings, az=-60, el=38)
    return pat.Shape


# 3. Body pattern: link array of a bracket body (Draft ortho array, use_link).
def body_pattern(doc):
    import Draft

    bracket = Part.makeBox(30, 20, 4)
    bracket = bracket.fuse(Part.makeBox(4, 20, 24)).removeSplitter()
    bracket = bracket.cut(Part.makeCylinder(3, 10, V(17, 10, -2)))
    seed = doc.addObject("Part::Feature", "Bracket")
    seed.Shape = bracket
    arr = Draft.make_ortho_array(seed, v_x=V(45, 0, 0), v_y=V(0, 35, 0), v_z=V(0, 0, 0),
                                 n_x=3, n_y=2, n_z=1, use_link=True)
    doc.recompute()
    items = []
    for i in range(3):
        for j in range(2):
            s = bracket.copy()
            s.translate(V(45 * i, 35 * j, 0))
            items.append((s, COL_SEED if (i, j) == (0, 0) else COL_INST, 1.0, True))
    print("link array elements:", arr.Count if hasattr(arr, "Count") else "?",
          "ExpandArray" in arr.PropertiesList)
    render("body_pattern", items, az=-55, el=32)


# 4. Component pattern: bolts (separate parts) around the flange, linked.
def component_pattern(doc, flange):
    head = Part.makeCylinder(8, 6, V(0, 0, 0))
    hexhead = Part.makePolygon([V(8.5 * math.cos(math.pi / 3 * k), 8.5 * math.sin(math.pi / 3 * k), 0)
                                for k in range(7)])
    head = Part.Face(hexhead).extrude(V(0, 0, 6))
    shank = Part.makeCylinder(4.6, 30, V(0, 0, -24))
    bolt = head.fuse(shank).removeSplitter()
    items = [(flange, COL_GHOST, 0.55, True)]
    for k in range(8):
        t = 360.0 * k / 8
        b = bolt.copy()
        b.translate(V(45, 0, 10))
        b.rotate(V(0, 0, 0), V(0, 0, 1), t)
        items.append((b, COL_SEED if k == 0 else COL_INST, 1.0, True))
    render("component_pattern", items, az=-60, el=38)


# 5. Proposed: instance suppression and symmetric direction (index-set view).
def suppression(doc):
    plate = Part.makeBox(150, 90, 6)
    items = []
    supp = {(1, 1), (2, 1), (4, 0)}
    holes = []
    for i in range(5):
        for j in range(3):
            if (i, j) not in supp:
                holes.append(Part.makeCylinder(5, 20, V(15 + 30 * i, 15 + 30 * j, -5)))
    plate = plate.cut(Part.makeCompound(holes))
    items.append((plate, COL_BASE, 1.0, True))
    for i in range(5):
        for j in range(3):
            c = V(15 + 30 * i, 15 + 30 * j, 6.01)
            if (i, j) in supp:
                disc = Part.Face(Part.Wire(Part.makeCircle(5, c)))
                items.append((disc, (210, 60, 60), 0.35, True))
            else:
                ring = Part.Face(Part.Wire(Part.makeCircle(7.5, c))).cut(
                    Part.Face(Part.Wire(Part.makeCircle(5, c))))
                items.append((ring, COL_SEED if (i, j) == (0, 0) else COL_INST, 1.0, False))
    render("suppression", items, az=-50, el=40)


def symmetric(doc):
    plate = Part.makeBox(160, 40, 6, V(-80, -20, 0))
    holes, items = [], []
    for i in range(-2, 3):
        holes.append(Part.makeCylinder(5, 20, V(30 * i, 0, -5)))
    plate = plate.cut(Part.makeCompound(holes))
    items.append((plate, COL_BASE, 1.0, True))
    for i in range(-2, 3):
        c = V(30 * i, 0, 6.01)
        ring = Part.Face(Part.Wire(Part.makeCircle(7.5, c))).cut(
            Part.Face(Part.Wire(Part.makeCircle(5, c))))
        items.append((ring, COL_SEED if i == 0 else COL_INST, 1.0, False))
    render("symmetric", items, size=(1400, 600), az=-70, el=35)


doc = App.newDocument("PlanFigures")
rect_feature(doc)
fl = circ_feature(doc)
body_pattern(doc)
component_pattern(doc, fl)
suppression(doc)
symmetric(doc)
print("done")
