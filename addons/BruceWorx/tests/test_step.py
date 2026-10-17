# SPDX-License-Identifier: LGPL-2.1-or-later
"""STEP export selection, with a fake exporter."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bruceworx.step_export import export_step  # noqa: E402
from fakes import FakeDoc, FakeObj, FakeShape  # noqa: E402


class StepExportTests(unittest.TestCase):
    def test_exports_solid_roots_only(self):
        calls = []

        def exporter(objects, path):
            calls.append(([obj.Name for obj in objects], path))
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("ISO-10303-21;\n")

        pad = FakeObj("Pad", shape=FakeShape())
        body = FakeObj("Body", typeid="PartDesign::Body", shape=FakeShape(), children=[pad])
        sketch = FakeObj("Sketch", typeid="Sketcher::SketchObject", shape=FakeShape(solids=0))
        doc = FakeDoc("D", "D", [body, pad, sketch])
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, "part.step")
            result = export_step(doc, output, exporter=exporter)
            self.assertTrue(os.path.isfile(output))
        self.assertEqual(calls[0][0], ["Body"])
        self.assertEqual(result["objects"], ["Body"])

    def test_explicit_objects_and_suffix(self):
        calls = []

        def exporter(objects, path):
            calls.append(objects)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("ISO-10303-21;\n")

        box = FakeObj("Box", shape=FakeShape())
        doc = FakeDoc("D", "D", [box])
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, "box.stp")
            export_step(doc, output, objects=[box], exporter=exporter)
        self.assertEqual(calls[0], [box])

    def test_rejects_non_step_and_empty(self):
        doc = FakeDoc("D", "D", [FakeObj("Box", shape=FakeShape())])
        with self.assertRaises(ValueError):
            export_step(doc, "out.brep", exporter=lambda *_: None)
        empty = FakeDoc("D", "D", [])
        with self.assertRaises(ValueError):
            export_step(empty, "out.step", exporter=lambda *_: None)

    def test_recompute_runs(self):
        seen = {}

        class Doc(FakeDoc):
            def recompute(self):
                seen["ran"] = True

        doc = Doc("D", "D", [FakeObj("Box", shape=FakeShape())])

        def exporter(_objects, path):
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("x")

        with tempfile.TemporaryDirectory() as directory:
            export_step(doc, os.path.join(directory, "a.step"), exporter=exporter)
        self.assertTrue(seen["ran"])


if __name__ == "__main__":
    unittest.main()
