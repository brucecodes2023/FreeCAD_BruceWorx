# SPDX-License-Identifier: LGPL-2.1-or-later
"""Folder vault (BW-PDM-01). The PDM-02 contract tests run unchanged against a
folder, then the folder-specific rules: ref file, write-once objects,
append-only journal, replay after reopening, and sync-service duplicates."""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_pdm  # noqa: E402
from bruceworx.pdm import IN_REVIEW, RELEASED, WIP, LifecycleError  # noqa: E402
from bruceworx.pdm_folder import FolderVault, VaultFormatError, find_ref_file  # noqa: E402

PART = test_pdm.PART
ASSY = test_pdm.ASSY


class _TempDir:
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bw-vault-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        super().setUp()


def _folder_vault_factory(case):
    counter = [0]

    def make():
        counter[0] += 1
        return FolderVault.init(os.path.join(case.tmp, f"v{counter[0]}"), "Contract", actor="tester@mac")

    return make


def _contract(cls):
    """Re-run a test_pdm case with every Vault() replaced by a folder vault."""

    class Folder(_TempDir, cls):
        def setUp(self):
            self.tmp = tempfile.mkdtemp(prefix="bw-vault-")
            self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
            original = test_pdm.Vault
            test_pdm.Vault = _folder_vault_factory(self)
            self.addCleanup(setattr, test_pdm, "Vault", original)
            cls.setUp(self)

    Folder.__name__ = f"Folder{cls.__name__}"
    Folder.__qualname__ = Folder.__name__
    return Folder


FolderLifecycleTests = _contract(test_pdm.LifecycleTests)
FolderDrawingTests = _contract(test_pdm.DrawingTests)
FolderBomTests = _contract(test_pdm.BomTests)


class ReplayTests(_TempDir, unittest.TestCase):
    """Reopening the folder rebuilds exactly the same state."""

    def test_reopen_rebuilds_state(self):
        vault = FolderVault.init(self.tmp, "Pedestal", actor="bruce@mac")
        vault.create_item(PART, "part", "Base plate")
        vault.create_item(ASSY, "assembly")
        vault.set_bom(ASSY, [(PART, 4)])
        vault.submit(PART)
        vault.reject(PART, "edge distance")
        vault.submit(PART)
        vault.approve(PART)
        again = FolderVault(self.tmp, actor="bruce@mac")
        self.assertEqual(again.status()["items"], vault.status()["items"])
        self.assertEqual(again.bom[ASSY], [(PART, 4)])
        self.assertEqual(again.items[PART].released.code, "A")
        self.assertEqual(again.problems, [])

    def test_refused_operation_writes_nothing(self):
        vault = FolderVault.init(self.tmp, "Pedestal", actor="bruce@mac")
        vault.create_item(PART)
        size = os.path.getsize(vault.journal_path)
        with self.assertRaises(LifecycleError):
            vault.approve(PART)  # not in review
        self.assertEqual(os.path.getsize(vault.journal_path), size)
        self.assertEqual(FolderVault(self.tmp, actor="bruce@mac").items[PART].latest.state, WIP)


class RefFileTests(_TempDir, unittest.TestCase):
    def test_open_by_ref_file_or_folder(self):
        vault = FolderVault.init(self.tmp, "Lift Eng", actor="bruce@mac")
        self.assertTrue(vault.ref_path.endswith("Lift-Eng.bwvault"))
        self.assertEqual(find_ref_file(self.tmp), vault.ref_path)
        self.assertEqual(FolderVault(vault.ref_path).ref["vault_id"], vault.ref["vault_id"])

    def test_refuses_foreign_or_newer_files(self):
        with open(os.path.join(self.tmp, "x.bwvault"), "w", encoding="utf-8") as handle:
            json.dump({"format": "something-else"}, handle)
        with self.assertRaises(VaultFormatError):
            FolderVault(self.tmp)
        other = os.path.join(self.tmp, "newer")
        os.makedirs(other)
        with open(os.path.join(other, "n.bwvault"), "w", encoding="utf-8") as handle:
            json.dump({"format": "bruceworx.vault", "version": 99}, handle)
        with self.assertRaises(VaultFormatError):
            FolderVault(other)

    def test_init_twice_refused(self):
        FolderVault.init(self.tmp, "A")
        with self.assertRaises(VaultFormatError):
            FolderVault.init(self.tmp, "B")


class FileTests(_TempDir, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.vault = FolderVault.init(os.path.join(self.tmp, "vault"), "Pedestal", actor="bruce@mac")
        self.vault.create_item(PART, "part", "Base plate")
        self.work = os.path.join(self.tmp, "work")
        os.makedirs(self.work)

    def _save(self, text):
        path = os.path.join(self.work, "base-plate.FCStd")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_checkin_needs_checkout(self):
        with self.assertRaises(LifecycleError):
            self.vault.checkin(PART, self._save("v1"))

    def test_versions_are_write_once_objects(self):
        self.vault.checkout(PART)
        v1 = self.vault.checkin(PART, self._save("v1"), "first")
        self.vault.checkout(PART)
        v2 = self.vault.checkin(PART, self._save("v2"), "second")
        self.assertNotEqual(v1.sha256, v2.sha256)
        objects = [os.path.join(self.vault.root, v.object_name) for v in (v1, v2)]
        self.assertTrue(all(os.path.isfile(p) for p in objects))
        stamps = [os.stat(p).st_mtime_ns for p in objects]
        self.vault.checkout(PART)
        self.vault.checkin(PART, self._save("v3"))
        self.assertEqual([os.stat(p).st_mtime_ns for p in objects], stamps)  # never rewritten
        self.assertEqual(len(self.vault.versions[PART]), 3)
        self.assertIsNone(self.vault.locks.get(PART))
        leftovers = [n for _d, _s, files in os.walk(self.vault.root) for n in files if n.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_unchanged_checkin_only_unlocks(self):
        self.vault.checkout(PART)
        v1 = self.vault.checkin(PART, self._save("v1"))
        self.vault.checkout(PART)
        same = self.vault.checkin(PART, self._save("v1"))
        self.assertEqual(same.sha256, v1.sha256)
        self.assertEqual(len(self.vault.versions[PART]), 1)
        self.assertIsNone(self.vault.locks.get(PART))

    def test_checkout_copies_latest_to_workspace(self):
        self.vault.checkout(PART)
        self.vault.checkin(PART, self._save("v1"))
        other = os.path.join(self.tmp, "elsewhere")
        path = self.vault.checkout(PART, workspace=other)
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "v1")

    def test_released_revision_freezes_its_file(self):
        self.vault.checkout(PART)
        v1 = self.vault.checkin(PART, self._save("v1"))
        self.vault.submit(PART)
        with self.assertRaises(LifecycleError):
            self.vault.checkout(PART)  # in review: read-only
        self.vault.approve(PART)
        self.assertEqual(self.vault.released_version(PART).sha256, v1.sha256)
        reopened = FolderVault(self.vault.root, actor="bruce@mac")
        self.assertEqual(reopened.released_version(PART).sha256, v1.sha256)
        self.assertEqual(reopened.items[PART].latest.state, RELEASED)

    def test_damaged_object_is_detected(self):
        self.vault.checkout(PART)
        v1 = self.vault.checkin(PART, self._save("v1"))
        with open(os.path.join(self.vault.root, v1.object_name), "w", encoding="utf-8") as handle:
            handle.write("tampered")
        with self.assertRaises(LifecycleError):
            self.vault.fetch(PART, self.work)


class SyncServiceTests(_TempDir, unittest.TestCase):
    """What iCloud, Dropbox and friends can do to the folder."""

    def setUp(self):
        super().setUp()
        self.vault = FolderVault.init(self.tmp, "Pedestal", actor="bruce@mac")
        self.vault.create_item(PART)
        self.vault.submit(PART)

    def test_duplicate_journal_copies_neither_lose_nor_double(self):
        journal = self.vault.journal_path
        folder = os.path.dirname(journal)
        # iCloud keeps the older server copy as "name 2", Dropbox and
        # Syncthing use their own names. The newer copy holds an extra event.
        shutil.copyfile(journal, os.path.join(folder, "bruce@mac 2.jsonl"))
        shutil.copyfile(journal, os.path.join(folder, "bruce@mac (conflicted copy 2026-10-19).jsonl"))
        self.vault.approve(PART)
        shutil.copyfile(journal, os.path.join(folder, "bruce@mac.sync-conflict-20261019-101500-ABCDEF.jsonl"))
        with open(journal, "w", encoding="utf-8"):
            pass  # worst case: the main file was replaced by an empty one
        again = FolderVault(self.tmp, actor="bruce@mac")
        self.assertEqual(again.items[PART].released.code, "A")
        self.assertEqual(again.problems, [])
        # Writing continues without reusing an event number.
        again.raise_ecr("ECR-0001", "thicker", [PART])
        self.assertEqual(len(FolderVault(self.tmp).ecrs), 1)

    def test_half_synced_line_is_ignored(self):
        with open(self.vault.journal_path, "a", encoding="utf-8") as handle:
            handle.write('{"id": "partial", "actor": "bruce@mac", "se')
        again = FolderVault(self.tmp, actor="bruce@mac")
        self.assertEqual(again.items[PART].latest.state, IN_REVIEW)
        self.assertEqual(again.problems, [])

    def test_journal_before_object_is_reported(self):
        work = os.path.join(self.tmp, "..", os.path.basename(self.tmp) + "-work")
        os.makedirs(work, exist_ok=True)
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        vault = FolderVault.init(os.path.join(self.tmp, "v2"), "Second", actor="bruce@mac")
        vault.create_item(PART)
        vault.checkout(PART)
        path = os.path.join(work, "p.FCStd")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("v1")
        version = vault.checkin(PART, path)
        os.remove(os.path.join(vault.root, version.object_name))  # not downloaded yet
        again = FolderVault(vault.root, actor="bruce@mac")
        self.assertEqual(again.missing_objects(), [version.object_name])
        with self.assertRaises(FileNotFoundError):
            again.fetch(PART, work)

    def test_ref_file_duplicate_is_harmless(self):
        shutil.copyfile(self.vault.ref_path, self.vault.ref_path.replace(".bwvault", " 2.bwvault"))
        self.assertEqual(FolderVault(self.tmp).ref["vault_id"], self.vault.ref["vault_id"])


class CliTests(_TempDir, unittest.TestCase):
    def _run(self, *argv):
        import contextlib
        import io

        from bruceworx.cli import main

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["vault", *argv, "--vault", self.vault_dir, "--actor", "bruce@mac"])
        line = [ln for ln in out.getvalue().splitlines() if ln.startswith("BW_RESULT ")][-1]
        return code, json.loads(line[len("BW_RESULT "):])

    def test_drive_the_vault_from_the_command_line(self):
        self.vault_dir = os.path.join(self.tmp, "Pedestal")
        code, result = self._run("init")
        self.assertEqual(code, 0)
        self.assertTrue(result["ref"].endswith("Pedestal.bwvault"))
        self._run("create", "--pn", PART, "--description", "Base plate")
        self._run("checkout", "--pn", PART)
        model = os.path.join(self.tmp, "plate.FCStd")
        with open(model, "w", encoding="utf-8") as handle:
            handle.write("v1")
        code, result = self._run("checkin", "--pn", PART, "--file", model, "--comment", "first")
        self.assertEqual((code, len(result["sha256"])), (0, 64))
        self._run("submit", "--pn", PART)
        code, result = self._run("approve", "--pn", PART)
        self.assertEqual((result["revision"], result["state"]), ("A", RELEASED))
        code, status = self._run("status")
        row = status["items"][0]
        self.assertEqual((row["display"], row["versions"], row["file"]), (PART + "-A", 1, "plate.FCStd"))


if __name__ == "__main__":
    unittest.main()
