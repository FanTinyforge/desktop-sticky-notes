# -*- coding: utf-8 -*-
"""便利贴窗口：无描边、轻投影、胶带标题条、拖动 / 缩放 / 折叠 / 置顶。"""
import ctypes
import logging
import os
import re
from ctypes import wintypes

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QActionGroup,
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QTextCharFormat,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import theme

# Win32 句柄是 64 位，必须声明参数类型，否则 ctypes 按 32 位 int 传参会直接失败
_SetWindowPos = ctypes.windll.user32.SetWindowPos
_SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_uint,
]
_SetWindowPos.restype = wintypes.BOOL

HWND_TOPMOST = ctypes.c_void_p(-1)
HWND_NOTOPMOST = ctypes.c_void_p(-2)
HWND_BOTTOM = ctypes.c_void_p(1)
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010


def _lerp(a, b, t):
    return a + (b - a) * t


def _as_int(value, default, lo, hi):
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, number))


def _as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _as_color(value, default):
    if isinstance(value, str) and value.startswith("#") and QColor(value).isValid():
        return value
    return default


def _as_title(value, allow_empty=False):
    """标题只保留一行，最长 TITLE_MAX；缺省时回落到“待办事项”，但允许用户主动清空。"""
    if not isinstance(value, str):
        return theme.TITLE_DEFAULT
    text = value.replace("\r", " ").replace("\n", " ").strip()[: theme.TITLE_MAX]
    if not text and not allow_empty:
        return theme.TITLE_DEFAULT
    return text


def _as_opacity(value):
    """兼容 0.3~1.0 与 30~100 两种历史格式。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 1.0
    if number > 1.0:
        number /= 100.0
    return max(0.3, min(1.0, number))


_BODY_TAG_RE = re.compile(r"<body[^>]*>", re.I)


def _prepare_html(html):
    """载入存档 HTML 时去掉 body 上烘焙的默认字号，让全局字号仍然可控。"""
    return _BODY_TAG_RE.sub(
        '<body style="background-color:transparent;">', html, count=1
    )


class Grip(QWidget):
    """右下角缩放柄。"""

    def __init__(self, note):
        super().__init__(note.card)
        self.note = note
        self.setFixedSize(18, 18)
        self.setCursor(Qt.SizeFDiagCursor)
        self._start = None
        self._geo = None

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(0, 0, 0, 72), 1.0))
        w, h = self.width(), self.height()
        for d in (6, 10, 14):
            p.drawLine(w - d, h - 2, w - 2, h - d)
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start = event.globalPosition().toPoint()
            self._geo = self.note.geometry()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._start is None:
            return
        delta = event.globalPosition().toPoint() - self._start
        card_w = self._geo.width() - theme.MARGIN * 2 + delta.x()
        card_h = self._geo.height() - theme.MARGIN * 2 + delta.y()
        card_w = max(150, min(720, card_w))
        card_h = max(120, min(820, card_h))
        self.note.resize(card_w + theme.MARGIN * 2, card_h + theme.MARGIN * 2)

    def mouseReleaseEvent(self, event):
        if self._start is not None:
            self._start = None
            self.note.save_state()


class Card(QWidget):
    """纸张本体：纯色 + 右下折角，没有任何描边。"""

    def __init__(self, note):
        super().__init__(note)
        self.note = note
        self.setMouseTracking(True)

    def paintEvent(self, event):
        if self.note.collapsed:
            # 折叠后只剩胶带条，纸面完全不画
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, theme.RADIUS, theme.RADIUS)

        color = QColor(self.note.paper)
        color.setAlphaF(theme.PAPER_ALPHA)
        p.fillPath(path, color)

        # 右下角轻轻翘起的一点纸影
        w, h = self.width(), self.height()
        fold = QPainterPath()
        fold.moveTo(w - 16, h)
        fold.lineTo(w, h - 16)
        fold.lineTo(w, h)
        fold.closeSubpath()
        p.save()
        p.setClipPath(path)
        p.fillPath(fold, QColor(0, 0, 0, 12))
        p.restore()
        p.end()

    def mousePressEvent(self, event):
        self.note.select()
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.note.set_hover(True)

    def leaveEvent(self, event):
        self.note.set_hover(False)


class BodyEdit(QTextEdit):
    def __init__(self, note):
        super().__init__(note.card)
        self.note = note

    def focusInEvent(self, event):
        self.note.select()
        super().focusInEvent(event)

    def mousePressEvent(self, event):
        self.note.select()
        self.note.hide_confirm()
        super().mousePressEvent(event)

    def has_selection(self):
        return self.textCursor().hasSelection()

    def format_selection_size(self, size):
        """只改选中的字，返回 False 表示当前没有选区。"""
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return False
        font = QFont(self.font())
        font.setPixelSize(int(size))
        fmt = QTextCharFormat()
        fmt.setFont(font)
        cursor.mergeCharFormat(fmt)
        self.setTextCursor(cursor)
        return True

    def format_selection_color(self, color):
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return False
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.mergeCharFormat(fmt)
        self.setTextCursor(cursor)
        return True

    def selection_color(self, fallback):
        if not self.has_selection():
            return fallback
        color = self.textCursor().charFormat().foreground().color()
        return color.name() if color.isValid() else fallback


class TitleEdit(QLineEdit):
    """标题行内编辑器：回车 / 失焦保存，Esc 取消。"""

    cancelled = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class TitleBar(QWidget):
    """胶带条：深一档的颜色 + 细竖纹；拖动它移动整张纸，双击标题文字可改标题。"""

    def __init__(self, note):
        super().__init__(note.card)
        self.note = note
        self._drag = None
        self._press = None
        self._offset = None
        self._editing = False
        self._font_size = note.title_font_size
        self._font_color = note.title_color
        self.setFixedHeight(theme.title_height(self._font_size))
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("拖动移动便签；双击标题文字修改标题")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(3)
        lay.addStretch(1)

        self.buttons = []
        specs = [
            ("钉", "置顶（浮在所有窗口上）/ 再点回桌面层", self.note.toggle_pin),
            ("▲", "折叠 / 展开", self.note.toggle_collapse),
            ("✕", "删除", self.note.request_delete),
        ]
        for text, tip, slot in specs:
            b = QPushButton(text, self)
            b.setToolTip(tip)
            b.setFixedSize(19, 19)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(TitleBar.BTN_QSS)
            b.clicked.connect(slot)
            lay.addWidget(b)
            self.buttons.append(b)
        self.btn_pin, self.btn_fold, self.btn_del = self.buttons

        self.title_edit = TitleEdit(self)
        self.title_edit.setMaxLength(theme.TITLE_MAX)
        self.title_edit.setPlaceholderText(theme.TITLE_DEFAULT)
        self._style_edit()
        self.title_edit.hide()
        self.title_edit.editingFinished.connect(self._commit_title)
        self.title_edit.cancelled.connect(self._cancel_title)

        self.set_tools_visible(False)
        self.sync_state()

    BTN_QSS = (
        "QPushButton{background:rgba(255,255,255,115);border:0;border-radius:4px;"
        "color:#4A463C;font-size:10px;font-family:'Microsoft YaHei';}"
        "QPushButton:hover{background:rgba(255,255,255,224);}"
    )
    BTN_ON_QSS = (
        "QPushButton{background:rgba(74,58,40,205);border:0;border-radius:4px;"
        "color:#FFF6E4;font-size:10px;font-family:'Microsoft YaHei';}"
        "QPushButton:hover{background:rgba(74,58,40,232);}"
    )

    def sync_state(self):
        """钉按下去＝置顶状态；折叠后箭头朝下表示可展开。"""
        self.btn_pin.setStyleSheet(
            TitleBar.BTN_ON_QSS if self.note.pinned else TitleBar.BTN_QSS
        )
        self.btn_fold.setText("▼" if self.note.collapsed else "▲")

    def _style_edit(self):
        self.title_edit.setStyleSheet(
            "QLineEdit{background:rgba(255,255,255,195);border:0;border-radius:4px;"
            "padding:0 4px;color:%s;font-family:'Microsoft YaHei';font-size:%dpx;"
            "selection-background-color:#D98B52;selection-color:#FFFFFF;}"
            % (QColor(self._font_color).name(), self._font_size)
        )

    def apply_style(self, size, color):
        """标题字号 / 颜色单独生效，返回标题条高度变化量。"""
        old = self.height()
        self._font_size = max(10, min(28, int(size)))
        self._font_color = QColor(color).name()
        self.setFixedHeight(theme.title_height(self._font_size))
        self._style_edit()
        self.update()
        return self.height() - old

    def set_tools_visible(self, on):
        for b in self.buttons:
            b.setVisible(bool(on))

    def _edit_rect(self):
        # 给右侧三个按钮留出 84px，窄便签至少保留 42px 输入宽度
        width = max(42, self.width() - 16 - 84)
        return QRect(14, 3, width, self.height() - 6)

    def start_title_edit(self):
        if self._editing:
            return
        self._editing = True
        self._press = None
        self._drag = None
        self.setCursor(Qt.OpenHandCursor)
        self._style_edit()
        self.title_edit.setGeometry(self._edit_rect())
        self.title_edit.setText(self.note.title_text)
        self.title_edit.show()
        self.title_edit.raise_()
        self.title_edit.setFocus(Qt.MouseFocusReason)
        self.title_edit.selectAll()

    def _commit_title(self):
        if not self._editing:
            return
        self._editing = False
        text = self.title_edit.text()
        self.title_edit.hide()
        self.note.set_title_text(text)
        self.update()

    def _cancel_title(self):
        self._editing = False
        self.title_edit.hide()
        self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().x() < self.width() - 84:
            self.start_title_edit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def resizeEvent(self, event):
        if self._editing:
            self.title_edit.setGeometry(self._edit_rect())
        super().resizeEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        if self.note.collapsed:
            # 折叠态：整条四角都是圆的，不再往下接纸面
            path.addRoundedRect(QRectF(self.rect()), theme.RADIUS, theme.RADIUS)
        else:
            # 平铺态：只圆上面两角，下面与纸面齐平
            path.addRoundedRect(
                QRectF(0, -theme.RADIUS, self.width(), self.height() + theme.RADIUS),
                theme.RADIUS,
                theme.RADIUS,
            )
        p.fillPath(path, QColor(self.note.tape))

        p.setPen(QPen(QColor(255, 255, 255, 26), 1.0))
        x = 0
        while x < self.width():
            p.drawLine(x, 0, x, self.height())
            x += 6

        if not self._editing:
            title_color = QColor(self._font_color)
            title_font = QFont("Microsoft YaHei")
            title_font.setPixelSize(self._font_size)
            p.setFont(title_font)
            p.setPen(title_color)
            avail = max(0, self.width() - 16 - 84)
            fitted = QFontMetrics(title_font).elidedText(
                self.note.title_text, Qt.ElideRight, avail
            )
            p.drawText(
                QRectF(16, 0, avail, self.height()),
                Qt.AlignVCenter | Qt.AlignLeft,
                fitted,
            )

        cy = self.height() / 2
        if self.note.pinned:
            # 一枚深色小钉，表示这张浮在最上层
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(72, 54, 36, 150))
            p.drawEllipse(QRectF(8.5, cy - 2.2, 4.4, 4.4))
        if self.note.is_selected:
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(72, 54, 36, 150), 1.0))
            p.drawEllipse(QRectF(6.6, cy - 4.1, 8.2, 8.2))
        p.end()

    def mousePressEvent(self, event):
        if self._editing:
            self.title_edit.setFocus(Qt.MouseFocusReason)
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            self.note.select()
            self.note.hide_confirm()
            self._press = event.globalPosition().toPoint()
            self._drag = None
            self._offset = self._press - self.note.frameGeometry().topLeft()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self._press is not None:
            pos = event.globalPosition().toPoint()
            if self._drag is None and (pos - self._press).manhattanLength() >= 3:
                self._drag = self._offset
                self.note.begin_drag()
            if self._drag is not None:
                self.note.move(pos - self._drag)

    def mouseReleaseEvent(self, event):
        if self._drag is not None:
            self.note.end_drag()
        self._drag = None
        self._press = None
        self._offset = None
        self.setCursor(Qt.OpenHandCursor)

    def contextMenuEvent(self, event):
        self.note.show_menu(event.globalPos())


class ConfirmBar(QWidget):
    """便签内部的删除确认条，非模态，不会像弹窗那样藏在别的窗口后面。"""

    def __init__(self, note):
        super().__init__(note.card)
        self.note = note
        self.setObjectName("confirmBar")
        self.setFixedHeight(34)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "QWidget#confirmBar{background:rgba(58,44,34,240);}"
            "QLabel{color:#FFF6E4;font-family:'Microsoft YaHei';font-size:12px;}"
            "QPushButton{background:rgba(255,255,255,34);border:0;border-radius:6px;"
            "color:#FFF6E4;font-family:'Microsoft YaHei';font-size:12px;padding:4px 10px;}"
            "QPushButton:hover{background:rgba(255,255,255,68);}"
            "QPushButton#danger{background:#D7624F;color:#FFFFFF;}"
            "QPushButton#danger:hover{background:#E4705D;}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 6, 4)
        lay.setSpacing(6)
        self.label = QLabel("删除？")
        lay.addWidget(self.label)
        lay.addStretch(1)
        self.btn_cancel = QPushButton("算了")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet("padding:3px 7px;")
        self.btn_cancel.clicked.connect(note.hide_confirm)
        lay.addWidget(self.btn_cancel)
        self.btn_delete = QPushButton("删除")
        self.btn_delete.setObjectName("danger")
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.setStyleSheet("padding:3px 7px;")
        self.btn_delete.clicked.connect(note.delete_now)
        lay.addWidget(self.btn_delete)

    def resizeEvent(self, event):
        # 窄便签放不下文字，只留两个按钮
        self.label.setVisible(self.width() >= 150)
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        event.accept()


class NoteWindow(QWidget):
    selected = Signal(object)
    changed = Signal()
    deleted = Signal(object)

    def __init__(self, data, sounds):
        super().__init__()
        self.sounds = sounds
        self.data = dict(data)
        self.paper = _as_color(data.get("paper"), theme.PAPER_DEFAULT)
        self.tape = _as_color(data.get("tape"), theme.TAPE_DEFAULT)
        self.font_key = data.get("font") if data.get("font") in theme.FONTS else "楷体"
        self.pinned = _as_bool(data.get("pinned", False))
        self.collapsed = _as_bool(data.get("collapsed", False))
        self.opacity = _as_opacity(data.get("opacity", 1.0))
        self.title_text = _as_title(data.get("title", theme.TITLE_DEFAULT), allow_empty=True)
        self.title_font_size = _as_int(
            data.get("title_font_size"), theme.TITLE_FONT_SIZE, 10, 28
        )
        self.title_color = _as_color(
            data.get("title_color"), theme.TITLE_COLOR_DEFAULT
        )
        self.font_size = _as_int(data.get("font_size"), theme.FONT_SIZE, 10, 36)
        self.font_color = _as_color(data.get("font_color"), theme.TEXT_DEFAULT)
        self.is_selected = False
        self._level = 0.0
        self._dragging = False
        self._hover = False
        self._expanded_h = _as_int(data.get("h"), 200, 120, 820) + theme.MARGIN * 2

        self.setWindowTitle("便利贴")
        self.setWindowFlags(self._flags())
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(theme.MARGIN, theme.MARGIN, theme.MARGIN, theme.MARGIN)
        outer.setSpacing(0)
        self.card = Card(self)
        outer.addWidget(self.card)
        # 显式给窗口一个最小高度，否则折叠时会被布局最小高度顶住缩不下去
        self.setMinimumSize(
            150 + theme.MARGIN * 2,
            theme.title_height(self.title_font_size) + theme.MARGIN * 2,
        )

        inner = QVBoxLayout(self.card)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        self.title = TitleBar(self)
        inner.addWidget(self.title)

        self.body = BodyEdit(self)
        self.body.setFrameShape(QFrame.Shape.NoFrame)
        self.body.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.body.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body.setStyleSheet(
            "QTextEdit{background:transparent;border:0px;}"
            "QScrollBar:vertical{background:transparent;width:6px;margin:2px;}"
            "QScrollBar::handle:vertical{background:rgba(0,0,0,46);border-radius:3px;min-height:24px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;}"
            "QScrollBar::add-page,QScrollBar::sub-page{background:transparent;}"
        )
        self.body.document().setDocumentMargin(14)
        self._apply_body_font()
        self._apply_text_palette()
        self.body.setPlaceholderText("双击这里输入内容…")
        text = data.get("text", "")
        if not isinstance(text, str):
            text = "" if text is None else str(text)
        html = data.get("text_html", "")
        if isinstance(html, str) and html.strip():
            try:
                self.body.setHtml(_prepare_html(html))
            except Exception:
                logging.exception("恢复正文富文本失败，退回纯文本")
                self.body.setPlainText(text)
        else:
            self.body.setPlainText(text)
        self.body.textChanged.connect(self.changed.emit)
        self.body.setContextMenuPolicy(Qt.CustomContextMenu)
        self.body.customContextMenuRequested.connect(
            lambda pos: self.show_menu(self.body.mapToGlobal(pos))
        )
        inner.addWidget(self.body, 1)

        self.grip = Grip(self)
        self.grip.raise_()

        self.confirm = ConfirmBar(self)
        self.confirm.hide()

        self.effect = QGraphicsDropShadowEffect(self.card)
        self.effect.setOffset(0.0, theme.SHADOW_REST[1])
        self.effect.setBlurRadius(theme.SHADOW_REST[0])
        self.effect.setColor(QColor(0, 0, 0, int(255 * theme.SHADOW_REST[2])))
        self.card.setGraphicsEffect(self.effect)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._apply_shadow)

        w = _as_int(data.get("w"), 230, 150, 720)
        h = _as_int(data.get("h"), 200, 120, 820)
        self.resize(w + theme.MARGIN * 2, h + theme.MARGIN * 2)
        self.move(
            _as_int(data.get("x"), 200, -20000, 20000),
            _as_int(data.get("y"), 120, -20000, 20000),
        )

        if self.collapsed:
            self.body.hide()
            self.grip.hide()
            self.resize(
                w + theme.MARGIN * 2,
                theme.MARGIN * 2 + self.title.height(),
            )
            self.title.set_tools_visible(True)
            self.title.sync_state()

        self.setWindowOpacity(self.opacity)

    # ---------- 窗口层级 ----------
    def _flags(self):
        # 不用 Qt 的 StaysOnTop/Bottom hint：Tool 窗口上它不保证生效，
        # 置顶/贴桌面统一由 Win32 SetWindowPos 控制
        return Qt.FramelessWindowHint | Qt.Tool | Qt.NoDropShadowWindowHint

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_zorder)

    def _apply_zorder(self):
        if os.environ.get("STICKY_DEBUG_TOPMOST"):
            return
        try:
            hwnd = wintypes.HWND(int(self.winId()))
            flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            if self.pinned:
                _SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
            else:
                _SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
                _SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, flags)
        except Exception:
            # 层级失败不能让便签消失，但必须留日志，不能像旧版那样静默吞掉
            logging.exception("SetWindowPos failed (pinned=%s)", self.pinned)

    def ensure_visible(self):
        """拔掉副屏 / 分辨率变化后，把便签拉回某块屏幕，至少保证标题条能被抓到。"""
        frame = self.frameGeometry()
        scr = QGuiApplication.screenAt(frame.center())
        if scr is None:
            for candidate in QGuiApplication.screens():
                if candidate.availableGeometry().intersects(frame):
                    scr = candidate
                    break
        if scr is None:
            scr = QGuiApplication.primaryScreen()
            av = scr.availableGeometry()
            self.move(
                av.center().x() - self.width() // 2,
                av.center().y() - self.height() // 2,
            )
            return
        av = scr.availableGeometry()
        x = min(max(self.x(), av.left() - self.width() + 72), av.right() - 72)
        y = min(max(self.y(), av.top()), av.bottom() - theme.MARGIN * 2 - self.title.height())
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    # ---------- 阴影三态 ----------
    def _shadow_to(self, level, animate=True):
        self._anim.stop()
        if not animate:
            # 拖动是高频路径：直接切到目标态，避免每帧重建高斯模糊
            self._apply_shadow(float(level))
            return
        self._anim.setStartValue(float(self._level))
        self._anim.setEndValue(float(level))
        self._anim.start()

    def _apply_shadow(self, value):
        v = float(value)
        self._level = v
        if v <= 1.0:
            t = v
            blur = _lerp(theme.SHADOW_REST[0], theme.SHADOW_HOVER[0], t)
            dy = _lerp(theme.SHADOW_REST[1], theme.SHADOW_HOVER[1], t)
            alpha = _lerp(theme.SHADOW_REST[2], theme.SHADOW_HOVER[2], t)
        else:
            t = v - 1.0
            blur = _lerp(theme.SHADOW_HOVER[0], theme.SHADOW_DRAG[0], t)
            dy = _lerp(theme.SHADOW_HOVER[1], theme.SHADOW_DRAG[1], t)
            alpha = _lerp(theme.SHADOW_HOVER[2], theme.SHADOW_DRAG[2], t)
        self.effect.setBlurRadius(blur)
        self.effect.setOffset(0.0, dy)
        self.effect.setColor(QColor(0, 0, 0, int(255 * alpha)))

    def set_hover(self, on):
        self._hover = bool(on)
        self.title.set_tools_visible(on or self._dragging or self.collapsed)
        if not self._dragging:
            self._shadow_to(1 if on else 0)

    # ---------- 拖动 ----------
    def begin_drag(self):
        if self._dragging:
            return
        self._dragging = True
        self.title.set_tools_visible(True)
        self._shadow_to(2, animate=False)
        self.sounds.play("snap")

    def end_drag(self):
        if not self._dragging:
            return
        self._dragging = False
        self.sounds.play("drop")
        self._shadow_to(1 if self._hover else 0, animate=False)
        self.title.set_tools_visible(self._hover or self.collapsed)
        self.save_state()
        if not self.pinned:
            self._apply_zorder()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if not self.pinned:
            self._apply_zorder()

    # ---------- 选中 ----------
    def select(self):
        if not self.is_selected:
            self.is_selected = True
            self.title.update()
        self.selected.emit(self)

    def set_selected(self, on):
        self.is_selected = bool(on)
        self.title.update()

    # ---------- 置顶 ----------
    def toggle_pin(self):
        self.set_pinned(not self.pinned)

    def set_pinned(self, on):
        on = bool(on)
        if on == self.pinned:
            return
        self.pinned = on
        # 只改 Win32 层级，不动窗口 flags，避免窗口重建丢透明度 / 闪烁
        self._apply_zorder()
        self.title.sync_state()
        self.title.update()
        self.changed.emit()

    def set_opacity(self, value):
        self.opacity = max(0.3, min(1.0, float(value)))
        self.setWindowOpacity(self.opacity)
        self.changed.emit()

    def raise_note(self):
        self._apply_zorder()
        self.changed.emit()

    # ---------- 折叠 ----------
    def toggle_collapse(self):
        self.set_collapsed(not self.collapsed)

    def set_collapsed(self, on):
        on = bool(on)
        if on == self.collapsed:
            return
        self.hide_confirm()
        if on:
            self._expanded_h = self.height()
            self.collapsed = True
            self.grip.hide()
            self.body.hide()
            self.title.sync_state()
            self.title.set_tools_visible(True)
            self.card.update()
            self.title.update()
            self._animate_height(theme.MARGIN * 2 + self.title.height())
        else:
            self.collapsed = False
            self.body.show()
            self.title.sync_state()
            self.card.update()
            self.title.update()
            self._animate_height(self._expanded_h, show_grip=True)
        self.changed.emit()

    def _animate_height(self, target, show_grip=False):
        start = self.geometry()
        end = QRect(start.x(), start.y(), start.width(), int(target))
        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(180)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(start)
        anim.setEndValue(end)
        anim.finished.connect(lambda: self._height_done(int(target), show_grip))
        self._h_anim = anim
        anim.start()

    def _height_done(self, target, show_grip):
        if self.height() != target:
            # 布局最小高度可能把窗口顶回去，兜底再压一次
            self.resize(self.width(), target)
        if show_grip:
            self.grip.show()
            self.grip.raise_()

    # ---------- 样式 ----------
    def apply_paper(self, color):
        self.paper = color
        self.card.update()
        self.changed.emit()

    def apply_tape(self, color):
        self.tape = color
        self.title.update()
        self.changed.emit()

    def set_title_text(self, text):
        text = _as_title(text, allow_empty=True)
        if text == self.title_text:
            return
        self.title_text = text
        self.title.update()
        self.changed.emit()

    def apply_title_font_size(self, size):
        size = _as_int(size, theme.TITLE_FONT_SIZE, 10, 28)
        if size == self.title_font_size:
            return
        self.title_font_size = size
        delta = self.title.apply_style(size, self.title_color)
        self.setMinimumSize(
            150 + theme.MARGIN * 2,
            self.title.height() + theme.MARGIN * 2,
        )
        if delta:
            if self.collapsed:
                self._expanded_h = max(
                    120 + theme.MARGIN * 2, self._expanded_h + delta
                )
                self.resize(
                    self.width(),
                    max(self.minimumHeight(), theme.MARGIN * 2 + self.title.height()),
                )
            else:
                self.resize(
                    self.width(),
                    max(120 + theme.MARGIN * 2, self.height() + delta),
                )
        self.changed.emit()

    def apply_title_color(self, color):
        parsed = QColor(color) if isinstance(color, str) else QColor()
        if not parsed.isValid():
            return
        self.title_color = parsed.name()
        self.title.apply_style(self.title_font_size, self.title_color)
        self.changed.emit()

    def _apply_body_font(self):
        font = QFont()
        font.setFamilies(theme.FONTS.get(self.font_key, theme.FONTS["楷体"]))
        font.setPixelSize(self.font_size)
        self.body.setFont(font)
        self.body.document().setDefaultFont(font)
        self.body.viewport().update()

    def _apply_text_palette(self):
        pal = self.body.palette()
        pal.setColor(QPalette.ColorRole.Text, QColor(self.font_color))
        pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(120, 108, 92, 120))
        pal.setColor(QPalette.ColorRole.Base, QColor(0, 0, 0, 0))
        self.body.setPalette(pal)
        self.body.viewport().setPalette(pal)
        self.body.viewport().update()

    def apply_font(self, key):
        self.font_key = key
        self._apply_body_font()
        self.changed.emit()

    def apply_font_size(self, size):
        size = _as_int(size, theme.FONT_SIZE, 10, 36)
        if self.body.format_selection_size(size):
            self.changed.emit()
            return True
        self.font_size = size
        self._apply_body_font()
        self.changed.emit()
        return False

    def apply_font_color(self, color):
        parsed = QColor(color) if isinstance(color, str) else QColor()
        if not parsed.isValid():
            return False
        name = parsed.name()
        if self.body.format_selection_color(name):
            self.changed.emit()
            return True
        self.font_color = name
        self._apply_text_palette()
        self.changed.emit()
        return False

    def apply_size(self, w, h):
        if self.collapsed:
            self._expanded_h = h + theme.MARGIN * 2
        else:
            self.resize(int(w) + theme.MARGIN * 2, int(h) + theme.MARGIN * 2)
        self.changed.emit()

    # ---------- 删除 / 菜单 ----------
    def request_delete(self):
        self.select()
        if self.collapsed:
            self.set_collapsed(False)
            QTimer.singleShot(220, self._show_confirm)
        else:
            self._show_confirm()

    def _show_confirm(self):
        confirm = getattr(self, "confirm", None)
        if confirm is None:
            return
        confirm.show()
        confirm.raise_()

    def delete_now(self):
        self.confirm.hide()
        self.deleted.emit(self)

    def hide_confirm(self):
        confirm = getattr(self, "confirm", None)
        if confirm is not None:
            confirm.hide()

    def show_menu(self, global_pos):
        self.select()
        menu = QMenu(self)

        act_title = menu.addAction("修改标题")
        act_title.triggered.connect(lambda: QTimer.singleShot(0, self.title.start_title_edit))
        menu.addSeparator()

        layer = menu.addMenu("层级")
        act_top = layer.addAction("置顶（浮在其他窗口上）")
        act_top.setCheckable(True)
        act_top.setChecked(self.pinned)
        act_bottom = layer.addAction("贴桌面（压在最底层）")
        act_bottom.setCheckable(True)
        act_bottom.setChecked(not self.pinned)
        layer_group = QActionGroup(menu)
        layer_group.setExclusive(True)
        layer_group.addAction(act_top)
        layer_group.addAction(act_bottom)
        act_top.triggered.connect(lambda: self.set_pinned(True))
        act_bottom.triggered.connect(lambda: self.set_pinned(False))

        opac = menu.addMenu("透明度")
        opac_group = QActionGroup(menu)
        opac_group.setExclusive(True)
        for pct in (100, 90, 80, 70, 60, 50, 40, 30):
            act = opac.addAction("%d%%" % pct)
            act.setCheckable(True)
            act.setChecked(abs(self.opacity * 100 - pct) < 3)
            act.triggered.connect(lambda checked=False, v=pct / 100.0: self.set_opacity(v))
            opac_group.addAction(act)

        menu.addSeparator()
        act_fold = menu.addAction("展开" if self.collapsed else "折叠")
        act_fold.triggered.connect(self.toggle_collapse)
        menu.addSeparator()
        act_del = menu.addAction("删除")
        act_del.triggered.connect(self.request_delete)
        menu.exec(global_pos)

    def contextMenuEvent(self, event):
        self.show_menu(event.globalPos())

    # ---------- 持久化 ----------
    def save_state(self):
        self.changed.emit()

    def to_dict(self):
        if self.collapsed:
            card_h = max(120, self._expanded_h - theme.MARGIN * 2)
        else:
            card_h = max(120, self.height() - theme.MARGIN * 2)
        return dict(
            x=self.x(),
            y=self.y(),
            w=max(150, self.width() - theme.MARGIN * 2),
            h=card_h,
            paper=self.paper,
            tape=self.tape,
            font=self.font_key,
            font_size=self.font_size,
            font_color=self.font_color,
            title=self.title_text,
            title_font_size=self.title_font_size,
            title_color=self.title_color,
            pinned=self.pinned,
            collapsed=self.collapsed,
            opacity=round(self.opacity, 2),
            text=self.body.toPlainText(),
            text_html=self.body.toHtml(),
        )

    def resizeEvent(self, event):
        self.grip.move(self.width() - theme.MARGIN * 2 - 18, self.height() - theme.MARGIN * 2 - 18)
        self.grip.raise_()
        confirm = getattr(self, "confirm", None)
        if confirm is not None:
            confirm.setGeometry(0, self.card.height() - confirm.height(), self.card.width(), confirm.height())
            confirm.raise_()
        super().resizeEvent(event)
