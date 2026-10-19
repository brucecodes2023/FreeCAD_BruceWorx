# SPDX-License-Identifier: LGPL-2.1-or-later
"""Folder-backed PDM vault (BW-PDM-01 choice, 19 Oct 2026).

Any folder works: local disk, iCloud Drive, Dropbox, OneDrive, a NAS share.
The vault never relies on the sync service for anything but copying files,
and it is laid out so a sync service has nothing to conflict over::

    <folder>/
      <name>.bwvault            ref file: identifies the vault; written once
      objects/<ab>/<sha256>.<ext>   file versions; written once, never changed
      journal/<actor>.jsonl     append-only event log, one writer per file

The ref file is what a reader opens (FreeCAD, the CLI, later Ops) to view
and drive the vault. All state is rebuilt by replaying the journal through
:class:`bruceworx.pdm.Vault`, so the lifecycle rules are exactly the
reference model's.

Scope: one writer at a time (one FreeCAD instance). Several journals are
read and merged in timestamp order so a second device can be added later,
but simultaneous edits from two instances are not reconciled.

Sync-service hazards handled here:

* Duplicate copies (iCloud ``x 2.jsonl``, Dropbox ``x (conflicted copy)``,
  Syncthing ``x.sync-conflict-...``): every ``*.jsonl`` in ``journal/`` is
  read and events are de-duplicated by id, so a copy never loses or doubles
  an event.
* A half-synced last line is ignored until the rest arrives.
* Objects are written under a ``.tmp`` name (iCloud does not sync those)
  and renamed when complete; reads verify the SHA-256.
* A journal entry can arrive before its object: :meth:`FolderVault.missing_objects`
  lists them and :meth:`FolderVault.fetch` says so instead of failing oddly.
"""

from __future__ import annotations

import datetime as _dt
import getpass
import hashlib
import json
import os
import re
import shutil
import socket
import uuid
from dataclasses import dataclass, field

from bruceworx import pdm
from bruceworx.pdm import WIP, LifecycleError

FORMAT = "bruceworx.vault"
FORMAT_VERSION = 1
REF_SUFFIX = ".bwvault"
OBJECTS = "objects"
JOURNAL = "journal"
_ACTOR_SAFE = re.compile(r"[^A-Za-z0-9._@-]+")

# Lifecycle operations replayed through pdm.Vault, with their argument names.
LIFECYCLE_OPS = {
    "create_item": ("part_number", "item_type", "description", "drawing_of"),
    "submit": ("part_number",),
    "reject": ("part_number", "reason"),
    "approve": ("part_number",),
    "retire": ("part_number",),
    "raise_ecr": ("number", "problem", "items"),
    "decide_ecr": ("number", "approved"),
    "open_eco": ("number", "ecr_numbers"),
    "release_eco": ("number",),
    "set_bom": ("parent", "lines"),
}
FILE_OPS = ("checkout", "undo_checkout", "checkin")


class VaultFormatError(ValueError):
    """The folder or ref file is not a BruceWorx vault this code can read."""


@dataclass
class FileVersion:
    sha256: str
    size: int
    filename: str
    revision: str
    actor: str
    at: str
    comment: str = ""

    @property
    def object_name(self) -> str:
        return object_name(self.sha256, self.filename)


@dataclass
class Event:
    id: str
    actor: str
    seq: int
    at: str
    op: str
    args: dict = field(default_factory=dict)

    def sort_key(self):
        return (self.at, self.actor, self.seq)

    def to_json(self) -> str:
        return json.dumps(
            {"id": self.id, "actor": self.actor, "seq": self.seq, "at": self.at,
             "op": self.op, "args": self.args},
            sort_keys=True, separators=(",", ":"),
        )


def object_name(sha256: str, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return os.path.join(OBJECTS, sha256[:2], sha256 + ext)


def sha256_of(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def default_actor() -> str:
    """``user@host``; ``BW_PDM_ACTOR`` overrides."""
    actor = os.environ.get("BW_PDM_ACTOR") or f"{getpass.getuser()}@{socket.gethostname().split('.')[0]}"
    return _ACTOR_SAFE.sub("-", actor)


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="microseconds")


def find_ref_file(path: str) -> str:
    """Accept the ref file itself or the vault folder."""
    path = os.path.abspath(path)
    if os.path.isfile(path):
        return path
    if not os.path.isdir(path):
        raise FileNotFoundError(path)
    refs = sorted(n for n in os.listdir(path) if n.endswith(REF_SUFFIX))
    if not refs:
        raise VaultFormatError(f"{path} has no {REF_SUFFIX} file")
    # A sync service may have duplicated the ref file; all copies are identical.
    return os.path.join(path, refs[0])


class FolderVault:
    """A :class:`pdm.Vault` whose every change is an event in a folder."""

    def __init__(self, ref_path: str, actor: str | None = None):
        self.ref_path = find_ref_file(ref_path)
        self.root = os.path.dirname(self.ref_path)
        with open(self.ref_path, encoding="utf-8") as handle:
            try:
                self.ref = json.load(handle)
            except json.JSONDecodeError as exc:
                raise VaultFormatError(f"{self.ref_path}: {exc}") from exc
        if self.ref.get("format") != FORMAT:
            raise VaultFormatError(f"{self.ref_path} is not a {FORMAT} file")
        if int(self.ref.get("version", 0)) > FORMAT_VERSION:
            raise VaultFormatError(
                f"{self.ref_path} is format {self.ref['version']}; this BruceWorx reads up to {FORMAT_VERSION}"
            )
        self.actor = _ACTOR_SAFE.sub("-", actor) if actor else default_actor()
        self.journal_path = os.path.join(self.root, JOURNAL, f"{self.actor}.jsonl")
        self.refresh()

    # ----- creation -----------------------------------------------------

    @classmethod
    def init(cls, folder: str, name: str, actor: str | None = None) -> "FolderVault":
        folder = os.path.abspath(folder)
        os.makedirs(folder, exist_ok=True)
        if any(n.endswith(REF_SUFFIX) for n in os.listdir(folder)):
            raise VaultFormatError(f"{folder} already holds a vault")
        safe = _ACTOR_SAFE.sub("-", name).strip("-") or "vault"
        ref = {
            "format": FORMAT,
            "version": FORMAT_VERSION,
            "vault_id": str(uuid.uuid4()),
            "name": name,
            "created": _now(),
            "layout": {"objects": OBJECTS, "journal": JOURNAL},
        }
        for sub in (OBJECTS, JOURNAL):
            os.makedirs(os.path.join(folder, sub), exist_ok=True)
        ref_path = os.path.join(folder, safe + REF_SUFFIX)
        _write_once(ref_path, (json.dumps(ref, indent=2) + "\n").encode("utf-8"))
        return cls(ref_path, actor=actor)

    # ----- replay ---------------------------------------------------------

    def refresh(self):
        """Rebuild all state from the journal (after a sync, or on open)."""
        self.model = pdm.Vault()
        self.versions: dict[str, list[FileVersion]] = {}
        self.locks: dict[str, str] = {}
        self.released_files: dict[tuple[str, str], str] = {}
        self.problems: list[str] = []
        self._seen: set[str] = set()
        self._seq = 0
        for event in self._read_events():
            self._seen.add(event.id)
            if event.actor == self.actor:
                self._seq = max(self._seq, event.seq)
            try:
                self._apply(event)
            except (LifecycleError, ValueError, KeyError) as exc:
                self.problems.append(f"{event.at} {event.actor} {event.op}: {exc}")

    def _read_events(self) -> list[Event]:
        folder = os.path.join(self.root, JOURNAL)
        events: dict[str, Event] = {}
        if not os.path.isdir(folder):
            return []
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".jsonl"):
                continue
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                text = handle.read()
            lines = text.split("\n")
            if not text.endswith("\n"):
                lines = lines[:-1]  # last line still syncing
            for line in lines:
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                    event = Event(raw["id"], raw["actor"], int(raw["seq"]), raw["at"], raw["op"], raw.get("args", {}))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    self.problems.append(f"{name}: unreadable journal line skipped")
                    continue
                events.setdefault(event.id, event)
        return sorted(events.values(), key=Event.sort_key)

    def _apply(self, event: Event):
        args = event.args
        if event.op in LIFECYCLE_OPS:
            if event.op == "set_bom":
                args = dict(args, lines=[(child, int(qty)) for child, qty in args["lines"]])
            result = getattr(self.model, event.op)(**args)
            if event.op == "approve":
                self._freeze(args["part_number"])
            elif event.op == "release_eco":
                for pn in self.model.ecos[args["number"]].items:
                    self._freeze(pn)
            return result
        pn = args.get("part_number")
        if event.op == "checkout":
            self._require_wip(pn, "check out")
            holder = self.locks.get(pn)
            if holder and holder != event.actor:
                raise LifecycleError(f"{pn} is checked out by {holder}")
            self.locks[pn] = event.actor
        elif event.op == "undo_checkout":
            if self.locks.get(pn) not in (None, event.actor) and not args.get("force"):
                raise LifecycleError(f"{pn} is checked out by {self.locks[pn]}")
            self.locks.pop(pn, None)
        elif event.op == "checkin":
            self._require_wip(pn, "check in")
            if self.locks.get(pn) != event.actor:
                raise LifecycleError(f"{pn} is not checked out by {event.actor}")
            version = FileVersion(
                args["sha256"], int(args["size"]), args["filename"],
                self.model.items[pn].latest.code, event.actor, event.at, args.get("comment", ""),
            )
            self.versions.setdefault(pn, []).append(version)
            if not args.get("keep_lock"):
                self.locks.pop(pn, None)
            return version
        else:
            raise ValueError(f"unknown operation {event.op!r}")
        return None

    def _freeze(self, pn):
        item = self.model.items[pn]
        versions = self.versions.get(pn)
        if versions:
            self.released_files[(pn, item.released.code)] = versions[-1].sha256

    def _require_wip(self, pn, action):
        rev = self.model.items[pn].latest
        if rev.state != WIP:
            raise LifecycleError(f"cannot {action} {pn} rev {rev.code}: it is {rev.state}, not {WIP}")

    # ----- recording --------------------------------------------------------

    def _record(self, op: str, args: dict):
        """Validate by applying to the in-memory state, then append the event.
        A refused operation writes nothing."""
        self._seq += 1
        event = Event(str(uuid.uuid4()), self.actor, self._seq, _now(), op, _jsonable(args))
        try:
            result = self._apply(event)
        except Exception:
            self._seq -= 1
            raise
        os.makedirs(os.path.dirname(self.journal_path), exist_ok=True)
        with open(self.journal_path, "a", encoding="utf-8") as handle:
            handle.write(event.to_json() + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._seen.add(event.id)
        return result

    # pdm.Vault surface: same names and arguments, so the contract tests run
    # unchanged against a folder.
    @property
    def items(self):
        return self.model.items

    @property
    def ecrs(self):
        return self.model.ecrs

    @property
    def ecos(self):
        return self.model.ecos

    @property
    def bom(self):
        return self.model.bom

    def create_item(self, part_number, item_type="part", description="", drawing_of=None):
        return self._record("create_item", dict(part_number=part_number, item_type=item_type,
                                                description=description, drawing_of=drawing_of))

    def submit(self, part_number):
        return self._record("submit", dict(part_number=part_number))

    def reject(self, part_number, reason=""):
        return self._record("reject", dict(part_number=part_number, reason=reason))

    def approve(self, part_number):
        return self._record("approve", dict(part_number=part_number))

    def retire(self, part_number):
        return self._record("retire", dict(part_number=part_number))

    def raise_ecr(self, number, problem, items):
        return self._record("raise_ecr", dict(number=number, problem=problem, items=list(items)))

    def decide_ecr(self, number, approved):
        return self._record("decide_ecr", dict(number=number, approved=bool(approved)))

    def open_eco(self, number, ecr_numbers):
        return self._record("open_eco", dict(number=number, ecr_numbers=list(ecr_numbers)))

    def release_eco(self, number):
        return self._record("release_eco", dict(number=number))

    def set_bom(self, parent, lines):
        return self._record("set_bom", dict(parent=parent, lines=[[c, int(q)] for c, q in lines]))

    def drawings_of(self, part_number):
        return self.model.drawings_of(part_number)

    def explode(self, top):
        return self.model.explode(top)

    def flattened(self, top):
        return self.model.flattened(top)

    def where_used(self, part_number, released_only=False):
        return self.model.where_used(part_number, released_only=released_only)

    # ----- files ------------------------------------------------------------

    def checkout(self, part_number, workspace: str | None = None) -> str | None:
        """Take the lock. With ``workspace``, also copy the latest version
        there and return its path (the place FreeCAD edits and saves)."""
        self._record("checkout", dict(part_number=part_number))
        if workspace and self.versions.get(part_number):
            return self.fetch(part_number, workspace)
        return None

    def undo_checkout(self, part_number, force=False):
        return self._record("undo_checkout", dict(part_number=part_number, force=bool(force)))

    def checkin(self, part_number, path: str, comment: str = "", keep_lock: bool = False):
        """Store ``path`` as a new version. Unchanged content only releases the lock."""
        if self.locks.get(part_number) != self.actor:
            raise LifecycleError(f"{part_number} is not checked out by {self.actor}")
        digest = sha256_of(path)
        current = self.latest_version(part_number)
        if current is not None and current.sha256 == digest:
            if not keep_lock:
                self.undo_checkout(part_number)
            return current
        filename = os.path.basename(path)
        target = os.path.join(self.root, object_name(digest, filename))
        if not os.path.exists(target):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(path, "rb") as handle:
                _write_once(target, handle.read())
        return self._record("checkin", dict(part_number=part_number, sha256=digest,
                                            size=os.path.getsize(path), filename=filename,
                                            comment=comment, keep_lock=bool(keep_lock)))

    def latest_version(self, part_number) -> FileVersion | None:
        versions = self.versions.get(part_number)
        return versions[-1] if versions else None

    def released_version(self, part_number) -> FileVersion | None:
        item = self.model.items[part_number]
        if item.released is None:
            return None
        sha = self.released_files.get((part_number, item.released.code))
        return next((v for v in self.versions.get(part_number, []) if v.sha256 == sha), None)

    def fetch(self, part_number, dest_dir: str, version: FileVersion | None = None) -> str:
        """Copy a version (default: latest) out of the vault, verifying it."""
        version = version or self.latest_version(part_number)
        if version is None:
            raise LifecycleError(f"{part_number} has no file versions")
        source = os.path.join(self.root, version.object_name)
        if not os.path.exists(source):
            raise FileNotFoundError(
                f"{part_number} version {version.sha256[:12]} has not synced to this device yet ({source})"
            )
        if sha256_of(source) != version.sha256:
            raise LifecycleError(f"{source} does not match its SHA-256; the copy is damaged or incomplete")
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, version.filename)
        shutil.copyfile(source, dest)
        return dest

    def missing_objects(self) -> list[str]:
        missing = []
        for versions in self.versions.values():
            for version in versions:
                if not os.path.exists(os.path.join(self.root, version.object_name)):
                    missing.append(version.object_name)
        return missing

    # ----- reading ------------------------------------------------------------

    def status(self) -> dict:
        """Everything a reader shows, as JSON-ready data."""
        rows = []
        for pn, item in sorted(self.model.items.items()):
            rev = item.latest
            latest = self.latest_version(pn)
            rows.append({
                "part_number": pn,
                "type": item.item_type,
                "description": item.description,
                "revision": rev.code,
                "state": rev.state,
                "released": item.released.code if item.released else None,
                "display": pdm.display_part_number(pn, rev.code),
                "checked_out_by": self.locks.get(pn),
                "file": latest.filename if latest else None,
                "sha256": latest.sha256 if latest else None,
                "versions": len(self.versions.get(pn, [])),
            })
        return {
            "vault": self.ref.get("name"),
            "vault_id": self.ref.get("vault_id"),
            "root": self.root,
            "actor": self.actor,
            "items": rows,
            "missing_objects": self.missing_objects(),
            "problems": list(self.problems),
        }


def _write_once(path: str, data: bytes) -> None:
    """Write under a ``.tmp`` name (not synced by iCloud), then rename."""
    tmp = f"{path}.{uuid.uuid4().hex[:8]}.tmp"
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def _jsonable(args: dict) -> dict:
    return json.loads(json.dumps(args))
