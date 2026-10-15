# SPDX-License-Identifier: LGPL-2.1-or-later
"""Headless proof that a Python add-on can read PartDesign history.

Run with FreeCAD's console binary (name is ``FreeCADCmd`` in a source build
and ``freecadcmd`` in the conda package)::

    freecadcmd package/bruceworx/mods/HistoryTimeline/tests/test_timeline_access.py

The script exits 0 when every check passes and 1 otherwise. It does not load
the GUI.
"""

from __future__ import annotations

import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import FreeCAD as App

from history_timeline import model

FAILURES = []
PASSED = 0


def emit(message):
    # FreeCADCmd exits with os._exit, which skips the stdout flush. A pipe
    # would otherwise swallow every result line.
    print(message, flush=True)


def check(condition, message):
    global PASSED
    if condition:
        PASSED += 1
        emit(f"PASS  {message}")
    else:
        FAILURES.append(message)
        emit(f"FAIL  {message}")


def volume(obj):
    try:
        shape = obj.Shape
        if shape.isNull():
            return None
        return float(shape.Volume)
    except Exception:
        return None


def state_of(obj):
    try:
        return list(obj.State)
    except Exception:
        return []


def names(objects):
    return [obj.Name for obj in objects]


def base_map(objects):
    found = {}
    for obj in objects:
        link = getattr(obj, "BaseFeature", None)
        found[obj.Name] = link.Name if link else None
    return found


def find_origin_plane(doc):
    for obj in doc.Objects:
        if obj.Name.startswith("XY_Plane") or obj.Label == "XY_Plane":
            return obj
    return None


def build_body(doc):
    """Sketch, datum plane, three primitives, and a VarSet when the type exists."""
    body = doc.addObject("PartDesign::Body", "Body")
    doc.recompute()
    plane_xy = find_origin_plane(doc)

    sketch = doc.addObject("Sketcher::SketchObject", "Sketch")
    if plane_xy is not None:
        sketch.AttachmentSupport = (plane_xy, [""])
        sketch.MapMode = "FlatFace"
    body.addObject(sketch)

    datum = doc.addObject("PartDesign::Plane", "Datum")
    if plane_xy is not None:
        datum.AttachmentSupport = (plane_xy, [""])
        datum.MapMode = "FlatFace"
    body.addObject(datum)

    box = doc.addObject("PartDesign::AdditiveBox", "Box")
    box.Length = 10
    box.Width = 10
    box.Height = 10
    body.addObject(box)

    cylinder = doc.addObject("PartDesign::AdditiveCylinder", "Cylinder")
    cylinder.Radius = 2
    cylinder.Height = 20
    body.addObject(cylinder)

    sphere = doc.addObject("PartDesign::AdditiveSphere", "Sphere")
    sphere.Radius = 5
    body.addObject(sphere)

    varset = None
    try:
        varset = doc.addObject("App::VarSet", "Vars")
        body.addObject(varset)
    except Exception as exc:
        emit(f"NOTE  VarSet not added: {exc}")
        varset = None

    doc.recompute()
    return {
        "body": body,
        "sketch": sketch,
        "datum": datum,
        "box": box,
        "cylinder": cylinder,
        "sphere": sphere,
        "varset": varset,
        "plane_xy": plane_xy,
    }


def test_read_order_tip_and_chain():
    doc = App.newDocument("TimelineRead")
    try:
        built = build_body(doc)
        body = built["body"]
        emit("--- read_timeline ---")
        timeline = model.read_timeline(body)
        emit(timeline.format_report())

        expected = [
            built["sketch"].Name,
            built["datum"].Name,
            built["box"].Name,
            built["cylinder"].Name,
            built["sphere"].Name,
        ]
        if built["varset"] is not None:
            expected.append(built["varset"].Name)
        check(names(body.Group) == expected, f"Group order is {expected}, got {names(body.Group)}")
        check(timeline.tip_name == built["sphere"].Name, "Tip is the last solid (Sphere)")
        check(timeline.tip_in_group, "Tip object is inside Group")

        check(not model.is_solid_feature(built["sketch"]), "Sketch is not a solid feature")
        check(not model.is_solid_feature(built["datum"]), "Datum plane is not a solid feature")
        check(model.is_solid_feature(built["box"]), "AdditiveBox is a solid feature")
        check(model.is_solid_feature(built["cylinder"]), "AdditiveCylinder is a solid feature")
        check(model.is_solid_feature(built["sphere"]), "AdditiveSphere is a solid feature")
        if built["varset"] is not None:
            check(not model.is_solid_feature(built["varset"]), "VarSet is not a solid feature")
            check(
                not hasattr(built["varset"], "Suppressed"),
                "VarSet has no Suppressed property",
            )

        check(hasattr(built["box"], "Suppressed"), "Solid features expose Suppressed")
        check(not model.is_suppressed(built["box"]), "New solid is not suppressed")

        check(built["box"].BaseFeature is None, "First solid BaseFeature is None")
        check(
            built["cylinder"].BaseFeature == built["box"],
            "Cylinder.BaseFeature is Box (addObject wired the chain)",
        )
        check(
            built["sphere"].BaseFeature == built["cylinder"],
            "Sphere.BaseFeature is Cylinder",
        )
        check(
            model.previous_solid_in_group(body, built["sphere"]) == built["cylinder"],
            "Group-order previous solid of Sphere matches BaseFeature",
        )

        check(built["plane_xy"] is not None, "Body created an XY_Plane on its origin")
        if built["plane_xy"] is not None:
            check(
                built["plane_xy"] not in list(body.Group),
                "Origin planes are not Body.Group entries",
            )

        # addObject hides earlier solids, so the first visible PartDesign
        # feature would be the tip. Force an earlier solid visible: headless
        # has no view-provider hider, so VisibleFeature and Tip can differ.
        built["box"].Visibility = True
        built["sphere"].Visibility = True
        visible = body.VisibleFeature
        visible_name = visible.Name if visible else None
        emit(f"NOTE  VisibleFeature={visible_name} Tip={body.Tip.Name}")
        check(visible_name == built["box"].Name, "VisibleFeature is the first visible solid, not the tip")
        check(visible != body.Tip, "VisibleFeature and Tip are different properties")

        full_volume = volume(body)
        emit(f"NOTE  body volume at tip Sphere = {full_volume}")
        check(full_volume is not None and full_volume > 0, "Body shape at the tip has a volume")
        check("Invalid" not in state_of(body) and body.isValid(), f"Body valid, state={state_of(body)}")
    finally:
        App.closeDocument(doc.Name)


def test_set_tip_and_suppress():
    doc = App.newDocument("TimelineTip")
    try:
        built = build_body(doc)
        body = built["body"]
        box = built["box"]
        cylinder = built["cylinder"]
        sphere = built["sphere"]
        full_volume = volume(body)

        model.set_tip(body, box)
        doc.recompute()
        rolled = model.read_timeline(body)
        emit("--- tip rolled to Box ---")
        emit(rolled.format_report())
        emit(f"NOTE  body volume at tip Box = {volume(body)} box volume = {volume(box)}")
        check(body.Tip == box, "set_tip assigns Body.Tip")
        check(
            volume(body) is not None and abs(volume(body) - volume(box)) < 1e-6,
            "Body shape equals the tip shape",
        )
        check(rolled.entry(cylinder.Name).after_tip, "Cylinder is after the rolled tip")
        check(rolled.entry(sphere.Name).after_tip, "Sphere is after the rolled tip")
        check(not rolled.entry(box.Name).after_tip, "The tip itself is not after the marker")
        check(not rolled.entry(built["sketch"].Name).after_tip, "Sketch before the tip stays before the marker")
        check(cylinder in list(body.Group) and sphere in list(body.Group), "Features past the tip stay in Group")
        check(not model.is_suppressed(cylinder), "Rolling the tip does not suppress later features")

        model.set_tip(body, None)
        doc.recompute()
        cleared = model.read_timeline(body)
        emit(f"NOTE  body volume with Tip=None = {volume(body)} null={body.Shape.isNull()} state={state_of(body)}")
        check(body.Tip is None, "Tip can be cleared")
        check(all(entry.after_tip for entry in cleared.entries), "Cleared tip puts the marker before every entry")
        check(volume(body) in (None, 0) or body.Shape.isNull(), "Cleared tip drops the body solid")

        model.set_tip(body, sphere)
        doc.recompute()
        check(abs(volume(body) - full_volume) < 1e-4, "Restoring the tip restores the body volume")

        ok, reason = model.can_be_tip(body, built["sketch"])
        check(not ok, f"Sketch cannot be the tip ({reason})")
        refused = False
        try:
            model.set_tip(body, built["sketch"])
        except ValueError:
            refused = True
        check(refused, "set_tip rejects a sketch")
        check(body.Tip == sphere, "Rejected set_tip leaves Tip unchanged")

        # The property itself will accept a sketch. Record what execute does.
        body.Tip = built["sketch"]
        doc.recompute()
        emit(
            f"NOTE  raw Tip=Sketch isValid={body.isValid()} state={state_of(body)} "
            f"volume={volume(body)}"
        )
        check(not body.isValid(), "Assigning Tip to a sketch marks the body invalid")
        check(
            "Invalid" in state_of(body),
            f"Body state contains Invalid after a sketch tip, got {state_of(body)}",
        )
        body.Tip = sphere
        doc.recompute()
        check(body.isValid() and volume(body) is not None, "Tip restored to Sphere after the non-solid assignment")

        before_suppress = volume(body)
        model.set_suppressed(cylinder, True)
        doc.recompute()
        emit(
            f"NOTE  suppressed Cylinder volume={volume(cylinder)} box={volume(box)} "
            f"body={volume(body)} before={before_suppress} state={state_of(body)}"
        )
        check(model.is_suppressed(cylinder), "Suppressed flag sticks")
        check(body.isValid(), f"Body still valid with a suppressed middle solid, state={state_of(body)}")
        cyl_vol = volume(cylinder)
        box_vol = volume(box)
        check(
            cyl_vol is not None and box_vol is not None and abs(cyl_vol - box_vol) / box_vol < 0.02,
            "Suppressed solid shape passes the base shape through",
        )
        after_suppress = volume(body)
        check(
            after_suppress is not None and abs(after_suppress - before_suppress) > 1e-3,
            "Suppressing a middle solid changes the tip result",
        )
        model.set_suppressed(cylinder, False)
        doc.recompute()
        check(not model.is_suppressed(cylinder), "Unsuppress clears the flag")
        check(
            abs(volume(body) - before_suppress) < 1e-3,
            "Unsuppress restores the tip volume",
        )
    finally:
        App.closeDocument(doc.Name)


def test_reorder_is_not_free():
    doc = App.newDocument("TimelineReorder")
    try:
        built = build_body(doc)
        body = built["body"]
        box = built["box"]
        cylinder = built["cylinder"]
        sphere = built["sphere"]
        original_group = names(body.Group)
        original_bases = base_map(body.Group)
        original_volume = volume(body)

        model.assign_group_order(body, list(reversed(body.Group)))
        emit("--- Group reversed, BaseFeature left alone ---")
        emit(model.read_timeline(body).format_report())
        check(names(body.Group) == list(reversed(original_group)), "assign_group_order reverses Group")
        check(base_map(body.Group) == original_bases, "Reversing Group does not rewrite BaseFeature")
        check(
            model.previous_solid_in_group(body, sphere) != cylinder,
            "After a Group-only reorder, Group-previous solid is no longer BaseFeature",
        )
        check(sphere.BaseFeature == cylinder, "Sphere.BaseFeature is still Cylinder")
        doc.recompute()
        emit(f"NOTE  volume after Group reverse = {volume(body)} state={state_of(body)}")
        check(body.isValid(), "Document still recomputes when only Group order changed")
        check(
            abs(volume(body) - original_volume) < 1e-3,
            "Group-only reorder does not change the tip solid (chain unchanged)",
        )

        # Setting BaseFeature does not pull Group into line. Feature::onChanged
        # looks up the base index into the wrong variable, so the branch is dead.
        group_before = names(body.Group)
        sphere.BaseFeature = box
        check(names(body.Group) == group_before, "Assigning BaseFeature does not reorder Group")
        check(sphere.BaseFeature == box, "BaseFeature assignment itself works")
        sphere.BaseFeature = cylinder
        model.assign_group_order(body, [doc.getObject(name) for name in original_group])
        doc.recompute()
        check(names(body.Group) == original_group, "Group restored")
        check(abs(volume(body) - original_volume) < 1e-3, "Volume restored after Group restore")

        # removeObject should be Body::removeObject: next solid's BaseFeature
        # skips the removed solid, Tip stays put if we did not remove the tip.
        model.remove_feature(body, cylinder)
        emit("--- after removeObject(Cylinder) ---")
        emit(f"NOTE  group={names(body.Group)} tip={body.Tip.Name if body.Tip else None}")
        emit(f"NOTE  sphere.BaseFeature={sphere.BaseFeature.Name if sphere.BaseFeature else None}")
        check(cylinder not in list(body.Group), "removeObject drops the feature from Group")
        check(sphere.BaseFeature == box, "removeObject relinks the next solid onto the previous solid")
        check(body.Tip == sphere, "Removing a non-tip solid leaves Tip alone")

        body.insertObject(cylinder, sphere, True)
        emit("--- after insertObject(Cylinder, after Sphere) ---")
        emit(model.read_timeline(body).format_report())
        solids = [obj.Name for obj in body.Group if model.is_solid_feature(obj)]
        check(solids == [box.Name, sphere.Name, cylinder.Name], f"Cylinder inserted after Sphere, solids={solids}")
        check(cylinder.BaseFeature == sphere, "insertObject sets the moved solid's BaseFeature")
        check(body.Tip == sphere, "insertObject does not move Tip")
        doc.recompute()
        emit(
            f"NOTE  tip still Sphere volume={volume(body)} sphere={volume(sphere)} "
            f"cylinder={volume(cylinder)} state={state_of(body)}"
        )
        check(body.isValid(), f"Recompute after remove+insert, state={state_of(body)}")
        check(
            volume(body) is not None and abs(volume(body) - volume(sphere)) < 1e-4,
            "Body shape still follows Tip, which is now before the moved solid",
        )

        # Second document-level check: explicit chain rewire, including sketches.
        # Done in this same body by putting solids back and calling the helper.
        ordered = [
            built["sketch"],
            built["datum"],
            box,
            cylinder,
            sphere,
        ]
        if built["varset"] is not None:
            ordered.append(built["varset"])
        model.rewire_solid_chain(body, ordered)
        doc.recompute()
        check(cylinder.BaseFeature == box and sphere.BaseFeature == cylinder, "rewire_solid_chain restores Box→Cylinder→Sphere")
        check(body.Tip == sphere, "rewire_solid_chain does not change Tip")
        check(abs(volume(body) - original_volume) < 1e-3, "Rewired chain matches the original tip volume")

        # insertObject does not remove an existing member first.
        before = len(body.Group)
        body.insertObject(box, sphere, True)
        after_names = names(body.Group)
        emit(f"NOTE  Group after insertObject of a member: {after_names}")
        check(len(body.Group) == before + 1, "insertObject of an existing member adds a second Group entry")
        check(after_names.count(box.Name) == 2, "The same object can appear twice in Group")
        # Do not recompute a duplicated, possibly cyclic chain. Put the model back.
        model.rewire_solid_chain(body, ordered)
        model.set_tip(body, sphere)
        doc.recompute()
        check(names(body.Group) == [obj.Name for obj in ordered], "Group restored after the duplicate insert")
        check(body.isValid(), "Body valid after restoring the duplicate insert")
    finally:
        App.closeDocument(doc.Name)


def main():
    version = ".".join(str(part) for part in App.Version()[:3])
    emit(f"=== History timeline spike on FreeCAD {version} ===")
    try:
        test_read_order_tip_and_chain()
        test_set_tip_and_suppress()
        test_reorder_is_not_free()
    except Exception:
        traceback.print_exc()
        sys.stderr.flush()
        FAILURES.append("unhandled exception (see traceback)")
    emit(f"=== {PASSED} passed, {len(FAILURES)} failed ===")
    if FAILURES:
        for message in FAILURES:
            emit(f"  - {message}")
        os._exit(1)
    os._exit(0)


main()
