# SPDX-License-Identifier: LGPL-2.1-or-later
"""Locate the local numbering JSON without touching the committed example."""

from __future__ import annotations

import os
import shutil

PACKAGE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
EXAMPLE_NAME = "numbering.example.json"
LOCAL_NAME = "numbering.json"


def config_dir() -> str:
    return os.path.join(PACKAGE_ROOT, "config")


def example_config_path() -> str:
    return os.path.join(config_dir(), EXAMPLE_NAME)


def local_config_path() -> str:
    return os.path.join(config_dir(), LOCAL_NAME)


def resolve_config_path(explicit: str | None, *, write: bool) -> str:
    """Return the numbering file to read or update.

    ``explicit`` is ``--config``. Otherwise use ``config/numbering.json`` when
    it already exists. Allocating (``write=True``) copies the example into
    that local file on first use. Preview reads the example until a local
    counter exists, so a dry run does not create a file.
    """
    if explicit:
        path = os.path.abspath(explicit)
        if not os.path.isfile(path):
            raise FileNotFoundError(path)
        return path
    local = local_config_path()
    if os.path.isfile(local):
        return local
    example = example_config_path()
    if not os.path.isfile(example):
        raise FileNotFoundError(example)
    if not write:
        return example
    os.makedirs(os.path.dirname(local), exist_ok=True)
    shutil.copyfile(example, local)
    return local
