# SPDX-License-Identifier: LGPL-2.1-or-later
"""BruceWorx Rectangular and Circular Pattern for bodies and components (BW-MOD-01).

A linked pattern is one ``App::Link`` array (``ElementCount`` = generated
instances) that links the seed's geometry. The pattern parameters are dynamic
properties on that link, in the "BruceWorx Pattern" group, so the pattern is
saved with the document and can be edited again. Because the array is a plain
``App::Link``, the Assembly workbench treats every element as a component
(``UtilsAssembly.isLinkGroup``).

The seed itself stays where it is; the array holds the other instances only.
Instance keys are index tuples: ``(i, j)`` for rectangular patterns and
``(k,)`` for circular ones. ``(0, 0)`` / ``(0,)`` is the seed.

* Symmetric directions use indices ``-floor((n-1)/2) .. ceil((n-1)/2)``.
* Suppressed instances keep their element (so indices stay stable) and are
  hidden with ``setElementVisible``, which also drops them from the shape.
* Instance placement is ``g_k * P0`` (world-frame transform times the seed
  placement), computed in the seed's parent coordinate system.

Independent copies are not parametric: bodies and solids become
``Part::Feature`` solids; components and App::Part containers become
separate ``App::Link`` objects.

PartDesign *features* are not handled here: the commands hand them to
PartDesign's own Linear/Polar Pattern.
"""

from __future__ import annotations

GROUP = "BruceWorx Pattern"
RECTANGULAR = "Rectangular"
CIRCULAR = "Circular"
DISTANCE_TYPES = ["Spacing", "Extent"]
CIRCULAR_TYPES = ["Full", "Angle", "Symmetric"]


# ---------------------------------------------------------------------------
# Pure math (no FreeCAD needed).


def index_set(count, symmetric=False):
    """Instance indices along one direction, the seed being 0."""
    count = max(1, int(count))
    if not symmetric:
        return list(range(count))
    low = -((count - 1) // 2)
    high = (count - 1) - (count - 1) // 2
    return list(range(low, high + 1))


def step(count, distance, distance_type):
    """Distance between neighbouring instances along one direction."""
    count = max(1, int(count))
    if distance_type == "Extent":
        return distance / (count - 1) if count > 1 else 0.0
    return float(distance)


def rectangular_offsets(params):
    """``{(i, j): (d1, d2)}`` distances along direction 1 and 2."""
    s1 = step(params["count1"], params["distance1"], params["type1"])
    s2 = step(params["count2"], params["distance2"], params["type2"])
    offsets = {}
    for i in index_set(params["count1"], params["symmetric1"]):
        for j in index_set(params["count2"], params["symmetric2"]):
            offsets[(i, j)] = (i * s1, j * s2)
    return offsets


def circular_angles(params):
    """``{(k,): angle_in_degrees}``.

    Full divides 360 by n (360 is the same as 0); Angle and Symmetric divide
    the total angle by n - 1 so both ends get an instance.
    """
    count = max(1, int(params["count1"]))
    kind = params["circular_type"]
    if kind == "Full":
        return {(k,): 360.0 * k / count for k in range(count)}
    total = float(params["angle"])
    each = total / (count - 1) if count > 1 else 0.0
    symmetric = kind == "Symmetric"
    return {(k,): each * k for k in index_set(count, symmetric)}


def seed_key(kind):
    return (0, 0) if kind == RECTANGULAR else (0,)


def key_to_text(key):
    return ",".join(str(v) for v in key)


def text_to_key(text):
    return tuple(int(v) for v in text.split(",") if v.strip() != "")


def classify_selection(objects):
    """'features' when every object is a PartDesign feature, 'objects' when none
    is, 'mixed' otherwise, 'empty' for no selection."""
    if not objects:
        return "empty"
    features = [_is_partdesign_feature(o) for o in objects]
    if all(features):
        return "features"
    if not any(features):
        return "objects"
    return "mixed"


def _is_partdesign_feature(obj):
    try:
        return obj.isDerivedFrom("PartDesign::Feature") and not obj.isDerivedFrom("PartDesign::Body")
    except Exception:
        return False


# ---------------------------------------------------------------------------
# FreeCAD side.


def _app():
    import FreeCAD

    return FreeCAD


def default_params(kind):
    App = _app()
    return {
        "kind": kind,
        "direction1": App.Vector(1, 0, 0),
        "direction2": App.Vector(0, 1, 0),
        "count1": 3 if kind == RECTANGULAR else 6,
        "count2": 1,
        "distance1": 20.0,
        "distance2": 20.0,
        "type1": "Spacing",
        "type2": "Spacing",
        "symmetric1": False,
        "symmetric2": False,
        "axis_base": App.Vector(0, 0, 0),
        "axis_direction": App.Vector(0, 0, 1),
        "circular_type": "Full",
        "angle": 360.0,
        "suppressed": [],
    }


def transforms(params):
    """``[(key, App.Placement g)]`` for every instance, seed included."""
    App = _app()
    out = []
    if params["kind"] == RECTANGULAR:
        u1 = App.Vector(params["direction1"])
        u2 = App.Vector(params["direction2"])
        if u1.Length < 1e-12:
            raise ValueError("Direction 1 has zero length")
        u1.normalize()
        if params["count2"] > 1:
            if u2.Length < 1e-12:
                raise ValueError("Direction 2 has zero length")
            u2.normalize()
            if abs(abs(u1.dot(u2)) - 1.0) < 1e-9:
                raise ValueError("Direction 1 and direction 2 are parallel")
        for key, (d1, d2) in sorted(rectangular_offsets(params).items()):
            out.append((key, App.Placement(u1 * d1 + u2 * d2, App.Rotation())))
        return out
    axis = App.Vector(params["axis_direction"])
    if axis.Length < 1e-12:
        raise ValueError("Axis has zero length")
    axis.normalize()
    centre = App.Vector(params["axis_base"])
    for key, angle in sorted(circular_angles(params).items()):
        # Placement(base, rotation, centre) rotates about ``centre``.
        out.append((key, App.Placement(App.Vector(), App.Rotation(axis, angle), centre)))
    return out


def instance_placements(params, seed_placement):
    """``[(key, placement)]`` for the generated instances (seed excluded)."""
    skip = seed_key(params["kind"])
    return [(key, g.multiply(seed_placement)) for key, g in transforms(params) if key != skip]


def linked_target(seed):
    """What the array links to: the part behind a component link, else the seed."""
    if seed.isDerivedFrom("App::Link") and seed.ElementCount == 0:
        target = seed.LinkedObject
        if target is not None:
            return target
    return seed


def parent_of(seed):
    try:
        return seed.getParentGeoFeatureGroup()
    except Exception:
        return None


# Dynamic properties on the array: (name, type, default-key, tooltip).
_PROPS = [
    ("PatternType", "App::PropertyEnumeration", None, "Rectangular or circular."),
    ("PatternSeed", "App::PropertyLinkHidden", None, "The body or component being patterned."),
    ("Direction1", "App::PropertyVector", "direction1", "Direction 1 (parent coordinates)."),
    ("Count1", "App::PropertyInteger", "count1", "Instances along direction 1, or around the axis, seed included."),
    ("Distance1", "App::PropertyDistance", "distance1", "Spacing or extent along direction 1."),
    ("DistanceType1", "App::PropertyEnumeration", None, "Spacing: gap between instances. Extent: total length."),
    ("Symmetric1", "App::PropertyBool", "symmetric1", "Spread direction 1 on both sides of the seed."),
    ("Direction2", "App::PropertyVector", "direction2", "Direction 2 (parent coordinates)."),
    ("Count2", "App::PropertyInteger", "count2", "Instances along direction 2; 1 turns direction 2 off."),
    ("Distance2", "App::PropertyDistance", "distance2", "Spacing or extent along direction 2."),
    ("DistanceType2", "App::PropertyEnumeration", None, "Spacing: gap between instances. Extent: total length."),
    ("Symmetric2", "App::PropertyBool", "symmetric2", "Spread direction 2 on both sides of the seed."),
    ("AxisBase", "App::PropertyVector", "axis_base", "A point on the circular pattern axis."),
    ("AxisDirection", "App::PropertyVector", "axis_direction", "Circular pattern axis direction."),
    ("CircularType", "App::PropertyEnumeration", None, "Full circle, total angle, or symmetric about the seed."),
    ("Angle", "App::PropertyAngle", "angle", "Total angle for Angle and Symmetric."),
    ("Suppressed", "App::PropertyStringList", None, "Suppressed instance keys, e.g. '1,0'."),
    ("InstanceKeys", "App::PropertyStringList", None, "Key of each array element, in element order."),
]


def is_pattern(obj):
    return obj is not None and hasattr(obj, "PropertiesList") and "PatternType" in obj.PropertiesList \
        and obj.getGroupOfProperty("PatternType") == GROUP


def _ensure_props(array):
    present = set(array.PropertiesList)
    for name, typ, _default, tip in _PROPS:
        if name not in present:
            array.addProperty(typ, name, GROUP, tip)
    array.PatternType = [RECTANGULAR, CIRCULAR]
    array.DistanceType1 = DISTANCE_TYPES
    array.DistanceType2 = DISTANCE_TYPES
    array.CircularType = CIRCULAR_TYPES
    array.setEditorMode("InstanceKeys", 1)


def write_params(array, params):
    _ensure_props(array)
    array.PatternType = params["kind"]
    for name, _typ, key, _tip in _PROPS:
        if key is not None:
            setattr(array, name, params[key])
    array.DistanceType1 = params["type1"]
    array.DistanceType2 = params["type2"]
    array.CircularType = params["circular_type"]
    array.Suppressed = [key_to_text(k) for k in params["suppressed"]]


def read_params(array):
    params = default_params(array.PatternType)
    for name, _typ, key, _tip in _PROPS:
        if key is None:
            continue
        value = getattr(array, name)
        if hasattr(value, "Value"):  # Quantity
            value = value.Value
        params[key] = value
    params["type1"] = array.DistanceType1
    params["type2"] = array.DistanceType2
    params["circular_type"] = array.CircularType
    params["suppressed"] = [text_to_key(t) for t in array.Suppressed]
    return params


def apply(array):
    """Recompute element count, placements and visibility from the parameters."""
    params = read_params(array)
    seed = array.PatternSeed
    if seed is None:
        raise ValueError(f"{array.Label}: the pattern has no seed")
    placed = instance_placements(params, seed.Placement)
    if array.ElementCount != len(placed):
        array.ElementCount = len(placed)
    suppressed = {tuple(k) for k in params["suppressed"]}
    elements = array.ElementList
    for index, (key, placement) in enumerate(placed):
        element = elements[index]
        if not element.Placement.isSame(placement, 1e-9):
            element.Placement = placement
        visible = key not in suppressed
        if bool(array.isElementVisible(str(index))) != visible:
            array.setElementVisible(str(index), visible)
    keys = [key_to_text(k) for k, _p in placed]
    if list(array.InstanceKeys) != keys:
        array.InstanceKeys = keys
    return placed


def create_linked(seed, params, doc=None):
    """Create a linked pattern of ``seed``. Returns the ``App::Link`` array."""
    doc = doc or seed.Document
    array = doc.addObject("App::Link", "Pattern")
    array.Label = f"{seed.Label} pattern"
    array.LinkedObject = linked_target(seed)
    write_params(array, params)
    array.PatternSeed = seed
    parent = parent_of(seed)
    if parent is not None:
        parent.addObject(array)
    apply(array)
    return array


def create_independent(seed, params, doc=None):
    """Create independent copies. Returns the new objects (not parametric)."""
    doc = doc or seed.Document
    parent = parent_of(seed)
    suppressed = {tuple(k) for k in params["suppressed"]}
    created = []
    # Solids are copied; components and containers (App::Part) become links.
    as_solid = seed.isDerivedFrom("Part::Feature")
    for key, placement in instance_placements(params, seed.Placement):
        if key in suppressed:
            continue
        name = f"{seed.Label} {key_to_text(key)}"
        if not as_solid:
            obj = doc.addObject("App::Link", "PatternInstance")
            obj.LinkedObject = linked_target(seed)
            obj.Placement = placement
        else:
            obj = doc.addObject("Part::Feature", "PatternInstance")
            shape = seed.Shape.copy()
            shape.Placement = placement
            obj.Shape = shape
            _copy_view_style(seed, obj)
        obj.Label = name
        if parent is not None:
            parent.addObject(obj)
        created.append(obj)
    return created


def make_independent(array):
    """Replace a linked pattern by independent copies; returns the copies."""
    params = read_params(array)
    seed = array.PatternSeed
    doc = array.Document
    copies = create_independent(seed, params, doc)
    doc.removeObject(array.Name)
    return copies


def _copy_view_style(src, dst):
    try:
        if src.ViewObject is not None and dst.ViewObject is not None:
            dst.ViewObject.ShapeAppearance = src.ViewObject.ShapeAppearance
    except Exception:
        pass


def patterns_of(seed):
    """Linked patterns whose seed is ``seed``."""
    found = []
    for obj in seed.InList:
        if is_pattern(obj) and obj.PatternSeed == seed:
            found.append(obj)
    return found


def describe_key(params, key):
    """Short label for the suppress list."""
    if params["kind"] == RECTANGULAR:
        return f"({key[0]}, {key[1]})"
    angle = circular_angles(params).get(tuple(key), 0.0)
    return f"#{key[0]}  {angle:.1f}°"
