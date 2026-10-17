# SPDX-License-Identifier: LGPL-2.1-or-later
"""Small document doubles for unit tests. Not a FreeCAD stand-in."""


class FakeShape:
    def __init__(self, solids=1, null=False):
        self.Solids = [object()] * solids
        self._null = null

    def isNull(self):
        return self._null


class FakeObj:
    def __init__(self, name, label=None, typeid="Part::Feature", shape=None, children=None):
        self.Name = name
        self.Label = name if label is None else label
        self.TypeId = typeid
        self.Shape = shape
        self.OutList = list(children or [])


class FakeDoc:
    def __init__(self, name, label, objects):
        self.Name = name
        self.Label = label
        self.FileName = ""
        self.Objects = list(objects)
        self.saved = None

    def recompute(self):
        return None

    def saveAs(self, path):
        self.saved = path
        self.FileName = path
