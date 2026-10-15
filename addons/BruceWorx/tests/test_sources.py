# SPDX-License-Identifier: LGPL-2.1-or-later
"""JSON numbering source and the Ops API placeholder."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bruceworx.config_path import example_config_path, resolve_config_path  # noqa: E402
from bruceworx.sources import (  # noqa: E402
    JsonNumberSource,
    NumberSource,
    OpsApiNumberSource,
    open_number_source,
)


def _write(path, programs=None, **extra):
    payload = {
        "source": "json",
        "format": "{PROG}-{NNNNN}-{REV}",
        "number_width": 5,
        "programs": programs
        or {"LE": {"description": "example", "revision": "A", "next": 1001}},
    }
    payload.update(extra)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)


class JsonSourceTests(unittest.TestCase):
    def test_allocate_persists_and_preview_does_not(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "numbering.json")
            _write(path)
            source = JsonNumberSource(path)
            self.assertEqual(source.preview("LE"), "LE-01001-A")
            self.assertEqual(source.preview("le"), "LE-01001-A")
            self.assertEqual(source.allocate("LE"), "LE-01001-A")
            self.assertEqual(source.preview("LE"), "LE-01002-A")
            with open(path, encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertEqual(saved["programs"]["LE"]["next"], 1002)
            self.assertFalse(os.path.exists(path + ".tmp"))

    def test_revision_override_does_not_change_stored_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "numbering.json")
            _write(path)
            source = JsonNumberSource(path)
            self.assertEqual(source.allocate("LE", revision="C"), "LE-01001-C")
            with open(path, encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertEqual(saved["programs"]["LE"]["revision"], "A")
            self.assertEqual(saved["programs"]["LE"]["next"], 1002)

    def test_unknown_program(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "numbering.json")
            _write(path)
            with self.assertRaises(KeyError):
                JsonNumberSource(path).allocate("NOPE")

    def test_rejects_non_json_source_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "numbering.json")
            _write(path, source="ops")
            with self.assertRaises(ValueError) as caught:
                JsonNumberSource(path).preview("LE")
            self.assertIn("FCB-P2-03", str(caught.exception))

    def test_rejects_wrong_width_and_format(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "numbering.json")
            _write(path, number_width=4)
            with self.assertRaises(ValueError):
                JsonNumberSource(path).preview("LE")
            _write(path, format="{PROG}-{REV}")
            with self.assertRaises(ValueError):
                JsonNumberSource(path).preview("LE")

    def test_example_file_previews_without_writing(self):
        path = example_config_path()
        with open(path, "rb") as handle:
            before = handle.read()
        stamp = os.path.getmtime(path)
        number = JsonNumberSource(path).preview("LE")
        self.assertEqual(number, "LE-01001-A")
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), before)
        self.assertEqual(os.path.getmtime(path), stamp)

    def test_interface(self):
        self.assertTrue(issubclass(JsonNumberSource, NumberSource))
        self.assertTrue(issubclass(OpsApiNumberSource, NumberSource))


class OpsSourceTests(unittest.TestCase):
    def test_allocate_is_not_implemented(self):
        source = open_number_source(
            {"source": "ops", "base_url": "https://ops.example/api", "token_env": "BW_OPS_TOKEN"}
        )
        self.assertIsInstance(source, OpsApiNumberSource)
        self.assertEqual(source.base_url, "https://ops.example/api")
        self.assertEqual(source.programs(), [])
        for method in (source.allocate, source.preview):
            with self.assertRaises(NotImplementedError) as caught:
                method("LE")
            self.assertIn("FCB-P2-03", str(caught.exception))
            self.assertIn("BW_OPS_TOKEN", str(caught.exception))

    def test_ops_requires_base_url(self):
        with self.assertRaises(ValueError):
            open_number_source({"source": "ops", "base_url": "  "})

    def test_unknown_kind(self):
        with self.assertRaises(ValueError):
            open_number_source({"source": "spreadsheet"})


class ResolveConfigTests(unittest.TestCase):
    def test_write_copies_example_once(self):
        import bruceworx.config_path as config_path

        with tempfile.TemporaryDirectory() as directory:
            example = os.path.join(directory, "numbering.example.json")
            local = os.path.join(directory, "numbering.json")
            _write(example)
            real_local = config_path.local_config_path
            real_example = config_path.example_config_path
            config_path.local_config_path = lambda: local
            config_path.example_config_path = lambda: example
            try:
                preview = resolve_config_path(None, write=False)
                self.assertEqual(preview, example)
                self.assertFalse(os.path.exists(local))
                created = resolve_config_path(None, write=True)
                self.assertEqual(created, local)
                self.assertTrue(os.path.isfile(local))
                again = resolve_config_path(None, write=False)
                self.assertEqual(again, local)
            finally:
                config_path.local_config_path = real_local
                config_path.example_config_path = real_example

    def test_missing_explicit_config(self):
        with self.assertRaises(FileNotFoundError):
            resolve_config_path("/no/such/numbering.json", write=False)


if __name__ == "__main__":
    unittest.main()
