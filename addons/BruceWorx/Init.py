# SPDX-License-Identifier: LGPL-2.1-or-later
"""Loaded when this folder is placed on FreeCAD's Mod path.

Headless use does not need that. Run hooks.py under FreeCADCmd; see README.md.
"""

import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)
