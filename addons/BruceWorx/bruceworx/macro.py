# SPDX-License-Identifier: LGPL-2.1-or-later
"""Part-number macro used by the GUI and by ``macros/PartNumber.FCMacro``."""

from __future__ import annotations

import os

from bruceworx.config_path import resolve_config_path
from bruceworx.numbering import assign_part_numbers, part_objects
from bruceworx.sources import open_number_source


def run(
    program: str | None = None,
    document_type: str | None = None,
    config: str | None = None,
    revision: str | None = None,
    parent: str | None = None,
    doc=None,
    objects=None,
):
    """Number ``doc`` (default: the active FreeCAD document).

    Object choice, in order: explicit ``objects``, the GUI selection, then
    solid roots from :func:`part_objects`. Program choice: argument,
    ``BW_PROGRAM``, then the only program in the numbering file. Document
    type: argument, ``BW_DOCUMENT_TYPE`` or ``BW_DT``, then the only type in
    the table. ``BW_PARENT`` continues a parent drawing instead of taking a
    new ``PPPPP``.
    """
    if doc is None:
        doc = active_document()
    if objects is None:
        selected = selected_objects()
        if selected:
            objects = selected
    source = open_number_source(resolve_config_path(config, write=True))
    if not program:
        program = os.environ.get("BW_PROGRAM") or sole_program(source)
    if not document_type:
        document_type = (
            os.environ.get("BW_DOCUMENT_TYPE")
            or os.environ.get("BW_DT")
            or sole_document_type(source)
        )
    if not parent:
        parent = os.environ.get("BW_PARENT") or None
    return assign_part_numbers(
        doc,
        source,
        program,
        document_type,
        objects=objects,
        revision=revision,
        parent=parent,
    )


def sole_document_type(source) -> str:
    codes = list(source.document_types())
    if len(codes) == 1:
        return codes[0]
    if not codes:
        raise ValueError("set BW_DOCUMENT_TYPE; this source lists no document types")
    raise ValueError(
        "set BW_DOCUMENT_TYPE to a 2-digit code; the table has " + ", ".join(codes)
    )


def sole_program(source) -> str:
    codes = list(source.programs())
    if len(codes) == 1:
        return codes[0]
    if not codes:
        raise ValueError("set BW_PROGRAM or pass a program code; this source lists none")
    raise ValueError(
        "set BW_PROGRAM or pass a program code; numbering file has "
        + ", ".join(codes)
    )


def active_document():
    import FreeCAD  # noqa: PLC0415

    doc = FreeCAD.ActiveDocument
    if doc is None:
        raise RuntimeError("No active document. Open a part, then run the macro.")
    return doc


def selected_objects() -> list:
    """GUI selection, or an empty list under FreeCADCmd."""
    try:
        import FreeCAD  # noqa: PLC0415
        import FreeCADGui  # noqa: PLC0415
    except ImportError:
        return []
    if not getattr(FreeCAD, "GuiUp", False):
        return []
    return list(FreeCADGui.Selection.getSelection())


def default_objects(doc):
    """Solid roots. Exposed for tests and scripts."""
    return part_objects(doc)
