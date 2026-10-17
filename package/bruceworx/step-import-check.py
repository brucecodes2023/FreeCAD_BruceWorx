# SPDX-License-Identifier: LGPL-2.1-or-later
# BruceWorx STEP smoke: import one upstream STEP file with FreeCADCmd and fail
# if no shapes come in. Invoked as:
#   FreeCADCmd package/bruceworx/step-import-check.py --pass path/to/file.stp
import sys

import FreeCAD
import Import

path = sys.argv[-1]
doc = FreeCAD.newDocument("bwstep")
Import.insert(path, doc.Name)
shapes = [o for o in doc.Objects if hasattr(o, "Shape") and not o.Shape.isNull()]
solids = sum(len(o.Shape.Solids) for o in shapes)
print(
    "BW STEP check: file=%s objects=%d shapes=%d solids=%d"
    % (path, len(doc.Objects), len(shapes), solids)
)
if not shapes:
    print("BW STEP check: FAIL - no shapes imported")
    sys.exit(1)
print("BW STEP check: PASS")
