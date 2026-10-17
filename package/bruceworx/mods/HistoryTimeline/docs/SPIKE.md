# FCB-P1F-15 — reading PartDesign history from Python

Sources read: this tree, FreeCAD 1.1.4 (`PartDesign::Body`, `Part::BodyBase`, `PartDesign::Feature`, `CmdPartDesignMoveTip`, `TreeWidget::sortDroppedObjects`).

Checks run: `tests/test_timeline_access.py` on conda-forge **FreeCAD 1.1.3** (`freecadcmd`, 71 passed, 0 failed). This workspace has no built `FreeCADCmd` yet. 1.1.3 and this tree expose the same properties the test uses (`Group`, `Tip`, `BaseFeature`, `Suppressed`, `insertObject`, `removeObject`, `VisibleFeature`). Re-run the script on a BruceWorx build when one exists; the script does not import anything BruceWorx-specific.

## Verdict

| Need | From Python, on stock FreeCAD | Safe for a timeline? |
|---|---|---|
| Feature order | `Body.Group`, front to back | Yes, as the display order |
| Which feature is current | `Body.Tip` | Yes |
| Roll the history marker | `Body.Tip = feature` (or `None`) | Yes, with the limits below |
| Suppressed features | `Feature.Suppressed` | Yes, and it is a different mechanism from the tip |
| Icons / labels | `Label`, `TypeId`, and in the GUI `ViewObject.Icon` | Yes |
| Move / reorder a feature | No single safe call | **No.** Do not ship drag-reorder on this |

A bottom bar that lists `Group`, marks `Tip`, and sets `Tip` is feasible as a Python add-on. A Fusion-style reorder is not, until we define a rewire that also moves sketches and refuses topology references.

## Order is `Body.Group`

`Body.addObject` appends while the tip has no following solid, and it moves `Tip` onto a new solid. The test body comes out as:

`Sketch`, `Datum` (`PartDesign::Plane`), `Box`, `Cylinder`, `Sphere`, `Vars` (`App::VarSet`)

with `Tip` = `Sphere`.

`isSolidFeature` / `isAllowed` / `getPrevSolidFeature` / `getNextSolidFeature` are not Python methods. The add-on reimplements the solid test with `isDerivedFrom("PartDesign::Feature")` and excludes `App::DatumElement` and `Part::Datum`. That matched the three primitives, the sketch, the datum plane, and the VarSet.

Not reproduced: `Transformed::isMultiTransformChild()` is C++ only. A pattern that lives inside a MultiTransform still looks like a solid to Python.

Origin planes (`XY_Plane`, …) hang off `Body.Origin`. They are not in `Group`. `Body.BaseFeature` (an imported solid) is also outside `Group`, but `Tip` is allowed to point at it.

`Body.VisibleFeature` is the first **visible** `PartDesign::Feature` in `Group`. After the test forced `Box` visible, `VisibleFeature` was `Box` while `Tip` was `Sphere`. The bar must use `Tip`, not `VisibleFeature`.

## Tip / Set tip

`PartDesign_MoveTip` is `body.Tip = <feature>` plus showing that feature. Python can do the assignment. `history_timeline.model.set_tip` copies the command's rule: a solid in the body, the body's base feature, or `None`. A sketch raises `ValueError` and leaves `Tip` alone.

What Set tip actually does, confirmed by the test:

* `Tip = Box` makes `Body.Shape` equal the box (volume 1000). Cylinder and Sphere stay in `Group`. Neither gains `Suppressed`.
* `Tip = None` makes `Body.Shape` null. State stays `Up-to-date`.
* Putting the tip back on Sphere restores the previous volume (about 1632.9).
* Assigning `Tip` to the sketch anyway (the property will take it) marks the body `Invalid` (`Touched`, `Invalid`). `Body::execute` reports "Linked object is not a PartDesign feature". The old volume is left on the shape. The add-on must not do this.

Rolling the tip does **not** stop later features from recomputing. `addObject` still inserts before the next solid after the tip, and `insertObject` / `setBaseProperty` rewires `BaseFeature` for that new solid. So "insert at the marker" already exists for features created through `addObject`. Features that were already after the tip keep computing.

## Suppressed

`PartDesign::Feature` has `SuppressibleExtension.Suppressed`. The sketch and the VarSet do not.

A suppressed solid still recomputes, then its `Shape` is replaced with the base shape. In the test, suppressing Cylinder (between Box and Sphere):

* Cylinder volume becomes the box volume (1000).
* The body, still tipped at Sphere, changes from about 1632.9 to about 1458.1.
* Unsuppress restores the flag and the volume.
* The body stays valid.

Suppression and the tip are independent. A dimmed "past the marker" feature is not a suppressed feature. The bar draws them differently (opacity vs a slash).

## Reorder

Three different operations, all exercised:

1. **`Body.Group = reversed(group)`** — this is what an in-body tree drop does (`TreeWidget::sortDroppedObjects` only writes `Group`). `BaseFeature` links do not change. `getPrevSolidFeature` walks `Group`, so the displayed previous solid and `BaseFeature` diverge (Sphere's group-previous solid was no longer Cylinder; `Sphere.BaseFeature` was still Cylinder). Recompute still succeeds and the tip volume does not change, because the compute chain is `BaseFeature`, not `Group`. Showing that order in a timeline would lie about history.

2. **`feature.BaseFeature = other`** — the link updates and `Group` does not move. `Feature::onChanged` looks like it should call `insertObject` when the base is not immediately previous, but the base index is written into `idx` instead of `baseidx`, so `baseidx` stays -1 and the branch never runs. Python cannot rely on setting `BaseFeature` to reorder the tree.

3. **`removeObject` + `insertObject`** — `body.removeObject` does dispatch to `Body::removeObject`. Removing Cylinder relinked `Sphere.BaseFeature` to Box and left `Tip` on Sphere. `insertObject(Cylinder, Sphere, True)` placed it after Sphere, set `Cylinder.BaseFeature` to Sphere, and **did not move Tip**. Body volume then matched Sphere; Cylinder, now past the tip, carried the full fusion volume. `rewire_solid_chain` (set each solid's `BaseFeature` to the previous solid, then assign `Group`) put the chain and the volume back without moving `Tip`.

`insertObject` on an object that is already in the body **inserts a second Group entry**. The test saw `Box` twice (`Sketch, Datum, Box, Cylinder, Sphere, Box, Vars`). Callers must `removeObject` first. Do not recompute while the duplicate is in place; the test restored the chain before recomputing.

What none of these do:

* Move a Pad's sketch with the Pad. Profile, Sections, Spine, and AttachmentSupport stay where they are.
* Rewrite dress-up sub-elements. Fillet/chamfer `onChanged` points `Base` at the new `BaseFeature` but keeps the old `FaceN` names.
* Update topological references from later features.
* Tell Python whether `isFeatureMovable` would allow a drag. That helper is GUI-only, and it returns false for any `PartDesign::Feature` that already has a `BaseFeature` — every solid after the first. It answers "can this leave the body", not "can the timeline reorder it".

So a timeline reorder is a new policy, not a wrapped command. The prototype leaves **Move earlier** / **Move later** disabled.

## Not in this spike

No C++ changes. The add-on is `package/bruceworx/mods/HistoryTimeline`. The fork build does not load it. The BruceWorx CI workflow is unchanged, including the self-hosted macOS job.

The dock (FCB-P1F-16) only reads `Group`, sets `Tip`, toggles `Suppressed`, and calls `setEdit`. Questions that block the full build are in [REVIEW.md](REVIEW.md).
