# SPDX-License-Identifier: LGPL-2.1-or-later
"""JSON numbering source and the Ops API placeholder."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bruceworx.config_path import example_config_path, resolve_config_path  # noqa: E402
from bruceworx.numbering import PART_NUMBER_FORMAT  # noqa: E402
from bruceworx.sources import (  # noqa: E402
    JsonNumberSource,
    NumberSource,
    OpsApiNumberSource,
    open_number_source,
)

EXAMPLE = "LE-01-01001-001-A"


def _types():
    return {
        "01": {"placeholder": True, "name": "PLACEHOLDER"},
        "02": {"placeholder": True, "name": "PLACEHOLDER"},
    }


def _programs():
    return {
        "LE": {
            "description": "example",
            "revision": "A",
            "counters": {"01": {"next_parent": 1001, "parents": {}}},
        }
    }


def _write(path, programs=None, **extra):
    payload = {
        "source": "json",
        "format": PART_NUMBER_FORMAT,
        "document_types": _types(),
        "programs": programs or _programs(),
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
            self.assertEqual(source.preview("LE", "01"), EXAMPLE)
            self.assertEqual(source.preview("le", "1"), EXAMPLE)
            self.assertEqual(source.allocate("LE", "01"), EXAMPLE)
            self.assertEqual(source.preview("LE", "01"), "LE-01-01002-001-A")
            self.assertEqual(source.preview("LE", "01", parent="01001"), "LE-01-01001-002-A")
            with open(path, encoding="utf-8") as handle:
                saved = json.load(handle)
            bucket = saved["programs"]["LE"]["counters"]["01"]
            self.assertEqual(bucket["next_parent"], 1002)
            self.assertEqual(bucket["parents"]["01001"]["next_sub"], 2)
            self.assertFalse(os.path.exists(path + ".tmp"))

    def test_sub_counter_is_per_parent_and_parent_counter_is_per_type(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "numbering.json")
            _write(path)
            source = JsonNumberSource(path)
            self.assertEqual(source.allocate("LE", "01"), "LE-01-01001-001-A")
            self.assertEqual(source.allocate("LE", "01", parent="1001"), "LE-01-01001-002-A")
            self.assertEqual(source.allocate("LE", "01"), "LE-01-01002-001-A")
            self.assertEqual(source.allocate("LE", "02"), "LE-02-01001-001-A")
            with open(path, encoding="utf-8") as handle:
                saved = json.load(handle)
            counters = saved["programs"]["LE"]["counters"]
            self.assertEqual(counters["01"]["next_parent"], 1003)
            self.assertEqual(counters["01"]["parents"]["01001"]["next_sub"], 3)
            self.assertEqual(counters["01"]["parents"]["01002"]["next_sub"], 2)
            self.assertEqual(counters["02"]["next_parent"], 1002)
            self.assertEqual(counters["02"]["parents"]["01001"]["next_sub"], 2)

    def test_revision_override_does_not_change_stored_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "numbering.json")
            _write(path)
            source = JsonNumberSource(path)
            issued = source.allocate("LE", "01", revision="C")
            self.assertEqual(issued, "LE-01-01001-001-C")
            with open(path, encoding="utf-8") as handle:
                saved = json.load(handle)
            self.assertEqual(saved["programs"]["LE"]["revision"], "A")

    def test_unknown_program_type_and_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "numbering.json")
            _write(path)
            source = JsonNumberSource(path)
            with self.assertRaises(KeyError):
                source.allocate("NOPE", "01")
            with self.assertRaises(KeyError):
                source.allocate("LE", "99")
            source.allocate("LE", "01")
            with self.assertRaises(KeyError):
                source.allocate("LE", "01", parent="01002")

    def test_rejects_non_json_source_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "numbering.json")
            _write(path, source="ops")
            with self.assertRaises(ValueError) as caught:
                JsonNumberSource(path).preview("LE", "01")
            self.assertIn("FCB-P2-03", str(caught.exception))

    def test_rejects_old_format(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "numbering.json")
            _write(path, number_width=5)
            with self.assertRaises(ValueError):
                JsonNumberSource(path).preview("LE", "01")
            _write(path, format="{PROG}-{NNNNN}-{REV}")
            with self.assertRaises(ValueError):
                JsonNumberSource(path).preview("LE", "01")

    def test_example_file_previews_without_writing(self):
        path = example_config_path()
        types_path = os.path.join(os.path.dirname(path), "document_types.json")
        with open(path, "rb") as handle:
            before = handle.read()
        with open(types_path, "rb") as handle:
            types_before = handle.read()
        stamp = os.path.getmtime(path)
        number = JsonNumberSource(path).preview("LE", "01")
        self.assertEqual(number, EXAMPLE)
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), before)
        with open(types_path, "rb") as handle:
            self.assertEqual(handle.read(), types_before)
        self.assertEqual(os.path.getmtime(path), stamp)

    def test_shipped_document_types_are_placeholders(self):
        path = os.path.join(
            os.path.dirname(example_config_path()),
            "document_types.json",
        )
        with open(path, encoding="utf-8") as handle:
            table = json.load(handle)
        self.assertTrue(table["placeholder"])
        self.assertIn("PLACEHOLDER", table["note"])
        self.assertEqual(set(table["types"]), {"01", "02"})
        for entry in table["types"].values():
            self.assertTrue(entry["placeholder"])
            self.assertIn("PLACEHOLDER", entry["name"])

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
        self.assertEqual(source.document_types(), [])
        for method in (source.allocate, source.preview):
            with self.assertRaises(NotImplementedError) as caught:
                method("LE", "01", parent="01001")
            self.assertIn("FCB-P2-03", str(caught.exception))
            self.assertIn("BW_OPS_TOKEN", str(caught.exception))
            self.assertIn("01", str(caught.exception))
            self.assertIn("01001", str(caught.exception))

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
