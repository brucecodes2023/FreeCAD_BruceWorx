# SPDX-License-Identifier: LGPL-2.1-or-later
"""Make external helpers that run without FreeCAD (BW-ASM-01). The split
itself is covered by tests/freecad_filemodel.py under FreeCADCmd."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bruceworx import filemodel  # noqa: E402


class Obj:
    def __init__(self, name, element_count=0):
        self.Name = name
        self.ElementCount = element_count


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.body = Obj("WingL")
        self.link = Obj("Link001")

    def test_component_rooted_reference_moves_to_link(self):
        ref = (self.body, ["Face6", "Vertex7"])
        new = filemodel._rewrite_reference(ref, self.body, self.link, "WingL", [])
        self.assertIs(new[0], self.link)
        self.assertEqual(new[1], ["WingL.Face6", "WingL.Vertex7"])

    def test_feature_path_kept_under_the_body(self):
        ref = (self.body, ["Pad.Face3", ""])
        new = filemodel._rewrite_reference(ref, self.body, self.link, "WingL", [])
        self.assertEqual(new[1], ["WingL.Pad.Face3", "WingL."])

    def test_assembly_rooted_reference(self):
        asm = Obj("Assembly")
        ref = (asm, ["WingL.Face6", "Fuselage.Vertex1"])
        new = filemodel._rewrite_reference(ref, self.body, self.link, "WingL", [])
        self.assertIs(new[0], asm)
        self.assertEqual(new[1], ["Link001.WingL.Face6", "Fuselage.Vertex1"])

    def test_unrelated_reference_untouched(self):
        other = Obj("Fin")
        self.assertIsNone(filemodel._rewrite_reference((other, ["Face1"]), self.body, self.link, "WingL", []))
        self.assertIsNone(filemodel._rewrite_reference(None, self.body, self.link, "WingL", []))
        self.assertIsNone(filemodel._rewrite_reference((None, []), self.body, self.link, "WingL", []))

    def test_retargeted_link_and_link_array(self):
        bolt_link = Obj("BoltLink")
        array = Obj("BoltPattern", element_count=6)
        a = filemodel._rewrite_reference((bolt_link, ["Face1"]), self.body, self.link, "Bolt", [bolt_link, array])
        self.assertEqual(a, (bolt_link, ["Bolt.Face1"]))
        b = filemodel._rewrite_reference((array, ["2.Face1"]), self.body, self.link, "Bolt", [bolt_link, array])
        self.assertEqual(b, (array, ["2.Bolt.Face1"]))


class NamingTests(unittest.TestCase):
    def test_safe_file_stem(self):
        self.assertEqual(filemodel.safe_file_stem("Wing L / root"), "Wing_L_root")
        self.assertEqual(filemodel.safe_file_stem("LE-01-01001-002"), "LE-01-01001-002")
        self.assertEqual(filemodel.safe_file_stem("..."), "Part")

    def test_unique_stems_case_insensitive(self):
        self.assertEqual(filemodel._unique_stems(["Wing", "wing", "Wing"]), ["Wing", "wing_2", "Wing_3"])

    def test_revision_left_out_of_file_name(self):
        self.assertEqual(filemodel._without_revision("LE-01-01001-002-A"), "LE-01-01001-002")
        with self.assertRaises(ValueError):
            filemodel._without_revision("not-a-number")


if __name__ == "__main__":
    unittest.main()
