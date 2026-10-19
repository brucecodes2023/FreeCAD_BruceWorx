# SPDX-License-Identifier: LGPL-2.1-or-later
"""Bottom history bar. Draws glyphs itself so the mock does not need FreeCAD icons.

Entries are duck-typed: ``name``, ``label``, ``kind``, ``is_tip``, ``after_tip``,
``suppressed``, and optional ``icon`` (QIcon). ``type_id`` and ``base_name`` are
optional tooltip fields.
"""

from history_timeline.qtcompat import load_qt, qt_enum

QtCore, QtGui, QtWidgets = load_qt()

_BG = "#323232"
_HEADER = "#e4e4e4"
_HINT = "#9a9a9a"
_BUTTON = "#3d3d3d"
_BUTTON_BORDER = "#555555"
_TIP = "#4da3ff"
_TIP_BG = "#2c4d6e"
_LABEL = "#f2f2f2"
_MARKER = "#f5c400"
_SLASH = "#ff5d5d"

# Previous bar reserved 112px and the dock stretched to match. One third of
# that still fits a single row of feature chips.
RIBBON_HEIGHT = 112 // 3


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
        self.setFixedSize(96, RIBBON_HEIGHT - 6)
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
            self._pixmap = icon.pixmap(QtCore.QSize(16, 16))
        else:
            self._pixmap = glyph(entry.kind, 16)

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(_antialias(), True)
        if self.entry.after_tip:
            painter.setOpacity(0.42)
        fill = QtGui.QColor(_TIP_BG if self.entry.is_tip else _BUTTON)
        border = QtGui.QColor(_TIP if self.entry.is_tip else _BUTTON_BORDER)
        painter.setPen(QtGui.QPen(border, 2 if self.entry.is_tip else 1))
        painter.setBrush(fill)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -2, -2), 4, 4)
        painter.drawPixmap(4, (self.height() - self._pixmap.height()) // 2, self._pixmap)
        painter.setPen(QtGui.QColor(_LABEL))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        label = self.entry.label
        if len(label) > 8:
            label = label[:7] + "…"
        align = _align_vcenter() | _align_left()
        painter.drawText(
            QtCore.QRect(22, 0, self.width() - 26, self.height()),
            align,
            label,
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
        self.setFixedWidth(16)
        self.setToolTip(
            "History marker. Sits after Body.Tip. "
            "Features to the right stay in the model and still recompute."
        )

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(_antialias(), True)
        x = self.width() // 2
        painter.setPen(QtGui.QPen(QtGui.QColor(_MARKER), 2))
        painter.drawLine(x, 16, x, self.height() - 8)
        painter.setPen(_no_pen())
        painter.setBrush(QtGui.QColor(_MARKER))
        path = QtGui.QPainterPath()
        path.moveTo(x - 6, 8)
        path.lineTo(x + 6, 8)
        path.lineTo(x, 16)
        path.closeSubpath()
        painter.drawPath(path)
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
        self.setStyleSheet(f"QWidget#HistoryTimelineBar {{ background: {_BG}; }}")
        self.setFixedHeight(RIBBON_HEIGHT)
        self.setToolTip("Click rolls the tip · double-click edits · right-click to suppress")

        self._title = QtWidgets.QLabel("History")
        self._title.setStyleSheet(f"color: {_HEADER}; font-weight: 600;")
        self._hint = QtWidgets.QLabel(
            "Spike · click rolls the tip · double-click edits · right-click to suppress"
        )
        self._hint.setStyleSheet(f"color: {_HINT};")
        self._hint.setObjectName("HistoryTimelineHint")
        self._hint.hide()

        self._row = QtWidgets.QHBoxLayout()
        self._row.setContentsMargins(4, 0, 4, 0)
        self._row.setSpacing(4)
        row_host = QtWidgets.QWidget()
        row_host.setLayout(self._row)
        row_host.setStyleSheet(f"background: {_BG};")

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(qt_enum(QtWidgets.QFrame, ("Shape", "NoFrame"), ("NoFrame",)))
        scroll.setHorizontalScrollBarPolicy(_scroll_as_needed())
        scroll.setVerticalScrollBarPolicy(_scroll_off())
        scroll.setWidget(row_host)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {_BG}; border: none; }}"
            f"QScrollBar:horizontal {{ height: 6px; background: {_BG}; }}"
        )

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

        if body_label:
            self._title.setText(f"History  ·  {body_label}")
        else:
            self._title.setText("History")

        if not entries:
            message = empty_message or "No PartDesign body in the active document."
            label = QtWidgets.QLabel(message)
            label.setStyleSheet(f"color: {_HINT}; padding: 0px 8px;")
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
