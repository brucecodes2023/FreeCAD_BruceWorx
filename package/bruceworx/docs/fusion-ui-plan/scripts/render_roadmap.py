"""Roadmap example figures, built in headless FreeCAD and rendered to ../fig.

    build/release/bin/FreeCADCmd package/bruceworx/docs/fusion-ui-plan/scripts/render_roadmap.py

Every model here is real FreeCAD geometry. Numbers quoted in the roadmap
(cut list, interference volume, flat length, mass and CG) are printed as
``FACT`` lines so the document can be checked against this script.
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import FreeCAD as App
import Part

from bwrender import COL_BASE, COL_GHOST, COL_INST, COL_SEED, V, render  # noqa: E402

RED = (215, 70, 60)
GREEN = (80, 160, 110)


def fact(key, value):
    print(f"FACT {key} = {value}")


# --------------------------------------------------------------------------
# Configurations: one PartDesign body, three VarSet value sets.
def configurations(doc):
    vs = doc.addObject("App::VarSet", "Config")
    vs.addProperty("App::PropertyLength", "Length", "Bracket")
    vs.addProperty("App::PropertyLength", "Height", "Bracket")
    body = doc.addObject("PartDesign::Body", "Bracket")
    base = body.newObject("PartDesign::AdditiveBox", "Base")
    base.Width, base.Height = 30, 5
    base.setExpression("Length", "Config.Length")
    wall = body.newObject("PartDesign::AdditiveBox", "Wall")
    wall.Length, wall.Width = 5, 30
    wall.setExpression("Height", "Config.Height")
    hole = body.newObject("PartDesign::SubtractiveCylinder", "Hole")
    hole.Radius, hole.Height = 3, 20
    hole.Placement = App.Placement(V(0, 15, -5), App.Rotation())
    hole.setExpression("Placement.Base.x", "Config.Length - 12 mm")
    body.Tip = hole
    items, configs = [], [("Short", 40, 25), ("Standard", 60, 35), ("Long", 90, 50)]
    x = 0.0
    for i, (name, length, height) in enumerate(configs):
        vs.Length, vs.Height = length, height
        doc.recompute()
        s = body.Shape.copy()
        fact(f"config_{name}_volume_mm3", round(s.Volume, 1))
        s.translate(V(x, 0, 0))
        items.append((s, (COL_SEED, COL_INST, GREEN)[i], 1.0, True))
        x += length + 25
    render("cfg_bracket", items, size=(1400, 600), az=-62, el=28)


# --------------------------------------------------------------------------
# Direct edit on a dumb solid: STEP round-trip, then Defeaturing (exists today).
def direct_edit(doc):
    blk = Part.makeBox(100, 50, 20)
    blk = blk.cut(Part.makeCylinder(6, 40, V(14, 25, -10)))
    blk = blk.cut(Part.makeCylinder(6, 40, V(86, 25, -10)))
    blk = blk.cut(Part.makeBox(36, 24, 10, V(32, 13, 10)))
    blk = blk.makeFillet(3, [e for e in blk.Edges if abs(e.Length - 20) < 1e-6 and e.Curve.__class__.__name__ == "Line"])
    path = os.path.join(App.getTempPath(), "bw_direct_edit.step")
    blk.exportStep(path)
    dumb = Part.read(path)
    fact("step_roundtrip_faces", len(dumb.Faces))
    # Faces of the right-hand hole: cylindrical, axis through x=60.
    target = [f for f in dumb.Faces
              if f.Surface.__class__.__name__ == "Cylinder" and abs(f.Surface.Center.x - 86) < 1e-6
              and abs(f.Surface.Radius - 6) < 1e-6]
    after = dumb.defeaturing(target)
    fact("defeaturing_faces_before_after", f"{len(dumb.Faces)} -> {len(after.Faces)}")
    fact("defeaturing_valid", after.isValid())
    before_items = [(dumb, COL_BASE, 1.0, True)] + [(f, RED, 1.0, False) for f in target]
    after_shape = after.copy()
    after_shape.translate(V(130, 0, 0))
    render("direct_edit", before_items + [(after_shape, COL_INST, 1.0, True)], size=(1400, 560), az=-58, el=34)


# --------------------------------------------------------------------------
# Frame / weldment: 45-degree mitred top frame (trapezoid members) + butt legs.
def frame(doc):
    L, W, w, h = 300.0, 200.0, 20.0, 260.0
    members, cut = [], []

    def trapezoid(p0, p1, inward):
        """Mitred member along p0->p1 (outer edge), width w toward `inward`."""
        d = (p1 - p0)
        d.normalize()
        q0 = p0 + inward * w + d * w
        q1 = p1 + inward * w - d * w
        wire = Part.makePolygon([p0, p1, q1, q0, p0])
        return Part.Face(wire).extrude(V(0, 0, w))

    corners = [V(0, 0, h), V(L, 0, h), V(L, W, h), V(0, W, h)]
    inward = [V(0, 1, 0), V(-1, 0, 0), V(0, -1, 0), V(1, 0, 0)]
    for i in range(4):
        m = trapezoid(corners[i], corners[(i + 1) % 4], inward[i])
        members.append((m, COL_INST if i % 2 == 0 else COL_SEED, 1.0, True))
        outer = (corners[(i + 1) % 4] - corners[i]).Length
        cut.append((f"top-{i + 1}", outer, outer - 2 * w, "45/45"))
    for c, (sx, sy) in zip(corners, [(0, 0), (-w, 0), (-w, -w), (0, -w)]):
        leg = Part.makeBox(w, w, h, V(c.x + sx, c.y + sy, 0))
        members.append((leg, COL_BASE, 1.0, True))
        cut.append(("leg", h, h, "0/0"))
    solids = [m[0] for m in members]
    fused = solids[0].fuse(solids[1:])
    fact("frame_is_valid", fused.isValid())
    for name, outer, inner, ang in cut:
        fact(f"cutlist_{name}", f"outer {outer:.0f} mm, inner {inner:.0f} mm, ends {ang}")
    render("frame_weldment", members, size=(1400, 900), az=-55, el=24)


# --------------------------------------------------------------------------
# Interference: a bolt that is 4 mm too long into a blind tapped hole.
def interference(doc):
    plate = Part.makeBox(60, 40, 10)
    block = Part.makeBox(60, 40, 20, V(0, 0, -20))
    block = block.cut(Part.makeCylinder(2.5, 12, V(30, 20, -12)))  # blind hole, 12 deep
    plate = plate.cut(Part.makeCylinder(3.2, 20, V(30, 20, -5)))
    head = Part.Face(Part.makePolygon([V(30 + 5.5 * math.cos(math.pi / 3 * k), 20 + 5.5 * math.sin(math.pi / 3 * k), 10)
                                       for k in range(7)])).extrude(V(0, 0, 4))
    shank = Part.makeCylinder(2.5, 26, V(30, 20, -16))  # 26 long: 10 plate + 16 into a 12 deep hole
    bolt = head.fuse(shank).removeSplitter()
    clash = bolt.common(block)
    fact("interference_volume_mm3", round(clash.Volume, 2))
    fact("interference_depth_mm", round(clash.BoundBox.ZMax - clash.BoundBox.ZMin, 2))
    # Half-section through the bolt axis (keep y >= 20) so the clash is visible.
    keep = Part.makeBox(200, 100, 200, V(-50, 20, -100))
    items = [(block.common(keep), COL_GHOST, 1.0, True), (plate.common(keep), COL_BASE, 1.0, True),
             (bolt.common(keep), COL_INST, 1.0, True), (clash.common(keep), RED, 1.0, True)]
    render("interference", items, size=(1100, 900), az=-75, el=12)


# --------------------------------------------------------------------------
# Sheet metal: 90-degree bracket and its flat pattern (bend allowance, K-factor).
def sheet_metal(doc):
    T, R, K, A, B, D = 1.5, 2.0, 0.44, 40.0, 30.0, 30.0  # thickness, inner radius, K, flange lengths, depth
    theta = math.pi / 2
    BA = theta * (R + K * T)
    flat_len = (A - (R + T)) + (B - (R + T)) + BA  # A, B measured to the outside mould lines
    fact("bend_allowance_mm", round(BA, 3))
    fact("flat_length_mm", round(flat_len, 3))
    a = A - (R + T)
    b = B - (R + T)
    # Flange 1 along +X on the XY plane, bend about an axis parallel to Y, flange 2 up +Z.
    f1 = Part.makeBox(a, D, T)
    outer = Part.makeCylinder(R + T, D, V(a, 0, R + T), V(0, 1, 0), 90)
    inner = Part.makeCylinder(R, D, V(a, 0, R + T), V(0, 1, 0), 90)
    f2 = Part.makeBox(T, D, b, V(a + R, 0, R + T))
    expected = (a + b) * D * T + math.pi / 4 * ((R + T) ** 2 - R ** 2) * D
    # The segment's start angle depends on makeCylinder's local axes; keep the
    # quadrant that joins both flanges into one solid of the expected volume.
    for quarter in range(4):
        bend = outer.cut(inner)
        bend.rotate(V(a, 0, R + T), V(0, 1, 0), 90 * quarter)
        part = f1.fuse([bend, f2]).removeSplitter()
        if len(part.Solids) == 1 and abs(part.Volume - expected) < 1e-3 * expected:
            break
    fact("bent_solids_volume_check", f"{len(part.Solids)} solid, {part.Volume:.1f} vs {expected:.1f} mm3")
    fact("bent_bbox_mm", f"{part.BoundBox.XLength:.2f} x {part.BoundBox.YLength:.2f} x {part.BoundBox.ZLength:.2f}")
    flat = Part.makeBox(flat_len, D, T, V(0, D + 25, 0))
    lines = []
    for x in (a, a + BA):
        lines.append(Part.makeLine(V(x, D + 25, T + 0.01), V(x, 2 * D + 25, T + 0.01)))
    items = [(part, COL_INST, 1.0, True), (flat, COL_SEED, 1.0, True)]
    items += [(Part.Face(Part.makePolygon([V(x - 0.25, D + 25, T + 0.02), V(x + 0.25, D + 25, T + 0.02),
                                           V(x + 0.25, 2 * D + 25, T + 0.02), V(x - 0.25, 2 * D + 25, T + 0.02),
                                           V(x - 0.25, D + 25, T + 0.02)])), RED, 1.0, False)
              for x in (a, a + BA)]
    render("sheet_flat", items, size=(1300, 900), az=-60, el=40)


# --------------------------------------------------------------------------
# Mass / CG: quad X-frame with COTS-style masses, combined CG marker.
def mass_cg(doc):
    rho_cf = 1.6e-3  # g/mm^3, carbon plate
    parts = []
    plate = Part.makeBox(80, 80, 3, V(-40, -40, 0))
    parts.append(("plate", plate, plate.Volume * rho_cf, COL_BASE))
    for k in range(4):
        ang = 45 + 90 * k
        arm = Part.makeBox(110, 14, 4, V(0, -7, 0))
        arm.rotate(V(0, 0, 0), V(0, 0, 1), ang)
        parts.append((f"arm{k}", arm, arm.Volume * rho_cf, COL_INST))
        cx, cy = 115 * math.cos(math.radians(ang)), 115 * math.sin(math.radians(ang))
        motor = Part.makeCylinder(14, 18, V(cx, cy, 4))
        parts.append((f"motor{k}", motor, 32.0, COL_SEED))  # COTS override: 32 g (2207-class)
    batt = Part.makeBox(70, 35, 30, V(-30, -17.5, -30))
    parts.append(("battery", batt, 190.0, GREEN))  # COTS override, offset forward
    total = sum(m for _, _, m, _ in parts)
    cg = V(0, 0, 0)
    for _, s, m, _ in parts:
        cg += s.CenterOfMass * m
    cg = cg * (1.0 / total)
    fact("mass_total_g", round(total, 1))
    fact("cg_mm", f"({cg.x:.2f}, {cg.y:.2f}, {cg.z:.2f})")
    items = [(s, col, 1.0, True) for _, s, _, col in parts]
    # Plumb line through the CG, with a marker above the frame.
    items.append((Part.makeCylinder(1.6, 95, V(cg.x, cg.y, cg.z - 40)), RED, 1.0, False))
    items.append((Part.makeSphere(6, V(cg.x, cg.y, cg.z + 55)), RED, 1.0, False))
    render("mass_cg", items, size=(1300, 850), az=-35, el=32)


doc = App.newDocument("RoadmapFigures")
configurations(doc)
direct_edit(doc)
frame(doc)
interference(doc)
sheet_metal(doc)
mass_cg(doc)
print("done")
