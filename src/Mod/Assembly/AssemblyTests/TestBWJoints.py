# SPDX-License-Identifier: LGPL-2.1-or-later
# [BW] BruceWorx joint behaviour: drag with and without limits, limits
# measured from datums, and joints made where the parts are.

import math
import unittest

import FreeCAD as App

import JointObject
import UtilsAssembly


def _msg(text, end="\n"):
    App.Console.PrintMessage(text + end)


class TestBWJoints(unittest.TestCase):
    def setUp(self):
        self.doc = App.newDocument(self.__class__.__name__)
        self.assembly = self.doc.addObject("Assembly::AssemblyObject", "Assembly")
        self.jointgroup = self.assembly.newObject("Assembly::JointGroup", "Joints")

        self.base = self.assembly.newObject("Part::Box", "Base")
        self.base.Length = self.base.Width = self.base.Height = 10
        self.arm = self.assembly.newObject("Part::Box", "Arm")
        self.arm.Length, self.arm.Width, self.arm.Height = 40, 5, 5
        self.arm.Placement = App.Placement(App.Vector(30, 30, 30), App.Rotation(10, 20, 30))

        ground = self.jointgroup.newObject("App::FeaturePython", "Ground")
        JointObject.GroundedJoint(ground, self.base)

    def tearDown(self):
        App.closeDocument(self.doc.Name)

    # ----- helpers ------------------------------------------------------------

    def makeRevolute(self, keep=False):
        joint = self.jointgroup.newObject("App::FeaturePython", "Revolute")
        JointObject.Joint(joint, JointObject.JointTypes.index("Revolute"))
        joint.KeepPosition = keep
        refs = [[self.base, ["Face6", "Vertex6"]], [self.arm, ["Face5", "Vertex1"]]]
        joint.Proxy.setJointConnectors(joint, refs)
        self.doc.recompute()
        return joint

    def jcsAngle(self, joint):
        return math.degrees(UtilsAssembly.getJointXYAngle(joint))

    def turnArm(self, joint, degrees):
        """Turn the arm about the joint axis so the joint reads `degrees`."""
        plc1 = UtilsAssembly.getJcsGlobalPlc(joint.Placement1, joint.Reference1)
        axis = plc1.Rotation.multVec(App.Vector(0, 0, 1))
        turn = App.Placement(App.Vector(), App.Rotation(axis, degrees - self.jcsAngle(joint)), plc1.Base)
        self.arm.Placement = turn * self.arm.Placement

    def drag(self, joint, angles):
        """Drag the arm through `angles` (joint readings); returns where it ends up."""
        self.assembly.preDrag([self.arm])
        for angle in angles:
            self.turnArm(joint, angle)
            self.assembly.doDragStep()
        self.assembly.postDrag()
        return self.jcsAngle(joint)

    # ----- drag ---------------------------------------------------------------

    def test_drag_is_free_without_limits(self):
        joint = self.makeRevolute()
        self.assertFalse(joint.EnableAngleMin or joint.EnableAngleMax)
        self.assertAlmostEqual(self.drag(joint, [60, 120, 170]), 170, places=3)
        self.assertAlmostEqual(self.drag(joint, [100, 0, -120]), -120, places=3)

    def test_drag_stops_at_limits(self):
        joint = self.makeRevolute()
        joint.EnableAngleMin = joint.EnableAngleMax = True
        joint.AngleMin, joint.AngleMax = 0, 90
        self.turnArm(joint, 45)
        self.assembly.solve()
        self.assertAlmostEqual(self.drag(joint, range(50, 140, 10)), 90, delta=0.2)
        self.assertAlmostEqual(self.drag(joint, range(80, -40, -20)), 0, delta=0.2)

    # ----- limits from datums -----------------------------------------------------

    def datumAngle(self, joint):
        """Angle from the base's Face1 to the arm's Face1, about the joint axis,
        worked out from the geometry alone."""
        plc1 = UtilsAssembly.getJcsGlobalPlc(joint.Placement1, joint.Reference1)
        axis = plc1.Rotation.multVec(App.Vector(0, 0, 1))

        def flat(vector):
            return vector - axis * vector.dot(axis)

        n1 = flat(self.base.Shape.Face1.normalAt(0, 0))
        n2 = flat(self.arm.Shape.Face1.normalAt(0, 0))
        return math.degrees(math.atan2(n1.cross(n2).dot(axis), n1.dot(n2)))

    def test_reading_follows_the_datums(self):
        joint = self.makeRevolute()
        joint.LimitDatum1 = [self.base, ["Face1", "Face1"]]
        joint.LimitDatum2 = [self.arm, ["Face1", "Face1"]]
        self.doc.recompute()
        for angle in (-150, -30, 0, 45, 120):
            self.turnArm(joint, angle)
            reading = JointObject.limitReading(joint)[0]
            self.assertAlmostEqual(reading, self.datumAngle(joint), places=6, msg=f"at {angle}")

    def test_drag_stops_at_limits_from_datums(self):
        joint = self.makeRevolute()
        joint.LimitDatum1 = [self.base, ["Face1", "Face1"]]
        joint.LimitDatum2 = [self.arm, ["Face1", "Face1"]]
        joint.EnableAngleMin = joint.EnableAngleMax = True
        joint.AngleMin, joint.AngleMax = 0, 30
        self.doc.recompute()
        zero = joint.LimitAngleZero.Value
        self.turnArm(joint, zero + 10)  # 10 deg from the datums
        self.assembly.solve()
        self.assertAlmostEqual(self.datumAngle(joint), 10, places=4)
        self.drag(joint, [zero + a for a in range(15, 80, 5)])
        self.assertAlmostEqual(self.datumAngle(joint), 30, delta=0.2)
        self.drag(joint, [zero + a for a in range(25, -60, -5)])
        self.assertAlmostEqual(self.datumAngle(joint), 0, delta=0.2)

    def test_datum_square_to_the_axis_is_flagged(self):
        joint = self.makeRevolute()
        joint.LimitDatum1 = [self.base, ["Face6", "Face6"]]  # the top: square to the axis
        joint.LimitDatum2 = [self.arm, ["Face1", "Face1"]]
        self.doc.recompute()
        self.assertEqual(JointObject.limitDatumProblems(joint), ["LimitDatum1"])
        joint.LimitDatum1 = [self.base, ["Face1", "Face1"]]
        self.assertEqual(JointObject.limitDatumProblems(joint), [])

    def test_no_datums_means_joint_axes(self):
        joint = self.makeRevolute()
        self.assertEqual(joint.LimitAngleZero.Value, 0.0)
        self.assertEqual(joint.LimitLengthZero.Value, 0.0)

    # ----- keep parts where they are --------------------------------------------

    def test_joint_moves_the_part_by_default(self):
        before = App.Placement(self.arm.Placement)
        self.makeRevolute()
        self.assertFalse(self.arm.Placement.isSame(before, 1e-6))

    def test_keep_position_leaves_parts_alone(self):
        before = App.Placement(self.arm.Placement)
        joint = self.makeRevolute(keep=True)
        self.assertTrue(self.arm.Placement.isSame(before, 1e-6), self.arm.Placement)
        self.assembly.solve()
        self.assertTrue(self.arm.Placement.isSame(before, 1e-6), self.arm.Placement)

        # The joint still works: the arm turns about it and stays on it.
        self.assertAlmostEqual(self.drag(joint, [20, 40]), 40, places=3)
        plc1 = UtilsAssembly.getJcsGlobalPlc(joint.Placement1, joint.Reference1)
        plc2 = UtilsAssembly.getJcsGlobalPlc(joint.Placement2, joint.Reference2)
        self.assertLess((plc1.Base - plc2.Base).Length, 1e-6)


if __name__ == "__main__":
    unittest.main()
