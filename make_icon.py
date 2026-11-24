import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

pm = QPixmap(256, 256)
pm.fill(Qt.transparent)
p = QPainter(pm)
p.setRenderHint(QPainter.Antialiasing)

# 投影
p.setPen(Qt.NoPen)
p.setBrush(QColor(0, 0, 0, 26))
p.drawRoundedRect(QRectF(30, 42, 200, 194), 18, 18)

# 纸面
p.setBrush(QColor("#FFF4CF"))
p.setPen(QPen(QColor("#E8DDB4"), 2))
p.drawRoundedRect(QRectF(26, 30, 200, 196), 18, 18)

# 标题条
p.setPen(Qt.NoPen)
p.setBrush(QColor("#D9C893"))
p.drawRoundedRect(QRectF(26, 30, 200, 40), 18, 18)
p.drawRect(QRectF(26, 54, 200, 16))

# 文字线
p.setBrush(QColor("#9A8B70"))
for i, w in enumerate((150, 168, 132)):
    p.drawRoundedRect(QRectF(48, 96 + i * 30, w, 9), 4.5, 4.5)

# 右下折角
p.setBrush(QColor("#F0E0A8"))
p.setPen(QPen(QColor("#E0D2A0"), 1))
p.drawPolygon(
    QPolygonF([
        QPointF(226, 200),
        QPointF(226, 226),
        QPointF(200, 226),
    ])
)

p.end()
from pathlib import Path
out = Path(__file__).with_name("app_icon.png")
pm.save(str(out))
print(f"icon png saved: {out}")
