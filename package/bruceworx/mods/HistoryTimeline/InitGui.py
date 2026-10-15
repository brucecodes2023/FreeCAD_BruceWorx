# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI init. Registers a BruceWorx menu item and leaves the dock hidden.

FreeCAD execs this file. The module directory is already on sys.path.
"""


def _bootstrap():
    from history_timeline.dock import install

    install()


try:
    _bootstrap()
except Exception:
    # Main window may not exist yet if this file is imported early.
    from history_timeline.qtcompat import load_qt

    QtCore, _QtGui, _QtWidgets = load_qt()
    QtCore.QTimer.singleShot(0, _bootstrap)
