# -*- coding: utf-8 -*-
"""底部控制条：新建、纸张色、标题条色、尺寸、字体、音效、置顶、折叠、重置。"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QRegion
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import theme

OPACITIES = (100, 90, 80, 70, 60, 50, 40, 30)


def _safe_qss_color(value, fallback):
    """只接受 QColor 认得的颜色，避免存档被篡改后拼进 QSS 造成样式注入。"""
    color = QColor(value)
    return color.name() if color.isValid() else fallback


class ControlPanel(QWidget):
    def __init__(self, manager):
        super().__init__(None)
        self.manager = manager
        self._sync = False

        self.setWindowTitle("控制条")
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setFixedSize(theme.PANEL_W, theme.PANEL_H)

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, theme.PANEL_W, theme.PANEL_H), 14, 14)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.card = QWidget(self)
        self.card.setStyleSheet(
            """
            QPushButton{
                background:rgba(255,255,255,26);
                border:0;border-radius:8px;color:#E9EDF4;
                padding:6px 10px;font-family:'Microsoft YaHei';font-size:12px;
            }
            QPushButton:hover{background:rgba(255,255,255,56);}
            QPushButton:checked{background:#D98B52;color:#FFFFFF;}
            QPushButton:disabled{color:rgba(233,237,244,89);background:rgba(255,255,255,13);}
            QPushButton#primary{background:#D98B52;color:#FFFFFF;font-weight:600;}
            QPushButton#primary:hover{background:#E79A60;}
            QComboBox{
                background:rgba(255,255,255,26);border:0;border-radius:8px;
                color:#E9EDF4;padding:5px 8px;font-family:'Microsoft YaHei';font-size:12px;
            }
            QComboBox:hover{background:rgba(255,255,255,51);}
            QComboBox::drop-down{border:0px;width:18px;}
            QComboBox QAbstractItemView{
                background:#2A3038;color:#E9EDF4;
                selection-background-color:#3E4753;border:1px solid #3E4753;
            }
            QLabel{color:#C9D1DC;font-family:'Microsoft YaHei';font-size:12px;}
            QLabel#hint{color:rgba(201,209,220,140);font-size:11px;}
            """
        )
        outer.addWidget(self.card)

        body = QVBoxLayout(self.card)
        body.setContentsMargins(14, 9, 14, 9)
        body.setSpacing(7)

        # 第一行
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        self.btn_new = QPushButton("＋ 新建便签")
        self.btn_new.setObjectName("primary")
        self.btn_new.setFixedHeight(28)
        self.btn_new.setCursor(Qt.PointingHandCursor)
        row1.addWidget(self.btn_new)
        row1.addWidget(self._sep())

        row1.addWidget(QLabel("颜色"))
        self.btn_paper = QPushButton()
        self.btn_paper.setFixedSize(30, 22)
        self.btn_paper.setCursor(Qt.PointingHandCursor)
        self.btn_paper.setToolTip("纸张颜色")
        row1.addWidget(self.btn_paper)

        row1.addWidget(QLabel("标题条"))
        self.btn_tape = QPushButton()
        self.btn_tape.setFixedSize(30, 22)
        self.btn_tape.setCursor(Qt.PointingHandCursor)
        self.btn_tape.setToolTip("标题条颜色")
        row1.addWidget(self.btn_tape)

        row1.addWidget(self._sep())
        row1.addWidget(QLabel("大小"))
        self.cb_size = QComboBox()
        self.cb_size.setFixedWidth(118)
        self.cb_size.setCursor(Qt.PointingHandCursor)
        for label, _w, _h in theme.SIZES:
            self.cb_size.addItem(label)
        self.cb_size.addItem("自定义")
        self._size_custom_index = self.cb_size.count() - 1
        row1.addWidget(self.cb_size)

        row1.addWidget(QLabel("字体"))
        self.cb_font = QComboBox()
        self.cb_font.setFixedWidth(88)
        self.cb_font.setCursor(Qt.PointingHandCursor)
        for key in theme.FONTS.keys():
            self.cb_font.addItem(key)
        row1.addWidget(self.cb_font)

        row1.addWidget(QLabel("字号"))
        self.cb_fontsize = QComboBox()
        self.cb_fontsize.setFixedWidth(58)
        self.cb_fontsize.setCursor(Qt.PointingHandCursor)
        self.cb_fontsize.setToolTip("只调选中这一张便签的正文大小")
        for size in theme.FONT_SIZES:
            self.cb_fontsize.addItem(str(size))
        row1.addWidget(self.cb_fontsize)

        row1.addWidget(QLabel("字色"))
        self.btn_textcolor = QPushButton("A")
        self.btn_textcolor.setFixedSize(30, 22)
        self.btn_textcolor.setCursor(Qt.PointingHandCursor)
        self.btn_textcolor.setToolTip("只调选中这一张便签的正文颜色")
        row1.addWidget(self.btn_textcolor)

        row1.addWidget(QLabel("透明度"))
        self.cb_opacity = QComboBox()
        self.cb_opacity.setFixedWidth(76)
        self.cb_opacity.setCursor(Qt.PointingHandCursor)
        self.cb_opacity.setToolTip("只调选中这一张便签的透明度")
        for pct in OPACITIES:
            self.cb_opacity.addItem("%d%%" % pct)
        row1.addWidget(self.cb_opacity)

        row1.addStretch(1)
        body.addLayout(row1)

        # 第二行
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self.btn_sound = QPushButton("音效开")
        self.btn_sound.setFixedHeight(26)
        self.btn_sound.setCursor(Qt.PointingHandCursor)
        self.btn_sound.setContextMenuPolicy(Qt.CustomContextMenu)
        self.btn_sound.customContextMenuRequested.connect(self._sound_menu)
        row2.addWidget(self.btn_sound)

        self.btn_pin = QPushButton("置顶")
        self.btn_pin.setFixedHeight(26)
        self.btn_pin.setCheckable(True)
        self.btn_pin.setCursor(Qt.PointingHandCursor)
        self.btn_pin.setToolTip("选中便签浮在其他窗口上面")
        row2.addWidget(self.btn_pin)

        self.btn_desktop = QPushButton("贴桌面")
        self.btn_desktop.setFixedHeight(26)
        self.btn_desktop.setCheckable(True)
        self.btn_desktop.setCursor(Qt.PointingHandCursor)
        self.btn_desktop.setToolTip("选中便签压到最底层，贴回桌面")
        row2.addWidget(self.btn_desktop)

        self.btn_fold = QPushButton("折叠")
        self.btn_fold.setFixedHeight(26)
        self.btn_fold.setCursor(Qt.PointingHandCursor)
        row2.addWidget(self.btn_fold)

        self.btn_reset = QPushButton("重置")
        self.btn_reset.setFixedHeight(26)
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        row2.addWidget(self.btn_reset)

        row2.addWidget(self._sep())
        row2.addWidget(QLabel("标题字号"))
        self.cb_titlesize = QComboBox()
        self.cb_titlesize.setFixedWidth(52)
        self.cb_titlesize.setCursor(Qt.PointingHandCursor)
        self.cb_titlesize.setToolTip("只调选中便签的标题字号；胶带条高度会自动跟着变")
        for size in theme.TITLE_FONT_SIZES:
            self.cb_titlesize.addItem(str(size))
        row2.addWidget(self.cb_titlesize)

        row2.addWidget(QLabel("标题色"))
        self.btn_titlecolor = QPushButton("A")
        self.btn_titlecolor.setFixedSize(30, 22)
        self.btn_titlecolor.setCursor(Qt.PointingHandCursor)
        self.btn_titlecolor.setToolTip("只调选中便签的标题文字颜色")
        row2.addWidget(self.btn_titlecolor)

        row2.addStretch(1)
        hint = QLabel("双击标题改标题 · 双击正文编辑 · 右键更多")
        hint.setObjectName("hint")
        row2.addWidget(hint)
        body.addLayout(row2)

        # 事件
        self.btn_new.clicked.connect(lambda: self.manager.new_note())
        self.btn_paper.clicked.connect(self.pick_paper)
        self.btn_tape.clicked.connect(self.pick_tape)
        self.cb_size.currentIndexChanged.connect(self.size_changed)
        self.cb_font.currentTextChanged.connect(self.font_changed)
        self.cb_fontsize.currentIndexChanged.connect(self.font_size_changed)
        self.btn_textcolor.clicked.connect(self.pick_text_color)
        self.cb_titlesize.currentIndexChanged.connect(self.title_size_changed)
        self.btn_titlecolor.clicked.connect(self.pick_title_color)
        self.cb_opacity.currentIndexChanged.connect(self.opacity_changed)
        self.btn_sound.clicked.connect(self.toggle_sound)
        self.btn_pin.clicked.connect(lambda: self.set_layer(True))
        self.btn_desktop.clicked.connect(lambda: self.set_layer(False))
        self.btn_fold.clicked.connect(self.toggle_fold)
        self.btn_reset.clicked.connect(self.reset_all)

        self.btn_sound.setText("音效开" if manager.sounds.enabled else "音效关")
        self.sync_sound()
        self.sync(None)

    @staticmethod
    def _sep():
        line = QFrame()
        line.setFixedWidth(1)
        line.setStyleSheet("background:rgba(255,255,255,46);")
        return line

    def paintEvent(self, event):
        """整块不透明底板 + 圆角遮罩，避免分层透明窗口在部分机器上不合成。"""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(28, 32, 40))
        p.drawRoundedRect(rect, 14, 14)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1.0))
        p.drawRoundedRect(rect, 14, 14)
        p.end()

    # ---------- 当前便签 ----------
    def _current(self):
        return self.manager.selected

    def pick_paper(self):
        note = self._current()
        if not note:
            return
        color = QColorDialog.getColor(QColor(note.paper), self, "选择纸张颜色")
        if color.isValid():
            note.apply_paper(color.name())
            self.sync(note)

    def pick_tape(self):
        note = self._current()
        if not note:
            return
        color = QColorDialog.getColor(QColor(note.tape), self, "选择标题条颜色")
        if color.isValid():
            note.apply_tape(color.name())
            self.sync(note)

    def pick_text_color(self):
        note = self._current()
        if not note:
            return
        selected = note.body.has_selection()
        start = note.body.selection_color(note.font_color) if selected else note.font_color
        color = QColorDialog.getColor(QColor(start), self, "选择字体颜色")
        if color.isValid():
            selection_only = note.apply_font_color(color.name())
            if selection_only:
                # 选区改了颜色，但整张便签的默认字色没变，不要把按钮同步回去
                self._style_color_button(self.btn_textcolor, color.name())
            else:
                self.sync(note)

    def pick_title_color(self):
        note = self._current()
        if not note:
            return
        color = QColorDialog.getColor(
            QColor(note.title_color), self, "选择标题文字颜色"
        )
        if color.isValid():
            note.apply_title_color(color.name())
            self.sync(note)

    @staticmethod
    def _style_color_button(button, color):
        c = QColor(color)
        if not c.isValid():
            c = QColor(theme.TEXT_DEFAULT)
        text_color = "#FFFFFF" if c.lightness() < 140 else "#3A2C1E"
        button.setStyleSheet(
            "QPushButton{background:%s;border:1px solid rgba(255,255,255,89);"
            "border-radius:5px;padding:0;color:%s;font-family:'Microsoft YaHei';"
            "font-size:12px;font-weight:600;}"
            % (c.name(), text_color)
        )

    def size_changed(self, index):
        if self._sync or index < 0 or index >= len(theme.SIZES):
            return
        note = self._current()
        if not note:
            return
        _label, w, h = theme.SIZES[index]
        note.apply_size(w, h)

    def font_changed(self, key):
        if self._sync or not key:
            return
        note = self._current()
        if note:
            note.apply_font(key)

    def font_size_changed(self, index):
        if self._sync or index < 0:
            return
        note = self._current()
        if note:
            note.apply_font_size(theme.FONT_SIZES[index])

    def title_size_changed(self, index):
        if self._sync or index < 0:
            return
        note = self._current()
        if note:
            note.apply_title_font_size(theme.TITLE_FONT_SIZES[index])
            self.sync(note)

    def opacity_changed(self, index):
        if self._sync or index < 0:
            return
        note = self._current()
        if note:
            note.set_opacity(OPACITIES[index] / 100.0)

    def toggle_sound(self):
        self.manager.toggle_sound(not self.manager.sounds.enabled)

    def sync_sound(self):
        enabled = self.manager.sounds.enabled
        available = self.manager.sounds.available
        self.btn_sound.setText("音效开" if enabled else "音效关")
        if available:
            self.btn_sound.setToolTip("左键开关；右键选择自己的拖动 / 落纸音效")
        else:
            self.btn_sound.setToolTip("音效不可用：文件无法生成，请检查数据目录权限")

    def _sound_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("选择拖动音效…").triggered.connect(
            lambda: self.manager.choose_sound("snap")
        )
        menu.addAction("选择落纸音效…").triggered.connect(
            lambda: self.manager.choose_sound("drop")
        )
        menu.addSeparator()
        menu.addAction("恢复默认音效").triggered.connect(self.manager.reset_sounds)
        menu.exec(self.btn_sound.mapToGlobal(pos))

    def set_layer(self, on_top):
        note = self._current()
        if note:
            note.set_pinned(bool(on_top))
            self.sync(note)

    def toggle_fold(self):
        note = self._current()
        if note:
            note.toggle_collapse()
            self.sync(note)

    def reset_all(self):
        self.manager.reset_all()

    # ---------- 同步选中状态 ----------
    def sync(self, note):
        self._sync = True
        has = note is not None
        for widget in (self.btn_paper, self.btn_tape, self.cb_size, self.cb_font,
                       self.cb_fontsize, self.btn_textcolor, self.cb_titlesize,
                       self.btn_titlecolor, self.cb_opacity,
                       self.btn_pin, self.btn_desktop, self.btn_fold):
            widget.setEnabled(has)

        if has:
            paper = _safe_qss_color(note.paper, theme.PAPER_DEFAULT)
            tape = _safe_qss_color(note.tape, theme.TAPE_DEFAULT)
            self.btn_paper.setStyleSheet(
                "QPushButton{background:%s;border:1px solid rgba(255,255,255,89);"
                "border-radius:5px;padding:0;}" % paper
            )
            self.btn_tape.setStyleSheet(
                "QPushButton{background:%s;border:1px solid rgba(255,255,255,89);"
                "border-radius:5px;padding:0;}" % tape
            )

            card_w = note.width() - theme.MARGIN * 2
            card_h = (note._expanded_h - theme.MARGIN * 2) if note.collapsed else (
                note.height() - theme.MARGIN * 2
            )
            index = -1
            for i, (_label, w, h) in enumerate(theme.SIZES):
                if abs(card_w - w) <= 8 and abs(card_h - h) <= 8:
                    index = i
                    break
            self.cb_size.setCurrentIndex(index if index >= 0 else self._size_custom_index)
            self.cb_font.setCurrentText(note.font_key)

            size_index = min(
                range(len(theme.FONT_SIZES)),
                key=lambda i: abs(theme.FONT_SIZES[i] - note.font_size),
            )
            self.cb_fontsize.setCurrentIndex(size_index)
            self._style_color_button(self.btn_textcolor, note.font_color)

            title_index = min(
                range(len(theme.TITLE_FONT_SIZES)),
                key=lambda i: abs(theme.TITLE_FONT_SIZES[i] - note.title_font_size),
            )
            self.cb_titlesize.setCurrentIndex(title_index)
            self._style_color_button(self.btn_titlecolor, note.title_color)

            self.btn_pin.setChecked(note.pinned)
            self.btn_desktop.setChecked(not note.pinned)
            self.btn_fold.setText("展开" if note.collapsed else "折叠")

            best = 0
            for i, pct in enumerate(OPACITIES):
                if abs(pct / 100.0 - note.opacity) < 0.03:
                    best = i
                    break
            else:
                best = min(range(len(OPACITIES)),
                           key=lambda i: abs(OPACITIES[i] / 100.0 - note.opacity))
            self.cb_opacity.setCurrentIndex(best)
        else:
            self.btn_pin.setChecked(False)
            self.btn_desktop.setChecked(False)
            self.cb_opacity.setCurrentIndex(0)
            self.cb_fontsize.setCurrentIndex(-1)
            self.cb_titlesize.setCurrentIndex(-1)
            self._style_color_button(self.btn_textcolor, theme.TEXT_DEFAULT)
            self._style_color_button(self.btn_titlecolor, theme.TITLE_COLOR_DEFAULT)

        self._sync = False
