# SPDX-License-Identifier: LGPL-2.1-or-later
"""Document tree JSON."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bruceworx.tree import SCHEMA, document_tree  # noqa: E402
from fakes import FakeDoc, FakeObj, FakeShape  # noqa: E402


class TreeTests(unittest.TestCase):
    def test_roots_and_children(self):
        pad = FakeObj("Pad", "Pad", "PartDesign::Pad", FakeShape())
        body = FakeObj("Body", "Body", "PartDesign::Body", FakeShape(), children=[pad])
        doc = FakeDoc("Part", "Bracket", [body, pad])
        doc.FileName = "/tmp/part.FCStd"
        tree = document_tree(doc)
        self.assertEqual(tree["schema"], SCHEMA)
        self.assertEqual(tree["document"]["name"], "Part")
        self.assertEqual(tree["document"]["label"], "Bracket")
        self.assertEqual(tree["document"]["file"], "/tmp/part.FCStd")
        self.assertEqual(len(tree["tree"]), 1)
        self.assertEqual(tree["tree"][0]["name"], "Body")
        self.assertEqual(tree["tree"][0]["children"][0]["name"], "Pad")
        self.assertEqual(tree["tree"][0]["children"][0]["typeid"], "PartDesign::Pad")

    def test_cycle_is_marked(self):
        left = FakeObj("Left")
        right = FakeObj("Right")
        left.OutList = [right]
        right.OutList = [left]
        doc = FakeDoc("Loop", "Loop", [left, right])
        tree = document_tree(doc)
        # Both are children of each other, so neither is a root. An empty
        # forest is the honest result; a self-cycle still reports.
        self.assertEqual(tree["tree"], [])
        loop = FakeObj("Loop")
        loop.OutList = [loop]
        alone = document_tree(FakeDoc("D", "D", [loop]))
        self.assertTrue(alone["tree"][0]["children"][0]["cycle"])

    def test_empty_document(self):
        tree = document_tree(FakeDoc("Empty", "Empty", []))
        self.assertEqual(tree["tree"], [])


if __name__ == "__main__":
    unittest.main()
