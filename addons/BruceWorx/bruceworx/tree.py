# SPDX-License-Identifier: LGPL-2.1-or-later
"""Document tree as JSON. Works on FreeCAD documents and on test doubles."""

from __future__ import annotations

SCHEMA = "bruceworx.document-tree.v1"


def document_tree(doc) -> dict:
    """Return the document tree.

    Roots are objects that are not in another object's ``OutList``. Cycles are
    reported on the back-edge and not walked again.
    """
    objects = list(getattr(doc, "Objects", []) or [])
    child_names = set()
    for obj in objects:
        for child in getattr(obj, "OutList", None) or []:
            name = getattr(child, "Name", None)
            # A self-OutList entry is a cycle, not a reason to drop the root.
            if name and name != obj.Name:
                child_names.add(name)
    roots = [obj for obj in objects if obj.Name not in child_names]
    tree = [_node(obj, set()) for obj in roots]
    return {
        "schema": SCHEMA,
        "document": {
            "name": getattr(doc, "Name", ""),
            "label": getattr(doc, "Label", ""),
            "file": getattr(doc, "FileName", "") or "",
        },
        "tree": tree,
    }


def _node(obj, stack: set[str]) -> dict:
    name = obj.Name
    if name in stack:
        return {
            "name": name,
            "label": getattr(obj, "Label", name),
            "typeid": getattr(obj, "TypeId", ""),
            "children": [],
            "cycle": True,
        }
    stack.add(name)
    children = []
    for child in getattr(obj, "OutList", None) or []:
        children.append(_node(child, stack))
    stack.remove(name)
    return {
        "name": name,
        "label": getattr(obj, "Label", name),
        "typeid": getattr(obj, "TypeId", ""),
        "children": children,
    }
