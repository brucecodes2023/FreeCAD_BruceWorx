# SPDX-License-Identifier: LGPL-2.1-or-later
"""FreeCAD document open/save and STEP import/export.

Imported only when a geometry command actually runs.
"""

from __future__ import annotations

import os


def freecad_available() -> bool:
    try:
        import FreeCAD  # noqa: F401, PLC0415
    except ImportError:
        return False
    return True


def require_freecad() -> None:
    if freecad_available():
        return
    raise RuntimeError(
        "This command needs FreeCAD. From the repository root:\n"
        "  FreeCADCmd -- addons/BruceWorx/hooks.py <command> ...\n"
        "or:\n"
        "  BW_HOOKS_ARGS='<command> ...' FreeCADCmd addons/BruceWorx/hooks.py"
    )


def open_document(path: str):
    require_freecad()
    import FreeCAD  # noqa: PLC0415

    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return FreeCAD.openDocument(path)


def new_document(name: str, label: str | None = None):
    require_freecad()
    import FreeCAD  # noqa: PLC0415

    if label is None:
        return FreeCAD.newDocument(name)
    return FreeCAD.newDocument(name, label)


def save_document(doc, output_path: str) -> str:
    output_path = os.path.abspath(output_path)
    directory = os.path.dirname(output_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    doc.saveAs(output_path)
    return output_path


def close_document(doc) -> None:
    import FreeCAD  # noqa: PLC0415

    FreeCAD.closeDocument(doc.Name)


def export_step(objects, output_path: str) -> None:
    """Write STEP. Prefer the Import workbench, then Part."""
    require_freecad()
    errors = []
    try:
        import Import  # noqa: PLC0415

        Import.export(list(objects), output_path)
        if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
            return
        errors.append("Import.export wrote an empty file")
    except Exception as exc:  # noqa: BLE001 — fall back to Part.export
        errors.append(f"Import.export: {exc}")
    import Part  # noqa: PLC0415

    Part.export(list(objects), output_path)
    if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
        detail = "; ".join(errors) if errors else "no writer succeeded"
        raise RuntimeError(f"STEP export failed ({detail})")


def import_step(path: str, doc) -> None:
    """Insert a STEP file into an existing document."""
    require_freecad()
    path = os.path.abspath(path)
    errors = []
    try:
        import Import  # noqa: PLC0415

        Import.insert(path, doc.Name)
        return
    except Exception as exc:  # noqa: BLE001 — fall back to Part.insert
        errors.append(f"Import.insert: {exc}")
    import Part  # noqa: PLC0415

    try:
        Part.insert(path, doc.Name)
    except Exception as exc:  # noqa: BLE001 — surface both attempts
        errors.append(f"Part.insert: {exc}")
        raise RuntimeError("STEP import failed ({})".format("; ".join(errors))) from exc
