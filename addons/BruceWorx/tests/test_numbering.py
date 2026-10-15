# SPDX-License-Identifier: LGPL-2.1-or-later
"""Part-number format and label assignment."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bruceworx.numbering import (  # noqa: E402
    PART_NUMBER_FORMAT,
    assign_part_numbers,
    format_part_number,
    part_objects,
)
from bruceworx.sources import JsonNumberSource  # noqa: E402
from fakes import FakeDoc, FakeObj, FakeShape  # noqa: E402


class FormatTests(unittest.TestCase):
    def test_example(self):
        self.assertEqual(format_part_number("LE", 1001, "A"), "LE-01001-A")

    def test_case_and_padding(self):
        self.assertEqual(format_part_number(" le ", 1, "b"), "LE-00001-B")
        self.assertEqual(format_part_number("L1", 99999, "AA"), "L1-99999-AA")

    def test_rejects_bad_program(self):
        for program in ("", "1LE", "LE-X", "TOOLONGCODE", "L E"):
            with self.assertRaises(ValueError):
                format_part_number(program, 1, "A")

    def test_rejects_bad_revision(self):
        for revision in ("", "1", "A1", "ABCD"):
            with self.assertRaises(ValueError):
                format_part_number("LE", 1, revision)

    def test_rejects_bad_sequence(self):
        for number in (-1, 100000, True, 1.5, "1001"):
            with self.assertRaises(ValueError):
                format_part_number("LE", number, "A")

    def test_format_constant(self):
        self.assertEqual(PART_NUMBER_FORMAT, "{PROG}-{NNNNN}-{REV}")


class AssignTests(unittest.TestCase):
    def _source(self, directory):
        path = os.path.join(directory, "numbering.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "source": "json",
                    "format": "{PROG}-{NNNNN}-{REV}",
                    "number_width": 5,
                    "programs": {"LE": {"revision": "A", "next": 1001}},
                },
                handle,
            )
        return JsonNumberSource(path)

    def test_sets_label_and_document_label(self):
        box = FakeObj("Box", "Box", "Part::Box", FakeShape())
        doc = FakeDoc("Unnamed", "Unnamed", [box])
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            result = assign_part_numbers(doc, self._source(directory), "le")
        self.assertEqual(box.Label, "LE-01001-A")
        self.assertEqual(doc.Label, "LE-01001-A")
        self.assertEqual(doc.Name, "Unnamed")
        self.assertEqual(result["assignments"][0]["old_label"], "Box")
        self.assertEqual(result["part_number"], "LE-01001-A")

    def test_children_are_not_numbered(self):
        pad = FakeObj("Pad", "Pad", "PartDesign::Pad", FakeShape())
        body = FakeObj("Body", "Body", "PartDesign::Body", FakeShape(), children=[pad])
        doc = FakeDoc("Part", "Part", [body, pad])
        self.assertEqual([obj.Name for obj in part_objects(doc)], ["Body"])

    def test_explicit_child_can_be_numbered(self):
        pad = FakeObj("Pad", "Pad", "PartDesign::Pad", FakeShape())
        body = FakeObj("Body", "Body", "PartDesign::Body", FakeShape(), children=[pad])
        doc = FakeDoc("Part", "Part", [body, pad])
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            result = assign_part_numbers(
                doc, self._source(directory), "LE", objects=part_objects(doc, ["Pad"])
            )
        self.assertEqual(pad.Label, "LE-01001-A")
        self.assertEqual(body.Label, "Body")
        self.assertEqual(result["assignments"][0]["name"], "Pad")

    def test_two_roots_get_successive_numbers(self):
        left = FakeObj("Left", shape=FakeShape())
        right = FakeObj("Right", shape=FakeShape())
        doc = FakeDoc("Asm", "Asm", [left, right])
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            assign_part_numbers(doc, self._source(directory), "LE")
        self.assertEqual(left.Label, "LE-01001-A")
        self.assertEqual(right.Label, "LE-01002-A")
        self.assertEqual(doc.Label, "LE-01001-A")

    def test_document_only_when_nothing_solid(self):
        sheet = FakeObj("Sheet", typeid="Spreadsheet::Sheet", shape=None)
        doc = FakeDoc("Notes", "Notes", [sheet])
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            result = assign_part_numbers(doc, self._source(directory), "LE")
        self.assertEqual(doc.Label, "LE-01001-A")
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
