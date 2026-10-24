"""Standalone, in-memory Qt hub prototype. No real tasks or timers are modified.

Run: python -m prototypes.qt_hub
Screenshot: QT_QPA_PLATFORM=offscreen python -m prototypes.qt_hub --screenshot hub.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

INK = '#554a60'
SAGE = '#8a75a0'
AVATAR = Path(__file__).resolve().parents[1] / 'assets/ui/app-icon.png'


def icon(name: str, color: str = SAGE) -> QIcon:
    """Small drawn icons, independent of emoji fonts and external assets."""
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(2, 2)
    painter.setPen(QPen(QColor(color), 1.7, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if name == 'home':
        path = QPainterPath()
        path.moveTo(3, 10); path.lineTo(12, 3); path.lineTo(21, 10)
        path.moveTo(5, 9); path.lineTo(5, 21); path.lineTo(19, 21); path.lineTo(19, 9)
        path.moveTo(9, 21); path.lineTo(9, 14); path.lineTo(15, 14); path.lineTo(15, 21)
        painter.drawPath(path)
    elif name == 'clock':
        painter.drawEllipse(QRectF(3, 3, 18, 18))
        painter.drawLine(12, 6, 12, 12); painter.drawLine(12, 12, 16, 14)
    elif name == 'check':
        painter.drawRoundedRect(QRectF(3, 3, 18, 18), 5, 5)
        painter.drawLine(7, 12, 10, 15); painter.drawLine(10, 15, 17, 8)
    elif name == 'heart':
        path = QPainterPath()
        path.moveTo(12, 20)
        path.cubicTo(2, 14, 1, 7, 6, 5)
        path.cubicTo(9, 4, 11, 6, 12, 8)
        path.cubicTo(13, 6, 15, 4, 18, 5)
        path.cubicTo(23, 7, 22, 14, 12, 20)
        painter.drawPath(path)
    elif name == 'leaf':
        path = QPainterPath()
        path.moveTo(5, 20); path.cubicTo(3, 5, 13, 3, 21, 3)
        path.cubicTo(21, 14, 16, 20, 5, 20)
        painter.drawPath(path)
        painter.drawLine(5, 20, 16, 8)
    elif name == 'close':
        painter.drawLine(7, 7, 17, 17); painter.drawLine(17, 7, 7, 17)
    else:
        painter.drawEllipse(QRectF(5, 5, 14, 14))
        painter.drawLine(12, 1, 12, 3); painter.drawLine(12, 21, 12, 23)
        painter.drawLine(1, 12, 3, 12); painter.drawLine(21, 12, 23, 12)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


def label(text: str, kind: str = '', wrap: bool = True) -> QLabel:
    item = QLabel(text)
    item.setWordWrap(wrap)
    item.setProperty('kind', kind)
    item.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return item


def button(text: str, symbol: str, primary: bool = False) -> QPushButton:
    item = QPushButton(icon(symbol, '#ffffff' if primary else SAGE), text)
    item.setIconSize(QSize(20, 20))
    item.setMinimumHeight(42)
    item.setCursor(Qt.CursorShape.PointingHandCursor)
    item.setProperty('primary', primary)
    item.setAccessibleName(text)
    return item


def card() -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName('card')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 14, 18, 14)
    layout.setSpacing(8)
    return frame, layout


class CompanionCorner(QFrame):
    """A little inhabited corner, using Xiaoxi's existing clean, high-resolution app portrait."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(190)
        self.setObjectName('companionCorner')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        status = label('小汐在家  ·  陪伴中', 'eyebrow')
        layout.addWidget(status)
        row = QHBoxLayout()
        row.setSpacing(16)
        portrait = QLabel()
        portrait.setFixedSize(96, 100)
        portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        portrait.setPixmap(QPixmap(str(AVATAR)).scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio,
                                                      Qt.TransformationMode.SmoothTransformation))
        portrait.setAccessibleName('小汐的原版白发小龙娘头像')
        # Reuse the clean rounded-square icon whole: do not crop horns or
        # recolor dark character details to remove the old avatar black matte.
        row.addWidget(portrait)
        self.bubble = label('你回来啦！\n要不要先陪我坐一会儿？')
        self.bubble.setObjectName('speechBubble')
        self.bubble.setMinimumHeight(82)
        row.addWidget(self.bubble, 1)
        layout.addLayout(row)
        layout.addWidget(label('今天的小屋，也为你留了一点暖意。', 'muted'))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0, QColor('#f0eaf7'))
        gradient.setColorAt(1, QColor('#fff1e3'))
        painter.setPen(QPen(QColor('#e6ddeb'), 1))
        painter.setBrush(gradient)
        painter.drawRoundedRect(rect, 25, 25)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#e8def2'))
        painter.drawRoundedRect(QRectF(19, 47, 96, 111), 46, 46)
        painter.setBrush(QColor('#f9f4fd'))
        painter.drawEllipse(QRectF(22, 146, 93, 11))
        # Tiny window-light marks, not a stock dashboard illustration.
        painter.setPen(QPen(QColor('#c7b4d8'), 1.4, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        for x, y, radius in [(self.width()-28, 25, 4), (126, 54, 3), (27, 37, 2)]:
            painter.drawLine(x-radius, y, x+radius, y)
            painter.drawLine(x, y-radius, x, y+radius)


class HubPrototype(QWidget):
    """Alpha-composited window, fixed logical width bounded by working area."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle('小汐的小屋 · 界面原型（演示数据）')
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName('hubPrototype')
        self.demo_running = False
        self.drag_origin: QPoint | None = None
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(500, screen.width()), min(700, screen.height()))
        self.move(screen.x() + (screen.width() - self.width()) // 2,
                  screen.y() + (screen.height() - self.height()) // 2)
        self.setStyleSheet('''
            QWidget { color: #554a60; font-size: 14px; }
            QLabel { background: transparent; }
            QLabel[kind="title"] { font-size: 25px; font-weight: 700; }
            QLabel[kind="heading"] { font-size: 19px; font-weight: 600; }
            QLabel[kind="muted"] { color: #8b7f91; font-size: 12px; }
            QLabel[kind="timer"] { font-size: 46px; font-weight: 600; color: #8a75a0; }
            QLabel[kind="eyebrow"] { color: #927e9e; font-size: 12px; font-weight: 600; }
            QFrame#card { background: #fffdf9; border: 1px solid #ece1e4; border-radius: 20px; }
            QLabel#speechBubble { background: #fffcfa; border: 1px solid #f1e7ee; border-radius: 18px; padding: 12px; color: #745e82; font-size: 15px; }
            QFrame#note { background: #fff2e3; border: 1px solid #f1e2d2; border-radius: 18px; }
            QPushButton { background: #f4edf5; border: 1px solid transparent;
                border-radius: 12px; padding: 7px 12px; font-weight: 500; }
            QPushButton:hover { background: #ece1f1; }
            QPushButton:pressed { background: #e1d4e9; }
            QPushButton:focus { border: 2px solid #b698c9; }
            QPushButton:checked { background: #eadff1; color: #78608c; }
            QPushButton[primary="true"] { background: #947ba9; color: white; }
            QPushButton[primary="true"]:hover { background: #806695; }
            QScrollArea, QStackedWidget { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 6px; margin: 3px 0; }
            QScrollBar::handle:vertical { background: #d7c7dd; border-radius: 3px; min-height: 28px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        ''')
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        outer.setSpacing(16)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title_box.addWidget(label('小汐的小屋', 'title'))
        title_box.addWidget(label('欢迎回来，今天也一起慢慢来。', 'muted'))
        header.addLayout(title_box, 1)
        close = button('关闭', 'close')
        close.clicked.connect(self.close)
        close.setToolTip('关闭原型，不影响正在运行的桌宠')
        header.addWidget(close)
        outer.addLayout(header)
        tabs = QHBoxLayout()
        self.tab_group = QButtonGroup(self)
        for index, (text, symbol) in enumerate([('我的小屋', 'home'), ('陪我专注', 'clock')]):
            tab = button(text, symbol)
            tab.setCheckable(True)
            tab.setChecked(index == 0)
            self.tab_group.addButton(tab, index)
            tabs.addWidget(tab, 1)
        outer.addLayout(tabs)
        self.pages = QStackedWidget()
        self.pages.addWidget(self._today())
        self.pages.addWidget(self._focus())
        self.tab_group.idClicked.connect(self.pages.setCurrentIndex)
        outer.addWidget(self.pages, 1)
        self.feedback = label('界面原型 · 演示数据 · 不连接真实任务或提醒', 'muted')
        self.feedback.setMinimumHeight(34)
        outer.addWidget(self.feedback)

    def _page(self) -> tuple[QScrollArea, QVBoxLayout]:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName('pageContent')
        content.setStyleSheet('QWidget#pageContent { background: transparent; }')
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 4)
        layout.setSpacing(14)
        area.setWidget(content)
        return area, layout

    def _today(self) -> QScrollArea:
        page, layout = self._page()
        self.corner = CompanionCorner()
        layout.addWidget(self.corner)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        for text, symbol, response in [
            ('摸摸头', 'heart', '唔……是熟悉的你。\n再陪我一小会儿吧。'),
            ('打招呼', 'sun', '嗨，欢迎回家！\n今天有什么小小的开心事？'),
            ('歇一会', 'leaf', '那我们就安静坐一会儿。\n不用着急，我在这里。'),
        ]:
            action = button(text, symbol)
            action.clicked.connect(lambda checked=False, line=response: self.say_demo(line))
            actions.addWidget(action, 1)
        layout.addLayout(actions)
        note, content = card()
        note.setObjectName('note')
        content.addWidget(label('留给你的小纸条', 'heading'))
        content.addWidget(label('“喝一点水，伸个懒腰。\n忙的时候，也记得照顾好自己呀。”'))
        content.addWidget(label('小汐的碎碎念 · 示例', 'muted'))
        layout.addWidget(note)
        invitation = QHBoxLayout()
        wording = QVBoxLayout()
        wording.addWidget(label('有件小事想做完？', 'eyebrow'))
        wording.addWidget(label('我可以安静陪着你。', 'muted'))
        invitation.addLayout(wording, 1)
        start = button('一起专注', 'clock')
        start.clicked.connect(self.show_focus)
        invitation.addWidget(start)
        layout.addLayout(invitation)
        layout.addStretch()
        return page

    def say_demo(self, text):
        self.corner.bubble.setText(text)
        self.feedback.setText('互动文案演示 · 未触发真实人物动作或通知')

    def _focus(self) -> QScrollArea:
        page, layout = self._page()
        welcome = QHBoxLayout()
        avatar = QLabel()
        avatar.setPixmap(QPixmap(str(AVATAR)).scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio,
                                                    Qt.TransformationMode.SmoothTransformation))
        avatar.setAccessibleName('小汐在身边')
        welcome.addWidget(avatar)
        welcome.addWidget(label('我会轻轻的，不打扰你。\n做完这件小事，我们再聊。'), 1)
        layout.addLayout(welcome)
        panel, content = card()
        content.addWidget(label('陪你专心一小会儿', 'heading'))
        content.addWidget(label('读完一小节，记下一个收获', 'muted'))
        timer = label('25:00', 'timer')
        timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content.addWidget(timer)
        self.demo_button = button('开始专注 · 演示', 'clock', True)
        self.demo_button.clicked.connect(self.toggle_demo)
        content.addWidget(self.demo_button)
        content.addWidget(label('静态时间预览，不启动真实计时。', 'muted'))
        layout.addWidget(panel)
        note, content = card()
        note.setObjectName('note')
        content.addWidget(label('小汐的小约定', 'eyebrow'))
        content.addWidget(label('不必一下子做到完美。\n往前一点点，也值得开心。'))
        layout.addWidget(note)
        layout.addStretch()
        return page

    def show_focus(self):
        self.pages.setCurrentIndex(1)
        self.tab_group.button(1).setChecked(True)
        self.demo_button.setFocus()

    def toggle_demo(self):
        self.demo_running = not self.demo_running
        self.demo_button.setText('暂停专注 · 演示' if self.demo_running else '开始专注 · 演示')
        self.demo_button.setAccessibleName(self.demo_button.text())
        self.feedback.setText('已切换为专注中样式。没有启动计时器。' if self.demo_running
                              else '已切换为暂停样式。没有修改真实专注状态。')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # True per-pixel alpha: no magenta key and no hard-edged window mask.
        body = QRectF(self.rect()).adjusted(12, 10, -12, -14)
        painter.setPen(Qt.PenStyle.NoPen)
        for spread in range(10, 0, -1):
            painter.setBrush(QColor(64, 64, 64, 2 if spread > 4 else 3))
            painter.drawRoundedRect(body.adjusted(-spread, -spread + 3, spread, spread + 3),
                                    25 + spread, 25 + spread)
        painter.setBrush(QColor('#fffaf4'))
        painter.setPen(QPen(QColor('#eee2e7'), 1))
        painter.drawRoundedRect(body, 25, 25)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 100:
            self.drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_origin)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.drag_origin = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshot', type=Path, help='Save a real Qt render and exit')
    parser.add_argument('--page', choices=('today', 'focus'), default='today')
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    font = QFont()
    font.setFamilies(['Microsoft YaHei UI', 'Noto Sans CJK SC', 'sans-serif'])
    font.setPointSize(10)
    app.setFont(font)
    window = HubPrototype()
    if args.page == 'focus':
        window.show_focus()
    window.show()
    if args.screenshot:
        def capture():
            # Save alpha, not an opaque screenshot background.
            if not window.grab().save(str(args.screenshot)):
                print(f'Could not save screenshot: {args.screenshot}', file=sys.stderr)
                app.exit(1)
            else:
                app.quit()
        QTimer.singleShot(150, capture)
    result = app.exec()
    # Destroy widgets (and their QPixmaps) while QApplication still exists.
    # Python signal closures can otherwise defer widget teardown until shutdown.
    window.close()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return result


if __name__ == '__main__':
    raise SystemExit(main())
