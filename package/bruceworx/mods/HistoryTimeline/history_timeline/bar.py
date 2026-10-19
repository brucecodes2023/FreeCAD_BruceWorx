# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bottom history bar. Draws glyphs itself so the mock does not need FreeCAD icons.

Entries are duck-typed: ``name``, ``label``, ``kind``, ``is_tip``, ``after_tip``,
``suppressed``, and optional ``icon`` (QIcon). ``type_id`` and ``base_name`` are
optional tooltip fields.
"""

from history_timeline.qtcompat import load_qt, qt_enum

QtCore, QtGui, QtWidgets = load_qt()

_BG = "#323232"
_SLASH = "#ff5d5d"

# One row of 28 px icon chips, as in the roadmap §13.3 mock.
RIBBON_HEIGHT = 36
CHIP_WIDTH = 28
CHIP_ICON = 20


def _palette_colors(widget):
    """Chip colours from the widget's palette, so the bar follows the theme.

    The BruceWorx stylesheet sets them on the chips (``[historyChip="true"]``):
    ``background-color`` is the chip, ``alternate-background-color`` its border, ``selection-background-color``
    the tip chip and ``selection-color`` the accent (tip border and marker).
    Without that sheet the platform palette gives a plain light bar.
    """
    pal = widget.palette()

    def role(name):
        return pal.color(qt_enum(QtGui.QPalette, ("ColorRole", name), (name,)))

    return {
        "fill": role("Window"),
        "border": role("AlternateBase"),
        "tip_fill": role("Highlight"),
        "accent": role("HighlightedText"),
    }


def _align_center():
    return qt_enum(QtCore.Qt, ("AlignmentFlag", "AlignCenter"), ("AlignCenter",))


def _align_vcenter():
    return qt_enum(QtCore.Qt, ("AlignmentFlag", "AlignVCenter"), ("AlignVCenter",))


def _align_left():
    return qt_enum(QtCore.Qt, ("AlignmentFlag", "AlignLeft"), ("AlignLeft",))


def _pointing_hand():
    return qt_enum(QtCore.Qt, ("CursorShape", "PointingHandCursor"), ("PointingHandCursor",))


def _antialias():
    return qt_enum(QtGui.QPainter, ("RenderHint", "Antialiasing"), ("Antialiasing",))


def _no_pen():
    style = qt_enum(QtCore.Qt, ("PenStyle", "NoPen"), ("NoPen",))
    return QtGui.QPen(style)


def _scroll_off():
    return qt_enum(
        QtCore.Qt, ("ScrollBarPolicy", "ScrollBarAlwaysOff"), ("ScrollBarAlwaysOff",)
    )


def _scroll_as_needed():
    return qt_enum(
        QtCore.Qt, ("ScrollBarPolicy", "ScrollBarAsNeeded"), ("ScrollBarAsNeeded",)
    )


def _styled_bg():
    return qt_enum(
        QtCore.Qt, ("WidgetAttribute", "WA_StyledBackground"), ("WA_StyledBackground",)
    )


def glyph(kind: str, size: int = 32) -> QtGui.QPixmap:
    """Small geometric stand-in for a PartDesign command icon."""
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(QtGui.QColor(0, 0, 0, 0))
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(_antialias(), True)
    pen = QtGui.QPen(QtGui.QColor("#f4f4f4"))
    pen.setWidthF(1.6)
    painter.setPen(pen)
    inset = 4
    rect = QtCore.QRectF(inset, inset, size - 2 * inset, size - 2 * inset)
    no_brush = qt_enum(QtCore.Qt, ("BrushStyle", "NoBrush"), ("NoBrush",))

    if kind == "sketch":
        painter.setBrush(QtGui.QColor("#5dade2"))
        painter.drawRoundedRect(rect.adjusted(2, 4, -2, -6), 2, 2)
        painter.drawLine(QtCore.QLineF(8, size - 8, size - 8, 10))
    elif kind == "datum":
        painter.setBrush(no_brush)
        pen.setStyle(qt_enum(QtCore.Qt, ("PenStyle", "DashLine"), ("DashLine",)))
        pen.setColor(QtGui.QColor("#f5c16c"))
        painter.setPen(pen)
        painter.drawRect(rect)
    elif kind == "pad":
        painter.setBrush(QtGui.QColor("#f6d365"))
        painter.drawRect(rect.adjusted(2, 8, -6, -2))
        painter.drawPolygon(
            [
                QtCore.QPointF(rect.left() + 2, rect.top() + 8),
                QtCore.QPointF(rect.left() + 8, rect.top() + 2),
                QtCore.QPointF(rect.right() - 0, rect.top() + 2),
                QtCore.QPointF(rect.right() - 6, rect.top() + 8),
            ]
        )
    elif kind == "pocket":
        painter.setBrush(QtGui.QColor("#7dcea0"))
        painter.drawRect(rect.adjusted(1, 6, -1, -2))
        painter.setBrush(QtGui.QColor(_BG))
        painter.drawEllipse(rect.adjusted(8, 10, -8, -6))
    elif kind == "fillet":
        painter.setBrush(QtGui.QColor("#f0b27a"))
        path = QtGui.QPainterPath()
        path.moveTo(rect.left(), rect.bottom())
        path.lineTo(rect.left(), rect.top() + 10)
        path.quadTo(rect.left(), rect.top(), rect.left() + 10, rect.top())
        path.lineTo(rect.right(), rect.top())
        path.lineTo(rect.right(), rect.bottom())
        path.closeSubpath()
        painter.drawPath(path)
    elif kind == "chamfer":
        painter.setBrush(QtGui.QColor("#d7bde2"))
        path = QtGui.QPainterPath()
        path.moveTo(rect.left(), rect.bottom())
        path.lineTo(rect.left(), rect.top() + 12)
        path.lineTo(rect.left() + 12, rect.top())
        path.lineTo(rect.right(), rect.top())
        path.lineTo(rect.right(), rect.bottom())
        path.closeSubpath()
        painter.drawPath(path)
    elif kind == "cylinder":
        painter.setBrush(QtGui.QColor("#85c1e9"))
        painter.drawRoundedRect(rect.adjusted(6, 4, -6, -4), 8, 8)
    elif kind == "sphere":
        painter.setBrush(QtGui.QColor("#f1948a"))
        painter.drawEllipse(rect.adjusted(2, 2, -2, -2))
    elif kind == "box":
        painter.setBrush(QtGui.QColor("#f7dc6f"))
        painter.drawRect(rect.adjusted(3, 6, -3, -3))
    elif kind == "vars":
        painter.setBrush(QtGui.QColor("#aed6f1"))
        painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 3, 3)
        painter.setPen(QtGui.QPen(QtGui.QColor("#1a1a1a")))
        painter.drawText(rect, _align_center(), "x")
    else:
        painter.setBrush(QtGui.QColor("#d5d8dc"))
        painter.drawEllipse(rect.adjusted(3, 3, -3, -3))

    painter.end()
    return pixmap


class FeatureButton(QtWidgets.QWidget):
    """One feature cell. Click, double-click, and context menu are separate signals."""

    clicked = QtCore.Signal()
    doubleClicked = QtCore.Signal()
    contextMenu = QtCore.Signal(object)

    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.setObjectName(f"HistoryTimeline_{entry.name}")
        self.setProperty("historyChip", True)
        self.setFixedSize(CHIP_WIDTH, RIBBON_HEIGHT - 10)
        self.setCursor(_pointing_hand())
        self.setMouseTracking(True)
        self._suppress_release = False
        type_id = getattr(entry, "type_id", entry.kind)
        base = getattr(entry, "base_name", None)
        state = []
        if entry.is_tip:
            state.append("tip")
        if entry.after_tip:
            state.append("after tip")
        if entry.suppressed:
            state.append("suppressed")
        state_text = ", ".join(state) if state else "in history"
        self.setToolTip(
            f"{entry.label}\n{type_id}\nbase: {base or '—'}\n{state_text}"
        )
        icon = getattr(entry, "icon", None)
        if icon is not None:
            self._pixmap = icon.pixmap(QtCore.QSize(CHIP_ICON, CHIP_ICON))
        else:
            self._pixmap = glyph(entry.kind, CHIP_ICON)

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(_antialias(), True)
        if self.entry.after_tip:
            painter.setOpacity(0.42)
        colors = _palette_colors(self)
        if self.entry.is_tip:
            painter.setPen(QtGui.QPen(colors["accent"], 1))
            painter.setBrush(colors["tip_fill"])
        else:
            painter.setPen(QtGui.QPen(colors["border"], 1))
            painter.setBrush(colors["fill"])
        painter.drawRoundedRect(QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 5, 5)
        size = self._pixmap.deviceIndependentSize().toSize() if hasattr(
            self._pixmap, "deviceIndependentSize") else self._pixmap.size()
        painter.drawPixmap(
            (self.width() - size.width()) // 2, (self.height() - size.height()) // 2, self._pixmap
        )
        if self.entry.suppressed:
            painter.setOpacity(1.0)
            painter.setPen(QtGui.QPen(QtGui.QColor(_SLASH), 2))
            painter.drawLine(8, self.height() - 6, self.width() - 8, 6)
        painter.end()

    def mouseReleaseEvent(self, event):
        left = qt_enum(QtCore.Qt, ("MouseButton", "LeftButton"), ("LeftButton",))
        if self._suppress_release:
            self._suppress_release = False
            event.accept()
            return
        if event.button() == left:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        left = qt_enum(QtCore.Qt, ("MouseButton", "LeftButton"), ("LeftButton",))
        if event.button() == left:
            # The second release of a double-click would otherwise roll the tip.
            self._suppress_release = True
            self.doubleClicked.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        self.contextMenu.emit(event.globalPos())
        event.accept()


class MarkerWidget(QtWidgets.QWidget):
    """Rollback marker. It sits after the tip feature (or at the front if the tip is unset)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HistoryTimelineMarker")
        self.setProperty("historyChip", True)
        self.setFixedWidth(8)
        self.setToolTip(
            "History marker. Sits after Body.Tip. "
            "Features to the right stay in the model and still recompute."
        )

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(_antialias(), True)
        accent = _palette_colors(self)["accent"]
        painter.setPen(_no_pen())
        painter.setBrush(accent)
        x = self.width() // 2
        painter.drawRoundedRect(QtCore.QRectF(x - 1.5, 5, 3, self.height() - 10), 1.5, 1.5)
        painter.end()


class TimelineBar(QtWidgets.QWidget):
    """Horizontal feature row plus the rollback marker.

    ``tipRequested`` / ``editRequested`` carry the feature's internal name.
    A single click waits briefly so a double-click does not also roll the tip.
    """

    tipRequested = QtCore.Signal(str)
    editRequested = QtCore.Signal(str)
    contextMenuRequested = QtCore.Signal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HistoryTimelineBar")
        self.setAttribute(_styled_bg(), True)
        self.setFixedHeight(RIBBON_HEIGHT)
        self.setToolTip("Click rolls the tip · double-click edits · right-click to suppress")

        self._title = QtWidgets.QLabel("History")
        self._title.setObjectName("HistoryTimelineTitle")
        self._hint = QtWidgets.QLabel(
            "Spike · click rolls the tip · double-click edits · right-click to suppress"
        )
        self._hint.setObjectName("HistoryTimelineHint")
        self._hint.hide()

        self._row = QtWidgets.QHBoxLayout()
        self._row.setContentsMargins(4, 0, 4, 0)
        self._row.setSpacing(4)
        row_host = QtWidgets.QWidget()
        row_host.setObjectName("HistoryTimelineRow")
        row_host.setLayout(self._row)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(qt_enum(QtWidgets.QFrame, ("Shape", "NoFrame"), ("NoFrame",)))
        scroll.setHorizontalScrollBarPolicy(_scroll_as_needed())
        scroll.setVerticalScrollBarPolicy(_scroll_off())
        scroll.setWidget(row_host)
        scroll.setObjectName("HistoryTimelineScroll")

        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(8, 2, 4, 2)
        outer.setSpacing(6)
        outer.addWidget(self._title)
        outer.addWidget(scroll, 1)

        self._pending_name = None
        self._click_timer = QtCore.QTimer(self)
        self._click_timer.setSingleShot(True)
        self._click_timer.setInterval(220)
        self._click_timer.timeout.connect(self._emit_single_click)
        self._buttons = {}

    def set_timeline(self, body_label, entries, empty_message=None):
        self._click_timer.stop()
        self._pending_name = None
        self._buttons = {}
        while self._row.count():
            item = self._row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._title.setText(body_label or "History")

        if not entries:
            message = empty_message or "No feature history in this document."
            label = QtWidgets.QLabel(message)
            label.setObjectName("HistoryTimelineHint")
            self._row.addWidget(label)
            self._row.addStretch(1)
            return

        marker_placed = False
        # Tip cleared, or tip is the external base feature: marker before the row.
        if all(entry.after_tip for entry in entries):
            self._row.addWidget(MarkerWidget())
            marker_placed = True

        for entry in entries:
            button = FeatureButton(entry)
            button.clicked.connect(lambda name=entry.name: self._schedule_click(name))
            button.doubleClicked.connect(lambda name=entry.name: self._on_double(name))
            button.contextMenu.connect(
                lambda pos, name=entry.name: self.contextMenuRequested.emit(name, pos)
            )
            self._buttons[entry.name] = button
            self._row.addWidget(button)
            if entry.is_tip:
                self._row.addWidget(MarkerWidget())
                marker_placed = True

        if not marker_placed:
            # Tip object is missing from the row. Keep a marker at the end so
            # the bar does not look like history has no playhead.
            self._row.addWidget(MarkerWidget())
        self._row.addStretch(1)

    def button_widget(self, name):
        return self._buttons.get(name)

    def _schedule_click(self, name):
        self._pending_name = name
        self._click_timer.start()

    def _emit_single_click(self):
        name = self._pending_name
        self._pending_name = None
        if name:
            self.tipRequested.emit(name)

    def _on_double(self, name):
        self._click_timer.stop()
        self._pending_name = None
        self.editRequested.emit(name)
