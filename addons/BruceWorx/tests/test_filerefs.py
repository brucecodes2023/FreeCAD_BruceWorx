# SPDX-License-Identifier: LGPL-2.1-or-later
"""External references, resolver and pack and go (BW-ASM-01), on hand-made
.FCStd zips. tests/freecad_filemodel.py repeats the round trip with real
FreeCAD documents."""

import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bruceworx import filerefs  # noqa: E402


def write_fcstd(path, objects=("Part",), links=(), extra=b"brep-bytes"):
    """A minimal .FCStd: Document.xml with Objects and one App::Link per
    ``(file, name)`` in ``links``, plus a binary member that must survive a
    rewrite untouched."""
    lines = ['<?xml version="1.0" encoding="utf-8"?>', '<Document SchemaVersion="4">', "<Objects>"]
    for name in objects:
        lines.append(f'<Object type="App::Part" name="{name}"/>')
    for i, _link in enumerate(links):
        lines.append(f'<Object type="App::Link" name="Link{i:03d}"/>')
    lines.append("</Objects>")
    lines.append("<ObjectData>")
    for i, (file, name) in enumerate(links):
        lines.append(f'<Object name="Link{i:03d}"><Properties><Property name="LinkedObject" type="App::PropertyXLink">')
        lines.append(f'<XLink file="{filerefs.encode_attribute(file)}" stamp="2026-11-01T00:00:00Z" name="{name}"/>')
        lines.append("</Property></Properties></Object>")
    lines.append("</ObjectData></Document>")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(filerefs.DOCUMENT_XML, "\n".join(lines))
        archive.writestr("PartShape.brp", extra, compress_type=zipfile.ZIP_STORED)


def read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


class FileRefsBase(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="bw-refs-"))
        self.addCleanup(shutil.rmtree, self.tmp)

    def p(self, *parts):
        return os.path.join(self.tmp, *parts)

    def jet(self):
        """jet/VL-JET.FCStd -> wing (sub-assembly) -> spar; fuselage; bolt
        used twice from the shared library beside the project folder."""
        write_fcstd(self.p("lib", "BOLT.FCStd"))
        write_fcstd(self.p("jet", "parts", "SPAR.FCStd"))
        write_fcstd(self.p("jet", "parts", "FUSELAGE.FCStd"))
        write_fcstd(
            self.p("jet", "WING.FCStd"),
            objects=("Assembly",),
            links=[("parts/SPAR.FCStd", "Part"), ("../lib/BOLT.FCStd", "Part")],
        )
        write_fcstd(
            self.p("jet", "VL-JET.FCStd"),
            objects=("Assembly",),
            links=[
                ("WING.FCStd", "Assembly"),
                ("parts/FUSELAGE.FCStd", "Part"),
                ("../lib/BOLT.FCStd", "Part"),
            ],
        )
        return self.p("jet", "VL-JET.FCStd")


class ReadTests(FileRefsBase):
    def test_walk_lists_every_file_once(self):
        graph = filerefs.walk(self.jet())
        names = [os.path.relpath(f, self.tmp) for f in graph.files]
        self.assertEqual(names[0], os.path.join("jet", "VL-JET.FCStd"))
        self.assertEqual(
            sorted(names),
            sorted(
                [
                    os.path.join("jet", "VL-JET.FCStd"),
                    os.path.join("jet", "WING.FCStd"),
                    os.path.join("jet", "parts", "FUSELAGE.FCStd"),
                    os.path.join("jet", "parts", "SPAR.FCStd"),
                    os.path.join("lib", "BOLT.FCStd"),
                ]
            ),
        )
        self.assertEqual(len(graph.references), 5)  # the bolt link counts twice
        self.assertTrue(graph.ok)
        self.assertEqual(graph.as_json()["schema"], filerefs.SCHEMA)

    def test_links_inside_one_document_are_ignored(self):
        xml = '<XLink name="Body"/><XLink file="" name="X"/><XLink file="a.FCStd" stamp="" name="P"/>'
        refs = filerefs.parse_references(xml, self.p("owner.FCStd"))
        self.assertEqual([r.file for r in refs], ["a.FCStd"])

    def test_escaped_paths_round_trip(self):
        odd = "parts/A & B 'quoted'.FCStd"
        write_fcstd(self.p("parts", "A & B 'quoted'.FCStd"))
        write_fcstd(self.p("asm.FCStd"), links=[(odd, "Part")])
        (ref,) = filerefs.read_references(self.p("asm.FCStd"))
        self.assertEqual(ref.file, odd)
        self.assertTrue(ref.exists)

    def test_cycle_terminates(self):
        write_fcstd(self.p("a.FCStd"), links=[("b.FCStd", "Part")])
        write_fcstd(self.p("b.FCStd"), links=[("a.FCStd", "Part")])
        graph = filerefs.walk(self.p("a.FCStd"))
        self.assertEqual(len(graph.files), 2)

    def test_unreadable_file_is_reported(self):
        write_fcstd(self.p("asm.FCStd"), links=[("bad.FCStd", "Part")])
        with open(self.p("bad.FCStd"), "wb") as handle:
            handle.write(b"not a zip")
        graph = filerefs.walk(self.p("asm.FCStd"))
        self.assertFalse(graph.ok)
        self.assertIn(self.p("bad.FCStd"), graph.unreadable)


class MovedFolderTests(FileRefsBase):
    def test_moved_folder_keeps_links(self):
        """The ASM-01 acceptance test, file side: move the whole tree."""
        self.jet()
        shutil.move(self.p("jet"), self.p("moved", "jet"))
        shutil.move(self.p("lib"), self.p("moved", "lib"))
        graph = filerefs.walk(self.p("moved", "jet", "VL-JET.FCStd"))
        self.assertTrue(graph.ok, graph.as_json()["missing"])
        self.assertEqual(len(graph.files), 5)

    def test_moving_only_the_project_breaks_the_library_link(self):
        self.jet()
        shutil.move(self.p("jet"), self.p("moved", "jet"))
        graph = filerefs.walk(self.p("moved", "jet", "VL-JET.FCStd"))
        self.assertEqual({os.path.basename(r.file) for r in graph.missing}, {"BOLT.FCStd"})
        self.assertEqual(len(graph.missing), 2)  # from the top and from the wing


class ResolveTests(FileRefsBase):
    def test_resolver_finds_moved_file_and_relinks_relative(self):
        root = self.jet()
        shutil.move(self.p("lib"), self.p("shared", "hardware"))
        before = read_bytes(self.p("jet", "parts", "SPAR.FCStd"))
        report = filerefs.resolve(root, [self.tmp])
        self.assertTrue(report["ok"], report)
        self.assertEqual(len(report["fixed"]), 2)
        self.assertEqual(report["ambiguous"], [])
        files = {r.file for r in filerefs.read_references(root)}
        self.assertIn("../shared/hardware/BOLT.FCStd", files)
        # Files without broken links are not rewritten.
        self.assertEqual(read_bytes(self.p("jet", "parts", "SPAR.FCStd")), before)

    def test_rewrite_keeps_other_members_byte_for_byte(self):
        root = self.jet()
        shutil.move(self.p("lib"), self.p("shared"))
        filerefs.resolve(root, [self.tmp])
        with zipfile.ZipFile(root) as archive:
            self.assertEqual(archive.read("PartShape.brp"), b"brep-bytes")
            self.assertEqual(archive.getinfo("PartShape.brp").compress_type, zipfile.ZIP_STORED)
        self.assertEqual([n for n in os.listdir(self.p("jet")) if n.startswith(".bw-relink")], [])

    def test_dry_run_writes_nothing(self):
        root = self.jet()
        shutil.move(self.p("lib"), self.p("shared"))
        before = read_bytes(root)
        report = filerefs.resolve(root, [self.tmp], apply=False)
        self.assertFalse(report["applied"])
        self.assertTrue(report["fixed"])
        self.assertEqual(read_bytes(root), before)

    def test_two_candidates_is_ambiguous_not_guessed(self):
        root = self.jet()
        shutil.move(self.p("lib"), self.p("a"))
        write_fcstd(self.p("b", "BOLT.FCStd"))
        report = filerefs.resolve(root, [self.tmp])
        self.assertFalse(report["ok"])
        self.assertEqual(report["fixed"], [])
        self.assertEqual(len(report["ambiguous"][0]["candidates"]), 2)

    def test_object_name_breaks_a_tie(self):
        root = self.jet()
        shutil.move(self.p("lib"), self.p("a"))
        write_fcstd(self.p("b", "BOLT.FCStd"), objects=("Body",))  # no "Part" in it
        report = filerefs.resolve(root, [self.tmp])
        self.assertTrue(report["ok"], report)
        self.assertTrue(report["fixed"][0]["new_path"].startswith(self.p("a")))

    def test_unresolved_is_reported(self):
        root = self.jet()
        shutil.rmtree(self.p("lib"))
        report = filerefs.resolve(root, [self.tmp])
        self.assertFalse(report["ok"])
        self.assertEqual(len(report["unresolved"]), 2)

    def test_absolute_link_made_relative(self):
        write_fcstd(self.p("parts", "P.FCStd"))
        write_fcstd(self.p("asm.FCStd"), links=[(self.p("parts", "P.FCStd"), "Part")])
        report = filerefs.resolve(self.p("asm.FCStd"))
        self.assertEqual(len(report["relativised"]), 1)
        (ref,) = filerefs.read_references(self.p("asm.FCStd"))
        self.assertEqual(ref.file, "parts/P.FCStd")

    def test_sub_assembly_fixed_then_its_children_checked(self):
        """The wing is missing and so is the spar it links: one call fixes both."""
        root = self.jet()
        os.makedirs(self.p("elsewhere"))
        shutil.move(self.p("jet", "WING.FCStd"), self.p("elsewhere", "WING.FCStd"))
        report = filerefs.resolve(root, [self.tmp])
        self.assertTrue(report["ok"], report)
        self.assertEqual({os.path.basename(f["file"]) for f in report["fixed"]}, {"WING.FCStd", "SPAR.FCStd"})
        # ../lib/BOLT.FCStd still points at the bolt from elsewhere/.


class PackAndGoTests(FileRefsBase):
    def test_pack_copies_closure_and_opens_clean(self):
        root = self.jet()
        report = filerefs.pack_and_go(root, self.p("out"))
        self.assertTrue(report["ok"], report)
        self.assertEqual(len(report["files"]), 5)
        self.assertTrue(os.path.isfile(self.p("out", "lib", "BOLT.FCStd")))
        self.assertEqual(report["output"], self.p("out", "jet", "VL-JET.FCStd"))
        # The copy works after the source is gone.
        shutil.rmtree(self.p("jet"))
        shutil.rmtree(self.p("lib"))
        self.assertTrue(filerefs.walk(report["output"]).ok)

    def test_pack_rewrites_absolute_links_in_the_copy_only(self):
        write_fcstd(self.p("src", "parts", "P.FCStd"))
        write_fcstd(self.p("src", "asm.FCStd"), links=[(self.p("src", "parts", "P.FCStd"), "Part")])
        report = filerefs.pack_and_go(self.p("src", "asm.FCStd"), self.p("out"))
        self.assertEqual(report["rewritten"], 1)
        (copy_ref,) = filerefs.read_references(report["output"])
        self.assertEqual(copy_ref.file, "parts/P.FCStd")
        (orig_ref,) = filerefs.read_references(self.p("src", "asm.FCStd"))
        self.assertTrue(orig_ref.absolute)

    def test_pack_refuses_broken_and_non_empty(self):
        root = self.jet()
        os.makedirs(self.p("busy"))
        with open(self.p("busy", "x"), "w"):
            pass
        with self.assertRaises(FileExistsError):
            filerefs.pack_and_go(root, self.p("busy"))
        shutil.rmtree(self.p("lib"))
        with self.assertRaises(RuntimeError):
            filerefs.pack_and_go(root, self.p("out"))


if __name__ == "__main__":
    unittest.main()
