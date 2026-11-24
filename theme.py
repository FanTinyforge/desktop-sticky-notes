# -*- coding: utf-8 -*-
"""视觉常量：纸色、标题条、字体、尺寸、阴影三态。"""

PAPER_DEFAULT = "#FFF4CF"
TAPE_DEFAULT = "#D9C893"

# 面板里的预设尺寸（纸张本体尺寸）
SIZES = [
    ("小 180×160", 180, 160),
    ("中 230×200", 230, 200),
    ("大 300×260", 300, 260),
]
SIZE_MAP = {label: (w, h) for label, w, h in SIZES}

FONTS = {
    "楷体": ["KaiTi", "STKaiti", "楷体", "Kaiti SC"],
    "宋体": ["SimSun", "宋体", "Songti SC"],
    "黑体": ["Microsoft YaHei", "微软雅黑", "PingFang SC"],
}
FONT_SIZE = 17          # 逻辑像素，默认字号
FONT_SIZES = (12, 13, 14, 16, 17, 18, 20, 22, 24, 26, 28)
TEXT_DEFAULT = "#33322C"  # 正文字体默认颜色
TITLE_DEFAULT = "待办事项"  # 胶带条默认标题，可双击修改
TITLE_MAX = 40
TITLE_FONT_SIZE = 12       # 标题字默认字号（逻辑像素）
TITLE_FONT_SIZES = (10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28)
TITLE_COLOR_DEFAULT = "#483626"  # 标题字默认颜色
PAPER_ALPHA = 0.94      # 纸张轻微透光
TITLE_H = 26            # 标题条最小高度；实际高度跟标题字号走
MARGIN = 32             # 窗口为阴影预留的透明边距（略大于最大阴影外扩，避免被窗口切平）
RADIUS = 6

PANEL_W = 920
PANEL_H = 128


def title_height(font_size):
    """胶带条高度跟着标题字号走，最小保持原高度。"""
    return max(TITLE_H, int(font_size) + 12)

# 三态阴影：(模糊半径, 向下偏移, 不透明度)
# 控制在 MARGIN 以内，拖动时不再每帧重建高斯模糊
SHADOW_REST = (10.0, 4.0, 0.15)
SHADOW_HOVER = (16.0, 8.0, 0.21)
SHADOW_DRAG = (22.0, 10.0, 0.30)

PANEL_BG = (28, 32, 40, 221)
