# SPDX-License-Identifier: LGPL-2.1-or-later
"""Schema-driven part properties (BW-ASM-04 / PDM-02) without FreeCAD.
FreeCAD itself is covered by tests/freecad_partprops_smoke.py."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bruceworx import partprops  # noqa: E402
from bruceworx.partprops import Schema, SchemaError, load_schema  # noqa: E402


class FakePropObj:
    """Just enough of FreeCAD's dynamic-property API."""

    def __init__(self, **existing):
        self._types = {}
        self._modes = {}
        self._enums = {}
        for name, (typeid, value) in existing.items():
            self._types[name] = typeid
            object.__setattr__(self, name, value)

    @property
    def PropertiesList(self):
        return list(self._types)

    def addProperty(self, typeid, name, group="", doc=""):
        if name in self._types:
            raise ValueError(f"{name} exists")
        self._types[name] = typeid
        object.__setattr__(self, name, None)

    def removeProperty(self, name):
        del self._types[name]
        object.__delattr__(self, name)

    def getTypeIdOfProperty(self, name):
        return self._types[name]

    def setEditorMode(self, name, mode):
        self._modes[name] = list(mode)

    def __setattr__(self, name, value):
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        if self._types.get(name) == "App::PropertyEnumeration":
            if isinstance(value, list):
                self._enums[name] = value
                value = value[0]
            elif value not in self._enums.get(name, []):
                raise ValueError(f"{value!r} not in {name}")
        object.__setattr__(self, name, value)


def _layer(*props, renamed=None):
    return {"schema": partprops.SCHEMA_ID, "version": 1, "properties": list(props), "renamed": renamed or {}}


class BuiltinSchemaTests(unittest.TestCase):
    def setUp(self):
        self.schema = load_schema(user_layer=False)

    def test_builtin_layer_loads(self):
        names = list(self.schema.properties)
        for name in ("PartNumber", "Revision", "Description", "MaterialName", "Mass"):
            self.assertIn(name, names)
        self.assertEqual(self.schema.properties["Mass"].freecad_type, "App::PropertyMass")

    def test_bom_columns_are_dot_property_names(self):
        cols = self.schema.bom_columns()
        self.assertEqual(cols[:3], [".PartNumber", ".Revision", ".Description"])
        self.assertIn(".Mass", cols)
        self.assertNotIn(".Vendor", cols)

    def test_apply_adds_everything_once(self):
        obj = FakePropObj()
        report = self.schema.apply(obj, compute=False)
        self.assertEqual(sorted(report["added"]), sorted(self.schema.properties))
        self.assertEqual(obj.ItemType, "part")
        self.assertEqual(obj._modes["PartNumber"], ["ReadOnly"])
        self.assertEqual(obj._modes["Description"], [])
        again = self.schema.apply(obj, compute=False)
        self.assertEqual(again["added"], [])

    def test_missing_by_stage(self):
        obj = FakePropObj()
        self.schema.apply(obj, compute=False)
        self.assertEqual(self.schema.missing(obj, "submit"), ["Description", "MaterialName"])
        obj.Description = "Base plate"
        obj.MaterialName = "Aluminum-6061-T6"
        self.assertEqual(self.schema.missing(obj, "release"), [])


class LayerTests(unittest.TestCase):
    def setUp(self):
        self.schema = load_schema(user_layer=False)

    def test_new_property_needs_no_code(self):
        self.schema.add_layer(_layer(
            {"name": "Supplier", "type": "string", "bom": True, "required": "release"},
            {"name": "LeadTimeDays", "type": "int", "default": 10},
        ), "company")
        obj = FakePropObj()
        self.schema.apply(obj, compute=False)
        self.assertEqual(obj.LeadTimeDays, 10)
        self.assertIn(".Supplier", self.schema.bom_columns())
        self.assertIn("Supplier", self.schema.missing(obj, "release"))
        self.assertNotIn("Supplier", self.schema.missing(obj, "submit"))

    def test_layer_may_restyle_but_not_retype(self):
        self.schema.add_layer(_layer({"name": "Vendor", "bom": True, "required": "submit"}), "company")
        self.assertIn(".Vendor", self.schema.bom_columns())
        with self.assertRaises(SchemaError):
            self.schema.add_layer(_layer({"name": "Mass", "type": "float"}), "bad")

    def test_rename_moves_the_value(self):
        obj = FakePropObj(Finsh=("App::PropertyString", "Anodise clear"))
        self.schema.add_layer(_layer(renamed={"Finsh": "Finish"}), "fix-typo")
        report = self.schema.apply(obj, compute=False)
        self.assertEqual(obj.Finish, "Anodise clear")
        self.assertNotIn("Finsh", obj.PropertiesList)
        self.assertEqual(report["renamed"], ["Finsh->Finish"])

    def test_unknown_properties_survive(self):
        obj = FakePropObj(FromNewerSchema=("App::PropertyString", "keep me"))
        self.schema.apply(obj, compute=False)
        self.assertEqual(obj.FromNewerSchema, "keep me")

    def test_type_clash_is_reported_not_changed(self):
        obj = FakePropObj(Mass=("App::PropertyFloat", 1.5))
        report = self.schema.apply(obj, compute=False)
        self.assertEqual(obj.Mass, 1.5)
        self.assertTrue(report["conflicts"][0].startswith("Mass"))

    def test_enum_keeps_a_still_valid_choice(self):
        obj = FakePropObj()
        self.schema.apply(obj, compute=False)
        obj.ItemType = "cots"
        self.schema.add_layer(_layer({"name": "ItemType", "values": ["part", "assembly", "cots", "drawing", "kit"]}), "c")
        self.schema.apply(obj, compute=False)
        self.assertEqual(obj.ItemType, "cots")

    def test_bad_layers(self):
        for bad in (
            {"schema": "other"},
            _layer({"name": "x y", "type": "string"}),
            _layer({"name": "Thing", "type": "colour"}),
            _layer({"name": "Kind", "type": "enum"}),
            _layer({"name": "Stamp", "type": "string", "required": "shipping"}),
        ):
            with self.assertRaises(SchemaError):
                Schema().add_layer(bad, "bad")

    def test_load_schema_reads_extra_layer_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "part_properties.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(_layer({"name": "Coating", "type": "string", "bom": True}), handle)
            schema = load_schema([path], user_layer=False)
        self.assertIn(".Coating", schema.bom_columns())
        self.assertEqual(schema.layers[-1], path)


if __name__ == "__main__":
    unittest.main()
