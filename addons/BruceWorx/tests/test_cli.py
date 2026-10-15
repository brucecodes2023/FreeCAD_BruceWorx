# SPDX-License-Identifier: LGPL-2.1-or-later
"""CLI parsing, numbering commands, and rename/export wiring without FreeCAD."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bruceworx import freecad_io  # noqa: E402
from bruceworx.cli import (  # noqa: E402
    _default_rename_output,
    emit,
    main,
    split_entrypoint_argv,
)
from bruceworx.macro import run as run_macro  # noqa: E402
from bruceworx.macro import sole_document_type, sole_program  # noqa: E402
from bruceworx.sources import JsonNumberSource  # noqa: E402
from fakes import FakeDoc, FakeObj, FakeShape  # noqa: E402

EXAMPLE = "LE-01-01001-001-A"


def _config(directory, next_parent=1001):
    path = os.path.join(directory, "numbering.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "source": "json",
                "format": "{PROG}-{DT}-{PPPPP}-{SSS}-{REV}",
                "document_types": {
                    "01": {"placeholder": True, "name": "PLACEHOLDER"},
                    "02": {"placeholder": True, "name": "PLACEHOLDER"},
                },
                "programs": {
                    "LE": {
                        "revision": "A",
                        "counters": {
                            "01": {"next_parent": next_parent, "parents": {}},
                        },
                    }
                },
            },
            handle,
        )
    return path


def _result(stdout: str) -> dict:
    lines = [line for line in stdout.splitlines() if line.startswith("BW_RESULT ")]
    if not lines:
        raise AssertionError(f"no BW_RESULT in {stdout!r}")
    return json.loads(lines[-1][len("BW_RESULT ") :])


class ArgvTests(unittest.TestCase):
    def test_plain_python(self):
        argv = ["hooks.py", "next", "--program", "LE"]
        self.assertEqual(split_entrypoint_argv(argv), ["next", "--program", "LE"])

    def test_freecad_double_dash(self):
        argv = [
            "FreeCADCmd",
            "--",
            "/opt/addons/BruceWorx/hooks.py",
            "export-step",
            "--input",
            "a.FCStd",
            "--output",
            "a.step",
        ]
        self.assertEqual(
            split_entrypoint_argv(argv),
            ["export-step", "--input", "a.FCStd", "--output", "a.step"],
        )

    def test_already_stripped(self):
        argv = ["preview", "--program", "LE"]
        self.assertEqual(split_entrypoint_argv(argv), argv)

    def test_help_flag_kept(self):
        self.assertEqual(split_entrypoint_argv(["--help"]), ["--help"])


class NumberCommandTests(unittest.TestCase):
    def test_next_then_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _config(directory)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(
                    ["next", "--program", "LE", "--document-type", "01", "--config", path]
                )
            self.assertEqual(code, 0)
            issued = _result(buf.getvalue())
            self.assertEqual(issued["part_number"], EXAMPLE)
            self.assertEqual(issued["document_type"], "01")
            self.assertEqual(issued["parent"], "01001")
            self.assertEqual(issued["sub"], "001")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(
                    ["preview", "--program", "LE", "--document-type", "01", "--config", path]
                )
            self.assertEqual(code, 0)
            self.assertEqual(_result(buf.getvalue())["part_number"], "LE-01-01002-001-A")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(
                    [
                        "preview",
                        "--program",
                        "LE",
                        "--dt",
                        "01",
                        "--parent",
                        "01001",
                        "--config",
                        path,
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(_result(buf.getvalue())["part_number"], "LE-01-01001-002-A")

    def test_env_args_when_argv_omitted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = _config(directory)
            os.environ["BW_HOOKS_ARGS"] = (
                f'preview --program LE --document-type 01 --config "{path}"'
            )
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = main(None)
            finally:
                del os.environ["BW_HOOKS_ARGS"]
            self.assertEqual(code, 0)
            self.assertEqual(_result(buf.getvalue())["part_number"], EXAMPLE)
            with open(path, encoding="utf-8") as handle:
                saved = json.load(handle)
            bucket = saved["programs"]["LE"]["counters"]["01"]
            self.assertEqual(bucket["next_parent"], 1001)
            self.assertEqual(bucket["parents"], {})

    def test_usage_error(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            code = main(["export-step"])
        self.assertEqual(code, 2)

    def test_help(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("export-step", buf.getvalue())
        self.assertIn("list-tree", buf.getvalue())
        self.assertIn("rename", buf.getvalue())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(["next", "--help"])
        self.assertEqual(code, 0)
        self.assertIn("--document-type", buf.getvalue())
        self.assertIn("--parent", buf.getvalue())

    def test_missing_freecad(self):
        real = freecad_io.freecad_available
        freecad_io.freecad_available = lambda: False
        try:
            with tempfile.TemporaryDirectory() as directory:
                fcstd = os.path.join(directory, "a.FCStd")
                with open(fcstd, "wb") as handle:
                    handle.write(b"not a real document")
                buf = io.StringIO()
                with contextlib.redirect_stderr(buf):
                    code = main(
                        [
                            "export-step",
                            "--input",
                            fcstd,
                            "--output",
                            os.path.join(directory, "a.step"),
                        ]
                    )
        finally:
            freecad_io.freecad_available = real
        self.assertEqual(code, 1)
        self.assertIn("FreeCADCmd", buf.getvalue())


class WiredCommandTests(unittest.TestCase):
    def test_rename_and_list_and_export_use_injected_freecad(self):
        box = FakeObj("Box", "Box", "Part::Box", FakeShape())
        doc = FakeDoc("Unnamed", "Unnamed", [box])
        opened = {}

        def open_document(path):
            opened["path"] = path
            return doc

        real = {
            "available": freecad_io.freecad_available,
            "open": freecad_io.open_document,
            "save": freecad_io.save_document,
            "close": freecad_io.close_document,
            "export": freecad_io.export_step,
        }
        freecad_io.freecad_available = lambda: True
        freecad_io.open_document = open_document
        freecad_io.save_document = lambda document, path: document.saveAs(path) or path
        freecad_io.close_document = lambda _document: None
        try:
            with tempfile.TemporaryDirectory() as directory:
                fcstd = os.path.join(directory, "box.FCStd")
                with open(fcstd, "wb") as handle:
                    handle.write(b"fcstd")
                config = _config(directory)
                step = os.path.join(directory, "box.step")
                tree_path = os.path.join(directory, "tree.json")
                renamed = os.path.join(directory, "numbered.FCStd")

                def exporter(objects, path):
                    self.assertEqual([obj.Name for obj in objects], ["Box"])
                    with open(path, "w", encoding="utf-8") as handle:
                        handle.write("ISO-10303-21;\n")

                freecad_io.export_step = exporter
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = main(["export-step", "--input", fcstd, "--output", step])
                self.assertEqual(code, 0)
                self.assertEqual(_result(buf.getvalue())["objects"], ["Box"])
                with open(step, encoding="utf-8") as handle:
                    self.assertTrue(handle.read().startswith("ISO-10303-21"))
                freecad_io.export_step = real["export"]

                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = main(["list-tree", "--input", fcstd, "--output", tree_path])
                self.assertEqual(code, 0)
                with open(tree_path, encoding="utf-8") as handle:
                    tree = json.load(handle)
                self.assertEqual(tree["tree"][0]["name"], "Box")
                self.assertEqual(_result(buf.getvalue())["roots"], 1)

                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    code = main(
                        [
                            "rename",
                            "--input",
                            fcstd,
                            "--program",
                            "LE",
                            "--document-type",
                            "01",
                            "--config",
                            config,
                            "--output",
                            renamed,
                        ]
                    )
                self.assertEqual(code, 0)
                payload = _result(buf.getvalue())
                self.assertEqual(payload["document_label"], EXAMPLE)
                self.assertEqual(payload["document_name"], "Unnamed")
                self.assertEqual(payload["parent"], "01001")
                self.assertEqual(payload["sub"], "001")
                self.assertEqual(box.Label, EXAMPLE)
                self.assertEqual(os.path.abspath(doc.saved), os.path.abspath(renamed))
                self.assertEqual(os.path.abspath(opened["path"]), os.path.abspath(fcstd))
        finally:
            freecad_io.freecad_available = real["available"]
            freecad_io.open_document = real["open"]
            freecad_io.save_document = real["save"]
            freecad_io.close_document = real["close"]
            freecad_io.export_step = real["export"]


class MacroTests(unittest.TestCase):
    def test_macro_run_numbers_document(self):
        box = FakeObj("Box", shape=FakeShape())
        doc = FakeDoc("Unnamed", "Unnamed", [box])
        with tempfile.TemporaryDirectory() as directory:
            path = _config(directory)
            result = run_macro(program="LE", document_type="01", config=path, doc=doc)
        self.assertEqual(result["document_label"], EXAMPLE)
        self.assertEqual(box.Label, EXAMPLE)

    def test_sole_program(self):
        with tempfile.TemporaryDirectory() as directory:
            source = JsonNumberSource(_config(directory))
            self.assertEqual(sole_program(source), "LE")

    def test_two_document_types_need_an_explicit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            source = JsonNumberSource(_config(directory))
            with self.assertRaises(ValueError) as caught:
                sole_document_type(source)
        self.assertIn("01", str(caught.exception))
        self.assertIn("02", str(caught.exception))


class RenamePathTests(unittest.TestCase):
    def test_default_file_is_the_part_number(self):
        path = _default_rename_output("/tmp/jobs/box.FCStd", EXAMPLE)
        self.assertEqual(path, os.path.join("/tmp/jobs", EXAMPLE + ".FCStd"))


class EmitTests(unittest.TestCase):
    def test_emit_file_and_line(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "out.json")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                emit({"ok": True, "part_number": EXAMPLE}, path)
            with open(path, encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertEqual(saved["part_number"], EXAMPLE)
            self.assertEqual(_result(buf.getvalue())["ok"], True)


if __name__ == "__main__":
    unittest.main()
