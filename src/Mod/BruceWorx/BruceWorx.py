# SPDX-License-Identifier: LGPL-2.1-or-later
"""BruceWorx floating model tree (FCB-P1F-06/07).

Uses FreeCAD's existing overlay dock parameters and one QSS file. No
OverlayManager or DockWindowManager edits.

BruceWorx turns this on when FloatingModelTree is missing. While it is on,
the model dock is listed on OverlayLeft with AutoHide, Transparent, Width,
and the offset parameters. The first apply snapshots the previous overlay
parameters. Turning the preference off writes that snapshot back, and the
overlay reload puts those docks back where they were.

Spike gap (FCB-P1F-11, not done here): the left overlay is pinned to the
edge. OverlayTabWidget::setRect moves a left panel to x=0, so Offset3 (the
left inset preference) is stored and not applied. A free-floating panel,
not attached to an edge, needs a small OverlayManager change. Height of a
side panel is also computed to fill the viewport minus the top offset and
bottom inset; a free height is the same later change.
"""

import json
import os

PREFS_PATH = "User parameter:BaseApp/Preferences/BruceWorx"
OVERLAY_PATH = "User parameter:BaseApp/MainWindow/DockWindows"
STYLE_PATH = "User parameter:BaseApp/Preferences/MainWindow"
DOCK_PREFS_PATH = "User parameter:BaseApp/Preferences/DockWindows"

SIDES = ("OverlayLeft", "OverlayRight", "OverlayTop", "OverlayBottom")
STYLE_KEY = "OverlayActiveStyleSheet"
SNAPSHOT_KEY = "OverlaySnapshot"
APPLIED_KEY = "FloatingModelTreeApplied"

DEFAULT_WIDTH = 280
DEFAULT_TOP_OFFSET = 8
DEFAULT_BOTTOM_INSET = 8
DEFAULT_LEFT_INSET = 0
MIN_WIDTH = 120

# Keys we rewrite on OverlayLeft. Sizes is cleared while the feature is on
# so a previous splitter layout is not applied to the model tree alone.
LEFT_KEYS = (
    ("Widgets", "str"),
    ("Sizes", "str"),
    ("Width", "int"),
    ("Offset1", "int"),
    ("Offset2", "int"),
    ("Offset3", "int"),
    ("AutoHide", "bool"),
    ("EditHide", "bool"),
    ("EditShow", "bool"),
    ("TaskShow", "bool"),
    ("Transparent", "bool"),
)
WIDGET_KEYS = (("Widgets", "str"),)

_KIND_BUCKET = {"str": "String", "int": "Integer", "bool": "Boolean"}
_busy = False
_scheduled = False
_installed = False
_observer = None


def parse_widgets(text):
    if not text:
        return []
    return [part for part in str(text).split(",") if part]


def format_widgets(names):
    names = list(names)
    if not names:
        return ""
    return ",".join(names) + ","


def tree_dock_names(dock_prefs):
    """Object names of the model-tree docks that are enabled.

    Combined mode (the default) is the "Model" dock. Independent mode is
    "Tree view". Both are included when both preferences are on.
    """
    names = []
    if dock_prefs.GetGroup("ComboView").GetBool("Enabled", True):
        names.append("Model")
    if dock_prefs.GetGroup("TreeView").GetBool("Enabled", False):
        names.append("Tree view")
    return names or ["Model"]


def _contents(group):
    found = {"String": {}, "Integer": {}, "Boolean": {}}
    raw = group.GetContents()
    if not raw:
        return found
    for kind, name, value in raw:
        if kind in found:
            found[kind][name] = value
    return found


def _capture(group, keys):
    found = _contents(group)
    captured = {}
    for name, kind in keys:
        bucket = found[_KIND_BUCKET[kind]]
        if name in bucket:
            captured[name] = {"kind": kind, "present": True, "value": bucket[name]}
        else:
            captured[name] = {"kind": kind, "present": False}
    return captured


def _has_string(group, name):
    return name in _contents(group)["String"]


def _write(group, name, kind, value):
    if kind == "str":
        group.SetString(name, "" if value is None else str(value))
    elif kind == "int":
        group.SetInt(name, int(value))
    elif kind == "bool":
        group.SetBool(name, 1 if value else 0)
    else:
        raise ValueError(kind)


def _remove(group, name, kind):
    if kind == "str":
        group.RemString(name)
    elif kind == "int":
        group.RemInt(name)
    elif kind == "bool":
        group.RemBool(name)
    else:
        raise ValueError(kind)


def _restore_keys(group, captured):
    for name, item in captured.items():
        if item.get("present"):
            _write(group, name, item["kind"], item.get("value"))
        else:
            _remove(group, name, item["kind"])


def _stored_widgets(group):
    found = _contents(group)["String"]
    if "Widgets" not in found:
        return None
    return found["Widgets"]


def _strip_names(text, drop):
    drop = set(drop)
    return format_widgets(name for name in parse_widgets(text) if name not in drop)


def _read_int(prefs, name, default):
    return int(prefs.GetInt(name, default))


def _snapshot_state(overlay_root, style_group):
    sides = {}
    for side in SIDES:
        keys = LEFT_KEYS if side == "OverlayLeft" else WIDGET_KEYS
        sides[side] = _capture(overlay_root.GetGroup(side), keys)
    style = _capture(style_group, ((STYLE_KEY, "str"),))
    return {"style": style, "sides": sides}


def _apply_tree(prefs, overlay_root, style_group, qss_path, tree_names):
    width = max(MIN_WIDTH, _read_int(prefs, "FloatingModelTreeWidth", DEFAULT_WIDTH))
    top = _read_int(prefs, "FloatingModelTreeTopOffset", DEFAULT_TOP_OFFSET)
    bottom = _read_int(prefs, "FloatingModelTreeBottomInset", DEFAULT_BOTTOM_INSET)
    left = _read_int(prefs, "FloatingModelTreeLeftInset", DEFAULT_LEFT_INSET)
    auto_hide = bool(prefs.GetBool("FloatingModelTreeAutoHide", True))
    transparent = bool(prefs.GetBool("FloatingModelTreeTransparent", True))

    for side in SIDES:
        if side == "OverlayLeft":
            continue
        group = overlay_root.GetGroup(side)
        stored = _stored_widgets(group)
        if stored is None:
            continue
        stripped = _strip_names(stored, tree_names)
        if stripped != stored:
            group.SetString("Widgets", stripped)

    left_group = overlay_root.GetGroup("OverlayLeft")
    left_group.SetString("Widgets", format_widgets(tree_names))
    left_group.RemString("Sizes")
    left_group.SetInt("Width", width)
    left_group.SetInt("Offset1", top)
    left_group.SetInt("Offset2", bottom)
    left_group.SetInt("Offset3", left)
    left_group.SetBool("AutoHide", 1 if auto_hide else 0)
    left_group.SetBool("EditHide", 0)
    left_group.SetBool("EditShow", 0)
    left_group.SetBool("TaskShow", 0)
    left_group.SetBool("Transparent", 1 if transparent else 0)

    if qss_path:
        style_group.SetString(STYLE_KEY, qss_path)


def _restore_state(overlay_root, style_group, snapshot):
    for side, captured in snapshot.get("sides", {}).items():
        _restore_keys(overlay_root.GetGroup(side), captured)
    if "style" in snapshot:
        _restore_keys(style_group, snapshot["style"])


def sync(prefs, overlay_root, style_group, qss_path, tree_names):
    """Apply or revert the floating model tree.

    Returns "on", "off", or "noop". Safe to call again: the pre-feature
    snapshot is taken once and kept until the preference is turned off.
    """
    global _busy
    if _busy:
        return "busy"
    _busy = True
    try:
        return _sync_unlocked(prefs, overlay_root, style_group, qss_path, tree_names)
    finally:
        _busy = False


def _sync_unlocked(prefs, overlay_root, style_group, qss_path, tree_names):
    want = bool(prefs.GetBool("FloatingModelTree", True))
    applied = bool(prefs.GetBool(APPLIED_KEY, False))
    has_snapshot = _has_string(prefs, SNAPSHOT_KEY)

    if not want and not applied and not has_snapshot:
        return "noop"

    if want:
        if not has_snapshot:
            snapshot = _snapshot_state(overlay_root, style_group)
            prefs.SetString(SNAPSHOT_KEY, json.dumps(snapshot))
        _apply_tree(prefs, overlay_root, style_group, qss_path, tree_names)
        if not applied:
            prefs.SetBool(APPLIED_KEY, 1)
        return "on"

    if has_snapshot:
        snapshot = json.loads(prefs.GetString(SNAPSHOT_KEY))
        _restore_state(overlay_root, style_group, snapshot)
        prefs.RemString(SNAPSHOT_KEY)
    if applied:
        prefs.SetBool(APPLIED_KEY, 0)
    return "off"


def qss_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "BruceWorxModelTree.qss")


def sync_live():
    """Apply the preference against the real parameter tree."""
    import FreeCAD

    prefs = FreeCAD.ParamGet(PREFS_PATH)
    overlay = FreeCAD.ParamGet(OVERLAY_PATH)
    style = FreeCAD.ParamGet(STYLE_PATH)
    docks = FreeCAD.ParamGet(DOCK_PREFS_PATH)
    state = sync(prefs, overlay, style, qss_path(), tree_dock_names(docks))
    if state not in ("noop", "busy"):
        FreeCAD.Console.PrintLog("BruceWorx floating model tree: %s\n" % state)
    return state


def schedule_sync():
    global _scheduled
    if _busy or _scheduled:
        return
    _scheduled = True
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(0, _flush_scheduled)
    except Exception:
        _flush_scheduled()


def _flush_scheduled():
    global _scheduled
    _scheduled = False
    try:
        sync_live()
    except Exception:
        import traceback

        import FreeCAD

        FreeCAD.Console.PrintError("BruceWorx floating model tree failed:\n")
        FreeCAD.Console.PrintError(traceback.format_exc())


class _PrefObserver:
    def onChange(self, _group, _name):
        schedule_sync()


def install():
    """Register the preference page and apply the current (default on) state."""
    global _installed, _observer
    if _installed:
        return
    _installed = True
    try:
        import FreeCAD
        import FreeCADGui

        ui = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preferences-bruceworx.ui")
        FreeCADGui.addPreferencePage(ui, "BruceWorx")
        _observer = _PrefObserver()
        FreeCAD.ParamGet(PREFS_PATH).Attach(_observer)
        sync_live()
    except Exception:
        import traceback

        import FreeCAD

        FreeCAD.Console.PrintError("BruceWorx install failed:\n")
        FreeCAD.Console.PrintError(traceback.format_exc())
