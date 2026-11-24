# -*- coding: utf-8 -*-
r"""便签数据持久化：%APPDATA%\StickyNotesTool\notes.json，带上一版备份。

读取原则（宁可提示，也不静默清空用户数据）：
1) 主文件能解析且结构合法 -> 用它；
2) 主文件损坏 -> 隔离为 notes.json.corrupt，回退 notes.json.bak；
3) 两份都不可用 -> 返回空列表 + "corrupt" 状态，由界面提示用户，不装作首次启动。
"""
import json
import os
import re
import shutil

import theme

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "StickyNotesTool")
NOTES_FILE = os.path.join(APP_DIR, "notes.json")
LAYER_MARK = os.path.join(APP_DIR, "default-bottom-v1")

COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def ensure_dir():
    os.makedirs(APP_DIR, exist_ok=True)


def layer_defaulted():
    """是否已经把老存档统一改成“默认贴桌面”。"""
    return os.path.exists(LAYER_MARK)


def mark_layer_defaulted():
    ensure_dir()
    try:
        with open(LAYER_MARK, "w", encoding="utf-8") as f:
            f.write("bottom")
    except Exception:
        pass


def exists():
    """存档是否存在（区别于“存在但是空列表”：用户把便签全删光后不该再塞回示例）。"""
    return os.path.exists(NOTES_FILE)


def _num(item, key, default, lo, hi):
    try:
        value = int(float(item.get(key, default)))
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, value))


def _opacity(value):
    """兼容两种历史格式：0.3~1.0 的小数，以及 30~100 的百分比。"""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 1.0
    if value > 1.0:
        value /= 100.0
    return max(0.3, min(1.0, value))


def _tobool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _color(value, default):
    return value if isinstance(value, str) and COLOR_RE.match(value) else default


def _normalize(item):
    """把任意来源的存档条目收敛成 NoteWindow 能安全消费的结构。"""
    text = item.get("text", "")
    if not isinstance(text, str):
        text = "" if text is None else str(text)

    font = item.get("font", "楷体")
    if font not in theme.FONTS:
        font = "楷体"

    title = item.get("title", theme.TITLE_DEFAULT)
    if not isinstance(title, str):
        title = theme.TITLE_DEFAULT
    title = title.strip().replace("\r", " ").replace("\n", " ")[: theme.TITLE_MAX]
    if not title and "title" not in item:
        title = theme.TITLE_DEFAULT

    text_html = item.get("text_html", "")
    if not isinstance(text_html, str):
        text_html = ""

    return dict(
        x=_num(item, "x", 200, -20000, 20000),
        y=_num(item, "y", 120, -20000, 20000),
        w=_num(item, "w", 230, 150, 720),
        h=_num(item, "h", 200, 120, 820),
        paper=_color(item.get("paper"), theme.PAPER_DEFAULT),
        tape=_color(item.get("tape"), theme.TAPE_DEFAULT),
        font=font,
        font_size=_num(item, "font_size", theme.FONT_SIZE, 10, 36),
        font_color=_color(item.get("font_color"), theme.TEXT_DEFAULT),
        title=title,
        title_font_size=_num(
            item, "title_font_size", theme.TITLE_FONT_SIZE, 10, 28
        ),
        title_color=_color(item.get("title_color"), theme.TITLE_COLOR_DEFAULT),
        pinned=_tobool(item.get("pinned", False)),
        collapsed=_tobool(item.get("collapsed", False)),
        opacity=_opacity(item.get("opacity", 1.0)),
        text=text,
        text_html=text_html,
    )


def _read_items(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("top-level value is not a list")
    items = [_normalize(x) for x in data if isinstance(x, dict)]
    # 单条损坏不应拖垮整份存档；这里只跳过非字典项
    return items


def _quarantine(path):
    """损坏的主文件改名留证，绝不直接删掉用户数据。"""
    try:
        os.replace(path, path + ".corrupt")
    except OSError:
        pass


def load():
    """返回 (items, status)，status: ok / recovered / corrupt / missing。"""
    had_any = os.path.exists(NOTES_FILE) or os.path.exists(NOTES_FILE + ".bak")
    for path, status in ((NOTES_FILE, "ok"), (NOTES_FILE + ".bak", "recovered")):
        if not os.path.exists(path):
            continue
        try:
            return _read_items(path), status
        except Exception:
            if status == "ok":
                _quarantine(NOTES_FILE)
            continue
    return [], ("corrupt" if had_any else "missing")


def save(items):
    """原子写：先写 .tmp 并落盘，再把旧版留成 .bak，最后整体替换。"""
    ensure_dir()
    data = json.dumps(items, ensure_ascii=False, indent=1)
    tmp = NOTES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())

    if os.path.exists(NOTES_FILE):
        try:
            shutil.copyfile(NOTES_FILE, NOTES_FILE + ".bak")
        except OSError:
            # 备份失败不阻塞主流程，但主文件仍然会原子替换
            pass
    os.replace(tmp, NOTES_FILE)


DEFAULT_NOTES = [
    dict(x=150, y=70, w=230, h=190, paper="#FFF4CF", tape="#D9C893", font="楷体", pinned=False,
         text="请不要修改我桌面上的任何文件！！\n也不要碰我的电脑！！"),
    dict(x=520, y=88, w=250, h=180, paper="#F8DCDC", tape="#D9A7A7", font="楷体", pinned=False,
         text="1. 5点前把会议报告发给组长！\n2. 记得回复甲方邮件！！\n3. 2点开会千万不能迟到！"),
    dict(x=305, y=300, w=240, h=190, paper="#E4E4DC", tape="#B9BCB4", font="楷体", pinned=False,
         text="记得定期清理回收站。\n老是莫名其妙出现奇怪的垃圾文件，\n导致 C 盘都快炸了！！！"),
    dict(x=760, y=330, w=230, h=185, paper="#E7EEC4", tape="#BDC89A", font="楷体", pinned=False,
         text="操作说明\n左键拖动标题条 → 移动\n双击正文 → 编辑\n右下角 → 调整大小\n右键 → 更多"),
]
