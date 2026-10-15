# SPDX-License-Identifier: LGPL-2.1-or-later
"""Part numbers in the BruceWorx form ``{PROG}-{NNNNN}-{REV}``.

Example: ``LE-01001-A``.

The sequence is always five digits. ``PROG`` is 1 to 8 characters, starting
with a letter. ``REV`` is 1 to 3 letters. Callers pass a :class:`NumberSource`
(JSON today, BruceWorx Ops API later) and do not care where the next number
came from.
"""

from __future__ import annotations

import re

PART_NUMBER_FORMAT = "{PROG}-{NNNNN}-{REV}"
NUMBER_WIDTH = 5
_PROGRAM_RE = re.compile(r"[A-Z][A-Z0-9]{0,7}\Z")
_REVISION_RE = re.compile(r"[A-Z]{1,3}\Z")
PART_NUMBER_RE = re.compile(r"[A-Z][A-Z0-9]{0,7}-\d{5}-[A-Z]{1,3}\Z")


def normalize_program(program: str) -> str:
    """Return the canonical program code, or raise ValueError."""
    text = str(program).strip().upper()
    if not _PROGRAM_RE.fullmatch(text):
        raise ValueError(
            f"program {program!r} must be 1-8 letters or digits and start with a letter"
        )
    return text


def normalize_revision(revision: str) -> str:
    """Return the canonical revision, or raise ValueError."""
    text = str(revision).strip().upper()
    if not _REVISION_RE.fullmatch(text):
        raise ValueError(f"revision {revision!r} must be 1-3 letters")
    return text


def format_part_number(program: str, number: int, revision: str) -> str:
    """Format one part number. ``number`` is the sequence before padding."""
    program = normalize_program(program)
    revision = normalize_revision(revision)
    if isinstance(number, bool) or not isinstance(number, int):
        raise ValueError(f"sequence number must be an integer, got {number!r}")
    if number < 0 or number > 99999:
        raise ValueError(f"sequence number {number} is outside 0..99999")
    formatted = f"{program}-{number:0{NUMBER_WIDTH}d}-{revision}"
    if not PART_NUMBER_RE.fullmatch(formatted):
        raise ValueError(f"refusing to emit invalid part number {formatted!r}")
    return formatted


def part_objects(doc, names: list[str] | None = None) -> list:
    """Solid objects to number or export.

    Explicit ``names`` match ``Name`` or ``Label``. Otherwise keep objects
    that own a solid and drop anything that is a child of another kept
    object, so a PartDesign Body is numbered and its Pad is not.
    """
    objects = list(getattr(doc, "Objects", []) or [])
    if names:
        return _resolve_names(objects, names)
    candidates = [obj for obj in objects if _has_solid(obj)]
    child_names = set()
    kept = {obj.Name for obj in candidates}
    for obj in candidates:
        for child in getattr(obj, "OutList", None) or []:
            child_name = getattr(child, "Name", None)
            if child_name in kept:
                child_names.add(child_name)
    return [obj for obj in candidates if obj.Name not in child_names]


def assign_part_numbers(doc, source, program: str, objects=None, revision: str | None = None):
    """Set object Labels and the document Label from ``source``.

    ``objects`` None selects :func:`part_objects`. An empty selection still
    numbers the document Label, using a single allocated number.

    Returns a dict suitable for JSON. Does not save the document.
    """
    targets = part_objects(doc) if objects is None else list(objects)
    if not targets:
        number = source.allocate(program, revision)
        doc.Label = number
        return {
            "document_name": doc.Name,
            "document_label": doc.Label,
            "assignments": [],
            "part_number": number,
        }

    assignments = []
    first = None
    for obj in targets:
        number = source.allocate(program, revision)
        if first is None:
            first = number
        old_label = getattr(obj, "Label", "")
        obj.Label = number
        assignments.append(
            {
                "name": obj.Name,
                "old_label": old_label,
                "part_number": number,
            }
        )
    doc.Label = first
    return {
        "document_name": doc.Name,
        "document_label": doc.Label,
        "assignments": assignments,
        "part_number": first,
    }


def _resolve_names(objects, names: list[str]) -> list:
    wanted = []
    for name in names:
        text = str(name).strip()
        if text:
            wanted.append(text)
    if not wanted:
        raise ValueError("object list is empty")
    found = []
    missing = []
    for text in wanted:
        match = None
        for obj in objects:
            if obj.Name == text or getattr(obj, "Label", None) == text:
                match = obj
                break
        if match is None:
            missing.append(text)
        else:
            found.append(match)
    if missing:
        known = ", ".join(sorted(obj.Name for obj in objects))
        raise ValueError(f"objects not found: {', '.join(missing)} (known names: {known})")
    return found


def _has_solid(obj) -> bool:
    shape = getattr(obj, "Shape", None)
    if shape is None:
        return False
    is_null = getattr(shape, "isNull", None)
    if callable(is_null) and is_null():
        return False
    solids = getattr(shape, "Solids", None)
    if solids is None:
        # Test doubles stand in for a solid when they don't model Solids.
        return True
    try:
        return len(solids) > 0
    except TypeError:
        return False
