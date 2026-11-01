# SPDX-License-Identifier: LGPL-2.1-or-later
"""Make external: one part per file (BW-ASM-01). Needs FreeCAD.

Takes a design file that holds several bodies (the Fusion way of working)
and splits it the SolidWorks way: every body becomes its own part file, and
the design file becomes an assembly that links those files.

For each body (or other solid root):

1. A new document gets a copy of the body and everything it depends on,
   inside an ``App::Part`` container. The body's placement moves to the link,
   so the part file is modelled about its own origin. The container gets the
   BruceWorx part properties (``partprops``) and, when numbering is used, its
   part number.
2. The part file is saved, then an ``App::Link`` to its container replaces
   the body in the assembly, in the same group and at the same place.
3. Everything that pointed at the body is moved to the link: assembly
   joints (``Reference1``/``Reference2`` become ``(link, ["Body.Face6"])``),
   grounded joints, and other links to the body (patterns, repeated
   components). Anything else that depends on the body stops the run before
   a file is written; pass ``objects`` to leave such bodies alone.
4. The body and the objects only it used are removed from the assembly.

The input file is never written: the assembly is saved under a new name
first. Links are stored relative to the assembly (``filerefs``), so the
output folder can be moved or packed as a whole.
"""

from __future__ import annotations

import os
import re

from bruceworx import filerefs
from bruceworx.numbering import part_objects

SCHEMA = "bruceworx.make-external.v1"
CONTAINER_TYPES = ("App::Part",)
# Objects whose own Placement can move to the link without changing what the
# rest of the copy computes.
_MOVABLE_PLACEMENT = ("PartDesign::Body", "App::Part")


class MakeExternalError(RuntimeError):
    """The document cannot be split as asked. Nothing was written."""


def safe_file_stem(text: str) -> str:
    """A file name from a label: keeps letters, digits, ``-``, ``_`` and ``.``."""
    stem = re.sub(r"[^\w.-]+", "_", str(text).strip(), flags=re.UNICODE).strip("._")
    return stem or "Part"


def plan_targets(doc, names: list[str] | None = None) -> list:
    """Bodies and other solid roots to make external. Links (already
    external, or instances of a body) and assembly containers are skipped."""
    if names:
        return [o for o in part_objects(doc, names) if not _skipped(o)]
    # part_objects would stop at the Assembly (it has a shape and holds the
    # bodies). Look through assemblies and groups: a target is a solid that
    # no other solid target owns.
    candidates = [o for o in doc.Objects if not _skipped(o) and _has_solid(o)]
    kept = {o.Name for o in candidates}
    owned = set()
    for obj in candidates:
        for child in obj.OutListRecursive:
            if child.Name in kept and child.Name != obj.Name:
                owned.add(child.Name)
    return [o for o in candidates if o.Name not in owned]


def _skipped(obj) -> bool:
    return (
        _is_link(obj)
        or obj.isDerivedFrom("Assembly::AssemblyObject")
        or obj.isDerivedFrom("App::Part")
        or obj.isDerivedFrom("App::DocumentObjectGroup")
    )


def _has_solid(obj) -> bool:
    shape = getattr(obj, "Shape", None)
    try:
        return shape is not None and not shape.isNull() and bool(shape.Solids)
    except Exception:  # noqa: BLE001 — not a Part shape
        return False


def blocking_dependents(doc, targets) -> dict[str, list[str]]:
    """Objects outside ``targets`` that use a target in a way this module
    cannot move to the link. Empty means the split is safe."""
    target_names = {t.Name for t in targets}
    blocking = {}
    for target in targets:
        owned = {o.Name for o in _owned(target)}
        bad = []
        for user in target.InList:
            if user.Name in target_names or user.Name in owned:
                continue
            if _handled_user(user, target):
                continue
            bad.append(f"{user.Name} ({user.Label}, {user.TypeId})")
        if bad:
            blocking[target.Name] = sorted(set(bad))
    return blocking


def make_external(
    doc,
    output_dir: str,
    *,
    objects: list[str] | None = None,
    numbers: list[str] | None = None,
    assembly_file: str | None = None,
    parts_dir: str = "",
    schema=None,
    overwrite: bool = False,
    create_assembly: bool = True,
) -> dict:
    """Split ``doc`` into part files plus an assembly. See the module doc.

    ``numbers``: optional part numbers, the assembly's first and then one per
    target in :func:`plan_targets` order. They name the files (without the
    revision, which is metadata) and fill ``PartNumber``. Without numbers the
    labels name the files.

    ``schema``: a ``partprops.Schema``; ``None`` loads the default layers.
    ``False`` skips part properties.

    Returns a JSON-ready report. Part documents are closed; ``doc`` is left
    open as the saved assembly.
    """
    import FreeCAD  # noqa: PLC0415

    targets = plan_targets(doc, objects)
    if not targets:
        raise MakeExternalError("no bodies or solids to make external")
    if numbers is not None and len(numbers) != len(targets) + 1:
        raise MakeExternalError(
            f"need {len(targets) + 1} part numbers (assembly + {len(targets)} parts), got {len(numbers)}"
        )
    blocking = blocking_dependents(doc, targets)
    if blocking:
        lines = [f"{name}: used by {', '.join(users)}" for name, users in blocking.items()]
        raise MakeExternalError(
            "these bodies are used by objects that cannot follow them into another file "
            "(leave them out with --objects): " + "; ".join(lines)
        )
    if schema is None:
        from bruceworx.partprops import load_schema  # noqa: PLC0415

        schema = load_schema()

    output_dir = os.path.abspath(output_dir)
    base_numbers = [_without_revision(n) for n in numbers] if numbers else None
    stems = _unique_stems(
        [base_numbers[0] if base_numbers else _assembly_stem(doc)]
        + (base_numbers[1:] if base_numbers else [t.Label for t in targets])
    )
    asm_path = os.path.abspath(assembly_file) if assembly_file else os.path.join(output_dir, stems[0] + ".FCStd")
    part_paths = [os.path.join(output_dir, parts_dir, s + ".FCStd") for s in stems[1:]]
    source = os.path.abspath(doc.FileName) if doc.FileName else ""
    for path in [asm_path] + part_paths:
        if source and os.path.normcase(path) == os.path.normcase(source):
            raise MakeExternalError(f"refusing to overwrite the input file {path}")
        if os.path.exists(path) and not overwrite:
            raise MakeExternalError(f"{path} exists (pass overwrite to replace it)")

    shared = _shared_dependencies(targets)
    os.makedirs(os.path.dirname(asm_path), exist_ok=True)
    doc.saveAs(asm_path)  # the input stays as it was

    assembly = _assembly_for(doc, targets, create_assembly)
    parts = []
    first_link = None
    for index, (target, path) in enumerate(zip(targets, part_paths)):
        number = base_numbers[index + 1] if base_numbers else ""
        label, name = target.Label, target.Name
        container, inner, placement = _write_part_file(FreeCAD, target, path, number, schema)
        link = _replace_with_link(doc, target, container, inner, placement, assembly)
        _remove_original(doc, target)
        link.Label = label  # free now that the body is gone
        if first_link is None:
            first_link = link
        parts.append(
            {
                "object": name,
                "label": link.Label,
                "file": path,
                "link": link.Name,
                "part_number": number,
                "stored_path": filerefs.relative_link(asm_path, path),
            }
        )

    grounded = False
    if assembly is not None and first_link is not None and create_assembly:
        grounded = _ground_if_needed(assembly, first_link)
    if base_numbers:
        _number_assembly(doc, assembly, base_numbers[0], schema)
    doc.recompute()
    doc.save()
    for part in parts:
        _close_by_file(FreeCAD, part["file"])
    graph = filerefs.walk(asm_path)
    return {
        "schema": SCHEMA,
        "ok": graph.ok,
        "input": source,
        "assembly": asm_path,
        "assembly_object": assembly.Name if assembly is not None else "",
        "grounded": grounded,
        "parts": parts,
        "shared_dependencies": shared,
        "references": graph.as_json()["references"],
    }


# ----- steps -----------------------------------------------------------------


def _write_part_file(FreeCAD, target, path, number, schema):
    """Copy ``target`` into a new document inside an App::Part and save it.
    Returns (container, name of the copy inside it, placement for the link)."""
    part_doc = FreeCAD.newDocument(safe_file_stem(os.path.splitext(os.path.basename(path))[0]))
    # Copying anything that carries a link property needs a saved target document.
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part_doc.saveAs(path)
    copied = part_doc.copyObject(target, True)
    copies = copied if isinstance(copied, (list, tuple)) else [copied]
    copy = next((c for c in copies if c.Label == target.Label and c.TypeId == target.TypeId), copies[-1])
    placement = FreeCAD.Placement()
    if target.TypeId in _MOVABLE_PLACEMENT or not _has_shape_inputs(target):
        placement = FreeCAD.Placement(target.Placement)
        copy.Placement = FreeCAD.Placement()
    container = part_doc.addObject("App::Part", "Part")
    container.Label = number or target.Label
    container.addObject(copy)
    # Loose copies (a sketch the body used, a spreadsheet) go in as well, so
    # the container is the whole part.
    for other in copies:
        if other is not copy and other.getParentGeoFeatureGroup() is None and other.isDerivedFrom("App::GeoFeature"):
            container.addObject(other)
    if schema:
        schema.apply(container, compute=False)
        if number and "PartNumber" in container.PropertiesList:
            container.PartNumber = number
        if "ItemType" in container.PropertiesList:
            container.ItemType = "part"
    part_doc.recompute()
    if schema:
        schema.apply(container, compute=True)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    part_doc.saveAs(path)
    return container, copy.Name, placement


def _replace_with_link(doc, target, container, inner, placement, assembly):
    link = doc.addObject("App::Link", "Link")
    link.setLink(container)
    link.Label = target.Label
    link.Placement = placement
    parent = target.getParentGeoFeatureGroup() or _parent_group(target)
    if parent is None and assembly is not None:
        parent = assembly
    if parent is not None and link not in getattr(parent, "Group", []):
        parent.addObject(link)
    try:
        link.Visibility = target.Visibility
    except Exception:  # noqa: BLE001 — headless documents may lack it
        pass
    _retarget_users(doc, target, link, container, inner)
    return link


def _retarget_users(doc, target, link, container, inner):
    """Point joints, grounds and in-document links at the new link."""
    retargeted_links = []
    for user in list(target.InList):
        if _is_link(user) and user is not link and _linked(user) is target:
            user.setLink(container)
            retargeted_links.append(user)
    for joint in doc.Objects:
        for prop in ("Reference1", "Reference2"):
            if prop not in joint.PropertiesList:
                continue
            ref = getattr(joint, prop)
            new = _rewrite_reference(ref, target, link, inner, retargeted_links)
            if new is not None:
                setattr(joint, prop, new)
        if "ObjectToGround" in joint.PropertiesList and joint.ObjectToGround is target:
            joint.ObjectToGround = link


def _rewrite_reference(ref, target, link, inner, retargeted_links):
    """``ref`` is (object, [subnames]). Returns the rewritten tuple, or None
    when it does not involve ``target``."""
    if not ref or ref[0] is None:
        return None
    owner, subs = ref[0], list(ref[1] or [])
    if owner is target:
        return (link, [f"{inner}.{s}" if s else inner + "." for s in subs])
    if owner in retargeted_links:
        # A link to the body now links the container: element names move one
        # level down, after the array index for link arrays ("Pattern.2.Face3").
        return (owner, [_insert_inner(owner, s, inner) for s in subs])
    # Older files root the reference at the assembly: "Body.Face6".
    prefix = target.Name + "."
    if any(s.startswith(prefix) for s in subs):
        return (owner, [f"{link.Name}.{inner}.{s[len(prefix):]}" if s.startswith(prefix) else s for s in subs])
    return None


def _insert_inner(link_obj, sub, inner):
    count = getattr(link_obj, "ElementCount", 0) or 0
    head, _, rest = sub.partition(".")
    if count and head.isdigit():
        return f"{head}.{inner}.{rest}"
    return f"{inner}.{sub}"


def _remove_original(doc, target):
    """Delete ``target`` and the objects that only it used."""
    if not _alive(target):
        return
    owned = [o for o in _owned(target) if _alive(o)]
    doomed = {target.Name} | {o.Name for o in owned}
    if target.isDerivedFrom("PartDesign::Body"):
        target.removeObjectsFromDocument()
    name = target.Name
    doc.removeObject(name)
    # Remove what is left, users first, so nothing is orphaned mid-way.
    for _round in range(len(doomed) + 1):
        left = [doc.getObject(n) for n in doomed if doc.getObject(n) is not None]
        if not left:
            break
        for obj in left:
            if all(u.Name in doomed for u in obj.InList):
                doc.removeObject(obj.Name)


def _assembly_for(doc, targets, create):
    """The Assembly the links go into: the one that already holds a target,
    else the only one in the document, else a new one (``create``)."""
    assemblies = [o for o in doc.Objects if o.isDerivedFrom("Assembly::AssemblyObject")]
    for target in targets:
        for asm in assemblies:
            if target in asm.OutListRecursive:
                return asm
    if len(assemblies) == 1:
        return assemblies[0]
    if not create:
        return None
    try:
        assembly = doc.addObject("Assembly::AssemblyObject", "Assembly")
    except Exception:  # noqa: BLE001 — Assembly module not built
        return None
    assembly.Type = "Assembly"
    assembly.newObject("Assembly::JointGroup", "Joints")
    return assembly


def _ground_if_needed(assembly, link) -> bool:
    """Ground the first part, as Insert Component does, when nothing is
    grounded yet. Best effort: needs the Assembly Python module."""
    joints = [o for o in assembly.OutListRecursive if o.isDerivedFrom("Assembly::JointGroup")]
    if not joints:
        return False
    group = joints[0]
    for joint in group.Group:
        if "ObjectToGround" in joint.PropertiesList:
            return False
    try:
        import JointObject  # noqa: PLC0415
    except Exception:  # noqa: BLE001 — headless build without pivy
        return False
    ground = group.newObject("App::FeaturePython", "GroundedJoint")
    JointObject.GroundedJoint(ground, link)
    return True


def _number_assembly(doc, assembly, number, schema):
    doc.Label = number
    if assembly is None:
        return
    assembly.Label = number
    if schema:
        schema.apply(assembly, compute=False)
        if "PartNumber" in assembly.PropertiesList:
            assembly.PartNumber = number
        if "ItemType" in assembly.PropertiesList:
            assembly.ItemType = "assembly"


# ----- helpers ---------------------------------------------------------------


def _owned(target) -> list:
    """Objects ``target`` uses that nothing outside ``target`` uses."""
    deps = list(target.OutListRecursive)
    inside = {target.Name} | {d.Name for d in deps}
    owned = []
    for dep in deps:
        if all(user.Name in inside for user in dep.InList):
            owned.append(dep)
    return owned


def _shared_dependencies(targets) -> list[dict]:
    """Objects that two or more targets depend on: each part file gets its
    own copy, so later edits to one no longer reach the others."""
    users: dict[str, list[str]] = {}
    labels = {}
    for target in targets:
        for dep in target.OutListRecursive:
            if dep.isDerivedFrom("App::Origin") or dep.isDerivedFrom("App::DatumElement"):
                continue
            users.setdefault(dep.Name, []).append(target.Name)
            labels[dep.Name] = dep.Label
    return [
        {"object": name, "label": labels[name], "used_by": names}
        for name, names in users.items()
        if len(names) > 1
    ]


def _handled_user(user, target) -> bool:
    if user.isDerivedFrom("App::Part") or user.isDerivedFrom("App::DocumentObjectGroup"):
        return True
    if user.isDerivedFrom("Assembly::AssemblyObject") or user.isDerivedFrom("Assembly::JointGroup"):
        return True
    if _is_link(user) and _linked(user) is target:
        return True
    props = user.PropertiesList
    if "Reference1" in props or "Reference2" in props or "ObjectToGround" in props:
        return True
    return False


def _has_shape_inputs(obj) -> bool:
    return any(dep.isDerivedFrom("Part::Feature") for dep in obj.OutList)


def _is_link(obj) -> bool:
    return obj.isDerivedFrom("App::Link") or obj.isDerivedFrom("App::LinkElement")


def _linked(link):
    try:
        return link.LinkedObject
    except AttributeError:
        return None


def _parent_group(obj):
    for user in obj.InList:
        if user.isDerivedFrom("App::DocumentObjectGroup") and obj in user.Group:
            return user
    return None


def _alive(obj) -> bool:
    try:
        return obj.Document is not None and obj.Document.getObject(obj.Name) is obj
    except Exception:  # noqa: BLE001 — deleted object
        return False


def _close_by_file(FreeCAD, path):
    for doc in list(FreeCAD.listDocuments().values()):
        if doc.FileName and os.path.normcase(os.path.abspath(doc.FileName)) == os.path.normcase(path):
            FreeCAD.closeDocument(doc.Name)


def _assembly_stem(doc) -> str:
    if doc.FileName:
        return safe_file_stem(os.path.splitext(os.path.basename(doc.FileName))[0]) + "_asm"
    return safe_file_stem(doc.Label) + "_asm"


def _unique_stems(stems: list[str]) -> list[str]:
    out, seen = [], set()
    for stem in stems:
        stem = safe_file_stem(stem)
        candidate, n = stem, 2
        while candidate.lower() in seen:
            candidate = f"{stem}_{n}"
            n += 1
        seen.add(candidate.lower())
        out.append(candidate)
    return out


def _without_revision(number: str) -> str:
    """``LE-01-01001-002-A`` -> ``LE-01-01001-002``. The revision is
    metadata (roadmap decision): it does not name the file or fill
    PartNumber."""
    from bruceworx.numbering import parse_part_number  # noqa: PLC0415

    fields = parse_part_number(number)
    return "-".join(fields[k] for k in ("program", "document_type", "parent", "sub"))
