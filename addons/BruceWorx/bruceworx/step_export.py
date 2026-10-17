# SPDX-License-Identifier: LGPL-2.1-or-later
"""Choose solids and hand them to a STEP exporter.

The exporter is injected in tests. Under FreeCADCmd the default exporter is
:func:`bruceworx.freecad_io.export_step`.
"""

from __future__ import annotations

import os

from bruceworx.numbering import part_objects


def export_step(doc, output_path: str, objects=None, exporter=None) -> dict:
    """Export solids from ``doc`` to a ``.step`` or ``.stp`` file.

    Recomputes the document first when it offers ``recompute``, so a box that
    was just created has a shape. Returns the names that were exported.
    """
    output_path = os.path.abspath(output_path)
    _require_step_path(output_path)
    if hasattr(doc, "recompute"):
        doc.recompute()
    chosen = part_objects(doc) if objects is None else list(objects)
    if not chosen:
        raise ValueError("no solid objects to export; pass --objects Name,Label")
    directory = os.path.dirname(output_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if exporter is None:
        from bruceworx.freecad_io import export_step as exporter  # noqa: PLC0415
    exporter(chosen, output_path)
    if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError(f"STEP export wrote no data to {output_path}")
    return {
        "output": output_path,
        "objects": [obj.Name for obj in chosen],
    }


def _require_step_path(path: str) -> None:
    ext = os.path.splitext(path)[1].lower()
    if ext not in {".step", ".stp"}:
        raise ValueError(f"STEP output must end in .step or .stp, got {path!r}")
