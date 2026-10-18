# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI entry for the hooks add-on: BruceWorx → Assign Part Number….

Loaded from InitGui.py when the add-on is on (default). Uses the same
``bruceworx.macro.run`` as ``macros/PartNumber.FCMacro``; the only additions
are a program / document-type picker when the numbering file has more than
one, and a writable default numbering file in the user data folder.
"""

from __future__ import annotations

import os
import shutil

from bruceworx import config_path

COMMAND_NAME = "BruceWorx_PartNumber"
ACTION_NAME = "BruceWorxPartNumberAction"


def user_config_dir() -> str:
    import FreeCAD

    return os.path.join(FreeCAD.getUserAppDataDir(), "BruceWorx", "numbering")


def gui_config_path() -> str:
    """Numbering file for the GUI command.

    ``BW_NUMBERING_CONFIG`` wins. Otherwise an existing
    ``config/numbering.json`` next to the add-on (a source checkout) is used.
    Otherwise ``<UserAppData>/BruceWorx/numbering/numbering.json``, seeded
    from the shipped example and type table on first use. The installed
    add-on folder can be read-only (an app bundle), so it is not written.
    """
    explicit = os.environ.get("BW_NUMBERING_CONFIG")
    if explicit:
        return os.path.abspath(explicit)
    local = config_path.local_config_path()
    if os.path.isfile(local):
        return local
    target_dir = user_config_dir()
    target = os.path.join(target_dir, config_path.LOCAL_NAME)
    if not os.path.isfile(target):
        os.makedirs(target_dir, exist_ok=True)
        shutil.copyfile(config_path.example_config_path(), target)
        types = os.path.join(config_path.config_dir(), "document_types.json")
        if os.path.isfile(types):
            types_target = os.path.join(target_dir, "document_types.json")
            if not os.path.isfile(types_target):
                shutil.copyfile(types, types_target)
    return target


def _qt():
    try:
        from PySide6 import QtGui, QtWidgets
    except ImportError:
        from PySide import QtGui

        QtWidgets = QtGui
    return QtGui, QtWidgets


def _pick(parent, title, label, codes):
    if len(codes) == 1:
        return codes[0]
    _QtGui, QtWidgets = _qt()
    value, ok = QtWidgets.QInputDialog.getItem(parent, title, label, codes, 0, False)
    if not ok:
        return None
    return str(value)


class PartNumberCommand:
    def GetResources(self):
        return {
            "MenuText": "Assign Part Number…",
            "ToolTip": (
                "Label the selected objects (or the solid roots) and the document with the "
                "next BruceWorx part number, {PROG}-{DT}-{PPPPP}-{SSS}-{REV}. "
                "Turn the hooks add-on off on Preferences → BruceWorx."
            ),
        }

    def IsActive(self):
        import FreeCAD

        return FreeCAD.ActiveDocument is not None

    def Activated(self, *_args):
        import FreeCAD
        import FreeCADGui

        from bruceworx.macro import run
        from bruceworx.sources import open_number_source

        _QtGui, QtWidgets = _qt()
        window = FreeCADGui.getMainWindow()
        try:
            config = gui_config_path()
            source = open_number_source(config)
            program = os.environ.get("BW_PROGRAM") or _pick(
                window, "Assign Part Number", "Program:", list(source.programs())
            )
            if not program:
                return
            document_type = (
                os.environ.get("BW_DOCUMENT_TYPE")
                or os.environ.get("BW_DT")
                or _pick(window, "Assign Part Number", "Document type:", list(source.document_types()))
            )
            if not document_type:
                return
            doc = FreeCAD.ActiveDocument
            doc.openTransaction("Assign part number")
            try:
                result = run(program=program, document_type=document_type, config=config, doc=doc)
            except Exception:
                doc.abortTransaction()
                raise
            doc.commitTransaction()
        except Exception as exc:
            FreeCAD.Console.PrintError(f"BruceWorx part number: {exc}\n")
            QtWidgets.QMessageBox.warning(window, "Assign Part Number", str(exc))
            return
        FreeCAD.Console.PrintMessage(f"BruceWorx part number: {result}\n")


def install():
    import FreeCADGui

    FreeCADGui.addCommand(COMMAND_NAME, PartNumberCommand())
    try:
        import bruceworx_menu
    except ImportError:
        return  # Not a BruceWorx build: the command exists, there is no menu.
    QtGui, _QtWidgets = _qt()
    window = FreeCADGui.getMainWindow()
    action = QtGui.QAction("Assign Part Number…", window)
    action.setToolTip(PartNumberCommand().GetResources()["ToolTip"])
    action.triggered.connect(lambda _checked=False: FreeCADGui.runCommand(COMMAND_NAME))
    bruceworx_menu.add_action(action, ACTION_NAME)
