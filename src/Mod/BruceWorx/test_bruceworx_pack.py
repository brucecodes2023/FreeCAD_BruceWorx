# SPDX-License-Identifier: LGPL-2.1-or-later
"""Stdlib tests for the BruceWorx preference pack. No FreeCAD build required.

    python3 src/Mod/BruceWorx/test_bruceworx_pack.py
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bruceworx_pack as pack  # noqa: E402
import ground_grid  # noqa: E402


ROOT = pack.repo_root()


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class RestoreTest(unittest.TestCase):
    def test_enable_then_off_restores_stock_and_user_values(self):
        store = pack.MemoryStore()
        store.set("BaseApp/Preferences/Units", "UserSchema", "int", 4)
        store.set("BaseApp/Preferences/View", "NavigationStyle", "text", "Gui::BlenderNavigationStyle")
        store.set("BaseApp/Preferences/View", "DefaultShapeLineWidth", "int", 4)
        # Gradient is absent: Off must remove it, not invent a value.
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "stock-snapshot.json")
            pack.enable(store, snap, "light")
            self.assertTrue(store.get(pack.APPLIED_GROUP, pack.APPLIED_NAME, "bool", False))
            self.assertEqual(store.get("BaseApp/Preferences/Units", "UserSchema", "int", -1), 0)
            self.assertEqual(
                store.get("BaseApp/Preferences/View", "NavigationStyle", "text", ""),
                "Gui::RevitNavigationStyle",
            )
            self.assertEqual(
                store.get("BaseApp/Preferences/MainWindow", "StyleSheet", "text", ""),
                "BruceWorx.qss",
            )
            self.assertEqual(
                store.get("BaseApp/Preferences/MainWindow", "Theme", "text", ""),
                "BruceWorx",
            )
            self.assertTrue(store.get(pack.APPLIED_GROUP, "ShowGroundGrid", "bool", False))
            self.assertEqual(pack.disable(store, snap), "snapshot")
            self.assertFalse(os.path.exists(snap))

        self.assertEqual(store.get("BaseApp/Preferences/Units", "UserSchema", "int", -1), 4)
        self.assertEqual(
            store.get("BaseApp/Preferences/View", "NavigationStyle", "text", ""),
            "Gui::BlenderNavigationStyle",
        )
        self.assertEqual(store.get("BaseApp/Preferences/View", "DefaultShapeLineWidth", "int", -1), 4)
        self.assertFalse(store.has("BaseApp/Preferences/View", "Gradient", "bool"))
        self.assertFalse(store.has("BaseApp/Preferences/MainWindow", "StyleSheet", "text"))
        self.assertFalse(store.has(pack.APPLIED_GROUP, pack.APPLIED_NAME, "bool"))
        self.assertFalse(store.has(pack.APPLIED_GROUP, "ShowGroundGrid", "bool"))
        self.assertEqual(pack.disable(store, os.path.join(tmp, "missing.json")), "noop")

    def test_reapply_does_not_overwrite_the_original_snapshot(self):
        store = pack.MemoryStore()
        store.set("BaseApp/Preferences/Units", "UserSchema", "int", 2)
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "stock-snapshot.json")
            pack.enable(store, snap, "light")
            store.set("BaseApp/Preferences/Units", "UserSchema", "int", 9)
            pack.enable(store, snap, "dark")
            self.assertEqual(
                store.get("BaseApp/Preferences/MainWindow", "Theme", "text", ""),
                "BruceWorx Dark",
            )
            pack.disable(store, snap)
            self.assertEqual(store.get("BaseApp/Preferences/Units", "UserSchema", "int", -1), 2)

    def test_theme_dialog_pack_name_is_not_saved_as_the_user_theme(self):
        store = pack.MemoryStore()
        store.set("BaseApp/Preferences/MainWindow", "Theme", "text", "BruceWorx")
        store.set("BaseApp/Preferences/MainWindow", "StyleSheet", "text", "FreeCAD.qss")
        with tempfile.TemporaryDirectory() as tmp:
            snap = os.path.join(tmp, "stock-snapshot.json")
            pack.enable(store, snap, "light")
            pack.disable(store, snap)
        self.assertFalse(store.has("BaseApp/Preferences/MainWindow", "Theme", "text"))
        self.assertEqual(
            store.get("BaseApp/Preferences/MainWindow", "StyleSheet", "text", ""),
            "FreeCAD.qss",
        )

    def test_missing_snapshot_clears_pack_keys(self):
        store = pack.MemoryStore()
        pack.apply_entries(store, pack.pack_entries("light"))
        self.assertEqual(pack.disable(store, os.path.join(tempfile.gettempdir(), "no-such-bw-snap.json")), "cleared")
        self.assertFalse(store.has(pack.APPLIED_GROUP, pack.APPLIED_NAME, "bool"))
        self.assertFalse(store.has("BaseApp/Preferences/View", "NavigationStyle", "text"))


class PackContentsTest(unittest.TestCase):
    def test_required_workbenches_are_first_and_enabled(self):
        ordered = ""
        disabled = ""
        for entry in pack.pack_entries("light"):
            if entry["name"] == "Ordered":
                ordered = entry["value"]
            if entry["name"] == "Disabled":
                disabled = entry["value"]
        names = ordered.split(",")
        self.assertEqual(names[:5], list(pack.REQUIRED_WORKBENCHES))
        for name in pack.REQUIRED_WORKBENCHES:
            self.assertNotIn(name, disabled.split(","))

    def test_fusion_nav_and_millimetres(self):
        entries = {(e["path"], e["name"]): e["value"] for e in pack.pack_entries("light")}
        self.assertEqual(entries[("BaseApp/Preferences/Units", "UserSchema")], 0)
        self.assertEqual(
            entries[("BaseApp/Preferences/View", "NavigationStyle")],
            "Gui::RevitNavigationStyle",
        )
        self.assertEqual(entries[("BaseApp/Preferences/General", "AutoloadModule")], "PartDesignWorkbench")
        self.assertTrue(entries[("BaseApp/Preferences/View", "Perspective")])
        self.assertFalse(entries[("BaseApp/Preferences/View", "Orthographic")])
        self.assertEqual(entries[("BaseApp/Preferences/View", "DefaultShapeLineWidth")], 1)
        self.assertEqual(entries[("BaseApp/Preferences/View", "DefaultShapeShininess")], 40)
        self.assertEqual(entries[("BaseApp/Preferences/NaviCube", "CornerNaviCube")], 1)
        self.assertEqual(entries[("BaseApp/Preferences/NaviCube", "CubeSize")], 112)
        self.assertEqual(entries[("BaseApp/Preferences/NaviCube", "FontString")], "Noto Sans")
        self.assertTrue(entries[("BaseApp/MainWindow/Toolbars", "Part Design Modeling Features")])
        self.assertFalse(entries[("BaseApp/MainWindow/Toolbars", "Macro")])
        self.assertFalse(entries[("BaseApp/MainWindow/Toolbars", "B-Spline Tools")])
        self.assertTrue(entries[("BaseApp/MainWindow/Toolbars", "Assembly")])

    def test_dark_differs_only_in_color_and_theme(self):
        light = {(e["path"], e["name"]): e["value"] for e in pack.pack_entries("light")}
        dark = {(e["path"], e["name"]): e["value"] for e in pack.pack_entries("dark")}
        self.assertEqual(set(light), set(dark))
        self.assertNotEqual(
            light[("BaseApp/Preferences/View", "BackgroundColor2")],
            dark[("BaseApp/Preferences/View", "BackgroundColor2")],
        )
        self.assertEqual(dark[("BaseApp/Preferences/MainWindow", "Theme")], "BruceWorx Dark")
        self.assertEqual(light[("BaseApp/Preferences/MainWindow", "StyleSheet")], dark[("BaseApp/Preferences/MainWindow", "StyleSheet")])

    def test_committed_cfg_matches_inventory(self):
        for mode in ("light", "dark"):
            path = pack.cfg_path(mode)
            with open(path, encoding="utf-8") as handle:
                on_disk = handle.read()
            self.assertEqual(on_disk, pack.render_cfg(pack.pack_entries(mode)))
            root = ET.fromstring(on_disk)
            self.assertEqual(root.tag, "FCParameters")

    def test_off_pack_has_no_cfg(self):
        folder = os.path.join(ROOT, "src", "Gui", "PreferencePacks", "BruceWorx Off")
        self.assertTrue(os.path.isfile(os.path.join(folder, "pre.FCMacro")))
        self.assertTrue(os.path.isfile(os.path.join(folder, "post.FCMacro")))
        self.assertFalse(any(name.endswith(".cfg") for name in os.listdir(folder)))

    def test_inventory_covers_view_groups(self):
        paths = {item["path"] for item in pack.INVENTORY}
        for required in (
            "BaseApp/Preferences/View",
            "BaseApp/Preferences/View/LightSources",
            "BaseApp/Preferences/NaviCube",
            "BaseApp/Preferences/Mod/Part",
        ):
            self.assertIn(required, paths)
        names = {item["name"] for item in pack.INVENTORY}
        for required in (
            "BackgroundColor2",
            "BackgroundColor3",
            "SelectionColor",
            "HighlightColor",
            "HeadlightIntensity",
            "DefaultShapeLineWidth",
            "CubeSize",
            "ShowGroundGrid",
        ):
            self.assertIn(required, names)


class StylesheetTest(unittest.TestCase):
    def test_qss_tokens_exist_in_both_themes(self):
        qss_path = os.path.join(ROOT, "src", "Gui", "Stylesheets", "BruceWorx.qss")
        with open(qss_path, encoding="utf-8") as handle:
            qss = handle.read()
        self.assertIn("font-family", qss)
        self.assertIn("border-radius", qss)
        tokens = set(re.findall(r"@([A-Za-z][A-Za-z0-9]*)", qss))
        self.assertIn("AccentColor", tokens)
        self.assertIn("TextForegroundColor", tokens)
        self.assertIn("ToolbarButtonsPadding", tokens)
        for filename in ("BruceWorx.yaml", "BruceWorx Dark.yaml"):
            path = os.path.join(ROOT, "src", "Gui", "Stylesheets", "parameters", filename)
            with open(path, encoding="utf-8") as handle:
                defined = set()
                for line in handle:
                    line = line.split("#", 1)[0].strip()
                    if not line or ":" not in line:
                        continue
                    defined.add(line.split(":", 1)[0].strip())
            missing = tokens - defined
            self.assertFalse(missing, f"{filename} missing {sorted(missing)}")


class PackagingTest(unittest.TestCase):
    def test_package_xml_lists_packs(self):
        path = os.path.join(ROOT, "src", "Gui", "PreferencePacks", "package.xml")
        tree = ET.parse(path)
        names = [node.findtext("name") for node in tree.findall(".//preferencepack")]
        self.assertIn("BruceWorx", names)
        self.assertIn("BruceWorx Dark", names)
        self.assertIn("BruceWorx Off", names)
        off = [node for node in tree.findall(".//preferencepack") if node.findtext("name") == "BruceWorx Off"][0]
        self.assertNotEqual(off.findtext("type"), "Theme")

    def test_cmake_installs_pack_stylesheet_and_mod(self):
        packs = _read(os.path.join(ROOT, "src", "Gui", "PreferencePacks", "CMakeLists.txt"))
        for folder in ("BruceWorx", "BruceWorx Dark", "BruceWorx Off"):
            self.assertIn(f'"{folder}"', packs)
        sheets = _read(os.path.join(ROOT, "src", "Gui", "Stylesheets", "CMakeLists.txt"))
        self.assertIn("BruceWorx.qss", sheets)
        self.assertIn("parameters/BruceWorx.yaml", sheets)
        self.assertIn("parameters/BruceWorx Dark.yaml", sheets)
        mods = _read(os.path.join(ROOT, "src", "Mod", "CMakeLists.txt"))
        self.assertIn("add_subdirectory(BruceWorx)", mods)

    def test_mac_runner_stays_gated(self):
        workflow = _read(os.path.join(ROOT, ".github", "workflows", "bruceworx-ci.yml"))
        self.assertIn("vars.BW_MAC_RUNNER == 'true'", workflow)
        self.assertNotIn("BW_MAC_RUNNER: true", workflow)
        self.assertNotIn('BW_MAC_RUNNER == "false"', workflow)


class GroundGridTest(unittest.TestCase):
    def test_segments_lie_on_the_xy_plane(self):
        segments = ground_grid.grid_segments()
        self.assertGreater(len(segments), 10)
        majors = 0
        for start, end, major in segments:
            self.assertEqual(start[2], 0.0)
            self.assertEqual(end[2], 0.0)
            self.assertLessEqual(abs(start[0]), ground_grid.HALF_EXTENT_MM)
            self.assertLessEqual(abs(start[1]), ground_grid.HALF_EXTENT_MM)
            self.assertLessEqual(abs(end[0]), ground_grid.HALF_EXTENT_MM)
            self.assertLessEqual(abs(end[1]), ground_grid.HALF_EXTENT_MM)
            if major:
                majors += 1
        self.assertGreater(majors, 0)

    def test_toggle_requires_both_flags(self):
        self.assertFalse(ground_grid.should_show(False, True))
        self.assertFalse(ground_grid.should_show(True, False))
        self.assertTrue(ground_grid.should_show(True, True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
