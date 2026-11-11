"""Render the approved lettering as portable, high-resolution UI artwork."""
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parent.parent
SCALE = 3
PADDING = 8


def render(filename, text, family, size, spacing, color, height, alignment):
    if family not in QFontDatabase.families():
        raise RuntimeError(f"Regenerating this artwork requires the approved font: {family}")
    image = QImage(480 * SCALE, height * SCALE, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.scale(SCALE, SCALE)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    font = QFont(family)
    font.setPixelSize(size)
    font.setWeight(QFont.Weight.Normal)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    painter.setFont(font)
    painter.setPen(QColor(color))
    painter.drawText(QRectF(PADDING, PADDING, 464, height - 2 * PADDING), alignment, text)
    painter.end()
    target = ROOT / "assets" / filename
    if not image.save(str(target)):
        raise RuntimeError(f"Could not write {target}")
    print(target)


if __name__ == "__main__":
    app = QApplication([])
    title_alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
    render("headline-first.png", "越练，", "演示流云楷", 109, -109 * 0.025, "#34523c", 180, title_alignment)
    render("headline-second.png", "越懂你", "演示流云楷", 109, -109 * 0.025, "#34523c", 180, title_alignment)
    render("subtitle.png", "你的鸿蒙 AI 健身私教", "方正风雅宋简体", 29, 1.0, "#667763", 64,
           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
