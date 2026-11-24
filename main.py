# -*- coding: utf-8 -*-
"""桌面便利贴：启动、托盘、便签管理。"""
import ctypes
import logging
import os
import sys
import traceback
from ctypes import wintypes
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import QLockFile, QPoint, QRect, QSettings, QTimer, Qt
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

import store
import sound
import theme
from note import NoteWindow
from panel import ControlPanel
from sound import SoundPlayer

_WindowFromPoint = ctypes.windll.user32.WindowFromPoint
_WindowFromPoint.argtypes = [wintypes.POINT]
_WindowFromPoint.restype = wintypes.HWND
_GetClassNameW = ctypes.windll.user32.GetClassNameW
_GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_GetClassNameW.restype = ctypes.c_int

DESKTOP_CLASSES = ("Progman", "WorkerW", "SHELLDLL_DefView", "SysListView32")


def install_crash_handler():
    """落盘日志 + 弹窗提示，避免窗口化 exe 的异常变成“双击没反应”。"""
    try:
        store.ensure_dir()
        log_path = os.path.join(store.APP_DIR, "app.log")
        handler = RotatingFileHandler(
            log_path, maxBytes=512 * 1024, backupCount=2, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logging.basicConfig(
            level=logging.WARNING,
            handlers=[handler],
        )
    except Exception:
        logging.basicConfig(level=logging.WARNING)

    def hook(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.error("未捕获异常:\n%s", text)
        try:
            box = QMessageBox(
                QMessageBox.Critical,
                "桌面便利贴",
                "程序遇到错误：%s\n日志已写入：%s" % (exc_value, os.path.join(store.APP_DIR, "app.log")),
            )
            box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            box.exec()
        except Exception:
            pass

    sys.excepthook = hook


def make_icon():
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#FFF4CF"))
    p.drawRoundedRect(6, 6, 52, 52, 7, 7)
    p.setBrush(QColor("#D9C893"))
    p.drawRoundedRect(6, 6, 52, 13, 7, 7)
    p.setPen(QPen(QColor("#9A8B70"), 2))
    p.drawLine(16, 32, 48, 32)
    p.drawLine(16, 42, 40, 42)
    p.end()
    return QIcon(pm)


class Manager:
    def __init__(self, app):
        self.app = app
        self.sounds = SoundPlayer(enabled=bool(QSettings().value("sound", True, type=bool)))
        self.notes = []
        self.selected = None
        self._save_error_shown = False

        self._save_timer = QTimer()
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(700)
        self._save_timer.timeout.connect(self.save_all)

        self.panel = ControlPanel(self)
        # 托盘先建好：加载存档发现问题时要能立刻告诉用户
        self._build_tray()
        self._wire_screens()
        self._load_notes()

        if getattr(self, "_migrated_now", False):
            # 迁移这一次吹个气泡，告诉用户便签沉到桌面层了，去哪儿找
            QTimer.singleShot(3000, self._notify_layer_migrated)

        # 便签窗口建立之后再显示控制条：多张分层窗口同时创建时，
        # 先显示的那张容易停在“已显示但没上屏”的状态，重显一次即可。
        self.panel.show()
        self.panel.raise_()
        self.panel.repaint()
        self._position_panel()

    # ---------- 便签 ----------
    def _position_panel(self):
        screen = QGuiApplication.screenAt(QCursor.pos()) or self.app.primaryScreen()
        geo = screen.availableGeometry()
        w, h = self.panel.width(), self.panel.height()
        x = geo.center().x() - w // 2
        y = geo.bottom() - h - 8
        if w <= geo.width():
            x = max(geo.left() + 8, min(x, geo.right() - w - 8))
        if h <= geo.height():
            y = max(geo.top() + 8, min(y, geo.bottom() - h - 8))
        self.panel.move(x, y)

    def _wire_screens(self):
        self.app.screenAdded.connect(self._on_screen_added)
        self.app.screenRemoved.connect(self._on_screen_removed)
        for screen in self.app.screens():
            screen.availableGeometryChanged.connect(self._on_geometry_changed)

    def _on_screen_added(self, screen):
        screen.availableGeometryChanged.connect(self._on_geometry_changed)
        self._on_geometry_changed()

    def _on_screen_removed(self, *_):
        # 等 Qt 刷完屏幕列表再回收，避免在信号里拿到旧 geometry
        QTimer.singleShot(0, self._ensure_all_visible)

    def _on_geometry_changed(self, *_):
        QTimer.singleShot(0, self._ensure_all_visible)

    def _ensure_all_visible(self):
        moved = False
        for note in self.notes:
            before = note.pos()
            note.ensure_visible()
            moved = moved or note.pos() != before
        self._position_panel()
        if moved:
            self.schedule_save()

    def _clamp_position(self, x, y, w, h):
        """至少保证标题条有 80px 落在某块屏幕的可视区里，否则拉回主屏中央。"""
        x, y = int(x), int(y)
        title = QRect(x, y + theme.MARGIN, int(w), theme.TITLE_H)
        for screen in self.app.screens():
            visible = screen.availableGeometry().intersected(title)
            if visible.width() >= 80 and visible.height() > 0:
                return x, y
        geo = self.app.primaryScreen().availableGeometry()
        return geo.center().x() - int(w) // 2, geo.center().y() - int(h) // 2

    def _desktop_visible_at(self, x, y, w, h):
        """落点中心是不是露着桌面（而不是被别的窗口压住）。

        WindowFromPoint 收物理像素；多屏混合 DPI 下不能拿主屏 DPR 一刀切，
        这里取落点所在屏幕的 DPR 做近似换算（只用于“新建便签是否先浮起”的启发式判断）。
        """
        try:
            cx, cy = int(x + w / 2), int(y + h / 2)
            screen = QGuiApplication.screenAt(QPoint(cx, cy)) or self.app.primaryScreen()
            dpr = screen.devicePixelRatio()
            pt = wintypes.POINT(int(cx * dpr), int(cy * dpr))
            hwnd = _WindowFromPoint(pt)
            if not hwnd:
                return True
            buf = ctypes.create_unicode_buffer(128)
            _GetClassNameW(hwnd, buf, 128)
            return buf.value in DESKTOP_CLASSES
        except Exception:
            logging.exception("WindowFromPoint 探测失败，按桌面可见处理")
            return True

    def create_note(self, data=None, select=True, save=True):
        data = dict(data or {})
        try:
            w = max(150, min(720, int(float(data.get("w", 230)))))
            h = max(120, min(820, int(float(data.get("h", 200)))))
        except (TypeError, ValueError):
            w, h = 230, 200
        if "x" not in data or "y" not in data:
            geo = self.app.primaryScreen().availableGeometry()
            step = (len(self.notes) % 6) * 30
            data["x"] = geo.center().x() - 150 + step
            data["y"] = max(geo.top() + 60, geo.center().y() - 220 + step)
        data["x"], data["y"] = self._clamp_position(data["x"], data["y"], w, h)
        data.setdefault("w", w)
        data.setdefault("h", h)
        if "pinned" not in data:
            # 默认贴桌面；但落点被别的窗口盖住时先浮上来，免得新建了一张却看不见
            data["pinned"] = not self._desktop_visible_at(
                data["x"] - theme.MARGIN,
                data["y"] - theme.MARGIN,
                w + theme.MARGIN * 2,
                h + theme.MARGIN * 2,
            )

        note = NoteWindow(data, self.sounds)
        note.selected.connect(self.select)
        note.changed.connect(self.schedule_save)
        note.deleted.connect(self.delete_note)
        note.show()
        note.ensure_visible()
        self.notes.append(note)

        if select:
            self.select(note)
        if save:
            self.schedule_save()
        return note

    def new_note(self):
        if self.selected:
            data = dict(
                paper=self.selected.paper,
                tape=self.selected.tape,
                font=self.selected.font_key,
                w=max(150, self.selected.width() - theme.MARGIN * 2),
                h=max(120, self.selected.height() - theme.MARGIN * 2),
            )
        else:
            data = dict(paper=theme.PAPER_DEFAULT, tape=theme.TAPE_DEFAULT, font="楷体",
                        w=230, h=200)
        data["text"] = ""
        self.create_note(data)

    def select(self, note):
        for other in self.notes:
            if other is not note:
                other.set_selected(False)
        self.selected = note
        note.set_selected(True)
        if note.pinned:
            note._apply_zorder()
        self.panel.sync(note)

    def delete_note(self, note):
        if note in self.notes:
            self.notes.remove(note)
        try:
            note.deleted.disconnect(self.delete_note)
        except (RuntimeError, TypeError):
            pass
        note.hide()
        note.clearFocus()
        note.deleteLater()
        if self.selected is note:
            self.selected = None
            if self.notes:
                self.select(self.notes[-1])
        if not self.notes:
            self.panel.sync(None)
        self.save_all()

    def _notify(self, title, message, ms=6000, warning=False):
        try:
            self.tray.showMessage(
                title,
                message,
                QSystemTrayIcon.MessageIcon.Warning if warning
                else QSystemTrayIcon.MessageIcon.Information,
                ms,
            )
        except Exception:
            logging.exception("托盘通知失败")

    def reset_all(self):
        # 不用 panel 作父窗口：topmost Tool 的子模态框会跑到所有窗口后面，看起来像“卡住”
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("重置便利贴")
        box.setText("清空当前全部便签，恢复默认示例？")
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        box.button(QMessageBox.StandardButton.Yes).setText("重置")
        box.button(QMessageBox.StandardButton.No).setText("算了")
        box.setWindowModality(Qt.WindowModality.ApplicationModal)
        box.raise_()
        box.activateWindow()
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        for note in list(self.notes):
            note.hide()
            note.deleteLater()
        self.notes.clear()
        self.selected = None
        for item in store.DEFAULT_NOTES:
            self.create_note(dict(item), select=False, save=False)
        self.save_all()
        self.panel.sync(None)

    def show_all(self):
        for note in self.notes:
            note.show()

    def hide_all(self):
        for note in self.notes:
            note.hide()

    def set_all_layer(self, on_top):
        for note in self.notes:
            note.pinned = bool(on_top)
            note._apply_zorder()
            note.title.sync_state()
        self.save_all()
        self.panel.sync(self.selected)

    # ---------- 保存 ----------
    def schedule_save(self):
        self._save_timer.start()

    def save_all(self):
        try:
            store.save([note.to_dict() for note in self.notes])
            self._save_error_shown = False
        except Exception as exc:
            logging.exception("保存便签失败")
            if not self._save_error_shown:
                self._save_error_shown = True
                self._notify(
                    "便签保存失败",
                    "这次修改没能写到磁盘：%s\n内容还在内存里，请检查磁盘空间或目录权限后再试。" % exc,
                    8000,
                    warning=True,
                )

    def _load_notes(self):
        data, status = store.load()
        if status == "recovered":
            self._notify(
                "存档已从备份恢复",
                "上次写入可能没有完成，已回滚到上一版内容，请检查是否有少量丢失。",
                8000,
                warning=True,
            )
        elif status == "corrupt":
            self._notify(
                "存档损坏",
                "读不出 notes.json，已隔离为 notes.json.corrupt。可从托盘「重置便签」恢复示例，"
                "或把 .corrupt 文件发给维护者尝试修复。",
                12000,
                warning=True,
            )

        if status == "missing":
            # 首次运行才放示例；用户把便签删光后重启就是干净的桌面
            for item in store.DEFAULT_NOTES:
                self.create_note(dict(item), select=False, save=False)
            self.save_all()
        else:
            for item in data:
                self.create_note(dict(item), select=False, save=False)
        if not store.layer_defaulted():
            # 一次性迁移：老存档里的“置顶”统一改成默认贴桌面（用户要的默认层级）
            for note in self.notes:
                note.pinned = False
                note._apply_zorder()
                note.title.sync_state()
            store.mark_layer_defaulted()
            self.save_all()
            self._migrated_now = True
        self.panel.sync(None)

    # ---------- 托盘 ----------
    def _build_tray(self):
        self.tray = QSystemTrayIcon(make_icon(), self.app)
        self.tray.setToolTip("桌面便利贴")
        menu = QMenu()

        act_new = menu.addAction("新建便签")
        act_new.triggered.connect(self.new_note)
        act_show = menu.addAction("显示全部")
        act_show.triggered.connect(self.show_all)
        act_hide = menu.addAction("隐藏全部")
        act_hide.triggered.connect(self.hide_all)
        act_top = menu.addAction("全部置顶（浮到前面）")
        act_top.triggered.connect(lambda: self.set_all_layer(True))
        act_bottom = menu.addAction("全部贴桌面")
        act_bottom.triggered.connect(lambda: self.set_all_layer(False))
        menu.addSeparator()

        sound_menu = menu.addMenu("音效")
        self.act_sound = sound_menu.addAction("启用音效")
        self.act_sound.setCheckable(True)
        self.act_sound.setChecked(self.sounds.enabled)
        self.act_sound.triggered.connect(self.toggle_sound)
        sound_menu.addSeparator()
        sound_menu.addAction("选择拖动音效…").triggered.connect(
            lambda: self.choose_sound("snap")
        )
        sound_menu.addAction("选择落纸音效…").triggered.connect(
            lambda: self.choose_sound("drop")
        )
        sound_menu.addAction("恢复默认音效").triggered.connect(self.reset_sounds)
        menu.aboutToShow.connect(self._sync_tray_menu)
        menu.addSeparator()

        self.act_panel = menu.addAction("显示控制条")
        self.act_panel.setCheckable(True)
        self.act_panel.setChecked(True)
        self.act_panel.triggered.connect(self._toggle_panel)
        menu.addSeparator()

        act_reset = menu.addAction("重置便签")
        act_reset.triggered.connect(self.reset_all)
        act_quit = menu.addAction("退出")
        act_quit.triggered.connect(self._quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _sync_tray_menu(self):
        self.act_sound.setChecked(self.sounds.enabled)

    def toggle_sound(self, on):
        on = bool(on)
        if on and not self.sounds.available:
            self._notify(
                "音效不可用",
                "音效文件无法生成或播放，请检查数据目录权限。",
                warning=True,
            )
            on = False
        self.sounds.enabled = on
        QSettings().setValue("sound", on)
        self.act_sound.setChecked(on)
        self.panel.sync_sound()

    def choose_sound(self, kind):
        label = sound.KIND_LABEL[kind]
        path, _ = QFileDialog.getOpenFileName(
            None, "选择%s音效" % label, "", "WAV 音频 (*.wav)"
        )
        if not path:
            return
        try:
            self.sounds.set_custom(kind, path)
        except Exception as exc:
            _message_box(
                QMessageBox.Icon.Warning,
                "音效格式不支持",
                "请选择 16 位 PCM 的 .wav 文件。\n\n%s" % exc,
            )
            return
        self._notify("音效已更新", "%s音效已换成：%s" % (label, os.path.basename(path)))
        self.panel.sync_sound()

    def reset_sounds(self):
        self.sounds.clear_custom("snap")
        self.sounds.clear_custom("drop")
        self._notify("音效已恢复默认", "已恢复为程序自带的轻量音效。")
        self.panel.sync_sound()

    def _toggle_panel(self, checked):
        if checked:
            self.panel.show()
            self._position_panel()
        else:
            self.panel.hide()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_all()
            self.panel.show()
            self._position_panel()

    def _notify_layer_migrated(self):
        try:
            self.tray.showMessage(
                "桌面便利贴",
                "便签已改为默认贴桌面。被窗口挡住时，右键托盘图标 →「全部置顶」。",
                QSystemTrayIcon.MessageIcon.Information,
                6000,
            )
        except Exception:
            pass

    def _quit(self):
        self.save_all()
        self.tray.hide()
        self.app.quit()


def _message_box(icon, title, text):
    box = QMessageBox(icon, title, text, QMessageBox.StandardButton.Ok)
    box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    box.setWindowModality(Qt.WindowModality.ApplicationModal)
    box.raise_()
    box.activateWindow()
    box.exec()


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("桌面便利贴")
    app.setApplicationVersion("1.1.1")
    app.setOrganizationName("StickyNotesTool")
    app.setQuitOnLastWindowClosed(False)

    try:
        store.ensure_dir()
    except OSError as exc:
        _message_box(
            QMessageBox.Icon.Critical,
            "桌面便利贴",
            "无法创建数据目录：\n%s\n\n请检查 %%APPDATA%% 的写入权限。" % exc,
        )
        return 1

    install_crash_handler()

    lock = QLockFile(os.path.join(store.APP_DIR, "app.lock"))
    lock.setStaleLockTime(30000)
    if not lock.tryLock(800):
        _message_box(
            QMessageBox.Icon.Information,
            "桌面便利贴",
            "已经有一个便利贴在运行啦。\n请从任务栏托盘图标打开它。",
        )
        return 0
    app._lock = lock

    try:
        manager = Manager(app)
    except Exception as exc:
        logging.exception("启动失败")
        _message_box(
            QMessageBox.Icon.Critical,
            "桌面便利贴",
            "启动失败：%s\n\n日志已写入：%s" % (exc, os.path.join(store.APP_DIR, "app.log")),
        )
        return 1
    app._manager = manager
    app.aboutToQuit.connect(manager.save_all)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
