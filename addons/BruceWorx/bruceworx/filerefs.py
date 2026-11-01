# SPDX-License-Identifier: LGPL-2.1-or-later
"""External references between .FCStd files (BW-ASM-01). No FreeCAD needed.

An assembly that links a part in another file stores the link in its
``Document.xml`` as::

    <XLink file="parts/LE-01-01001-002.FCStd" stamp="..." name="Part"/>

``file`` is written relative to the folder of the file that holds the link
(``PropertyXLink::Save``), so a folder moved as a whole keeps working. Links
break when one file moves without the others, when a file is renamed, or
when a link was made before its owner was saved and kept an absolute path.

This module reads those tags straight out of the zip, so it runs under plain
Python as well as FreeCADCmd:

* :func:`walk` follows links from one file and reports every file it
  reaches, links that point nowhere, and absolute links.
* :func:`resolve` repairs broken links by looking for the file under search
  folders, and turns absolute links into relative ones.
* :func:`pack_and_go` copies a file and everything it links into a new
  folder, keeping relative positions so the copy opens with no fixing.

Only ``Document.xml`` is rewritten. Every other zip member is copied byte
for byte, and the rewrite goes to a temporary file that replaces the
original only once it is complete.
"""

from __future__ import annotations

import html
import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field

SCHEMA = "bruceworx.file-references.v1"
DOCUMENT_XML = "Document.xml"
_XLINK_RE = re.compile(r"<XLink\b[^>]*>")
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
_OBJECT_RE = re.compile(r'<Object\b[^>]*\bname="([^"]*)"')


@dataclass
class Reference:
    """One external link, as stored in ``owner``."""

    owner: str  # absolute path of the file that holds the link
    file: str  # the path as stored (usually relative to owner's folder)
    object: str  # linked object Name inside that file

    @property
    def absolute(self) -> bool:
        return os.path.isabs(self.file)

    @property
    def path(self) -> str:
        """Where the link points, as an absolute path."""
        if self.absolute:
            return os.path.normpath(self.file)
        return os.path.normpath(os.path.join(os.path.dirname(self.owner), self.file))

    @property
    def exists(self) -> bool:
        return os.path.isfile(self.path)

    def as_json(self) -> dict:
        return {
            "owner": self.owner,
            "file": self.file,
            "object": self.object,
            "path": self.path,
            "absolute": self.absolute,
            "exists": self.exists,
        }


@dataclass
class Graph:
    """Files reachable from ``root`` through external links."""

    root: str
    files: list[str] = field(default_factory=list)  # root first, each once
    references: list[Reference] = field(default_factory=list)
    unreadable: dict[str, str] = field(default_factory=dict)  # path -> error

    @property
    def missing(self) -> list[Reference]:
        return [ref for ref in self.references if not ref.exists]

    @property
    def absolute(self) -> list[Reference]:
        return [ref for ref in self.references if ref.absolute]

    @property
    def ok(self) -> bool:
        return not self.missing and not self.unreadable

    def as_json(self) -> dict:
        return {
            "schema": SCHEMA,
            "root": self.root,
            "ok": self.ok,
            "files": list(self.files),
            "references": [ref.as_json() for ref in self.references],
            "missing": [ref.as_json() for ref in self.missing],
            "absolute": [ref.as_json() for ref in self.absolute],
            "unreadable": dict(self.unreadable),
        }


# ----- reading ----------------------------------------------------------------


def read_document_xml(path: str) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read(DOCUMENT_XML).decode("utf-8")


def parse_references(xml: str, owner: str) -> list[Reference]:
    """Every ``<XLink file=...>`` in ``xml``. Links without ``file`` are
    links inside the same document and are skipped."""
    owner = os.path.abspath(owner)
    refs = []
    for tag in _XLINK_RE.findall(xml):
        attrs = {key: html.unescape(value) for key, value in _ATTR_RE.findall(tag)}
        if "file" not in attrs or not attrs["file"]:
            continue
        refs.append(Reference(owner, attrs["file"], attrs.get("name", "")))
    return refs


def read_references(path: str) -> list[Reference]:
    """External links stored in one .FCStd file, in file order, duplicates
    kept (each tag is one link property)."""
    path = os.path.abspath(path)
    return parse_references(read_document_xml(path), path)


def object_names(path: str) -> set[str]:
    """Object Names in a .FCStd file (used to confirm a candidate file)."""
    return set(_OBJECT_RE.findall(read_document_xml(path)))


def walk(root: str) -> Graph:
    """Follow external links from ``root``, breadth first. A file reached
    twice (a part used by two sub-assemblies) is listed once; a link cycle
    stops at the file already seen."""
    root = os.path.abspath(root)
    graph = Graph(root)
    seen = {_key(root)}
    queue = [root]
    while queue:
        current = queue.pop(0)
        graph.files.append(current)
        try:
            refs = read_references(current)
        except (OSError, KeyError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
            graph.unreadable[current] = f"{type(exc).__name__}: {exc}"
            continue
        graph.references.extend(refs)
        for ref in refs:
            target = ref.path
            if ref.exists and _key(target) not in seen:
                seen.add(_key(target))
                queue.append(target)
    return graph


# ----- rewriting --------------------------------------------------------------


def encode_attribute(text: str) -> str:
    """Same escapes as ``Base::Persistence::encodeAttribute``."""
    out = []
    for char in text:
        out.append(
            {
                "<": "&lt;",
                '"': "&quot;",
                "'": "&apos;",
                "&": "&amp;",
                ">": "&gt;",
                "\r": "&#13;",
                "\n": "&#10;",
                "\t": "&#9;",
            }.get(char, char)
        )
    return "".join(out)


def relink_xml(xml: str, mapping: dict[str, str]) -> tuple[str, int]:
    """Replace stored ``file`` values found in ``mapping``. Returns the new
    text and how many tags changed."""
    changed = 0

    def tag(match):
        nonlocal changed
        text = match.group(0)

        def attr(m):
            nonlocal changed
            if m.group(1) != "file":
                return m.group(0)
            old = html.unescape(m.group(2))
            if old not in mapping or mapping[old] == old:
                return m.group(0)
            changed += 1
            return f'file="{encode_attribute(mapping[old])}"'

        return _ATTR_RE.sub(attr, text)

    return _XLINK_RE.sub(tag, xml), changed


def rewrite_references(path: str, mapping: dict[str, str]) -> int:
    """Rewrite link paths in one file. ``mapping`` is stored value -> new
    stored value. Returns the number of links changed; 0 leaves the file
    untouched."""
    path = os.path.abspath(path)
    xml = read_document_xml(path)
    new_xml, changed = relink_xml(xml, mapping)
    if not changed:
        return 0
    directory = os.path.dirname(path)
    handle, temp = tempfile.mkstemp(prefix=".bw-relink-", suffix=".FCStd", dir=directory)
    os.close(handle)
    try:
        with zipfile.ZipFile(path) as source, zipfile.ZipFile(temp, "w") as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == DOCUMENT_XML:
                    data = new_xml.encode("utf-8")
                target.writestr(info, data, compress_type=info.compress_type)
        shutil.copystat(path, temp)
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.remove(temp)
        raise
    return changed


def relative_link(owner: str, target: str) -> str:
    """Link text for ``target`` as FreeCAD writes it: relative to owner's
    folder, forward slashes."""
    rel = os.path.relpath(os.path.abspath(target), os.path.dirname(os.path.abspath(owner)))
    return rel.replace(os.sep, "/")


# ----- resolver ---------------------------------------------------------------


def find_candidates(ref: Reference, search_dirs: list[str]) -> list[str]:
    """Files under ``search_dirs`` with the link's file name. When the link
    names an object, files that do not contain it are dropped."""
    name = os.path.basename(ref.file.replace("\\", "/"))
    found = []
    seen = set()
    for directory in search_dirs:
        for dirpath, dirnames, filenames in os.walk(os.path.abspath(directory)):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            if name in filenames:
                candidate = os.path.join(dirpath, name)
                if _key(candidate) not in seen:
                    seen.add(_key(candidate))
                    found.append(candidate)
    if ref.object and len(found) > 1:
        holding = []
        for candidate in found:
            try:
                if ref.object in object_names(candidate):
                    holding.append(candidate)
            except (OSError, KeyError, zipfile.BadZipFile):
                continue
        if holding:
            found = holding
    return found


def resolve(
    root: str,
    search_dirs: list[str] | None = None,
    *,
    apply: bool = True,
    make_relative: bool = True,
) -> dict:
    """Repair the links reachable from ``root``.

    A missing file is looked for by name under ``search_dirs`` (default: the
    root's folder). One match is relinked; several matches are reported as
    ambiguous and left alone, never guessed. ``make_relative`` also rewrites
    working absolute links as relative ones. ``apply=False`` reports what
    would change and writes nothing.

    Files are walked again after each repair, so a part that only becomes
    reachable once its sub-assembly is fixed is checked too.
    """
    root = os.path.abspath(root)
    search_dirs = [os.path.abspath(d) for d in (search_dirs or [os.path.dirname(root)])]
    fixed, ambiguous, unresolved, relativised = [], [], [], []
    handled = set()
    for _round in range(64):  # bounded: each round fixes at least one link or stops
        graph = walk(root)
        plan: dict[str, dict[str, str]] = {}
        for ref in graph.references:
            marker = (_key(ref.owner), ref.file)
            if marker in handled:
                continue
            if not ref.exists:
                handled.add(marker)
                candidates = find_candidates(ref, search_dirs)
                entry = ref.as_json()
                if len(candidates) == 1:
                    new = relative_link(ref.owner, candidates[0])
                    plan.setdefault(ref.owner, {})[ref.file] = new
                    entry.update(new_file=new, new_path=candidates[0])
                    fixed.append(entry)
                elif candidates:
                    entry["candidates"] = candidates
                    ambiguous.append(entry)
                else:
                    unresolved.append(entry)
            elif ref.absolute and make_relative:
                handled.add(marker)
                new = relative_link(ref.owner, ref.path)
                plan.setdefault(ref.owner, {})[ref.file] = new
                entry = ref.as_json()
                entry["new_file"] = new
                relativised.append(entry)
        if not plan or not apply:
            break
        for owner, mapping in plan.items():
            rewrite_references(owner, mapping)
    final = walk(root)
    return {
        "schema": SCHEMA,
        "root": root,
        "applied": apply,
        "fixed": fixed,
        "relativised": relativised,
        "ambiguous": ambiguous,
        "unresolved": unresolved,
        "ok": final.ok if apply else not (ambiguous or unresolved),
    }


# ----- pack and go ------------------------------------------------------------


def pack_and_go(root: str, destination: str, *, overwrite: bool = False) -> dict:
    """Copy ``root`` and every file it links into ``destination``.

    Files keep their positions relative to the deepest folder that holds
    them all, so relative links need no change. Absolute links are rewritten
    in the copies to point at the copied file. The originals are not
    touched. Refuses to start when a link is broken (run :func:`resolve`
    first) or when ``destination`` already has files, unless ``overwrite``.
    """
    root = os.path.abspath(root)
    destination = os.path.abspath(destination)
    graph = walk(root)
    if not graph.ok:
        broken = [f"{r.owner}: {r.file}" for r in graph.missing] + list(graph.unreadable)
        raise RuntimeError("broken references, run resolve-refs first: " + "; ".join(broken))
    base = os.path.commonpath([os.path.dirname(f) for f in graph.files])
    if os.path.isdir(destination) and os.listdir(destination) and not overwrite:
        raise FileExistsError(f"{destination} is not empty (pass overwrite to reuse it)")
    copies = {}
    for source in graph.files:
        target = os.path.join(destination, os.path.relpath(source, base))
        if _key(target) == _key(source):
            raise ValueError(f"pack and go would overwrite its own source {source}")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(source, target)
        copies[_key(source)] = target
    rewritten = 0
    for source in graph.files:
        mapping = {}
        for ref in read_references(source):
            if ref.absolute:
                mapping[ref.file] = relative_link(copies[_key(source)], copies[_key(ref.path)])
        if mapping:
            rewritten += rewrite_references(copies[_key(source)], mapping)
    new_root = copies[_key(root)]
    check = walk(new_root)
    escaped = [f for f in check.files if not _inside(f, destination)]
    return {
        "schema": SCHEMA,
        "root": root,
        "output": new_root,
        "destination": destination,
        "files": [copies[_key(f)] for f in graph.files],
        "rewritten": rewritten,
        "ok": check.ok and not escaped,
        "outside_destination": escaped,
    }


def _inside(path: str, folder: str) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(folder)]) == os.path.abspath(folder)
    except ValueError:  # different drives
        return False


def _key(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))
