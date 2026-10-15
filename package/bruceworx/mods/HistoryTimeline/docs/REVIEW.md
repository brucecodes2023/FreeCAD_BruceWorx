# FCB-P1F-17 — questions for Bruce

The spike (FCB-P1F-15) and the bar mock (FCB-P1F-16) are in this folder. Nothing here should be built out until these choices are made. The prototype's current behavior is the first option when one is marked "prototype".

## 1. What is one timeline entry?

* **A. Prototype.** Every `Body.Group` child, in order: sketches, datums, solids, binders, VarSets.
* **B.** Solid features only.
* **C.** Solids, with each sketch nested under the feature that uses it as `Profile` (not flat Group order).

Origin planes are not in `Group`. Confirm they stay off the bar.

## 2. What does the marker mean?

* **A. Prototype.** The marker sits after `Body.Tip`. Later features stay in the model and **still recompute**. New features created with `addObject` insert before the next solid after the tip. This is today's Set tip.
* **B.** Fusion-style rollback: features after the marker do not recompute. That is new behavior, not a `Tip` assignment.
* **C.** Rolling the marker also sets `Suppressed` on everything after the tip. That changes downstream shapes, and it is a different property from `Tip`.

## 3. Click behavior

* **A. Prototype.** Single click rolls the tip. Double-click edits (`setEdit`). Right-click has both.
* **B.** Single click edits. The marker is a separate control.
* **C.** Single click only selects. The marker is dragged. Edit is on the context menu (closer to Fusion).

## 4. Is reorder in the first build?

* **A. Prototype, and the spike's recommendation.** Not in v1. **Move earlier** / **Move later** stay disabled.
* **B.** Reorder solids by `removeObject` + `insertObject` (or `rewire_solid_chain`), move each feature's Profile sketch with it, and refuse the drop when anything is attached to a generated face or is a dress-up (fillet, chamfer, thickness). `Tip` is left where it is unless we also decide to move it.
* **C.** Match the tree: rewrite `Group` only, and accept that `BaseFeature` can disagree with the order on screen.

`insertObject` on a member that is already in the body duplicates the Group entry. Any reorder has to remove first. `isFeatureMovable` is not available to Python, and it answers a different question (can this feature leave the body). It is false for every solid that already has a `BaseFeature`.

## 5. Which body does the bar show?

* **A. Prototype.** The active PartDesign body (`pdbody`). If none is active, the first body in the document, with a label that says so.
* **B.** Active body only. Empty state otherwise. If several bodies exist and none is active, show a picker.
* **C.** One strip per body (tabs).

## 6. Suppression vs past-the-tip

Confirm these stay visually distinct. The prototype uses a red slash for `Suppressed` and 42% opacity for "after `Tip`". They can combine. Suppressing a middle solid changes the tip shape (the test went from volume ~1632.9 to ~1458.1). Rolling the tip does not.

## 7. Where the dock lives

* **A. Prototype.** A global bottom dock, any workbench, hidden until **BruceWorx → History Timeline** is checked.
* **B.** Visible only while the PartDesign workbench is active.
* **C.** Not a dock. Sit it in the tree, or replace the tree for PartDesign bodies.

## 8. Non-solids as the tip

Confirm the prototype's refusal: sketches and datums cannot be `Tip`. Assigning `Tip` to a sketch marks the body `Invalid` ("Linked object is not a PartDesign feature"). `None` is allowed and clears the solid. The body's external `BaseFeature` is allowed, matching **Set tip**.

## 9. Imported base feature

When `Body.BaseFeature` is set, should the bar show it as a leading entry (it is not in `Group`)? The prototype omits it. If `Tip` points at that base feature, the marker is drawn at the front of the row.

## 10. Failures

Should an `Invalid` feature get a red mark? The prototype does not. A sketch tip leaves the previous volume on the shape while `isValid()` is false, so a badge would matter.

## 11. Keeping it optional

Confirm the add-on stays out of `src/Mod` and out of the default module path, with `Mod/HistoryTimeline/Enabled` defaulting to false. Hard off switches already work without code changes: `ADDON_DISABLED` in this folder, and `--disable-addon HistoryTimeline`.

## 12. Patterns

Flat `Group` order even for Mirrored / LinearPattern / PolarPattern / MultiTransform? Python cannot see `isMultiTransformChild()`, so a transform that is not itself a solid still appears as one. Is that acceptable for v1, or do patterns need a C++ query before the bar can be honest?
