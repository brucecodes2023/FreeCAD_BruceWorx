# SPDX-License-Identifier: LGPL-2.1-or-later
"""Offscreen before/after of the BruceWorx stylesheet and viewport colors.

Renders a Qt mock of the main window (the real BruceWorx.qss, with theme
tokens substituted) and a 3D view painted from the preference-pack colors.
This is not a FreeCAD process; it is the sheet and the View/NaviCube values
the pack writes.

    QT_QPA_PLATFORM=offscreen python3 package/bruceworx/render_style_preview.py [outdir]
"""

from __future__ import annotations

import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src", "Mod", "BruceWorx"))

import ground_grid  # noqa: E402
import bruceworx_pack as pack  # noqa: E402

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRect, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QFont,
    QIcon,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStatusBar,
    QTabBar,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


def _load_tokens(path: str) -> dict[str, str]:
    """Read theme yaml. Quoted values keep their #hex colors; a bare # starts a comment."""
    tokens = {}
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            value = value.strip()
            if value[:1] in "'\"":
                quote = value[0]
                end = value.find(quote, 1)
                value = value[1:end] if end != -1 else value[1:]
            else:
                value = value.split("#", 1)[0].strip()
            if value:
                tokens[key.strip()] = value
    return tokens


def _substitute(qss: str, tokens: dict[str, str]) -> str:
    pattern = re.compile(r"@([A-Za-z][A-Za-z0-9]*)")
    for _ in range(6):
        updated = pattern.sub(lambda match: tokens.get(match.group(1), match.group(0)), qss)
        if updated == qss:
            break
        qss = updated
    return qss


def _theme(mode: str) -> tuple[str, dict[str, str]]:
    sheet = os.path.join(ROOT, "src", "Gui", "Stylesheets", "BruceWorx.qss")
    theme = "BruceWorx.yaml" if mode == "light" else "BruceWorx Dark.yaml"
    tokens = _load_tokens(os.path.join(ROOT, "src", "Gui", "Stylesheets", "parameters", theme))
    with open(sheet, encoding="utf-8") as handle:
        return _substitute(handle.read(), tokens), tokens


def _unpack(value: int) -> QColor:
    return QColor((value >> 24) & 255, (value >> 16) & 255, (value >> 8) & 255, value & 255)


def _colors(mode: str) -> dict:
    entries = {(item["path"], item["name"]): item["value"] for item in pack.pack_entries(mode)}
    view = "BaseApp/Preferences/View"
    cube = "BaseApp/Preferences/NaviCube"
    return {
        "top": _unpack(entries[(view, "BackgroundColor2")]),
        "bottom": _unpack(entries[(view, "BackgroundColor3")]),
        "shape": _unpack(entries[(view, "DefaultShapeColor")]),
        "edge": _unpack(entries[(view, "DefaultShapeLineColor")]),
        "selection": _unpack(entries[(view, "SelectionColor")]),
        "preselect": _unpack(entries[(view, "HighlightColor")]),
        "cube": _unpack(entries[(cube, "BaseColor")]),
        "cube_text": _unpack(entries[(cube, "EmphaseColor")]),
        "cube_hilite": _unpack(entries[(cube, "HiliteColor")]),
        "font": entries[(cube, "FontString")],
        "grid_minor": QColor(158, 163, 173, 150),
        "grid_major": QColor(90, 96, 110, 190),
    }


STOCK_COLORS = {
    "top": QColor(0x33, 0x33, 0x65),
    "bottom": QColor(0xAB, 0xAB, 0xC1),
    "shape": QColor(0xCC, 0xCC, 0xCC),
    "edge": QColor(0x19, 0x19, 0x19),
    "selection": QColor(26, 204, 26),
    "preselect": QColor(204, 26, 26),
    "cube": QColor(0xE2, 0xE8, 0xEF, 192),
    "cube_text": QColor(20, 20, 20),
    "cube_hilite": QColor(0xAA, 0xE2, 0xFF),
    "font": "DejaVu Sans",
    "grid_minor": QColor(180, 180, 190, 90),
    "grid_major": QColor(210, 210, 220, 140),
}

STOCK_QSS = """
QMainWindow, QDialog, QDockWidget, QMenuBar, QToolBar, QStatusBar {
  background: #f0f0f0;
  color: #202020;
  font-family: "DejaVu Sans", sans-serif;
  font-size: 12px;
}
QMenuBar::item { padding: 2px 6px; background: transparent; }
QToolBar { spacing: 0px; padding: 1px; border-bottom: 1px solid #c8c8c8; }
QToolButton { border: 1px solid transparent; border-radius: 0; padding: 1px; margin: 0; }
QDockWidget { border: 1px solid #b4b4b4; }
QDockWidget::title { background: #e4e4e4; padding: 2px 4px; text-align: left; }
QTabBar::tab { background: #e6e6e6; padding: 3px 8px; border: 1px solid #c0c0c0; border-radius: 0; }
QTabBar::tab:selected { background: #ffffff; }
QTreeWidget { background: #ffffff; border: none; font-size: 12px; }
QTreeWidget::item { padding: 1px; min-height: 16px; }
QStatusBar { border-top: 1px solid #c8c8c8; }
"""


class Viewport(QWidget):
    def __init__(self, colors: dict):
        super().__init__()
        self.colors = colors
        self.setMinimumSize(640, 420)
        self.setObjectName("BWViewport")

    def _project(self, x: float, y: float, z: float) -> QPointF:
        width = self.width()
        height = self.height()
        scale = min(width, height) / 780.0
        origin_x = width * 0.46
        origin_y = height * 0.66
        return QPointF(origin_x + (x - y * 0.62) * scale, origin_y + (y * 0.34 - z) * scale)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_background(painter)
        self._paint_grid(painter)
        self._paint_body(painter, (-70, -46, 0), (78, 52, 64), selected=True)
        self._paint_body(painter, (96, -30, 0), (168, 28, 36), selected=False)
        self._paint_cube(painter)
        painter.end()

    def _paint_background(self, painter: QPainter):
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, self.colors["top"])
        gradient.setColorAt(1, self.colors["bottom"])
        painter.fillRect(self.rect(), gradient)

    def _paint_grid(self, painter: QPainter):
        for start, end, major in ground_grid.grid_segments():
            color = self.colors["grid_major"] if major else self.colors["grid_minor"]
            pen = QPen(color)
            pen.setWidthF(1.4 if major else 0.8)
            painter.setPen(pen)
            painter.drawLine(self._project(*start), self._project(*end))

    def _paint_body(self, painter: QPainter, lo, hi, selected: bool):
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        corners = {
            name: self._project(x, y, z)
            for name, (x, y, z) in {
                "lbf": (x0, y0, z0),
                "rbf": (x1, y0, z0),
                "rtf": (x1, y1, z0),
                "ltf": (x0, y1, z0),
                "lbb": (x0, y0, z1),
                "rbb": (x1, y0, z1),
                "rtb": (x1, y1, z1),
                "ltb": (x0, y1, z1),
            }.items()
        }
        shape = QColor(self.colors["shape"])
        top = shape.lighter(108)
        side = shape.darker(112)
        front = shape.darker(102)
        if not selected:
            top.setAlpha(210)
            side.setAlpha(210)
            front.setAlpha(210)
        faces = (
            (("lbb", "rbb", "rtb", "ltb"), top),
            (("rbf", "rtf", "rtb", "rbb"), side),
            (("ltf", "rtf", "rtb", "ltb"), front),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        for keys, color in faces:
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF([corners[key] for key in keys]))
        edge = QColor(self.colors["selection"] if selected else self.colors["preselect"])
        pen = QPen(edge)
        pen.setWidthF(2.2 if selected else 1.6)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        loops = (
            ("lbf", "rbf", "rtf", "ltf"),
            ("lbb", "rbb", "rtb", "ltb"),
        )
        uprights = (("lbf", "lbb"), ("rbf", "rbb"), ("rtf", "rtb"), ("ltf", "ltb"))
        for loop in loops:
            painter.drawPolygon(QPolygonF([corners[key] for key in loop]))
        for a, b in uprights:
            painter.drawLine(corners[a], corners[b])

    def _paint_cube(self, painter: QPainter):
        size = 78
        margin = 18
        origin = QPointF(self.width() - margin - size, margin + 8)
        face = size * 0.42

        def corner(x, y, z):
            return QPointF(origin.x() + x * face + y * face * 0.15, origin.y() + size - z * face + y * face * 0.55)

        base = QColor(self.colors["cube"])
        base.setAlpha(min(255, base.alpha() + 30))
        hilite = QColor(self.colors["cube_hilite"])
        text = QColor(self.colors["cube_text"])
        faces = (
            (("0,1,1", "1,1,1", "1,1,0", "0,1,0"), base.darker(108)),
            (("1,0,1", "1,1,1", "1,1,0", "1,0,0"), hilite),
            (("0,0,1", "1,0,1", "1,1,1", "0,1,1"), base.lighter(108)),
        )
        painter.setPen(QPen(text, 1))
        for keys, color in faces:
            polygon = []
            for key in keys:
                x, y, z = (float(part) for part in key.split(","))
                polygon.append(corner(x, y, z))
            painter.setBrush(color)
            painter.drawPolygon(QPolygonF(polygon))
        font = QFont(self.colors["font"], 8)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        painter.setPen(text)
        painter.drawText(QRect(int(origin.x()), int(origin.y()) + 8, int(size), 18), Qt.AlignmentFlag.AlignCenter, "TOP")
        painter.drawText(
            QRect(int(origin.x()) + 8, int(origin.y()) + int(size * 0.42), int(size * 0.7), 16),
            Qt.AlignmentFlag.AlignCenter,
            "FRONT",
        )


def _icon(kind: str, color: QColor) -> QIcon:
    pixmap = QPixmap(28, 28)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color, 1.6)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    if kind == "pad":
        painter.drawRect(6, 10, 16, 10)
        painter.drawLine(8, 10, 10, 6)
        painter.drawLine(22, 10, 20, 6)
        painter.drawLine(10, 6, 20, 6)
    elif kind == "pocket":
        painter.drawRect(6, 8, 16, 12)
        painter.drawLine(10, 12, 18, 12)
    elif kind == "revolve":
        painter.drawEllipse(6, 6, 16, 16)
        painter.drawLine(14, 6, 14, 22)
    elif kind == "sketch":
        painter.drawLine(6, 20, 22, 8)
        painter.drawEllipse(18, 5, 6, 6)
    else:
        painter.drawRect(7, 7, 14, 14)
    painter.end()
    return QIcon(pixmap)


def _tree(dark_text: bool) -> QTreeWidget:
    tree = QTreeWidget()
    tree.setHeaderHidden(True)
    tree.setIndentation(16)
    root = QTreeWidgetItem(["Bracket"])
    body = QTreeWidgetItem(["Body"])
    body.addChild(QTreeWidgetItem(["Origin"]))
    body.addChild(QTreeWidgetItem(["Sketch"]))
    body.addChild(QTreeWidgetItem(["Pad"]))
    body.addChild(QTreeWidgetItem(["Pocket"]))
    root.addChild(body)
    root.addChild(QTreeWidgetItem(["Assembly"]))
    tree.addTopLevelItem(root)
    tree.expandAll()
    tree.setMinimumWidth(230)
    if dark_text:
        tree.setStyleSheet("")
    return tree


def _properties() -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)
    for label in ("Pad", "Length   20 mm", "Reversed   no", "Midplane   no", "Type   Dimension"):
        layout.addWidget(QLabel(label))
    layout.addStretch(1)
    panel.setMinimumWidth(220)
    return panel


def _build(
    title: str,
    colors: dict,
    stylesheet: str,
    dark_chrome: bool,
    status_text: str,
    card: str = "",
) -> QMainWindow:
    window = QMainWindow()
    window.setWindowTitle(title)
    window.resize(1400, 860)
    window.setStyleSheet(stylesheet)

    menu = window.menuBar()
    for name in ("File", "Edit", "View", "Tools"):
        menu.addMenu(name)

    tabs = QTabBar()
    for name in ("Part Design", "Assembly", "Sketcher", "Part", "TechDraw"):
        tabs.addTab(name)
    tabs.setCurrentIndex(0)
    tabs.setDrawBase(False)
    tab_bar = QToolBar("Workbench")
    tab_bar.setMovable(False)
    tab_bar.addWidget(tabs)
    window.addToolBar(Qt.ToolBarArea.TopToolBarArea, tab_bar)
    window.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)

    bar = QToolBar("Part Design Modeling Features")
    bar.setMovable(False)
    icon_color = QColor("#F5F5F7") if dark_chrome else QColor("#1D1D1F")
    for kind, label in (("sketch", "Sketch"), ("pad", "Pad"), ("pocket", "Pocket"), ("revolve", "Revolve")):
        button = QToolButton()
        button.setIcon(QIcon(_icon(kind, icon_color)))
        button.setToolTip(label)
        button.setText(label)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        bar.addWidget(button)
    window.addToolBar(bar)

    model = QDockWidget("Model")
    model.setWidget(_tree(dark_chrome))
    window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, model)

    props = QDockWidget("Property")
    panel = _properties()
    # The sheet leaves QWidget unstyled on purpose. The mock property card
    # uses the same fill as the model tree so the dock reads as a panel.
    if card:
        panel.setStyleSheet(f"background-color: {card};")
    props.setWidget(panel)
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, props)

    window.setCentralWidget(Viewport(colors))

    status = QStatusBar()
    status.showMessage(status_text)
    window.setStatusBar(status)
    return window


def _save(window: QMainWindow, path: str) -> None:
    window.show()
    QApplication.processEvents()
    pixmap = window.grab()
    if pixmap.isNull() or pixmap.width() < 100:
        raise RuntimeError(f"empty grab for {path}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not pixmap.save(path):
        raise RuntimeError(f"failed to save {path}")
    print(f"wrote {path} ({pixmap.width()}x{pixmap.height()})")


def main() -> None:
    outdir = sys.argv[1] if len(sys.argv) > 1 else "/opt/cursor/artifacts/screenshots"
    app = QApplication([])
    light_qss, light_tokens = _theme("light")
    dark_qss, dark_tokens = _theme("dark")
    shots = (
        ("before-stock.png", "FreeCAD", STOCK_COLORS, STOCK_QSS, False, "Ready", ""),
        (
            "after-bruceworx-light.png",
            "FreeCAD BruceWorx",
            _colors("light"),
            light_qss,
            False,
            "Standard (mm, kg, s)    Revit navigation    Part Design",
            light_tokens["GeneralAlternateBackgroundColor"],
        ),
        (
            "after-bruceworx-dark.png",
            "FreeCAD BruceWorx Dark",
            _colors("dark"),
            dark_qss,
            True,
            "Standard (mm, kg, s)    Revit navigation    Part Design",
            dark_tokens["GeneralAlternateBackgroundColor"],
        ),
    )
    for filename, title, colors, stylesheet, dark, status_text, card in shots:
        window = _build(title, colors, stylesheet, dark, status_text, card)
        _save(window, os.path.join(outdir, filename))
        window.close()
    app.processEvents()


if __name__ == "__main__":
    main()
