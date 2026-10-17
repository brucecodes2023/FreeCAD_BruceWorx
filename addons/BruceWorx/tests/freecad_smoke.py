# SPDX-License-Identifier: LGPL-2.1-or-later
"""In-process FreeCADCmd check for export, import, tree and rename.

Run with FreeCADCmd (it imports this file as a module)::

    FreeCADCmd addons/BruceWorx/tests/freecad_smoke.py

The shell wrapper tests/run_freecad_smoke.sh also launches hooks.py itself.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import traceback

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

SMOKE_DIR = os.environ.get("BW_SMOKE_DIR", "/tmp/bruceworx-hooks-smoke")


def run() -> None:
    import FreeCAD  # noqa: PLC0415

    from bruceworx.cli import main  # noqa: PLC0415
    from bruceworx.freecad_io import import_step  # noqa: PLC0415

    if os.path.isdir(SMOKE_DIR):
        shutil.rmtree(SMOKE_DIR)
    os.makedirs(SMOKE_DIR)

    doc = FreeCAD.newDocument("BoxDoc")
    box = doc.addObject("Part::Box", "Box")
    box.Length = 10
    box.Width = 20
    box.Height = 30
    doc.recompute()
    fcstd = os.path.join(SMOKE_DIR, "box.FCStd")
    doc.saveAs(fcstd)
    FreeCAD.closeDocument(doc.Name)

    step = os.path.join(SMOKE_DIR, "box.step")
    _check(main(["export-step", "--input", fcstd, "--output", step]), "export-step")
    header = open(step, "rb").read(80)
    if b"ISO-10303-21" not in header:
        raise RuntimeError(f"STEP header missing: {header!r}")

    imported = FreeCAD.newDocument("Imported")
    import_step(step, imported)
    imported.recompute()
    volumes = []
    for obj in imported.Objects:
        shape = getattr(obj, "Shape", None)
        if shape is None or shape.isNull() or not shape.Solids:
            continue
        volumes.append(shape.Volume)
    if not any(abs(volume - 6000.0) / 6000.0 < 0.05 for volume in volumes):
        names = [obj.Name for obj in imported.Objects]
        raise RuntimeError(f"STEP import volumes {volumes} objects {names}")
    FreeCAD.closeDocument(imported.Name)

    tree_path = os.path.join(SMOKE_DIR, "tree.json")
    _check(main(["list-tree", "--input", fcstd, "--output", tree_path]), "list-tree")
    tree = json.load(open(tree_path, encoding="utf-8"))
    if tree.get("schema") != "bruceworx.document-tree.v1":
        raise RuntimeError(f"unexpected tree schema {tree.get('schema')!r}")
    if not tree["tree"] or tree["tree"][0]["name"] != "Box":
        raise RuntimeError(f"tree did not start at Box: {tree['tree']!r}")

    config = os.path.join(SMOKE_DIR, "numbering.json")
    example = os.path.join(_ROOT, "config", "numbering.example.json")
    shutil.copyfile(example, config)
    # The example points at document_types.json beside the numbering file.
    shutil.copyfile(
        os.path.join(_ROOT, "config", "document_types.json"),
        os.path.join(SMOKE_DIR, "document_types.json"),
    )
    # Default save name is the part number. FreeCAD reloads Document.Label
    # from that file name.
    part_number = "LE-01-01001-001-A"
    _check(
        main(
            [
                "rename",
                "--input",
                fcstd,
                "--program",
                "LE",
                "--document-type",
                "01",
                "--config",
                config,
            ]
        ),
        "rename",
    )
    renamed = os.path.join(SMOKE_DIR, part_number + ".FCStd")
    if not os.path.isfile(renamed):
        raise RuntimeError(f"expected renamed file at {renamed}")
    numbered = FreeCAD.openDocument(renamed)
    if numbered.Label != part_number:
        raise RuntimeError(f"document label is {numbered.Label!r}")
    numbered_box = numbered.getObject("Box")
    if numbered_box is None or numbered_box.Label != part_number:
        raise RuntimeError(f"Box label was not set to {part_number}")
    # Hyphens are not legal in an internal Name, so the reopened document is
    # LE_01_01001_001_A while Label keeps LE-01-01001-001-A.
    if numbered.Name != "LE_01_01001_001_A":
        raise RuntimeError(f"internal document name is {numbered.Name!r}")
    FreeCAD.closeDocument(numbered.Name)
    print("BW_SMOKE PASS", flush=True)


def _check(code: int, command: str) -> None:
    if code != 0:
        raise RuntimeError(f"{command} exited {code}")


def _entry() -> int:
    try:
        import FreeCAD  # noqa: F401, PLC0415
    except ImportError:
        print("freecad_smoke.py must be run with FreeCADCmd", file=sys.stderr)
        return 1
    try:
        run()
    except Exception:  # noqa: BLE001 — report and fail the process
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__" or __name__ == "freecad_smoke":
    sys.exit(_entry())
