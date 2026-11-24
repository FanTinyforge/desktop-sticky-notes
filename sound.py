# -*- coding: utf-8 -*-
"""程序合成的轻量拖动 / 落纸音效；支持用户替换成自己的 wav。"""
import logging
import math
import os
import random
import shutil
import struct
import wave

from PySide6.QtCore import QSettings, QUrl

from store import APP_DIR

SR = 44100

DEFAULT_FILES = {
    "snap": "snap_default_v2.wav",
    "drop": "drop_default_v2.wav",
}
CUSTOM_FILES = {
    "snap": "snap_custom.wav",
    "drop": "drop_custom.wav",
}
KIND_LABEL = {"snap": "拖动", "drop": "落纸"}


def _settings():
    # 与 main.py 里 setOrganizationName / setApplicationName 保持一致
    return QSettings("StickyNotesTool", "桌面便利贴")


def _write_wav(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = bytearray()
        for s in samples:
            v = int(max(-1.0, min(1.0, s)) * 32000)
            frames += struct.pack("<h", v)
        w.writeframes(bytes(frames))


def _normalize(buf, amp):
    peak = max(abs(v) for v in buf) or 1.0
    return [v / peak * amp for v in buf]


def _fade_edges(buf, ms=3):
    """首尾各淡入淡出几毫秒，避免扬声器里出现“啪”的爆音。"""
    k = min(len(buf) // 2, int(SR * ms / 1000.0))
    if k <= 0:
        return buf
    for i in range(k):
        g = i / float(k)
        buf[i] *= g
        buf[-1 - i] *= g
    return buf


def _make_snap():
    """纸张轻推的沙沙声 + 一声很轻的木质“嗒”，比旧版的高频咔嚓柔和。"""
    n = int(SR * 0.16)
    buf = [0.0] * n
    rnd = random.Random(7)

    # 两级低通后的带限噪声：像纸面摩擦，而不是电流杂音
    lp1 = lp2 = 0.0
    a = 0.10
    tail = int(SR * 0.145)
    for i in range(tail):
        x = rnd.uniform(-1, 1)
        lp1 += a * (x - lp1)
        lp2 += a * (lp1 - lp2)
        if i < int(SR * 0.012):
            env = i / (SR * 0.012)
        else:
            env = math.exp(-(i - SR * 0.012) / (SR * 0.050))
        buf[i] += (lp1 - lp2) * env * 0.60

    # 轻“嗒”：880Hz 迅速衰减，给一点“拿起纸”的落点感
    off = int(SR * 0.020)
    L2 = int(SR * 0.055)
    for i in range(L2):
        t = i / SR
        buf[off + i] += math.sin(2.0 * math.pi * 880.0 * t) * math.exp(-t * 55.0) * 0.16

    buf = _fade_edges(buf, 4)
    return _normalize(buf, 0.32)


def _make_drop():
    """松手落纸：一声更低的闷响，没有尖锐噪声。"""
    n = int(SR * 0.12)
    buf = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / SR
        f = 150.0 * math.exp(-t * 20.0) + 80.0
        phase += 2.0 * math.pi * f / SR
        env = math.exp(-t * 38.0)
        buf[i] += math.sin(phase) * env * 0.70

    # 极轻的一层纸面接触噪声
    rnd = random.Random(13)
    for i in range(int(SR * 0.006)):
        env = (1.0 - i / (SR * 0.006)) ** 2
        buf[i] += rnd.uniform(-1, 1) * env * 0.05

    buf = _fade_edges(buf, 3)
    return _normalize(buf, 0.28)


def _valid_wav(path, strict=False):
    """strict=True 用于程序自带音效；自定义只要求 16 位 PCM。"""
    try:
        with wave.open(path, "rb") as w:
            channels = w.getnchannels()
            width = w.getsampwidth()
            rate = w.getframerate()
            frames = w.getnframes()
            if frames <= 0 or width != 2:
                return False
            if strict:
                return channels == 1 and rate == SR
            return channels in (1, 2) and rate >= 8000
    except Exception:
        return False


def ensure_sounds():
    """生成/校验程序自带的两个默认音效，返回 {kind: path}。"""
    os.makedirs(APP_DIR, exist_ok=True)
    paths = {}
    for kind, filename in DEFAULT_FILES.items():
        path = os.path.join(APP_DIR, filename)
        if not _valid_wav(path, strict=True):
            if kind == "snap":
                _write_wav(path, _make_snap())
            else:
                _write_wav(path, _make_drop())
        paths[kind] = path
    return paths


def custom_path(kind):
    return os.path.join(APP_DIR, CUSTOM_FILES[kind])


def custom_enabled(kind):
    return bool(_settings().value("sound_%s_custom" % kind, False, type=bool))


class SoundPlayer:
    def __init__(self, enabled=True):
        self._defaults = {}
        self._paths = {}
        self._effects = {}
        self._winsound = None
        self.available = False
        try:
            self._defaults = ensure_sounds()
            for kind in ("snap", "drop"):
                candidate = custom_path(kind)
                if custom_enabled(kind) and _valid_wav(candidate):
                    self._paths[kind] = candidate
                else:
                    self._paths[kind] = self._defaults[kind]
            self.available = all(_valid_wav(p) for p in self._paths.values())
        except Exception:
            logging.exception("音效初始化失败，本次静音运行")

        self.enabled = bool(enabled and self.available)
        self._load_backend()

    def _load_backend(self):
        self._effects = {}
        self._winsound = None
        try:
            from PySide6.QtMultimedia import QSoundEffect

            for kind, path in self._paths.items():
                if not _valid_wav(path):
                    continue
                effect = QSoundEffect()
                effect.setSource(QUrl.fromLocalFile(path))
                effect.setVolume(0.8)
                effect.load()
                self._effects[kind] = effect
        except Exception:
            self._effects = {}

        if not self._effects:
            try:
                import winsound

                self._winsound = winsound
            except Exception:
                logging.exception("winsound 不可用，本次静音运行")
                self._winsound = None

    def set_custom(self, kind, source):
        if kind not in CUSTOM_FILES:
            raise ValueError("unknown sound kind")
        if not _valid_wav(source):
            raise ValueError("不是 16 位 PCM 的 wav 文件")
        target = custom_path(kind)
        if os.path.abspath(source) != os.path.abspath(target):
            shutil.copyfile(source, target)
        settings = _settings()
        settings.setValue("sound_%s_custom" % kind, True)
        settings.sync()
        self._paths[kind] = target
        self._load_backend()

    def clear_custom(self, kind):
        if kind not in CUSTOM_FILES:
            return
        try:
            os.remove(custom_path(kind))
        except OSError:
            pass
        settings = _settings()
        settings.setValue("sound_%s_custom" % kind, False)
        settings.sync()
        if self._defaults:
            self._paths[kind] = self._defaults[kind]
        self._load_backend()

    def play(self, name):
        if not self.enabled or not self.available:
            return
        effect = self._effects.get(name)
        if effect is not None:
            effect.play()
            return
        if self._winsound:
            path = self._paths.get(name)
            if not path:
                return
            try:
                self._winsound.PlaySound(
                    path,
                    self._winsound.SND_FILENAME
                    | self._winsound.SND_ASYNC
                    | self._winsound.SND_NODEFAULT,
                )
            except Exception:
                logging.exception("播放音效失败")
