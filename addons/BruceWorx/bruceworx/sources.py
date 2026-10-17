# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where the next part number comes from.

FCB-P2-04/05 read a local JSON file. FCB-P2-03 (BruceWorx Ops API) is not
implemented. Both sources implement :class:`NumberSource` so the macro, the
rename script and the CLI never branch on the transport.

Counters:

* ``next_parent`` is the next ``PPPPP`` for one program and document type.
* ``parents[<PPPPP>].next_sub`` is the next ``SSS`` under that parent.

Document type codes live in ``config/document_types.json`` (or an embedded
``document_types`` object). The shipped table is placeholder data for Bruce.

Ops source shape, accepted by :func:`open_number_source` and rejected until
FCB-P2-03 lands::

    {
      "source": "ops",
      "base_url": "https://ops.example/api",
      "token_env": "BW_OPS_TOKEN"
    }

Expected future HTTP contract (not called)::

    POST {base_url}/part-numbers
    {"program": "LE", "document_type": "01", "revision": "A", "parent": null}
    -> {"part_number": "LE-01-01001-001-A"}

    POST {base_url}/part-numbers
    {"program": "LE", "document_type": "01", "revision": "A", "parent": "01001"}
    -> {"part_number": "LE-01-01001-002-A"}

``parent`` null reserves the next parent drawing and its first sub-assembly.
A five-digit ``parent`` reserves only the next sub-assembly under that drawing.
Authentication will be a bearer token from ``token_env`` (default ``BW_OPS_TOKEN``).
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod

from bruceworx.numbering import (
    DEFAULT_NEXT_PARENT,
    DEFAULT_NEXT_SUB,
    PART_NUMBER_FORMAT,
    format_part_number,
    normalize_document_type,
    normalize_parent,
    normalize_program,
)


class NumberSource(ABC):
    """Reserve BruceWorx part numbers.

    Implementations must be safe for one caller at a time. The Ops API reader
    is the place for cross-process allocation.
    """

    @abstractmethod
    def allocate(
        self,
        program: str,
        document_type: str,
        revision: str | None = None,
        parent: str | None = None,
    ) -> str:
        """Reserve the next part number and return it.

        ``parent`` None takes the next parent drawing for ``program`` +
        ``document_type`` and issues sub-assembly 001. A parent drawing
        number takes the next sub-assembly under that parent and does not
        advance ``next_parent``.
        """

    @abstractmethod
    def preview(
        self,
        program: str,
        document_type: str,
        revision: str | None = None,
        parent: str | None = None,
    ) -> str:
        """Return the next part number without reserving it."""

    def programs(self) -> list[str]:
        """Program codes this source can issue. Empty if it cannot list them."""
        return []

    def document_types(self) -> list[str]:
        """Document type codes this source accepts. Empty if it cannot list them."""
        return []


class JsonNumberSource(NumberSource):
    """Local JSON counter. Single writer. Updates are replaced atomically."""

    def __init__(self, path: str | os.PathLike):
        self.path = os.fspath(path)

    def allocate(
        self,
        program: str,
        document_type: str,
        revision: str | None = None,
        parent: str | None = None,
    ) -> str:
        data = self._load()
        formatted, _parent_key, _sub = self._issue(
            data, program, document_type, revision, parent, write=True
        )
        self._save(data)
        return formatted

    def preview(
        self,
        program: str,
        document_type: str,
        revision: str | None = None,
        parent: str | None = None,
    ) -> str:
        data = self._load()
        formatted, _parent_key, _sub = self._issue(
            data, program, document_type, revision, parent, write=False
        )
        return formatted

    def programs(self) -> list[str]:
        return sorted(self._load()["programs"])

    def document_types(self) -> list[str]:
        return sorted(self._document_types(self._load()))

    def _issue(self, data, program, document_type, revision, parent, write: bool):
        entry, key = self._program(data, program)
        code = self._known_document_type(data, document_type)
        rev = revision if revision is not None else entry.get("revision")
        counters = entry.setdefault("counters", {})
        bucket = counters.setdefault(
            code, {"next_parent": DEFAULT_NEXT_PARENT, "parents": {}}
        )
        parents = bucket.setdefault("parents", {})
        if parent is None:
            parent_number = _as_int(bucket.get("next_parent"), f"{key}/{code} next_parent")
            parent_key = normalize_parent(parent_number)
            if parent_key in parents:
                raise ValueError(
                    f"parent {parent_key} already exists under {key}/{code}; "
                    "next_parent is behind the issued drawings"
                )
            slot = {"next_sub": DEFAULT_NEXT_SUB}
            sub_number = DEFAULT_NEXT_SUB
            if write:
                parents[parent_key] = slot
                bucket["next_parent"] = parent_number + 1
                slot["next_sub"] = sub_number + 1
        else:
            parent_key = normalize_parent(parent)
            slot = parents.get(parent_key)
            if slot is None:
                known = ", ".join(sorted(parents)) or "(none)"
                raise KeyError(
                    f"unknown parent {parent_key} for {key}/{code}; known: {known}"
                )
            sub_number = _as_int(slot.get("next_sub"), f"{key}/{code}/{parent_key} next_sub")
            if write:
                slot["next_sub"] = sub_number + 1
        formatted = format_part_number(key, code, parent_key, sub_number, rev)
        return formatted, parent_key, sub_number

    def _known_document_type(self, data, document_type: str) -> str:
        code = normalize_document_type(document_type)
        table = self._document_types(data)
        if code not in table:
            known = ", ".join(sorted(table))
            raise KeyError(f"unknown document type {document_type!r}; known: {known}")
        return code

    def _document_types(self, data: dict) -> dict:
        if "document_types" in data:
            return _coerce_document_types(data["document_types"])
        ref = data.get("document_types_file", "document_types.json")
        path = ref if os.path.isabs(ref) else os.path.join(os.path.dirname(self.path), ref)
        if not os.path.isfile(path):
            raise FileNotFoundError(f"document type table not found: {path}")
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
        return _coerce_document_types(raw)

    def _load(self) -> dict:
        with open(self.path, encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"{self.path} must contain a JSON object")
        kind = data.get("source", "json")
        if kind != "json":
            raise ValueError(
                f"{self.path} declares source {kind!r}. Pass that object to "
                "open_number_source() so the Ops API reader (FCB-P2-03) can handle it."
            )
        declared = data.get("format", PART_NUMBER_FORMAT)
        if declared != PART_NUMBER_FORMAT:
            raise ValueError(
                f"{self.path} format {declared!r} is not {PART_NUMBER_FORMAT!r}"
            )
        if "number_width" in data:
            raise ValueError(
                f"{self.path} uses removed key number_width; counters are "
                "next_parent per program+document type and next_sub per parent"
            )
        programs = data.get("programs")
        if not isinstance(programs, dict) or not programs:
            raise ValueError(f"{self.path} needs a non-empty programs object")
        return data

    def _program(self, data: dict, program: str) -> tuple[dict, str]:
        canonical = normalize_program(program)
        programs = data["programs"]
        key = None
        for name in programs:
            if str(name).upper() == canonical:
                key = name
                break
        if key is None:
            known = ", ".join(sorted(str(name) for name in programs))
            raise KeyError(f"unknown program {program!r}; known: {known}")
        entry = programs[key]
        if not isinstance(entry, dict):
            raise ValueError(f"program {key} must be an object")
        if "revision" not in entry:
            raise ValueError(f"program {key} needs revision")
        if key != canonical:
            programs[canonical] = entry
            del programs[key]
            key = canonical
        return entry, key

    def _save(self, data: dict) -> None:
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        os.replace(tmp, self.path)


class OpsApiNumberSource(NumberSource):
    """FCB-P2-03 placeholder. Constructing it is allowed; allocating is not.

    ``base_url`` and ``token_env`` are stored so a later reader can fill in
    :meth:`allocate` and :meth:`preview` without a CLI change. Nothing is
    fetched. The keyword arguments match the JSON source: ``document_type``
    selects the two-digit type, and ``parent`` None versus a five-digit
    parent selects a new drawing versus the next sub-assembly.
    """

    def __init__(self, base_url: str, token_env: str = "BW_OPS_TOKEN"):
        if not base_url or not str(base_url).strip():
            raise ValueError("ops source needs base_url")
        self.base_url = str(base_url).rstrip("/")
        self.token_env = token_env or "BW_OPS_TOKEN"

    def allocate(
        self,
        program: str,
        document_type: str,
        revision: str | None = None,
        parent: str | None = None,
    ) -> str:
        raise self._not_ready(program, document_type, parent)

    def preview(
        self,
        program: str,
        document_type: str,
        revision: str | None = None,
        parent: str | None = None,
    ) -> str:
        raise self._not_ready(program, document_type, parent)

    def _not_ready(self, program: str, document_type: str, parent: str | None):
        return NotImplementedError(
            "BruceWorx Ops API reader is not implemented (FCB-P2-03). "
            f"Configured base_url={self.base_url!r}, token_env={self.token_env!r}. "
            f"Request would be program={program!r}, document_type={document_type!r}, "
            f"parent={parent!r}. Use a local JSON numbering file (source 'json') until then."
        )


def open_number_source(spec) -> NumberSource:
    """Build a source from a JSON path or a spec dict.

    A path (or a dict with ``source`` omitted or ``json``) returns
    :class:`JsonNumberSource`. ``{"source": "ops", "base_url": ...}`` returns
    :class:`OpsApiNumberSource`.
    """
    if isinstance(spec, dict):
        kind = spec.get("source", "json")
        if kind == "json":
            path = spec.get("path")
            if not path:
                raise ValueError("json source spec needs path")
            return JsonNumberSource(path)
        if kind == "ops":
            return OpsApiNumberSource(
                base_url=spec.get("base_url", ""),
                token_env=spec.get("token_env", "BW_OPS_TOKEN"),
            )
        raise ValueError(f"unknown numbering source {kind!r}")
    if isinstance(spec, (str, os.PathLike)):
        return JsonNumberSource(spec)
    raise TypeError(f"numbering spec must be a path or dict, got {type(spec).__name__}")


def _coerce_document_types(raw) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("document type table must be a JSON object")
    table = raw["types"] if isinstance(raw.get("types"), dict) else raw
    cleaned = {}
    for key, entry in table.items():
        if key in {"note", "placeholder", "source", "types"}:
            continue
        code = normalize_document_type(key)
        if not isinstance(entry, dict):
            raise ValueError(f"document type {code} must be an object")
        cleaned[code] = entry
    if not cleaned:
        raise ValueError("document type table is empty")
    return cleaned


def _as_int(value, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer, got {value!r}")
    if value < 0:
        raise ValueError(f"{label} must be >= 0, got {value!r}")
    return value
