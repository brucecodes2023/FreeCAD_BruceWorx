# SPDX-License-Identifier: LGPL-2.1-or-later
"""PySide6, or FreeCAD's PySide shim (QtWidgets re-exported on QtGui)."""


def load_qt():
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide import QtCore, QtGui

        QtWidgets = QtGui
    return QtCore, QtGui, QtWidgets


def qt_enum(owner, *paths):
    """Return the first enum that exists.

    Each path is a tuple of attribute names, for example
    ``("AlignmentFlag", "AlignLeft")`` on PySide6 or ``("AlignLeft",)`` on the shim.
    """
    for path in paths:
        current = owner
        found = True
        for part in path:
            if not hasattr(current, part):
                found = False
                break
            current = getattr(current, part)
        if found:
            return current
    raise AttributeError(paths)
