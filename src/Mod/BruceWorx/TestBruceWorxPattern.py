# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tests for bruceworx_pattern (BW-MOD-01).

The math tests run in plain Python. The document tests need FreeCAD and are
skipped without it:

    FreeCADCmd -t TestBruceWorxPattern
    python3 -m unittest TestBruceWorxPattern      # math only
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bruceworx_pattern as bp

try:
    import FreeCAD as App
    import Part
except ImportError:  # plain Python
    App = None


def _rect(**kw):
    params = {
        "kind": bp.RECTANGULAR, "count1": 3, "count2": 1, "distance1": 10.0, "distance2": 10.0,
        "type1": "Spacing", "type2": "Spacing", "symmetric1": False, "symmetric2": False,
    }
    params.update(kw)
    return params


class MathTests(unittest.TestCase):
    def test_index_set(self):
        self.assertEqual(bp.index_set(4), [0, 1, 2, 3])
        self.assertEqual(bp.index_set(5, True), [-2, -1, 0, 1, 2])
        self.assertEqual(bp.index_set(4, True), [-1, 0, 1, 2])
        self.assertEqual(bp.index_set(1, True), [0])
        self.assertEqual(bp.index_set(0), [0])

    def test_step(self):
        self.assertEqual(bp.step(4, 30.0, "Extent"), 10.0)
        self.assertEqual(bp.step(4, 30.0, "Spacing"), 30.0)
        self.assertEqual(bp.step(1, 30.0, "Extent"), 0.0)

    def test_rectangular_offsets(self):
        offsets = bp.rectangular_offsets(_rect(count2=2, distance2=5.0))
        self.assertEqual(len(offsets), 6)
        self.assertEqual(offsets[(2, 1)], (20.0, 5.0))
        sym = bp.rectangular_offsets(_rect(symmetric1=True))
        self.assertEqual(sorted(sym), [(-1, 0), (0, 0), (1, 0)])

    def test_circular_angles(self):
        full = bp.circular_angles({"count1": 8, "circular_type": "Full", "angle": 360.0})
        self.assertEqual(len(full), 8)
        self.assertAlmostEqual(full[(1,)], 45.0)
        self.assertAlmostEqual(full[(7,)], 315.0)  # 360 is the seed, never repeated
        angle = bp.circular_angles({"count1": 3, "circular_type": "Angle", "angle": 90.0})
        self.assertEqual(sorted(angle.values()), [0.0, 45.0, 90.0])
        sym = bp.circular_angles({"count1": 3, "circular_type": "Symmetric", "angle": 90.0})
        self.assertEqual(sorted(sym.values()), [-45.0, 0.0, 45.0])

    def test_keys(self):
        self.assertEqual(bp.text_to_key(bp.key_to_text((-1, 2))), (-1, 2))
        self.assertEqual(bp.text_to_key("3"), (3,))


@unittest.skipIf(App is None, "needs FreeCAD")
class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.doc = App.newDocument("BWPatternTest")

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    def _box(self, placement=None):
        box = self.doc.addObject("Part::Box", "Seed")
        box.Length = box.Width = box.Height = 4.0
        if placement is not None:
            box.Placement = placement
        self.doc.recompute()
        return box

    def _params(self, kind=bp.RECTANGULAR, **kw):
        params = bp.default_params(kind)
        params.update(kw)
        return params

    def test_rectangular_linked(self):
        seed = self._box()
        array = bp.create_linked(seed, self._params(count1=3, count2=2, distance1=10, distance2=20))
        self.doc.recompute()
        self.assertEqual(array.TypeId, "App::Link")
        self.assertEqual(array.ElementCount, 5)  # 3 x 2 minus the seed
        self.assertEqual(len(array.Shape.Solids), 5)
        self.assertAlmostEqual(array.Shape.Volume, 5 * 64.0)
        base = sorted((round(e.Placement.Base.x), round(e.Placement.Base.y)) for e in array.ElementList)
        self.assertEqual(base, [(0, 20), (10, 0), (10, 20), (20, 0), (20, 20)])
        self.assertTrue(bp.is_pattern(array))
        self.assertEqual(bp.patterns_of(seed), [array])

    def test_suppression_hides_and_drops_from_shape(self):
        seed = self._box()
        array = bp.create_linked(seed, self._params(count1=4, suppressed=[(2, 0)]))
        self.doc.recompute()
        self.assertEqual(array.ElementCount, 3)
        self.assertEqual(len(array.Shape.Solids), 2)
        keys = list(array.InstanceKeys)
        self.assertFalse(array.isElementVisible(str(keys.index("2,0"))))
        # Unsuppress: the element comes back without renumbering.
        array.Suppressed = []
        bp.apply(array)
        self.doc.recompute()
        self.assertEqual(len(array.Shape.Solids), 3)
        self.assertEqual(list(array.InstanceKeys), keys)

    def test_symmetric_spreads_both_sides(self):
        seed = self._box()
        array = bp.create_linked(seed, self._params(count1=3, distance1=10, symmetric1=True))
        xs = sorted(round(e.Placement.Base.x) for e in array.ElementList)
        self.assertEqual(xs, [-10, 10])

    def test_extent_mode(self):
        seed = self._box()
        array = bp.create_linked(seed, self._params(count1=5, distance1=40, type1="Extent"))
        xs = sorted(round(e.Placement.Base.x) for e in array.ElementList)
        self.assertEqual(xs, [10, 20, 30, 40])

    def test_rotated_seed_is_patterned_in_world_directions(self):
        rotated = App.Placement(App.Vector(5, 0, 0), App.Rotation(App.Vector(0, 0, 1), 90))
        seed = self._box(rotated)
        array = bp.create_linked(seed, self._params(count1=2, distance1=10))
        element = array.ElementList[0]
        self.assertTrue(element.Placement.Base.isEqual(App.Vector(15, 0, 0), 1e-9))
        self.assertAlmostEqual(element.Placement.Rotation.Angle, rotated.Rotation.Angle)

    def test_circular_full(self):
        seed = self._box(App.Placement(App.Vector(20, 0, 0), App.Rotation()))
        params = self._params(bp.CIRCULAR, count1=8, circular_type="Full")
        array = bp.create_linked(seed, params)
        self.doc.recompute()
        self.assertEqual(array.ElementCount, 7)
        for element in array.ElementList:
            self.assertAlmostEqual(element.Placement.Base.Length, 20.0, places=6)
        self.assertAlmostEqual(array.Shape.Volume, 7 * 64.0, places=6)

    def test_editing_count_and_type(self):
        seed = self._box()
        array = bp.create_linked(seed, self._params(count1=3))
        array.PatternType = bp.CIRCULAR
        array.Count1 = 4
        bp.apply(array)
        self.assertEqual(array.ElementCount, 3)
        self.assertEqual(list(array.InstanceKeys), ["1", "2", "3"])

    def test_follows_seed_geometry(self):
        seed = self._box()
        array = bp.create_linked(seed, self._params(count1=2, distance1=10))
        seed.Height = 8.0
        self.doc.recompute()
        self.assertAlmostEqual(array.Shape.Volume, 128.0)

    def test_save_and_reload_keeps_parameters(self):
        seed = self._box()
        array = bp.create_linked(seed, self._params(count1=3, symmetric1=True, suppressed=[(1, 0)]))
        array_name, seed_name = array.Name, seed.Name
        path = os.path.join(App.getTempPath(), "bw_pattern_roundtrip.FCStd")
        self.doc.saveAs(path)
        App.closeDocument(self.doc.Name)
        self.doc = App.openDocument(path)
        array = self.doc.getObject(array_name)
        self.assertTrue(bp.is_pattern(array))
        params = bp.read_params(array)
        self.assertTrue(params["symmetric1"])
        self.assertEqual(params["suppressed"], [(1, 0)])
        self.assertEqual(array.PatternSeed.Name, seed_name)
        self.assertEqual(array.ElementCount, 2)

    def test_independent_copies(self):
        seed = self._box()
        copies = bp.create_independent(seed, self._params(count1=4, suppressed=[(3, 0)]))
        self.doc.recompute()
        self.assertEqual(len(copies), 2)
        for copy in copies:
            self.assertEqual(copy.TypeId, "Part::Feature")
            self.assertAlmostEqual(copy.Shape.Volume, 64.0)
        seed.Height = 8.0
        self.doc.recompute()
        self.assertAlmostEqual(copies[0].Shape.Volume, 64.0)  # detached from the seed

    def test_make_independent_replaces_array(self):
        seed = self._box()
        array = bp.create_linked(seed, self._params(count1=3))
        name = array.Name
        copies = bp.make_independent(array)
        self.assertIsNone(self.doc.getObject(name))
        self.assertEqual(len(copies), 2)

    def test_parallel_directions_rejected(self):
        with self.assertRaises(ValueError):
            bp.transforms(self._params(count2=2, direction2=App.Vector(2, 0, 0)))

    def test_assembly_sees_every_component(self):
        try:
            import UtilsAssembly
        except ImportError:
            self.skipTest("Assembly module not available")
        bolt = self.doc.addObject("Part::Cylinder", "Bolt")
        bolt.Radius, bolt.Height = 2.5, 20
        assembly = self.doc.addObject("Assembly::AssemblyObject", "Assembly")
        component = self.doc.addObject("App::Link", "BoltLink")
        component.LinkedObject = bolt
        component.Placement = App.Placement(App.Vector(30, 0, 0), App.Rotation())
        assembly.addObject(component)
        self.doc.recompute()
        array = bp.create_linked(component, self._params(bp.CIRCULAR, count1=6))
        self.doc.recompute()
        self.assertIn(array, assembly.Group)
        self.assertIs(array.LinkedObject, bolt)
        self.assertTrue(UtilsAssembly.isLinkGroup(array))
        # The component itself plus the five generated instances.
        self.assertEqual(UtilsAssembly.number_of_components_in(assembly), 6)

    def test_classify_selection(self):
        body = self.doc.addObject("PartDesign::Body", "Body")
        pad = self.doc.addObject("PartDesign::AdditiveBox", "Box")
        body.addObject(pad)
        box = self._box()
        self.assertEqual(bp.classify_selection([]), "empty")
        self.assertEqual(bp.classify_selection([pad]), "features")
        self.assertEqual(bp.classify_selection([body, box]), "objects")
        self.assertEqual(bp.classify_selection([pad, box]), "mixed")


if __name__ == "__main__":
    unittest.main()
