# SPDX-License-Identifier: LGPL-2.1-or-later
"""FreeCADCmd round trip for one part per file (BW-ASM-01).

Builds a small multi-body jet (fuselage, two wings, fin, a bolt used twice)
in one file, the way it would come over from Fusion, with an Assembly,
a grounded part and a fixed joint. Then:

1. make external, numbered: one part file per body plus the assembly;
2. reopen and compare every part's world shape and the joints;
3. move the whole folder and reopen (the ASM-01 acceptance test);
4. pack and go into a new folder and reopen the copy;
5. rename the parts folder, repair with resolve-refs, reopen.

Run::

    FreeCADCmd addons/BruceWorx/tests/freecad_filemodel.py

Prints ``BW_FILEMODEL PASS`` at the end; raises on the first failure.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import traceback

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

WORK = os.environ.get("BW_FILEMODEL_DIR", "/tmp/bruceworx-filemodel")
TOL = 1e-6


def build_design(path):
    import FreeCAD as App  # noqa: PLC0415
    import JointObject  # noqa: PLC0415

    doc = App.newDocument("VLJetDesign")
    sheet = doc.addObject("Spreadsheet::Sheet", "Params")
    sheet.set("A1", "120")
    sheet.setAlias("A1", "span")
    doc.recompute()

    assembly = doc.addObject("Assembly::AssemblyObject", "Assembly")
    assembly.Type = "Assembly"
    joints = assembly.newObject("Assembly::JointGroup", "Joints")

    def body(name, size, placement, span=False):
        b = doc.addObject("PartDesign::Body", name)
        assembly.addObject(b)
        box = b.newObject("PartDesign::AdditiveBox", name + "Box")
        box.Length, box.Width, box.Height = size
        if span:
            box.setExpression("Width", "Params.span")
        b.Placement = placement
        return b

    rot = App.Rotation(App.Vector(0, 0, 1), 0)
    fuselage = body("Fuselage", (300, 40, 40), App.Placement(App.Vector(0, -20, 0), rot))
    wing_l = body("WingL", (60, 120, 4), App.Placement(App.Vector(120, 20, 18), rot), span=True)
    wing_r = body("WingR", (60, 120, 4), App.Placement(App.Vector(120, -140, 18), rot), span=True)
    fin = body("Fin", (40, 3, 60), App.Placement(App.Vector(260, -1.5, 40), App.Rotation(App.Vector(0, 1, 0), 10)))
    bolt = doc.addObject("Part::Cylinder", "Bolt")
    bolt.Radius, bolt.Height = 1.5, 12
    bolt.Placement = App.Placement(App.Vector(150, 30, 10), rot)
    assembly.addObject(bolt)
    bolt2 = doc.addObject("App::Link", "BoltLink")
    bolt2.setLink(bolt)
    bolt2.Placement = App.Placement(App.Vector(150, -30, 10), rot)
    assembly.addObject(bolt2)
    doc.recompute()

    ground = joints.newObject("App::FeaturePython", "GroundedJoint")
    JointObject.GroundedJoint(ground, fuselage)
    joint = joints.newObject("App::FeaturePython", "FinJoint")
    JointObject.Joint(joint, 0)  # Fixed
    # Fin's bottom face on the fuselage's top face; the solver moves the fin.
    joint.Proxy.setJointConnectors(joint, [[fuselage, ["Face6", "Vertex8"]], [fin, ["Face5", "Vertex1"]]])
    doc.recompute()
    doc.saveAs(path)
    return doc


def world_boxes(doc, names):
    import Part  # noqa: PLC0415

    out = {}
    for name in names:
        obj = doc.getObject(name)
        shape = Part.getShape(obj)
        if shape.isNull():
            raise RuntimeError(f"{name} has no shape")
        box = shape.BoundBox
        out[obj.Label] = (box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax, shape.Volume)
    return out


def same_boxes(a, b, where):
    if set(a) != set(b):
        raise RuntimeError(f"{where}: labels differ {sorted(a)} vs {sorted(b)}")
    for label in a:
        if any(abs(x - y) > TOL * max(1.0, abs(x)) for x, y in zip(a[label], b[label])):
            raise RuntimeError(f"{where}: {label} moved or changed {a[label]} -> {b[label]}")


def link_names(doc):
    return [o.Name for o in doc.Objects if o.TypeId == "App::Link"]


def open_and_check(path, expected, where):
    import FreeCAD as App  # noqa: PLC0415

    for d in list(App.listDocuments().values()):
        App.closeDocument(d.Name)
    doc = App.openDocument(path)
    for name in link_names(doc):
        link = doc.getObject(name)
        target = link.getLinkedObject(True)
        if target is None or target.Document is doc:
            raise RuntimeError(f"{where}: {link.Label} does not reach its part file")
    doc.recompute()
    same_boxes(world_boxes(doc, link_names(doc)), expected, where)
    return doc


def digest(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def run():
    import FreeCAD as App  # noqa: PLC0415

    from bruceworx import filerefs  # noqa: PLC0415
    from bruceworx.filemodel import MakeExternalError, make_external, plan_targets  # noqa: PLC0415
    from bruceworx.numbering import allocate_numbers  # noqa: PLC0415
    from bruceworx.sources import open_number_source  # noqa: PLC0415

    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK)
    design_path = os.path.join(WORK, "design", "VL-JET-design.FCStd")
    os.makedirs(os.path.dirname(design_path))
    doc = build_design(design_path)
    solids = ["Fuselage", "WingL", "WingR", "Fin", "Bolt", "BoltLink"]
    before = world_boxes(doc, solids)
    design_hash = digest(design_path)
    fin_before = App.Placement(doc.getObject("Fin").Placement)

    targets = [t.Name for t in plan_targets(doc)]
    if sorted(targets) != sorted(["Fuselage", "WingL", "WingR", "Fin", "Bolt"]):
        raise RuntimeError(f"unexpected targets {targets}")

    # A body used by a loose feature cannot be split: refused before writing.
    probe = doc.addObject("Part::Feature", "UsesFin")
    probe.setExpression("Placement", "Fin.Placement")
    doc.recompute()
    try:
        make_external(doc, os.path.join(WORK, "refused"), schema=False)
    except MakeExternalError as exc:
        if "UsesFin" not in str(exc):
            raise
    else:
        raise RuntimeError("make_external accepted a body with an outside user")
    if os.path.exists(os.path.join(WORK, "refused")):
        raise RuntimeError("refused run wrote files")
    doc.removeObject("UsesFin")
    doc.recompute()

    config = os.path.join(WORK, "numbering.json")
    shutil.copyfile(os.path.join(_ROOT, "config", "numbering.example.json"), config)
    shutil.copyfile(os.path.join(_ROOT, "config", "document_types.json"), os.path.join(WORK, "document_types.json"))
    numbers = allocate_numbers(open_number_source(config), "LE", "01", len(targets) + 1)

    project = os.path.join(WORK, "project", "VL-JET")
    report = make_external(doc, project, numbers=numbers, parts_dir="parts")
    if not report["ok"]:
        raise RuntimeError(f"make_external not ok: {report}")
    if digest(design_path) != design_hash:
        raise RuntimeError("the input file was modified")
    shared = {s["label"] for s in report["shared_dependencies"]}
    if "Params" not in shared:
        raise RuntimeError(f"shared spreadsheet not reported: {report['shared_dependencies']}")
    asm_path = report["assembly"]
    if os.path.basename(asm_path) != "LE-01-01001-001.FCStd":
        raise RuntimeError(f"assembly file name {asm_path}")
    for part in report["parts"]:
        if not part["stored_path"].startswith("parts/"):
            raise RuntimeError(f"link not relative: {part}")
    print("make-external ok:", [os.path.basename(p["file"]) for p in report["parts"]])

    # Part files: one App::Part, numbered, body about its own origin.
    for part in report["parts"]:
        pdoc = App.openDocument(part["file"])
        containers = [o for o in pdoc.Objects if o.TypeId == "App::Part"]
        if len(containers) != 1 or containers[0].PartNumber != part["part_number"]:
            raise RuntimeError(f"{part['file']}: container/PartNumber wrong")
        for o in pdoc.Objects:
            if o.TypeId == "PartDesign::Body" and not o.Placement.isIdentity():
                raise RuntimeError(f"{part['file']}: body placement not reset")
        App.closeDocument(pdoc.Name)

    expected = dict(before)
    asm = open_and_check(asm_path, expected, "reopened")
    joints = {o.Name: o for o in asm.Objects if "Reference1" in o.PropertiesList}
    fin_joint = joints["FinJoint"]
    for prop in ("Reference1", "Reference2"):
        owner, subs = getattr(fin_joint, prop)
        if owner.TypeId != "App::Link":
            raise RuntimeError(f"{prop} not on a link: {owner.Name} {subs}")
        part_doc = owner.LinkedObject.Document
        for sub in subs:
            inner = part_doc.getObject(sub.split(".")[0])
            if inner is None or inner.TypeId != "PartDesign::Body":
                raise RuntimeError(f"{prop} subname {sub!r} does not start at the body")
    ground = [o for o in asm.Objects if "ObjectToGround" in o.PropertiesList]
    if len(ground) != 1 or ground[0].ObjectToGround.TypeId != "App::Link":
        raise RuntimeError("ground not moved to the fuselage link")
    bolt_link = asm.getObject("BoltLink")
    if bolt_link.LinkedObject.Document is asm:
        raise RuntimeError("BoltLink still links inside the assembly")
    assembly = asm.getObject("Assembly")
    fin_link = next(o for o in asm.Objects if o.TypeId == "App::Link" and o.Label == "Fin")
    status = assembly.solve()
    if status not in (0, None):
        raise RuntimeError(f"solve failed: {status}")
    if not fin_link.Placement.isSame(fin_before, 1e-6):
        raise RuntimeError(f"fin moved on solve {fin_before} -> {fin_link.Placement}")
    print("reopen ok: shapes, joints, ground, repeated bolt, solve")

    # Acceptance: the whole folder moves.
    for d in list(App.listDocuments().values()):
        App.closeDocument(d.Name)
    moved = os.path.join(WORK, "moved", "elsewhere", "VL-JET")
    shutil.move(project, moved)
    moved_asm = os.path.join(moved, os.path.basename(asm_path))
    if not filerefs.walk(moved_asm).ok:
        raise RuntimeError("moved folder has broken links (file check)")
    open_and_check(moved_asm, expected, "moved folder")
    print("moved folder ok")

    packed = os.path.join(WORK, "packed")
    pack = filerefs.pack_and_go(moved_asm, packed)
    if not pack["ok"] or len(pack["files"]) != 6:
        raise RuntimeError(f"pack and go: {pack}")
    for d in list(App.listDocuments().values()):
        App.closeDocument(d.Name)
    shutil.rmtree(moved)  # the copy must stand alone
    open_and_check(pack["output"], expected, "pack and go")
    print("pack and go ok")

    for d in list(App.listDocuments().values()):
        App.closeDocument(d.Name)
    shutil.move(os.path.join(packed, "parts"), os.path.join(packed, "renamed-parts"))
    if filerefs.walk(pack["output"]).ok:
        raise RuntimeError("renamed parts folder should break the links")
    fix = filerefs.resolve(pack["output"], [packed])
    if not fix["ok"] or len(fix["fixed"]) != 5:
        raise RuntimeError(f"resolve-refs: {fix}")
    open_and_check(pack["output"], expected, "after resolve-refs")
    print("resolve-refs ok")


def _main():
    try:
        run()
    except Exception:  # noqa: BLE001 — report and fail the process
        traceback.print_exc()
        print("BW_FILEMODEL FAIL", flush=True)
        sys.exit(1)
    print("BW_FILEMODEL PASS", flush=True)
    sys.exit(0)


if __name__ in ("__main__", "freecad_filemodel"):
    _main()
