# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where the next part number comes from.

FCB-P2-04/05 read a local JSON file. FCB-P2-03 (BruceWorx Ops API) is not
implemented. Both sources implement :class:`NumberSource` so the macro, the
rename script and the CLI never branch on the transport.

JSON file shape::

    {
      "source": "json",
      "format": "{PROG}-{NNNNN}-{REV}",
      "number_width": 5,
      "programs": {
        "LE": {"revision": "A", "next": 1001, "description": "optional"}
      }
    }

Ops source shape, accepted by :func:`open_number_source` and rejected until
FCB-P2-03 lands::

    {
      "source": "ops",
      "base_url": "https://ops.example/api",
      "token_env": "BW_OPS_TOKEN"
    }

Expected future HTTP contract (not called)::

    POST {base_url}/part-numbers
    {"program": "LE", "revision": "A"}
    -> {"part_number": "LE-01001-A"}

Authentication will be a bearer token from the environment variable named by
``token_env`` (default ``BW_OPS_TOKEN``).
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod

from bruceworx.numbering import (
    NUMBER_WIDTH,
    PART_NUMBER_FORMAT,
    format_part_number,
    normalize_program,
)


class NumberSource(ABC):
    """Reserve BruceWorx part numbers.

    Implementations must be safe for one caller at a time. The Ops API reader
    is the place for cross-process allocation.
    """

    @abstractmethod
    def allocate(self, program: str, revision: str | None = None) -> str:
        """Reserve the next part number and return it."""

    @abstractmethod
    def preview(self, program: str, revision: str | None = None) -> str:
        """Return the next part number without reserving it."""

    def programs(self) -> list[str]:
        """Program codes this source can issue. Empty if it cannot list them."""
        return []


class JsonNumberSource(NumberSource):
    """Local JSON counter. Single writer. Updates are replaced atomically."""

    def __init__(self, path: str | os.PathLike):
        self.path = os.fspath(path)

    def allocate(self, program: str, revision: str | None = None) -> str:
        data = self._load()
        entry, key = self._entry(data, program)
        number = _as_sequence(entry.get("next"), key)
        rev = revision if revision is not None else entry.get("revision")
        formatted = format_part_number(key, number, rev)
        entry["next"] = number + 1
        self._save(data)
        return formatted

    def preview(self, program: str, revision: str | None = None) -> str:
        data = self._load()
        entry, key = self._entry(data, program)
        number = _as_sequence(entry.get("next"), key)
        rev = revision if revision is not None else entry.get("revision")
        return format_part_number(key, number, rev)

    def programs(self) -> list[str]:
        data = self._load()
        return sorted(data["programs"])

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
        width = data.get("number_width", NUMBER_WIDTH)
        if width != NUMBER_WIDTH:
            raise ValueError(
                f"{self.path} number_width must be {NUMBER_WIDTH} to match NNNNN"
            )
        programs = data.get("programs")
        if not isinstance(programs, dict) or not programs:
            raise ValueError(f"{self.path} needs a non-empty programs object")
        return data

    def _entry(self, data: dict, program: str) -> tuple[dict, str]:
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
        if "revision" not in entry or "next" not in entry:
            raise ValueError(f"program {key} needs revision and next")
        # Store the canonical code so a lowercase key cannot be emitted.
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
    fetched.
    """

    def __init__(self, base_url: str, token_env: str = "BW_OPS_TOKEN"):
        if not base_url or not str(base_url).strip():
            raise ValueError("ops source needs base_url")
        self.base_url = str(base_url).rstrip("/")
        self.token_env = token_env or "BW_OPS_TOKEN"

    def allocate(self, program: str, revision: str | None = None) -> str:
        raise self._not_ready()

    def preview(self, program: str, revision: str | None = None) -> str:
        raise self._not_ready()

    def _not_ready(self) -> NotImplementedError:
        return NotImplementedError(
            "BruceWorx Ops API reader is not implemented (FCB-P2-03). "
            f"Configured base_url={self.base_url!r}, token_env={self.token_env!r}. "
            "Use a local JSON numbering file (source 'json') until then."
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


def _as_sequence(value, program: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"program {program} next must be an integer, got {value!r}")
    return value
