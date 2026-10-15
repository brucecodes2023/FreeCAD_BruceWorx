# SPDX-License-Identifier: LGPL-2.1-or-later
"""BruceWorx hooks command line.

Geometry commands open the document themselves. They are meant to run under
FreeCADCmd, which also treats loose arguments as files to open, so prefer one
of:

    FreeCADCmd -- addons/BruceWorx/hooks.py export-step --input a.FCStd --output a.step
    BW_HOOKS_ARGS='export-step --input a.FCStd --output a.step' \\
        FreeCADCmd addons/BruceWorx/hooks.py

``next`` and ``preview`` also run under plain Python.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import traceback

from bruceworx import freecad_io
from bruceworx.config_path import resolve_config_path
from bruceworx.numbering import assign_part_numbers, parse_part_number
from bruceworx.sources import open_number_source
from bruceworx.step_export import export_step
from bruceworx.tree import document_tree

COMMANDS = ("export-step", "list-tree", "rename", "next", "preview")
_ENTRY_NAMES = {"hooks.py", "hooks"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bw-hooks",
        description="Drive FreeCAD headlessly and issue BruceWorx part numbers.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    export = sub.add_parser("export-step", help="Export solids from an FCStd file to STEP")
    export.add_argument("--input", required=True, help="Source .FCStd document")
    export.add_argument("--output", required=True, help="Destination .step or .stp file")
    export.add_argument(
        "--objects",
        default="",
        help="Comma-separated object Name or Label values (default: solid roots)",
    )

    listing = sub.add_parser("list-tree", help="Write the document tree as JSON")
    listing.add_argument("--input", required=True, help="Source .FCStd document")
    listing.add_argument(
        "--output",
        default="",
        help="Write the tree JSON here (stdout BW_RESULT is a short pointer)",
    )

    rename = sub.add_parser(
        "rename",
        help="Set Labels and the document Label from the part-number source",
    )
    rename.add_argument("--input", required=True, help="Source .FCStd document")
    rename.add_argument("--program", required=True, help="Program code, for example LE")
    rename.add_argument(
        "--document-type",
        "--dt",
        required=True,
        help="2-digit document type, for example 01",
    )
    rename.add_argument("--config", default="", help="Numbering JSON (default: local config)")
    rename.add_argument("--revision", default="", help="Override the program's revision")
    rename.add_argument(
        "--parent",
        default="",
        help="Number under this parent drawing instead of taking a new one",
    )
    rename.add_argument(
        "--objects",
        default="",
        help="Comma-separated object Name or Label values (default: solid roots)",
    )
    rename.add_argument(
        "--output",
        default="",
        help="Save as this .FCStd (default: <directory>/<part-number>.FCStd)",
    )

    nxt = sub.add_parser("next", help="Allocate the next part number (no FreeCAD)")
    nxt.add_argument("--program", required=True)
    nxt.add_argument("--document-type", "--dt", required=True)
    nxt.add_argument("--config", default="")
    nxt.add_argument("--revision", default="")
    nxt.add_argument("--parent", default="", help="Existing parent drawing (PPPPP)")

    preview = sub.add_parser("preview", help="Show the next part number without allocating")
    preview.add_argument("--program", required=True)
    preview.add_argument("--document-type", "--dt", required=True)
    preview.add_argument("--config", default="")
    preview.add_argument("--revision", default="")
    preview.add_argument("--parent", default="", help="Existing parent drawing (PPPPP)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns a process exit code."""
    try:
        args = build_parser().parse_args(_command_argv(argv))
        if args.command == "export-step":
            return _export_step(args)
        if args.command == "list-tree":
            return _list_tree(args)
        if args.command == "rename":
            return _rename(args)
        if args.command == "next":
            return _number_command(args, allocate=True)
        if args.command == "preview":
            return _number_command(args, allocate=False)
        print(f"error: unknown command {args.command}", file=sys.stderr)
        return 2
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        if exc.code:
            print(exc.code, file=sys.stderr)
            return 1
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, NotImplementedError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception:  # noqa: BLE001 — CLI boundary
        traceback.print_exc()
        return 1


def split_entrypoint_argv(argv: list[str]) -> list[str]:
    """Strip FreeCADCmd / hooks.py noise off a full ``sys.argv``.

    Accepts an already-stripped command list as well.
    """
    args = list(argv)
    if args and os.path.basename(args[0]) not in _ENTRY_NAMES and args[0] not in COMMANDS:
        if args[0] not in {"-h", "--help"} and not args[0].startswith("-"):
            args = args[1:]
    if args and args[0] == "--":
        args = args[1:]
    if args and os.path.basename(args[0]) in _ENTRY_NAMES:
        args = args[1:]
    if args and args[0] == "--":
        args = args[1:]
    return args


def emit(payload: dict, output: str | None = None) -> None:
    """Write pretty JSON to ``output`` if given, and one ``BW_RESULT`` line."""
    if output:
        path = os.path.abspath(output)
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
    line = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    print(f"BW_RESULT {line}", flush=True)


def _command_argv(argv: list[str] | None) -> list[str]:
    if argv is not None:
        return list(argv)
    env = os.environ.get("BW_HOOKS_ARGS")
    if env:
        return shlex.split(env)
    return split_entrypoint_argv(sys.argv)


def _export_step(args) -> int:
    freecad_io.require_freecad()
    _require_fcstd(args.input)
    doc = freecad_io.open_document(args.input)
    try:
        names = _object_names(args.objects)
        chosen = None
        if names:
            from bruceworx.numbering import part_objects  # noqa: PLC0415

            chosen = part_objects(doc, names)
        result = export_step(doc, args.output, objects=chosen)
    finally:
        freecad_io.close_document(doc)
    emit(
        {
            "ok": True,
            "command": "export-step",
            "input": os.path.abspath(args.input),
            "output": result["output"],
            "objects": result["objects"],
        }
    )
    return 0


def _list_tree(args) -> int:
    freecad_io.require_freecad()
    _require_fcstd(args.input)
    doc = freecad_io.open_document(args.input)
    try:
        tree = document_tree(doc)
    finally:
        freecad_io.close_document(doc)
    if args.output:
        emit_path = os.path.abspath(args.output)
        directory = os.path.dirname(emit_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(emit_path, "w", encoding="utf-8") as handle:
            json.dump(tree, handle, indent=2)
            handle.write("\n")
        emit(
            {
                "ok": True,
                "command": "list-tree",
                "output": emit_path,
                "roots": len(tree["tree"]),
            }
        )
        return 0
    payload = {"ok": True, "command": "list-tree"}
    payload.update(tree)
    emit(payload)
    return 0


def _rename(args) -> int:
    freecad_io.require_freecad()
    _require_fcstd(args.input)
    if args.output:
        _require_fcstd_name(args.output)
    source = open_number_source(resolve_config_path(args.config or None, write=True))
    doc = freecad_io.open_document(args.input)
    try:
        names = _object_names(args.objects)
        targets = None
        if names:
            from bruceworx.numbering import part_objects  # noqa: PLC0415

            targets = part_objects(doc, names)
        assigned = assign_part_numbers(
            doc,
            source,
            args.program,
            args.document_type,
            objects=targets,
            revision=args.revision or None,
            parent=args.parent or None,
        )
        output = args.output or _default_rename_output(args.input, assigned["document_label"])
        saved = freecad_io.save_document(doc, output)
    finally:
        freecad_io.close_document(doc)
    assigned["ok"] = True
    assigned["command"] = "rename"
    assigned["output"] = saved
    emit(assigned)
    return 0


def _number_command(args, *, allocate: bool) -> int:
    path = resolve_config_path(args.config or None, write=allocate)
    source = open_number_source(path)
    revision = args.revision or None
    parent = args.parent or None
    if allocate:
        number = source.allocate(args.program, args.document_type, revision, parent)
        command = "next"
    else:
        number = source.preview(args.program, args.document_type, revision, parent)
        command = "preview"
    parsed = parse_part_number(number)
    emit(
        {
            "ok": True,
            "command": command,
            "program": parsed["program"],
            "document_type": parsed["document_type"],
            "parent": parsed["parent"],
            "sub": parsed["sub"],
            "part_number": number,
            "config": path,
        }
    )
    return 0


def _default_rename_output(input_path: str, part_number: str) -> str:
    """File name FreeCAD will show as the document label after the next open.

    On load, FreeCAD sets Document.Label from the file name and discards the
    label stored in the file. Saving as ``<part-number>.FCStd`` is what makes
    the document name stick.
    """
    directory = os.path.dirname(os.path.abspath(input_path))
    return os.path.join(directory, part_number + ".FCStd")


def _object_names(text: str) -> list[str] | None:
    if not text.strip():
        return None
    return [part.strip() for part in text.split(",") if part.strip()]


def _require_fcstd(path: str) -> None:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    _require_fcstd_name(path)


def _require_fcstd_name(path: str) -> None:
    if not str(path).lower().endswith(".fcstd"):
        raise ValueError(f"document path must end in .FCStd, got {path!r}")
