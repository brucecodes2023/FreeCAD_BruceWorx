# SPDX-License-Identifier: LGPL-2.1-or-later
"""FreeCADCmd check: schema properties on a real part, computed mass and
material, and the Assembly BOM printing them.

    FreeCADCmd addons/BruceWorx/tests/freecad_partprops_smoke.py
"""

from __future__ import annotations

import os
import sys
import traceback

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _material(name):
    import Materials  # noqa: PLC0415

    for material in Materials.MaterialManager().Materials.values():
        if material.Name == name:
            return material
    raise LookupError(name)


def run() -> None:
    import FreeCAD  # noqa: PLC0415

    from bruceworx.partprops import load_schema  # noqa: PLC0415

    schema = load_schema(user_layer=False)
    doc = FreeCAD.newDocument("PartPropsSmoke")
    part = doc.addObject("App::Part", "Part")
    box = doc.addObject("Part::Box", "Plate")
    box.Length, box.Width, box.Height = 100, 50, 10  # 50 000 mm^3
    part.addObject(box)
    box.ShapeMaterial = _material("Aluminum-6061-T6")
    doc.recompute()

    report = schema.apply(part)
    assert not report["conflicts"], report
    assert part.getTypeIdOfProperty("Mass") == "App::PropertyMass"
    assert part.MaterialName == "Aluminum-6061-T6", part.MaterialName
    mass = part.Mass.getValueAs("kg").Value
    density = FreeCAD.Units.Quantity(box.ShapeMaterial.getPhysicalValue("Density")).getValueAs("kg/mm^3").Value
    assert abs(mass - 50000 * density) < 1e-9, (mass, density)
    assert 0.1 < mass < 0.2, mass  # aluminium plate, about 0.135 kg
    assert "ReadOnly" in part.getEditorMode("PartNumber")
    assert schema.missing(part, "submit") == ["Description"], schema.missing(part, "submit")
    part.PartNumber = "LE-01-01001-001"
    part.Revision = "01"
    part.Description = "Base plate"
    part.Finish = "Clear anodise"

    import UtilsAssembly  # noqa: PLC0415

    assembly = doc.addObject("Assembly::AssemblyObject", "Assembly")
    link = assembly.newObject("App::Link", "PlateLink")
    link.LinkedObject = part
    bom = UtilsAssembly.getBomGroup(assembly).newObject("Assembly::BomObject", "BOM")
    bom.columnsNames = ["Index", "Name", "Quantity"] + schema.bom_columns()
    doc.recompute()
    header = [bom.getContents(f"{chr(65 + i)}1") for i in range(len(bom.columnsNames))]
    row = {h.lstrip("'"): bom.getContents(f"{chr(65 + i)}2").lstrip("'") for i, h in enumerate(header)}
    print("BOM row", row)
    assert row[".PartNumber"] == "LE-01-01001-001", row
    assert row[".Revision"] == "01", row
    assert row[".MaterialName"] == "Aluminum-6061-T6", row
    assert row[".Mass"].lstrip("=").replace(" ", "") in ("135g", "0.135kg"), row  # a unit expression
    FreeCAD.closeDocument(doc.Name)
    print("BW_PARTPROPS_SMOKE PASS")


try:
    run()
except Exception:  # noqa: BLE001
    traceback.print_exc()
    print("BW_PARTPROPS_SMOKE FAIL")
    sys.exit(1)
