# SPDX-License-Identifier: LGPL-2.1-or-later
"""Read and write PartDesign history data. No GUI imports.

The body's displayed result is ``Body.Tip`` (see ``PartDesign::Body::execute``).
``Body.Group`` is the tree order. Each solid's ``BaseFeature`` is the object it
actually fuses or cuts. Those two orders match after ``Body.addObject`` /
``insertObject``, and they diverge if only ``Group`` is rewritten.
"""

from __future__ import annotations


def is_solid_feature(obj) -> bool:
    """Python stand-in for ``PartDesign::Body::isSolidFeature``.

    Datums (``App::DatumElement`` / ``Part::Datum``) are not solids. Sketches,
    VarSets and binders are not ``PartDesign::Feature``.

    Not reproduced here: ``Transformed::isMultiTransformChild()`` is C++ only,
    so a pattern nested inside a MultiTransform still looks like a solid.
    """
    if obj is None:
        return False
    try:
        if not obj.isDerivedFrom("PartDesign::Feature"):
            return False
        if obj.isDerivedFrom("App::DatumElement") or obj.isDerivedFrom("Part::Datum"):
            return False
    except (AttributeError, RuntimeError, TypeError):
        return False
    return True


def is_suppressed(obj) -> bool:
    """``SuppressibleExtension.Suppressed``. Missing property means not suppressed."""
    prop = getattr(obj, "Suppressed", None)
    if prop is None:
        return False
    try:
        return bool(prop)
    except (AttributeError, RuntimeError, TypeError):
        return False


def _link_name(link):
    if not link:
        return None
    try:
        return link.Name
    except (AttributeError, RuntimeError):
        return None


def icon_kind(type_id: str) -> str:
    """Coarse glyph key for the prototype bar. Real sessions prefer ViewObject.Icon."""
    table = {
        "Sketcher::SketchObject": "sketch",
        "PartDesign::Plane": "datum",
        "PartDesign::Line": "datum",
        "PartDesign::Point": "datum",
        "PartDesign::CoordinateSystem": "datum",
        "PartDesign::Pad": "pad",
        "PartDesign::Pocket": "pocket",
        "PartDesign::Revolution": "pad",
        "PartDesign::Groove": "pocket",
        "PartDesign::Fillet": "fillet",
        "PartDesign::Chamfer": "chamfer",
        "PartDesign::Thickness": "feature",
        "PartDesign::AdditiveBox": "box",
        "PartDesign::SubtractiveBox": "box",
        "PartDesign::AdditiveCylinder": "cylinder",
        "PartDesign::SubtractiveCylinder": "cylinder",
        "PartDesign::AdditiveSphere": "sphere",
        "PartDesign::SubtractiveSphere": "sphere",
        "PartDesign::Hole": "pocket",
        "PartDesign::Mirrored": "feature",
        "PartDesign::LinearPattern": "feature",
        "PartDesign::PolarPattern": "feature",
        "PartDesign::MultiTransform": "feature",
        "PartDesign::Boolean": "feature",
        "PartDesign::ShapeBinder": "feature",
        "PartDesign::SubShapeBinder": "feature",
        "App::VarSet": "vars",
    }
    if type_id in table:
        return table[type_id]
    if type_id.startswith("PartDesign::Additive"):
        return "box"
    if type_id.startswith("PartDesign::Subtractive"):
        return "pocket"
    if "Sketch" in type_id:
        return "sketch"
    return "feature"


class TimelineEntry:
    """One ``Body.Group`` child, in Group order."""

    def __init__(self, obj, index, tip, tip_index):
        self.obj = obj
        self.index = index
        self.name = obj.Name
        self.label = obj.Label
        self.type_id = obj.TypeId
        self.kind = icon_kind(self.type_id)
        self.is_solid = is_solid_feature(obj)
        self.suppressed = is_suppressed(obj)
        self.base_name = _link_name(getattr(obj, "BaseFeature", None))
        self.is_tip = tip is not None and obj == tip
        if tip is None or tip_index is None:
            # Tip is unset, or it points outside Group (usually Body.BaseFeature).
            # Either way the marker is in front of this row.
            self.after_tip = True
        else:
            self.after_tip = index > tip_index
        self.icon = None  # optional QIcon, filled in by the dock

    def __repr__(self):
        flags = []
        if self.is_solid:
            flags.append("solid")
        if self.is_tip:
            flags.append("tip")
        if self.after_tip:
            flags.append("after-tip")
        if self.suppressed:
            flags.append("suppressed")
        extra = (" " + ",".join(flags)) if flags else ""
        return f"<TimelineEntry {self.name} {self.type_id}{extra}>"


class Timeline:
    def __init__(self, body, entries, tip, tip_index):
        self.body = body
        self.body_name = body.Name
        self.body_label = body.Label
        self.entries = entries
        self.tip = tip
        self.tip_name = tip.Name if tip is not None else None
        self.tip_index = tip_index
        self.tip_in_group = tip_index is not None
        self.base_feature_name = _link_name(body.BaseFeature)

    def entry(self, name):
        for item in self.entries:
            if item.name == name:
                return item
        return None

    def format_report(self):
        lines = [
            f"body {self.body_label} ({self.body_name})",
            f"tip {self.tip_name!r} index={self.tip_index} in_group={self.tip_in_group}",
            f"base_feature {self.base_feature_name!r}",
        ]
        for item in self.entries:
            lines.append(
                f"  [{item.index}] {item.label} ({item.name}) {item.type_id}"
                f" solid={item.is_solid} suppressed={item.suppressed}"
                f" tip={item.is_tip} after_tip={item.after_tip}"
                f" base={item.base_name}"
            )
        return "\n".join(lines)


def read_timeline(body) -> Timeline:
    """Snapshot ``body.Group`` and where ``body.Tip`` sits in that list."""
    group = list(body.Group)
    tip = body.Tip
    tip_index = None
    if tip is not None:
        for index, obj in enumerate(group):
            if obj == tip:
                tip_index = index
                break
    entries = [TimelineEntry(obj, i, tip, tip_index) for i, obj in enumerate(group)]
    return Timeline(body, entries, tip, tip_index)


def can_be_tip(body, feature):
    """Same rule as ``PartDesign_MoveTip`` (``CmdPartDesignMoveTip``).

    Returns ``(ok, reason)``. ``feature is None`` clears the tip, which the
    command does when the body itself is selected.
    """
    if feature is None:
        return True, ""
    in_group = feature in list(body.Group)
    is_base = body.BaseFeature is not None and feature == body.BaseFeature
    if is_solid_feature(feature) and (in_group or is_base):
        return True, ""
    if is_base:
        return True, ""
    type_id = getattr(feature, "TypeId", type(feature).__name__)
    name = getattr(feature, "Name", repr(feature))
    return (
        False,
        "Only a solid feature, the body's base feature, or None can be the tip "
        f"({name} is {type_id}).",
    )


def set_tip(body, feature):
    """Assign ``Body.Tip``. Does not suppress later features and does not recompute.

    Later features stay in ``Group`` and still recompute when the document does.
    The body's ``Shape`` becomes the tip shape (or null when the tip is cleared).
    """
    ok, reason = can_be_tip(body, feature)
    if not ok:
        raise ValueError(reason)
    body.Tip = feature


def set_suppressed(feature, value: bool):
    """Toggle ``Feature.Suppressed``.

    A suppressed solid still recomputes, then its ``Shape`` is replaced with the
    base shape (passthrough). This is independent of ``Body.Tip``.
    """
    if not hasattr(feature, "Suppressed"):
        raise AttributeError(
            f"{getattr(feature, 'Name', feature)} ({getattr(feature, 'TypeId', '?')}) "
            "has no Suppressed property"
        )
    feature.Suppressed = bool(value)


def previous_solid_in_group(body, feature):
    """Previous solid in ``Group`` order. This is what ``getPrevSolidFeature`` walks.

    It is not ``feature.BaseFeature`` once those have diverged.
    """
    group = list(body.Group)
    try:
        index = group.index(feature)
    except ValueError:
        return None
    for obj in reversed(group[:index]):
        if is_solid_feature(obj):
            return obj
    return None


def assign_group_order(body, ordered_objects):
    """Rewrite ``Body.Group`` only.

    This is what the tree does on an in-body drop (``TreeWidget::sortDroppedObjects``).
    ``BaseFeature`` links are left untouched, so the compute chain can disagree
    with the displayed order. Not safe for a Fusion-style reorder.
    """
    body.Group = list(ordered_objects)


def rewire_solid_chain(body, ordered_objects):
    """Point each solid's ``BaseFeature`` at the previous solid, then assign ``Group``.

    ``Tip`` is not moved. Sketches are only moved if the caller placed them in
    ``ordered_objects``. Dress-up features (fillet, chamfer, …) copy the old
    sub-element names onto the new base when ``BaseFeature`` changes, so this
    is still unsafe for topology-based features. Patterns and profile links
    are not updated.
    """
    previous = None
    for obj in ordered_objects:
        if is_solid_feature(obj) and hasattr(obj, "BaseFeature"):
            obj.BaseFeature = previous
            previous = obj
    body.Group = list(ordered_objects)


def remove_feature(body, feature):
    """``Body.removeObject``. Virtual dispatch should run ``Body::removeObject``.

    That C++ method relinks the next solid's ``BaseFeature`` and moves ``Tip``
    off the removed object. ``insertObject`` does not move ``Tip``.
    """
    return body.removeObject(feature)
