# SPDX-License-Identifier: LGPL-2.1-or-later
"""GUI entry for the hooks add-on: BruceWorx → Assign Part Number… and the
one-part-per-file tools (BW-ASM-01).

Loaded from InitGui.py when the add-on is on (default). Assign Part Number
uses the same ``bruceworx.macro.run`` as ``macros/PartNumber.FCMacro``; the
only additions are a program / document-type picker when the numbering file
has more than one, and a writable default numbering file in the user data
folder.

Make Parts External…, Pack and Go… and Fix Broken References… are thin
dialogs over ``bruceworx.filemodel`` and ``bruceworx.filerefs``, which the
``make-external``, ``pack-and-go`` and ``resolve-refs`` CLI commands also
use. Off switch: ``BaseApp/Preferences/BruceWorx/FileModelTools`` (the
"One part per file" box on Preferences → BruceWorx), next start.
"""

from __future__ import annotations

import os
import shutil

from bruceworx import config_path

COMMAND_NAME = "BruceWorx_PartNumber"
ACTION_NAME = "BruceWorxPartNumberAction"
FILE_MODEL_KEY = "FileModelTools"


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


def _report_dialog(title, report, ok_text):
    """Show a short summary; the full JSON goes to the Report view."""
    import json

    import FreeCAD
    import FreeCADGui

    _QtGui, QtWidgets = _qt()
    FreeCAD.Console.PrintMessage(f"BruceWorx {title}: {json.dumps(report, indent=2)}\n")
    box = QtWidgets.QMessageBox.information if report.get("ok") else QtWidgets.QMessageBox.warning
    box(FreeCADGui.getMainWindow(), title, ok_text if report.get("ok") else _problems(report))


def _problems(report):
    lines = []
    for key in ("missing", "unresolved", "ambiguous"):
        for entry in report.get(key, []):
            lines.append(f"{key}: {os.path.basename(entry['owner'])} → {entry['file']}")
    for path in report.get("outside_destination", []):
        lines.append(f"outside the folder: {path}")
    return "\n".join(lines[:20]) or "See the Report view."


def _saved_active_document(title):
    import FreeCAD
    import FreeCADGui

    _QtGui, QtWidgets = _qt()
    doc = FreeCAD.ActiveDocument
    if doc is None:
        return None
    if not doc.FileName:
        QtWidgets.QMessageBox.warning(FreeCADGui.getMainWindow(), title, "Save the document first.")
        return None
    if doc.isTouched() or any(getattr(d, "isTouched", lambda: False)() for d in FreeCAD.listDocuments().values()):
        answer = QtWidgets.QMessageBox.question(
            FreeCADGui.getMainWindow(), title, "Save changes to open documents first?"
        )
        if answer != QtWidgets.QMessageBox.Yes:
            return None
        for d in FreeCAD.listDocuments().values():
            if d.FileName and d.isTouched():
                d.save()
    return doc


class MakeExternalCommand:
    TITLE = "Make Parts External"

    def GetResources(self):
        return {
            "MenuText": "Make Parts External…",
            "ToolTip": (
                "One part per file: save every body of this document as its own part file "
                "and turn this document into an assembly of links to them. The open file is "
                "not changed; the assembly is saved under a new name in the folder you pick."
            ),
        }

    def IsActive(self):
        import FreeCAD

        return FreeCAD.ActiveDocument is not None

    def Activated(self, *_args):
        import FreeCAD
        import FreeCADGui

        from bruceworx.filemodel import make_external, plan_targets
        from bruceworx.numbering import allocate_numbers
        from bruceworx.sources import open_number_source

        _QtGui, QtWidgets = _qt()
        window = FreeCADGui.getMainWindow()
        doc = _saved_active_document(self.TITLE)
        if doc is None:
            return
        selected = [o.Name for o in FreeCADGui.Selection.getSelection(doc.Name)] or None
        targets = plan_targets(doc, selected)
        if not targets:
            QtWidgets.QMessageBox.warning(window, self.TITLE, "No bodies or solids to make external.")
            return
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            window, f"{self.TITLE}: folder for the assembly and {len(targets)} part files",
            os.path.dirname(doc.FileName),
        )
        if not folder:
            return
        numbers = None
        answer = QtWidgets.QMessageBox.question(
            window, self.TITLE, "Give the assembly and each part a BruceWorx part number?"
        )
        try:
            if answer == QtWidgets.QMessageBox.Yes:
                config = gui_config_path()
                source = open_number_source(config)
                program = _pick(window, self.TITLE, "Program:", list(source.programs()))
                document_type = program and _pick(
                    window, self.TITLE, "Document type:", list(source.document_types())
                )
                if not document_type:
                    return
                numbers = allocate_numbers(source, program, document_type, len(targets) + 1)
            report = make_external(doc, folder, objects=[t.Name for t in targets], numbers=numbers)
        except Exception as exc:
            FreeCAD.Console.PrintError(f"BruceWorx make external: {exc}\n")
            QtWidgets.QMessageBox.warning(window, self.TITLE, str(exc))
            return
        _report_dialog(
            self.TITLE,
            report,
            f"{len(report['parts'])} part files written.\nThis window now shows the assembly "
            f"{os.path.basename(report['assembly'])}.",
        )


class PackAndGoCommand:
    TITLE = "Pack and Go"

    def GetResources(self):
        return {
            "MenuText": "Pack and Go…",
            "ToolTip": "Copy this assembly and every file it links into an empty folder.",
        }

    def IsActive(self):
        import FreeCAD

        return FreeCAD.ActiveDocument is not None

    def Activated(self, *_args):
        import FreeCAD
        import FreeCADGui

        from bruceworx.filerefs import pack_and_go

        _QtGui, QtWidgets = _qt()
        window = FreeCADGui.getMainWindow()
        doc = _saved_active_document(self.TITLE)
        if doc is None:
            return
        folder = QtWidgets.QFileDialog.getExistingDirectory(window, f"{self.TITLE}: empty folder")
        if not folder:
            return
        try:
            report = pack_and_go(doc.FileName, folder)
        except Exception as exc:
            FreeCAD.Console.PrintError(f"BruceWorx pack and go: {exc}\n")
            QtWidgets.QMessageBox.warning(window, self.TITLE, str(exc))
            return
        _report_dialog(self.TITLE, report, f"{len(report['files'])} files copied to {folder}.")


class FixReferencesCommand:
    TITLE = "Fix Broken References"

    def GetResources(self):
        return {
            "MenuText": "Fix Broken References…",
            "ToolTip": (
                "Find part files this assembly can no longer reach, by name, under a folder you "
                "pick, and relink them with relative paths. Close and reopen the assembly afterwards."
            ),
        }

    def IsActive(self):
        import FreeCAD

        return FreeCAD.ActiveDocument is not None

    def Activated(self, *_args):
        import FreeCAD
        import FreeCADGui

        from bruceworx import filerefs

        _QtGui, QtWidgets = _qt()
        window = FreeCADGui.getMainWindow()
        doc = FreeCAD.ActiveDocument
        if doc is None or not doc.FileName:
            return
        path = doc.FileName
        graph = filerefs.walk(path)
        if graph.ok and not graph.absolute:
            QtWidgets.QMessageBox.information(window, self.TITLE, "All references resolve.")
            return
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            window, f"{self.TITLE}: folder to search", os.path.dirname(path)
        )
        if not folder:
            return
        # The file is rewritten on disk, so the open copy must not be saved over it.
        FreeCAD.closeDocument(doc.Name)
        try:
            report = filerefs.resolve(path, [folder])
        finally:
            FreeCAD.openDocument(path)
        _report_dialog(self.TITLE, report, f"{len(report['fixed'])} links repaired.")


FILE_MODEL_COMMANDS = (
    ("BruceWorx_MakeExternal", MakeExternalCommand, "BruceWorxMakeExternalAction"),
    ("BruceWorx_PackAndGo", PackAndGoCommand, "BruceWorxPackAndGoAction"),
    ("BruceWorx_FixReferences", FixReferencesCommand, "BruceWorxFixReferencesAction"),
)


def file_model_enabled() -> bool:
    import FreeCAD

    return FreeCAD.ParamGet("User parameter:BaseApp/Preferences/BruceWorx").GetBool(FILE_MODEL_KEY, True)


def install():
    import FreeCADGui

    commands = [(COMMAND_NAME, PartNumberCommand, ACTION_NAME)]
    if file_model_enabled():
        commands += list(FILE_MODEL_COMMANDS)
    for name, cls, _action in commands:
        FreeCADGui.addCommand(name, cls())
    try:
        import bruceworx_menu
    except ImportError:
        return  # Not a BruceWorx build: the commands exist, there is no menu.
    QtGui, _QtWidgets = _qt()
    window = FreeCADGui.getMainWindow()
    for name, cls, action_name in commands:
        resources = cls().GetResources()
        action = QtGui.QAction(resources["MenuText"], window)
        action.setToolTip(resources["ToolTip"])
        action.triggered.connect(lambda _checked=False, n=name: FreeCADGui.runCommand(n))
        bruceworx_menu.add_action(action, action_name)
