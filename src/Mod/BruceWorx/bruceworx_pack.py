# SPDX-License-Identifier: LGPL-2.1-or-later
"""BruceWorx preference pack: values, snapshot, and restore.

FreeCAD applies a preference pack by merging a ``.cfg`` file. That merge is
one-way, so this module snapshots every key the pack writes and puts the
previous values back when the "BruceWorx Off" pack runs.

The ``.cfg`` files under ``src/Gui/PreferencePacks/`` are generated from
``INVENTORY`` (``python3 -m`` is not required; ``render_cfg`` is the writer).
Keep the two in lockstep: the unit test fails if a committed cfg drifts.

View / 3D inventory (FCB-P1V-01)
--------------------------------
Stock defaults below are the values FreeCAD uses when the key is absent
(UI ``prefEntry`` defaults and ``View3DSettings`` / ``ViewParams`` / NaviCube).
Keys with a BruceWorx value are written by the pack. Keys with value ``None``
were surveyed and left alone.

Navigation is ``Gui::RevitNavigationStyle``: middle-mouse pan, Shift+middle
orbit, wheel zoom. That is the built-in style that matches Fusion 360's
default. Units are schema index 0, "Standard (mm, kg, s, °)".

Part objects stay on the compiled display mode "Flat Lines" (shaded faces
plus solid edges). There is no global preference for that mode; edge color,
edge width, shininess and two-sided lighting are the preferences new shapes
read.
"""

from __future__ import annotations

import json
import os
import xml.sax.saxutils as xml_escape

SNAPSHOT_VERSION = 1
APPLIED_GROUP = "BaseApp/Preferences/BruceWorx"
APPLIED_NAME = "Applied"

# Theme strings the preferences dialog writes *before* a pack's pre.FCMacro
# runs. They are not the user's previous theme.
PACK_THEME_NAMES = ("BruceWorx", "BruceWorx Dark", "BruceWorx Off")

REQUIRED_WORKBENCHES = (
    "PartDesignWorkbench",
    "AssemblyWorkbench",
    "SketcherWorkbench",
    "PartWorkbench",
    "TechDrawWorkbench",
)

_UNSET = object()


def rgba(r: int, g: int, b: int, a: int = 255) -> int:
    """FreeCAD packed color: 0xRRGGBBAA (see Base::Color::asPackedRGBA)."""
    return (r << 24) | (g << 16) | (b << 8) | a


def _e(path, name, typ, stock, light, dark=_UNSET, note=""):
    if dark is _UNSET:
        dark = light
    return {
        "path": path,
        "name": name,
        "type": typ,
        "stock": stock,
        "light": light,
        "dark": dark,
        "note": note,
    }


# Order is the cfg order (grouped by path, then name) after render_cfg sorts.
INVENTORY = [
    # --- units, start workbench, toolbar chrome (FCB-P1-04 / P1-05) ---
    _e(
        "BaseApp/Preferences/Units",
        "UserSchema",
        "int",
        0,
        0,
        note="0 = Standard (mm, kg, s, °). Written so a previous inch schema is restored on Off.",
    ),
    _e(
        "BaseApp/Preferences/General",
        "AutoloadModule",
        "text",
        "StartWorkbench",
        "PartDesignWorkbench",
        note="Startup workbench. Stock config often falls through to Start.",
    ),
    _e(
        "BaseApp/Preferences/General",
        "BackgroundAutoloadModules",
        "text",
        "",
        "",
        note="No extra workbenches loaded in the background.",
    ),
    _e(
        "BaseApp/Preferences/General",
        "ToolbarIconSize",
        "int",
        0,
        24,
        note="0 means 'use the current toolbar size'. 24px is the compact modern size.",
    ),
    _e(
        "BaseApp/Preferences/Workbenches",
        "Ordered",
        "text",
        "",
        ",".join(REQUIRED_WORKBENCHES),
        note="Required workbenches first. Any other enabled workbench is appended by FreeCAD.",
    ),
    _e(
        "BaseApp/Preferences/Workbenches",
        "Disabled",
        "text",
        "NoneWorkbench,TestWorkbench,InspectionWorkbench,RobotWorkbench,OpenSCADWorkbench",
        ",".join(
            [
                "NoneWorkbench",
                "TestWorkbench",
                "InspectionWorkbench",
                "RobotWorkbench",
                "OpenSCADWorkbench",
                "MeshWorkbench",
                "PointsWorkbench",
                "ReverseEngineeringWorkbench",
                "SurfaceWorkbench",
                "MeshPartWorkbench",
                "CAMWorkbench",
                "FemWorkbench",
                "BIMWorkbench",
                "MaterialWorkbench",
                "ImportWorkbench",
                "CloudWorkbench",
                "SandboxWorkbench",
            ]
        ),
        note="Selector trim. Draft, Spreadsheet and Start stay available.",
    ),
    _e(
        "BaseApp/Preferences/Workbenches",
        "WorkbenchSelectorType",
        "int",
        0,
        1,
        note="0 = combo box, 1 = tab bar (Fusion-style workbench switcher).",
    ),
    _e(
        "BaseApp/Preferences/Workbenches",
        "WorkbenchSelectorItem",
        "int",
        0,
        0,
        note="0 = icon and text. Unchanged, recorded so Off can restore a custom style.",
    ),
    # Toolbars live in one global group, keyed by the toolbar's command name.
    # False hides it; True keeps the modeling toolbars that a trimmed layout needs.
    *[
        _e(
            "BaseApp/MainWindow/Toolbars",
            name,
            "bool",
            None,
            visible,
            note="Toolbar visibility. None stock means 'workbench default'.",
        )
        for name, visible in (
            ("File", True),
            ("Workbench", True),
            ("View", True),
            ("Structure", True),
            ("Clipboard", False),
            ("Macro", False),
            ("Individual Views", False),
            ("Help", False),
            ("Edit", False),
            ("Part Design Helper Features", True),
            ("Part Design Modeling Features", True),
            ("Part Design Dress-Up Features", True),
            ("Part Design Transformation Features", True),
            ("Sketcher", True),
            ("Edit Mode", True),
            ("Geometries", True),
            ("Constraints", True),
            ("Sketcher Tools", True),
            ("B-Spline Tools", False),
            ("Visual Helpers", True),
            ("Solids", True),
            ("Part Tools", True),
            ("Boolean Tools", True),
            ("Assembly", True),
            ("Assembly Joints", True),
            ("TechDraw Pages", True),
            ("TechDraw Views", True),
            ("TechDraw Dimensions", True),
            ("TechDraw Annotation", True),
            ("TechDraw Stacking", False),
            ("TechDraw Attributes", False),
            ("TechDraw Centerlines", False),
            ("TechDraw Extend Dimensions", False),
            ("TechDraw File Access", False),
            ("TechDraw Decoration", False),
        )
    ],
    # --- UI theme (FCB-P1-02). One QSS, two parameter yamls. ---
    _e(
        "BaseApp/Preferences/MainWindow",
        "StyleSheet",
        "text",
        "",
        "BruceWorx.qss",
        note="Token stylesheet. Light and dark share it.",
    ),
    _e(
        "BaseApp/Preferences/MainWindow",
        "Theme",
        "text",
        "",
        "BruceWorx",
        "BruceWorx Dark",
        note="Selects Gui/Stylesheets/parameters/<Theme>.yaml.",
    ),
    _e(
        "BaseApp/Preferences/MainWindow",
        "QtStyle",
        "text",
        "",
        "FreeCAD",
        note="Same Qt style plugin the built-in FreeCAD Light pack uses.",
    ),
    _e(
        "BaseApp/Preferences/MainWindow",
        "OverlayActiveStyleSheet",
        "text",
        "",
        "Freecad Overlay.qss",
        note="Keep the stock overlay sheet so dock overlays still theme.",
    ),
    _e("BaseApp/Preferences/Themes", "ThemeAccentColor1", "uint", None, rgba(0, 113, 227), rgba(10, 132, 255)),
    _e("BaseApp/Preferences/Themes", "ThemeAccentColor2", "uint", None, rgba(90, 200, 250), rgba(64, 156, 255)),
    _e("BaseApp/Preferences/Themes", "ThemeAccentColor3", "uint", None, rgba(0, 113, 227), rgba(10, 132, 255)),
    _e("BaseApp/Preferences/TreeView", "TreeActiveColor", "uint", None, rgba(210, 230, 255), rgba(10, 60, 110)),
    _e("BaseApp/Preferences/TreeView", "TreeEditColor", "uint", None, rgba(210, 240, 210), rgba(30, 80, 50)),
    # --- viewport background (FCB-P1V-02) ---
    _e(
        "BaseApp/Preferences/View",
        "Gradient",
        "bool",
        True,
        True,
        note="Linear gradient. Stock UI default is the classic blue gradient.",
    ),
    _e("BaseApp/Preferences/View", "RadialGradient", "bool", False, False),
    _e("BaseApp/Preferences/View", "Simple", "bool", False, False),
    _e("BaseApp/Preferences/View", "UseBackgroundColorMid", "bool", False, False),
    _e(
        "BaseApp/Preferences/View",
        "BackgroundColor",
        "uint",
        3940932863,
        rgba(231, 235, 242),
        rgba(28, 30, 36),
        note="Simple-color fallback. Stock runtime default is #EAE5DC.",
    ),
    _e(
        "BaseApp/Preferences/View",
        "BackgroundColor2",
        "uint",
        859006463,
        rgba(244, 246, 250),
        rgba(50, 54, 63),
        note="Gradient top. Stock #333365.",
    ),
    _e(
        "BaseApp/Preferences/View",
        "BackgroundColor3",
        "uint",
        2880160255,
        rgba(215, 220, 230),
        rgba(23, 25, 30),
        note="Gradient bottom. Stock #ABABC1.",
    ),
    _e(
        "BaseApp/Preferences/View",
        "BackgroundColor4",
        "uint",
        1869583359,
        rgba(230, 233, 240),
        rgba(36, 39, 46),
        note="Middle stop, unused while UseBackgroundColorMid is false. Stock #6F6F93.",
    ),
    # --- selection / preselection (FCB-P1V-02) ---
    _e(
        "BaseApp/Preferences/View",
        "SelectionColor",
        "uint",
        None,
        rgba(0, 113, 227),
        rgba(10, 132, 255),
        note="Stock runtime default is SbColor(0.1, 0.8, 0.1), a green.",
    ),
    _e(
        "BaseApp/Preferences/View",
        "HighlightColor",
        "uint",
        None,
        rgba(90, 200, 250),
        rgba(100, 210, 255),
        note="Preselection. Stock runtime default is SbColor(0.8, 0.1, 0.1), a red.",
    ),
    _e("BaseApp/Preferences/View", "EnableSelection", "bool", True, True),
    _e("BaseApp/Preferences/View", "EnablePreselection", "bool", True, True),
    # --- navigation (FCB-P1-04) ---
    _e(
        "BaseApp/Preferences/View",
        "NavigationStyle",
        "text",
        "Gui::CADNavigationStyle",
        "Gui::RevitNavigationStyle",
        note="Fusion-like: pan MMB, orbit Shift+MMB, zoom wheel.",
    ),
    _e(
        "BaseApp/Preferences/View",
        "Perspective",
        "bool",
        False,
        True,
        note="Fusion opens in perspective. Stock template is orthographic.",
    ),
    _e("BaseApp/Preferences/View", "Orthographic", "bool", True, False),
    _e("BaseApp/Preferences/View", "ShowNaviCube", "bool", True, True),
    # --- shading and edges (FCB-P1V-03 / 04) ---
    _e(
        "BaseApp/Preferences/View",
        "DefaultShapeColor",
        "uint",
        0xCCCCCCFF,
        rgba(200, 205, 214),
        rgba(176, 182, 192),
        note="Body color for new shapes. Stock #CCCCCC.",
    ),
    _e(
        "BaseApp/Preferences/View",
        "DefaultShapeLineColor",
        "uint",
        421075455,
        rgba(58, 58, 60),
        rgba(242, 242, 247),
        note="Edge color. Stock #191919. Dark pack uses a light edge so it reads on the dark ground.",
    ),
    _e(
        "BaseApp/Preferences/View",
        "DefaultShapeVertexColor",
        "uint",
        421075455,
        rgba(58, 58, 60),
        rgba(242, 242, 247),
    ),
    _e(
        "BaseApp/Preferences/View",
        "DefaultShapeLineWidth",
        "int",
        2,
        1,
        note="Thinner edges. DrawStyle stays the compiled Solid default.",
    ),
    _e("BaseApp/Preferences/View", "DefaultShapePointSize", "int", 2, 2),
    _e(
        "BaseApp/Preferences/View",
        "DefaultShapeShininess",
        "int",
        90,
        40,
        note="Stock UI default is 90 (glossy). 40 is a softer studio highlight.",
    ),
    _e(
        "BaseApp/Preferences/View",
        "DefaultShapeTransparency",
        "int",
        0,
        0,
    ),
    _e(
        "BaseApp/Preferences/View",
        "DefaultAmbientColor",
        "uint",
        rgba(85, 85, 85),
        rgba(110, 110, 115),
        note="Slightly lifted ambient so faces are less harsh. Stock #555555.",
    ),
    _e(
        "BaseApp/Preferences/View",
        "DefaultSpecularColor",
        "uint",
        rgba(136, 136, 136),
        rgba(90, 90, 96),
        note="Quieter specular. Stock #888888.",
    ),
    _e(
        "BaseApp/Preferences/View",
        "DefaultEmissiveColor",
        "uint",
        rgba(0, 0, 0),
        rgba(0, 0, 0),
    ),
    _e(
        "BaseApp/Preferences/Mod/Part",
        "TwoSideRendering",
        "bool",
        True,
        True,
        note="Two-sided lighting is the Part default. Recorded so Off restores a user who turned it off.",
    ),
    # Lights are read from View/LightSources at startup. The preference page
    # also stores the enable flags on View, so both are written.
    _e("BaseApp/Preferences/View", "EnableHeadlight", "bool", True, True),
    _e("BaseApp/Preferences/View", "EnableBacklight", "bool", True, True),
    _e("BaseApp/Preferences/View", "EnableFillLight", "bool", True, True),
    _e("BaseApp/Preferences/View/LightSources", "EnableHeadlight", "bool", True, True),
    _e("BaseApp/Preferences/View/LightSources", "EnableBacklight", "bool", True, True),
    _e("BaseApp/Preferences/View/LightSources", "EnableFillLight", "bool", True, True),
    _e(
        "BaseApp/Preferences/View/LightSources",
        "HeadlightColor",
        "uint",
        0xFFFFFFFF,
        rgba(255, 255, 255),
    ),
    _e(
        "BaseApp/Preferences/View/LightSources",
        "HeadlightIntensity",
        "int",
        90,
        82,
        note="A little softer than the stock 90.",
    ),
    _e(
        "BaseApp/Preferences/View/LightSources",
        "BacklightColor",
        "uint",
        0xF5F5EEFF,
        rgba(247, 244, 238),
        note="Slightly warm backlight. Stock is #F5F5EE.",
    ),
    _e("BaseApp/Preferences/View/LightSources", "BacklightIntensity", "int", 60, 35),
    _e(
        "BaseApp/Preferences/View/LightSources",
        "FillLightColor",
        "uint",
        0xE6FAFFFF,
        rgba(234, 244, 255),
        note="Cool fill. Stock is #E6FAFF.",
    ),
    _e("BaseApp/Preferences/View/LightSources", "FillLightIntensity", "int", 40, 30),
    _e(
        "BaseApp/Preferences/View/LightSources",
        "AmbientLightColor",
        "uint",
        0xFFFFFFFF,
        rgba(255, 255, 255),
    ),
    _e("BaseApp/Preferences/View/LightSources", "AmbientLightIntensity", "int", 20, 26),
    # Directions are surveyed and left at the compiled defaults:
    #   Headlight (0.6841049,-0.12062616,-0.7193398)
    #   Fill      (-0.6403416,0.7631294,0.087155744)
    #   Back      (-0.7544065,-0.63302225,-0.17364818)
    # --- navigation cube (FCB-P1V-06) ---
    _e(
        "BaseApp/Preferences/NaviCube",
        "CornerNaviCube",
        "int",
        1,
        1,
        note="0 top-left, 1 top-right, 2 bottom-left, 3 bottom-right. Top-right matches Fusion.",
    ),
    _e("BaseApp/Preferences/NaviCube", "CubeSize", "int", 132, 112, note="Slightly smaller than the stock 132px cube."),
    _e("BaseApp/Preferences/NaviCube", "OffsetX", "int", 0, 12),
    _e("BaseApp/Preferences/NaviCube", "OffsetY", "int", 0, 12),
    _e("BaseApp/Preferences/NaviCube", "FontString", "text", "", "Noto Sans"),
    _e("BaseApp/Preferences/NaviCube", "FontZoom", "float", 0.3, 0.34),
    _e(
        "BaseApp/Preferences/NaviCube",
        "FontWeight",
        "int",
        0,
        57,
        note="0 keeps the default weight. 57 maps to QFont::Medium.",
    ),
    _e("BaseApp/Preferences/NaviCube", "ChamferSize", "float", 0.12, 0.16),
    _e("BaseApp/Preferences/NaviCube", "BorderWidth", "float", 1.1, 1.0),
    _e("BaseApp/Preferences/NaviCube", "InactiveOpacity", "int", 50, 45),
    _e("BaseApp/Preferences/NaviCube", "NaviRotateToNearest", "bool", True, True),
    _e("BaseApp/Preferences/NaviCube", "ShowCS", "bool", True, True),
    _e(
        "BaseApp/Preferences/NaviCube",
        "BaseColor",
        "uint",
        3806916544,
        rgba(245, 245, 247, 220),
        rgba(44, 44, 46, 230),
        note="Stock base is #E2E8EF at alpha 192.",
    ),
    _e(
        "BaseApp/Preferences/NaviCube",
        "EmphaseColor",
        "uint",
        None,
        rgba(29, 29, 31),
        rgba(245, 245, 247),
        note="Face text. Stock contrasts automatically against the base color.",
    ),
    _e(
        "BaseApp/Preferences/NaviCube",
        "HiliteColor",
        "uint",
        2867003391,
        rgba(0, 113, 227),
        rgba(10, 132, 255),
        note="Stock hilite is #AAE2FF.",
    ),
    # --- pack flags. The ground grid reads these (FCB-P1V-05). ---
    _e(
        APPLIED_GROUP,
        APPLIED_NAME,
        "bool",
        False,
        True,
        note="True while either BruceWorx theme pack is applied.",
    ),
    _e(
        APPLIED_GROUP,
        "ShowGroundGrid",
        "bool",
        False,
        True,
        note="Toggle the ground grid without leaving the pack. Off removes the key.",
    ),
]


def pack_entries(mode: str = "light") -> list[dict]:
    if mode not in ("light", "dark"):
        raise ValueError(mode)
    entries = []
    for item in INVENTORY:
        value = item["light"] if mode == "light" else item["dark"]
        if value is None:
            continue
        entries.append(
            {
                "path": item["path"],
                "name": item["name"],
                "type": item["type"],
                "value": value,
            }
        )
    return entries


def managed_keys() -> list[tuple[str, str, str]]:
    """Union of keys either theme pack writes."""
    seen = []
    found = set()
    for mode in ("light", "dark"):
        for entry in pack_entries(mode):
            key = (entry["path"], entry["name"], entry["type"])
            if key not in found:
                found.add(key)
                seen.append(key)
    return seen


class MemoryStore:
    """Stand-in for FreeCAD's parameter groups. Used by the unit test."""

    def __init__(self):
        self._data: dict[tuple[str, str], tuple[str, object]] = {}

    def has(self, path: str, name: str, typ: str) -> bool:
        item = self._data.get((path, name))
        return item is not None and item[0] == typ

    def get(self, path: str, name: str, typ: str, default):
        item = self._data.get((path, name))
        if item is None or item[0] != typ:
            return default
        return item[1]

    def set(self, path: str, name: str, typ: str, value) -> None:
        self._data[(path, name)] = (typ, value)

    def remove(self, path: str, name: str, typ: str) -> None:
        item = self._data.get((path, name))
        if item is not None and item[0] == typ:
            del self._data[(path, name)]


class FreeCADStore:
    """Adapter over ``App.ParamGet("User parameter:...")``."""

    def __init__(self):
        import FreeCAD as App

        self._App = App

    def _group(self, path: str):
        return self._App.ParamGet("User parameter:" + path)

    def has(self, path: str, name: str, typ: str) -> bool:
        group = self._group(path)
        names = {
            "bool": group.GetBools,
            "int": group.GetInts,
            "uint": group.GetUnsigneds,
            "float": group.GetFloats,
            "text": group.GetStrings,
        }[typ]()
        return name in list(names)

    def get(self, path: str, name: str, typ: str, default):
        group = self._group(path)
        if typ == "bool":
            return bool(group.GetBool(name, bool(default)))
        if typ == "int":
            return int(group.GetInt(name, int(default)))
        if typ == "uint":
            return int(group.GetUnsigned(name, int(default)))
        if typ == "float":
            return float(group.GetFloat(name, float(default)))
        return str(group.GetString(name, "" if default is None else str(default)))

    def set(self, path: str, name: str, typ: str, value) -> None:
        group = self._group(path)
        if typ == "bool":
            group.SetBool(name, bool(value))
        elif typ == "int":
            group.SetInt(name, int(value))
        elif typ == "uint":
            group.SetUnsigned(name, int(value))
        elif typ == "float":
            group.SetFloat(name, float(value))
        else:
            group.SetString(name, str(value))

    def remove(self, path: str, name: str, typ: str) -> None:
        group = self._group(path)
        {
            "bool": group.RemBool,
            "int": group.RemInt,
            "uint": group.RemUnsigned,
            "float": group.RemFloat,
            "text": group.RemString,
        }[typ](name)


def _is_applied(store) -> bool:
    return bool(store.get(APPLIED_GROUP, APPLIED_NAME, "bool", False))


def _capture(store, entry: dict) -> dict:
    path, name, typ = entry["path"], entry["name"], entry["type"]
    present = store.has(path, name, typ)
    recorded = {"path": path, "name": name, "type": typ, "present": present}
    if not present:
        return recorded
    value = store.get(path, name, typ, None)
    if name == "Theme" and path.endswith("MainWindow") and value in PACK_THEME_NAMES:
        # The theme combo writes the pack name before pre.FCMacro. That is
        # not the theme the user had.
        recorded["present"] = False
        return recorded
    recorded["value"] = value
    return recorded


def snapshot_if_needed(store, snapshot_path: str, mode: str = "light") -> bool:
    """Write the stock snapshot once. Returns True when a new file is written."""
    if _is_applied(store):
        return False
    if os.path.exists(snapshot_path):
        # A previous enable was interrupted after the snapshot and before
        # Applied was set. Keep the original file.
        return False
    payload = {
        "version": SNAPSHOT_VERSION,
        "entries": [_capture(store, entry) for entry in pack_entries(mode)],
    }
    os.makedirs(os.path.dirname(snapshot_path), exist_ok=True)
    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return True


def apply_entries(store, entries: list[dict]) -> None:
    for entry in entries:
        store.set(entry["path"], entry["name"], entry["type"], entry["value"])


def _restore_record(store, record: dict) -> None:
    path, name, typ = record["path"], record["name"], record["type"]
    if record.get("present"):
        store.set(path, name, typ, record.get("value"))
    else:
        store.remove(path, name, typ)


def restore_snapshot(store, snapshot_path: str) -> str:
    """Put snapshotted keys back.

    Returns ``"snapshot"`` when the file was used, ``"cleared"`` when the
    pack was on but the file was missing (keys removed so code defaults
    return), or ``"noop"`` when the pack was not applied.
    """
    if os.path.exists(snapshot_path):
        with open(snapshot_path, encoding="utf-8") as handle:
            payload = json.load(handle)
        for record in payload.get("entries", []):
            _restore_record(store, record)
        # Keys a later theme added (dark-only values share keys, but be safe).
        restored = {(r["path"], r["name"]) for r in payload.get("entries", [])}
        for path, name, typ in managed_keys():
            if (path, name) not in restored:
                store.remove(path, name, typ)
        try:
            os.remove(snapshot_path)
        except OSError:
            pass
        return "snapshot"
    if _is_applied(store):
        for path, name, typ in managed_keys():
            store.remove(path, name, typ)
        return "cleared"
    return "noop"


def enable(store, snapshot_path: str, mode: str = "light") -> None:
    snapshot_if_needed(store, snapshot_path, mode)
    apply_entries(store, pack_entries(mode))


def disable(store, snapshot_path: str) -> str:
    return restore_snapshot(store, snapshot_path)


def default_snapshot_path() -> str:
    import FreeCAD as App

    return os.path.join(App.getUserAppDataDir(), "BruceWorx", "stock-snapshot.json")


def freecad_pre(mode: str) -> None:
    snapshot_if_needed(FreeCADStore(), default_snapshot_path(), mode)


def freecad_off() -> str:
    return disable(FreeCADStore(), default_snapshot_path())


def _fmt_float(value: float) -> str:
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    if "." not in text:
        text += ".0"
    return text


def _fmt_value(typ: str, value) -> str:
    if typ == "bool":
        return "1" if value else "0"
    if typ == "float":
        return _fmt_float(value)
    if typ == "text":
        return str(value)
    return str(int(value))


def _xml_param(entry: dict, indent: int) -> str:
    pad = "  " * indent
    typ = entry["type"]
    tag = {"bool": "FCBool", "int": "FCInt", "uint": "FCUInt", "float": "FCFloat", "text": "FCText"}[typ]
    name = xml_escape.escape(entry["name"], {'"': "&quot;"})
    if typ == "text":
        body = xml_escape.escape(str(entry["value"]))
        return f"{pad}<{tag} Name=\"{name}\">{body}</{tag}>"
    return f"{pad}<{tag} Name=\"{name}\" Value=\"{_fmt_value(typ, entry['value'])}\"/>"


class _Node:
    def __init__(self):
        self.params: list[dict] = []
        self.children: dict[str, _Node] = {}


def render_cfg(entries: list[dict]) -> str:
    root = _Node()
    for entry in entries:
        node = root
        for part in entry["path"].split("/"):
            node = node.children.setdefault(part, _Node())
        node.params.append(entry)

    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>',
        "<FCParameters>",
        '  <FCParamGroup Name="Root">',
    ]

    def emit(node: _Node, indent: int) -> None:
        pad = "  " * indent
        for entry in sorted(node.params, key=lambda item: item["name"]):
            lines.append(_xml_param(entry, indent))
        for name in sorted(node.children):
            lines.append(f'{pad}<FCParamGroup Name="{xml_escape.escape(name)}">')
            emit(node.children[name], indent + 1)
            lines.append(f"{pad}</FCParamGroup>")

    emit(root, 2)
    lines.append("  </FCParamGroup>")
    lines.append("</FCParameters>")
    lines.append("")
    return "\n".join(lines)


def repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def cfg_path(mode: str) -> str:
    folder = "BruceWorx" if mode == "light" else "BruceWorx Dark"
    filename = folder + ".cfg"
    return os.path.join(repo_root(), "src", "Gui", "PreferencePacks", folder, filename)


def write_cfg_files() -> None:
    for mode in ("light", "dark"):
        path = cfg_path(mode)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(render_cfg(pack_entries(mode)))


if __name__ == "__main__":
    write_cfg_files()
    print("wrote", cfg_path("light"))
    print("wrote", cfg_path("dark"))
