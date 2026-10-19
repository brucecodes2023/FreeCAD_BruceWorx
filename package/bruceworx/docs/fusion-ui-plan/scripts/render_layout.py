"""Offscreen mock of the proposed Fusion-style BruceWorx layout.

    QT_QPA_PLATFORM=offscreen python render_layout.py <repo_root>

Not a FreeCAD process: QPainter with FreeCAD's own SVG icons.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

ROOT = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "..", "fig")

ICONS = {
    "sketch": "src/Mod/Sketcher/Gui/Resources/icons/general/Sketcher_NewSketch.svg",
    "pad": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Pad.svg",
    "pocket": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Pocket.svg",
    "revolve": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Revolution.svg",
    "loft": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_AdditiveLoft.svg",
    "sweep": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_AdditivePipe.svg",
    "hole": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Hole.svg",
    "rect": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_LinearPattern.svg",
    "circ": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_PolarPattern.svg",
    "mirror": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Mirrored.svg",
    "fillet": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Fillet.svg",
    "chamfer": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Chamfer.svg",
    "shell": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Thickness.svg",
    "draft": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Draft.svg",
    "combine": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Boolean.svg",
    "component": "src/Mod/Assembly/Gui/Resources/icons/Assembly_InsertLink.svg",
    "joint": "src/Mod/Assembly/Gui/Resources/icons/Assembly_CreateJointRevolute.svg",
    "rigid": "src/Mod/Assembly/Gui/Resources/icons/Assembly_CreateJointFixed.svg",
    "plane": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Plane.svg",
    "axis": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Line.svg",
    "point": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Point.svg",
    "measure": "src/Gui/Icons/umf-measurement.svg",
    "section": "src/Mod/Part/Gui/Resources/icons/Part_SectionCut.svg",
    "body": "src/Mod/PartDesign/Gui/Resources/icons/PartDesign_Body.svg",
    "new": "src/Gui/Icons/document-new.svg",
    "open": "src/Gui/Icons/document-open.svg",
    "save": "src/Gui/Icons/document-save.svg",
    "undo": "src/Gui/Icons/edit-undo.svg",
    "redo": "src/Gui/Icons/edit-redo.svg",
    "folder": "src/Gui/Icons/folder.svg",
    "iso": "src/Gui/Icons/view-isometric.svg",
    "fit": "src/Gui/Icons/zoom-all.svg",
    "group": "src/Gui/Icons/Geofeaturegroup.svg",
}
_svg = {}


def icon(p, key, x, y, s):
    if key not in _svg:
        _svg[key] = QSvgRenderer(os.path.join(ROOT, ICONS[key]))
    _svg[key].render(p, QRectF(x, y, s, s))


# Tokens (light BruceWorx).
BG = QColor("#f3f4f6")
CHROME = QColor("#e9ebef")
CHROME2 = QColor("#dfe2e7")
LINE = QColor("#c9cdd4")
TEXT = QColor("#22262d")
MUTED = QColor("#6b7280")
ACCENT = QColor("#1f6feb")
ORANGE = QColor("#e5782f")
DARK = QColor("#2b2f36")


def font(px, bold=False, mono=False):
    f = QFont("Menlo" if mono else "Helvetica Neue")
    f.setPixelSize(px)
    f.setBold(bold)
    return f


def text(p, x, y, s, px=12, col=TEXT, bold=False, mono=False, align=Qt.AlignLeft | Qt.AlignVCenter, w=400, h=None):
    p.setFont(font(px, bold, mono))
    p.setPen(col)
    p.drawText(QRectF(x, y, w, h or px * 1.6), align, s)


def rrect(p, r, rad, fill, stroke=None, sw=1.0):
    path = QPainterPath()
    path.addRoundedRect(r, rad, rad)
    p.fillPath(path, QBrush(fill))
    if stroke is not None:
        p.setPen(QPen(stroke, sw))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)


def chevron(p, x, y, col=MUTED, s=4):
    p.setPen(QPen(col, 1.4))
    p.drawLine(QPointF(x - s, y - s / 2), QPointF(x, y + s / 2))
    p.drawLine(QPointF(x, y + s / 2), QPointF(x + s, y - s / 2))


W, H = 1600, 1000


def titlebar(p):
    p.fillRect(QRectF(0, 0, W, 40), CHROME)
    for i, c in enumerate(("#ff5f57", "#febc2e", "#28c840")):
        p.setBrush(QColor(c))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(18 + 20 * i, 20), 6, 6)
    rrect(p, QRectF(76, 9, 22, 22), 5, ACCENT)
    text(p, 76, 9, "F", 13, QColor("white"), True, align=Qt.AlignCenter, w=22, h=22)
    x = 108
    for k in ("new", "open", "save", "undo", "redo"):
        icon(p, k, x, 11, 18)
        x += 28
    # Document tabs at the top (moved from the bottom of the MDI area).
    x = 270
    for label, active in (("Flange v3", True), ("FEMExample", False)):
        w = 150
        r = QRectF(x, 6, w, 34)
        if active:
            rrect(p, r.adjusted(0, 0, 0, 8), 8, BG, LINE)
            p.fillRect(QRectF(x + 1, 34, w - 2, 8), BG)
        icon(p, "body", x + 10, 15, 16)
        text(p, x + 32, 6, label, 12, TEXT if active else MUTED, active, h=34)
        text(p, x + w - 22, 6, "×", 13, MUTED, h=34)
        x += w + 4
    text(p, x + 4, 6, "+", 16, MUTED, h=34)
    rrect(p, QRectF(W - 330, 8, 230, 24), 12, QColor("white"), LINE)
    text(p, W - 314, 8, "Search tools, prefs & tree   ⌘K", 12, MUTED, h=24)
    text(p, W - 88, 8, "?   ⚙", 15, MUTED, h=24)


def workspace_row(p):
    y = 40
    p.fillRect(QRectF(0, y, W, 34), BG)
    rrect(p, QRectF(12, y + 5, 150, 24), 5, QColor("white"), LINE)
    text(p, 22, y + 5, "DESIGN", 12, TEXT, True, h=24)
    chevron(p, 148, y + 17)
    x = 184
    for i, t in enumerate(("SOLID", "SURFACE", "MESH", "SHEET METAL", "UTILITIES")):
        w = 14 + 8.2 * len(t)
        text(p, x, y + 4, t, 12, ACCENT if i == 0 else MUTED, i == 0, h=26, w=w, align=Qt.AlignCenter)
        if i == 0:
            p.fillRect(QRectF(x + 4, y + 30, w - 8, 3), ACCENT)
        x += w + 10
    p.setPen(QPen(LINE, 1))
    p.drawLine(0, y + 33, W, y + 33)


GROUPS = [
    ("CREATE", ["sketch", "pad", "pocket", "revolve", "loft", "sweep", "hole", "rect", "circ", "mirror"]),
    ("MODIFY", ["fillet", "chamfer", "shell", "draft", "combine"]),
    ("ASSEMBLE", ["component", "joint", "rigid"]),
    ("CONSTRUCT", ["plane", "axis", "point"]),
    ("INSPECT", ["measure", "section"]),
]


def toolbar(p, hi=("rect", "circ")):
    y = 74
    p.fillRect(QRectF(0, y, W, 66), BG)
    x = 14
    for name, keys in GROUPS:
        gx = x
        for k in keys:
            if k in hi:
                rrect(p, QRectF(x - 3, y + 5, 34, 34), 6, QColor(31, 111, 235, 40), ACCENT, 1.4)
            icon(p, k, x + 2, y + 9, 26)
            x += 36
        gw = x - gx
        text(p, gx, y + 42, name, 10, MUTED, True, w=gw - 6, align=Qt.AlignCenter, h=16)
        chevron(p, gx + gw / 2 + 4.2 * len(name) + 2, y + 51, MUTED, 3)
        x += 10
        p.setPen(QPen(LINE, 1))
        p.drawLine(QPointF(x - 6, y + 8), QPointF(x - 6, y + 58))
        x += 6
    p.drawLine(0, y + 66, W, y + 66)


def viewport(p, render_png):
    r = QRectF(0, 140, W, 690)
    g = QLinearGradient(0, r.top(), 0, r.bottom())
    g.setColorAt(0, QColor("#f7f8fb"))
    g.setColorAt(1, QColor("#dfe3ea"))
    p.fillRect(r, g)
    img = QImage(render_png)
    if not img.isNull():
        # Key the render's flat background out so it sits on the gradient.
        img = img.convertToFormat(QImage.Format_ARGB32)
        bgc = img.pixelColor(2, 2)
        for yy in range(img.height()):
            for xx in range(img.width()):
                c = img.pixelColor(xx, yy)
                if abs(c.red() - bgc.red()) + abs(c.green() - bgc.green()) + abs(c.blue() - bgc.blue()) < 6:
                    img.setPixelColor(xx, yy, QColor(0, 0, 0, 0))
        tw = 860
        th = tw * img.height() / img.width()
        p.drawImage(QRectF(W / 2 - tw / 2 - 40, r.top() + (r.height() - th) / 2, tw, th), img)
    # NaviCube placeholder.
    cx, cy = W - 110, r.top() + 80
    rrect(p, QRectF(cx - 42, cy - 42, 84, 84), 10, QColor(255, 255, 255, 200), LINE)
    text(p, cx - 42, cy - 42, "TOP\nFRONT · RIGHT", 10, MUTED, True, align=Qt.AlignCenter, w=84, h=84)
    # Bottom-centre navigation pill (Fusion's nav bar).
    pw = 250
    rrect(p, QRectF(W / 2 - pw / 2, r.bottom() - 46, pw, 34), 17, QColor(255, 255, 255, 230), LINE)
    x = W / 2 - pw / 2 + 18
    for k in ("iso", "fit", "section", "measure", "group"):
        icon(p, k, x, r.bottom() - 40, 22)
        x += 46


def browser(p):
    r = QRectF(12, 152, 260, 318)
    rrect(p, r, 8, QColor(255, 255, 255, 228), LINE)
    rrect(p, QRectF(r.left(), r.top(), r.width(), 30), 8, QColor(233, 235, 239, 240))
    p.fillRect(QRectF(r.left(), r.top() + 20, r.width(), 10), QColor(233, 235, 239, 240))
    text(p, r.left() + 12, r.top() + 2, "BROWSER", 11, MUTED, True, h=26)
    text(p, r.right() - 46, r.top() + 2, "–  ⧉", 12, MUTED, h=26)
    rows = [
        (0, "▾", "body", "Flange v3", True),
        (1, "▸", "folder", "Document Settings", False),
        (1, "▸", "folder", "Named Views", False),
        (1, "▸", "plane", "Origin", False),
        (1, "▾", "folder", "Bodies", False),
        (2, " ", "body", "Flange", False),
        (1, "▸", "sketch", "Sketches", False),
        (1, "▾", "folder", "Patterns", False),
        (2, " ", "circ", "Circular Pattern1", False),
        (2, " ", "component", "Bolt × 8  (linked)", False),
    ]
    y = r.top() + 36
    for lvl, tw, ic, label, bold in rows:
        x = r.left() + 10 + 16 * lvl
        text(p, x, y, tw, 11, MUTED, h=26)
        icon(p, ic, x + 14, y + 5, 16)
        text(p, x + 36, y, label, 12, TEXT, bold, h=26)
        y += 27


def dialog(p, x, y):
    w, h = 330, 358
    r = QRectF(x, y, w, h)
    sh = QRectF(x + 3, y + 5, w, h)
    rrect(p, sh, 10, QColor(0, 0, 0, 30))
    rrect(p, r, 10, QColor("white"), LINE)
    rrect(p, QRectF(x, y, w, 36), 10, DARK)
    p.fillRect(QRectF(x, y + 26, w, 10), DARK)
    icon(p, "circ", x + 12, y + 8, 20)
    text(p, x + 40, y, "CIRCULAR PATTERN", 12, QColor("white"), True, h=36)
    text(p, x + w - 30, y, "×", 15, QColor("#c9ccd2"), h=36)
    rows = [
        ("Pattern Type", "combo", "Components"),
        ("Objects", "chip", "Bolt  ×"),
        ("Axis", "chip", "Flange · Z axis  ×"),
        ("Type", "combo", "Full"),
        ("Quantity", "spin", "8"),
        ("Copies", "combo", "Linked (App::Link array)"),
        ("Suppress", "check", "Pick instances in view"),
    ]
    yy = y + 48
    for label, kind, val in rows:
        text(p, x + 14, yy, label, 12, MUTED, h=28, w=100)
        fr = QRectF(x + 116, yy + 2, w - 130, 24)
        if kind == "chip":
            rrect(p, fr, 4, QColor("#eef4ff"), QColor("#b7cff9"))
            text(p, fr.left() + 8, fr.top(), val, 12, ACCENT, h=24, w=fr.width() - 10)
        elif kind == "check":
            rrect(p, QRectF(fr.left(), fr.top() + 5, 14, 14), 3, QColor("white"), LINE)
            text(p, fr.left() + 22, fr.top(), val, 12, TEXT, h=24)
        else:
            rrect(p, fr, 4, QColor("white"), LINE)
            text(p, fr.left() + 8, fr.top(), val, 12, TEXT, h=24, w=fr.width() - 30)
            if kind == "combo":
                chevron(p, fr.right() - 12, fr.center().y(), MUTED, 3.5)
            else:
                text(p, fr.right() - 22, fr.top(), "⇕", 12, MUTED, h=24)
        yy += 34
    text(p, x + 14, yy, "ⓘ  Linked copies follow the source part.", 11, MUTED, h=24, w=w - 20)
    yy += 32
    rrect(p, QRectF(x + w - 172, yy, 74, 28), 5, ACCENT)
    text(p, x + w - 172, yy, "OK", 12, QColor("white"), True, align=Qt.AlignCenter, w=74, h=28)
    rrect(p, QRectF(x + w - 88, yy, 74, 28), 5, QColor("white"), LINE)
    text(p, x + w - 88, yy, "Cancel", 12, TEXT, align=Qt.AlignCenter, w=74, h=28)
    return r


def timeline(p, y):
    p.fillRect(QRectF(0, y, W, 40), QColor("#2f3237"))
    x = 14
    for g in ("⏮", "◀", "▶", "⏭"):
        text(p, x, y + 6, g, 13, QColor("#c9ccd2"), h=28, w=20, align=Qt.AlignCenter)
        x += 24
    x += 16
    feats = ["sketch", "pad", "pad", "pocket", "sketch", "hole", "circ", "fillet", "chamfer", "component", "circ"]
    for i, k in enumerate(feats):
        if i == 9:
            p.fillRect(QRectF(x - 5, y + 6, 4, 28), QColor("#f2c94c"))
            x += 6
        rrect(p, QRectF(x, y + 7, 26, 26), 4, QColor("#3d4148") if i < 9 else QColor("#34373c"))
        p.setOpacity(1.0 if i < 9 else 0.42)
        icon(p, k, x + 3, y + 10, 20)
        p.setOpacity(1.0)
        x += 30
    text(p, W - 220, y + 6, "History · Flange", 12, QColor("#9aa0aa"), h=28, w=200, align=Qt.AlignRight | Qt.AlignVCenter)


def cmdline(p, y, popup=True):
    p.fillRect(QRectF(0, y, W, 34), CHROME)
    p.setPen(QPen(LINE, 1))
    p.drawLine(0, y, W, y)
    rrect(p, QRectF(10, y + 5, 66, 24), 5, DARK)
    text(p, 10, y + 5, "ALIAS ▾", 11, QColor("white"), True, align=Qt.AlignCenter, w=66, h=24)
    rrect(p, QRectF(84, y + 5, 820, 24), 5, QColor("white"), LINE)
    text(p, 94, y + 5, "› CPAT", 13, TEXT, mono=True, h=24)
    p.fillRect(QRectF(150, y + 10, 1.5, 14), TEXT)
    text(p, 160, y + 5, "Select objects to pattern, or [Type/Axis/Quantity]:", 12, MUTED, h=24, w=600)
    text(p, W - 520, y + 5, "mm · kg · s     Revit nav     17.07 × 88.26 mm     ⚠ 0", 12, MUTED, h=24, w=500,
         align=Qt.AlignRight | Qt.AlignVCenter)
    if popup:
        r = QRectF(84, y - 132, 420, 128)
        rrect(p, r, 6, QColor("white"), LINE)
        items = [
            ("CPATTERN", "Circular Pattern", "circ", True),
            ("CP", "alias → CPATTERN", "circ", False),
            ("CPAD", "no match · did you mean PAD?", "pad", False),
            ("Gui.runCommand('PartDesign_PolarPattern')", "Python", "circ", False),
        ]
        yy = r.top() + 6
        for a, b, ic, sel in items:
            if sel:
                rrect(p, QRectF(r.left() + 4, yy, r.width() - 8, 28), 4, QColor("#e8f0fe"))
            icon(p, ic, r.left() + 12, yy + 5, 18)
            text(p, r.left() + 38, yy, a, 12, TEXT, sel, mono=True, h=28, w=210)
            text(p, r.left() + 250, yy, b, 11, MUTED, h=28, w=165)
            yy += 30


def main_mock():
    img = QImage(W * 2, H * 2, QImage.Format_ARGB32)
    img.setDevicePixelRatio(2)
    img.fill(BG)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    titlebar(p)
    workspace_row(p)
    toolbar(p)
    viewport(p, os.path.join(FIG, "component_pattern.png"))
    browser(p)
    dialog(p, W - 360, 290)
    cmdline(p, 830)
    timeline(p, 864)
    p.fillRect(QRectF(0, 904, W, 96), BG)
    p.end()
    img = img.copy(0, 0, W * 2, 904 * 2)
    img.save(os.path.join(FIG, "layout_proposed.png"))


def callout_crops():
    """Close-ups: dialog, command line, toolbar."""
    for name, size, draw in (
        ("dialog_circ", (360, 385), lambda p: dialog(p, 14, 12)),
        ("cmdline", (1000, 180), lambda p: (p.fillRect(QRectF(0, 0, 1000, 180), QColor("#e6e9ee")), cmdline(p, 140))),
        ("toolbar", (1010, 72), lambda p: (p.translate(0, -74), toolbar(p))),
        ("workspace", (760, 34), lambda p: (p.translate(0, -40), workspace_row(p))),
    ):
        img = QImage(size[0] * 2, size[1] * 2, QImage.Format_ARGB32)
        img.setDevicePixelRatio(2)
        img.fill(BG)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        draw(p)
        p.end()
        img.save(os.path.join(FIG, name + ".png"))


app = QApplication(sys.argv[:1])
main_mock()
callout_crops()
print("ok")
