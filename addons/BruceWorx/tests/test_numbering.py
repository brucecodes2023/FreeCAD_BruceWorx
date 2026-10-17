# SPDX-License-Identifier: LGPL-2.1-or-later
"""Part-number format and label assignment."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bruceworx.numbering import (  # noqa: E402
    PART_NUMBER_FORMAT,
    assign_part_numbers,
    format_part_number,
    parse_part_number,
    part_objects,
)
from bruceworx.sources import JsonNumberSource  # noqa: E402
from fakes import FakeDoc, FakeObj, FakeShape  # noqa: E402

EXAMPLE = "LE-01-01001-001-A"


def _write(directory, next_parent=1001):
    path = os.path.join(directory, "numbering.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "source": "json",
                "format": PART_NUMBER_FORMAT,
                "document_types": {
                    "01": {"placeholder": True, "name": "PLACEHOLDER"},
                    "02": {"placeholder": True, "name": "PLACEHOLDER"},
                },
                "programs": {
                    "LE": {
                        "revision": "A",
                        "counters": {
                            "01": {"next_parent": next_parent, "parents": {}},
                        },
                    }
                },
            },
            handle,
        )
    return JsonNumberSource(path)


class FormatTests(unittest.TestCase):
    def test_example(self):
        self.assertEqual(format_part_number("LE", "01", 1001, 1, "A"), EXAMPLE)

    def test_case_and_padding(self):
        self.assertEqual(
            format_part_number(" le ", "1", 1, 2, "b"),
            "LE-01-00001-002-B",
        )
        self.assertEqual(
            format_part_number("L1", "2", 99999, 999, "AA"),
            "L1-02-99999-999-AA",
        )

    def test_parse_round_trip(self):
        parsed = parse_part_number("le-01-01001-001-a")
        self.assertEqual(parsed["program"], "LE")
        self.assertEqual(parsed["document_type"], "01")
        self.assertEqual(parsed["parent"], "01001")
        self.assertEqual(parsed["sub"], "001")
        self.assertEqual(parsed["revision"], "A")

    def test_rejects_bad_program(self):
        for program in ("", "1LE", "LE-X", "TOOLONGCODE", "L E"):
            with self.assertRaises(ValueError):
                format_part_number(program, "01", 1001, 1, "A")

    def test_rejects_bad_revision(self):
        for revision in ("", "1", "A1", "ABCD"):
            with self.assertRaises(ValueError):
                format_part_number("LE", "01", 1001, 1, revision)

    def test_rejects_bad_fields(self):
        with self.assertRaises(ValueError):
            format_part_number("LE", "100", 1001, 1, "A")
        with self.assertRaises(ValueError):
            format_part_number("LE", "01", 100000, 1, "A")
        with self.assertRaises(ValueError):
            format_part_number("LE", "01", 1001, 1000, "A")
        with self.assertRaises(ValueError):
            parse_part_number("LE-01001-A")

    def test_format_constant(self):
        self.assertEqual(PART_NUMBER_FORMAT, "{PROG}-{DT}-{PPPPP}-{SSS}-{REV}")


class AssignTests(unittest.TestCase):
    def test_sets_label_and_document_label(self):
        box = FakeObj("Box", "Box", "Part::Box", FakeShape())
        doc = FakeDoc("Unnamed", "Unnamed", [box])
        with tempfile.TemporaryDirectory() as directory:
            result = assign_part_numbers(doc, _write(directory), "le", "01")
        self.assertEqual(box.Label, EXAMPLE)
        self.assertEqual(doc.Label, EXAMPLE)
        self.assertEqual(doc.Name, "Unnamed")
        self.assertEqual(result["assignments"][0]["old_label"], "Box")
        self.assertEqual(result["part_number"], EXAMPLE)
        self.assertEqual(result["parent"], "01001")
        self.assertEqual(result["sub"], "001")

    def test_children_are_not_numbered(self):
        pad = FakeObj("Pad", "Pad", "PartDesign::Pad", FakeShape())
        body = FakeObj("Body", "Body", "PartDesign::Body", FakeShape(), children=[pad])
        doc = FakeDoc("Part", "Part", [body, pad])
        self.assertEqual([obj.Name for obj in part_objects(doc)], ["Body"])

    def test_explicit_child_can_be_numbered(self):
        pad = FakeObj("Pad", "Pad", "PartDesign::Pad", FakeShape())
        body = FakeObj("Body", "Body", "PartDesign::Body", FakeShape(), children=[pad])
        doc = FakeDoc("Part", "Part", [body, pad])
        with tempfile.TemporaryDirectory() as directory:
            result = assign_part_numbers(
                doc,
                _write(directory),
                "LE",
                "01",
                objects=part_objects(doc, ["Pad"]),
            )
        self.assertEqual(pad.Label, EXAMPLE)
        self.assertEqual(body.Label, "Body")
        self.assertEqual(result["assignments"][0]["name"], "Pad")

    def test_two_roots_share_a_parent(self):
        left = FakeObj("Left", shape=FakeShape())
        right = FakeObj("Right", shape=FakeShape())
        doc = FakeDoc("Asm", "Asm", [left, right])
        with tempfile.TemporaryDirectory() as directory:
            assign_part_numbers(doc, _write(directory), "LE", "01")
        self.assertEqual(left.Label, "LE-01-01001-001-A")
        self.assertEqual(right.Label, "LE-01-01001-002-A")
        self.assertEqual(doc.Label, "LE-01-01001-001-A")

    def test_explicit_parent_does_not_take_a_new_drawing(self):
        left = FakeObj("Left", shape=FakeShape())
        right = FakeObj("Right", shape=FakeShape())
        doc = FakeDoc("Asm", "Asm", [left, right])
        with tempfile.TemporaryDirectory() as directory:
            source = _write(directory)
            source.allocate("LE", "01")
            assign_part_numbers(doc, source, "LE", "01", parent="01001")
        self.assertEqual(left.Label, "LE-01-01001-002-A")
        self.assertEqual(right.Label, "LE-01-01001-003-A")

    def test_document_only_when_nothing_solid(self):
        sheet = FakeObj("Sheet", typeid="Spreadsheet::Sheet", shape=None)
        doc = FakeDoc("Notes", "Notes", [sheet])
        with tempfile.TemporaryDirectory() as directory:
            result = assign_part_numbers(doc, _write(directory), "LE", "01")
        self.assertEqual(doc.Label, EXAMPLE)
        self.assertEqual(sheet.Label, "Sheet")
        self.assertEqual(result["assignments"], [])

    def test_sketch_without_solids_is_skipped(self):
        sketch = FakeObj("Sketch", typeid="Sketcher::SketchObject", shape=FakeShape(solids=0))
        doc = FakeDoc("D", "D", [sketch])
        self.assertEqual(part_objects(doc), [])

    def test_missing_object(self):
        doc = FakeDoc("D", "D", [FakeObj("Box", shape=FakeShape())])
        with self.assertRaises(ValueError):
            part_objects(doc, ["Nope"])


if __name__ == "__main__":
    unittest.main()
