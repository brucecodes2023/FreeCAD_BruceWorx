# SPDX-License-Identifier: LGPL-2.1-or-later
"""Render the prototype history bar offscreen for the design review.

Uses PySide6 (or FreeCAD's PySide shim). Does not start FreeCAD.

    QT_QPA_PLATFORM=offscreen python docs/mock/render_mock.py

Writes PNGs next to this file:

* timeline-bar.png — marker after the current tip, one suppressed feature past it
* timeline-rollback.png — tip rolled back to Pad
* timeline-context-menu.png — the spike's context menu on Pocket
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from history_timeline.bar import TimelineBar
from history_timeline.qtcompat import load_qt, qt_enum

QtCore, QtGui, QtWidgets = load_qt()

CAPTION = (
    "Offscreen render of the prototype bar (history_timeline.bar). "
    "Design mock for FCB-P1F-16 — not a FreeCAD session."
)


class Item:
    def __init__(
        self,
        name,
        label,
        kind,
        type_id,
        is_tip=False,
        after_tip=False,
        suppressed=False,
        base_name=None,
    ):
        self.name = name
        self.label = label
        self.kind = kind
        self.type_id = type_id
        self.is_tip = is_tip
        self.after_tip = after_tip
        self.suppressed = suppressed
        self.base_name = base_name
        self.icon = None


def _features(tip_name):
    spec = [
        ("Sketch", "Profile", "sketch", "Sketcher::SketchObject", None),
        ("Pad", "Pad", "pad", "PartDesign::Pad", None),
        ("Sketch001", "Hole sketch", "sketch", "Sketcher::SketchObject", "Pad"),
        ("Pocket", "Pocket", "pocket", "PartDesign::Pocket", "Pad"),
        ("Fillet", "Fillet", "fillet", "PartDesign::Fillet", "Pocket"),
        ("Chamfer", "Chamfer", "chamfer", "PartDesign::Chamfer", "Fillet"),
    ]
    names = [row[0] for row in spec]
    tip_index = names.index(tip_name)
    items = []
    for index, (name, label, kind, type_id, base) in enumerate(spec):
        items.append(
            Item(
                name,
                label,
                kind,
                type_id,
                is_tip=(name == tip_name),
                after_tip=index > tip_index,
                suppressed=(name == "Chamfer"),
                base_name=base,
            )
        )
    return items


def _show(widget, width, height):
    widget.resize(width, height)
    widget.show()
    QtWidgets.QApplication.processEvents()
    return widget.grab()


def _with_caption(pixmap, extra_note=None):
    lines = [CAPTION]
    if extra_note:
        lines.append(extra_note)
    footer_h = 18 * len(lines) + 14
    canvas = QtGui.QPixmap(pixmap.width(), pixmap.height() + footer_h)
    canvas.fill(QtGui.QColor("#141414"))
    painter = QtGui.QPainter(canvas)
    painter.drawPixmap(0, 0, pixmap)
    painter.setPen(QtGui.QColor("#ffffff"))
    font = painter.font()
    font.setPointSize(9)
    painter.setFont(font)
    align = qt_enum(QtCore.Qt, ("AlignmentFlag", "AlignLeft"), ("AlignLeft",))
    align = align | qt_enum(QtCore.Qt, ("AlignmentFlag", "AlignVCenter"), ("AlignVCenter",))
    painter.drawText(
        QtCore.QRect(12, pixmap.height(), pixmap.width() - 24, footer_h),
        align,
        "\n".join(lines),
    )
    painter.end()
    return canvas


def _fallback_menu():
    card = QtWidgets.QFrame()
    card.setObjectName("MockMenu")
    card.setStyleSheet(
        "QFrame#MockMenu { background: #f7f7f7; border: 1px solid #bdbdbd; }"
        "QLabel { color: #202020; padding: 4px 16px; }"
        "QLabel#disabled { color: #9a9a9a; }"
        "QLabel#rule { background: #d0d0d0; padding: 0; margin: 4px 8px; }"
    )
    layout = QtWidgets.QVBoxLayout(card)
    layout.setContentsMargins(1, 4, 1, 4)
    layout.setSpacing(0)
    for text, enabled in (
        ("Edit feature", True),
        ("Roll history to here", True),
        ("Suppress feature", True),
        (None, True),
        ("Move earlier", False),
        ("Move later", False),
    ):
        if text is None:
            rule = QtWidgets.QLabel("")
            rule.setObjectName("rule")
            rule.setFixedHeight(1)
            layout.addWidget(rule)
            continue
        label = QtWidgets.QLabel(text)
        if not enabled:
            label.setObjectName("disabled")
        layout.addWidget(label)
    card.setFixedWidth(230)
    card.adjustSize()
    return _show(card, 230, card.sizeHint().height())


def _save(name, pixmap):
    path = os.path.join(HERE, name)
    if not pixmap.save(path):
        raise RuntimeError(f"failed to save {path}")
    print(path, pixmap.width(), pixmap.height())


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    bar = TimelineBar()
    bar.set_timeline("Body", _features("Fillet"))
    current = _with_caption(_show(bar, 920, 118))
    _save("timeline-bar.png", current)

    bar.set_timeline("Body", _features("Pad"))
    rolled = _with_caption(
        _show(bar, 920, 118),
        "Marker rolled to Pad. Pocket, Fillet and Chamfer are past the tip and still in the model.",
    )
    _save("timeline-rollback.png", rolled)

    bar.set_timeline("Body", _features("Fillet"))
    bar_pix = _show(bar, 920, 118)
    # Drawn card, not a live popup: offscreen QMenu grabs drop the disabled
    # styling, and the spike's point is that reorder stays disabled.
    menu_pix = _fallback_menu()
    menu_note = (
        "Same actions as the prototype QMenu. "
        "Move earlier and Move later are disabled until reorder is safe."
    )

    pocket = bar.button_widget("Pocket")
    origin = pocket.mapTo(bar, QtCore.QPoint(8, pocket.height() - 10))
    width = max(bar_pix.width(), origin.x() + menu_pix.width() + 16)
    height = max(bar_pix.height(), origin.y() + menu_pix.height() + 8)
    composed = QtGui.QPixmap(width, height)
    composed.fill(QtGui.QColor("#323232"))
    painter = QtGui.QPainter(composed)
    painter.drawPixmap(0, 0, bar_pix)
    painter.drawPixmap(origin, menu_pix)
    painter.end()
    _save(
        "timeline-context-menu.png",
        _with_caption(composed, menu_note + " Move earlier/later stay disabled in this spike."),
    )
    return app


if __name__ == "__main__":
    main()
